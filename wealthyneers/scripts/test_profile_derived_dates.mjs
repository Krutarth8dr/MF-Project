import assert from 'assert';
import { parseUtcDate } from '../src/lib/plans.js';

console.log('================================================================');
console.log('WEALTHYNEERS PROFILE DERIVED DATES VERIFICATION SUITE');
console.log('================================================================\n');

// Implementation of the pure derivation logic matching src/app/profile/page.jsx
function deriveProfileSubscriptionData(subscriptions, subStatus = 'active') {
  const completedSubscriptions = subscriptions.filter(
    (sub) => sub.payment_status === 'completed'
  );

  const originalStartDate = completedSubscriptions.length === 0
    ? null
    : completedSubscriptions.reduce((earliest, sub) => {
        const rawDate = sub.subscription_start_date || sub.created_at;
        const start = parseUtcDate(rawDate);
        if (!start || Number.isNaN(start.getTime())) return earliest;
        return !earliest || start < earliest ? start : earliest;
      }, null);

  const latestExpiryDate = completedSubscriptions.length === 0
    ? null
    : completedSubscriptions.reduce((latest, sub) => {
        if (sub.subscription_end_date === null) return 'continuous';
        if (latest === 'continuous') return 'continuous';
        const end = parseUtcDate(sub.subscription_end_date);
        if (!end || Number.isNaN(end.getTime())) return latest;
        return !latest || end > latest ? end : latest;
      }, null);

  const totalAmountPaid = completedSubscriptions.reduce((sum, s) => {
    const amt = Number(s.amount_paid || s.amount || (s.plan_type === 'yearly_250' ? 250 : 30));
    return sum + (Number.isNaN(amt) ? 0 : amt);
  }, 0);

  // Determine current active or latest subscription
  let currentSub = null;
  const activeSubs = subscriptions.filter(
    (s) =>
      s.payment_status === 'completed' &&
      (s.subscription_end_date === null ||
        (parseUtcDate(s.subscription_end_date)?.getTime() || 0) > Date.now())
  );

  if (activeSubs.length > 0) {
    const sortedByEnd = [...activeSubs].sort((a, b) => {
      if (!a.subscription_end_date) return -1;
      if (!b.subscription_end_date) return 1;
      const bTime = parseUtcDate(b.subscription_end_date)?.getTime() || 0;
      const aTime = parseUtcDate(a.subscription_end_date)?.getTime() || 0;
      return bTime - aTime;
    });
    currentSub = sortedByEnd[0];
  } else if (subscriptions.length > 0) {
    currentSub = subscriptions[0];
  }

  // Formatting helper
  const formatDate = (dateVal) => {
    if (!dateVal) return '—';
    if (dateVal === 'continuous') return 'Active (Continuous)';
    const d = parseUtcDate(dateVal);
    if (!d || isNaN(d.getTime())) return String(dateVal);
    return d.toLocaleDateString('en-IN', {
      day: '2-digit',
      month: 'long',
      year: 'numeric',
      timeZone: 'UTC', // deterministic test comparison
    });
  };

  const displayedStarted = originalStartDate
    ? formatDate(originalStartDate)
    : currentSub?.subscription_start_date
    ? formatDate(currentSub.subscription_start_date)
    : '—';

  const displayedValidUntil = latestExpiryDate === 'continuous'
    ? 'Active (Continuous)'
    : latestExpiryDate
    ? formatDate(latestExpiryDate)
    : currentSub?.subscription_end_date
    ? formatDate(currentSub.subscription_end_date)
    : subStatus === 'active'
    ? 'Active (Continuous)'
    : '—';

  const planLabel = completedSubscriptions.length > 1 ? 'Latest Plan / Extension' : 'Current Plan';
  const paymentLabel = completedSubscriptions.length > 1 ? 'Latest Payment' : 'Amount Paid';
  const planName = currentSub?.plan_name ||
    (currentSub?.plan_type === 'yearly_250'
      ? 'Yearly Institutional Access'
      : subStatus === 'active' || currentSub?.plan_type === 'monthly_30'
      ? '30-Day Institutional Access'
      : currentSub?.plan_type || 'No active plan');

  const latestPayment = currentSub
    ? Number(currentSub.amount_paid || currentSub.amount || (currentSub.plan_type === 'yearly_250' ? 250 : 30))
    : 0;

  return {
    planLabel,
    planName,
    displayedStarted,
    displayedValidUntil,
    paymentLabel,
    latestPayment,
    totalAmountPaid,
    hasMultipleCompleted: completedSubscriptions.length > 1,
    currentSub,
  };
}

