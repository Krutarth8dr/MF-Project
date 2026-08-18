'use client';

import { useState, useEffect, useCallback, useRef, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { supabase } from '@/lib/supabase';
import ReportGuideModal from '@/app/components/ReportGuideModal';

// ─── Formatters & Helpers ──────────────────────────────────────────

/** Format standard date YYYY-MM-DD to "Jul 2026" */
function fmtDisplayMonth(dateStr) {
  if (!dateStr) return '—';
  const [y, m, d] = String(dateStr).split('-').map(Number);
  const date = new Date(y, m - 1, d || 1);
  if (isNaN(date.getTime())) return dateStr;
  return date.toLocaleString('en-US', { month: 'short', year: 'numeric' });
}

/** Format signed Net Buying Score (+10, +8, -2, 0) */
function fmtNetScore(score) {
  if (score == null || isNaN(score)) return '0';
  const val = Number(score);
  if (val > 0) return `+${val}`;
  return `${val}`;
}

// ─── Constants ─────────────────────────────────────────────────────
const PAGE_SIZE = 50;
const SEARCH_DEBOUNCE = 300;

// ─── Main Component Inner ──────────────────────────────────────────
function Report5Content() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryISIN = searchParams ? searchParams.get('isin') : null;

  // Auth & Subscription
  const [authLoading, setAuthLoading] = useState(true);
  const [isSubscribed, setIsSubscribed] = useState(false);

  // Metadata
  const [datesMeta, setDatesMeta] = useState({ latest_date: null, prev_date: null, total_amcs: 0 });

  // Sorting Mode
  // 'strongest_buying': Selling ASC -> Buying DESC -> Net Score DESC -> Name ASC
  // 'custom': Clicked column header
  const [isStrongestBuying, setIsStrongestBuying] = useState(true);
  const [sortCol, setSortCol] = useState('buying_count');
  const [sortDir, setSortDir] = useState('desc');

  // Filters & Presets
  const [secSearchText, setSecSearchText] = useState('');
  const [selectedSec, setSelectedSec] = useState(null); // { isin, name_1 }
  const [selectedISIN, setSelectedISIN] = useState('');
  const [presetFilter, setPresetFilter] = useState(''); // '', 'zero_selling', 'broad_consensus', 'net_positive'
  const [secTypeaheadResults, setSecTypeaheadResults] = useState([]);
  const [showSecTypeahead, setShowSecTypeahead] = useState(false);

  // Pagination
  const [page, setPage] = useState(0);

  // Guide modal state
  const [showGuide, setShowGuide] = useState(false);

  // Data & Summary States
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
    const timer = setTimeout(() => {
      if (mounted) setAuthLoading(false);
    }, 2500);

    const checkAuth = async () => {
      try {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) {
          if (mounted) router.push('/login');
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

        if (mounted) setIsSubscribed(!!active);
      } catch (err) {
        console.error('Report 5 auth check error:', err);
      } finally {
        clearTimeout(timer);
        if (mounted) setAuthLoading(false);
      }
    };
    checkAuth();

    return () => {
      mounted = false;
      clearTimeout(timer);
    };
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
      router.replace('/report5', { scroll: false });
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

  // ── 2. Load Metadata (Dates & Total AMCs) ─────────────────────────
  const loadMetadata = useCallback(async () => {
    try {
      const { data, error: sbErr } = await supabase.rpc('get_report5_metadata');
      if (sbErr) throw sbErr;

      if (data) {
        setDatesMeta({
          latest_date: data.latest_date,
          prev_date: data.prev_date,
          total_amcs: data.total_amcs || 0,
        });
      }
    } catch (err) {
      console.error('Error loading Report 5 metadata:', err);
    }
  }, []);

  useEffect(() => {
    if (authLoading || !isSubscribed) return;
    loadMetadata();
  }, [authLoading, isSubscribed, loadMetadata]);

  // ── 3. Security Name Typeahead Search (Across name_1..name_20) ───
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

  // Close typeahead on outside click
  useEffect(() => {
    const handler = (e) => {
      if (secWrapRef.current && !secWrapRef.current.contains(e.target)) {
        setShowSecTypeahead(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // ── 5. Fetch Table Ranking Data & Summary Metrics ─────────────────
  const fetchRankingData = useCallback(async () => {
    setDataLoading(true);
    setError(null);

    const effectiveISIN = selectedISIN || selectedSec?.isin || null;
    const searchParam = !selectedSec && secSearchText.trim() ? secSearchText.trim() : null;
    const presetParam = presetFilter || null;
    const sortMode = isStrongestBuying ? 'strongest_buying' : 'custom';

    try {
      // 1. Fetch Paginated Ranking Rows
      const { data, error: sbErr } = await supabase.rpc('get_report5_ranking', {
        p_search: searchParam,
        p_isin: effectiveISIN,
        p_preset: presetParam,
        p_sort_mode: sortMode,
        p_sort_col: sortCol,
        p_sort_dir: sortDir,
        p_limit: PAGE_SIZE,
        p_offset: page * PAGE_SIZE,
      });

      if (sbErr) throw sbErr;

      setRows(data || []);
      const count = data && data.length > 0 ? Number(data[0].total_count) : 0;
      setTotalCount(count);

      // 2. Fetch Summary Statistics
      setSummaryLoading(true);
      const { data: sumData, error: sumErr } = await supabase.rpc('get_report5_summary', {
        p_search: searchParam,
        p_isin: effectiveISIN,
        p_preset: presetParam,
      });

      if (!sumErr && sumData) {
        setSummary(sumData);
        if (sumData.latest_date && sumData.prev_date) {
          setDatesMeta((prev) => ({
            ...prev,
            latest_date: sumData.latest_date,
            prev_date: sumData.prev_date,
          }));
        }
      }
    } catch (err) {
      console.error('Report 5 fetch error:', err);
      setError(err.message || 'Failed to load AMC Buying Breadth ranking.');
      setRows([]);
      setTotalCount(0);
    } finally {
      setDataLoading(false);
      setSummaryLoading(false);
    }
  }, [selectedISIN, selectedSec, secSearchText, presetFilter, isStrongestBuying, sortCol, sortDir, page]);

  // Debounced fetch trigger
  useEffect(() => {
    if (authLoading || !isSubscribed) return;

    if (fetchDebounceRef.current) clearTimeout(fetchDebounceRef.current);
    fetchDebounceRef.current = setTimeout(() => {
      fetchRankingData();
    }, 200);

    return () => clearTimeout(fetchDebounceRef.current);
  }, [authLoading, isSubscribed, fetchRankingData]);

  // ── 6. Strongest Buying Toggle & Column Header Sorting ────────────
  const toggleStrongestBuying = () => {
    setIsStrongestBuying(true);
    setPage(0);
  };

  const handleCustomSort = (col) => {
    setIsStrongestBuying(false);
    if (sortCol === col) {
      setSortDir((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortCol(col);
      setSortDir(['selling_count', 'isin', 'name_1'].includes(col) ? 'asc' : 'desc');
    }
    setPage(0);
  };

  // ── 7. Reset Filters ─────────────────────────────────────────────
  const clearAllFilters = () => {
    handleClearSecurity();
    setPresetFilter('');
    setIsStrongestBuying(true);
    setSortCol('buying_count');
    setSortDir('desc');
    setPage(0);
  };

  const totalPages = Math.ceil(totalCount / PAGE_SIZE);

  // ── Render: Loading ──────────────────────────────────────────────
  if (authLoading) {
    return (
      <div className="r5-page">
        <div className="r6-status-msg">
          <div className="r6-spinner" />
          <p>Verifying access to Report 5…</p>
        </div>
      </div>
    );
  }

  // ── Render: Not Subscribed ───────────────────────────────────────
  if (!isSubscribed) {
    return (
      <div className="r5-page">
        <div className="r6-locked-container">
          <div className="r6-locked-icon">🔒</div>
          <h1>Report 5 is Subscribers Only</h1>
          <p>
            Subscribe to Wealthyneers Premium to unlock the AMC Buying Breadth ranking and discover
            high-conviction institutional accumulation with low selling pressure.
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

  // ── Render: Main Report 5 ────────────────────────────────────────
  return (
    <div className="r5-page">

      {/* ── Page Header ── */}
      <div className="r5-header">
        <div className="r5-header-top">
          <div className="r5-badges">
            <div className="report-badge-row">
              <span className="report-badge">Report 5</span>
              <button
                type="button"
                className="report-desc-btn"
                onClick={() => setShowGuide(true)}
                title="View comprehensive report documentation & guide"
              >
                📖 Report Description
              </button>
            </div>
            <span className="r5-live-tag">🔥 AMC Buying Breadth</span>
          </div>
          {datesMeta.latest_date && datesMeta.prev_date && (
            <div className="r5-period-pill" title="Dynamically determined from latest disclosures">
              <span className="r5-period-label">Comparison:</span>
              <strong>{fmtDisplayMonth(datesMeta.latest_date)}</strong>
              <span className="r5-period-vs">vs</span>
              <span>{fmtDisplayMonth(datesMeta.prev_date)}</span>
            </div>
          )}
        </div>

        <h1 className="r5-title">AMC Buying Breadth Ranking</h1>
        <p className="r5-subtitle">
          Ranks securities by institutional consensus—identifying stocks where multiple AMCs are actively
          accumulating while experiencing minimal to zero selling pressure.
        </p>
      </div>

      {/* ── Summary Statistics Cards ── */}
      <div className="r5-summary-grid">
        <div className="r5-stat-card" onClick={() => { setPresetFilter(''); setPage(0); }}>
          <div className="r5-stat-label">Securities Ranked</div>
          <div className="r5-stat-value">
            {summaryLoading ? '…' : (summary?.total_securities ?? 0).toLocaleString('en-US')}
          </div>
          <div className="r5-stat-sub">Across mutual fund universe</div>
        </div>

        <div className="r5-stat-card r5-stat-green" onClick={() => { setPresetFilter('zero_selling'); setPage(0); }}>
          <div className="r5-stat-label">🟢 Zero Selling Club</div>
          <div className="r5-stat-value">
            {summaryLoading ? '…' : (summary?.zero_selling_count ?? 0).toLocaleString('en-US')}
          </div>
          <div className="r5-stat-sub">0 selling AMCs &amp; ≥1 buying</div>
        </div>

        <div className="r5-stat-card r5-stat-gold" onClick={() => { setPresetFilter('broad_consensus'); setPage(0); }}>
          <div className="r5-stat-label">🏆 Broad Consensus</div>
          <div className="r5-stat-value">
            {summaryLoading ? '…' : (summary?.broad_consensus_count ?? 0).toLocaleString('en-US')}
          </div>
          <div className="r5-stat-sub">≥5 AMCs accumulating</div>
        </div>

        <div className="r5-stat-card r5-stat-blue" onClick={() => { setPresetFilter('net_positive'); setPage(0); }}>
          <div className="r5-stat-label">📈 Net Accumulating</div>
          <div className="r5-stat-value">
            {summaryLoading ? '…' : (summary?.net_positive_count ?? 0).toLocaleString('en-US')}
          </div>
          <div className="r5-stat-sub">Net Buying Score &gt; 0</div>
        </div>

        <div className="r5-stat-card">
          <div className="r5-stat-label">Evaluated AMCs</div>
          <div className="r5-stat-value">
            {datesMeta.total_amcs || '13+'}
          </div>
          <div className="r5-stat-sub">Distinct fund houses</div>
        </div>
      </div>

      {/* ── Filter Bar ── */}
      <div className="r5-filter-bar">

        {/* Security Name Search (Searches all name_1..name_20 aliases) */}
        <div className="r5-filter-group r5-sec-group" ref={secWrapRef}>
          <label className="r5-filter-label">Security Name (Name_1)</label>
          {selectedSec ? (
            <div className="r5-selected-chip">
              <span className="r5-chip-text">{selectedSec.name_1}</span>
              <button
                className="r5-chip-x"
                onClick={handleClearSecurity}
                aria-label="Remove security"
                type="button"
              >
                ×
              </button>
            </div>
          ) : (
            <div className="r5-search-wrap">
              <svg className="r5-search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <input
                type="text"
                className="r5-search-input"
                placeholder="Search stock name (e.g. Adani, Torrent, PB Fintech)…"
                value={secSearchText}
                onChange={(e) => {
                  setSecSearchText(e.target.value);
                  setPage(0);
                }}
                onFocus={() => secTypeaheadResults.length > 0 && setShowSecTypeahead(true)}
              />
              {secSearchText && (
                <button
                  className="r5-search-clear"
                  type="button"
                  onClick={handleClearSecurity}
                >
                  ×
                </button>
              )}
              {showSecTypeahead && (
                <ul className="r5-sec-dropdown">
                  {secTypeaheadResults.map((s) => (
                    <li
                      key={s.isin}
                      className="r5-sec-opt"
                      onMouseDown={() => handleSelectSecurity(s)}
                    >
                      <div className="r5-sec-opt-left">
                        <span className="r5-sec-opt-name">{s.name_1}</span>
                        {s.matched_name && s.matched_name.toLowerCase() !== s.name_1.toLowerCase() && (
                          <span className="r5-sec-opt-alias">Matched: &ldquo;{s.matched_name}&rdquo;</span>
                        )}
                      </div>
                      <span className="r5-sec-opt-isin">{s.isin}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>

        {/* ISIN Filter (Authoritative Key) */}
        <div className="r5-filter-group r5-isin-group">
          <label className="r5-filter-label">ISIN</label>
          <div className="r5-search-wrap">
            <input
              type="text"
              className="r5-search-input r5-isin-input"
              placeholder="e.g. INE423A01024"
              value={selectedISIN}
              onChange={(e) => handleISINChange(e.target.value)}
            />
            {selectedISIN && (
              <button
                className="r5-search-clear"
                type="button"
                onClick={() => handleISINChange('')}
              >
                ×
              </button>
            )}
          </div>
        </div>

        {/* Strongest Buying Primary Toggle */}
        <div className="r5-filter-group r5-sort-ctrl-group">
          <label className="r5-filter-label">Ranking Mode</label>
          <button
            type="button"
            className={`r5-strongest-btn ${isStrongestBuying ? 'r5-strongest-active' : ''}`}
            onClick={toggleStrongestBuying}
            title="Ranks stocks by lowest selling pressure first (0 selling, 1 selling, etc.), then by highest buying AMC count."
          >
            🔥 Strongest Buying {isStrongestBuying ? '✓' : ''}
          </button>
        </div>

        {/* Clear Filters */}
        <div className="r5-filter-group r5-clear-group">
          <button
            type="button"
            className="btn btn-outline r5-clear-btn"
            onClick={clearAllFilters}
          >
            Reset Filters
          </button>
        </div>
      </div>

      {/* ── Tabs & Sort Indicator Bar ── */}
      <div className="r5-tabs-bar">
        <div className="r5-tabs-left">
          <button
            className={`r5-tab-btn ${presetFilter === '' ? 'r5-tab-active' : ''}`}
            onClick={() => { setPresetFilter(''); setPage(0); }}
          >
            All Securities
          </button>
          <button
            className={`r5-tab-btn ${presetFilter === 'zero_selling' ? 'r5-tab-active r5-tab-green' : ''}`}
            onClick={() => { setPresetFilter('zero_selling'); setPage(0); }}
            title="Stocks with 0 selling AMCs and at least 1 buying AMC"
          >
            🟢 Zero Selling (0 Selling)
          </button>
          <button
            className={`r5-tab-btn ${presetFilter === 'broad_consensus' ? 'r5-tab-active r5-tab-gold' : ''}`}
            onClick={() => { setPresetFilter('broad_consensus'); setPage(0); }}
            title="Stocks where 5 or more AMCs are simultaneously accumulating"
          >
            🏆 Broad Consensus (5+ Buying)
          </button>
          <button
            className={`r5-tab-btn ${presetFilter === 'net_positive' ? 'r5-tab-active r5-tab-blue' : ''}`}
            onClick={() => { setPresetFilter('net_positive'); setPage(0); }}
            title="Stocks with Net Buying Score > 0"
          >
            📈 Net Accumulation
          </button>
        </div>

        <div className="r5-sort-status">
          {isStrongestBuying ? (
            <span className="r5-sort-badge r5-sort-badge-fire">
              🔥 Mode: <strong>Strongest Buying</strong> (0 Selling AMCs first → Highest Buying AMCs)
            </span>
          ) : (
            <span className="r5-sort-badge">
              Sorted by: <strong>{sortCol.replace(/_/g, ' ')}</strong> ({sortDir.toUpperCase()})
              <button
                className="r5-restore-strongest"
                onClick={toggleStrongestBuying}
                type="button"
              >
                Reset to Strongest Buying ↺
              </button>
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

      {/* ── Main Breadth Ranking Table ── */}
      <div className="r5-table-wrap">
        <table className="r5-table">
          <thead>
            <tr>
              <th className="r5-th r5-th-rank">#</th>

              <th
                className="r5-th r5-th-isin r5-th-sortable"
                onClick={() => handleCustomSort('isin')}
                title="International Securities Identification Number"
              >
                ISIN {!isStrongestBuying && sortCol === 'isin' && (sortDir === 'asc' ? '▲' : '▼')}
              </th>

              <th
                className="r5-th r5-th-name r5-th-sortable"
                onClick={() => handleCustomSort('name_1')}
                title="Primary standardized security name"
              >
                Security Name (Name_1) {!isStrongestBuying && sortCol === 'name_1' && (sortDir === 'asc' ? '▲' : '▼')}
              </th>

              <th
                className="r5-th r5-th-count r5-th-sortable r5-th-green"
                onClick={() => handleCustomSort('buying_count')}
                title="Total Buying AMC Count: Number of AMCs whose aggregate holding quantity increased from the previous month"
              >
                Buying AMCs {!isStrongestBuying && sortCol === 'buying_count' && (sortDir === 'asc' ? '▲' : '▼')}
              </th>

              <th
                className="r5-th r5-th-count r5-th-sortable r5-th-red"
                onClick={() => handleCustomSort('selling_count')}
                title="Total Selling AMC Count: Number of AMCs whose aggregate holding quantity decreased from the previous month"
              >
                Selling AMCs {!isStrongestBuying && sortCol === 'selling_count' && (sortDir === 'asc' ? '▲' : '▼')}
              </th>

              <th
                className="r5-th r5-th-net r5-th-sortable"
                onClick={() => handleCustomSort('net_buying_score')}
                title="Net Buying Score: Buying AMCs minus Selling AMCs"
              >
                Net Buying Score {!isStrongestBuying && sortCol === 'net_buying_score' && (sortDir === 'asc' ? '▲' : '▼')}
              </th>

              <th className="r5-th r5-th-actions">Explore Details</th>
            </tr>
          </thead>

          <tbody>
            {dataLoading ? (
              <tr>
                <td colSpan={7} className="r5-td-state">
                  <div className="r6-spinner" />
                  <p>Ranking securities by AMC buying breadth…</p>
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={7} className="r5-td-state">
                  <span className="r5-empty-icon">🔍</span>
                  <p>No securities match the selected criteria.</p>
                  <button type="button" className="btn btn-outline r5-empty-btn" onClick={clearAllFilters}>
                    Clear Filters
                  </button>
                </td>
              </tr>
            ) : (
              rows.map((row, idx) => {
                const rankNum = page * PAGE_SIZE + idx + 1;
                const netScore = row.net_buying_score;
                const isZeroSelling = row.selling_count === 0 && row.buying_count > 0;
                const isHighConsensus = row.buying_count >= 5;

                return (
                  <tr key={row.isin} className={`r5-tr ${isZeroSelling ? 'r5-tr-zero-selling' : ''}`}>
                    {/* Rank */}
                    <td className="r5-td r5-td-rank">
                      <span className="r5-rank-badge">{rankNum}</span>
                    </td>

                    {/* ISIN */}
                    <td className="r5-td r5-td-isin">
                      <span className="r5-isin-badge">{row.isin}</span>
                    </td>

                    {/* Security Name */}
                    <td className="r5-td r5-td-name" title={row.name_1}>
                      <div className="r5-name-wrap">
                        <span className="r5-sec-name-text">{row.name_1}</span>
                        {isZeroSelling && (
                          <span className="r5-tag-zero-selling" title="0 selling AMCs">
                            Zero Selling
                          </span>
                        )}
                        {isHighConsensus && (
                          <span className="r5-tag-consensus" title="5+ AMCs accumulating">
                            5+ AMCs
                          </span>
                        )}
                      </div>
                    </td>

                    {/* Buying AMC Count */}
                    <td
                      className="r5-td r5-td-count"
                      title={`${row.buying_count} AMCs increased their aggregate holding quantity`}
                    >
                      <span className="r5-count-pill r5-count-green">
                        🟢 {row.buying_count}
                      </span>
                    </td>

                    {/* Selling AMC Count */}
                    <td
                      className="r5-td r5-td-count"
                      title={`${row.selling_count} AMCs decreased their aggregate holding quantity`}
                    >
                      <span className={`r5-count-pill ${row.selling_count === 0 ? 'r5-count-zero' : 'r5-count-red'}`}>
                        {row.selling_count === 0 ? '0' : `🔴 ${row.selling_count}`}
                      </span>
                    </td>

                    {/* Net Buying Score */}
                    <td
                      className="r5-td r5-td-net"
                      title={`Net Buying Score = ${row.buying_count} Buying minus ${row.selling_count} Selling = ${fmtNetScore(netScore)}`}
                    >
                      <span
                        className={`r5-net-pill ${
                          netScore > 0 ? 'r5-net-positive' : netScore < 0 ? 'r5-net-negative' : 'r5-net-neutral'
                        }`}
                      >
                        {fmtNetScore(netScore)}
                      </span>
                    </td>

                    {/* Actions: Links to Report 4 and Report 3 */}
                    <td className="r5-td r5-td-actions">
                      <div className="r5-action-links">
                        <Link
                          href={`/report4?isin=${row.isin}`}
                          className="r5-action-link"
                          title={`View ${row.name_1} in Report 4 AMC Direction Matrix`}
                        >
                          Matrix 🧭
                        </Link>
                        <Link
                          href={`/report3?isin=${row.isin}`}
                          className="r5-action-link"
                          title={`View ${row.name_1} historical trend in Report 3`}
                        >
                          Trend 📈
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
        <div className="r5-pagination">
          <div className="r5-page-info">
            Showing <strong>{rows.length > 0 ? page * PAGE_SIZE + 1 : 0}–{Math.min((page + 1) * PAGE_SIZE, totalCount)}</strong> of <strong>{totalCount.toLocaleString('en-US')}</strong> securities
          </div>
          <div className="r5-page-buttons">
            <button
              className="btn btn-outline r5-page-btn"
              disabled={page === 0 || dataLoading}
              onClick={() => setPage(0)}
            >
              « First
            </button>
            <button
              className="btn btn-outline r5-page-btn"
              disabled={page === 0 || dataLoading}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
            >
              ‹ Prev
            </button>
            <button
              className="btn btn-outline r5-page-btn"
              disabled={page >= totalPages - 1 || dataLoading}
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            >
              Next ›
            </button>
            <button
              className="btn btn-outline r5-page-btn"
              disabled={page >= totalPages - 1 || dataLoading}
              onClick={() => setPage(totalPages - 1)}
            >
              Last »
            </button>
          </div>
        </div>
      )}

      {/* ── Research Methodology Card ── */}
      <div className="r5-method-card">
        <div className="r5-method-header">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="16" x2="12" y2="12" />
            <line x1="12" y1="8" x2="12.01" y2="8" />
          </svg>
          <h3>Report 5 Breadth Ranking Methodology</h3>
        </div>
        <div className="r5-method-grid">
          <div className="r5-method-item">
            <strong>Strongest Buying Priority:</strong> Stocks with 0 selling AMCs appear first, followed by stocks with 1 selling AMC, 2 selling AMCs, etc. Within each selling tier, stocks with the highest number of buying AMCs rank highest.
          </div>
          <div className="r5-method-item">
            <strong>Buying AMC Count:</strong> The number of distinct asset management companies whose combined holding across all underlying schemes increased month-over-month.
          </div>
          <div className="r5-method-item">
            <strong>Selling AMC Count:</strong> The number of distinct asset management companies whose combined holding across all underlying schemes decreased month-over-month.
          </div>
          <div className="r5-method-item">
            <strong>Net Buying Score:</strong> Calculated as (Buying AMC Count minus Selling AMC Count). Provides the directional net breadth balance for the security.
          </div>
        </div>
      </div>

      {/* ── Report Documentation Modal ── */}
      <ReportGuideModal
        reportId="report5"
        isOpen={showGuide}
        onClose={() => setShowGuide(false)}
      />
    </div>
  );
}

export default function Report5Page() {
  return (
    <Suspense
      fallback={
        <div className="r5-page">
          <div className="r6-status-msg">
            <div className="r6-spinner" />
            <p>Loading Report 5…</p>
          </div>
        </div>
      }
    >
      <Report5Content />
    </Suspense>
  );
}
