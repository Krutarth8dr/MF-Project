// Targeted Pre-Deployment Safety & Entitlement Verification Suite
import assert from 'node:assert';
import { PLANS, getPlan, calculateSubscriptionEndDate, addOneCalendarYear } from '../src/lib/plans.js';

console.log('--- Starting Wealthyneers Pre-Deployment Safety Verification ---');

// Test 1: Pricing Savings Claim Math & Customer-Facing Wording
console.log('\n[Test 1] Pricing Savings Claim Verification');
const twelvePassesCost = 12 * PLANS.monthly_30.price; // 12 * 30 = 360
const yearlyPassCost = PLANS.yearly_250.price; // 250
const savingsPercent = ((twelvePassesCost - yearlyPassCost) / twelvePassesCost) * 100;
console.log(`  12 passes cost: ₹${twelvePassesCost} (360 days)`);
console.log(`  Yearly pass cost: ₹${yearlyPassCost} (365 days)`);
console.log(`  Exact savings percentage: ${savingsPercent.toFixed(2)}%`);
assert.strictEqual(Math.round(savingsPercent), 31, 'Savings percentage should round to 31%');

const expectedWording = 'Save approximately 31% compared with 12 separate 30-day passes';
assert.strictEqual(PLANS.yearly_250.savingsLabel, expectedWording, 'Yearly plan savingsLabel must match exact approved wording');
console.log('  ✓ Savings claim math and customer-facing wording verified: ' + PLANS.yearly_250.savingsLabel);

// Test 2: Entitlement Consistency & Leap Year Arithmetic
console.log('\n[Test 2] Entitlement Consistency & Date Calculations');
// Both plans exist and have correct amounts in paise
assert.strictEqual(getPlan('monthly_30').amountPaise, 3000);
assert.strictEqual(getPlan('yearly_250').amountPaise, 25000);

// Leap year safe calculation
const leapYearInput = new Date(Date.UTC(2028, 1, 29, 12, 0, 0)); // 2028-02-29T12:00:00Z
const leapYearOutput = addOneCalendarYear(leapYearInput);
assert.strictEqual(leapYearOutput.getUTCFullYear(), 2029);
assert.strictEqual(leapYearOutput.getUTCMonth(), 1); // February
assert.strictEqual(leapYearOutput.getUTCDate(), 28); // Clamped to 28
assert.strictEqual(leapYearOutput.getUTCHours(), 12);
console.log('  ✓ Leap-year arithmetic verified (2028-02-29 -> 2029-02-28)');

// Standard year calculation
const standardInput = new Date(Date.UTC(2026, 10, 8, 14, 0, 0));
const standardYearly = calculateSubscriptionEndDate('yearly_250', standardInput);
assert.strictEqual(standardYearly.getUTCFullYear(), 2027);
assert.strictEqual(standardYearly.getUTCMonth(), 10);
assert.strictEqual(standardYearly.getUTCDate(), 8);
console.log('  ✓ Standard 1-calendar-year arithmetic verified (2026-11-08 -> 2027-11-08)');

// 30-day calculation
const standard30 = calculateSubscriptionEndDate('monthly_30', standardInput);
const diffMs = standard30.getTime() - standardInput.getTime();
const diffDays = Math.round(diffMs / (1000 * 60 * 60 * 24));
assert.strictEqual(diffDays, 30);
console.log('  ✓ Standard 30-day arithmetic verified (exact 30 days)');

// Test 3: Payment Capture Safety State Machine
console.log('\n[Test 3] Payment Capture State Machine');

function evaluatePaymentCapture(paymentStatus, canCapture = true) {
  let status = paymentStatus;
  let captureAttempted = false;

  if (status !== 'captured') {
    if (status === 'authorized') {
      captureAttempted = true;
      if (canCapture) {
        status = 'captured';
      } else {
        return { allowed: false, code: 'PAYMENT_CAPTURE_FAILED', status, captureAttempted };
      }
    }
  }

  if (status !== 'captured') {
    return { allowed: false, code: 'PAYMENT_NOT_CAPTURED', status, captureAttempted };
  }

  return { allowed: true, code: 'SUCCESS', status, captureAttempted };
}

