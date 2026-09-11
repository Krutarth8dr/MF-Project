-- ==============================================================================
-- DEDUPLICATE & CREATE UNIQUE INDEX FOR FUND_HOLDINGS
-- ==============================================================================
-- Run this in your Supabase SQL Editor:
-- https://supabase.com/dashboard/project/sbyidtthoxclyxmeromt/sql

-- 1. Deduplicate any existing identical records (retains the latest row)
DELETE FROM fund_holdings a
USING fund_holdings b
WHERE a.id < b.id
  AND a.amc = b.amc
  AND a.fund_name = b.fund_name
  AND a.isin = b.isin
  AND a.portfolio_date = b.portfolio_date;

-- 2. Create Unique Index required for PostgREST Upsert ON CONFLICT resolution
CREATE UNIQUE INDEX IF NOT EXISTS idx_fund_holdings_unique_holding 
ON fund_holdings (amc, fund_name, isin, portfolio_date);