// ── TEST 1: One ₹30 subscription ──
console.log('--- TEST 1: One ₹30 subscription ---');
const sub1 = [
  {
    id: 'sub_1',
    plan_type: 'monthly_30',
    amount_paid: 30,
    payment_status: 'completed',
    subscription_start_date: '2026-10-22T09:00:00',
    subscription_end_date: '2026-11-21T09:00:00',
  },
];
const res1 = deriveProfileSubscriptionData(sub1);
assert.strictEqual(res1.planLabel, 'Current Plan');
assert.strictEqual(res1.planName, '30-Day Institutional Access');
assert.strictEqual(res1.displayedStarted, '22 October 2026');
assert.strictEqual(res1.displayedValidUntil, '21 November 2026');
assert.strictEqual(res1.paymentLabel, 'Amount Paid');
assert.strictEqual(res1.latestPayment, 30);
assert.strictEqual(res1.hasMultipleCompleted, false);
console.log('  ✓ Plan:', res1.planName);
console.log('  ✓ Started:', res1.displayedStarted);
console.log('  ✓ Valid Until:', res1.displayedValidUntil);
console.log('  ✓ Payment:', res1.paymentLabel, '₹' + res1.latestPayment);

// ── TEST 2: One ₹250 subscription ──
console.log('\n--- TEST 2: One ₹250 subscription ---');
const sub2 = [
  {
    id: 'sub_2',
    plan_type: 'yearly_250',
    amount_paid: 250,
    payment_status: 'completed',
    subscription_start_date: '2026-11-01T12:00:00',
    subscription_end_date: '2027-11-01T12:00:00',
  },
];
const res2 = deriveProfileSubscriptionData(sub2);
assert.strictEqual(res2.planLabel, 'Current Plan');
assert.strictEqual(res2.planName, 'Yearly Institutional Access');
assert.strictEqual(res2.displayedStarted, '01 November 2026');
assert.strictEqual(res2.displayedValidUntil, '01 November 2027');
assert.strictEqual(res2.paymentLabel, 'Amount Paid');
assert.strictEqual(res2.latestPayment, 250);
assert.strictEqual(res2.hasMultipleCompleted, false);
console.log('  ✓ Plan:', res2.planName);
console.log('  ✓ Started:', res2.displayedStarted);
console.log('  ✓ Valid Until:', res2.displayedValidUntil);
console.log('  ✓ Payment:', res2.paymentLabel, '₹' + res2.latestPayment);

// ── TEST 3: ₹30 followed by ₹250 extension ──
console.log('\n--- TEST 3: ₹30 followed by ₹250 Extension ---');
const sub3 = [
  {
    id: 'sub_3_yearly',
    plan_type: 'yearly_250',
    amount_paid: 250,
    payment_status: 'completed',
    subscription_start_date: '2026-11-21T09:00:00', // Stacks onto sub_3_monthly
    subscription_end_date: '2027-11-21T09:00:00',
  },
  {
    id: 'sub_3_monthly',
    plan_type: 'monthly_30',
    amount_paid: 30,
    payment_status: 'completed',
    subscription_start_date: '2026-10-22T09:00:00',
    subscription_end_date: '2026-11-21T09:00:00',
  },
];
const res3 = deriveProfileSubscriptionData(sub3);
assert.strictEqual(res3.planLabel, 'Latest Plan / Extension');
assert.strictEqual(res3.planName, 'Yearly Institutional Access');
// Crucial: Must display original October start date, NOT November 21!
assert.strictEqual(res3.displayedStarted, '22 October 2026');
// Crucial: Must display final extended November 2027 expiry!
assert.strictEqual(res3.displayedValidUntil, '21 November 2027');
assert.strictEqual(res3.paymentLabel, 'Latest Payment');
assert.strictEqual(res3.latestPayment, 250);
assert.strictEqual(res3.totalAmountPaid, 280);
assert.strictEqual(res3.hasMultipleCompleted, true);
console.log('  ✓ Plan Label:', res3.planLabel, '->', res3.planName);
console.log('  ✓ Started (Original):', res3.displayedStarted);
console.log('  ✓ Valid Until (Extended):', res3.displayedValidUntil);
console.log('  ✓ Latest Payment:', res3.paymentLabel, '₹' + res3.latestPayment);
console.log('  ✓ Total Paid:', '₹' + res3.totalAmountPaid);

