// ─── Razorpay Recurring Subscription Checkout Helper ─────────────────
import { supabase } from '@/lib/supabase';

/**
 * Loads Razorpay script dynamically if not already loaded.
 */
export function loadRazorpaySDK() {
  return new Promise((resolve) => {
    if (typeof window !== 'undefined' && window.Razorpay) {
      resolve(true);
      return;
    }
    const script = document.createElement('script');
    script.src = 'https://checkout.razorpay.com/v1/checkout.js';
    script.async = true;
    script.onload = () => resolve(true);
    script.onerror = () => resolve(false);
    document.body.appendChild(script);
  });
}

/**
 * Initiates Razorpay recurring subscription checkout for ₹30/month.
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
    // 1. Obtain current authenticated Supabase session JWT
    const { data: { session } } = await supabase.auth.getSession();
    const token = session?.access_token;

    if (!token) {
      throw new Error('Active user session not found. Please log in again.');
    }

    // 2. Create server-side subscription with JWT authorization
    const subRes = await fetch('/api/create-subscription', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    const subData = await subRes.json();

    if (!subRes.ok) {
      if (subData.code === 'ALREADY_SUBSCRIBED') {
        throw new Error('You already have an active subscription.');
      }
      throw new Error(subData.error || 'Failed to initiate subscription.');
    }

    const subscriptionId = subData.subscriptionId || subData.id;
    const keyId = subData.keyId || subData.key_id || process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID;

    if (!subscriptionId || !keyId) {
      throw new Error('Invalid subscription response from payment server.');
    }

    // 3. Load Razorpay SDK
    const loaded = await loadRazorpaySDK();
    if (!loaded) {
      throw new Error('Unable to load payment SDK. Please check your internet connection.');
    }

    // 4. Configure Razorpay Subscription Checkout Options
    const options = {
      key: keyId,
      subscription_id: subscriptionId, // Recurring subscription
      name: 'Wealthyneers',
      description: 'Wealthyneers Monthly Subscription — ₹30/month',
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
          // Re-fetch active session token in case it refreshed
          const { data: { session: freshSession } } = await supabase.auth.getSession();
          const activeToken = freshSession?.access_token || token;

          // 5. Verify subscription signature on the server
          const verifyRes = await fetch('/api/verify-subscription', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${activeToken}`,
            },
            body: JSON.stringify({
              razorpay_subscription_id: response.razorpay_subscription_id || subscriptionId,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature: response.razorpay_signature,
            }),
          });

          const verifyData = await verifyRes.json();
          if (!verifyRes.ok || !verifyData.success) {
            throw new Error(verifyData.error || 'Subscription verification failed.');
          }

          if (onSuccess) {
            onSuccess(verifyData.subscription);
          }
        } catch (verifyErr) {
          console.error('[razorpay-checkout] Verification error:', verifyErr);
          if (onError) onError(verifyErr.message || 'Subscription verification failed.');
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

    rzp.open();
    if (onOpen) onOpen();
  } catch (err) {
    console.error('[razorpay-checkout] Initiation error:', err);
    if (onError) {
      onError(err.message || 'Could not start subscription checkout.');
    }
  }
}
