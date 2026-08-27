'use client';

import { useState, useEffect, useCallback, useRef, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LabelList,
} from 'recharts';
import { supabase } from '@/lib/supabase';
import { getCachedSubscription, checkUserSubscription } from '@/lib/subscriptionCache';
import ReportGuideModal from '@/app/components/ReportGuideModal';

// ─── Helpers ─────────────────────────────────────────────────────────

/** Format quantity — compact but precise (2 decimal places) */
function fmtQty(n) {
  if (n == null || isNaN(n)) return '0';
  const abs = Math.abs(n);
  if (abs >= 1_000_000_000) return (n / 1_000_000_000).toFixed(2) + 'B';
  if (abs >= 1_000_000) return (n / 1_000_000).toFixed(2) + 'M';
  if (abs >= 1_000) return (n / 1_000).toFixed(2) + 'K';
  return n.toLocaleString('en-IN');
}

/** Custom data-label rendered above each dot on the line chart */
function DataLabel({ x, y, value }) {
  if (value == null) return null;
  return (
    <text
      x={x}
      y={y - 10}
      textAnchor="middle"
      fontSize={9}
      fontWeight="700"
      fill="var(--primary)"
      style={{ userSelect: 'none' }}
    >
      {fmtQty(value)}
    </text>
  );
}

/** Parse a YYYY-MM-DD string safely in local time to avoid UTC-shift */
function parseLocalDate(dateStr) {
  if (!dateStr) return null;
  const [y, m, d] = dateStr.split('-').map(Number);
  return new Date(y, m - 1, d);
}

/** Format a portfolio_date string as "Oct-2024" */
function fmtMonth(dateStr) {
  const d = parseLocalDate(dateStr);
  if (!d) return dateStr;
  const mon = d.toLocaleString('en-US', { month: 'short' });
  return `${mon}-${d.getFullYear()}`;
}

// ─── Custom recharts tooltip ─────────────────────────────────────────
function R1Tooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const qty = payload[0]?.value;
  return (
    <div className="r1-tooltip">
      <p className="r1-tooltip-date">{fmtMonth(label)}</p>
      <div className="r1-tooltip-row">
        <span>Total Quantity</span>
        <strong>{qty != null ? qty.toLocaleString('en-US') : '—'}</strong>
      </div>
    </div>
  );
}

