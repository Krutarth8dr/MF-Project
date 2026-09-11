import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || '';
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '';

// Deduplicated refresh promise to avoid race conditions when multiple requests fail concurrently
let refreshPromise = null;

/**
 * Safely refreshes the active session with deduplication.
 */
export async function refreshSessionSafely() {
  if (typeof window === 'undefined') return null;

  if (refreshPromise) {
    return refreshPromise;
  }

  refreshPromise = (async () => {
    try {
      const { data, error } = await supabase.auth.refreshSession();
      if (error || !data?.session) {
        console.warn('[Supabase Auth] Session refresh failed:', error?.message);
        return null;
      }
      return data.session;
    } catch (err) {
      console.warn('[Supabase Auth] Session refresh exception:', err);
      return null;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

/**
 * Returns a guaranteed valid session, refreshing if the access token has expired
 * or is within 2 minutes of expiration.
 */
export async function getValidSession() {
  if (typeof window === 'undefined') return null;

  try {
    const { data: { session }, error } = await supabase.auth.getSession();
    if (error || !session) return null;

    const now = Math.floor(Date.now() / 1000);
    // If expired or expiring in under 120 seconds, proactively refresh
    if (session.expires_at && session.expires_at - now < 120) {
      const refreshed = await refreshSessionSafely();
      return refreshed;
    }

    return session;
  } catch (err) {
    console.warn('[Supabase Auth] Error in getValidSession:', err);
    return null;
  }
}

/**
 * Helper to check whether an error is a JWT / Session expiration error.
 */
export function isJwtExpiredError(err) {
  if (!err) return false;
  const msg = typeof err === 'string' ? err : err.message || '';
  const code = err?.code || '';
  const str = (msg + ' ' + code).toLowerCase();
  return (
    str.includes('jwt expired') ||
    str.includes('token has expired') ||
    str.includes('invalid jwt') ||
    str.includes('pgrst301') ||
    str.includes('pgrst302')
  );
}

/**
 * Formats user-facing error messages, converting cryptic JWT/timeout errors into helpful guidance.
 */
export function formatFriendlyErrorMessage(err, fallback = 'Failed to load data.') {
  if (!err) return fallback;
  const msg = typeof err === 'string' ? err : err.message || '';
  if (isJwtExpiredError(err)) {
    return 'Your session has expired. Please refresh the page or log in again.';
  }
  if (msg.toLowerCase().includes('canceling statement due to statement timeout')) {
    return 'The request took longer than expected to complete. Please try narrowing your filters or try again in a moment.';
  }
  return msg || fallback;
}

/**
 * Global fetch wrapper with automatic 401 JWT-expired interception and replay.
 */
const customFetch = async (url, options = {}) => {
  let response = await fetch(url, options);

  // If unauthorized / token expired, attempt transparent refresh and replay
  if (response.status === 401 && typeof window !== 'undefined') {
    try {
      const clone = response.clone();
      const bodyText = await clone.text();

      if (
        bodyText.toLowerCase().includes('jwt expired') ||
        bodyText.toLowerCase().includes('token has expired') ||
        bodyText.includes('PGRST301')
      ) {
        // Prevent infinite loops if retry also returns 401
        const isRetry = options?.headers && (
          (options.headers instanceof Headers && options.headers.get('X-Auth-Retry')) ||
          options.headers['X-Auth-Retry']
        );

        if (!isRetry) {
          console.info('[Supabase Client] JWT expired detected. Refreshing session...');
          const newSession = await refreshSessionSafely();

          if (newSession?.access_token) {
            // Build updated headers
            const newHeaders = new Headers(options.headers || {});
            newHeaders.set('Authorization', `Bearer ${newSession.access_token}`);
            newHeaders.set('apikey', supabaseAnonKey);
            newHeaders.set('X-Auth-Retry', '1');

            // Replay the request with the fresh token
            const retriedResponse = await fetch(url, {
              ...options,
              headers: newHeaders,
            });

            return retriedResponse;
          } else {
            console.warn('[Supabase Client] Refresh token expired/revoked. User session has ended.');
          }
        }
      }
    } catch (e) {
      console.warn('[Supabase Client] Interceptor error:', e);
    }
  }

  return response;
};

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
  },
  global: {
    fetch: customFetch,
  },
});
