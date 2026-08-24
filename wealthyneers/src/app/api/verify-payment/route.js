import crypto from 'crypto';
import Razorpay from 'razorpay';
import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import { getClientIp, checkRateLimit, rateLimitExceededResponse } from '@/lib/rateLimit';
import { getRazorpayCredentials } from '@/lib/envHelper';
import { supabaseAdmin } from '@/lib/supabaseAdmin';

const EXPECTED_AMOUNT_PAISE = 3000; // ₹30.00 = 3000 paise (Fixed Server-Side)
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

    // 4. Parse Request Body (Strictly One-Time Order Parameters)
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

    // 6. Server-Side Verification via Razorpay API
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

    if (rzpOrder.notes?.user_id && rzpOrder.notes.user_id !== userId) {
      return NextResponse.json(
        { code: 'USER_MISMATCH', error: 'Order does not belong to the current authenticated account.' },
        { status: 403 }
      );
    }

    if (rzpOrder.amount !== EXPECTED_AMOUNT_PAISE) {
      return NextResponse.json(
        { code: 'AMOUNT_MISMATCH', error: 'Order amount does not match required price.' },
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

    // 7. Check Duplicate / Replay Protection
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

    // 9. Compute 30-day Access Window (One-Time Payment)
    const startDate = new Date();
    const endDate = new Date(startDate.getTime() + 30 * 24 * 60 * 60 * 1000);

    // 10. Insert One-Time Access Record via Service-Role (auto_renew: false)
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
          razorpay_order_id: orderId,
          subscription_start_date: startDate.toISOString(),
          subscription_end_date: endDate.toISOString(),
          auto_renew: false, // Strictly ONE-TIME (no recurring billing)
        },
      ])
      .select('id, plan_type, subscription_start_date, subscription_end_date')
      .single();

    if (error) {
      if (error.code === '23505') {
        return NextResponse.json(
          { code: 'PAYMENT_ALREADY_PROCESSED', error: 'This payment has already been processed.' },
          { status: 409 }
        );
      }
      console.error('[verify-payment] ACCESS_RECORD_CREATION_FAILED:', error);
      return NextResponse.json(
        { code: 'SUBSCRIPTION_CREATION_FAILED', error: 'Failed to record active access in database.' },
        { status: 500 }
      );
    }

    return NextResponse.json({
      success: true,
      message: 'Access successfully activated for 30 days.',
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
