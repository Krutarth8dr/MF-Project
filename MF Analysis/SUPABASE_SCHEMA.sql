-- ============================================
-- SUPABASE SCHEMA FOR WEALTHINEERS DASHBOARD
-- ============================================
-- Run these SQL commands in Supabase SQL Editor

-- Create fund_holdings table
CREATE TABLE IF NOT EXISTS fund_holdings (
    id BIGSERIAL PRIMARY KEY,
    amc VARCHAR(255) NOT NULL,
    security_name VARCHAR(255) NOT NULL,
    isin VARCHAR(20),
    portfolio_date DATE NOT NULL,
    month VARCHAR(20),
    industry_rating VARCHAR(100),
    fund_name VARCHAR(255) NOT NULL,
    quantity BIGINT,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Unique constraint to prevent duplicates
    CONSTRAINT unique_holding UNIQUE (amc, fund_name, security_name, portfolio_date)
);

-- Create indexes for faster queries
CREATE INDEX idx_amc ON fund_holdings(amc);
CREATE INDEX idx_fund_name ON fund_holdings(fund_name);
CREATE INDEX idx_security_name ON fund_holdings(security_name);
CREATE INDEX idx_portfolio_date ON fund_holdings(portfolio_date);
CREATE INDEX idx_month ON fund_holdings(month);

-- Create views for easier querying

-- View: Get unique securities
CREATE OR REPLACE VIEW unique_securities AS
SELECT DISTINCT security_name
FROM fund_holdings
ORDER BY security_name;

-- View: Get unique funds
CREATE OR REPLACE VIEW unique_funds AS
SELECT DISTINCT fund_name, amc
FROM fund_holdings
ORDER BY amc, fund_name;

-- View: Get unique AMCs
CREATE OR REPLACE VIEW unique_amcs AS
SELECT DISTINCT amc
FROM fund_holdings
ORDER BY amc;

-- View: Get unique months/dates
CREATE OR REPLACE VIEW unique_months AS
SELECT DISTINCT portfolio_date, month
FROM fund_holdings
ORDER BY portfolio_date DESC;

-- Enable RLS (Row Level Security) for frontend access
ALTER TABLE fund_holdings ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if any
DROP POLICY IF EXISTS "Enable select for authenticated users" ON fund_holdings;
DROP POLICY IF EXISTS "Enable select for anonymous users" ON fund_holdings;
DROP POLICY IF EXISTS "Enable all for all users" ON fund_holdings;

-- Allow full access for fund_holdings (select, insert, update)
CREATE POLICY "Enable all for all users" ON fund_holdings
    FOR ALL USING (true) WITH CHECK (true);

-- ============================================
-- 2. SECURITY MASTER TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS security_master (
    isin VARCHAR(50) PRIMARY KEY,
    name_1 VARCHAR(255) NOT NULL,
    name_2 VARCHAR(255),
    name_3 VARCHAR(255),
    name_4 VARCHAR(255),
    name_5 VARCHAR(255),
    name_6 VARCHAR(255),
    name_7 VARCHAR(255),
    name_8 VARCHAR(255),
    name_9 VARCHAR(255),
    name_10 VARCHAR(255),
    name_11 VARCHAR(255),
    name_12 VARCHAR(255),
    name_13 VARCHAR(255),
    name_14 VARCHAR(255),
    name_15 VARCHAR(255),
    name_16 VARCHAR(255),
    name_17 VARCHAR(255),
    name_18 VARCHAR(255),
    name_19 VARCHAR(255),
    name_20 VARCHAR(255),
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index on primary name for quick search
CREATE INDEX IF NOT EXISTS idx_security_master_name_1 ON security_master(name_1);

-- Enable RLS for security_master
ALTER TABLE security_master ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if any
DROP POLICY IF EXISTS "Enable select for authenticated users on security_master" ON security_master;
DROP POLICY IF EXISTS "Enable select for anonymous users on security_master" ON security_master;
DROP POLICY IF EXISTS "Enable all for all users on security_master" ON security_master;

-- Allow full access for security_master (select, insert, update)
CREATE POLICY "Enable all for all users on security_master" ON security_master
    FOR ALL USING (true) WITH CHECK (true);


