'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { supabase } from '@/lib/supabase';
import { getCachedSubscription, checkUserSubscription } from '@/lib/subscriptionCache';
import ReportGuideModal from '@/app/components/ReportGuideModal';

// ─── Formatters & Helpers ──────────────────────────────────────────

/** Format quantity into compact financial notation (e.g. 173.2M, 57.5K) */
function fmtQtyCompact(n) {
  if (n == null || isNaN(n)) return '0';
  const val = Number(n);
  const abs = Math.abs(val);
  if (abs >= 1_000_000_000) return (val / 1_000_000_000).toFixed(2) + 'B';
  if (abs >= 1_000_000) return (val / 1_000_000).toFixed(2) + 'M';
  if (abs >= 1_000) return (val / 1_000).toFixed(2) + 'K';
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

/** Format percentage (+49.62%, -18.20%, etc.) */
function fmtPct(pct, changeType) {
  if (changeType === 'NEW') return 'New';
  if (changeType === 'EXIT') return '-100.0%';
  if (pct == null || isNaN(pct)) return '—';
  const val = Number(pct);
  if (val > 0) return `+${val.toFixed(2)}%`;
  if (val < 0) return `${val.toFixed(2)}%`;
  return '0.00%';
}

/** Format standard date YYYY-MM-DD to "01 Jul 2026" or "Jul 2026" */
function fmtDisplayDate(dateStr, includeDay = true) {
  if (!dateStr) return '—';
  const [y, m, d] = String(dateStr).split('-').map(Number);
  const date = new Date(y, m - 1, d || 1);
  if (isNaN(date.getTime())) return dateStr;
  const monthName = date.toLocaleString('en-US', { month: 'short' });
  const year = date.getFullYear();
  if (!includeDay) return `${monthName} ${year}`;
  const day = String(d || 1).padStart(2, '0');
  return `${day} ${monthName} ${year}`;
}

// ─── Multi-Select AMC Dropdown ─────────────────────────────────────
function AMCMultiSelect({ options, selected, onChange }) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const ref = useRef(null);

  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const filtered = options.filter((amc) =>
    amc.toLowerCase().includes(search.toLowerCase().trim())
  );

  const toggle = (amc) => {
    onChange(
      selected.includes(amc)
        ? selected.filter((a) => a !== amc)
        : [...selected, amc]
    );
  };

  const label =
    selected.length === 0
      ? 'All AMCs'
      : selected.length === 1
      ? selected[0]
      : `${selected.length} AMCs selected`;

  return (
    <div className="r2-amc-wrap" ref={ref}>
      <button
        className="r2-amc-trigger"
        onClick={() => setOpen((o) => !o)}
        type="button"
      >
        <span className="r2-amc-label-text">{label}</span>
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {open && (
        <div className="r2-amc-panel">
          <div className="r2-amc-search-wrap">
            <input
              type="text"
              className="r2-amc-search"
              placeholder="Search AMC..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              autoFocus
            />
          </div>
          <div className="r2-amc-panel-actions">
            <button
              type="button"
              onClick={() => onChange(options)}
              className="r2-amc-action"
            >
              Select All
            </button>
            <button
              type="button"
              onClick={() => onChange([])}
              className="r2-amc-action"
            >
              Clear
            </button>
          </div>
          <ul className="r2-amc-list">
            {filtered.length === 0 ? (
              <li className="r2-amc-empty">No AMCs found</li>
            ) : (
              filtered.map((amc) => (
                <li key={amc}>
                  <label className="r2-check-row">
                    <input
                      type="checkbox"
                      checked={selected.includes(amc)}
                      onChange={() => toggle(amc)}
                    />
                    <span>{amc}</span>
                  </label>
                </li>
              ))
            )}
          </ul>
        </div>
      )}
    </div>
  );
}

// ─── Constants ─────────────────────────────────────────────────────
const PAGE_SIZE = 50;
const SEARCH_DEBOUNCE = 350;

