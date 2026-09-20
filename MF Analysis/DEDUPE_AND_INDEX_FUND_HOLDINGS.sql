-- ==============================================================================
-- DEDUPLICATE & CREATE UNIQUE INDEX FOR FUND_HOLDINGS
-- ==============================================================================
-- Run this in your Supabase SQL Editor:
-- https://supabase.com/dashboard/project/sbyidtthoxclyxmeromt/sql

-- Set timeout to 5 minutes so index build on 500k rows completes smoothly
SET statement_timeout = '300s';

-- 1. Deduplicate any existing identical records (retains the latest row)
DELETE FROM public.fund_holdings a
USING public.fund_holdings b
WHERE a.id < b.id
  AND a.amc = b.amc
  AND a.fund_name = b.fund_name
  AND a.isin = b.isin
  AND a.portfolio_date = b.portfolio_date
  AND a.security_name = b.security_name;

-- 2. Drop existing constraint or index (handles both table constraints and standalone indexes)
ALTER TABLE public.fund_holdings DROP CONSTRAINT IF EXISTS idx_fund_holdings_unique_holding CASCADE;
ALTER TABLE public.fund_holdings DROP CONSTRAINT IF EXISTS unique_holding CASCADE;
DROP INDEX IF EXISTS public.idx_fund_holdings_unique_holding CASCADE;

-- 3. Create Unique Index on 5 columns required for separate tranche tracking and PostgREST Upsert
CREATE UNIQUE INDEX idx_fund_holdings_unique_holding 
ON public.fund_holdings (amc, fund_name, isin, portfolio_date, security_name);

-- 4. Verify the newly created index
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE tablename = 'fund_holdings' AND indexname = 'idx_fund_holdings_unique_holding';
