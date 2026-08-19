import { NextResponse } from 'next/server';

/**
 * DEPRECATED: Recurring Razorpay Subscription Verification is no longer supported.
 * Wealthyneers now exclusively verifies one-time order payments via /api/verify-payment.
 */
export async function POST() {
  return NextResponse.json(
    {
      code: 'SUBSCRIPTIONS_DEPRECATED',
      error: 'Recurring subscription verification is no longer supported. Please use the standard one-time payment verification.',
    },
    { status: 410 }
  );
}

export async function GET() {
  return NextResponse.json(
    {
      code: 'SUBSCRIPTIONS_DEPRECATED',
      error: 'Recurring subscription verification is no longer supported.',
    },
    { status: 410 }
  );
}
