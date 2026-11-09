// Durable, Security-Hardened Reconciliation Script for Captured Razorpay Payments
// Safety Default: Runs in DRY-RUN mode unless explicitly invoked with --execute
// Usage:
//   Dry Run (safe inspection): node scripts/reconcile_captured_payments.mjs
//   Execute (write access):    node scripts/reconcile_captured_payments.mjs --execute
import Razorpay from 'razorpay';
import { createClient } from '@supabase/supabase-js';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const envPath = path.resolve(__dirname, '../.env.local');
if (fs.existsSync(envPath)) {
  const envContent = fs.readFileSync(envPath, 'utf8');
  envContent.split(/\r?\n/).forEach(line => {
    const trimmed = line.trim();
    if (trimmed && !trimmed.startsWith('#')) {
      const idx = trimmed.indexOf('=');
      if (idx !== -1) {
        const k = trimmed.substring(0, idx).trim();
        const v = trimmed.substring(idx + 1).trim();
        if (!process.env[k]) {
          process.env[k] = v;
        }
      }
    }
  });
}

// Enforce Dry-Run as default; writes require explicit --execute flag
const isExecute = process.argv.includes('--execute');
const isDryRun = !isExecute;

const keyId = process.env.RAZORPAY_KEY_ID || process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID;
const keySecret = process.env.RAZORPAY_KEY_SECRET;
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

if (!keyId || !keySecret || !supabaseUrl || !serviceKey) {
  console.error('[Reconcile] Missing required environment variables (Razorpay credentials or Supabase service key).');
  process.exit(1);
}

const rzp = new Razorpay({ key_id: keyId, key_secret: keySecret });
const supabaseAdmin = createClient(supabaseUrl, serviceKey, { auth: { persistSession: false } });

// Server-authoritative plan definitions
const ALLOWED_PLANS = {
  monthly_30: { amountPaise: 3000, price: 30.0, currency: 'INR' },
  yearly_250: { amountPaise: 25000, price: 250.0, currency: 'INR' },
};

