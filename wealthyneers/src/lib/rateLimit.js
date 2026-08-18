import { NextResponse } from 'next/server.js';

/**
 * In-Memory Sliding Window Rate Limiter for Next.js API Routes (Best-Effort Defense-in-Depth).
 *
 * NOTE ON SERVERLESS EXECUTION:
 * In-memory stores are instance-local. In a multi-instance serverless deployment (such as Vercel),
 * state is maintained within each active execution container. This provides effective throttling against
 * rapid repeated requests and script loops hitting the same container, but does not guarantee a globally
 * synchronized cluster-wide limit. A globally distributed state store (e.g., Upstash Redis) can be added
 * as a future infrastructure enhancement if cluster-wide strict quotas become necessary.
 */

// Memory store for tracking request timestamps: Map<string, number[]>
const requestStore = new Map();

// Periodic cleanup of expired timestamps to prevent memory growth
const CLEANUP_INTERVAL_MS = 10 * 60 * 1000; // 10 minutes
let lastCleanup = Date.now();

function cleanupExpiredEntries() {
  const now = Date.now();
  if (now - lastCleanup < CLEANUP_INTERVAL_MS) return;
  lastCleanup = now;

  for (const [key, timestamps] of requestStore.entries()) {
    const activeTimestamps = timestamps.filter((t) => now - t < 3600 * 1000); // 1 hour max window
    if (activeTimestamps.length === 0) {
      requestStore.delete(key);
    } else {
      requestStore.set(key, activeTimestamps);
    }
  }
}

/**
 * Extracts client IP address safely from standard Next.js request headers.
 */
export function getClientIp(request) {
  const forwarded = request.headers.get('x-forwarded-for');
  if (forwarded) {
    return forwarded.split(',')[0].trim();
  }
  return request.headers.get('x-real-ip') || '127.0.0.1';
}

/**
 * Checks whether a given key exceeds the maximum allowed requests within a sliding time window.
 *
 * @param {string} key - Unique rate limit identifier (e.g. `order:user:<id>` or `order:ip:<ip>`)
 * @param {number} limit - Maximum number of allowed requests within window
 * @param {number} windowMs - Window duration in milliseconds
 * @returns {{ allowed: boolean, limit: number, remaining: number, resetInMs: number }}
 */
export function checkRateLimit(key, limit, windowMs) {
  cleanupExpiredEntries();

  const now = Date.now();
  const timestamps = requestStore.get(key) || [];

  // Filter out timestamps outside the active window
  const activeTimestamps = timestamps.filter((t) => now - t < windowMs);

  if (activeTimestamps.length >= limit) {
    const oldestTimestamp = activeTimestamps[0];
    const resetInMs = Math.max(0, windowMs - (now - oldestTimestamp));

    return {
      allowed: false,
      limit,
      remaining: 0,
      resetInMs,
    };
  }

  // Record current request timestamp
  activeTimestamps.push(now);
  requestStore.set(key, activeTimestamps);

  return {
    allowed: true,
    limit,
    remaining: limit - activeTimestamps.length,
    resetInMs: windowMs,
  };
}

/**
 * Returns a standardized HTTP 429 Too Many Requests response with RFC-compliant headers.
 */
export function rateLimitExceededResponse(resetInMs, customMessage = null) {
  const retryAfterSeconds = Math.max(1, Math.ceil(resetInMs / 1000));
  const message =
    customMessage ||
    `Too many requests. Please wait ${retryAfterSeconds} second${retryAfterSeconds === 1 ? '' : 's'} before trying again.`;

  return NextResponse.json(
    { error: message },
    {
      status: 429,
      headers: {
        'Retry-After': String(retryAfterSeconds),
        'X-RateLimit-Reset': String(Math.ceil((Date.now() + resetInMs) / 1000)),
      },
    }
  );
}
