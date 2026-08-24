import crypto from 'crypto';
import { NextResponse } from 'next/server';
import { getRazorpayCredentials } from '@/lib/envHelper';

// In-memory idempotency cache for recently processed event IDs (prevent duplicates)
const processedEvents = new Map();
const IDEMPOTENCY_TTL_MS = 60 * 60 * 1000; // 1 hour

function markEventProcessed(eventId) {
  if (!eventId) return;
  processedEvents.set(eventId, Date.now());
  if (processedEvents.size > 2000) {
    const now = Date.now();
    for (const [id, time] of processedEvents.entries()) {
      if (now - time > IDEMPOTENCY_TTL_MS) {
        processedEvents.delete(id);
      }
    }
  }
}

function isEventProcessed(eventId) {
  if (!eventId) return false;
  const time = processedEvents.get(eventId);
  if (!time) return false;
  if (Date.now() - time > IDEMPOTENCY_TTL_MS) {
    processedEvents.delete(eventId);
    return false;
  }
  return true;
}

/**
 * Razorpay Webhook Endpoint.
 * Recurring subscription lifecycle management is permanently disabled.
 * Payment verification and access activation is strictly handled in real-time via /api/verify-payment.
 */
export async function POST(request) {
  try {
    const { webhookSecret } = getRazorpayCredentials();

    // 1. Webhook Secret Configuration Check (Fail Closed)
    if (!webhookSecret) {
      console.error('[razorpay-webhook] RAZORPAY_WEBHOOK_SECRET is not configured on the server.');
      return NextResponse.json(
        { error: 'Webhook secret not configured' },
        { status: 500 }
      );
    }

    const rawBody = await request.text();
    const signature = request.headers.get('x-razorpay-signature');

    // 2. Verify Webhook Signature
    if (!signature) {
      console.warn('[razorpay-webhook] Missing x-razorpay-signature header');
      return NextResponse.json({ error: 'Signature required' }, { status: 400 });
    }

    const expectedSignature = crypto
      .createHmac('sha256', webhookSecret)
      .update(rawBody)
      .digest('hex');

    const expectedBuf = Buffer.from(expectedSignature, 'utf8');
    const signatureBuf = Buffer.from(signature, 'utf8');

    if (
      expectedBuf.length !== signatureBuf.length ||
      !crypto.timingSafeEqual(expectedBuf, signatureBuf)
    ) {
      console.warn('[razorpay-webhook] Invalid signature received');
      return NextResponse.json({ error: 'Invalid signature' }, { status: 400 });
    }

    // 2. Parse Event Payload
    let eventPayload;
    try {
      eventPayload = JSON.parse(rawBody);
    } catch {
      return NextResponse.json({ error: 'Invalid JSON payload' }, { status: 400 });
    }

    const eventName = eventPayload.event;
    const eventId = eventPayload.account_id ? `${eventPayload.account_id}_${eventPayload.created_at}_${eventName}` : null;

    // 3. Idempotency Check
    if (eventId && isEventProcessed(eventId)) {
      console.log(`[razorpay-webhook] Duplicate event ignored: ${eventId}`);
      return NextResponse.json({ status: 'ok', message: 'Event already processed' });
    }

    if (eventId) markEventProcessed(eventId);

    // Recurring subscription events are ignored in the one-time payment model
    console.log(`[razorpay-webhook] Acknowledged event: ${eventName}`);

    return NextResponse.json({ status: 'ok', message: 'Webhook acknowledged' });
  } catch (error) {
    console.error('[razorpay-webhook] Handler error:', error?.message || error);
    return NextResponse.json({ error: 'Webhook handler error' }, { status: 500 });
  }
}
