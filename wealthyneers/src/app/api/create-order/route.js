import Razorpay from 'razorpay';
import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import { getClientIp, checkRateLimit, rateLimitExceededResponse } from '@/lib/rateLimit';

// Server-enforced subscription specifications (₹30.00 = 3000 paise)
const SUBSCRIPTION_PRICE_PAISE = 3000;
const SUBSCRIPTION_CURRENCY = 'INR';
const SUBSCRIPTION_PLAN_TYPE = 'monthly_30';

// Rate Limiting: 5 orders / 15 min in production, 100 in dev
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

import { getRazorpayCredentials } from '@/lib/envHelper';

export async function POST(request) {
  try {
    // 1. Authenticate Request via Supabase Bearer Token
    const authHeader = request.headers.get('authorization') || '';
    const token = authHeader.startsWith('Bearer ') ? authHeader.substring(7).trim() : null;

    if (!token) {
      return NextResponse.json(
        { code: 'AUTH_REQUIRED', error: 'Authentication required to initiate subscription order.' },
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

    // 2. Server-Side Rate Limiting (User UUID + Client IP)
    const clientIp = getClientIp(request);
    const userLimit = checkRateLimit(`order:user:${user.id}`, RATE_LIMIT_MAX_REQUESTS, RATE_LIMIT_WINDOW_MS);
    if (!userLimit.allowed) {
      return rateLimitExceededResponse(
        userLimit.resetInMs,
        'Too many order creation attempts. Please wait a few minutes.'
      );
    }

    const ipLimit = checkRateLimit(`order:ip:${clientIp}`, RATE_LIMIT_MAX_REQUESTS, RATE_LIMIT_WINDOW_MS);
    if (!ipLimit.allowed) {
      return rateLimitExceededResponse(
        ipLimit.resetInMs,
        'Too many order requests from this network. Please wait a few minutes.'
      );
    }

    // 3. Validate Server-Side Razorpay Configuration (Fail Closed)
    const { keyId, keySecret } = getRazorpayCredentials();

    if (!keyId || !keySecret) {
      console.error('[create-order] RAZORPAY_CONFIG_MISSING: API credentials missing in server environment.');
      return NextResponse.json(
        { code: 'RAZORPAY_CONFIG_MISSING', error: 'Payment gateway configuration error. Please contact support.' },
        { status: 500 }
      );
    }

    // 4. Create Fixed ₹30 Razorpay Order with Authenticated User Association
    const instance = new Razorpay({
      key_id: keyId,
      key_secret: keySecret,
    });

    const options = {
      amount: SUBSCRIPTION_PRICE_PAISE,
      currency: SUBSCRIPTION_CURRENCY,
      receipt: `rcpt_${Date.now().toString(36)}_${Math.random().toString(36).substring(2, 7)}`,
      checkout_config_id: 'config_TTA4yOciDuRJ46',
      notes: {
        user_id: user.id,
        user_email: user.email || '',
        plan_type: SUBSCRIPTION_PLAN_TYPE,
      },
    };

    const order = await instance.orders.create(options);

    return NextResponse.json({
      orderId: order.id,
      id: order.id,
      amount: order.amount,
      currency: order.currency,
      keyId: keyId,
      key_id: keyId,
    });
  } catch (error) {
    const errorDescription = error?.error?.description || error?.message || 'Failed to create payment order.';
    console.error('[create-order] RAZORPAY_ORDER_FAILED:', errorDescription);
    return NextResponse.json(
      { code: 'RAZORPAY_ORDER_FAILED', error: errorDescription },
      { status: 500 }
    );
  }
}
