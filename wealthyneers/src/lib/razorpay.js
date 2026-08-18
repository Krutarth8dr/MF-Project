// ─── Razorpay Standard Checkout Helper (UPI, Cards, Netbanking) ─────────
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
 * Initiates Razorpay payment checkout for ₹30/month membership.
 * Supports Google Pay, PhonePe, Paytm, UPI, Cards, and Netbanking.
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

    // 2. Create server-side order with JWT authorization
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
        throw new Error('You already have an active subscription.');
      }
      throw new Error(orderData.error || 'Failed to initiate payment order.');
    }

    const orderId = orderData.orderId || orderData.id;
    const keyId = orderData.keyId || orderData.key_id || process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID;

    if (!orderId || !keyId) {
      throw new Error('Invalid payment response from payment server.');
    }

    // 3. Load Razorpay SDK
    const loaded = await loadRazorpaySDK();
    if (!loaded) {
      throw new Error('Unable to load payment SDK. Please check your internet connection.');
    }

    // 4. Configure Razorpay Standard Checkout Options
    const options = {
      key: keyId,
      order_id: orderId,
      amount: orderData.amount || 3000,
      currency: orderData.currency || 'INR',
      name: 'Wealthyneers',
      description: 'Wealthyneers Monthly Membership — ₹30',
      image: '/wealthyneers-logo.png',
      prefill: {
        email: user.email || '',
        name: user.user_metadata?.full_name || '',
        contact: user.phone || user.user_metadata?.phone || '',
      },
      theme: {
        color: '#0A4D68',
      },
      config: {
        display: {
          blocks: {
            upi: {
              name: 'Pay via UPI (GPay, PhonePe, Paytm, QR)',
              instruments: [
                {
                  method: 'upi',
                },
              ],
            },
            cards: {
              name: 'Cards (Credit / Debit Card)',
              instruments: [
                {
                  method: 'card',
                },
              ],
            },
            netbanking: {
              name: 'Netbanking',
              instruments: [
                {
                  method: 'netbanking',
                },
              ],
            },
          },
          sequence: ['block.upi', 'block.cards', 'block.netbanking'],
          preferences: {
            show_default_blocks: false,
          },
        },
      },
      handler: async function (response) {
        try {
          // Re-fetch active session token in case it refreshed
          const { data: { session: freshSession } } = await supabase.auth.getSession();
          const activeToken = freshSession?.access_token || token;

          // 5. Verify payment signature on the server
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

    rzp.open();
    if (onOpen) onOpen();
  } catch (err) {
    console.error('[razorpay-checkout] Initiation error:', err);
    if (onError) {
      onError(err.message || 'Could not start payment checkout.');
    }
  }
}
