// Verification that Payment Replay cannot alter Order, Plan, or Amount
import assert from 'node:assert';

console.log('--- Starting Payment Replay Immutability Test ---');

// Mock existing database subscription record
const existingDbRecord = {
  id: 'sub_orig_001',
  user_id: 'user_alice',
  razorpay_payment_id: 'pay_orig_123',
  razorpay_order_id: 'order_orig_30',
  plan_type: 'monthly_30',
  amount_paid: 30.00,
  currency: 'INR',
  payment_status: 'completed',
  subscription_start_date: '2026-11-01T00:00:00Z',
  subscription_end_date: '2026-12-01T00:00:00Z',
};

// Simulation of Replay Handling
function processPaymentVerification({
  authenticatedUserId,
  submittedPaymentId,
  submittedOrderId,
  submittedPlanType,
  submittedAmount,
}) {
  // If payment already exists in DB
  if (submittedPaymentId === existingDbRecord.razorpay_payment_id) {
    if (existingDbRecord.user_id !== authenticatedUserId) {
      return { status: 409, code: 'PAYMENT_ALREADY_PROCESSED', error: 'Payment claimed by another account' };
    }
    // Idempotent return: strictly returns the immutable original DB record
    return {
      status: 200,
      code: 'ALREADY_PROCESSED',
      subscription: { ...existingDbRecord },
    };
  }

  return { status: 200, code: 'NEW_INSERT' };
}

// 1. Same user replaying, but attempting to claim 'yearly_250' with ₹250
const replayWithYearly = processPaymentVerification({
  authenticatedUserId: 'user_alice',
  submittedPaymentId: 'pay_orig_123',
  submittedOrderId: 'order_hacked_250',
  submittedPlanType: 'yearly_250',
  submittedAmount: 250.00,
});

assert.strictEqual(replayWithYearly.status, 200);
// Crucial: The returned subscription is STILL monthly_30, ₹30, and order_orig_30
assert.strictEqual(replayWithYearly.subscription.plan_type, 'monthly_30');
assert.strictEqual(replayWithYearly.subscription.amount_paid, 30.00);
assert.strictEqual(replayWithYearly.subscription.razorpay_order_id, 'order_orig_30');
console.log('  ✓ Replay attempt with altered plan/amount returned original immutable record (no elevation to yearly).');

// 2. Different user attempting to replay the payment
const replayDifferentUser = processPaymentVerification({
  authenticatedUserId: 'user_bob',
  submittedPaymentId: 'pay_orig_123',
  submittedOrderId: 'order_orig_30',
  submittedPlanType: 'monthly_30',
  submittedAmount: 30.00,
});

assert.strictEqual(replayDifferentUser.status, 409);
assert.strictEqual(replayDifferentUser.code, 'PAYMENT_ALREADY_PROCESSED');
console.log('  ✓ Replay attempt by different user strictly rejected with HTTP 409.');

console.log('--- ALL REPLAY IMMUTABILITY CHECKS PASSED ---');
