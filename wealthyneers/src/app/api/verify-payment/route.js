import crypto from 'crypto';
import Razorpay from 'razorpay';
import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import { getClientIp, checkRateLimit, rateLimitExceededResponse } from '@/lib/rateLimit';
import { getRazorpayCredentials } from '@/lib/envHelper';

const EXPECTED_AMOUNT_PAISE = 3000;
const EXPECTED_CURRENCY = 'INR';
const EXPECTED_PLAN_TYPE = 'monthly_30';

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

function getSupabaseAdminClient() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  return createClient(url, serviceKey, {
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

    // 2. Server-Side Rate Limiting
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
      razorpay_subscription_id,
      razorpay_payment_id,
      razorpay_signature,
    } = body;

    const subId = razorpay_subscription_id;
    const orderId = razorpay_order_id;
    const primaryId = subId || orderId;

    if (!primaryId || !razorpay_payment_id || !razorpay_signature) {
      return NextResponse.json(
        { code: 'INVALID_PARAMETERS', error: 'Missing required payment verification parameters.' },
        { status: 400 }
      );
    }

    // 5. Cryptographic Signature Verification (Timing-Safe Comparison)
    let expectedSignature;
    if (subId) {
      expectedSignature = crypto
        .createHmac('sha256', keySecret)
        .update(`${razorpay_payment_id}|${subId}`)
        .digest('hex');
    } else {
      expectedSignature = crypto
        .createHmac('sha256', keySecret)
        .update(`${orderId}|${razorpay_payment_id}`)
        .digest('hex');
    }

    const expectedBuf = Buffer.from(expectedSignature, 'utf8');
    const signatureBuf = Buffer.from(razorpay_signature, 'utf8');

    if (
      expectedBuf.length !== signatureBuf.length ||
      !crypto.timingSafeEqual(expectedBuf, signatureBuf)
    ) {
      console.warn(`[verify-payment] INVALID_SIGNATURE for ${subId ? 'sub ' + subId : 'order ' + orderId}`);
      return NextResponse.json(
        { code: 'INVALID_SIGNATURE', error: 'Invalid payment signature. Verification rejected.' },
        { status: 400 }
      );
    }

    // 6. Server-Side Verification via Razorpay API
    const instance = new Razorpay({
      key_id: keyId,
      key_secret: keySecret,
    });

    let startDate = new Date();
    let endDate = new Date(startDate);
    endDate.setMonth(endDate.getMonth() + 1);

    if (subId) {
      let rzpSub, rzpPayment;
      try {
        [rzpSub, rzpPayment] = await Promise.all([
          instance.subscriptions.fetch(subId),
          instance.payments.fetch(razorpay_payment_id),
        ]);
      } catch (apiErr) {
        console.error('[verify-payment] Subscription fetch error:', apiErr?.message || apiErr);
        return NextResponse.json(
          { code: 'SUBSCRIPTION_MISMATCH', error: 'Unable to verify subscription with payment gateway.' },
          { status: 400 }
        );
      }

      if (!rzpSub || rzpSub.id !== subId) {
        return NextResponse.json(
          { code: 'SUBSCRIPTION_MISMATCH', error: 'Razorpay subscription verification failed.' },
          { status: 400 }
        );
      }

      if (rzpSub.notes?.user_id && rzpSub.notes.user_id !== userId) {
        return NextResponse.json(
          { code: 'USER_MISMATCH', error: 'Subscription does not belong to this account.' },
          { status: 403 }
        );
      }

      if (rzpSub.current_start) startDate = new Date(rzpSub.current_start * 1000);
      if (rzpSub.current_end) endDate = new Date(rzpSub.current_end * 1000);
    } else {
      let rzpOrder, rzpPayment;
      try {
        [rzpOrder, rzpPayment] = await Promise.all([
          instance.orders.fetch(orderId),
          instance.payments.fetch(razorpay_payment_id),
        ]);
      } catch (apiErr) {
        console.error('[verify-payment] Order fetch error:', apiErr?.message || apiErr);
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

      if (rzpOrder.amount !== EXPECTED_AMOUNT_PAISE) {
        return NextResponse.json(
          { code: 'AMOUNT_MISMATCH', error: 'Order amount does not match required subscription price.' },
          { status: 400 }
        );
      }

      if (rzpOrder.currency !== EXPECTED_CURRENCY) {
        return NextResponse.json(
          { code: 'CURRENCY_MISMATCH', error: 'Order currency mismatch.' },
          { status: 400 }
        );
      }

      if (rzpPayment.status !== 'captured' && rzpPayment.status !== 'authorized') {
        return NextResponse.json(
          { code: 'PAYMENT_NOT_CAPTURED', error: `Payment is not in a valid state (status: ${rzpPayment.status}).` },
          { status: 400 }
        );
      }
    }

    // 7. Check Duplicate / Replay Protection
    const supabaseAdmin = getSupabaseAdminClient();
    const { data: existingSub } = await supabaseAdmin
      .from('subscriptions')
      .select('id, user_id, payment_status')
      .eq('razorpay_payment_id', razorpay_payment_id)
      .maybeSingle();

    if (existingSub) {
      return NextResponse.json(
        { code: 'PAYMENT_ALREADY_PROCESSED', error: 'This payment has already been credited.' },
        { status: 409 }
      );
    }

    // 8. Fetch user's full_name from public.users
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

    // 9. Insert Subscription Record via Service-Role
    const { data, error } = await supabaseAdmin
      .from('subscriptions')
      .insert([
        {
          user_id: userId,
          full_name: fullName,
          plan_type: EXPECTED_PLAN_TYPE,
          amount_paid: 30.0,
          currency: EXPECTED_CURRENCY,
          payment_status: 'completed',
          razorpay_payment_id,
          razorpay_order_id: primaryId,
          subscription_start_date: startDate.toISOString(),
          subscription_end_date: endDate.toISOString(),
          auto_renew: true,
        },
      ])
      .select()
      .single();

    if (error) {
      if (error.code === '23505') {
        return NextResponse.json(
          { code: 'PAYMENT_ALREADY_PROCESSED', error: 'This payment has already been processed.' },
          { status: 409 }
        );
      }
      console.error('[verify-payment] SUBSCRIPTION_CREATION_FAILED:', error);
      return NextResponse.json(
        { code: 'SUBSCRIPTION_CREATION_FAILED', error: 'Failed to record active subscription in database.' },
        { status: 500 }
      );
    }

    return NextResponse.json({
      success: true,
      message: 'Subscription successfully activated.',
      subscription: data,
    });
  } catch (error) {
    console.error('[verify-payment] Unhandled error:', error?.message || error);
    return NextResponse.json(
      { code: 'INTERNAL_ERROR', error: 'Internal server error during verification.' },
      { status: 500 }
    );
  }
}
