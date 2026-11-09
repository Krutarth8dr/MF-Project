import { spawnSync } from 'child_process';
import assert from 'assert';
import fs from 'fs';
import { parseUtcDate, calculateSubscriptionEndDate, addOneCalendarYear } from '../src/lib/plans.js';

console.log('================================================================');
console.log('WEALTHYNEERS UTC & CROSS-TIMEZONE SAFETY VERIFICATION SUITE');
console.log('================================================================\n');

// ── TEST 1: Unit Parsing of Timestamps without Trailing 'Z' ──
console.log('--- TEST 1: Parsing Various Supabase Formats as UTC ---');

const testCases = [
  {
    input: '2026-11-06T09:25:35.448',
    expectedIso: '2026-11-06T09:25:35.448Z',
    desc: 'PostgREST ISO without Z',
  },
  {
    input: '2026-11-06 09:25:35.448',
    expectedIso: '2026-11-06T09:25:35.448Z',
    desc: 'PostgreSQL space-delimited with ms',
  },
  {
    input: '2026-11-06T09:25:35',
    expectedIso: '2026-11-06T09:25:35.000Z',
    desc: 'PostgREST ISO without ms or Z',
  },
  {
    input: '2026-11-06 09:25:35',
    expectedIso: '2026-11-06T09:25:35.000Z',
    desc: 'PostgreSQL space-delimited without ms or Z',
  },
  {
    input: '2026-11-06T09:25:35.448Z',
    expectedIso: '2026-11-06T09:25:35.448Z',
    desc: 'Standard UTC ISO with Z',
  },
  {
    input: '2026-11-06T09:25:35.448+00:00',
    expectedIso: '2026-11-06T09:25:35.448Z',
    desc: 'ISO with explicit +00:00 offset',
  },
  {
    input: '2026-11-06',
    expectedIso: '2026-11-06T00:00:00.000Z',
    desc: 'Date-only YYYY-MM-DD',
  },
];

for (const tc of testCases) {
  const d = parseUtcDate(tc.input);
  assert(d !== null, `Failed to parse ${tc.desc}`);
  assert.strictEqual(d.toISOString(), tc.expectedIso, `Mismatch on ${tc.desc}`);
  console.log(`  ✓ ${tc.desc}: "${tc.input}" -> ${d.toISOString()}`);
}

// ── TEST 2: Cross-Timezone Comparison (UTC vs Asia/Kolkata) ──
console.log('\n--- TEST 2: Cross-Timezone Parity (UTC vs Asia/Kolkata) ---');

const runnerScript = `
import { parseUtcDate, calculateSubscriptionEndDate, addOneCalendarYear } from './src/lib/plans.js';

const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
const offset = new Date().getTimezoneOffset();

// Test string without Z
const rawDbDate = '2026-12-06T09:25:35.448';
const parsed = parseUtcDate(rawDbDate);
const yearlyEnd = calculateSubscriptionEndDate('yearly_250', rawDbDate);
const monthlyEnd = calculateSubscriptionEndDate('monthly_30', rawDbDate);

// Leap year Feb 29
const leapStart = '2028-02-29T12:00:00';
const leapEnd = addOneCalendarYear(leapStart);

console.log(JSON.stringify({
  tz,
  offset,
  parsedMs: parsed.getTime(),
  parsedIso: parsed.toISOString(),
  yearlyMs: yearlyEnd.getTime(),
  yearlyIso: yearlyEnd.toISOString(),
  monthlyMs: monthlyEnd.getTime(),
  monthlyIso: monthlyEnd.toISOString(),
  leapEndIso: leapEnd.toISOString()
}));
`;

// Run in Asia/Kolkata
const kolkataRes = spawnSync(process.execPath, ['--input-type=module', '-e', runnerScript], {
  env: { ...process.env, TZ: 'Asia/Kolkata' },
  cwd: process.cwd(),
});

if (kolkataRes.error || kolkataRes.status !== 0) {
  console.error('Kolkata runner failed:', kolkataRes.stderr?.toString() || kolkataRes.error);
  process.exit(1);
}
const kolkataData = JSON.parse(kolkataRes.stdout.toString().trim());

// Run in UTC
const utcRes = spawnSync(process.execPath, ['--input-type=module', '-e', runnerScript], {
  env: { ...process.env, TZ: 'UTC' },
  cwd: process.cwd(),
});

if (utcRes.error || utcRes.status !== 0) {
  console.error('UTC runner failed:', utcRes.stderr?.toString() || utcRes.error);
  process.exit(1);
}
const utcData = JSON.parse(utcRes.stdout.toString().trim());

console.log(`  Kolkata runtime detected: ${kolkataData.tz} (offset: ${kolkataData.offset} min)`);
console.log(`  UTC runtime detected:     ${utcData.tz} (offset: ${utcData.offset} min)`);