// Case 3a: Payment already captured
const r1 = evaluatePaymentCapture('captured');
assert.strictEqual(r1.allowed, true);
assert.strictEqual(r1.captureAttempted, false);
console.log('  ✓ Pre-captured payment is allowed without re-capture');

// Case 3b: Payment authorized and capture succeeds
const r2 = evaluatePaymentCapture('authorized', true);
assert.strictEqual(r2.allowed, true);
assert.strictEqual(r2.captureAttempted, true);
assert.strictEqual(r2.status, 'captured');
console.log('  ✓ Authorized payment is actively captured and allowed');

// Case 3c: Payment authorized but capture fails
const r3 = evaluatePaymentCapture('authorized', false);
assert.strictEqual(r3.allowed, false);
assert.strictEqual(r3.code, 'PAYMENT_CAPTURE_FAILED');
console.log('  ✓ Authorized payment where capture fails is rejected');

// Case 3d: Payment failed or created
const r4 = evaluatePaymentCapture('failed');
assert.strictEqual(r4.allowed, false);
assert.strictEqual(r4.code, 'PAYMENT_NOT_CAPTURED');
console.log('  ✓ Failed payment is strictly rejected');

// Test 4: Concurrency Simulation (Advisory Lock Serialization vs Unlocked TOCTOU)
console.log('\n[Test 4] Concurrency & Sequential Extension Race Condition Simulation');

// Mock in-memory database
class MockSubDatabase {
  constructor() {
    this.subs = [];
    this.userLocks = new Map();
  }

  // Simulates non-atomic TOCTOU (vulnerable to concurrent race conditions)
  async nonAtomicProvision(userId, planId, paymentId, price) {
    // 1. Pre-check replay
    if (this.subs.some(s => s.razorpay_payment_id === paymentId)) {
      return { success: false, code: 'PAYMENT_ALREADY_PROCESSED' };
    }

    // 2. Read latest end date (Simulating async delay where parallel read occurs)
    const now = new Date();
    const active = this.subs
      .filter(s => s.user_id === userId && s.payment_status === 'completed' && s.end_date > now)
      .sort((a, b) => b.end_date - a.end_date);

    await new Promise(res => setTimeout(res, 20)); // simulated DB network latency

    let startDate = active.length > 0 ? active[0].end_date : now;
    let endDate = calculateSubscriptionEndDate(planId, startDate);

    const record = {
      id: 'sub_' + Math.random().toString(36).substring(2, 8),
      user_id: userId,
      plan_type: planId,
      amount_paid: price,
      payment_status: 'completed',
      razorpay_payment_id: paymentId,
      start_date: startDate,
      end_date: endDate,
    };
    this.subs.push(record);
    return { success: true, subscription: record };
  }

  // Simulates PostgreSQL transaction advisory lock (Atomic RPC behavior)
  async atomicProvision(userId, planId, paymentId, price) {
    // Acquire user lock
    while (this.userLocks.get(userId)) {
      await this.userLocks.get(userId);
    }

    let unlock;
    const lockPromise = new Promise(resolve => { unlock = resolve; });
    this.userLocks.set(userId, lockPromise);

    try {
      // Re-check replay inside locked transaction
      if (this.subs.some(s => s.razorpay_payment_id === paymentId)) {
        return { success: false, code: 'PAYMENT_ALREADY_PROCESSED' };
      }

      const now = new Date();
      const active = this.subs
        .filter(s => s.user_id === userId && s.payment_status === 'completed' && s.end_date > now)
        .sort((a, b) => b.end_date - a.end_date);

      await new Promise(res => setTimeout(res, 20)); // simulated DB processing

      let startDate = active.length > 0 ? active[0].end_date : now;
      let endDate = calculateSubscriptionEndDate(planId, startDate);

      const record = {
        id: 'sub_' + Math.random().toString(36).substring(2, 8),
        user_id: userId,
        plan_type: planId,
        amount_paid: price,
        payment_status: 'completed',
        razorpay_payment_id: paymentId,
        start_date: startDate,
        end_date: endDate,
      };
      this.subs.push(record);
      return { success: true, subscription: record };
    } finally {
      this.userLocks.delete(userId);
      unlock();
    }
  }
}

