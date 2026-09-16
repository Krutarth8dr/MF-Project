-- ==============================================================================
-- WEALTHYNEERS REPORT 6 — MULTI-SELECT AMC & FUND NAME FILTER RPC
-- ==============================================================================
-- Run this in your Supabase SQL Editor:
-- https://supabase.com/dashboard/project/sbyidtthoxclyxmeromt/sql
--
-- This script adds:
-- 1. get_report6_filter_options(p_amcs text[] DEFAULT NULL):
--    Returns clean, deduplicated, sorted AMCs and corresponding funds mapping.
-- 2. get_report6_data(...):
--    Extended with p_amcs text[] and p_funds text[] parameters.
--    - When p_amcs IS NULL AND p_funds IS NULL: Serves from mf_report_6 directly (100% regression fidelity).
--    - When p_amcs or p_funds is set: Dynamically recomputes the 1M-7M consensus,
--      green/red/neutral counts, and NET score solely from the filtered holdings universe.
-- ==============================================================================

-- ── 1. FILTER OPTIONS RPC ─────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.get_report6_filter_options(
    p_amcs text[] DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS 
DECLARE
    v_amcs jsonb;
    v_funds jsonb;
    v_map jsonb;
BEGIN
    -- Security check: Verify active subscription (bypassed for service_role)
    IF auth.role() != 'service_role' THEN
        IF NOT EXISTS (
            SELECT 1 FROM public.subscriptions 
            WHERE user_id = auth.uid() 
              AND payment_status = 'completed' 
              AND (subscription_end_date IS NULL OR subscription_end_date > now())
        ) THEN
            RAISE EXCEPTION 'Access Denied: Active institutional subscription required.';
        END IF;
    END IF;

    -- All unique clean AMCs (sorted alphabetically, no nulls/blanks)
    SELECT jsonb_agg(amc ORDER BY amc)
    INTO v_amcs
    FROM (
        SELECT DISTINCT TRIM(amc) AS amc
        FROM public.fund_holdings
        WHERE amc IS NOT NULL AND TRIM(amc) <> ''
    ) t;

    -- Distinct clean funds matching selected AMCs (or all funds if no AMC selected)
    SELECT jsonb_agg(fund_name ORDER BY fund_name)
    INTO v_funds
    FROM (
        SELECT DISTINCT TRIM(fund_name) AS fund_name
        FROM public.fund_holdings
        WHERE fund_name IS NOT NULL 
          AND TRIM(fund_name) <> ''
          AND (p_amcs IS NULL OR cardinality(p_amcs) = 0 OR TRIM(amc) = ANY(p_amcs))
    ) f;

    -- Mapping of each AMC to its distinct list of funds
    SELECT jsonb_object_agg(amc, fund_list)
    INTO v_map
    FROM (
        SELECT 
            TRIM(amc) AS amc,
            jsonb_agg(DISTINCT TRIM(fund_name) ORDER BY TRIM(fund_name)) AS fund_list
        FROM public.fund_holdings
        WHERE amc IS NOT NULL AND TRIM(amc) <> ''
          AND fund_name IS NOT NULL AND TRIM(fund_name) <> ''
        GROUP BY TRIM(amc)
    ) m;

    RETURN jsonb_build_object(
        'amcs', COALESCE(v_amcs, '[]'::jsonb),
        'funds', COALESCE(v_funds, '[]'::jsonb),
        'amc_funds_map', COALESCE(v_map, '{}'::jsonb)
    );
END;
;

GRANT EXECUTE ON FUNCTION public.get_report6_filter_options(text[]) TO authenticated, service_role, anon;

-- ── 2. REPORT 6 DATA RPC WITH DYNAMIC AMC & FUND FILTERING ────────────────────
CREATE OR REPLACE FUNCTION public.get_report6_data(
    p_search text DEFAULT NULL,
    p_dirs jsonb DEFAULT NULL,
    p_limit integer DEFAULT 50,
    p_offset integer DEFAULT 0,
    p_amcs text[] DEFAULT NULL,
    p_funds text[] DEFAULT NULL
)
RETURNS TABLE (
    isin varchar,
    security_name varchar,
    amc_direction text,
    amc_2_direction text,
    amc_3_direction text,
    amc_4_direction text,
    amc_5_direction text,
    amc_6_direction text,
    amc_7_direction text,
    m1_cur_date date,
    m1_prev_date date,
    m1_cur_qty bigint,
    m1_prev_qty bigint,
    m1_change bigint,
    m2_cur_date date,
    m2_prev_date date,
    m2_cur_qty bigint,
    m2_prev_qty bigint,
    m2_change bigint,
    m3_cur_date date,
    m3_prev_date date,
    m3_cur_qty bigint,
    m3_prev_qty bigint,
    m3_change bigint,
    m4_cur_date date,
    m4_prev_date date,
    m4_cur_qty bigint,
    m4_prev_qty bigint,
    m4_change bigint,
    m5_cur_date date,
    m5_prev_date date,
    m5_cur_qty bigint,
    m5_prev_qty bigint,
    m5_change bigint,
    m6_cur_date date,
    m6_prev_date date,
    m6_cur_qty bigint,
    m6_prev_qty bigint,
    m6_change bigint,
    m7_cur_date date,
    m7_prev_date date,
    m7_cur_qty bigint,
    m7_prev_qty bigint,
    m7_change bigint,
    amc_green_count integer,
    amc_red_count integer,
    amc_neutral_count integer,
    amc_net integer,
    total_count bigint
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS 
DECLARE
    v_dates date[];
    d1 date; d2 date; d3 date; d4 date; d5 date; d6 date; d7 date; d8 date;
BEGIN
    -- Security check: Verify active subscription (bypassed for service_role)
    IF auth.role() != 'service_role' THEN
        IF NOT EXISTS (
            SELECT 1 FROM public.subscriptions 
            WHERE user_id = auth.uid() 
              AND payment_status = 'completed' 
              AND (subscription_end_date IS NULL OR subscription_end_date > now())
        ) THEN
            RAISE EXCEPTION 'Access Denied: Active institutional subscription required.';
        END IF;
    END IF;

    -- =========================================================================
    -- CASE A: DEFAULT UNFILTERED VIEW (All AMCs + All Funds)
    -- Directly serve from mf_report_6 for instant query time & exact regression fidelity
    -- =========================================================================
    IF (p_amcs IS NULL OR cardinality(p_amcs) = 0) AND (p_funds IS NULL OR cardinality(p_funds) = 0) THEN
        RETURN QUERY
        WITH base AS (
            SELECT 
                m.*,
                COUNT(*) OVER() AS full_count
            FROM public.mf_report_6 m
            WHERE (p_search IS NULL OR m.security_name ILIKE ('%' || p_search || '%') OR m.isin ILIKE ('%' || p_search || '%'))
              AND (p_dirs IS NULL OR (
                    (p_dirs->>'amc_direction' IS NULL OR m.amc_direction = (p_dirs->>'amc_direction')) AND
                    (p_dirs->>'amc_2_direction' IS NULL OR m.amc_2_direction = (p_dirs->>'amc_2_direction')) AND
                    (p_dirs->>'amc_3_direction' IS NULL OR m.amc_3_direction = (p_dirs->>'amc_3_direction')) AND
                    (p_dirs->>'amc_4_direction' IS NULL OR m.amc_4_direction = (p_dirs->>'amc_4_direction')) AND
                    (p_dirs->>'amc_5_direction' IS NULL OR m.amc_5_direction = (p_dirs->>'amc_5_direction')) AND
                    (p_dirs->>'amc_6_direction' IS NULL OR m.amc_6_direction = (p_dirs->>'amc_6_direction')) AND
                    (p_dirs->>'amc_7_direction' IS NULL OR m.amc_7_direction = (p_dirs->>'amc_7_direction'))
              ))
        )
        SELECT 
            b.isin::varchar,
            b.security_name::varchar,
            b.amc_direction::text,
            b.amc_2_direction::text,
            b.amc_3_direction::text,
            b.amc_4_direction::text,
            b.amc_5_direction::text,
            b.amc_6_direction::text,
            b.amc_7_direction::text,
            b.m1_cur_date::date,
            b.m1_prev_date::date,
            b.m1_cur_qty::bigint,
            b.m1_prev_qty::bigint,
            b.m1_change::bigint,
            b.m2_cur_date::date,
            b.m2_prev_date::date,
            b.m2_cur_qty::bigint,
            b.m2_prev_qty::bigint,
            b.m2_change::bigint,
            b.m3_cur_date::date,
            b.m3_prev_date::date,
            b.m3_cur_qty::bigint,
            b.m3_prev_qty::bigint,
            b.m3_change::bigint,
            b.m4_cur_date::date,
            b.m4_prev_date::date,
            b.m4_cur_qty::bigint,
            b.m4_prev_qty::bigint,
            b.m4_change::bigint,
            b.m5_cur_date::date,
            b.m5_prev_date::date,
            b.m5_cur_qty::bigint,
            b.m5_prev_qty::bigint,
            b.m5_change::bigint,
            b.m6_cur_date::date,
            b.m6_prev_date::date,
            b.m6_cur_qty::bigint,
            b.m6_prev_qty::bigint,
            b.m6_change::bigint,
            b.m7_cur_date::date,
            b.m7_prev_date::date,
            b.m7_cur_qty::bigint,
            b.m7_prev_qty::bigint,
            b.m7_change::bigint,
            b.amc_green_count::integer,
            b.amc_red_count::integer,
            b.amc_neutral_count::integer,
            b.amc_net::integer,
            b.full_count::bigint AS total_count
        FROM base b
        ORDER BY b.amc_net DESC, b.security_name ASC
        LIMIT p_limit OFFSET p_offset;
        RETURN;
    END IF;

    -- =========================================================================
    -- CASE B: DYNAMIC CALCULATION FROM FILTERED HOLDINGS (AMC / Fund selected)
    -- Recompute 1M-7M directions, counts & NET score solely from the chosen universe
    -- =========================================================================
    -- Fetch the latest 8 consecutive portfolio disclosure dates
    SELECT ARRAY(
        SELECT DISTINCT portfolio_date
        FROM public.fund_holdings
        ORDER BY portfolio_date DESC
        LIMIT 8
    ) INTO v_dates;

    IF v_dates IS NULL OR cardinality(v_dates) < 8 THEN
        RETURN;
    END IF;

    d1 := v_dates[1];
    d2 := v_dates[2];
    d3 := v_dates[3];
    d4 := v_dates[4];
    d5 := v_dates[5];
    d6 := v_dates[6];
    d7 := v_dates[7];
    d8 := v_dates[8];

    RETURN QUERY
    WITH filtered_holdings AS (
        SELECT 
            fh.isin,
            fh.portfolio_date,
            SUM(fh.quantity)::bigint AS qty
        FROM public.fund_holdings fh
        WHERE (p_amcs IS NULL OR cardinality(p_amcs) = 0 OR TRIM(fh.amc) = ANY(p_amcs))
          AND (p_funds IS NULL OR cardinality(p_funds) = 0 OR TRIM(fh.fund_name) = ANY(p_funds))
          AND fh.portfolio_date >= d8
          AND fh.isin LIKE 'INE%'
        GROUP BY fh.isin, fh.portfolio_date
    ),
    isin_monthly AS (
        SELECT
            fh.isin,
            COALESCE(SUM(fh.qty) FILTER (WHERE fh.portfolio_date = d1), 0)::bigint AS q1,
            COALESCE(SUM(fh.qty) FILTER (WHERE fh.portfolio_date = d2), 0)::bigint AS q2,
            COALESCE(SUM(fh.qty) FILTER (WHERE fh.portfolio_date = d3), 0)::bigint AS q3,
            COALESCE(SUM(fh.qty) FILTER (WHERE fh.portfolio_date = d4), 0)::bigint AS q4,
            COALESCE(SUM(fh.qty) FILTER (WHERE fh.portfolio_date = d5), 0)::bigint AS q5,
            COALESCE(SUM(fh.qty) FILTER (WHERE fh.portfolio_date = d6), 0)::bigint AS q6,
            COALESCE(SUM(fh.qty) FILTER (WHERE fh.portfolio_date = d7), 0)::bigint AS q7,
            COALESCE(SUM(fh.qty) FILTER (WHERE fh.portfolio_date = d8), 0)::bigint AS q8
        FROM filtered_holdings fh
        GROUP BY fh.isin
        HAVING COALESCE(SUM(fh.qty), 0) > 0
    ),
    computed AS (
        SELECT
            im.isin,
            COALESCE(sm.name_1, (SELECT fh2.security_name FROM public.fund_holdings fh2 WHERE fh2.isin = im.isin LIMIT 1), im.isin) AS sec_name,
            -- Directions: G = Increase, R = Decrease, N = Flat
            CASE WHEN im.q1 > im.q2 THEN 'G' WHEN im.q1 < im.q2 THEN 'R' ELSE 'N' END AS dir_1,
            CASE WHEN im.q2 > im.q3 THEN 'G' WHEN im.q2 < im.q3 THEN 'R' ELSE 'N' END AS dir_2,
            CASE WHEN im.q3 > im.q4 THEN 'G' WHEN im.q3 < im.q4 THEN 'R' ELSE 'N' END AS dir_3,
            CASE WHEN im.q4 > im.q5 THEN 'G' WHEN im.q4 < im.q5 THEN 'R' ELSE 'N' END AS dir_4,
            CASE WHEN im.q5 > im.q6 THEN 'G' WHEN im.q5 < im.q6 THEN 'R' ELSE 'N' END AS dir_5,
            CASE WHEN im.q6 > im.q7 THEN 'G' WHEN im.q6 < im.q7 THEN 'R' ELSE 'N' END AS dir_6,
            CASE WHEN im.q7 > im.q8 THEN 'G' WHEN im.q7 < im.q8 THEN 'R' ELSE 'N' END AS dir_7,
            -- Dates & quantities
            d1 AS c_d1, d2 AS p_d1, im.q1 AS c_q1, im.q2 AS p_q1, (im.q1 - im.q2) AS chg_1,
            d2 AS c_d2, d3 AS p_d2, im.q2 AS c_q2, im.q3 AS p_q2, (im.q2 - im.q3) AS chg_2,
            d3 AS c_d3, d4 AS p_d3, im.q3 AS c_q3, im.q4 AS p_q3, (im.q3 - im.q4) AS chg_3,
            d4 AS c_d4, d5 AS p_d4, im.q4 AS c_q4, im.q5 AS p_q4, (im.q4 - im.q5) AS chg_4,
            d5 AS c_d5, d6 AS p_d5, im.q5 AS c_q5, im.q6 AS p_q5, (im.q5 - im.q6) AS chg_5,
            d6 AS c_d6, d7 AS p_d6, im.q6 AS c_q6, im.q7 AS p_q6, (im.q6 - im.q7) AS chg_6,
            d7 AS c_d7, d8 AS p_d7, im.q7 AS c_q7, im.q8 AS p_q7, (im.q7 - im.q8) AS chg_7
        FROM isin_monthly im
        LEFT JOIN public.security_master sm ON sm.isin = im.isin
    ),
    with_counts AS (
        SELECT
            c.*,
            (
                (CASE WHEN c.dir_1 = 'G' THEN 1 ELSE 0 END) +
                (CASE WHEN c.dir_2 = 'G' THEN 1 ELSE 0 END) +
                (CASE WHEN c.dir_3 = 'G' THEN 1 ELSE 0 END) +
                (CASE WHEN c.dir_4 = 'G' THEN 1 ELSE 0 END) +
                (CASE WHEN c.dir_5 = 'G' THEN 1 ELSE 0 END) +
                (CASE WHEN c.dir_6 = 'G' THEN 1 ELSE 0 END) +
                (CASE WHEN c.dir_7 = 'G' THEN 1 ELSE 0 END)
            )::integer AS g_cnt,
            (
                (CASE WHEN c.dir_1 = 'R' THEN 1 ELSE 0 END) +
                (CASE WHEN c.dir_2 = 'R' THEN 1 ELSE 0 END) +
                (CASE WHEN c.dir_3 = 'R' THEN 1 ELSE 0 END) +
                (CASE WHEN c.dir_4 = 'R' THEN 1 ELSE 0 END) +
                (CASE WHEN c.dir_5 = 'R' THEN 1 ELSE 0 END) +
                (CASE WHEN c.dir_6 = 'R' THEN 1 ELSE 0 END) +
                (CASE WHEN c.dir_7 = 'R' THEN 1 ELSE 0 END)
            )::integer AS r_cnt,
            (
                (CASE WHEN c.dir_1 = 'N' THEN 1 ELSE 0 END) +
                (CASE WHEN c.dir_2 = 'N' THEN 1 ELSE 0 END) +
                (CASE WHEN c.dir_3 = 'N' THEN 1 ELSE 0 END) +
                (CASE WHEN c.dir_4 = 'N' THEN 1 ELSE 0 END) +
                (CASE WHEN c.dir_5 = 'N' THEN 1 ELSE 0 END) +
                (CASE WHEN c.dir_6 = 'N' THEN 1 ELSE 0 END) +
                (CASE WHEN c.dir_7 = 'N' THEN 1 ELSE 0 END)
            )::integer AS n_cnt
        FROM computed c
    ),
    with_net AS (
        SELECT
            wc.*,
            (wc.g_cnt - wc.r_cnt)::integer AS net_score
        FROM with_counts wc
    ),
    filtered_results AS (
        SELECT
            wn.*,
            COUNT(*) OVER() AS full_count
        FROM with_net wn
        WHERE (p_search IS NULL OR wn.sec_name ILIKE ('%' || p_search || '%') OR wn.isin ILIKE ('%' || p_search || '%'))
          AND (p_dirs IS NULL OR (
                (p_dirs->>'amc_direction' IS NULL OR wn.dir_1 = (p_dirs->>'amc_direction')) AND
                (p_dirs->>'amc_2_direction' IS NULL OR wn.dir_2 = (p_dirs->>'amc_2_direction')) AND
                (p_dirs->>'amc_3_direction' IS NULL OR wn.dir_3 = (p_dirs->>'amc_3_direction')) AND
                (p_dirs->>'amc_4_direction' IS NULL OR wn.dir_4 = (p_dirs->>'amc_4_direction')) AND
                (p_dirs->>'amc_5_direction' IS NULL OR wn.dir_5 = (p_dirs->>'amc_5_direction')) AND
                (p_dirs->>'amc_6_direction' IS NULL OR wn.dir_6 = (p_dirs->>'amc_6_direction')) AND
                (p_dirs->>'amc_7_direction' IS NULL OR wn.dir_7 = (p_dirs->>'amc_7_direction'))
          ))
    )
    SELECT
        fr.isin::varchar,
        fr.sec_name::varchar AS security_name,
        fr.dir_1::text AS amc_direction,
        fr.dir_2::text AS amc_2_direction,
        fr.dir_3::text AS amc_3_direction,
        fr.dir_4::text AS amc_4_direction,
        fr.dir_5::text AS amc_5_direction,
        fr.dir_6::text AS amc_6_direction,
        fr.dir_7::text AS amc_7_direction,
        fr.c_d1::date AS m1_cur_date,
        fr.p_d1::date AS m1_prev_date,
        fr.c_q1::bigint AS m1_cur_qty,
        fr.p_q1::bigint AS m1_prev_qty,
        fr.chg_1::bigint AS m1_change,
        fr.c_d2::date AS m2_cur_date,
        fr.p_d2::date AS m2_prev_date,
        fr.c_q2::bigint AS m2_cur_qty,
        fr.p_q2::bigint AS m2_prev_qty,
        fr.chg_2::bigint AS m2_change,
        fr.c_d3::date AS m3_cur_date,
        fr.p_d3::date AS m3_prev_date,
        fr.c_q3::bigint AS m3_cur_qty,
        fr.p_q3::bigint AS m3_prev_qty,
        fr.chg_3::bigint AS m3_change,
        fr.c_d4::date AS m4_cur_date,
        fr.p_d4::date AS m4_prev_date,
        fr.c_q4::bigint AS m4_cur_qty,
        fr.p_q4::bigint AS m4_prev_qty,
        fr.chg_4::bigint AS m4_change,
        fr.c_d5::date AS m5_cur_date,
        fr.p_d5::date AS m5_prev_date,
        fr.c_q5::bigint AS m5_cur_qty,
        fr.p_q5::bigint AS m5_prev_qty,
        fr.chg_5::bigint AS m5_change,
        fr.c_d6::date AS m6_cur_date,
        fr.p_d6::date AS m6_prev_date,
        fr.c_q6::bigint AS m6_cur_qty,
        fr.p_q6::bigint AS m6_prev_qty,
        fr.chg_6::bigint AS m6_change,
        fr.c_d7::date AS m7_cur_date,
        fr.p_d7::date AS m7_prev_date,
        fr.c_q7::bigint AS m7_cur_qty,
        fr.p_q7::bigint AS m7_prev_qty,
        fr.chg_7::bigint AS m7_change,
        fr.g_cnt::integer AS amc_green_count,
        fr.r_cnt::integer AS amc_red_count,
        fr.n_cnt::integer AS amc_neutral_count,
        fr.net_score::integer AS amc_net,
        fr.full_count::bigint AS total_count
    FROM filtered_results fr
    ORDER BY fr.net_score DESC, fr.sec_name ASC
    LIMIT p_limit OFFSET p_offset;
END;
;

GRANT EXECUTE ON FUNCTION public.get_report6_data(text, jsonb, integer, integer, text[], text[]) TO authenticated, service_role, anon;
