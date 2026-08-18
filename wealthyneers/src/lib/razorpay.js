// ─── Razorpay Checkout Helper (Recurring Subscriptions & Standard Orders) ───
import { supabase } from '@/lib/supabase';

let sdkLoadPromise = null;

/**
 * Robustly loads Razorpay Checkout SDK script with timeout protection and deduping.
 * Never hangs indefinitely.
 */
export function loadRazorpaySDK() {
  if (typeof window === 'undefined') {
    return Promise.resolve(false);
  }

  if (window.Razorpay) {
    return Promise.resolve(true);
  }

  if (sdkLoadPromise) {
    return sdkLoadPromise;
  }

  sdkLoadPromise = new Promise((resolve) => {
    // 1. Double-check if Razorpay is already available
    if (window.Razorpay) {
      resolve(true);
      return;
    }

    // 2. Check if script tag is already in DOM
    const existingScript = document.querySelector('script[src*="checkout.razorpay.com"]');
    if (existingScript) {
      // Poll every 50ms for up to 4000ms
      let elapsed = 0;
      const interval = setInterval(() => {
        elapsed += 50;
        if (window.Razorpay) {
          clearInterval(interval);
          resolve(true);
        } else if (elapsed >= 4000) {
          clearInterval(interval);
          resolve(!!window.Razorpay);
        }
      }, 50);
      return;
    }

    // 3. Create and inject script tag with 4s timeout protection
    let finished = false;
    const timeout = setTimeout(() => {
      if (!finished) {
        finished = true;
        resolve(!!window.Razorpay);
      }
    }, 4000);

    const script = document.createElement('script');
    script.src = 'https://checkout.razorpay.com/v1/checkout.js';
    script.async = true;
    script.onload = () => {
      if (!finished) {
        finished = true;
        clearTimeout(timeout);
        resolve(true);
      }
    };
    script.onerror = () => {
      if (!finished) {
        finished = true;
        clearTimeout(timeout);
        resolve(false);
      }
    };

    (document.head || document.body || document.documentElement).appendChild(script);
  });

  return sdkLoadPromise;
}

/**
 * Initiates Razorpay checkout for Wealthyneers Monthly Membership (₹30/month).
 * Supports both recurring subscription flow and standard order fallback.
 *
 * @param {Object} params
 * @param {Object} params.user - Authenticated Supabase user object { id, email, user_metadata }
 * @param {Function} [params.onOpen] - Callback when checkout modal successfully opens
 * @param {Function} [params.onSuccess] - Callback on verified subscription completion
 * @param {Function} [params.onError] - Callback on error
 * @param {Function} [params.onDismiss] - Callback when user closes payment modal
 */
export async function startRazorpayCheckout({
  user,
  onOpen,
  onSuccess,
  onError,
  onDismiss,
}) {
  if (!user || !user.id) {
    if (onError) onError('User session not found. Please log in first.');
    return;
  }

  try {
    // 1. Eagerly start loading the SDK concurrently with server request
    const sdkPromise = loadRazorpaySDK();

    // 2. Obtain current authenticated Supabase session JWT
    let { data: { session } } = await supabase.auth.getSession();
    if (!session?.access_token) {
      // Retry once to ensure token sync
      const refreshed = await supabase.auth.refreshSession();
      session = refreshed.data?.session;
    }

    const token = session?.access_token;
    if (!token) {
      throw new Error('Active user session not found. Please log in again.');
    }

    // 3. Request subscription creation from backend
    let subData = null;
    let isSubscriptionMode = true;

    const subRes = await fetch('/api/create-subscription', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    subData = await subRes.json();

    if (!subRes.ok) {
      if (subData.code === 'ALREADY_SUBSCRIBED') {
        throw new Error('You already have an active subscription.');
      }

      // If subscription endpoint returned configuration or generic error, try fallback order endpoint
      console.warn('[razorpay-checkout] Subscription creation failed, trying order endpoint...', subData.error);
      const orderRes = await fetch('/api/create-order', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
      });

      const orderData = await orderRes.json();
      if (!orderRes.ok) {
        throw new Error(subData.error || orderData.error || 'Failed to initiate payment.');
      }

      subData = orderData;
      isSubscriptionMode = false;
    }

    const subscriptionId = subData.subscriptionId || subData.subscription_id;
    const orderId = subData.orderId || subData.order_id || subData.id;
    const keyId = subData.keyId || subData.key_id || process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID;

    if (!keyId || (!subscriptionId && !orderId)) {
      throw new Error('Invalid payment configuration returned from server.');
    }

    // 4. Ensure Razorpay SDK is ready
    const isSdkLoaded = await sdkPromise;
    if (!isSdkLoaded || typeof window === 'undefined' || !window.Razorpay) {
      throw new Error('Unable to load Razorpay payment SDK. Please check your network or disable ad-blockers and try again.');
    }

    // 5. Configure Razorpay Checkout Options
    const options = {
      key: keyId,
      name: 'Wealthyneers',
      description: 'Wealthyneers Monthly Subscription — ₹30/month',
      image: '/wealthyneers-logo.png',
      amount: subData.amount || 3000,
      currency: subData.currency || 'INR',
      prefill: {
        email: user.email || '',
        name: user.user_metadata?.full_name || '',
      },
      theme: {
        color: '#0A4D68',
      },
      handler: async function (response) {
        try {
          // Re-fetch active session token
          const { data: { session: freshSession } } = await supabase.auth.getSession();
          const activeToken = freshSession?.access_token || token;

          // Determine verification endpoint
          const endpoint = isSubscriptionMode && (response.razorpay_subscription_id || subscriptionId)
            ? '/api/verify-subscription'
            : '/api/verify-payment';

          const verifyRes = await fetch(endpoint, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${activeToken}`,
            },
            body: JSON.stringify({
              razorpay_subscription_id: response.razorpay_subscription_id || subscriptionId || null,
              razorpay_order_id: response.razorpay_order_id || orderId || null,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature: response.razorpay_signature,
            }),
          });

          const verifyData = await verifyRes.json();
          if (!verifyRes.ok || !verifyData.success) {
            throw new Error(verifyData.error || 'Payment verification failed.');
          }

          if (onSuccess) {
            onSuccess(verifyData.subscription);
          }
        } catch (verifyErr) {
          console.error('[razorpay-checkout] Verification error:', verifyErr);
          if (onError) onError(verifyErr.message || 'Payment verification failed.');
        }
      },
      modal: {
        ondismiss: function () {
          if (onDismiss) onDismiss();
        },
      },
    };

    // Attach subscription_id for recurring subscriptions or order_id for one-time orders
    if (isSubscriptionMode && subscriptionId) {
      options.subscription_id = subscriptionId;
    } else if (orderId) {
      options.order_id = orderId;
    }

    const rzp = new window.Razorpay(options);

    rzp.on('payment.failed', function (response) {
      console.error('[razorpay-checkout] Payment failed:', response.error);
      if (onError) {
        onError(response.error.description || 'Payment was declined or failed.');
      }
    });

    // Notify UI that checkout modal is now opening (resets loading state)
    if (onOpen) onOpen();

    rzp.open();
  } catch (err) {
    console.error('[razorpay-checkout] Initiation error:', err);
    if (onError) {
      onError(err.message || 'Could not start payment checkout.');
    }
  }
}