// ─── Main Page Component ───────────────────────────────────────────
export default function Report2Page() {
  const router = useRouter();

  // Auth & Subscription
  const [authLoading, setAuthLoading] = useState(true);
  const [isSubscribed, setIsSubscribed] = useState(false);

  // Metadata & Comparison Dates
  const [datesMeta, setDatesMeta] = useState({ latest_date: null, prev_date: null });
  const [amcOptions, setAmcOptions] = useState([]);
  const [fundOptions, setFundOptions] = useState([]);

  // Active Filters
  const [selectedAMCs, setSelectedAMCs] = useState([]);
  const [selectedFund, setSelectedFund] = useState('');
  const [selectedISIN, setSelectedISIN] = useState('');
  const [secSearchText, setSecSearchText] = useState('');
  const [selectedSec, setSelectedSec] = useState(null); // { isin, name_1 }
  const [secTypeaheadResults, setSecTypeaheadResults] = useState([]);
  const [showSecTypeahead, setShowSecTypeahead] = useState(false);

  // View Mode / Quick Filter Tabs
  // 'all' | 'increases' | 'decreases' | 'new' | 'exits'
  const [viewMode, setViewMode] = useState('all');

  // Guide modal state
  const [showGuide, setShowGuide] = useState(false);

  // Sorting
  const [sortCol, setSortCol] = useState('net_change');
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

  // ── 1. Auth & Subscription Verification ──────────────────────────
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
        console.error('Report 2 auth check error:', err);
        if (mounted) setAuthLoading(false);
      }
    };
    checkAuth();

    return () => {
      mounted = false;
    };
  }, [router]);

  // ── 2. Load Dynamic Dates & Initial Filter Options ───────────────
  const loadFilterOptions = useCallback(async (amcsToFilter = []) => {
    try {
      const { data, error: sbErr } = await supabase.rpc('get_report2_filter_options', {
        p_amcs: amcsToFilter.length > 0 ? amcsToFilter : null,
      });

      if (sbErr) throw sbErr;
      if (data) {
        if (data.latest_date && data.prev_date) {
          setDatesMeta({
            latest_date: data.latest_date,
            prev_date: data.prev_date,
          });
        }
        if (Array.isArray(data.amcs) && amcsToFilter.length === 0) {
          setAmcOptions(data.amcs);
        }
        if (Array.isArray(data.funds)) {
          setFundOptions(data.funds);
        }
      }
    } catch (err) {
      console.error('Error loading Report 2 filter options:', err?.message || err);
    }
  }, []);

  useEffect(() => {
    if (authLoading || !isSubscribed) return;
    loadFilterOptions([]);
  }, [authLoading, isSubscribed, loadFilterOptions]);

  // When AMC selection changes, reload the available fund list dynamically
  useEffect(() => {
    if (authLoading || !isSubscribed) return;
    loadFilterOptions(selectedAMCs);
    // If selected fund is no longer valid for new AMC list, reset it
    setSelectedFund('');
  }, [selectedAMCs, authLoading, isSubscribed, loadFilterOptions]);

  // ── 3. Security Name (Name_1) Typeahead Search ────────────────────
  useEffect(() => {
    if (selectedSec || !secSearchText.trim()) {
      setSecTypeaheadResults([]);
      setShowSecTypeahead(false);
      return;
    }

    if (secDebounceRef.current) clearTimeout(secDebounceRef.current);
    secDebounceRef.current = setTimeout(async () => {
      try {
        const { data } = await supabase.rpc('search_security_master', {
          p_search: secSearchText.trim(),
          p_limit: 20,
        });

        setSecTypeaheadResults(data || []);
        setShowSecTypeahead((data?.length ?? 0) > 0);
      } catch (err) {
        console.error('Typeahead search error:', err);
      }
    }, SEARCH_DEBOUNCE);

    return () => clearTimeout(secDebounceRef.current);
  }, [secSearchText, selectedSec]);

  // Close security typeahead dropdown when clicking outside
  useEffect(() => {
    const handler = (e) => {
      if (secWrapRef.current && !secWrapRef.current.contains(e.target)) {
        setShowSecTypeahead(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // ── 4. Security & ISIN Selection Handlers ────────────────────────
  const handleSelectSecurity = (sec) => {
    setSelectedSec(sec);
    setSecSearchText(sec.name_1);
    setSelectedISIN(sec.isin); // Automatically cascade ISIN!
    setShowSecTypeahead(false);
    setSecTypeaheadResults([]);
    setPage(0);
  };

  const handleClearSecurity = () => {
    setSelectedSec(null);
    setSecSearchText('');
    setSelectedISIN('');
    setSecTypeaheadResults([]);
    setShowSecTypeahead(false);
    setPage(0);
  };

  const handleISINChange = async (isinVal) => {
    setSelectedISIN(isinVal);
    setPage(0);
    if (!isinVal) {
      handleClearSecurity();
      return;
    }
    // Reverse lookup: update Name_1 if user manually picks ISIN
    const { data } = await supabase.rpc('lookup_security', { p_isin: isinVal });

    if (data && data.isin) {
      setSelectedSec(data);
      setSecSearchText(data.name_1);
    }
  };

  // ── 5. Fetch Table Data & Summary Metrics ─────────────────────────
  const fetchReportData = useCallback(async () => {
    setDataLoading(true);
    setError(null);

    const effectiveISINs = selectedISIN
      ? [selectedISIN]
      : selectedSec?.isin
      ? [selectedSec.isin]
      : null;

    const amcParam = selectedAMCs.length > 0 ? selectedAMCs : null;
    const fundParam = selectedFund ? [selectedFund] : null;
    const searchParam = !selectedSec && secSearchText.trim() ? secSearchText.trim() : null;

    try {
      // 1. Fetch Paginated Rows
      const { data, error: sbErr } = await supabase.rpc('get_report2_data', {
        p_amcs: amcParam,
        p_funds: fundParam,
        p_isins: effectiveISINs,
        p_search: searchParam,
        p_view: viewMode,
        p_sort_col: sortCol,
        p_sort_dir: sortDir,
        p_limit: PAGE_SIZE,
        p_offset: page * PAGE_SIZE,
      });

      if (sbErr) throw sbErr;

      setRows(data || []);
      const count = data && data.length > 0 ? Number(data[0].total_count) : 0;
      setTotalCount(count);

      // 2. Fetch Summary Statistics (Across entire active filter universe)
      setSummaryLoading(true);
      const { data: sumData, error: sumErr } = await supabase.rpc('get_report2_summary', {
        p_amcs: amcParam,
        p_funds: fundParam,
        p_isins: effectiveISINs,
        p_search: searchParam,
      });

      if (!sumErr && sumData) {
        setSummary(sumData);
        if (sumData.latest_date && sumData.prev_date) {
          setDatesMeta({
            latest_date: sumData.latest_date,
            prev_date: sumData.prev_date,
          });
        }
      }
    } catch (err) {
      console.error('Report 2 fetch error:', err);
      setError(err.message || 'Failed to load Report 2 data.');
      setRows([]);
      setTotalCount(0);
    } finally {
      setDataLoading(false);
      setSummaryLoading(false);
    }
  }, [
    selectedAMCs,
    selectedFund,
    selectedISIN,
    selectedSec,
    secSearchText,
    viewMode,
    sortCol,
    sortDir,
    page,
  ]);

  // Debounced fetch trigger
  useEffect(() => {
    if (authLoading || !isSubscribed) return;

    if (fetchDebounceRef.current) clearTimeout(fetchDebounceRef.current);
    fetchDebounceRef.current = setTimeout(() => {
      fetchReportData();
    }, 200);

    return () => clearTimeout(fetchDebounceRef.current);
  }, [authLoading, isSubscribed, fetchReportData]);

  // ── 6. Column Sorting Handler ────────────────────────────────────
  const handleSort = (col) => {
    if (sortCol === col) {
      setSortDir((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortCol(col);
      // Default directions: quantities & % change start desc, text starts asc
      setSortDir(['isin', 'name_1'].includes(col) ? 'asc' : 'desc');
    }
    setPage(0);
  };

  // ── 7. Quick Filter Tab Click ────────────────────────────────────
  const handleViewModeChange = (mode) => {
    setViewMode(mode);
    if (mode === 'increases') {
      setSortCol('net_change');
      setSortDir('desc');
    } else if (mode === 'decreases') {
      setSortCol('net_change');
      setSortDir('asc');
    }
    setPage(0);
  };

  // ── 8. Reset All Filters ─────────────────────────────────────────
  const clearAllFilters = () => {
    setSelectedAMCs([]);
    setSelectedFund('');
    handleClearSecurity();
    setViewMode('all');
    setSortCol('net_change');
    setSortDir('desc');
    setPage(0);
  };

  const totalPages = Math.ceil(totalCount / PAGE_SIZE);

  // ── Render: Auth Loading ─────────────────────────────────────────
  if (authLoading) {
    return (
      <div className="r2-page">
        <div className="r6-status-msg">
          <div className="r6-spinner" />
          <p>Verifying access to Report 2…</p>
        </div>
      </div>
    );
  }

  // ── Render: Paywall / Not Subscribed ─────────────────────────────
  if (!isSubscribed) {
    return (
      <div className="r2-page">
        <div className="r6-locked-container">
          <div className="r6-locked-icon">🔒</div>
          <h1>Report 2 is Subscribers Only</h1>
          <p>
            Subscribe to Wealthyneers Premium to unlock the Monthly Institutional Activity
            Monitor and track institutional buying &amp; selling momentum across all AMCs.
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

  // ── Render: Main Report 2 ────────────────────────────────────────
  return (
    <div className="r2-page">

      {/* ── Page Header ── */}
      <div className="r2-header">
        <div className="r2-header-top">
          <div className="r2-badges">
            <div className="report-badge-row">
              <span className="report-badge">Report 2</span>
              <button
                type="button"
                className="report-desc-btn"
                onClick={() => setShowGuide(true)}
                title="View comprehensive report documentation & guide"
              >
                📖 Report Description
              </button>
            </div>
            <span className="r2-live-tag">⚡ Activity Scanner</span>
          </div>
          {datesMeta.latest_date && datesMeta.prev_date && (
            <div className="r2-period-pill" title="Dynamically determined from latest disclosures">
              <span className="r2-period-label">Comparison Period:</span>
              <strong>{fmtDisplayDate(datesMeta.latest_date, false)}</strong>
              <span className="r2-period-vs">vs</span>
              <span>{fmtDisplayDate(datesMeta.prev_date, false)}</span>
            </div>
          )}
        </div>

        <h1 className="r2-title">Monthly Institutional Activity Monitor</h1>
        <p className="r2-subtitle">
          Compare the latest mutual-fund portfolio snapshot with the previous month to identify
          securities experiencing the largest institutional accumulation, reduction, new entries, and exits.
        </p>
      </div>

      {/* ── Summary Statistics Cards ── */}
      <div className="r2-summary-grid">
        <div className="r2-stat-card">
          <div className="r2-stat-label">Securities Monitored</div>
          <div className="r2-stat-value">
            {summaryLoading ? '…' : (summary?.total_securities ?? 0).toLocaleString('en-US')}
          </div>
          <div className="r2-stat-sub">Across active filters</div>
        </div>

        <div className="r2-stat-card r2-stat-green" onClick={() => handleViewModeChange('increases')}>
          <div className="r2-stat-label">🟢 Accumulating (Net +)</div>
          <div className="r2-stat-value">
            {summaryLoading ? '…' : (summary?.total_increases ?? 0).toLocaleString('en-US')}
          </div>
          <div className="r2-stat-sub">Stocks with quantity increases</div>
        </div>

        <div className="r2-stat-card r2-stat-red" onClick={() => handleViewModeChange('decreases')}>
          <div className="r2-stat-label">🔴 Reducing (Net -)</div>
          <div className="r2-stat-value">
            {summaryLoading ? '…' : (summary?.total_decreases ?? 0).toLocaleString('en-US')}
          </div>
          <div className="r2-stat-sub">Stocks with quantity reductions</div>
        </div>

        <div className="r2-stat-card r2-stat-purple" onClick={() => handleViewModeChange('new')}>
          <div className="r2-stat-label">⭐ New Positions</div>
          <div className="r2-stat-value">
            {summaryLoading ? '…' : (summary?.total_new ?? 0).toLocaleString('en-US')}
          </div>
          <div className="r2-stat-sub">Entered during latest month</div>
        </div>

        <div className="r2-stat-card r2-stat-orange" onClick={() => handleViewModeChange('exits')}>
          <div className="r2-stat-label">🚪 Complete Exits</div>
          <div className="r2-stat-value">
            {summaryLoading ? '…' : (summary?.total_exits ?? 0).toLocaleString('en-US')}
          </div>
          <div className="r2-stat-sub">Quantity reduced to 0</div>
        </div>
      </div>

      {/* ── Filter Bar ── */}
      <div className="r2-filter-bar">

        {/* Security Name Typeahead (Name_1) */}
        <div className="r2-filter-group r2-sec-group" ref={secWrapRef}>
          <label className="r2-filter-label">Security Name (Name_1)</label>
          {selectedSec ? (
            <div className="r2-selected-chip">
              <span className="r2-chip-text">{selectedSec.name_1}</span>
              <button
                className="r2-chip-x"
                onClick={handleClearSecurity}
                aria-label="Remove security"
                type="button"
              >
                ×
              </button>
            </div>
          ) : (
            <div className="r2-search-wrap">
              <svg className="r2-search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <input
                type="text"
                className="r2-search-input"
                placeholder="Search stock name (e.g. KSB, Biocon)…"
                value={secSearchText}
                onChange={(e) => {
                  setSecSearchText(e.target.value);
                  setPage(0);
                }}
                onFocus={() => secTypeaheadResults.length > 0 && setShowSecTypeahead(true)}
              />
              {secSearchText && (
                <button
                  className="r2-search-clear"
                  type="button"
                  onClick={handleClearSecurity}
                >
                  ×
                </button>
              )}
              {showSecTypeahead && (
                <ul className="r2-sec-dropdown">
                  {secTypeaheadResults.map((s) => (
                    <li
                      key={s.isin}
                      className="r2-sec-opt"
                      onMouseDown={() => handleSelectSecurity(s)}
                    >
                      <span className="r2-sec-opt-name">{s.name_1}</span>
                      <span className="r2-sec-opt-isin">{s.isin}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>

        {/* ISIN Filter (Cascades with Name_1) */}
        <div className="r2-filter-group">
          <label className="r2-filter-label">ISIN</label>
          <div className="r2-search-wrap">
            <input
              type="text"
              className="r2-search-input r2-isin-input"
              placeholder="e.g. INE001B01026"
              value={selectedISIN}
              onChange={(e) => handleISINChange(e.target.value.trim().toUpperCase())}
            />
            {selectedISIN && (
              <button
                className="r2-search-clear"
                type="button"
                onClick={() => handleISINChange('')}
              >
                ×
              </button>
            )}
          </div>
        </div>

        {/* AMC Multi-Select Filter */}
        <div className="r2-filter-group">
          <label className="r2-filter-label">AMC</label>
          <AMCMultiSelect
            options={amcOptions}
            selected={selectedAMCs}
            onChange={(val) => {
              setSelectedAMCs(val);
              setPage(0);
            }}
          />
        </div>

        {/* Fund Name Filter (Dynamic based on selected AMCs) */}
        <div className="r2-filter-group">
          <label className="r2-filter-label">
            Fund Name {selectedAMCs.length > 0 && <span className="r2-label-sub">({fundOptions.length})</span>}
          </label>
          <select
            className="r2-select r2-select-fund"
            value={selectedFund}
            onChange={(e) => {
              setSelectedFund(e.target.value);
              setPage(0);
            }}
          >
            <option value="">All Funds</option>
            {fundOptions.map((f) => (
              <option key={f} value={f}>{f}</option>
            ))}
          </select>
        </div>

        {/* Clear Filters Button */}
        <div className="r2-filter-group r2-clear-group">
          <button
            type="button"
            className="btn btn-outline r2-clear-btn"
            onClick={clearAllFilters}
          >
            Clear All
          </button>
        </div>
      </div>

      {/* ── Quick Scanner Tabs (View Modes) ── */}
      <div className="r2-tabs-bar">
        <div className="r2-tabs-left">
          <button
            className={`r2-tab-btn ${viewMode === 'all' ? 'r2-tab-active' : ''}`}
            onClick={() => handleViewModeChange('all')}
          >
            All Securities
          </button>
          <button
            className={`r2-tab-btn ${viewMode === 'increases' ? 'r2-tab-active r2-tab-green' : ''}`}
            onClick={() => handleViewModeChange('increases')}
          >
            🟢 Top Accumulation
          </button>
          <button
            className={`r2-tab-btn ${viewMode === 'decreases' ? 'r2-tab-active r2-tab-red' : ''}`}
            onClick={() => handleViewModeChange('decreases')}
          >
            🔴 Top Reductions
          </button>
          <button
            className={`r2-tab-btn ${viewMode === 'new' ? 'r2-tab-active r2-tab-purple' : ''}`}
            onClick={() => handleViewModeChange('new')}
          >
            ⭐ New Positions
          </button>
          <button
            className={`r2-tab-btn ${viewMode === 'exits' ? 'r2-tab-active r2-tab-orange' : ''}`}
            onClick={() => handleViewModeChange('exits')}
          >
            🚪 Exited Positions
          </button>
        </div>

        <div className="r2-results-meta">
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

      {/* ── Main Data Table ── */}
      <div className="r2-table-wrap">
        <table className="r2-table">
          <thead>
            <tr>
              <th
                className="r2-th r2-th-isin r2-th-sortable"
                onClick={() => handleSort('isin')}
                title="International Securities Identification Number"
              >
                ISIN {sortCol === 'isin' && (sortDir === 'asc' ? '▲' : '▼')}
              </th>

              <th
                className="r2-th r2-th-name r2-th-sortable"
                onClick={() => handleSort('name_1')}
                title="Primary standardized security name"
              >
                Security Name (Name_1) {sortCol === 'name_1' && (sortDir === 'asc' ? '▲' : '▼')}
              </th>

              <th
                className="r2-th r2-th-num r2-th-sortable"
                onClick={() => handleSort('current_qty')}
                title="Total reported quantity in the latest portfolio snapshot"
              >
                Current Qty ({fmtDisplayDate(datesMeta.latest_date, false)}) {sortCol === 'current_qty' && (sortDir === 'asc' ? '▲' : '▼')}
              </th>

              <th
                className="r2-th r2-th-num r2-th-sortable"
                onClick={() => handleSort('prev_qty')}
                title="Total reported quantity in the previous portfolio snapshot"
              >
                Previous Qty ({fmtDisplayDate(datesMeta.prev_date, false)}) {sortCol === 'prev_qty' && (sortDir === 'asc' ? '▲' : '▼')}
              </th>

              <th
                className="r2-th r2-th-num r2-th-sortable"
                onClick={() => handleSort('net_change')}
                title="Current Qty minus Previous Qty"
              >
                Net Qty Change {sortCol === 'net_change' && (sortDir === 'asc' ? '▲' : '▼')}
              </th>

              <th
                className="r2-th r2-th-num r2-th-sortable"
                onClick={() => handleSort('pct_change')}
                title="Percentage change relative to previous month"
              >
                % Change {sortCol === 'pct_change' && (sortDir === 'asc' ? '▲' : '▼')}
              </th>

              <th className="r2-th r2-th-date">Latest Date</th>
              <th className="r2-th r2-th-date">Previous Date</th>
              <th className="r2-th r2-th-actions">Deep Dive</th>
            </tr>
          </thead>

          <tbody>
            {dataLoading ? (
              <tr>
                <td colSpan={9} className="r2-td-state">
                  <div className="r6-spinner" />
                  <p>Calculating institutional activity changes…</p>
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={9} className="r2-td-state">
                  <span className="r2-empty-icon">🔍</span>
                  <p>No securities match the selected filters.</p>
                  <button type="button" className="btn btn-outline r2-empty-btn" onClick={clearAllFilters}>
                    Clear Filters
                  </button>
                </td>
              </tr>
            ) : (
              rows.map((row) => {
                const isPositive = Number(row.net_change) > 0;
                const isNegative = Number(row.net_change) < 0;
                const isNew = row.change_type === 'NEW';
                const isExit = row.change_type === 'EXIT';

                return (
                  <tr key={row.isin} className="r2-tr">
                    {/* ISIN */}
                    <td className="r2-td r2-td-isin">
                      <span className="r2-isin-badge">{row.isin}</span>
                    </td>

                    {/* Security Name */}
                    <td className="r2-td r2-td-name">
                      <span className="r2-sec-name-text" title={row.name_1}>
                        {row.name_1}
                      </span>
                      {isNew && <span className="r2-status-pill r2-pill-new">NEW</span>}
                      {isExit && <span className="r2-status-pill r2-pill-exit">EXITED</span>}
                    </td>

                    {/* Current Month Qty */}
                    <td
                      className="r2-td r2-td-num"
                      title={`Exact: ${Number(row.current_qty).toLocaleString('en-US')} units`}
                    >
                      <span className="r2-qty-val">
                        {fmtQtyCompact(row.current_qty)}
                      </span>
                    </td>

                    {/* Previous Month Qty */}
                    <td
                      className="r2-td r2-td-num"
                      title={`Exact: ${Number(row.prev_qty).toLocaleString('en-US')} units`}
                    >
                      <span className="r2-qty-val">
                        {fmtQtyCompact(row.prev_qty)}
                      </span>
                    </td>

                    {/* Net Qty Change */}
                    <td
                      className={`r2-td r2-td-num r2-net-change ${
                        isPositive ? 'r2-positive' : isNegative ? 'r2-negative' : 'r2-neutral'
                      }`}
                      title={`Exact Change: ${Number(row.net_change) > 0 ? '+' : ''}${Number(row.net_change).toLocaleString('en-US')} units`}
                    >
                      <span className="r2-change-badge">
                        {fmtSignedQty(row.net_change)}
                      </span>
                    </td>

                    {/* % Change */}
                    <td className={`r2-td r2-td-num ${
                      isPositive ? 'r2-positive' : isNegative ? 'r2-negative' : 'r2-neutral'
                    }`}>
                      {isNew ? (
                        <span className="r2-pill-new-text">⭐ New</span>
                      ) : isExit ? (
                        <span className="r2-pill-exit-text">🚪 -100%</span>
                      ) : (
                        <strong>{fmtPct(row.pct_change, row.change_type)}</strong>
                      )}
                    </td>

                    {/* Latest Date */}
                    <td className="r2-td r2-td-date">
                      {fmtDisplayDate(row.latest_date)}
                    </td>

                    {/* Previous Date */}
                    <td className="r2-td r2-td-date">
                      {fmtDisplayDate(row.prev_date)}
                    </td>

                    {/* Actions: Open in Report 1 and Report 3 */}
                    <td className="r2-td r2-td-actions">
                      <div style={{ display: 'flex', gap: '0.4rem', justifyContent: 'center' }}>
                        <Link
                          href={`/report1?isin=${row.isin}`}
                          className="r2-action-link"
                          title={`View ${row.name_1} multi-year history in Report 1`}
                        >
                          History →
                        </Link>
                        <Link
                          href={`/report3?isin=${row.isin}`}
                          className="r2-action-link"
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
        <div className="r2-pagination">
          <div className="r2-page-info">
            Page <strong>{page + 1}</strong> of <strong>{totalPages}</strong> ({totalCount.toLocaleString('en-US')} records)
          </div>
          <div className="r2-page-buttons">
            <button
              className="btn btn-outline r2-page-btn"
              disabled={page === 0 || dataLoading}
              onClick={() => setPage(0)}
            >
              « First
            </button>
            <button
              className="btn btn-outline r2-page-btn"
              disabled={page === 0 || dataLoading}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
            >
              ‹ Prev
            </button>
            <button
              className="btn btn-outline r2-page-btn"
              disabled={page >= totalPages - 1 || dataLoading}
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            >
              Next ›
            </button>
            <button
              className="btn btn-outline r2-page-btn"
              disabled={page >= totalPages - 1 || dataLoading}
              onClick={() => setPage(totalPages - 1)}
            >
              Last »
            </button>
          </div>
        </div>
      )}

      {/* ── Research Methodology & Information Footer ── */}
      <div className="r2-methodology-card">
        <div className="r2-method-header">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="16" x2="12" y2="12" />
            <line x1="12" y1="8" x2="12.01" y2="8" />
          </svg>
          <h3>Report 2 Methodology &amp; Data Notes</h3>
        </div>
        <div className="r2-method-grid">
          <div className="r2-method-col">
            <strong>Current Month Qty:</strong> Total reported shares held by all matching mutual fund portfolios as of the globally latest portfolio disclosure ({fmtDisplayDate(datesMeta.latest_date)}).
          </div>
          <div className="r2-method-col">
            <strong>Previous Month Qty:</strong> Total reported shares held in the immediately preceding portfolio disclosure ({fmtDisplayDate(datesMeta.prev_date)}).
          </div>
          <div className="r2-method-col">
            <strong>New &amp; Exited Positions:</strong> Securities with zero holding in the previous month and positive holding currently are marked as <span className="r2-pill-new">NEW</span>. Positions completely liquidated to zero are marked as <span className="r2-pill-exit">EXITED</span>.
          </div>
          <div className="r2-method-col">
            <strong>Institutional Positioning:</strong> Report 2 tracks physical share volume changes from regulatory mutual fund filings. It does not measure price return or constitute an investment recommendation.
          </div>
        </div>
      </div>

      {/* ── Report Documentation Modal ── */}
      <ReportGuideModal
        reportId="report2"
        isOpen={showGuide}
        onClose={() => setShowGuide(false)}
      />
    </div>
  );
}
