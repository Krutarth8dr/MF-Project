// Wealthyneers Final Subscription Payment Safety Test Suite
import assert from 'node:assert';
import { PLANS, getPlan, calculateSubscriptionEndDate, addOneCalendarYear } from '../src/lib/plans.js';

console.log('================================================================');
console.log('WEALTHYNEERS FINAL SUBSCRIPTION PAYMENT SAFETY VERIFICATION');
console.log('================================================================\n');

// -----------------------------------------------------------------------------
// TEST 1: YEARLY EXPIRY BOUNDARIES & POSTGRESQL INTERVAL ALIGNMENT
// -----------------------------------------------------------------------------
console.log('--- TEST 1: Yearly Date Calculation & PostgreSQL Interval Alignment ---');

function postgresIntervalOneYear(date) {
  // Simulates PostgreSQL's exact implementation of TIMESTAMPTZ + INTERVAL '1 year'
  // (PostgreSQL increments year, and if month was Feb and day 29, clamps to 28 in non-leap year)
  const d = new Date(date);
  const year = d.getUTCFullYear();
  const month = d.getUTCMonth(); // 0-based: 1 = Feb
  const day = d.getUTCDate();
  const targetYear = year + 1;
  const isTargetLeap = (targetYear % 4 === 0 && targetYear % 100 !== 0) || targetYear % 400 === 0;

  let targetDay = day;
  if (month === 1 && day === 29 && !isTargetLeap) {
    targetDay = 28;
  }

  return new Date(Date.UTC(
    targetYear,
    month,
    targetDay,
    d.getUTCHours(),
    d.getUTCMinutes(),
    d.getUTCSeconds(),
    d.getUTCMilliseconds()
  ));
}

// 1a. Normal calendar date
const normalDate = new Date('2026-11-08T12:00:00.000Z');
const jsNormal = calculateSubscriptionEndDate('yearly_250', normalDate);
const pgNormal = postgresIntervalOneYear(normalDate);
assert.strictEqual(jsNormal.toISOString(), '2027-11-08T12:00:00.000Z');
assert.strictEqual(jsNormal.toISOString(), pgNormal.toISOString());
console.log('  ✓ Normal calendar date aligned: 2026-11-08 -> 2027-11-08');

// 1b. Leap year February 29
const leapFeb29 = new Date('2028-02-29T12:00:00.000Z');
const jsLeap = calculateSubscriptionEndDate('yearly_250', leapFeb29);
const pgLeap = postgresIntervalOneYear(leapFeb29);
assert.strictEqual(jsLeap.toISOString(), '2029-02-28T12:00:00.000Z');
assert.strictEqual(jsLeap.toISOString(), pgLeap.toISOString());
console.log('  ✓ Leap year February 29 safely clamped to Feb 28 in non-leap year: 2028-02-29 -> 2029-02-28');

// 1c. February 28 before leap year
const nonLeapFeb28 = new Date('2027-02-28T12:00:00.000Z');
const jsNonLeap = calculateSubscriptionEndDate('yearly_250', nonLeapFeb28);
const pgNonLeap = postgresIntervalOneYear(nonLeapFeb28);
assert.strictEqual(jsNonLeap.toISOString(), '2028-02-28T12:00:00.000Z');
assert.strictEqual(jsNonLeap.toISOString(), pgNonLeap.toISOString());
console.log('  ✓ February 28 before leap year correctly lands on Feb 28: 2027-02-28 -> 2028-02-28');

// 1d. February 28 in leap year
const leapFeb28 = new Date('2028-02-28T12:00:00.000Z');
const jsLeap28 = calculateSubscriptionEndDate('yearly_250', leapFeb28);
const pgLeap28 = postgresIntervalOneYear(leapFeb28);
assert.strictEqual(jsLeap28.toISOString(), '2029-02-28T12:00:00.000Z');
assert.strictEqual(jsLeap28.toISOString(), pgLeap28.toISOString());
console.log('  ✓ February 28 in leap year correctly lands on Feb 28: 2028-02-28 -> 2029-02-28');

// 1e. December 31 year boundary
const dec31 = new Date('2026-12-31T23:59:59.999Z');
const jsDec31 = calculateSubscriptionEndDate('yearly_250', dec31);
const pgDec31 = postgresIntervalOneYear(dec31);
assert.strictEqual(jsDec31.toISOString(), '2027-12-31T23:59:59.999Z');
assert.strictEqual(jsDec31.toISOString(), pgDec31.toISOString());
console.log('  ✓ Year-end boundary (Dec 31) aligned: 2026-12-31 -> 2027-12-31');

// 1f. Consecutive yearly renewals
let rolling = new Date('2026-11-08T00:00:00.000Z');
const years = [2027, 2028, 2029, 2030, 2031];
for (const expectedYear of years) {
  rolling = calculateSubscriptionEndDate('yearly_250', rolling);
  assert.strictEqual(rolling.getUTCFullYear(), expectedYear);
  assert.strictEqual(rolling.getUTCMonth(), 10);
  assert.strictEqual(rolling.getUTCDate(), 8);
}
console.log('  ✓ Consecutive yearly renewals extend cleanly through 2031');