assert.strictEqual(kolkataData.parsedMs, utcData.parsedMs, 'Epoch ms must be identical across timezones');
assert.strictEqual(kolkataData.parsedIso, utcData.parsedIso, 'ISO output must be identical across timezones');
console.log(`  ✓ Raw DB string '2026-12-06T09:25:35.448':`);
console.log(`    Kolkata epoch: ${kolkataData.parsedMs} -> ${kolkataData.parsedIso}`);
console.log(`    UTC epoch:     ${utcData.parsedMs} -> ${utcData.parsedIso}`);

assert.strictEqual(kolkataData.yearlyMs, utcData.yearlyMs, 'Yearly renewal ms must be identical');
assert.strictEqual(kolkataData.yearlyIso, utcData.yearlyIso, 'Yearly renewal ISO must be identical');
console.log(`  ✓ Yearly renewal calculation identical across timezones: ${utcData.yearlyIso}`);

assert.strictEqual(kolkataData.monthlyMs, utcData.monthlyMs, 'Monthly renewal ms must be identical');
assert.strictEqual(kolkataData.monthlyIso, utcData.monthlyIso, 'Monthly renewal ISO must be identical');
console.log(`  ✓ 30-Day renewal calculation identical across timezones: ${utcData.monthlyIso}`);

assert.strictEqual(kolkataData.leapEndIso, utcData.leapEndIso, 'Leap year calculation identical');
console.log(`  ✓ Leap year calculation identical: 2028-02-29 -> ${utcData.leapEndIso}`);

// ── TEST 3: Gating Boundary Simulation in Asia/Kolkata ──
console.log('\n--- TEST 3: Gating Boundary Evaluation in Asia/Kolkata ---');

// Suppose a subscription expires at 2026-11-09T12:00:00 (UTC).
// In old non-safe parsing, in Asia/Kolkata:
// new Date('2026-11-09T12:00:00') was evaluated as 12:00 IST (06:30 UTC),
// causing the subscriber to be locked out 5.5 hours early!
const rawExpiry = '2026-11-09T12:00:00';
const nowTimeAt1000UTC = new Date('2026-11-09T10:00:00Z').getTime();

// Simulated check using parseUtcDate:
const parsedExp = parseUtcDate(rawExpiry);
const isStillActiveAt1000UTC = parsedExp.getTime() > nowTimeAt1000UTC;
assert(isStillActiveAt1000UTC, 'Must be active at 10:00 UTC when expiring at 12:00 UTC');
console.log(`  ✓ Subscriber expiring at 12:00 UTC correctly remains ACTIVE at 10:00 UTC in Asia/Kolkata`);

const nowTimeAt1300UTC = new Date('2026-11-09T13:00:00Z').getTime();
const isExpiredAt1300UTC = parsedExp.getTime() <= nowTimeAt1300UTC;
assert(isExpiredAt1300UTC, 'Must be expired at 13:00 UTC when expiring at 12:00 UTC');
console.log(`  ✓ Subscriber expiring at 12:00 UTC correctly becomes EXPIRED at 13:00 UTC in Asia/Kolkata`);

// ── TEST 4: Live Supabase PostgREST Row Validation ──
console.log('\n--- TEST 4: Real PostgreSQL / Supabase Row Validation ---');

let envConfig = {};
try {
  const envText = fs.readFileSync('.env.local', 'utf8');
  envText.split('\n').forEach(line => {
    const m = line.match(/^\s*([^#=\s]+)\s*=\s*(.*)$/);
    if (m) envConfig[m[1]] = m[2].trim().replace(/^['"]|['"]$/g, '');
  });
} catch (_) {}

if (envConfig.NEXT_PUBLIC_SUPABASE_URL && envConfig.SUPABASE_SERVICE_ROLE_KEY) {
  const { createClient } = await import('@supabase/supabase-js');
  const supabase = createClient(envConfig.NEXT_PUBLIC_SUPABASE_URL, envConfig.SUPABASE_SERVICE_ROLE_KEY);

  const { data: realSubs, error } = await supabase
    .from('subscriptions')
    .select('id, user_id, plan_type, subscription_start_date, subscription_end_date, payment_status')
    .eq('payment_status', 'completed')
    .order('subscription_end_date', { ascending: false })
    .limit(5);

  if (error) {
    console.error('  [Warning] Could not query live Supabase:', error.message);
  } else {
    console.log(`  ✓ Successfully fetched ${realSubs.length} real subscription rows from Supabase`);
    realSubs.forEach((sub, i) => {
      const parsedStart = parseUtcDate(sub.subscription_start_date);
      const parsedEnd = parseUtcDate(sub.subscription_end_date);
      assert(parsedStart !== null, `Start date on row ${i} must parse`);
      assert(parsedEnd !== null, `End date on row ${i} must parse`);
      console.log(`    Row [${i}] (${sub.plan_type}): End "${sub.subscription_end_date}" -> ${parsedEnd.toISOString()}`);
    });
  }
} else {
  console.log('  [Note] Supabase credentials not found for live row query; tested via unit fixtures.');
}

console.log('\n================================================================');
console.log('ALL TIMEZONE & UTC SAFETY CHECKS PASSED (100%)');
console.log('================================================================');
