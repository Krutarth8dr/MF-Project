import { supabase } from './supabase';

const CACHE_KEY = 'wn_sub_status';

export function getCachedSubscription(userId) {
  if (typeof window === 'undefined' || !userId) return false;
  try {
    const raw = sessionStorage.getItem(`${CACHE_KEY}_${userId}`) || localStorage.getItem(`${CACHE_KEY}_${userId}`);
    if (!raw) return false;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed.active !== 'boolean') return false;
    // Check if end_date has expired
    if (parsed.endDate && new Date(parsed.endDate) <= new Date()) {
      return false;
    }
    return parsed.active;
  } catch {
    return false;
  }
}

export function setCachedSubscription(userId, active, endDate = null) {
  if (typeof window === 'undefined' || !userId) return;
  try {
    const data = JSON.stringify({
      active: !!active,
      endDate: endDate || null,
      cachedAt: Date.now(),
    });
    sessionStorage.setItem(`${CACHE_KEY}_${userId}`, data);
    localStorage.setItem(`${CACHE_KEY}_${userId}`, data);
  } catch {}
}

export function clearSubscriptionCache() {
  if (typeof window === 'undefined') return;
  try {
    Object.keys(sessionStorage).forEach((k) => {
      if (k.startsWith(CACHE_KEY)) sessionStorage.removeItem(k);
    });
    Object.keys(localStorage).forEach((k) => {
      if (k.startsWith(CACHE_KEY)) localStorage.removeItem(k);
    });
  } catch {}
}

let inFlightPromise = null;

/**
 * Deduplicated check for subscription status with Supabase.
 * Returns true/false and automatically caches the result.
 */
export async function checkUserSubscription(userId) {
  if (!userId) return false;

  // Deduplicate simultaneous in-flight requests for the same session
  if (inFlightPromise) {
    return inFlightPromise;
  }

  inFlightPromise = (async () => {
    try {
      const { data: subData, error } = await supabase
        .from('subscriptions')
        .select('payment_status, subscription_end_date')
        .eq('user_id', userId)
        .eq('payment_status', 'completed')
        .order('subscription_end_date', { ascending: false })
        .limit(1)
        .maybeSingle();

      if (error) {
        console.warn('Subscription fetch error:', error);
        return getCachedSubscription(userId);
      }

      const active =
        subData &&
        (subData.subscription_end_date === null ||
          new Date(subData.subscription_end_date) > new Date());

      setCachedSubscription(userId, !!active, subData?.subscription_end_date);
      return !!active;
    } catch (err) {
      console.warn('Error verifying subscription:', err);
      return getCachedSubscription(userId);
    } finally {
      inFlightPromise = null;
    }
  })();

  return inFlightPromise;
}