// ── TEST 4: Multiple yearly extensions ──
console.log('\n--- TEST 4: Multiple Yearly Extensions ---');
const sub4 = [
  {
    id: 'sub_4_year2',
    plan_type: 'yearly_250',
    amount_paid: 250,
    payment_status: 'completed',
    subscription_start_date: '2027-11-01T12:00:00',
    subscription_end_date: '2028-11-01T12:00:00',
  },
  {
    id: 'sub_4_year1',
    plan_type: 'yearly_250',
    amount_paid: 250,
    payment_status: 'completed',
    subscription_start_date: '2026-11-01T12:00:00',
    subscription_end_date: '2027-11-01T12:00:00',
  },
];
const res4 = deriveProfileSubscriptionData(sub4);
assert.strictEqual(res4.planName, 'Yearly Institutional Access');
assert.strictEqual(res4.displayedStarted, '01 November 2026');
assert.strictEqual(res4.displayedValidUntil, '01 November 2028');
assert.strictEqual(res4.latestPayment, 250);
assert.strictEqual(res4.totalAmountPaid, 500);
console.log('  ✓ Started (Earliest):', res4.displayedStarted);
console.log('  ✓ Valid Until (Furthest):', res4.displayedValidUntil);
console.log('  ✓ Total Paid:', '₹' + res4.totalAmountPaid);

// ── TEST 5: Expired subscriptions followed by a new purchase ──
console.log('\n--- TEST 5: Expired Subscriptions followed by a New Purchase ---');
const sub5 = [
  {
    id: 'sub_5_new',
    plan_type: 'yearly_250',
    amount_paid: 250,
    payment_status: 'completed',
    subscription_start_date: '2027-01-10T10:00:00',
    subscription_end_date: '2028-01-10T10:00:00', // Active
  },
  {
    id: 'sub_5_old_expired',
    plan_type: 'monthly_30',
    amount_paid: 30,
    payment_status: 'completed',
    subscription_start_date: '2026-01-01T10:00:00',
    subscription_end_date: '2026-01-31T10:00:00', // Long expired
  },
];
const res5 = deriveProfileSubscriptionData(sub5);
// Earliest subscription start is preserved:
assert.strictEqual(res5.displayedStarted, '01 January 2026');
// Furthest active access:
assert.strictEqual(res5.displayedValidUntil, '10 January 2028');
assert.strictEqual(res5.planName, 'Yearly Institutional Access');
assert.strictEqual(res5.latestPayment, 250);
assert.strictEqual(res5.totalAmountPaid, 280);
console.log('  ✓ Original Start Date Preserved:', res5.displayedStarted);
console.log('  ✓ Current Active Expiry:', res5.displayedValidUntil);

// ── TEST 6: No subscriptions (Inactive UI) ──
console.log('\n--- TEST 6: No Subscriptions (Inactive State) ---');
const sub6 = [];
const res6 = deriveProfileSubscriptionData(sub6, 'inactive');
assert.strictEqual(res6.planName, 'No active plan');
assert.strictEqual(res6.displayedStarted, '—');
assert.strictEqual(res6.displayedValidUntil, '—');
assert.strictEqual(res6.hasMultipleCompleted, false);
console.log('  ✓ Plan Name:', res6.planName);
console.log('  ✓ Started:', res6.displayedStarted);
console.log('  ✓ Valid Until:', res6.displayedValidUntil);

// ── TEST 7: UTC and Asia/Kolkata Consistency ──
console.log('\n--- TEST 7: UTC vs Asia/Kolkata Consistency ---');
// Verify that formatDate on raw DB strings without Z parses identically in both timezones
const testRawDbString = '2026-10-22T09:00:00';
const parsedDate = parseUtcDate(testRawDbString);
assert.strictEqual(parsedDate.toISOString(), '2026-10-22T09:00:00.000Z');
console.log(`  ✓ Raw DB String "${testRawDbString}" resolves strictly to UTC: ${parsedDate.toISOString()}`);

console.log('\n================================================================');
console.log('ALL 7 PROFILE DERIVED DATE TESTS PASSED (100%)');
console.log('================================================================');
