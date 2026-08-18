import fs from 'fs';
import path from 'path';

/**
 * Returns Razorpay credentials and configuration. In local development, dynamically hot-reads from .env.local
 * to prevent stale process.env memory caches when keys or plan IDs are updated.
 */
export function getRazorpayCredentials() {
  let keyId = (process.env.RAZORPAY_KEY_ID || process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID || '').trim().replace(/['"]/g, '');
  let keySecret = (process.env.RAZORPAY_KEY_SECRET || '').trim().replace(/['"]/g, '');
  let planId = (process.env.RAZORPAY_PLAN_ID || '').trim().replace(/['"]/g, '');
  let webhookSecret = (process.env.RAZORPAY_WEBHOOK_SECRET || '').trim().replace(/['"]/g, '');

  if (process.env.NODE_ENV !== 'production') {
    try {
      const envPath = path.join(process.cwd(), '.env.local');
      if (fs.existsSync(envPath)) {
        const content = fs.readFileSync(envPath, 'utf8');
        const keyMatch = content.match(/^RAZORPAY_KEY_ID\s*=\s*([^\r\n]+)/m);
        const secretMatch = content.match(/^RAZORPAY_KEY_SECRET\s*=\s*([^\r\n]+)/m);
        const planMatch = content.match(/^RAZORPAY_PLAN_ID\s*=\s*([^\r\n]+)/m);
        const webhookMatch = content.match(/^RAZORPAY_WEBHOOK_SECRET\s*=\s*([^\r\n]+)/m);

        if (keyMatch) keyId = keyMatch[1].trim().replace(/['"]/g, '');
        if (secretMatch) keySecret = secretMatch[1].trim().replace(/['"]/g, '');
        if (planMatch) planId = planMatch[1].trim().replace(/['"]/g, '');
        if (webhookMatch) webhookSecret = webhookMatch[1].trim().replace(/['"]/g, '');
      }
    } catch (_) {}
  }

  return { keyId, keySecret, planId, webhookSecret };
}
