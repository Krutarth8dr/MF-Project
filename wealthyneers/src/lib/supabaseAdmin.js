import { createClient } from '@supabase/supabase-js';

/**
 * Server-only Supabase Service-Role Admin Client.
 * 
 * IMPORTANT:
 * - This client bypasses Row Level Security (RLS) using the Service Role Secret.
 * - It must NEVER be imported or used in client-side code.
 * - Used strictly in server-side API routes and background cron jobs for administrative tasks
 *   (e.g., verifying user email confirmation status in auth.users, writing to public.email_logs).
 */

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

if (!supabaseUrl) {
  console.warn('[supabaseAdmin] Warning: NEXT_PUBLIC_SUPABASE_URL is not defined.');
}

export const supabaseAdmin = createClient(
  supabaseUrl || '',
  serviceRoleKey || '',
  {
    auth: {
      persistSession: false,
      autoRefreshToken: false,
    },
  }
);
