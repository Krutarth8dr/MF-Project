-- ============================================
-- SUPABASE SCHEMA FOR USERS & SUBSCRIPTIONS
-- ============================================
-- Run these SQL commands in Supabase SQL Editor
-- This extends the existing fund_holdings schema with auth/payment tracking

-- ============================================
-- 1. USERS TABLE (linked to Supabase Auth)
-- ============================================
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL UNIQUE,
    full_name VARCHAR(255),
    subscription_status VARCHAR(50) DEFAULT 'free',
    subscription_plan VARCHAR(50) DEFAULT 'none',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for faster lookups
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_subscription_status ON users(subscription_status);

-- ============================================
-- 2. SUBSCRIPTIONS TABLE (payment history)
-- ============================================
CREATE TABLE IF NOT EXISTS subscriptions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    razorpay_order_id VARCHAR(255),
    razorpay_payment_id VARCHAR(255) UNIQUE,
    amount_paid DECIMAL(10, 2) NOT NULL,
    currency VARCHAR(10) DEFAULT 'INR',
    payment_status VARCHAR(50) DEFAULT 'pending', -- pending, completed, failed, refunded
    plan_type VARCHAR(50) NOT NULL, -- basic, premium, etc.
    subscription_start_date TIMESTAMP,
    subscription_end_date TIMESTAMP,
    auto_renew BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for faster queries
CREATE INDEX idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX idx_subscriptions_razorpay_payment_id ON subscriptions(razorpay_payment_id);
CREATE INDEX idx_subscriptions_payment_status ON subscriptions(payment_status);
CREATE INDEX idx_subscriptions_user_status ON subscriptions(user_id, payment_status);

-- ============================================
-- 3. ENABLE RLS FOR USERS & SUBSCRIPTIONS
-- ============================================
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;

-- Users can only read their own profile
CREATE POLICY "Users can read own profile" ON users
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update own profile" ON users
    FOR UPDATE USING (auth.uid() = id);

-- Users can only read their own subscriptions
CREATE POLICY "Users can read own subscriptions" ON subscriptions
    FOR SELECT USING (auth.uid() = user_id);

-- ============================================
-- 4. AUTO-CREATE USER ON SIGNUP
-- ============================================
-- This function creates a user record when someone signs up
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.users (id, email)
  VALUES (NEW.id, NEW.email);
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

-- Trigger on auth.users to auto-create public.users record
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ============================================
-- 5. UPDATE FUND_HOLDINGS WITH RLS FOR PAID USERS ONLY
-- ============================================
-- DROP old permissive policies
DROP POLICY IF EXISTS "Enable select for authenticated users" ON fund_holdings;
DROP POLICY IF EXISTS "Enable select for anonymous users" ON fund_holdings;

-- New restrictive policy: Only show data to users with active subscriptions
CREATE POLICY "Enable select for paid subscribers" ON fund_holdings
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM subscriptions
            WHERE user_id = auth.uid()
            AND payment_status = 'completed'
            AND (subscription_end_date IS NULL OR subscription_end_date > NOW())
        )
        OR auth.role() = 'service_role'
    );

-- Service role (for upload script) bypasses RLS
-- If you want to prevent accidental queries, you can keep this more restrictive

-- ============================================
-- 6. HELPER VIEWS
-- ============================================
-- Get active subscribers
CREATE OR REPLACE VIEW active_subscribers AS
SELECT DISTINCT ON (u.id)
    u.id,
    u.email,
    u.full_name,
    s.subscription_start_date,
    s.subscription_end_date,
    s.plan_type,
    u.created_at
FROM users u
JOIN subscriptions s ON u.id = s.user_id
WHERE s.payment_status = 'completed'
AND (s.subscription_end_date IS NULL OR s.subscription_end_date > NOW())
ORDER BY u.id, s.subscription_end_date DESC NULLS LAST;

-- Get subscription status for dashboard
CREATE OR REPLACE VIEW user_subscription_status AS
SELECT
    u.id,
    u.email,
    u.subscription_status,
    u.subscription_plan,
    s.payment_status,
    s.subscription_end_date,
    ROW_NUMBER() OVER (PARTITION BY u.id ORDER BY s.created_at DESC) as latest
FROM users u
LEFT JOIN subscriptions s ON u.id = s.user_id;
