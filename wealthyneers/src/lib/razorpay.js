// ─── Razorpay Checkout Helper (UPI, Cards, Netbanking) ──────────────────
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
    if (window.Razorpay) {
      resolve(true);
      return;
    }

    let finished = false;
    const finish = (result) => {
      if (!finished) {
        finished = true;
        clearTimeout(timeout);
        if (!result) {
          sdkLoadPromise = null; // Reset to allow retry if failed
        }
        resolve(result);
      }
    };

    const timeout = setTimeout(() => {
      finish(!!window.Razorpay);
    }, 4000);

    const existingScript = document.querySelector('script[src*="checkout.razorpay.com"]');
    if (existingScript) {
      existingScript.addEventListener('load', () => finish(true));
      existingScript.addEventListener('error', () => finish(false));
      let elapsed = 0;
      const interval = setInterval(() => {
        elapsed += 50;
        if (window.Razorpay) {
          clearInterval(interval);
          finish(true);
        } else if (elapsed >= 3500) {
          clearInterval(interval);
          finish(!!window.Razorpay);
        }
      }, 50);
      return;
    }

    const script = document.createElement('script');
    script.src = 'https://checkout.razorpay.com/v1/checkout.js';
    script.async = true;
    script.onload = () => finish(true);
    script.onerror = () => finish(false);
    (document.head || document.body || document.documentElement).appendChild(script);
  });

  return sdkLoadPromise;
}

/**
 * Initiates Razorpay checkout for Wealthyneers 30-Day Institutional Access (₹30 for 30 days).
 * Full UPI, QR Code, Card, and Netbanking support.
 *
 * @param {Object} params
 * @param {Object} params.user - Authenticated Supabase user object { id, email, user_metadata }
 * @param {Function} [params.onOpen] - Callback when checkout modal successfully opens
 * @param {Function} [params.onSuccess] - Callback on verified payment completion
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
      const refreshed = await supabase.auth.refreshSession();
      session = refreshed.data?.session;
    }

    const token = session?.access_token;
    if (!token) {
      throw new Error('Active user session not found. Please log in again.');
    }

    // 3. Create server-side order with JWT authorization
    const orderRes = await fetch('/api/create-order', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const orderData = await orderRes.json();

    if (!orderRes.ok) {
      if (orderData.code === 'ALREADY_SUBSCRIBED') {
        throw new Error('You already have active access.');
      }
      throw new Error(orderData.error || 'Failed to initiate payment.');
    }

    const orderId = orderData.orderId || orderData.order_id || orderData.id;
    const keyId = orderData.keyId || orderData.key_id || process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID;

    if (!orderId || !keyId) {
      throw new Error('Invalid payment configuration returned from server.');
    }

    // 4. Ensure Razorpay SDK is ready
    const isSdkLoaded = await sdkPromise;
    if (!isSdkLoaded || typeof window === 'undefined' || !window.Razorpay) {
      throw new Error('Unable to load Razorpay payment SDK. Please check your network connection.');
    }

    // 5. Configure Razorpay Standard Checkout Options (UPI, Cards, Netbanking)
    const options = {
      key: keyId,
      order_id: orderId,
      amount: orderData.amount || 3000,
      currency: orderData.currency || 'INR',
      name: 'Wealthyneers',
      description: 'Wealthyneers 30-Day Access — ₹30',
      image: '/wealthyneers-logo.png',
      prefill: {
        email: user.email || '',
        name: user.user_metadata?.full_name || '',
      },
      theme: {
        color: '#0A4D68',
      },
      handler: async function (response) {
        try {
          const { data: { session: freshSession } } = await supabase.auth.getSession();
          const activeToken = freshSession?.access_token || token;

          const verifyRes = await fetch('/api/verify-payment', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${activeToken}`,
            },
            body: JSON.stringify({
              razorpay_order_id: response.razorpay_order_id || orderId,
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

    const rzp = new window.Razorpay(options);

    rzp.on('payment.failed', function (response) {
      console.error('[razorpay-checkout] Payment failed:', response.error);
      if (onError) {
        onError(response.error.description || 'Payment was declined or failed.');
      }
    });

    if (onOpen) onOpen();

    rzp.open();
  } catch (err) {
    console.error('[razorpay-checkout] Initiation error:', err);
    if (onError) {
      onError(err.message || 'Could not start payment checkout.');
    }
  }
}