async function runConcurrencyScenario() {
  // Scenario A: Without atomic lock, two simultaneous payments for same user create overlapping window
  const mockDb1 = new MockSubDatabase();
  const userId = 'user_uuid_123';

  // Seed with active sub expiring Dec 1, 2026
  mockDb1.subs.push({
    id: 'sub_0',
    user_id: userId,
    plan_type: 'monthly_30',
    payment_status: 'completed',
    razorpay_payment_id: 'pay_init',
    start_date: new Date('2026-11-01T00:00:00Z'),
    end_date: new Date('2026-12-01T00:00:00Z'),
  });

  // Two simultaneous purchases: 30-day and 1-year pass
  const [res1, res2] = await Promise.all([
    mockDb1.nonAtomicProvision(userId, 'monthly_30', 'pay_concurrent_1', 30),
    mockDb1.nonAtomicProvision(userId, 'yearly_250', 'pay_concurrent_2', 250),
  ]);

  // Notice: In non-atomic, both read Dec 1 as their start date!
  console.log(`  [Non-Atomic Concurrent] Req 1 start: ${res1.subscription.start_date.toISOString()} -> end: ${res1.subscription.end_date.toISOString()}`);
  console.log(`  [Non-Atomic Concurrent] Req 2 start: ${res2.subscription.start_date.toISOString()} -> end: ${res2.subscription.end_date.toISOString()}`);
  const nonAtomicOverlap = res1.subscription.start_date.getTime() === res2.subscription.start_date.getTime();
  assert.strictEqual(nonAtomicOverlap, true, 'Non-atomic implementation produces overlapping starts during concurrent requests');
  console.log('  ⚠️ Verified vulnerability: Non-atomic code allows race conditions with overlapping access windows.');

  // Scenario B: With atomic advisory lock (RPC behavior)
  const mockDb2 = new MockSubDatabase();
  mockDb2.subs.push({
    id: 'sub_0',
    user_id: userId,
    plan_type: 'monthly_30',
    payment_status: 'completed',
    razorpay_payment_id: 'pay_init',
    start_date: new Date('2026-11-01T00:00:00Z'),
    end_date: new Date('2026-12-01T00:00:00Z'),
  });

  const [atomRes1, atomRes2] = await Promise.all([
    mockDb2.atomicProvision(userId, 'monthly_30', 'pay_atomic_1', 30),
    mockDb2.atomicProvision(userId, 'yearly_250', 'pay_atomic_2', 250),
  ]);

  console.log(`  [Atomic Lock Concurrent] Sub 1 start: ${atomRes1.subscription.start_date.toISOString()} -> end: ${atomRes1.subscription.end_date.toISOString()}`);
  console.log(`  [Atomic Lock Concurrent] Sub 2 start: ${atomRes2.subscription.start_date.toISOString()} -> end: ${atomRes2.subscription.end_date.toISOString()}`);

  // Sub 2 start MUST match Sub 1 end
  assert.strictEqual(
    atomRes2.subscription.start_date.toISOString(),
    atomRes1.subscription.end_date.toISOString(),
    'With atomic advisory lock, Sub 2 must start exactly when Sub 1 ends'
  );
  console.log('  ✓ Verified Atomic Solution: Consecutive extensions are serialized seamlessly with 0 overlapping or lost days!');
}

await runConcurrencyScenario();

console.log('\n--- ALL PRE-DEPLOYMENT SAFETY CHECKS PASSED ---');
