import crypto from 'crypto';
import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import { getRazorpayCredentials } from '@/lib/envHelper';

function getSupabaseAdminClient() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  return createClient(url, serviceKey, {
    auth: { persistSession: false },
  });
}

async function getUserFullName(supabaseAdmin, userId) {
  if (!userId) return null;
  try {
    const { data: userProfile } = await supabaseAdmin
      .from('users')
      .select('full_name')
      .eq('id', userId)
      .maybeSingle();
    return userProfile?.full_name || null;
  } catch (err) {
    console.warn('[razorpay-webhook] Could not fetch user full_name:', err?.message || err);
    return null;
  }
}

// In-memory idempotency cache for recently processed event IDs (prevent duplicates)
const processedEvents = new Map();
const IDEMPOTENCY_TTL_MS = 60 * 60 * 1000; // 1 hour

function markEventProcessed(eventId) {
  if (!eventId) return;
  processedEvents.set(eventId, Date.now());
  // Prune older entries
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

export async function POST(request) {
  try {
    const rawBody = await request.text();
    const signature = request.headers.get('x-razorpay-signature');

    const { webhookSecret } = getRazorpayCredentials();

    // 1. Verify Webhook Signature (If secret is configured)
    if (webhookSecret) {
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

    const subEntity = eventPayload.payload?.subscription?.entity;
    const paymentEntity = eventPayload.payload?.payment?.entity;
    const subId = subEntity?.id;
    const userId = subEntity?.notes?.user_id || paymentEntity?.notes?.user_id;

    console.log(`[razorpay-webhook] Received event: ${eventName} for sub: ${subId || 'N/A'}`);

    const supabaseAdmin = getSupabaseAdminClient();

    // 4. Handle Subscription Lifecycle Events
    switch (eventName) {
      case 'subscription.authenticated':
      case 'subscription.activated': {
        if (subId && userId) {
          const startDate = subEntity.current_start
            ? new Date(subEntity.current_start * 1000).toISOString()
            : new Date().toISOString();
          const endDate = subEntity.current_end
            ? new Date(subEntity.current_end * 1000).toISOString()
            : new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString();

          const fullName = await getUserFullName(supabaseAdmin, userId);

          // Check if subscription record already exists
          const { data: existing } = await supabaseAdmin
            .from('subscriptions')
            .select('id, full_name')
            .eq('razorpay_order_id', subId)
            .maybeSingle();

          if (existing) {
            const updatePayload = {
              payment_status: 'completed',
              subscription_start_date: startDate,
              subscription_end_date: endDate,
              auto_renew: true,
              updated_at: new Date().toISOString(),
            };
            if (fullName && !existing.full_name) {
              updatePayload.full_name = fullName;
            }
            await supabaseAdmin
              .from('subscriptions')
              .update(updatePayload)
              .eq('id', existing.id);
          } else {
            await supabaseAdmin.from('subscriptions').insert([
              {
                user_id: userId,
                full_name: fullName,
                plan_type: 'monthly_30',
                amount_paid: 30.0,
                currency: 'INR',
                payment_status: 'completed',
                razorpay_order_id: subId,
                subscription_start_date: startDate,
                subscription_end_date: endDate,
                auto_renew: true,
              },
            ]);
          }
        }
        break;
      }

      case 'subscription.charged': {
        // Recurring charge successful
        if (subId && userId) {
          const paymentId = paymentEntity?.id;
          const startDate = subEntity.current_start
            ? new Date(subEntity.current_start * 1000).toISOString()
            : new Date().toISOString();
          const endDate = subEntity.current_end
            ? new Date(subEntity.current_end * 1000).toISOString()
            : new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString();

          // Check if this payment was already recorded
          if (paymentId) {
            const { data: existingPayment } = await supabaseAdmin
              .from('subscriptions')
              .select('id')
              .eq('razorpay_payment_id', paymentId)
              .maybeSingle();

            if (existingPayment) {
              break; // Already recorded
            }
          }

          const fullName = await getUserFullName(supabaseAdmin, userId);

          // Insert renewal cycle record or update existing sub
          await supabaseAdmin.from('subscriptions').insert([
            {
              user_id: userId,
              full_name: fullName,
              plan_type: 'monthly_30',
              amount_paid: 30.0,
              currency: 'INR',
              payment_status: 'completed',
              razorpay_payment_id: paymentId || null,
              razorpay_order_id: subId,
              subscription_start_date: startDate,
              subscription_end_date: endDate,
              auto_renew: true,
            },
          ]);
        }
        break;
      }

      case 'subscription.halted': {
        // Payment retries exhausted
        if (subId) {
          await supabaseAdmin
            .from('subscriptions')
            .update({
              payment_status: 'failed',
              auto_renew: false,
              updated_at: new Date().toISOString(),
            })
            .eq('razorpay_order_id', subId);
        }
        break;
      }

      case 'subscription.cancelled': {
        // User/Merchant cancelled subscription
        if (subId) {
          await supabaseAdmin
            .from('subscriptions')
            .update({
              auto_renew: false,
              updated_at: new Date().toISOString(),
            })
            .eq('razorpay_order_id', subId);
        }
        break;
      }

      case 'subscription.completed':
      case 'subscription.expired': {
        if (subId) {
          await supabaseAdmin
            .from('subscriptions')
            .update({
              auto_renew: false,
              updated_at: new Date().toISOString(),
            })
            .eq('razorpay_order_id', subId);
        }
        break;
      }

      default:
        // Unhandled event
        break;
    }

    if (eventId) markEventProcessed(eventId);

    return NextResponse.json({ status: 'ok', event: eventName });
  } catch (error) {
    console.error('[razorpay-webhook] Handler error:', error?.message || error);
    return NextResponse.json({ error: 'Webhook handler error' }, { status: 500 });
  }
}
