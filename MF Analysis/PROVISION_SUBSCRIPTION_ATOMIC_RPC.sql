-- ====================================================================
-- MIGRATION: HARDENED ATOMIC SUBSCRIPTION PROVISIONING & CONCURRENCY
-- Target: Supabase Postgres Database (public schema)
-- Project: Wealthyneers (https://wealthyneers.com)
-- Version: 3.0 (UTC-Safe & Live Schema Compatible)
-- Date: 2026-11-09
-- ====================================================================

-- 1. Ensure database-level unique constraint on subscriptions.razorpay_payment_id
-- (Safe check: avoids errors if constraint or index already exists)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint 
    WHERE conname = 'subscriptions_razorpay_payment_id_key'
  ) THEN
    IF NOT EXISTS (
      SELECT 1 FROM pg_indexes 
      WHERE tablename = 'subscriptions' 
        AND indexname = 'subscriptions_razorpay_payment_id_key'
    ) THEN
      ALTER TABLE public.subscriptions 
      ADD CONSTRAINT subscriptions_razorpay_payment_id_key UNIQUE (razorpay_payment_id);
    END IF;
  END IF;
END $$;

-- 2. Create the hardened atomic provisioning function
-- Fixed execution environment:
--   - SECURITY DEFINER (elevated rights for service_role)
--   - search_path = public, pg_temp (prevents search path injection)
--   - TimeZone = 'UTC' (ensures all calendar & interval arithmetic is strictly UTC)
CREATE OR REPLACE FUNCTION public.provision_subscription_access(
  p_user_id UUID,
  p_full_name TEXT,
  p_plan_type TEXT,
  p_amount_paid NUMERIC,
  p_currency TEXT,
  p_razorpay_payment_id TEXT,
  p_razorpay_order_id TEXT
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
SET TimeZone = 'UTC'
AS $$
DECLARE
  v_now TIMESTAMPTZ := clock_timestamp();
  v_latest_end TIMESTAMPTZ;
  v_start_date TIMESTAMPTZ;
  v_end_date TIMESTAMPTZ;
  v_sub_id UUID;
  v_existing_id UUID;
  v_existing_user_id UUID;
  v_existing_status TEXT;
  v_user_exists BOOLEAN;
  v_clean_currency TEXT;
  v_clean_plan TEXT;
BEGIN
  -- A. Validate non-null mandatory identifiers
  IF p_user_id IS NULL THEN
    RETURN jsonb_build_object(
      'success', false,
      'code', 'INVALID_PARAMETERS',
      'error', 'p_user_id is mandatory and cannot be null.'
    );
  END IF;

  IF p_razorpay_payment_id IS NULL OR TRIM(p_razorpay_payment_id) = '' THEN
    RETURN jsonb_build_object(
      'success', false,
      'code', 'INVALID_PARAMETERS',
      'error', 'p_razorpay_payment_id is mandatory and cannot be empty.'
    );
  END IF;

  IF p_razorpay_order_id IS NULL OR TRIM(p_razorpay_order_id) = '' THEN
    RETURN jsonb_build_object(
      'success', false,
      'code', 'INVALID_PARAMETERS',
      'error', 'p_razorpay_order_id is mandatory and cannot be empty.'
    );
  END IF;

  -- B. Validate plan allowlist (rejects null, empty, or unsupported plans)
  v_clean_plan := TRIM(COALESCE(p_plan_type, ''));
  IF v_clean_plan NOT IN ('monthly_30', 'yearly_250') THEN
    RETURN jsonb_build_object(
      'success', false,
      'code', 'INVALID_PLAN_TYPE',
      'error', 'Unsupported or null plan type: ' || COALESCE(p_plan_type, 'NULL') || '. Allowed plans: monthly_30, yearly_250.'
    );
  END IF;

  -- C. Validate currency (strictly INR)
  v_clean_currency := UPPER(TRIM(COALESCE(p_currency, '')));
  IF v_clean_currency <> 'INR' THEN
    RETURN jsonb_build_object(
      'success', false,
      'code', 'CURRENCY_MISMATCH',
      'error', 'Invalid currency: ' || COALESCE(p_currency, 'NULL') || '. Only INR is supported.'
    );
  END IF;

  -- D. Enforce exact plan-to-amount mapping
  -- monthly_30 -> 30.00 INR
  -- yearly_250 -> 250.00 INR
  IF v_clean_plan = 'monthly_30' AND (p_amount_paid IS NULL OR p_amount_paid <> 30.00) THEN
    RETURN jsonb_build_object(
      'success', false,
      'code', 'AMOUNT_MISMATCH',
      'error', 'Amount mismatch: plan monthly_30 requires exactly 30.00 INR (got ' || COALESCE(p_amount_paid::text, 'NULL') || ').'
    );
  ELSIF v_clean_plan = 'yearly_250' AND (p_amount_paid IS NULL OR p_amount_paid <> 250.00) THEN
    RETURN jsonb_build_object(
      'success', false,
      'code', 'AMOUNT_MISMATCH',
      'error', 'Amount mismatch: plan yearly_250 requires exactly 250.00 INR (got ' || COALESCE(p_amount_paid::text, 'NULL') || ').'
    );
  END IF;

  -- E. Verify user exists in public.users
  SELECT EXISTS(SELECT 1 FROM public.users WHERE id = p_user_id) INTO v_user_exists;
  IF NOT v_user_exists THEN
    RETURN jsonb_build_object(
      'success', false,
      'code', 'USER_NOT_FOUND',
      'error', 'User record not found in public.users.'
    );
  END IF;

  -- F. Pre-lock fast idempotency check
  SELECT id, user_id, payment_status
  INTO v_existing_id, v_existing_user_id, v_existing_status
  FROM public.subscriptions
  WHERE razorpay_payment_id = TRIM(p_razorpay_payment_id);

  IF v_existing_id IS NOT NULL THEN
    IF v_existing_user_id = p_user_id AND v_existing_status = 'completed' THEN
      RETURN jsonb_build_object(
        'success', true,
        'idempotent_replay', true,
        'subscription', (
          SELECT jsonb_build_object(
            'id', s.id,
            'plan_type', s.plan_type,
            'subscription_start_date', s.subscription_start_date,
            'subscription_end_date', s.subscription_end_date
          )
          FROM public.subscriptions s
          WHERE s.id = v_existing_id
        )
      );
    ELSE
      RETURN jsonb_build_object(
        'success', false,
        'code', 'PAYMENT_ALREADY_PROCESSED',
        'error', 'This payment has already been credited to another account.'
      );
    END IF;
  END IF;

  -- G. Transaction-level Advisory Lock per user
  -- Serializes concurrent verifications for this exact user.
  -- Automatically released upon transaction commit or rollback.
  PERFORM pg_advisory_xact_lock(hashtext('sub_provision_' || p_user_id::text));

  -- H. Post-lock idempotency check (catches parallel executions that committed while waiting)
  SELECT id, user_id, payment_status
  INTO v_existing_id, v_existing_user_id, v_existing_status
  FROM public.subscriptions
  WHERE razorpay_payment_id = TRIM(p_razorpay_payment_id);

  IF v_existing_id IS NOT NULL THEN
    IF v_existing_user_id = p_user_id AND v_existing_status = 'completed' THEN
      RETURN jsonb_build_object(
        'success', true,
        'idempotent_replay', true,
        'subscription', (
          SELECT jsonb_build_object(
            'id', s.id,
            'plan_type', s.plan_type,
            'subscription_start_date', s.subscription_start_date,
            'subscription_end_date', s.subscription_end_date
          )
          FROM public.subscriptions s
          WHERE s.id = v_existing_id
        )
      );
    ELSE
      RETURN jsonb_build_object(
        'success', false,
        'code', 'PAYMENT_ALREADY_PROCESSED',
        'error', 'This payment has already been credited to another account.'
      );
    END IF;
  END IF;

  -- I. Sequential Overlap Access Window Calculation
  -- Look for the latest active completed subscription end date for this user
  SELECT MAX(subscription_end_date)
  INTO v_latest_end
  FROM public.subscriptions
  WHERE user_id = p_user_id
    AND payment_status = 'completed';

  IF v_latest_end IS NOT NULL AND v_latest_end > v_now THEN
    -- Active access remaining: start new access at the exact end of currently paid access
    v_start_date := v_latest_end;
  ELSE
    -- No active access or expired: start immediately
    v_start_date := v_now;
  END IF;

  -- J. Calculate end date using UTC-safe calendar arithmetic
  IF v_clean_plan = 'yearly_250' THEN
    -- Exactly 1 calendar year evaluated strictly in UTC
    -- (PostgreSQL automatically clamps Feb 29 to Feb 28 in non-leap years)
    v_end_date := ( (v_start_date AT TIME ZONE 'UTC') + INTERVAL '1 year' ) AT TIME ZONE 'UTC';
  ELSIF v_clean_plan = 'monthly_30' THEN
    -- Exactly 30 x 24 hours (720 hours) in UTC
    v_end_date := v_start_date + INTERVAL '720 hours';
  END IF;

  -- K. Insert the subscription record
  INSERT INTO public.subscriptions (
    user_id,
    full_name,
    plan_type,
    amount_paid,
    currency,
    payment_status,
    razorpay_payment_id,
    razorpay_order_id,
    subscription_start_date,
    subscription_end_date,
    auto_renew
  ) VALUES (
    p_user_id,
    p_full_name,
    v_clean_plan,
    p_amount_paid,
    v_clean_currency,
    'completed',
    TRIM(p_razorpay_payment_id),
    TRIM(p_razorpay_order_id),
    v_start_date,
    v_end_date,
    false
  )
  RETURNING id INTO v_sub_id;

  -- L. Sync user updated_at in public.users
  -- (Only updates columns that exist in the live schema: updated_at)
  UPDATE public.users
  SET updated_at = v_now
  WHERE id = p_user_id;

  -- M. Return structured success payload
  RETURN jsonb_build_object(
    'success', true,
    'subscription', jsonb_build_object(
      'id', v_sub_id,
      'plan_type', v_clean_plan,
      'subscription_start_date', v_start_date,
      'subscription_end_date', v_end_date
    )
  );
END;
$$;

-- 3. Security Hardening & Principle of Least Privilege
-- Strictly revoke from all public and client roles
REVOKE ALL ON FUNCTION public.provision_subscription_access(UUID, TEXT, TEXT, NUMERIC, TEXT, TEXT, TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.provision_subscription_access(UUID, TEXT, TEXT, NUMERIC, TEXT, TEXT, TEXT) FROM anon;
REVOKE ALL ON FUNCTION public.provision_subscription_access(UUID, TEXT, TEXT, NUMERIC, TEXT, TEXT, TEXT) FROM authenticated;

-- Grant execution exclusively to the backend service_role
GRANT EXECUTE ON FUNCTION public.provision_subscription_access(UUID, TEXT, TEXT, NUMERIC, TEXT, TEXT, TEXT) TO service_role;
