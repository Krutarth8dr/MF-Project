'use client';

import { useState, useEffect, useCallback, useRef, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { supabase } from '@/lib/supabase';
import ReportGuideModal from '@/app/components/ReportGuideModal';

// ─── Formatters & Helpers ──────────────────────────────────────────

/** Format quantity into compact financial notation (e.g. 173.2M, 57.5K) */
function fmtQtyCompact(n) {
  if (n == null || isNaN(n)) return '0';
  const val = Number(n);
  const abs = Math.abs(val);
  if (abs >= 1_000_000_000) return (val / 1_000_000_000).toFixed(2) + 'B';
  if (abs >= 1_000_000) return (val / 1_000_000).toFixed(2) + 'M';
  if (abs >= 1_000) return (val / 1_000).toFixed(1) + 'K';
  return val.toLocaleString('en-US');
}

/** Format signed quantity (+57.5M, -25.3M, 0) */
function fmtSignedQty(n) {
  if (n == null || isNaN(n)) return '0';
  const val = Number(n);
  if (val > 0) return `+${fmtQtyCompact(val)}`;
  if (val < 0) return `-${fmtQtyCompact(Math.abs(val))}`;
  return '0';
}

/** Format standard date YYYY-MM-DD to "Jul 2026" */
function fmtDisplayMonth(dateStr) {
  if (!dateStr) return '—';
  const [y, m, d] = String(dateStr).split('-').map(Number);
  const date = new Date(y, m - 1, d || 1);
  if (isNaN(date.getTime())) return dateStr;
  return date.toLocaleString('en-US', { month: 'short', year: 'numeric' });
}

// ─── Direction Badge Component ─────────────────────────────────────
const DIR_CLASS = { G: 'r4-dir-g', R: 'r4-dir-r', N: 'r4-dir-n' };
const DIR_EMOJI = { G: '🟢', R: '🔴', N: '⚪' };
const DIR_TEXT  = { G: 'Buying (Increase)', R: 'Selling (Reduction)', N: 'Neutral (No Change)' };

function R4DirBadge({ dir, amc, curQty, prevQty, change }) {
  const d = dir || 'N';
  const cQty = Number(curQty ?? 0);
  const pQty = Number(prevQty ?? 0);
  const netChg = change !== undefined && change !== null ? Number(change) : (cQty - pQty);

  let changeLabel = 'No Change / Flat';
  if (d === 'G' || netChg > 0) changeLabel = 'Buying (Increased Position)';
  else if (d === 'R' || netChg < 0) changeLabel = 'Selling (Reduced Position)';
  else if (cQty === 0 && pQty === 0) changeLabel = 'No Holdings Reported';

  const tooltipText = amc
    ? `${amc}\n` +
      `Signal: ${changeLabel}\n` +
      `Latest Qty: ${fmtQtyCompact(cQty)} (${cQty.toLocaleString('en-IN')})\n` +
      `Previous Qty: ${fmtQtyCompact(pQty)} (${pQty.toLocaleString('en-IN')})\n` +
      `Net Change: ${fmtSignedQty(netChg)} (${netChg > 0 ? '+' : ''}${netChg.toLocaleString('en-IN')})`
    : DIR_TEXT[d];

  return (
    <div className={`r4-dir-cell-wrap ${DIR_CLASS[d]}`} title={tooltipText}>
      <span className="r4-dir-dot">{DIR_EMOJI[d]}</span>
    </div>
  );
}

// ─── Constants ─────────────────────────────────────────────────────
const PAGE_SIZE = 50;
const SEARCH_DEBOUNCE = 300;

// ─── Main Page Component Inner ─────────────────────────────────────
function Report4Content() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryISIN = searchParams ? searchParams.get('isin') : null;

  // Auth & Subscription
  const [authLoading, setAuthLoading] = useState(true);
  const [isSubscribed, setIsSubscribed] = useState(false);

  // Metadata & Dynamic AMC Columns
  const [datesMeta, setDatesMeta] = useState({ latest_date: null, prev_date: null });
  const [amcColumns, setAmcColumns] = useState([]);

  // Active Filters
  const [secSearchText, setSecSearchText] = useState('');
  const [selectedSec, setSelectedSec] = useState(null); // { isin, name_1 }
  const [selectedISIN, setSelectedISIN] = useState('');
  const [overallDirFilter, setOverallDirFilter] = useState(''); // '', 'G', 'R', 'N'
  const [secTypeaheadResults, setSecTypeaheadResults] = useState([]);
  const [showSecTypeahead, setShowSecTypeahead] = useState(false);

  // Sorting
  const [sortCol, setSortCol] = useState('green_count');
  const [sortDir, setSortDir] = useState('desc');

  // Pagination
  const [page, setPage] = useState(0);

  // Data & Summary State
  const [rows, setRows] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [summary, setSummary] = useState(null);
  const [dataLoading, setDataLoading] = useState(false);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [error, setError] = useState(null);

  // Refs
  const secWrapRef = useRef(null);
  const secDebounceRef = useRef(null);
  const fetchDebounceRef = useRef(null);

  // Guide modal state
  const [showGuide, setShowGuide] = useState(false);

  // ── 1. Auth & Subscription Verification ──────────────────────────
  useEffect(() => {
    const checkAuth = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) {
        router.push('/login');
        return;
      }

      const { data: subData } = await supabase
        .from('subscriptions')
        .select('payment_status, subscription_end_date')
        .eq('user_id', session.user.id)
        .eq('payment_status', 'completed')
        .order('subscription_end_date', { ascending: false })
        .limit(1)
        .maybeSingle();

      const active =
        subData &&
        (subData.subscription_end_date === null ||
          new Date(subData.subscription_end_date) > new Date());

      setIsSubscribed(!!active);
      setAuthLoading(false);
    };
    checkAuth();
  }, [router]);

  // ── 2. Selection & ISIN Change Handlers ───────────────────────────
  const handleSelectSecurity = useCallback((sec) => {
    setSelectedSec(sec);
    setSecSearchText(sec.name_1);
    setSelectedISIN(sec.isin); // Sets authoritative ISIN!
    setShowSecTypeahead(false);
    setSecTypeaheadResults([]);
    setPage(0);
  }, []);

  const lastLoadedISINRef = useRef(null);

  const handleClearSecurity = useCallback(() => {
    lastLoadedISINRef.current = null;
    setSelectedSec(null);
    setSecSearchText('');
    setSelectedISIN('');
    setSecTypeaheadResults([]);
    setShowSecTypeahead(false);
    setPage(0);
    if (queryISIN) {
      router.replace('/report4', { scroll: false });
    }
  }, [queryISIN, router]);

  const handleISINChange = useCallback(async (val) => {
    const cleanISIN = (val || '').trim().toUpperCase();
    setSelectedISIN(cleanISIN);
    setPage(0);
    if (!cleanISIN) {
      handleClearSecurity();
      return;
    }

    const { data } = await supabase.rpc('lookup_security', { p_isin: cleanISIN });

    if (data && data.isin) {
      setSelectedSec(data);
      setSecSearchText(data.name_1);
    } else {
      setSelectedSec({ isin: cleanISIN, name_1: cleanISIN });
      setSecSearchText(cleanISIN);
    }
  }, [handleClearSecurity]);

  // ── 3. Auto-load from URL Query Parameter (?isin=...) ─────────────
  useEffect(() => {
    if (queryISIN && queryISIN !== lastLoadedISINRef.current) {
      lastLoadedISINRef.current = queryISIN;
      handleISINChange(queryISIN);
    }
  }, [queryISIN, handleISINChange]);

  // ── 4. Load Metadata (Latest/Prev Dates and Dynamic AMC list) ────
  const loadMetadata = useCallback(async () => {
    try {
      const { data, error: sbErr } = await supabase.rpc('get_report4_metadata');
      if (sbErr) throw sbErr;

      if (data) {
        setDatesMeta({
          latest_date: data.latest_date,
          prev_date: data.prev_date,
        });
        if (Array.isArray(data.amcs)) {
          setAmcColumns(data.amcs);
        }
      }
    } catch (err) {
      console.error('Error loading Report 4 metadata:', err);
    }
  }, []);

  useEffect(() => {
    if (authLoading || !isSubscribed) return;
    loadMetadata();
  }, [authLoading, isSubscribed, loadMetadata]);

  // ── 5. Security Name Typeahead Search (Across all name columns) ──
  useEffect(() => {
    if (selectedSec || !secSearchText.trim()) {
      setSecTypeaheadResults([]);
      setShowSecTypeahead(false);
      return;
    }

    if (secDebounceRef.current) clearTimeout(secDebounceRef.current);
    secDebounceRef.current = setTimeout(async () => {
      try {
        const { data, error: sbErr } = await supabase.rpc('search_security_master', {
          p_search: secSearchText.trim(),
          p_limit: 20,
        });

        if (sbErr) throw sbErr;
        setSecTypeaheadResults(data || []);
        setShowSecTypeahead((data?.length ?? 0) > 0);
      } catch (err) {
        console.error('Typeahead search error:', err);
      }
    }, SEARCH_DEBOUNCE);

    return () => clearTimeout(secDebounceRef.current);
  }, [secSearchText, selectedSec]);

  // Close typeahead when clicking outside
  useEffect(() => {
    const handler = (e) => {
      if (secWrapRef.current && !secWrapRef.current.contains(e.target)) {
        setShowSecTypeahead(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // ── 6. Fetch Table Matrix Data & Summary Metrics ──────────────────
  const fetchMatrixData = useCallback(async () => {
    setDataLoading(true);
    setError(null);

    const effectiveISIN = selectedISIN || selectedSec?.isin || null;
    const searchParam = !selectedSec && secSearchText.trim() ? secSearchText.trim() : null;
    const dirParam = overallDirFilter || null;

    try {
      // 1. Fetch Paginated Matrix Rows
      const { data, error: sbErr } = await supabase.rpc('get_report4_matrix', {
        p_search: searchParam,
        p_isin: effectiveISIN,
        p_overall_dir: dirParam,
        p_sort_col: sortCol,
        p_sort_dir: sortDir,
        p_limit: PAGE_SIZE,
        p_offset: page * PAGE_SIZE,
      });

      if (sbErr) throw sbErr;

      setRows(data || []);
      const count = data && data.length > 0 ? Number(data[0].total_count) : 0;
      setTotalCount(count);

      if (data && data.length > 0 && data[0].latest_date && data[0].prev_date) {
        setDatesMeta({
          latest_date: data[0].latest_date,
          prev_date: data[0].prev_date,
        });
      }

      // 2. Fetch Summary Statistics asynchronously in background
      supabase
        .rpc('get_report4_summary', {
          p_search: searchParam,
          p_isin: effectiveISIN,
          p_overall_dir: dirParam,
        })
        .then(({ data: sumData, error: sumErr }) => {
          if (!sumErr && sumData) {
            setSummary(sumData);
            if (sumData.latest_date && sumData.prev_date) {
              setDatesMeta({
                latest_date: sumData.latest_date,
                prev_date: sumData.prev_date,
              });
            }
          }
        })
        .catch((e) => console.warn('Background summary warning:', e?.message || e));
    } catch (err) {
      console.error('Report 4 fetch error:', err?.message || err);
      setError(err?.message || 'Failed to load AMC Direction Matrix.');
      setRows([]);
      setTotalCount(0);
    } finally {
      setDataLoading(false);
      setSummaryLoading(false);
    }
  }, [selectedISIN, selectedSec, secSearchText, overallDirFilter, sortCol, sortDir, page]);

  // Debounced fetch trigger
  useEffect(() => {
    if (authLoading || !isSubscribed) return;

    if (fetchDebounceRef.current) clearTimeout(fetchDebounceRef.current);
    fetchDebounceRef.current = setTimeout(() => {
      fetchMatrixData();
    }, 200);

    return () => clearTimeout(fetchDebounceRef.current);
  }, [authLoading, isSubscribed, fetchMatrixData]);

  // ── 6. Column Sorting Handler ────────────────────────────────────
  const handleSort = (col) => {
    if (sortCol === col) {
      setSortDir((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortCol(col);
      setSortDir(['isin', 'name_1'].includes(col) ? 'asc' : 'desc');
    }
    setPage(0);
  };

  // ── 7. Reset All Filters ─────────────────────────────────────────
  const clearAllFilters = () => {
    handleClearSecurity();
    setOverallDirFilter('');
    setSortCol('green_count');
    setSortDir('desc');
    setPage(0);
  };

  const totalPages = Math.ceil(totalCount / PAGE_SIZE);

  // ── Render: Loading ──────────────────────────────────────────────
  if (authLoading) {
    return (
      <div className="r4-page">
        <div className="r6-status-msg">
          <div className="r6-spinner" />
          <p>Verifying access to Report 4…</p>
        </div>
      </div>
    );
  }

  // ── Render: Not Subscribed ───────────────────────────────────────
  if (!isSubscribed) {
    return (
      <div className="r4-page">
        <div className="r6-locked-container">
          <div className="r6-locked-icon">🔒</div>
          <h1>Report 4 is Subscribers Only</h1>
          <p>
            Subscribe to Wealthyneers Premium to unlock the AMC Direction Matrix and track
            cross-AMC accumulation, reduction, and consensus signals across the entire equity universe.
          </p>
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

  // ── Render: Main Report 4 ────────────────────────────────────────
  return (
    <div className="r4-page">

      {/* ── Page Header ── */}
      <div className="r4-header">
        <div className="r4-header-top">
          <div className="r4-badges">
            <div className="report-badge-row">
              <span className="report-badge">Report 4</span>
              <button
                type="button"
                className="report-desc-btn"
                onClick={() => setShowGuide(true)}
                title="View comprehensive report documentation & guide"
              >
                📖 Report Description
              </button>
            </div>
            <span className="r4-live-tag">🧭 AMC Direction Matrix</span>
          </div>
          {datesMeta.latest_date && datesMeta.prev_date && (
            <div className="r4-period-pill" title="Dynamically determined from latest disclosures">
              <span className="r4-period-label">Comparison:</span>
              <strong>{fmtDisplayMonth(datesMeta.latest_date)}</strong>
              <span className="r4-period-vs">vs</span>
              <span>{fmtDisplayMonth(datesMeta.prev_date)}</span>
            </div>
          )}
        </div>

        <h1 className="r4-title">AMC Direction Matrix</h1>
        <p className="r4-subtitle">
          A cross-sectional directional matrix compressing individual AMC month-over-month quantity
          changes into clear signals (🟢 Buying, 🔴 Selling, ⚪ Neutral) across every security.
        </p>
      </div>

      {/* ── Summary Statistics Cards ── */}
      <div className="r4-summary-grid">
        <div className="r4-stat-card" onClick={() => setOverallDirFilter('')}>
          <div className="r4-stat-label">Securities Evaluated</div>
          <div className="r4-stat-value">
            {summaryLoading ? '…' : (summary?.total_securities ?? 0).toLocaleString('en-US')}
          </div>
          <div className="r4-stat-sub">Across active universe</div>
        </div>

        <div className="r4-stat-card r4-stat-green" onClick={() => setOverallDirFilter('G')}>
          <div className="r4-stat-label">🟢 Overall Net Buying</div>
          <div className="r4-stat-value">
            {summaryLoading ? '…' : (summary?.green_securities ?? 0).toLocaleString('en-US')}
          </div>
          <div className="r4-stat-sub">Total aggregate qty increased</div>
        </div>

        <div className="r4-stat-card r4-stat-red" onClick={() => setOverallDirFilter('R')}>
          <div className="r4-stat-label">🔴 Overall Net Selling</div>
          <div className="r4-stat-value">
            {summaryLoading ? '…' : (summary?.red_securities ?? 0).toLocaleString('en-US')}
          </div>
          <div className="r4-stat-sub">Total aggregate qty decreased</div>
        </div>

        <div className="r4-stat-card r4-stat-neutral" onClick={() => setOverallDirFilter('N')}>
          <div className="r4-stat-label">⚪ Overall Neutral</div>
          <div className="r4-stat-value">
            {summaryLoading ? '…' : (summary?.neutral_securities ?? 0).toLocaleString('en-US')}
          </div>
          <div className="r4-stat-sub">Net quantity unchanged</div>
        </div>

        <div className="r4-stat-card">
          <div className="r4-stat-label">Evaluated AMCs</div>
          <div className="r4-stat-value">
            {amcColumns.length}
          </div>
          <div className="r4-stat-sub">Distinct asset managers</div>
        </div>
      </div>

      {/* ── Filter Bar ── */}
      <div className="r4-filter-bar">

        {/* Security Name Search (Searches all name_1..name_20 aliases) */}
        <div className="r4-filter-group r4-sec-group" ref={secWrapRef}>
          <label className="r4-filter-label">Security Name (Name_1)</label>
          {selectedSec ? (
            <div className="r4-selected-chip">
              <span className="r4-chip-text">{selectedSec.name_1}</span>
              <button
                className="r4-chip-x"
                onClick={handleClearSecurity}
                aria-label="Remove security"
                type="button"
              >
                ×
              </button>
            </div>
          ) : (
            <div className="r4-search-wrap">
              <svg className="r4-search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <input
                type="text"
                className="r4-search-input"
                placeholder="Search stock name (e.g. Adani, ITC, KSB)…"
                value={secSearchText}
                onChange={(e) => {
                  setSecSearchText(e.target.value);
                  setPage(0);
                }}
                onFocus={() => secTypeaheadResults.length > 0 && setShowSecTypeahead(true)}
              />
              {secSearchText && (
                <button
                  className="r4-search-clear"
                  type="button"
                  onClick={handleClearSecurity}
                >
                  ×
                </button>
              )}
              {showSecTypeahead && (
                <ul className="r4-sec-dropdown">
                  {secTypeaheadResults.map((s) => (
                    <li
                      key={s.isin}
                      className="r4-sec-opt"
                      onMouseDown={() => handleSelectSecurity(s)}
                    >
                      <div className="r4-sec-opt-left">
                        <span className="r4-sec-opt-name">{s.name_1}</span>
                        {s.matched_name && s.matched_name.toLowerCase() !== s.name_1.toLowerCase() && (
                          <span className="r4-sec-opt-alias">Matched: &ldquo;{s.matched_name}&rdquo;</span>
                        )}
                      </div>
                      <span className="r4-sec-opt-isin">{s.isin}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>

        {/* ISIN Filter (Authoritative Key) */}
        <div className="r4-filter-group r4-isin-group">
          <label className="r4-filter-label">ISIN</label>
          <div className="r4-search-wrap">
            <input
              type="text"
              className="r4-search-input r4-isin-input"
              placeholder="e.g. INE423A01024"
              value={selectedISIN}
              onChange={(e) => handleISINChange(e.target.value)}
            />
            {selectedISIN && (
              <button
                className="r4-search-clear"
                type="button"
                onClick={() => handleISINChange('')}
              >
                ×
              </button>
            )}
          </div>
        </div>

        {/* Overall Direction Filter */}
        <div className="r4-filter-group">
          <label className="r4-filter-label">Overall Direction</label>
          <select
            className="r4-select"
            value={overallDirFilter}
            onChange={(e) => {
              setOverallDirFilter(e.target.value);
              setPage(0);
            }}
          >
            <option value="">All Directions</option>
            <option value="G">🟢 Green (Net Buying)</option>
            <option value="R">🔴 Red (Net Selling)</option>
            <option value="N">⚪ Neutral (Unchanged)</option>
          </select>
        </div>

        {/* Clear Filters Button */}
        <div className="r4-filter-group r4-clear-group">
          <button
            type="button"
            className="btn btn-outline r4-clear-btn"
            onClick={clearAllFilters}
          >
            Clear All
          </button>
        </div>
      </div>

      {/* ── Table Bar: Quick Tabs & Meta ── */}
      <div className="r4-tabs-bar">
        <div className="r4-tabs-left">
          <button
            className={`r4-tab-btn ${overallDirFilter === '' ? 'r4-tab-active' : ''}`}
            onClick={() => { setOverallDirFilter(''); setPage(0); }}
          >
            All Securities
          </button>
          <button
            className={`r4-tab-btn ${overallDirFilter === 'G' ? 'r4-tab-active r4-tab-green' : ''}`}
            onClick={() => { setOverallDirFilter('G'); setPage(0); }}
          >
            🟢 Net Accumulation
          </button>
          <button
            className={`r4-tab-btn ${overallDirFilter === 'R' ? 'r4-tab-active r4-tab-red' : ''}`}
            onClick={() => { setOverallDirFilter('R'); setPage(0); }}
          >
            🔴 Net Reduction
          </button>
        </div>

        <div className="r4-results-meta">
          {!dataLoading && (
            <span>
              Showing <strong>{rows.length > 0 ? page * PAGE_SIZE + 1 : 0}–{Math.min((page + 1) * PAGE_SIZE, totalCount)}</strong> of <strong>{totalCount.toLocaleString('en-US')}</strong> securities
            </span>
          )}
        </div>
      </div>

      {/* ── Error Banner ── */}
      {error && (
        <div className="r6-error-bar">
          ⚠️ {error}
        </div>
      )}

      {/* ── Main AMC Direction Matrix Table ── */}
      <div className="r4-table-wrap">
        <table className="r4-table">
          <thead>
            <tr>
              <th
                className="r4-th r4-th-isin r4-th-sortable"
                onClick={() => handleSort('isin')}
                title="International Securities Identification Number"
              >
                ISIN {sortCol === 'isin' && (sortDir === 'asc' ? '▲' : '▼')}
              </th>

              <th
                className="r4-th r4-th-name r4-th-sortable"
                onClick={() => handleSort('name_1')}
                title="Primary standardized security name"
              >
                Security Name (Name_1) {sortCol === 'name_1' && (sortDir === 'asc' ? '▲' : '▼')}
              </th>

              {/* Dynamic AMC Direction Columns */}
              {amcColumns.map((amc) => (
                <th
                  key={amc}
                  className="r4-th r4-th-amc"
                  title={`${amc} Direction (Latest vs Previous Month)`}
                >
                  <span className="r4-amc-header-text">{amc}</span>
                </th>
              ))}

              {/* Summary Columns */}
              <th className="r4-th r4-th-overall" title="Overall Direction determined by Total Net Quantity Change">
                Overall
              </th>

              <th
                className="r4-th r4-th-count r4-th-sortable r4-th-green"
                onClick={() => handleSort('green_count')}
                title="Total Buying AMC Count: number of AMCs where Latest Qty > Previous Qty"
              >
                Green {sortCol === 'green_count' && (sortDir === 'asc' ? '▲' : '▼')}
              </th>

              <th
                className="r4-th r4-th-count r4-th-sortable r4-th-red"
                onClick={() => handleSort('red_count')}
                title="Total Selling AMC Count: number of AMCs where Latest Qty < Previous Qty"
              >
                Red {sortCol === 'red_count' && (sortDir === 'asc' ? '▲' : '▼')}
              </th>

              <th
                className="r4-th r4-th-count r4-th-sortable r4-th-neutral"
                onClick={() => handleSort('neutral_count')}
                title="Total Neutral AMC Count: number of AMCs with unchanged holding"
              >
                Neutral {sortCol === 'neutral_count' && (sortDir === 'asc' ? '▲' : '▼')}
              </th>

              <th className="r4-th r4-th-actions">Explore</th>
            </tr>
          </thead>

          <tbody>
            {dataLoading ? (
              <tr>
                <td colSpan={amcColumns.length + 6} className="r4-td-state">
                  <div className="r6-spinner" />
                  <p>Calculating cross-AMC directional signals…</p>
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={amcColumns.length + 6} className="r4-td-state">
                  <span className="r4-empty-icon">🔍</span>
                  <p>No securities match the selected criteria.</p>
                  <button type="button" className="btn btn-outline r4-empty-btn" onClick={clearAllFilters}>
                    Clear Filters
                  </button>
                </td>
              </tr>
            ) : (
              rows.map((row) => {
                const dirs = row.amc_directions || {};

                return (
                  <tr key={row.isin} className="r4-tr">
                    {/* ISIN */}
                    <td className="r4-td r4-td-isin">
                      <span className="r4-isin-badge">{row.isin}</span>
                    </td>

                    {/* Security Name */}
                    <td className="r4-td r4-td-name" title={row.name_1}>
                      <span className="r4-sec-name-text">{row.name_1}</span>
                    </td>

                    {/* Individual AMC Direction Cells */}
                    {amcColumns.map((amc) => {
                      const amcInfo = dirs[amc] || { dir: 'N', cur_qty: 0, prev_qty: 0, change: 0 };
                      return (
                        <td key={amc} className="r4-td r4-td-amc-cell">
                          <R4DirBadge
                            dir={amcInfo.dir}
                            amc={amc}
                            curQty={amcInfo.cur_qty}
                            prevQty={amcInfo.prev_qty}
                            change={amcInfo.change}
                          />
                        </td>
                      );
                    })}

                    {/* Overall Direction */}
                    <td className="r4-td r4-td-overall-cell">
                      <R4DirBadge
                        dir={row.overall_dir}
                        amc="Overall Direction (All AMCs Combined)"
                        curQty={row.total_cur_qty}
                        prevQty={row.total_prev_qty}
                        change={row.net_total_change}
                      />
                    </td>

                    {/* Green Count */}
                    <td className="r4-td r4-td-count r4-td-green-count" title={`${row.green_count} AMCs buying`}>
                      <span className="r4-count-pill r4-count-green">{row.green_count}</span>
                    </td>

                    {/* Red Count */}
                    <td className="r4-td r4-td-count r4-td-red-count" title={`${row.red_count} AMCs selling`}>
                      <span className="r4-count-pill r4-count-red">{row.red_count}</span>
                    </td>

                    {/* Neutral Count */}
                    <td className="r4-td r4-td-count r4-td-neutral-count" title={`${row.neutral_count} AMCs neutral`}>
                      <span className="r4-count-pill r4-count-neutral">{row.neutral_count}</span>
                    </td>

                    {/* Actions: Links to Report 1 and Report 3 */}
                    <td className="r4-td r4-td-actions">
                      <div className="r4-action-links">
                        <Link
                          href={`/report3?isin=${row.isin}`}
                          className="r4-action-link"
                          title={`View ${row.name_1} multi-AMC chart in Report 3`}
                        >
                          Trend →
                        </Link>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* ── Pagination Controls ── */}
      {totalPages > 1 && (
        <div className="r4-pagination">
          <div className="r4-page-info">
            Page <strong>{page + 1}</strong> of <strong>{totalPages}</strong> ({totalCount.toLocaleString('en-US')} records)
          </div>
          <div className="r4-page-buttons">
            <button
              className="btn btn-outline r4-page-btn"
              disabled={page === 0 || dataLoading}
              onClick={() => setPage(0)}
            >
              « First
            </button>
            <button
              className="btn btn-outline r4-page-btn"
              disabled={page === 0 || dataLoading}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
            >
              ‹ Prev
            </button>
            <button
              className="btn btn-outline r4-page-btn"
              disabled={page >= totalPages - 1 || dataLoading}
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            >
              Next ›
            </button>
            <button
              className="btn btn-outline r4-page-btn"
              disabled={page >= totalPages - 1 || dataLoading}
              onClick={() => setPage(totalPages - 1)}
            >
              Last »
            </button>
          </div>
        </div>
      )}

      {/* ── Research Methodology Card ── */}
      <div className="r4-method-card">
        <div className="r4-method-header">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="16" x2="12" y2="12" />
            <line x1="12" y1="8" x2="12.01" y2="8" />
          </svg>
          <h3>Report 4 Directional Matrix Methodology</h3>
        </div>
        <div className="r4-method-grid">
          <div className="r4-method-item">
            <strong>AMC Direction Signals:</strong> For each fund house, holding quantities across all underlying schemes are aggregated. 🟢 denotes an increase in total shares, 🔴 denotes a decrease, and ⚪ denotes no change.
          </div>
          <div className="r4-method-item">
            <strong>Overall Direction Logic:</strong> Determined strictly by aggregate net volume change (Total Latest Qty minus Total Previous Qty). It reflects true institutional capital movement rather than a mere count of green vs red boxes.
          </div>
          <div className="r4-method-item">
            <strong>Institutional Breadth (Green Count):</strong> Represents the Total Buying AMC Count—how many separate fund houses increased exposure in the latest disclosure month.
          </div>
          <div className="r4-method-item">
            <strong>Cross-AMC Identification:</strong> Grouping is strictly bound by <code>ISIN</code>. Naming variations in AMC filings are consolidated into the canonical security.
          </div>
        </div>
      </div>

      {/* ── Report Documentation Modal ── */}
      <ReportGuideModal
        reportId="report4"
        isOpen={showGuide}
        onClose={() => setShowGuide(false)}
      />
    </div>
  );
}

export default function Report4Page() {
  return (
    <Suspense
      fallback={
        <div className="r4-page">
          <div className="r6-status-msg">
            <div className="r6-spinner" />
            <p>Loading Report 4…</p>
          </div>
        </div>
      }
    >
      <Report4Content />
    </Suspense>
  );
}
