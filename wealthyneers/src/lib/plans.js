/**
 * Wealthyneers Subscription Plans Configuration
 * Central server-authoritative source of truth for all subscription plans,
 * pricing, durations, and calendar-year arithmetic.
 */

export const PLANS = {
  monthly_30: {
    id: 'monthly_30',
    name: '30-Day Institutional Access',
    shortName: '30-Day Access',
    price: 30,
    amountPaise: 3000, // ₹30.00 = 3000 paise
    currency: 'INR',
    durationDays: 30,
    autoRenew: false,
    periodLabel: 'for 30 days',
    buttonText: 'Get Access Now — ₹30 for 30 days',
    description: 'One simple one-time payment. Complete access to all six institutional research reports for 30 days.',
  },
  yearly_250: {
    id: 'yearly_250',
    name: 'Yearly Institutional Access',
    shortName: 'Yearly Access',
    price: 250,
    amountPaise: 25000, // ₹250.00 = 25000 paise
    currency: 'INR',
    durationDays: 365,
    autoRenew: false,
    periodLabel: 'for 1 full year',
    buttonText: 'Get Yearly Access — ₹250',
    description: 'One simple one-time payment. Complete access to all six institutional research reports for 1 full year.',
    badge: 'Best Value',
    savingsLabel: 'Save approximately 31% compared with 12 separate 30-day passes',
  },
};

export const DEFAULT_PLAN_ID = 'monthly_30';

/**
 * Validates whether a plan identifier is valid and supported.
 * @param {string} planId
 * @returns {object|null} The plan object or null if invalid
 */
export function getPlan(planId) {
  if (!planId || typeof planId !== 'string') return null;
  const normalized = planId.trim().toLowerCase();
  return PLANS[normalized] || null;
}

/**
 * Safely parses any date representation (ISO string, PostgreSQL timestamp without time zone,
 * Date object, or numeric epoch timestamp) as a UTC Date.
 *
 * Crucial for PostgreSQL `timestamp without time zone` columns returned by Supabase PostgREST
 * (e.g. "2026-11-09T12:00:00" without trailing 'Z'). In ECMAScript, ISO date-time strings without
 * a timezone offset are parsed as local time by default, causing timezone shifts (e.g. -5.5 hours in IST).
 * Appending 'Z' guarantees consistent, exact UTC interpretation across all client and server runtimes.
 *
 * @param {Date|string|number|null|undefined} value
 * @returns {Date|null} Valid Date object interpreted strictly in UTC, or null if invalid
 */
export function parseUtcDate(value) {
  if (!value) return null;
  if (value instanceof Date) {
    return isNaN(value.getTime()) ? null : value;
  }
  if (typeof value === 'number') {
    const d = new Date(value);
    return isNaN(d.getTime()) ? null : d;
  }
  if (typeof value === 'string') {
    let clean = value.trim();
    if (!clean) return null;

    // Convert SQL timestamp space delimiter to ISO standard 'T'
    if (clean.includes(' ') && !clean.includes('T')) {
      clean = clean.replace(' ', 'T');
    }

    if (clean.includes('T')) {
      const timePart = clean.substring(clean.indexOf('T') + 1);
      // If no timezone indicator (Z or +/-HH:MM or +/-HHMM or +/-HH) is present, append 'Z'
      if (!/(Z|[+-]\d{2}(:?\d{2})?)$/i.test(timePart)) {
        clean += 'Z';
      }
    } else if (/^\d{4}-\d{2}-\d{2}$/.test(clean)) {
      // Date-only string (YYYY-MM-DD): append T00:00:00Z for explicit UTC
      clean += 'T00:00:00Z';
    }

    const d = new Date(clean);
    return isNaN(d.getTime()) ? null : d;
  }
  return null;
}

/**
 * Adds exactly 1 calendar year to a UTC Date safely, accounting for leap year boundaries (Feb 29).
 * If the start date is Feb 29 and the following year is not a leap year, it clamps safely to Feb 28.
 *
 * @param {Date|string|number} startDate
 * @returns {Date} Target date exactly 1 calendar year later in UTC
 */
export function addOneCalendarYear(startDate) {
  const d = parseUtcDate(startDate);
  if (!d) return null;
  const year = d.getUTCFullYear();
  const month = d.getUTCMonth();
  const date = d.getUTCDate();
  const hours = d.getUTCHours();
  const minutes = d.getUTCMinutes();
  const seconds = d.getUTCSeconds();
  const ms = d.getUTCMilliseconds();

  const targetYear = year + 1;
  let targetDate = date;

  // Leap-year boundary check: February 29
  if (month === 1 && date === 29) {
    const isTargetLeap =
      (targetYear % 4 === 0 && targetYear % 100 !== 0) || targetYear % 400 === 0;
    if (!isTargetLeap) {
      targetDate = 28;
    }
  }

  return new Date(Date.UTC(targetYear, month, targetDate, hours, minutes, seconds, ms));
}

/**
 * Calculates the exact subscription end date for a given plan and start date.
 * Uses UTC arithmetic throughout to prevent timezone drift.
 *
 * @param {string} planId - 'monthly_30' | 'yearly_250'
 * @param {Date|string|number} startDate
 * @returns {Date}
 */
export function calculateSubscriptionEndDate(planId, startDate) {
  const start = parseUtcDate(startDate) || new Date();
  if (planId === 'yearly_250') {
    return addOneCalendarYear(start);
  }
  // Default to 30 days (30 * 24 * 60 * 60 * 1000 ms)
  return new Date(start.getTime() + 30 * 24 * 60 * 60 * 1000);
}

/**
 * Helper to format plan display labels cleanly in user profiles and emails.
 * @param {string} planType
 * @returns {string}
 */
export function formatPlanName(planType) {
  if (planType === 'yearly_250') return PLANS.yearly_250.name;
  if (planType === 'monthly_30') return PLANS.monthly_30.name;
  return 'Institutional Access';
}