// ─── Multi-select AMC Dropdown Component ─────────────────────────────
function AMCMultiSelect({ options, selected, onChange }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const toggle = (amc) => {
    if (selected.includes(amc)) {
      onChange(selected.filter((a) => a !== amc));
    } else {
      onChange([...selected, amc]);
    }
  };

  const label =
    selected.length === 0 ? 'All AMCs'
    : selected.length === 1 ? selected[0]
    : `${selected.length} AMCs Selected`;

  return (
    <div className="r1-amc-wrap" ref={ref}>
      <button
        type="button"
        className="r1-amc-trigger"
        onClick={() => setOpen((o) => !o)}
      >
        <span className="r1-amc-label-text">{label}</span>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#5a6b7c" strokeWidth="2">
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {open && (
        <div className="r1-amc-panel">
          <div className="r1-amc-panel-actions">
            <button
              type="button"
              className="r1-amc-action"
              onClick={() => onChange([])}
            >
              Clear All
            </button>
            <button
              type="button"
              className="r1-amc-action"
              onClick={() => onChange([...options])}
            >
              Select All
            </button>
          </div>
          <ul className="r1-amc-list">
            {options.map((amc) => (
              <li key={amc}>
                <label className="r1-check-row">
                  <input
                    type="checkbox"
                    checked={selected.includes(amc)}
                    onChange={() => toggle(amc)}
                  />
                  <span>{amc}</span>
                </label>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// ─── Constants ────────────────────────────────────────────────────────
const SEC_DEBOUNCE = 350;
const CHART_DEBOUNCE = 250;

// ─── Main Content Inner ──────────────────────────────────────────────
function Report1Content() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryISIN = searchParams ? searchParams.get('isin') : null;

  // Auth
  const [authLoading, setAuthLoading] = useState(true);
  const [isSubscribed, setIsSubscribed] = useState(false);

  // Security typeahead
  const [secText, setSecText] = useState('');
  const [secResults, setSecResults] = useState([]);
  const [showSecDrop, setShowSecDrop] = useState(false);
  const [selectedSec, setSelectedSec] = useState(null); // full security_master row

  // ISIN sub-filter (within selected security)
  const [selectedISIN, setSelectedISIN] = useState('');

  // Filter options (loaded once)
  const [amcOptions, setAmcOptions] = useState([]);
  const [fundOptions, setFundOptions] = useState([]);
  const [ratingOptions, setRatingOptions] = useState([]);

  // Filter selections
  const [selectedAMCs, setSelectedAMCs] = useState([]);
  const [selectedFund, setSelectedFund] = useState('');
  const [selectedRating, setSelectedRating] = useState('');

  // Chart data
  const [chartData, setChartData] = useState([]);
  const [chartLoading, setChartLoading] = useState(false);
  const [chartError, setChartError] = useState(null);

  // Refs
  const secWrapRef = useRef(null);
  const secDebRef = useRef(null);

  // Guide modal state
  const [showGuide, setShowGuide] = useState(false);
  const chartDebRef = useRef(null);

  // ── Auth + subscription check ──────────────────────────────────────
  useEffect(() => {
    let mounted = true;

    const checkAuth = async () => {
      try {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) {
          if (mounted) router.push('/login');
          return;
        }

        // 1. Instant 0ms cache read
        const cached = getCachedSubscription(session.user.id);
        if (cached && mounted) {
          setIsSubscribed(true);
          setAuthLoading(false);
        }

        // 2. Validate in background / resolve if not cached
        const active = await checkUserSubscription(session.user.id);
        if (mounted) {
          setIsSubscribed(active);
          setAuthLoading(false);
        }
      } catch (err) {
        console.error('Report 1 auth check error:', err);
        if (mounted) setAuthLoading(false);
      }
    };
    checkAuth();

    return () => {
      mounted = false;
    };
  }, [router]);

  const lastLoadedISINRef = useRef(null);

  // ── Security selection helpers ─────────────────────────────────────
  const selectSecurity = useCallback((sec) => {
    setSelectedSec(sec);
    setSecText(sec.name_1);
    setShowSecDrop(false);
    setSecResults([]);
    setSelectedISIN(''); // reset ISIN sub-filter when security changes
  }, []);

  const clearSecurity = useCallback(() => {
    lastLoadedISINRef.current = null;
    setSelectedSec(null);
    setSecText('');
    setSecResults([]);
    setShowSecDrop(false);
    setSelectedISIN('');
    if (queryISIN) {
      router.replace('/report1', { scroll: false });
    }
  }, [queryISIN, router]);

  // ── Auto-select from query parameter (?isin=...) ────────────────────
  useEffect(() => {
    if (!queryISIN || queryISIN === lastLoadedISINRef.current) return;
    lastLoadedISINRef.current = queryISIN;
    const loadFromQuery = async () => {
      const clean = queryISIN.trim().toUpperCase();
      const { data } = await supabase.rpc('lookup_security', { p_isin: clean });

      if (data && data.isin) {
        selectSecurity(data);
      } else {
        selectSecurity({ isin: clean, name_1: clean });
      }
    };
    loadFromQuery();
  }, [queryISIN, selectSecurity]);

  // ── Load filter option values once user is confirmed subscribed ────
  useEffect(() => {
    if (authLoading || !isSubscribed) return;
    const loadOptions = async () => {
      const { data } = await supabase.rpc('get_report1_filter_options');
      if (!data) return;
      setAmcOptions(data.filter((r) => r.filter_type === 'amc').map((r) => r.value));
      setFundOptions(data.filter((r) => r.filter_type === 'fund_name').map((r) => r.value));
      setRatingOptions(data.filter((r) => r.filter_type === 'industry_rating').map((r) => r.value));
    };
    loadOptions();
  }, [authLoading, isSubscribed]);

  // ── Security name typeahead search ─────────────────────────────────
  useEffect(() => {
    // If a security is already selected, don't search
    if (selectedSec || !secText.trim()) {
      setSecResults([]);
      setShowSecDrop(false);
      return;
    }
    if (secDebRef.current) clearTimeout(secDebRef.current);
    secDebRef.current = setTimeout(async () => {
      const { data } = await supabase.rpc('search_security_master', {
        p_search: secText.trim(),
        p_limit: 25,
      });
      setSecResults(data || []);
      setShowSecDrop((data?.length ?? 0) > 0);
    }, SEC_DEBOUNCE);
    return () => clearTimeout(secDebRef.current);
  }, [secText, selectedSec]);

  // Close security dropdown when clicking outside
  useEffect(() => {
    const handler = (e) => {
      if (secWrapRef.current && !secWrapRef.current.contains(e.target))
        setShowSecDrop(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // ── Derived: effective ISIN list to pass to RPC ────────────────────
  // selectedISIN beats selectedSec.isin (user explicitly picked a sub-ISIN)
  const effectiveISINs =
    selectedISIN ? [selectedISIN]
    : selectedSec?.isin ? [selectedSec.isin]
    : null; // null = no ISIN filter → include all securities

  // ── Fetch chart data whenever any filter changes (default: all securities) ─
  useEffect(() => {
    if (authLoading || !isSubscribed) return;

    if (chartDebRef.current) clearTimeout(chartDebRef.current);
    chartDebRef.current = setTimeout(async () => {
      setChartLoading(true);
      setChartError(null);
      try {
        const { data, error } = await supabase.rpc('get_report1_chart', {
          p_isins: effectiveISINs,
          p_amcs: selectedAMCs.length > 0 ? selectedAMCs : null,
          p_funds: selectedFund ? [selectedFund] : null,
          p_ratings: selectedRating ? [selectedRating] : null,
        });
        if (error) throw error;
        setChartData(
          (data || []).map((row) => ({
            portfolio_date: row.portfolio_date,
            total_quantity: Number(row.total_quantity),
          }))
        );
      } catch (err) {
        console.error('Report 1 chart error:', err?.message || err);
        setChartError(err?.message || 'Failed to load chart data.');
        setChartData([]);
      } finally {
        setChartLoading(false);
      }
    }, CHART_DEBOUNCE);

    return () => clearTimeout(chartDebRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authLoading, isSubscribed, selectedSec, selectedISIN, selectedAMCs, selectedFund, selectedRating]);

  // ── Clear all filters ──────────────────────────────────────────────
  const clearAll = () => {
    clearSecurity();
    setSelectedAMCs([]);
    setSelectedFund('');
    setSelectedRating('');
  };

  // ── Alternative names (Name 2-5, deduplicated against Name 1) ─────
  const altNames = selectedSec
    ? [selectedSec.name_2, selectedSec.name_3, selectedSec.name_4, selectedSec.name_5]
        .filter((n) => n?.trim() && n.trim().toLowerCase() !== selectedSec.name_1?.toLowerCase())
    : [];

  // ── Y-axis domain ──────────────────────────────────────────────────
  const qtyValues = chartData.map((d) => d.total_quantity);
  const yMax = qtyValues.length ? Math.max(...qtyValues) : 0;
  const yMin = qtyValues.length ? Math.min(...qtyValues) : 0;
  const yPad = Math.max((yMax - yMin) * 0.12, yMax * 0.05, 1);

  // ── X-axis: always show every month label ─────────────────────────

  // ── Loading guard ──────────────────────────────────────────────────
  if (authLoading) {
    return (
      <div className="r6-page">
        <div className="r6-status-msg">
          <div className="r6-spinner" />
          <p>Verifying access…</p>
        </div>
      </div>
    );
  }

  // ── Not subscribed ─────────────────────────────────────────────────
  if (!isSubscribed) {
    return (
      <div className="r6-page">
        <div className="r6-locked-container">
          <div className="r6-locked-icon">🔒</div>
          <h1>Report 1 is Subscribers Only</h1>
          <p>Subscribe to Wealthyneers Premium to unlock the Mutual Fund Quantity Trend report and all analytics.</p>
          <Link href="/#pricing" className="btn btn-primary" style={{ marginTop: '1.5rem', display: 'inline-block' }}>
            Subscribe Now
          </Link>
          <div style={{ marginTop: '1rem' }}>
            <Link href="/dashboard" className="btn btn-outline">Back to Dashboard</Link>
          </div>
        </div>
      </div>
    );
  }

  // ── Main report ────────────────────────────────────────────────────
  return (
    <div className="r1-page">

      {/* ── Page header ── */}
      <div className="r1-header">
        <div className="report-badge-row">
          <span className="report-badge">Report 1</span>
          <button
            type="button"
            className="report-desc-btn"
            onClick={() => setShowGuide(true)}
            title="View comprehensive report documentation & guide"
            aria-label="How To Use Guide"
          >
            📖 How To Use
          </button>
        </div>
        <h1 className="r1-title">Mutual Fund Quantity Trend</h1>
        <p className="r1-subtitle">
          Track the total institutional holding quantity for any security across all AMCs,
          funds, and industry ratings — month by month.
        </p>
      </div>

      {/* ── Filter bar ── */}
      <div className="r1-filter-bar">

        {/* Security typeahead */}
        <div className="r1-filter-group r1-sec-group" ref={secWrapRef}>
          <label className="r1-filter-label">Security (Name)</label>
          {selectedSec ? (
            <div className="r1-selected-chip">
              <span className="r1-chip-text">{selectedSec.name_1}</span>
              <button
                className="r1-chip-x"
                onClick={clearSecurity}
                aria-label="Remove security"
                type="button"
              >
                ×
              </button>
            </div>
          ) : (
            <div className="r1-search-wrap">
              <svg className="r1-search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <input
                type="text"
                className="r1-search-input"
                placeholder="Search security name…"
                value={secText}
                onChange={(e) => setSecText(e.target.value)}
                onFocus={() => secResults.length > 0 && setShowSecDrop(true)}
              />
              {secText && (
                <button
                  className="r1-search-clear"
                  type="button"
                  onClick={() => { setSecText(''); setSecResults([]); setShowSecDrop(false); }}
                >
                  ×
                </button>
              )}
              {showSecDrop && (
                <ul className="r1-sec-dropdown">
                  {secResults.map((s) => (
                    <li
                      key={s.isin}
                      className="r1-sec-opt"
                      onMouseDown={() => selectSecurity(s)}
                    >
                      <span className="r1-sec-opt-name">{s.name_1}</span>
                      <span className="r1-sec-opt-isin">{s.isin}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>

        {/* ISIN — restricted by selected security */}
        <div className="r1-filter-group">
          <label className="r1-filter-label">ISIN</label>
          <select
            className="r1-select"
            value={selectedISIN}
            disabled={!selectedSec}
            onChange={(e) => setSelectedISIN(e.target.value)}
          >
            {selectedSec ? (
              <>
                <option value="">All ISINs for this security</option>
                {selectedSec.isin && (
                  <option value={selectedSec.isin}>{selectedSec.isin}</option>
                )}
              </>
            ) : (
              <option value="">Select a security first</option>
            )}
          </select>
        </div>

        {/* AMC multi-select */}
        <div className="r1-filter-group">
          <label className="r1-filter-label">AMC</label>
          <AMCMultiSelect
            options={amcOptions}
            selected={selectedAMCs}
            onChange={setSelectedAMCs}
          />
        </div>

        {/* Fund Name */}
        <div className="r1-filter-group">
          <label className="r1-filter-label">Fund Name</label>
          <select
            className="r1-select r1-select-fund"
            value={selectedFund}
            onChange={(e) => setSelectedFund(e.target.value)}
          >
            <option value="">All Funds</option>
            {fundOptions.map((f) => (
              <option key={f} value={f}>{f}</option>
            ))}
          </select>
        </div>

        {/* Industry Rating */}
        <div className="r1-filter-group">
          <label className="r1-filter-label">Industry Rating</label>
          <select
            className="r1-select"
            value={selectedRating}
            onChange={(e) => setSelectedRating(e.target.value)}
          >
            <option value="">All Ratings</option>
            {ratingOptions.map((r) => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>
        </div>

        {/* Clear all */}
        <div className="r1-filter-group r1-clear-group">
          <button
            type="button"
            className="btn btn-outline r1-clear-btn"
            onClick={clearAll}
          >
            Clear Filters
          </button>
        </div>
      </div>

      {/* ── Security info card (shown only when a security is selected) ── */}
      {selectedSec && (
        <div className="r1-sec-card">
          <div className="r1-sec-card-primary">
            <div>
              <div className="r1-sec-card-label">Primary Name</div>
              <div className="r1-sec-card-name">{selectedSec.name_1}</div>
            </div>
            <div className="r1-isin-pill">{selectedSec.isin}</div>
          </div>
          {altNames.length > 0 && (
            <div className="r1-sec-card-alts">
              <div className="r1-sec-card-alt-label">
                Alternative names (how this security appears across different AMC filings)
              </div>
              <div className="r1-alt-chips">
                {altNames.map((n, i) => (
                  <span key={i} className="r1-alt-chip">{n}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Chart card ── */}
      <div className="r1-chart-card">
        <div className="r1-chart-hdr">
          <h2 className="r1-chart-title">Sum of Quantity by Month</h2>
          {!chartLoading && chartData.length > 0 && (
            <div className="r1-chart-meta">
              {chartData.length} month{chartData.length !== 1 ? 's' : ''}
              {selectedSec ? <> · {selectedSec.name_1}</> : <> · All Securities (Total Market Quantity)</>}
              {selectedAMCs.length > 0 && <> · {selectedAMCs.join(', ')}</>}
              {selectedFund && <> · {selectedFund}</>}
              {selectedRating && <> · {selectedRating}</>}
            </div>
          )}
        </div>

        {/* Loading */}
        {chartLoading && (
          <div className="r1-chart-state">
            <div className="r6-spinner" />
            <p>Loading chart data…</p>
          </div>
        )}

        {/* Error */}
        {!chartLoading && chartError && (
          <div className="r6-error-bar" style={{ margin: '1rem' }}>⚠️ {chartError}</div>
        )}

        {/* Empty */}
        {!chartLoading && !chartError && chartData.length === 0 && (
          <div className="r1-chart-state">
            <span className="r1-empty-icon">📭</span>
            <p style={{ fontWeight: 600, fontSize: '1.05rem', color: 'var(--foreground)' }}>
              No holding data available for the selected filters.
            </p>
            <p className="r1-empty-hint">
              Try clearing one or more AMC, Fund, or Rating filters to widen results.
            </p>
          </div>
        )}

        {/* Chart */}
        {!chartLoading && !chartError && chartData.length > 0 && (
          <ResponsiveContainer width="100%" height={500}>
            <LineChart
              data={chartData}
              margin={{ top: 40, right: 32, left: 16, bottom: 100 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="var(--border)"
                vertical={false}
              />
              <XAxis
                dataKey="portfolio_date"
                tickFormatter={fmtMonth}
                tick={{ fontSize: 9, fill: 'var(--secondary)' }}
                angle={-65}
                textAnchor="end"
                height={100}
                interval={0}
              />
              <YAxis
                tickFormatter={fmtQty}
                tick={{ fontSize: 11, fill: 'var(--secondary)' }}
                width={80}
                domain={[
                  Math.max(0, Math.floor(yMin - yPad)),
                  Math.ceil(yMax + yPad),
                ]}
              />
              <Tooltip content={<R1Tooltip />} />
              <Line
                type="monotone"
                dataKey="total_quantity"
                stroke="var(--primary)"
                strokeWidth={2.5}
                dot={{ r: 4, fill: 'var(--primary)', stroke: 'white', strokeWidth: 2 }}
                activeDot={{ r: 6, fill: 'var(--accent)', stroke: 'var(--primary)', strokeWidth: 2 }}
                isAnimationActive
                animationDuration={600}
              >
                <LabelList
                  dataKey="total_quantity"
                  content={DataLabel}
                />
              </Line>
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* ── Data Notes & Coverage Disclaimers ── */}
      <div className="r1-notes-container">
        <div className="r1-help-row">
          <span>
            💡 <strong>Holding Metric:</strong> Quantity reflects the <strong>actual total units held</strong> by all tracked mutual fund schemes in that portfolio filing. Missing months indicate the security was not reported in that period.
          </span>
        </div>

        <div className="r1-disclaimer-card">
          <div className="r1-disclaimer-header">
            <span className="r1-disclaimer-icon">ℹ️</span>
            <strong>Historical Data Coverage Notice (October 2024 Expansion)</strong>
          </div>
          <p className="r1-disclaimer-text">
            The visible surge in total holding quantity starting from <strong>October 2024</strong> is due to a major platform coverage expansion, where multiple new Asset Management Companies (AMCs) and active schemes were onboarded into our tracking database. Trend lines prior to October 2024 reflect the initial cohort of monitored fund houses.
          </p>
        </div>
      </div>

      {/* ── Report Documentation Modal ── */}
      <ReportGuideModal
        reportId="report1"
        isOpen={showGuide}
        onClose={() => setShowGuide(false)}
      />
    </div>
  );
}

export default function Report1Page() {
  return (
    <Suspense
      fallback={
        <div className="r1-page">
          <div className="r6-status-msg">
            <div className="r6-spinner" />
            <p>Loading Report 1…</p>
          </div>
        </div>
      }
    >
      <Report1Content />
    </Suspense>
  );
}
