import Razorpay from 'razorpay';
import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import { getClientIp, checkRateLimit, rateLimitExceededResponse } from '@/lib/rateLimit';
import { getRazorpayCredentials } from '@/lib/envHelper';

const RATE_LIMIT_WINDOW_MS = 15 * 60 * 1000;
const RATE_LIMIT_MAX_REQUESTS = process.env.NODE_ENV === 'production' ? 5 : 100;

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
        { code: 'AUTH_REQUIRED', error: 'Authentication required to initiate subscription.' },
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

    // 2. Rate Limiting (User UUID + Client IP)
    const clientIp = getClientIp(request);
    const userLimit = checkRateLimit(`sub_create:user:${user.id}`, RATE_LIMIT_MAX_REQUESTS, RATE_LIMIT_WINDOW_MS);
    if (!userLimit.allowed) {
      return rateLimitExceededResponse(
        userLimit.resetInMs,
        'Too many subscription creation attempts. Please wait a few minutes.'
      );
    }

    const ipLimit = checkRateLimit(`sub_create:ip:${clientIp}`, RATE_LIMIT_MAX_REQUESTS, RATE_LIMIT_WINDOW_MS);
    if (!ipLimit.allowed) {
      return rateLimitExceededResponse(
        ipLimit.resetInMs,
        'Too many subscription requests from this network.'
      );
    }

    // 3. Check whether user already has an active subscription
    const supabaseAdmin = getSupabaseAdminClient();
    const { data: existingActiveSub } = await supabaseAdmin
      .from('subscriptions')
      .select('id, payment_status, subscription_end_date')
      .eq('user_id', user.id)
      .eq('payment_status', 'completed')
      .order('subscription_end_date', { ascending: false })
      .limit(1)
      .maybeSingle();

    const isCurrentlyActive =
      existingActiveSub &&
      (existingActiveSub.subscription_end_date === null ||
        new Date(existingActiveSub.subscription_end_date) > new Date());

    if (isCurrentlyActive) {
      return NextResponse.json(
        {
          code: 'ALREADY_SUBSCRIBED',
          error: 'You already have an active subscription to Wealthyneers.',
          isSubscribed: true,
        },
        { status: 400 }
      );
    }

    // 4. Validate Server-Side Razorpay Configuration
    const { keyId, keySecret, planId } = getRazorpayCredentials();

    if (!keyId || !keySecret) {
      console.error('[create-subscription] RAZORPAY_CONFIG_MISSING: API credentials missing on server.');
      return NextResponse.json(
        { code: 'RAZORPAY_CONFIG_MISSING', error: 'Payment gateway configuration error. Please contact support.' },
        { status: 500 }
      );
    }

    if (!planId) {
      console.error('[create-subscription] RAZORPAY_PLAN_MISSING: Plan ID missing on server.');
      return NextResponse.json(
        { code: 'RAZORPAY_PLAN_MISSING', error: 'Subscription plan not configured. Please contact support.' },
        { status: 500 }
      );
    }

    // 5. Create Razorpay Subscription
    const instance = new Razorpay({
      key_id: keyId,
      key_secret: keySecret,
    });

    const subscription = await instance.subscriptions.create({
      plan_id: planId,
      total_count: 12, // 12 monthly cycles
      quantity: 1,
      customer_notify: 1,
      notes: {
        user_id: user.id,
        user_email: user.email || '',
        plan_type: 'monthly_30',
      },
    });

    return NextResponse.json({
      subscriptionId: subscription.id,
      id: subscription.id,
      keyId: keyId,
      key_id: keyId,
      planId: subscription.plan_id,
      status: subscription.status,
      amount: 3000,
      currency: 'INR',
      user: {
        id: user.id,
        email: user.email || '',
        name: user.user_metadata?.full_name || '',
      },
    });
  } catch (error) {
    const errorDescription = error?.error?.description || error?.message || 'Failed to create subscription.';
    console.error('[create-subscription] RAZORPAY_SUBSCRIPTION_FAILED:', errorDescription);
    return NextResponse.json(
      { code: 'RAZORPAY_SUBSCRIPTION_FAILED', error: errorDescription },
      { status: 500 }
    );
  }
}
