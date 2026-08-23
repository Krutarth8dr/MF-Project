-- ============================================================
-- HARDEN PUBLIC.INVESTOR_PROFILE_GOOGLE_SYNC SECURITY
-- ============================================================
-- Enforces Zero-Trust access model:
--   anon          -> NO ACCESS
--   authenticated -> NO ACCESS
--   public        -> NO ACCESS
--   service_role  -> FULL SERVER-SIDE ACCESS
-- ============================================================

-- 1. Ensure Row Level Security (RLS) is ENABLED
ALTER TABLE public.investor_profile_google_sync ENABLE ROW LEVEL SECURITY;

-- 2. Drop existing client-facing policies
DROP POLICY IF EXISTS "Users can view own google sync" ON public.investor_profile_google_sync;
DROP POLICY IF EXISTS "Users can insert own google sync" ON public.investor_profile_google_sync;
DROP POLICY IF EXISTS "Users can update own google sync" ON public.investor_profile_google_sync;
DROP POLICY IF EXISTS "Enable read access for own records" ON public.investor_profile_google_sync;
DROP POLICY IF EXISTS "Enable insert for own records" ON public.investor_profile_google_sync;
DROP POLICY IF EXISTS "Enable update for own records" ON public.investor_profile_google_sync;
DROP POLICY IF EXISTS "Users can view own sync records" ON public.investor_profile_google_sync;
DROP POLICY IF EXISTS "Users can insert own sync records" ON public.investor_profile_google_sync;
DROP POLICY IF EXISTS "Users can update own sync records" ON public.investor_profile_google_sync;

-- 3. Revoke all table privileges from anon, authenticated, and public roles
REVOKE ALL ON public.investor_profile_google_sync FROM anon, authenticated, public;

-- 4. Grant full administrative privileges strictly to service_role
GRANT ALL ON public.investor_profile_google_sync TO service_role;
