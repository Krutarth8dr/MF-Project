import crypto from 'crypto';
import Razorpay from 'razorpay';
import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import { getClientIp, checkRateLimit, rateLimitExceededResponse } from '@/lib/rateLimit';
import { getRazorpayCredentials } from '@/lib/envHelper';
import { supabaseAdmin } from '@/lib/supabaseAdmin';
import { getPlan } from '@/lib/plans';

const RATE_LIMIT_WINDOW_MS = 15 * 60 * 1000;
const RATE_LIMIT_MAX_REQUESTS = process.env.NODE_ENV === 'production' ? 10 : 100;

function getSupabaseUserClient(authToken) {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  return createClient(url, anonKey, {
    global: { headers: { Authorization: `Bearer ${authToken}` } },
    auth: { persistSession: false },
  });
}

export async function POST(request) {
  try {
    // 1. Authenticate Request via Supabase Bearer Token
    const authHeader = request.headers.get('authorization') || '';
    const token = authHeader.startsWith('Bearer ') ? authHeader.substring(7).trim() : null;

    if (!token) {
      return NextResponse.json(
        { code: 'AUTH_REQUIRED', error: 'Authentication required. Please log in.' },
        { status: 401 }
      );
    }

    const userClient = getSupabaseUserClient(token);
    const {
      data: { user },
      error: userError,
    } = await userClient.auth.getUser(token);

    if (userError || !user) {
      return NextResponse.json(
        { code: 'AUTH_REQUIRED', error: 'Invalid or expired session. Please log in again.' },
        { status: 401 }
      );
    }

    const userId = user.id;

    // 2. Server-Side Rate Limiting (User UUID + Client IP)
    const clientIp = getClientIp(request);
    const userLimit = checkRateLimit(`verify:user:${userId}`, RATE_LIMIT_MAX_REQUESTS, RATE_LIMIT_WINDOW_MS);
    if (!userLimit.allowed) {
      return rateLimitExceededResponse(
        userLimit.resetInMs,
        'Too many payment verification attempts. Please wait a few minutes.'
      );
    }

    const ipLimit = checkRateLimit(`verify:ip:${clientIp}`, RATE_LIMIT_MAX_REQUESTS, RATE_LIMIT_WINDOW_MS);
    if (!ipLimit.allowed) {
      return rateLimitExceededResponse(
        ipLimit.resetInMs,
        'Too many payment verification requests from this network.'
      );
    }

    // 3. Validate Server Configuration
    const { keyId, keySecret } = getRazorpayCredentials();

    if (!keyId || !keySecret) {
      console.error('[verify-payment] RAZORPAY_CONFIG_MISSING: API credentials missing on server.');
      return NextResponse.json(
        { code: 'RAZORPAY_CONFIG_MISSING', error: 'Payment gateway configuration error.' },
        { status: 500 }
      );
    }

    // 4. Parse Request Body
    const body = await request.json();
    const {
      razorpay_order_id,
      razorpay_payment_id,
      razorpay_signature,
    } = body;

    const orderId = razorpay_order_id;

    if (!orderId || !razorpay_payment_id || !razorpay_signature) {
      return NextResponse.json(
        { code: 'INVALID_PARAMETERS', error: 'Missing required payment verification parameters.' },
        { status: 400 }
      );
    }

    // 5. Cryptographic Signature Verification (Timing-Safe Comparison)
    const expectedSignature = crypto
      .createHmac('sha256', keySecret)
      .update(`${orderId}|${razorpay_payment_id}`)
      .digest('hex');

    const expectedBuf = Buffer.from(expectedSignature, 'utf8');
    const signatureBuf = Buffer.from(razorpay_signature, 'utf8');

    if (
      expectedBuf.length !== signatureBuf.length ||
      !crypto.timingSafeEqual(expectedBuf, signatureBuf)
    ) {
      console.warn(`[verify-payment] INVALID_SIGNATURE for order: ${orderId}`);
      return NextResponse.json(
        { code: 'INVALID_SIGNATURE', error: 'Invalid payment signature. Verification rejected.' },
        { status: 400 }
      );
    }

    // 6. Direct Verification with Razorpay API (Server-to-Server)
    const instance = new Razorpay({
      key_id: keyId,
      key_secret: keySecret,
    });

    let rzpOrder, rzpPayment;
    try {
      [rzpOrder, rzpPayment] = await Promise.all([
        instance.orders.fetch(orderId),
        instance.payments.fetch(razorpay_payment_id),
      ]);
    } catch (apiErr) {
      console.error('[verify-payment] Order/Payment fetch error:', apiErr?.message || apiErr);
      return NextResponse.json(
        { code: 'ORDER_MISMATCH', error: 'Unable to verify order authenticity with payment gateway.' },
        { status: 400 }
      );
    }

    if (!rzpOrder || rzpOrder.id !== orderId) {
      return NextResponse.json(
        { code: 'ORDER_MISMATCH', error: 'Razorpay order verification failed.' },
        { status: 400 }
      );
    }

    // Verify ownership
    if (rzpOrder.notes?.user_id && rzpOrder.notes.user_id !== userId) {
      return NextResponse.json(
        { code: 'USER_MISMATCH', error: 'Order does not belong to the current authenticated account.' },
        { status: 403 }
      );
    }

    // Server-side plan resolution from order notes (never trust browser-supplied plan)
    const planType = rzpOrder.notes?.plan_type || 'monthly_30';
    const plan = getPlan(planType);

    if (!plan) {
      console.error(`[verify-payment] UNKNOWN_PLAN_TYPE in order notes: ${planType}`);
      return NextResponse.json(
        { code: 'INVALID_PLAN', error: 'The order references an invalid or unsupported subscription plan.' },
        { status: 400 }
      );
    }

    // Verify order amount matches the server-authoritative plan price (in paise)
    if (rzpOrder.amount !== plan.amountPaise) {
      console.warn(
        `[verify-payment] AMOUNT_MISMATCH: Order amount ${rzpOrder.amount} does not match expected ${plan.amountPaise} paise for plan ${plan.id}`
      );
      return NextResponse.json(
        { code: 'AMOUNT_MISMATCH', error: 'Order amount does not match required plan price.' },
        { status: 400 }
      );
    }

    if (rzpOrder.currency !== plan.currency) {
      return NextResponse.json(
        { code: 'CURRENCY_MISMATCH', error: 'Order currency mismatch.' },
        { status: 400 }
      );
    }

    if (rzpPayment.amount !== plan.amountPaise) {
      return NextResponse.json(
        { code: 'PAYMENT_AMOUNT_MISMATCH', error: 'Paid amount does not match plan price.' },
        { status: 400 }
      );
    }

    // Ensure payment reaches confirmed captured state (never grant access on uncaptured/failed payments)
    if (rzpPayment.status !== 'captured') {
      if (rzpPayment.status === 'authorized') {
        try {
          rzpPayment = await instance.payments.capture(
            razorpay_payment_id,
            plan.amountPaise,
            plan.currency
          );
        } catch (captureErr) {
          console.error('[verify-payment] Failed to capture authorized payment:', captureErr?.message || captureErr);
          return NextResponse.json(
            { code: 'PAYMENT_CAPTURE_FAILED', error: 'Payment authorization could not be captured. Please contact support.' },
            { status: 400 }
          );
        }
      }
    }

    if (rzpPayment.status !== 'captured') {
      return NextResponse.json(
        { code: 'PAYMENT_NOT_CAPTURED', error: `Payment is not in a confirmed captured state (current status: ${rzpPayment.status}).` },
        { status: 400 }
      );
    }

    // 7. Check Duplicate / Replay Protection & Idempotent Retry
    // If this payment was already processed for this user, return success idempotently.
    // This protects against network dropouts where the client retries without re-charging.
    const { data: existingSub } = await supabaseAdmin
      .from('subscriptions')
      .select('id, user_id, plan_type, subscription_start_date, subscription_end_date, payment_status')
      .eq('razorpay_payment_id', razorpay_payment_id)
      .maybeSingle();

    if (existingSub) {
      if (existingSub.user_id === userId && existingSub.payment_status === 'completed') {
        return NextResponse.json({
          success: true,
          message: `Access is already active for this payment.`,
          subscription: existingSub,
          already_processed: true,
        });
      }

      return NextResponse.json(
        { code: 'PAYMENT_ALREADY_PROCESSED', error: 'This payment has already been credited to another account.' },
        { status: 409 }
      );
    }

    // 8. Fetch user's full_name server-side from public.users
    let fullName = null;
    try {
      const { data: userProfile } = await supabaseAdmin
        .from('users')
        .select('full_name')
        .eq('id', userId)
        .maybeSingle();
      if (userProfile?.full_name) {
        fullName = userProfile.full_name;
      }
    } catch (nameErr) {
      console.warn('[verify-payment] Could not fetch user full_name:', nameErr?.message || nameErr);
    }

    // 9. Atomic Subscription Provisioning via Database RPC (No Non-Atomic Fallback)
    // Strictly enforced: All provisioning must execute via the atomic RPC.
    // The database-level advisory lock guarantees sequential processing with zero overlapping windows.
    const { data: rpcResult, error: rpcError } = await supabaseAdmin.rpc(
      'provision_subscription_access',
      {
        p_user_id: userId,
        p_full_name: fullName,
        p_plan_type: plan.id,
        p_amount_paid: plan.price,
        p_currency: plan.currency,
        p_razorpay_payment_id: razorpay_payment_id,
        p_razorpay_order_id: orderId,
      }
    );

    if (rpcError) {
      // Secure logging: log reference IDs and error message without exposing payment secrets
      console.error('[verify-payment] PROVISION_RPC_EXECUTION_FAILED', {
        userId,
        orderId,
        paymentId: razorpay_payment_id,
        error: rpcError.message,
      });

      return NextResponse.json(
        {
          code: 'PROVISIONING_TEMPORARILY_UNAVAILABLE',
          error: 'Your payment was safely captured, but access activation encountered a temporary database error. Please retry verification; you will not be charged again.',
          recoverable: true,
          orderId,
          paymentId: razorpay_payment_id,
        },
        { status: 503 }
      );
    }

    if (!rpcResult || !rpcResult.success) {
      const code = rpcResult?.code || 'PROVISION_FAILED';
      const errMsg = rpcResult?.error || 'Failed to provision subscription.';

      if (code === 'PAYMENT_ALREADY_PROCESSED') {
        return NextResponse.json(
          { code: 'PAYMENT_ALREADY_PROCESSED', error: 'This payment has already been credited.' },
          { status: 409 }
        );
      }

      console.error('[verify-payment] PROVISION_RPC_REJECTED', {
        userId,
        orderId,
        paymentId: razorpay_payment_id,
        code,
        error: errMsg,
      });

      return NextResponse.json(
        { code, error: errMsg, recoverable: false },
        { status: 400 }
      );
    }

    return NextResponse.json({
      success: true,
      message: `Access successfully activated for ${plan.name}.`,
      subscription: rpcResult.subscription,
    });
  } catch (error) {
    console.error('[verify-payment] Unhandled error:', error?.message || error);
    return NextResponse.json(
      { code: 'INTERNAL_ERROR', error: 'Internal server error during verification.' },
      { status: 500 }
    );
  }
}