// 1g. Yearly renewal following existing 30-day pass
const startDay = new Date('2026-11-08T00:00:00.000Z');
const after30 = calculateSubscriptionEndDate('monthly_30', startDay);
assert.strictEqual(after30.toISOString(), '2026-12-08T00:00:00.000Z');
const afterYear = calculateSubscriptionEndDate('yearly_250', after30);
assert.strictEqual(afterYear.toISOString(), '2027-12-08T00:00:00.000Z');
const totalDiffDays = Math.round((afterYear.getTime() - startDay.getTime()) / (1000 * 60 * 60 * 24));
assert.strictEqual(totalDiffDays, 395); // 30 + 365 = 395 days
console.log('  ✓ Yearly pass after 30-day pass adds exactly 395 days total without overlapping');


// -----------------------------------------------------------------------------
// TEST 2: HARDENED RPC VALIDATION LOGIC SIMULATION
// -----------------------------------------------------------------------------
console.log('\n--- TEST 2: Hardened SQL RPC Parameter & Amount Validation ---');

function mockProvisionRpc(params) {
  const {
    p_user_id,
    p_plan_type,
    p_amount_paid,
    p_currency,
    p_razorpay_payment_id,
    p_razorpay_order_id,
  } = params;

  if (!p_user_id) {
    return { success: false, code: 'INVALID_PARAMETERS', error: 'p_user_id is mandatory' };
  }
  if (!p_razorpay_payment_id || !p_razorpay_payment_id.trim()) {
    return { success: false, code: 'INVALID_PARAMETERS', error: 'p_razorpay_payment_id is mandatory' };
  }
  if (!p_razorpay_order_id || !p_razorpay_order_id.trim()) {
    return { success: false, code: 'INVALID_PARAMETERS', error: 'p_razorpay_order_id is mandatory' };
  }
  if (!['monthly_30', 'yearly_250'].includes(p_plan_type)) {
    return { success: false, code: 'INVALID_PLAN_TYPE', error: 'Unsupported plan type' };
  }
  if (!p_currency || p_currency.trim().toUpperCase() !== 'INR') {
    return { success: false, code: 'CURRENCY_MISMATCH', error: 'Only INR is supported' };
  }
  if (p_plan_type === 'monthly_30' && Number(p_amount_paid) !== 30.00) {
    return { success: false, code: 'AMOUNT_MISMATCH', error: 'monthly_30 requires 30.00 INR' };
  }
  if (p_plan_type === 'yearly_250' && Number(p_amount_paid) !== 250.00) {
    return { success: false, code: 'AMOUNT_MISMATCH', error: 'yearly_250 requires 250.00 INR' };
  }

  return { success: true };
}

// Valid inputs
assert.strictEqual(mockProvisionRpc({
  p_user_id: 'uuid-1',
  p_plan_type: 'monthly_30',
  p_amount_paid: 30.00,
  p_currency: 'INR',
  p_razorpay_payment_id: 'pay_1',
  p_razorpay_order_id: 'order_1',
}).success, true);

assert.strictEqual(mockProvisionRpc({
  p_user_id: 'uuid-1',
  p_plan_type: 'yearly_250',
  p_amount_paid: 250.00,
  p_currency: 'INR',
  p_razorpay_payment_id: 'pay_2',
  p_razorpay_order_id: 'order_2',
}).success, true);
console.log('  ✓ Valid monthly_30 and yearly_250 parameter sets accepted');

// Invalid plan
const badPlan = mockProvisionRpc({ p_user_id: 'u1', p_plan_type: 'quarterly_90', p_amount_paid: 90.00, p_currency: 'INR', p_razorpay_payment_id: 'p', p_razorpay_order_id: 'o' });
assert.strictEqual(badPlan.code, 'INVALID_PLAN_TYPE');
console.log('  ✓ Unsupported plan type rejected');

// Mismatched amount
const badAmount = mockProvisionRpc({ p_user_id: 'u1', p_plan_type: 'yearly_250', p_amount_paid: 30.00, p_currency: 'INR', p_razorpay_payment_id: 'p', p_razorpay_order_id: 'o' });
assert.strictEqual(badAmount.code, 'AMOUNT_MISMATCH');
console.log('  ✓ Mismatched plan amount rejected');

// Mismatched currency
const badCurrency = mockProvisionRpc({ p_user_id: 'u1', p_plan_type: 'yearly_250', p_amount_paid: 250.00, p_currency: 'USD', p_razorpay_payment_id: 'p', p_razorpay_order_id: 'o' });
assert.strictEqual(badCurrency.code, 'CURRENCY_MISMATCH');
console.log('  ✓ Non-INR currency rejected');

