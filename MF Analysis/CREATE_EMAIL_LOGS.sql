-- ============================================================
-- WEALTHYNEERS EMAIL NOTIFICATION LOGS & DEDUPLICATION TABLE
-- ============================================================
-- Run this SQL in the Supabase SQL Editor to enable email logging
-- and guarantee atomic duplicate protection for scheduled emails.

CREATE TABLE IF NOT EXISTS public.email_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    email_type VARCHAR(50) NOT NULL, -- e.g. 'subscription_expiry_reminder', 'monthly_data_announcement'
    reference_id VARCHAR(100) NOT NULL, -- e.g. subscriptions.id (for expiry) or 'YYYY-MM' (for monthly announcement)
    recipient_email VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'sent', -- 'sent', 'failed'
    error_message TEXT,
    sent_at TIMESTAMPTZ DEFAULT NOW(),

    -- HARD DATABASE CONSTRAINT: Guarantees zero duplicate emails per user/cycle
    CONSTRAINT unique_user_email_event UNIQUE (user_id, email_type, reference_id)
);

-- Performance indexes for fast deduplication lookups
CREATE INDEX IF NOT EXISTS idx_email_logs_user_type_ref 
    ON public.email_logs(user_id, email_type, reference_id);

CREATE INDEX IF NOT EXISTS idx_email_logs_status 
    ON public.email_logs(status);

-- Enable Row Level Security (RLS)
ALTER TABLE public.email_logs ENABLE ROW LEVEL SECURITY;

-- Note: No public/authenticated SELECT, INSERT, UPDATE, or DELETE policies are created.
-- This table is strictly accessible by the server-side Supabase Service Role client.
