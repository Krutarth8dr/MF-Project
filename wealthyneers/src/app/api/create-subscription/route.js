import { NextResponse } from 'next/server';

/**
 * DEPRECATED: Recurring Razorpay Subscriptions are no longer supported.
 * Wealthyneers now exclusively uses one-time payments via /api/create-order.
 */
export async function POST() {
  return NextResponse.json(
    {
      code: 'SUBSCRIPTIONS_DEPRECATED',
      error: 'Recurring subscriptions are no longer supported. Please use the one-time payment option.',
    },
    { status: 410 }
  );
}

export async function GET() {
  return NextResponse.json(
    {
      code: 'SUBSCRIPTIONS_DEPRECATED',
      error: 'Recurring subscriptions are no longer supported.',
    },
    { status: 410 }
  );
}