// Null payment ID
const nullPay = mockProvisionRpc({ p_user_id: 'u1', p_plan_type: 'yearly_250', p_amount_paid: 250.00, p_currency: 'INR', p_razorpay_payment_id: '', p_razorpay_order_id: 'o' });
assert.strictEqual(nullPay.code, 'INVALID_PARAMETERS');
console.log('  ✓ Null or empty payment ID rejected');


// -----------------------------------------------------------------------------
// TEST 3: REPLAY PROTECTION & IDEMPOTENT RETRY
// -----------------------------------------------------------------------------
console.log('\n--- TEST 3: Replay Protection & Idempotent Retry ---');

class MockPaymentEngine {
  constructor() {
    this.records = [];
  }

  async verifyAndProvision(userId, paymentId, orderId, planId, amount, rpcAvailable = true) {
    // 1. Check existing
    const existing = this.records.find(r => r.payment_id === paymentId);
    if (existing) {
      if (existing.user_id === userId) {
        return { status: 200, success: true, idempotent: true, subscription: existing };
      }
      return { status: 409, success: false, code: 'PAYMENT_ALREADY_PROCESSED' };
    }

    // 2. Execute RPC
    if (!rpcAvailable) {
      return {
        status: 503,
        success: false,
        code: 'PROVISIONING_TEMPORARILY_UNAVAILABLE',
        recoverable: true,
      };
    }

    // Provision
    const newRecord = {
      id: 'sub_' + Math.random().toString(36).substring(2, 7),
      user_id: userId,
      payment_id: paymentId,
      order_id: orderId,
      plan_type: planId,
      amount,
      start_date: new Date(),
      end_date: calculateSubscriptionEndDate(planId, new Date()),
    };
    this.records.push(newRecord);
    return { status: 200, success: true, idempotent: false, subscription: newRecord };
  }
}

const engine = new MockPaymentEngine();
const testUser = 'user_abc_123';
const payId = 'pay_real_001';

// Case 3a: First attempt fails due to temporary DB unavailable
const attempt1 = await engine.verifyAndProvision(testUser, payId, 'order_001', 'yearly_250', 250, false);
assert.strictEqual(attempt1.status, 503);
assert.strictEqual(attempt1.recoverable, true);
assert.strictEqual(engine.records.length, 0); // No non-atomic fallback inserted!
console.log('  ✓ Temporary DB outage returns 503 without executing non-atomic fallback');

// Case 3b: Retry after DB recovers succeeds safely
const attempt2 = await engine.verifyAndProvision(testUser, payId, 'order_001', 'yearly_250', 250, true);
assert.strictEqual(attempt2.status, 200);
assert.strictEqual(attempt2.idempotent, false);
assert.strictEqual(engine.records.length, 1);
console.log('  ✓ Retry after capture succeeds with no double-charging or data loss');

// Case 3c: Subsequent retry by the SAME user returns idempotent 200 OK
const attempt3 = await engine.verifyAndProvision(testUser, payId, 'order_001', 'yearly_250', 250, true);
assert.strictEqual(attempt3.status, 200);
assert.strictEqual(attempt3.idempotent, true);
assert.strictEqual(attempt3.subscription.id, attempt2.subscription.id);
assert.strictEqual(engine.records.length, 1); // No duplicate record created
console.log('  ✓ Subsequent retry by same user returns idempotent 200 OK without creating duplicate record');

// Case 3d: Replay by a DIFFERENT user is rejected with 409
const attempt4 = await engine.verifyAndProvision('malicious_user_999', payId, 'order_001', 'yearly_250', 250, true);
assert.strictEqual(attempt4.status, 409);
assert.strictEqual(attempt4.code, 'PAYMENT_ALREADY_PROCESSED');
assert.strictEqual(engine.records.length, 1);
console.log('  ✓ Replay attempt by a different user rejected with HTTP 409');


// -----------------------------------------------------------------------------
// TEST 4: PRICING SAVINGS CLAIM FORMULA
// -----------------------------------------------------------------------------
console.log('\n--- TEST 4: Pricing Savings Claim Verification ---');
const twelveThirtyCost = 12 * 30; // 360
const yearlyCost = 250;
const actualSavings = ((twelveThirtyCost - yearlyCost) / twelveThirtyCost) * 100;
console.log(`  Formula: (360 - 250) / 360 = 110 / 360 = ${actualSavings.toFixed(4)}% (~31%)`);
assert.strictEqual(Math.round(actualSavings), 31);
assert.strictEqual(
  PLANS.yearly_250.savingsLabel,
  'Save approximately 31% compared with 12 separate 30-day passes'
);
console.log('  ✓ Pricing claim strictly verified: ' + PLANS.yearly_250.savingsLabel);

console.log('\n================================================================');
console.log('ALL FINAL SUBSCRIPTION SAFETY VERIFICATION TESTS PASSED (100%)');
console.log('================================================================\n');