async function reconcile() {
  console.log('================================================================');
  console.log(`RAZORPAY PAYMENT RECONCILIATION AUDIT`);
  console.log(`Mode: ${isDryRun ? 'DRY-RUN (Safe Read-Only - no database writes)' : '⚠️ EXECUTE MODE (Live database provisioning)'}`);
  console.log('================================================================\n');

  if (isDryRun) {
    console.log('[Notice] Running in default safe dry-run mode. Pass --execute to apply live reconciliations.\n');
  }

  // Fetch recent payments (up to 50)
  const payments = await rzp.payments.all({ count: 50 });
  const allItems = payments.items || [];
  console.log(`[Reconcile] Fetched ${allItems.length} recent payments from Razorpay API.\n`);

  let alreadySyncedCount = 0;
  let orphanedCapturedCount = 0;
  let skippedNonCapturedCount = 0;
  let skippedRefundedCount = 0;
  let skippedInvalidCount = 0;

  for (const pay of allItems) {
    const paymentId = pay.id;

    // 1. Strict Payment Status Check: Must be 'captured'
    if (pay.status !== 'captured') {
      skippedNonCapturedCount++;
      continue;
    }

    // 2. Refund / Reversal Check: Ignore refunded or partially refunded payments
    if (pay.refund_status !== null || (pay.amount_refunded && pay.amount_refunded > 0)) {
      console.warn(`[Reconcile] Payment ${paymentId} has been refunded (status: ${pay.refund_status}, amount_refunded: ${pay.amount_refunded}). Skipping.`);
      skippedRefundedCount++;
      continue;
    }

    // 3. Order ID Presence Check
    const orderId = pay.order_id;
    if (!orderId) {
      console.warn(`[Reconcile] Captured payment ${paymentId} has no associated order_id. Skipping.`);
      skippedInvalidCount++;
      continue;
    }

    // 4. Duplicate Check in Supabase Subscriptions Table
    const { data: existingSub, error: subErr } = await supabaseAdmin
      .from('subscriptions')
      .select('id, user_id, payment_status, plan_type, subscription_end_date')
      .eq('razorpay_payment_id', paymentId)
      .maybeSingle();

    if (subErr) {
      console.error(`[Reconcile] Database query error for payment ${paymentId}:`, subErr.message);
      continue;
    }

    if (existingSub && existingSub.payment_status === 'completed') {
      alreadySyncedCount++;
      continue;
    }

    // 5. Independent Verification of Order via Razorpay API
    let order;
    try {
      order = await rzp.orders.fetch(orderId);
    } catch (orderErr) {
      console.error(`[Reconcile] Unable to fetch order ${orderId} for payment ${paymentId}:`, orderErr.message);
      skippedInvalidCount++;
      continue;
    }

    if (!order || order.id !== orderId) {
      console.error(`[Reconcile] Order mismatch for payment ${paymentId}. Skipping.`);
      skippedInvalidCount++;
      continue;
    }

    // 6. User ID Association & Validation
    const userId = order.notes?.user_id || pay.notes?.user_id;
    if (!userId) {
      console.warn(`[Reconcile] Payment ${paymentId} / Order ${orderId} has no user_id in notes. Skipping.`);
      skippedInvalidCount++;
      continue;
    }

    // Verify user exists in public.users
    const { data: userProfile, error: userErr } = await supabaseAdmin
      .from('users')
      .select('id, full_name, email')
      .eq('id', userId)
      .maybeSingle();

    if (userErr || !userProfile) {
      console.error(`[Reconcile] User ${userId} for payment ${paymentId} not found in public.users. Skipping.`);
      skippedInvalidCount++;
      continue;
    }

    // 7. Plan Identifier & Amount Validation
    const rawPlan = order.notes?.plan_type || pay.notes?.plan_type;
    const planConfig = ALLOWED_PLANS[rawPlan];

    if (!planConfig) {
      console.error(`[Reconcile] Payment ${paymentId} references invalid plan '${rawPlan}'. Skipping.`);
      skippedInvalidCount++;
      continue;
    }

    // 8. Strict Amount and Currency Matching
    if (pay.amount !== planConfig.amountPaise || order.amount !== planConfig.amountPaise) {
      console.error(`[Reconcile] Payment amount ${pay.amount} paise does not match plan expected ${planConfig.amountPaise} paise. Skipping.`);
      skippedInvalidCount++;
      continue;
    }

    if (pay.currency !== 'INR' || order.currency !== 'INR') {
      console.error(`[Reconcile] Currency mismatch for payment ${paymentId} (${pay.currency}). Skipping.`);
      skippedInvalidCount++;
      continue;
    }

    // Payment is 100% verified as an orphaned, captured payment that needs reconciliation
    orphanedCapturedCount++;
    console.log(`[Reconcile] ⚠️ ORPHANED CAPTURED PAYMENT IDENTIFIED:`, {
      paymentId,
      orderId,
      userId,
      userEmail: userProfile.email,
      plan: rawPlan,
      amountINR: planConfig.price,
      currency: 'INR',
    });

    if (isDryRun) {
      console.log(`[Reconcile] [DRY-RUN] Would atomically provision ${rawPlan} (₹${planConfig.price}) for user ${userId}.\n`);
      continue;
    }

    // Live Execution Mode: Call the atomic RPC
    console.log(`[Reconcile] [LIVE] Invoking provision_subscription_access RPC for user ${userId}...`);
    const { data: rpcResult, error: rpcError } = await supabaseAdmin.rpc(
      'provision_subscription_access',
      {
        p_user_id: userId,
        p_full_name: userProfile.full_name || null,
        p_plan_type: rawPlan,
        p_amount_paid: planConfig.price,
        p_currency: 'INR',
        p_razorpay_payment_id: paymentId,
        p_razorpay_order_id: orderId,
      }
    );

    if (rpcError) {
      console.error(`[Reconcile] RPC execution failed for payment ${paymentId}:`, rpcError.message);
    } else if (rpcResult?.success) {
      console.log(`[Reconcile] ✅ Successfully provisioned subscription for payment ${paymentId}!`, rpcResult.subscription);
    } else {
      console.error(`[Reconcile] RPC rejected provisioning:`, rpcResult);
    }
  }

  console.log('\n================================================================');
  console.log(`RECONCILIATION AUDIT SUMMARY`);
  console.log(`  Already Synced (Active in Database):  ${alreadySyncedCount}`);
  console.log(`  Orphaned Captured Payments Found:    ${orphanedCapturedCount}`);
  console.log(`  Skipped (Non-captured/Authorized):    ${skippedNonCapturedCount}`);
  console.log(`  Skipped (Refunded/Reversed):         ${skippedRefundedCount}`);
  console.log(`  Skipped (Invalid/Unassociated):       ${skippedInvalidCount}`);
  console.log('================================================================\n');
}

reconcile().catch(err => {
  console.error('[Reconcile] Fatal error:', err);
  process.exit(1);
});
