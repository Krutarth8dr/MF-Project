import fs from 'fs';
import path from 'path';

/**
 * Returns Razorpay credentials. In local development, dynamically hot-reads from .env.local
 * to prevent stale process.env memory caches when keys are updated.
 */
export function getRazorpayCredentials() {
  let keyId = process.env.RAZORPAY_KEY_ID;
  let keySecret = process.env.RAZORPAY_KEY_SECRET;

  if (process.env.NODE_ENV !== 'production') {
    try {
      const envPath = path.join(process.cwd(), '.env.local');
      if (fs.existsSync(envPath)) {
        const content = fs.readFileSync(envPath, 'utf8');
        const keyMatch = content.match(/^RAZORPAY_KEY_ID\s*=\s*([^\r\n]+)/m);
        const secretMatch = content.match(/^RAZORPAY_KEY_SECRET\s*=\s*([^\r\n]+)/m);
        if (keyMatch) keyId = keyMatch[1].trim().replace(/['"]/g, '');
        if (secretMatch) keySecret = secretMatch[1].trim().replace(/['"]/g, '');
      }
    } catch (_) {}
  }

  return { keyId, keySecret };
}
