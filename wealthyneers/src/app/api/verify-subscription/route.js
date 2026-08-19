import crypto from 'crypto';
import Razorpay from 'razorpay';
import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import { getClientIp, checkRateLimit, rateLimitExceededResponse } from '@/lib/rateLimit';
import { getRazorpayCredentials } from '@/lib/envHelper';

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

    // 2. Server-Side Rate Limiting (User UUID + Client IP)
    const clientIp = getClientIp(request);
    const userLimit = checkRateLimit(`verify_sub:user:${userId}`, RATE_LIMIT_MAX_REQUESTS, RATE_LIMIT_WINDOW_MS);
    if (!userLimit.allowed) {
      return rateLimitExceededResponse(
        userLimit.resetInMs,
        'Too many subscription verification attempts. Please wait a few minutes.'
      );
    }

    const ipLimit = checkRateLimit(`verify_sub:ip:${clientIp}`, RATE_LIMIT_MAX_REQUESTS, RATE_LIMIT_WINDOW_MS);
    if (!ipLimit.allowed) {
      return rateLimitExceededResponse(
        ipLimit.resetInMs,
        'Too many verification requests from this network.'
      );
    }

    // 3. Validate Server Configuration
    const { keyId, keySecret, planId } = getRazorpayCredentials();

    if (!keyId || !keySecret) {
      console.error('[verify-subscription] RAZORPAY_CONFIG_MISSING: API credentials missing on server.');
      return NextResponse.json(
        { code: 'RAZORPAY_CONFIG_MISSING', error: 'Payment gateway configuration error.' },
        { status: 500 }
      );
    }

    // 4. Parse Request Body
    const body = await request.json();
    const {
      razorpay_subscription_id,
      razorpay_payment_id,
      razorpay_signature,
    } = body;

    if (!razorpay_subscription_id || !razorpay_payment_id || !razorpay_signature) {
      return NextResponse.json(
        { code: 'INVALID_PARAMETERS', error: 'Missing required subscription verification parameters.' },
        { status: 400 }
      );
    }

    // 5. Cryptographic Signature Verification (Timing-Safe Comparison)
    // Razorpay Subscription verification signature is: HMAC_SHA256(razorpay_payment_id + '|' + razorpay_subscription_id, secret)
    const expectedSignature = crypto
      .createHmac('sha256', keySecret)
      .update(`${razorpay_payment_id}|${razorpay_subscription_id}`)
      .digest('hex');

    const expectedBuf = Buffer.from(expectedSignature, 'utf8');
    const signatureBuf = Buffer.from(razorpay_signature, 'utf8');

    if (
      expectedBuf.length !== signatureBuf.length ||
      !crypto.timingSafeEqual(expectedBuf, signatureBuf)
    ) {
      console.warn(`[verify-subscription] INVALID_SIGNATURE for subscription: ${razorpay_subscription_id}`);
      return NextResponse.json(
        { code: 'INVALID_SIGNATURE', error: 'Invalid subscription signature. Verification rejected.' },
        { status: 400 }
      );
    }

    // 6. Server-Side Verification via Razorpay API
    const instance = new Razorpay({
      key_id: keyId,
      key_secret: keySecret,
    });

    let rzpSub;
    let rzpPayment;
    try {
      [rzpSub, rzpPayment] = await Promise.all([
        instance.subscriptions.fetch(razorpay_subscription_id),
        instance.payments.fetch(razorpay_payment_id),
      ]);
    } catch (apiErr) {
      console.error('[verify-subscription] Gateway fetch error:', apiErr?.message || apiErr);
      return NextResponse.json(
        { code: 'SUBSCRIPTION_MISMATCH', error: 'Unable to verify subscription authenticity with payment gateway.' },
        { status: 400 }
      );
    }

    // Verify Subscription Integrity
    if (!rzpSub || rzpSub.id !== razorpay_subscription_id) {
      return NextResponse.json(
        { code: 'SUBSCRIPTION_MISMATCH', error: 'Razorpay subscription verification failed.' },
        { status: 400 }
      );
    }

    if (rzpSub.notes?.user_id && rzpSub.notes.user_id !== userId) {
      console.warn(`[verify-subscription] USER_MISMATCH: Sub user ${rzpSub.notes.user_id} != JWT user ${userId}`);
      return NextResponse.json(
        { code: 'USER_MISMATCH', error: 'Subscription does not belong to the current authenticated account.' },
        { status: 403 }
      );
    }

    // Verify Payment Integrity
    if (!rzpPayment || rzpPayment.id !== razorpay_payment_id) {
      return NextResponse.json(
        { code: 'PAYMENT_MISMATCH', error: 'Payment record verification failed.' },
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

    // 8. Compute Subscription Validity
    const startDate = rzpSub.current_start
      ? new Date(rzpSub.current_start * 1000).toISOString()
      : new Date().toISOString();

    const endDate = rzpSub.current_end
      ? new Date(rzpSub.current_end * 1000).toISOString()
      : new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString();

    // 9. Fetch user's full_name from public.users
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
      console.warn('[verify-subscription] Could not fetch user full_name:', nameErr?.message || nameErr);
    }

    // 10. Insert Subscription Record via Service-Role
    const { data, error } = await supabaseAdmin
      .from('subscriptions')
      .insert([
        {
          user_id: userId,
          full_name: fullName,
          plan_type: 'monthly_30',
          amount_paid: 30.0,
          currency: 'INR',
          payment_status: 'completed',
          razorpay_payment_id,
          razorpay_order_id: razorpay_subscription_id,
          subscription_start_date: startDate,
          subscription_end_date: endDate,
          auto_renew: true,
        },
      ])
      .select()
      .single();

    if (error) {
      if (error.code === '23505') {
        return NextResponse.json(
          { code: 'PAYMENT_ALREADY_PROCESSED', error: 'This subscription has already been recorded.' },
          { status: 409 }
        );
      }
      console.error('[verify-subscription] SUBSCRIPTION_INSERT_FAILED:', error);
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
    console.error('[verify-subscription] Unhandled error:', error?.message || error);
    return NextResponse.json(
      { code: 'INTERNAL_ERROR', error: 'Internal server error during subscription verification.' },
      { status: 500 }
    );
  }
}
