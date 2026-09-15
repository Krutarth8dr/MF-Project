'use client';

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { supabase } from '@/lib/supabase';
import { getCachedSubscription, checkUserSubscription } from '@/lib/subscriptionCache';
import ReportGuideModal from '@/app/components/ReportGuideModal';

// ─── Direction helpers ───────────────────────────────────────────────
const DIR_EMOJI = { G: '🟢', R: '🔴', N: '⚪', null: '—' };
const DIR_CLASS = { G: 'dir-g', R: 'dir-r', N: 'dir-n' };
const DIR_LABEL = { G: 'Green', R: 'Red', N: 'Neutral' };

/** Compact format for large quantities */
function fmtQtyCompact(val) {
  if (val === null || val === undefined || isNaN(val)) return '0';
  const n = Math.abs(Number(val));
  if (n >= 1e9) return (val / 1e9).toFixed(2) + 'B';
  if (n >= 1e7) return (val / 1e7).toFixed(2) + 'Cr';
  if (n >= 1e6) return (val / 1e6).toFixed(2) + 'M';
  if (n >= 1e5) return (val / 1e5).toFixed(2) + 'L';
  if (n >= 1e3) return (val / 1e3).toFixed(2) + 'K';
  return Number(val).toLocaleString('en-IN');
}

/** Formatted Month display e.g. "Jul 2026" */
function fmtMonth(dateStr) {
  if (!dateStr) return '—';
  const [y, m, d] = String(dateStr).split('-').map(Number);
  const date = new Date(y, m - 1, d || 1);
  if (isNaN(date.getTime())) return dateStr;
  return date.toLocaleString('en-US', { month: 'short', year: 'numeric' });
}

function DirBadge({ value, periodLabel, curDate, prevDate, curQty, prevQty, change }) {
  if (!value) return <span className="dir-empty">—</span>;

  const d = value || 'N';
  const cQty = Number(curQty ?? 0);
  const pQty = Number(prevQty ?? 0);
  const chg = change !== undefined && change !== null ? Number(change) : (cQty - pQty);

  let directionLabel = 'No Change / Flat';
  if (d === 'G' || chg > 0) directionLabel = '🟢 Accumulation (Quantity Increased)';
  else if (d === 'R' || chg < 0) directionLabel = '🔴 Reduction (Quantity Decreased)';
  else if (cQty === 0 && pQty === 0) directionLabel = '⚪ Sold Out / No Position';

  const sign = chg > 0 ? '+' : '';
  const tooltipText =
    `${periodLabel || 'Month Window'} Comparison\n` +
    `Period: ${fmtMonth(curDate)} vs ${fmtMonth(prevDate)}\n` +
    `Signal: ${directionLabel}\n` +
    `Current Qty (${fmtMonth(curDate)}): ${cQty.toLocaleString('en-IN')} (${fmtQtyCompact(cQty)})\n` +
    `Previous Qty (${fmtMonth(prevDate)}): ${pQty.toLocaleString('en-IN')} (${fmtQtyCompact(pQty)})\n` +
    `Net Change: ${sign}${fmtQtyCompact(chg)} (${sign}${chg.toLocaleString('en-IN')})`;

  return (
    <span
      className={`dir-badge ${DIR_CLASS[value]}`}
      title={tooltipText}
      style={{ cursor: 'pointer', display: 'inline-block' }}
    >
      {DIR_EMOJI[value]}
    </span>
  );
}

// ─── Direction filter dropdown ───────────────────────────────────────
function DirFilter({ label, value, onChange }) {
  return (
    <div className="r6-filter-group">
      <label className="r6-filter-label">{label}</label>
      <select
        className="r6-filter-select"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">All</option>
        <option value="G">🟢 Green</option>
        <option value="R">🔴 Red</option>
        <option value="N">⚪ Neutral</option>
      </select>
    </div>
  );
}

// ─── Searchable Multi-Select Dropdown Component ───────────────────────
function R6MultiSelect({
  options = [],
  selected = [],
  onChange,
  placeholder = 'Search...',
  defaultText = 'All',
  itemUnitName = 'items',
  disabled = false,
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const ref = useRef(null);

  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const filtered = useMemo(() => {
    const q = search.toLowerCase().trim();
    if (!q) return options;
    return options.filter((item) => String(item).toLowerCase().includes(q));
  }, [options, search]);

  const toggle = (item) => {
    if (selected.includes(item)) {
      onChange(selected.filter((x) => x !== item));
    } else {
      onChange([...selected, item]);
    }
  };

  const getLabelText = () => {
    if (!selected || selected.length === 0) return defaultText;
    if (selected.length === 1) return selected[0];
    if (selected.length === 2) {
      const combined = `${selected[0]}, ${selected[1]}`;
      return combined.length > 28 ? `2 ${itemUnitName} selected` : combined;
    }
    return `${selected.length} ${itemUnitName} selected`;
  };

  return (
    <div className="r6-multi-wrap" ref={ref}>
      <button
        type="button"
        disabled={disabled}
        className={`r6-multi-trigger ${selected.length > 0 ? 'has-selection' : ''}`}
        onClick={() => setOpen((o) => !o)}
        title={selected.length > 0 ? selected.join('\n') : defaultText}
      >
        <span className="r6-multi-label-text">{getLabelText()}</span>
        {selected.length > 0 && (
          <span className="r6-multi-badge">{selected.length}</span>
        )}
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {open && (
        <div className="r6-multi-panel">
          <div className="r6-multi-search-wrap">
            <input
              type="text"
              className="r6-multi-search"
              placeholder={placeholder}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              autoFocus
            />
          </div>
          <div className="r6-multi-panel-actions">
            <button
              type="button"
              className="r6-multi-action-btn"
              onClick={() => onChange(filtered.length > 0 ? Array.from(new Set([...selected, ...filtered])) : options)}
            >
              Select All
            </button>
            <button
              type="button"
              className="r6-multi-action-btn"
              onClick={() => onChange([])}
            >
              Clear
            </button>
          </div>
          <ul className="r6-multi-list">
            {filtered.length === 0 ? (
              <li className="r6-multi-empty">No matching {itemUnitName.toLowerCase()} found</li>
            ) : (
              filtered.map((item) => {
                const isChecked = selected.includes(item);
                return (
                  <li
                    key={item}
                    className="r6-multi-item"
                    onClick={() => toggle(item)}
                  >
                    <input
                      type="checkbox"
                      checked={isChecked}
                      onChange={() => {}}
                      onClick={(e) => {
                        e.stopPropagation();
                        toggle(item);
                      }}
                    />
                    <span className="r6-multi-item-text" title={item}>{item}</span>
                  </li>
                );
              })
            )}
          </ul>
        </div>
      )}
    </div>
  );
}

// ─── Page constants ──────────────────────────────────────────────────
const PAGE_SIZE = 50;
const DEBOUNCE_MS = 350;

// ─── Main component ──────────────────────────────────────────────────
export default function Report6Page() {
  const router = useRouter();

  // Auth & subscription state
  const [authLoading, setAuthLoading] = useState(true);
  const [isSubscribed, setIsSubscribed] = useState(false);

  // Filter state
  const [selectedAmcs, setSelectedAmcs] = useState([]);
  const [selectedFunds, setSelectedFunds] = useState([]);
  const [searchText, setSearchText] = useState('');
  const [dirFilters, setDirFilters] = useState({
    amc_direction: '',
    amc_2_direction: '',
    amc_3_direction: '',
    amc_4_direction: '',
    amc_5_direction: '',
    amc_6_direction: '',
    amc_7_direction: '',
  });

  // Filter options state
  const [filterOptions, setFilterOptions] = useState({
    amcs: [],
    funds: [],
    amcFundsMap: {},
  });
  const [dynamicFunds, setDynamicFunds] = useState([]);

  // Data state
  const [rows, setRows] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(0);
  const [dataLoading, setDataLoading] = useState(false);
  const [error, setError] = useState(null);

  // Debounce ref
  const debounceRef = useRef(null);

  // Guide Modal state
  const [showGuide, setShowGuide] = useState(false);

  // ── Auth check ───────────────────────────────────────────────────
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
        console.error('Report 6 auth check error:', err);
        if (mounted) setAuthLoading(false);
      }
    };
    checkAuth();

    return () => {
      mounted = false;
    };
  }, [router]);

  // ── Load filter options ──────────────────────────────────────────
  const loadFilterOptions = useCallback(async () => {
    try {
      // 1. Try dedicated get_report6_filter_options first
      const { data: r6Opts, error: r6Err } = await supabase.rpc('get_report6_filter_options');
      if (!r6Err && r6Opts) {
        setFilterOptions({
          amcs: r6Opts.amcs || [],
          funds: r6Opts.funds || [],
          amcFundsMap: r6Opts.amc_funds_map || {},
        });
        setDynamicFunds(r6Opts.funds || []);
        return;
      }

      // 2. Fallback to get_report2_filter_options if get_report6_filter_options is not yet deployed
      const { data: r2Opts, error: r2Err } = await supabase.rpc('get_report2_filter_options');
      if (!r2Err && r2Opts) {
        setFilterOptions({
          amcs: r2Opts.amcs || [],
          funds: r2Opts.funds || [],
          amcFundsMap: {},
        });
        setDynamicFunds(r2Opts.funds || []);
      }
    } catch (err) {
      console.error('Error loading Report 6 filter options:', err);
    }
  }, []);

  useEffect(() => {
    if (authLoading || !isSubscribed) return;
    loadFilterOptions();
  }, [authLoading, isSubscribed, loadFilterOptions]);

  // ── Derive dynamic funds based on selected AMCs ──────────────────
  useEffect(() => {
    let active = true;

    // If no AMC selected, show all funds
    if (selectedAmcs.length === 0) {
      setDynamicFunds(filterOptions.funds || []);
      return;
    }

    // If client-side mapping is present
    if (filterOptions.amcFundsMap && Object.keys(filterOptions.amcFundsMap).length > 0) {
      const fundSet = new Set();
      selectedAmcs.forEach((amc) => {
        const list = filterOptions.amcFundsMap[amc] || [];
        list.forEach((f) => fundSet.add(f));
      });
      const sorted = Array.from(fundSet).sort((a, b) => a.localeCompare(b));
      setDynamicFunds(sorted);
      return;
    }

    // Fallback: Query server for funds matching selected AMCs
    const fetchFundsForAmcs = async () => {
      try {
        const { data, error: rpcErr } = await supabase.rpc('get_report6_filter_options', {
          p_amcs: selectedAmcs,
        });
        if (!rpcErr && data && Array.isArray(data.funds) && active) {
          setDynamicFunds(data.funds);
        }
      } catch (err) {
        console.error('Error fetching filtered funds:', err);
      }
    };
    fetchFundsForAmcs();

    return () => {
      active = false;
    };
  }, [selectedAmcs, filterOptions]);

  // ── Prune incompatible selected funds when dynamicFunds change ────
  useEffect(() => {
    if (selectedAmcs.length === 0) return;
    setSelectedFunds((prev) => {
      if (prev.length === 0) return prev;
      const validSet = new Set(dynamicFunds);
      const filtered = prev.filter((f) => validSet.has(f));
      return filtered.length === prev.length ? prev : filtered;
    });
  }, [selectedAmcs, dynamicFunds]);

  // ── Fetch data via secure RPC with dynamic AMC & Fund filtering ──
  const fetchData = useCallback(async (currentPage, search, dirs, amcs, funds) => {
    setDataLoading(true);
    setError(null);
    try {
      const activeDirs = {};
      for (const [col, val] of Object.entries(dirs)) {
        if (val) activeDirs[col] = val;
      }

      const hasAmc = amcs && amcs.length > 0;
      const hasFund = funds && funds.length > 0;

      let params;
      if (hasAmc || hasFund) {
        // Derive effective AMCs if user selected funds directly without picking AMC
        let effectiveAmcs = hasAmc ? amcs : null;
        if (!effectiveAmcs && hasFund && filterOptions.amcFundsMap) {
          const derived = new Set();
          funds.forEach((f) => {
            for (const [amcName, fundList] of Object.entries(filterOptions.amcFundsMap)) {
              if (fundList.includes(f)) derived.add(amcName);
            }
          });
          if (derived.size > 0) effectiveAmcs = Array.from(derived);
        }

        params = {
          p_search: search.trim() || null,
          p_dirs: Object.keys(activeDirs).length > 0 ? activeDirs : null,
          p_limit: PAGE_SIZE,
          p_offset: currentPage * PAGE_SIZE,
          p_amcs: effectiveAmcs,
          p_funds: hasFund ? funds : null,
        };
      } else {
        // Default view: 4 parameters (uses fast baseline consensus)
        params = {
          p_search: search.trim() || null,
          p_dirs: Object.keys(activeDirs).length > 0 ? activeDirs : null,
          p_limit: PAGE_SIZE,
          p_offset: currentPage * PAGE_SIZE,
        };
      }

      // Call secure get_report6_data RPC
      const { data, error: rpcError } = await supabase.rpc('get_report6_data', params);

      if (rpcError) throw rpcError;

      setRows(data || []);
      const total = data && data.length > 0 ? Number(data[0].total_count) : 0;
      setTotalCount(total);
    } catch (err) {
      console.error('Report 6 fetch error:', err);
      const msg = err?.message || 'Failed to load report data.';
      if (msg.includes('schema cache') && ((amcs && amcs.length > 0) || (funds && funds.length > 0))) {
        setError('To enable multi-select AMC & Fund filtering, please execute UPDATE_REPORT6_MULTISELECT_RPC.sql in your Supabase SQL Editor.');
      } else {
        setError(msg);
      }
      setRows([]);
      setTotalCount(0);
    } finally {
      setDataLoading(false);
    }
  }, [filterOptions.amcFundsMap]);

  // ── Trigger fetch when filters or page change ────────────────────
  useEffect(() => {
    if (authLoading || !isSubscribed) return;

    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      fetchData(page, searchText, dirFilters, selectedAmcs, selectedFunds);
    }, DEBOUNCE_MS);

    return () => clearTimeout(debounceRef.current);
  }, [authLoading, isSubscribed, page, searchText, dirFilters, selectedAmcs, selectedFunds, fetchData]);

  // ── Reset page when filters change ──────────────────────────────
  const handleSearchChange = (val) => {
    setSearchText(val);
    setPage(0);
  };

  const handleDirChange = (col, val) => {
    setDirFilters((prev) => ({ ...prev, [col]: val }));
    setPage(0);
  };

  const clearAllFilters = () => {
    setSelectedAmcs([]);
    setSelectedFunds([]);
    setSearchText('');
    setDirFilters({
      amc_direction: '',
      amc_2_direction: '',
      amc_3_direction: '',
      amc_4_direction: '',
      amc_5_direction: '',
      amc_6_direction: '',
      amc_7_direction: '',
    });
    setPage(0);
  };

  const hasActiveFilters =
    selectedAmcs.length > 0 ||
    selectedFunds.length > 0 ||
    searchText.trim() !== '' ||
    Object.values(dirFilters).some(Boolean);

  const totalPages = Math.ceil(totalCount / PAGE_SIZE);

  // ── Render: loading ──────────────────────────────────────────────
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

  // ── Render: not subscribed ───────────────────────────────────────
  if (!isSubscribed) {
    return (
      <div className="r6-page">
        <div className="r6-locked-container">
          <div className="r6-locked-icon">🔒</div>
          <h1>Report 6 is Subscribers Only</h1>
          <p>
            The 7-Month Institutional Holding Direction report is available exclusively
            to Wealthyneers subscribers.
          </p>
          <Link href="/#pricing" className="btn btn-primary" style={{ marginTop: '1.5rem', display: 'inline-block' }}>
            Subscribe Now
          </Link>
          <div style={{ marginTop: '1rem' }}>
            <Link href="/dashboard" className="btn btn-outline">
              Back to Dashboard
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // ── Render: main report ──────────────────────────────────────────
  return (
    <div className="r6-page">
      {/* ── Page header ── */}
      <div className="r6-header">
        <div className="r6-header-left">
          <div className="report-badge-row">
            <span className="report-badge">Report 6</span>
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
          <h1 className="r6-title">7-Month Institutional Holding Direction</h1>
          <p className="r6-subtitle">
            Tracks the monthly quantity-change direction (increase / decrease / flat) of
            institutional holdings for each security across selected AMCs and mutual funds — over the
            latest 7 consecutive months.
          </p>
        </div>
      </div>

      {/* ── Multi-Row Filter Card ── */}
      <div className="r6-filter-card">
        {/* ROW 1: AMC | Fund Name | Security Name */}
        <div className="r6-filter-row-1">
          <div className="r6-filter-group">
            <label className="r6-filter-label">AMC</label>
            <R6MultiSelect
              options={filterOptions.amcs}
              selected={selectedAmcs}
              onChange={(newAmcs) => {
                setSelectedAmcs(newAmcs);
                setPage(0);
              }}
              placeholder="Search AMC..."
              defaultText="All AMCs"
              itemUnitName="AMCs"
            />
          </div>

          <div className="r6-filter-group">
            <label className="r6-filter-label">
              Fund Name {selectedAmcs.length > 0 ? `(${dynamicFunds.length})` : ''}
            </label>
            <R6MultiSelect
              options={dynamicFunds}
              selected={selectedFunds}
              onChange={(newFunds) => {
                setSelectedFunds(newFunds);
                setPage(0);
              }}
              placeholder="Search Fund..."
              defaultText="All Funds"
              itemUnitName="Funds"
            />
          </div>

          <div className="r6-filter-group r6-search-group">
            <label className="r6-filter-label">Security Name</label>
            <div className="r6-search-wrap">
              <svg className="r6-search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
              <input
                type="text"
                className="r6-search-input"
                placeholder="Search security or ISIN…"
                value={searchText}
                onChange={(e) => handleSearchChange(e.target.value)}
              />
              {searchText && (
                <button className="r6-search-clear" onClick={() => handleSearchChange('')}>×</button>
              )}
            </div>
          </div>
        </div>

        {/* ROW 2: 1M | 2M | 3M | 4M | 5M | 6M | 7M Directions */}
        <div className="r6-filter-row-2">
          {[
            ['1M', 'amc_direction'],
            ['2M', 'amc_2_direction'],
            ['3M', 'amc_3_direction'],
            ['4M', 'amc_4_direction'],
            ['5M', 'amc_5_direction'],
            ['6M', 'amc_6_direction'],
            ['7M', 'amc_7_direction'],
          ].map(([label, col]) => (
            <DirFilter
              key={col}
              label={`${label} Direction`}
              value={dirFilters[col]}
              onChange={(val) => handleDirChange(col, val)}
            />
          ))}
        </div>

        {/* ROW 3: Active Filter Badges & Clear Filters Action */}
        <div className="r6-filter-row-3">
          <div className="r6-active-filters-summary">
            {hasActiveFilters ? (
              <>
                <span style={{ fontWeight: 600 }}>Active Filters:</span>
                {selectedAmcs.map((amc) => (
                  <span key={amc} className="r6-active-tag">
                    AMC: {amc}
                    <button
                      type="button"
                      className="r6-active-tag-remove"
                      onClick={() => setSelectedAmcs((prev) => prev.filter((a) => a !== amc))}
                      title="Remove filter"
                    >
                      ×
                    </button>
                  </span>
                ))}
                {selectedFunds.map((fund) => (
                  <span key={fund} className="r6-active-tag">
                    Fund: {fund}
                    <button
                      type="button"
                      className="r6-active-tag-remove"
                      onClick={() => setSelectedFunds((prev) => prev.filter((f) => f !== fund))}
                      title="Remove filter"
                    >
                      ×
                    </button>
                  </span>
                ))}
                {searchText && (
                  <span className="r6-active-tag">
                    Search: &quot;{searchText}&quot;
                    <button
                      type="button"
                      className="r6-active-tag-remove"
                      onClick={() => setSearchText('')}
                      title="Clear search"
                    >
                      ×
                    </button>
                  </span>
                )}
                {Object.entries(dirFilters)
                  .filter(([, v]) => !!v)
                  .map(([col, v]) => {
                    const label = col === 'amc_direction' ? '1M' : `${col.replace('amc_', '').replace('_direction', '')}M`;
                    return (
                      <span key={col} className="r6-active-tag">
                        {label}: {DIR_EMOJI[v]} {DIR_LABEL[v]}
                        <button
                          type="button"
                          className="r6-active-tag-remove"
                          onClick={() => handleDirChange(col, '')}
                          title="Clear direction"
                        >
                          ×
                        </button>
                      </span>
                    );
                  })}
              </>
            ) : (
              <span>All AMCs &amp; funds included (full institutional universe).</span>
            )}
          </div>
          <button
            type="button"
            className="btn btn-outline r6-clear-btn"
            onClick={clearAllFilters}
          >
            Clear Filters
          </button>
        </div>
      </div>

      {/* ── Summary bar ── */}
      <div className="r6-summary-bar">
        {dataLoading ? (
          <span className="r6-summary-loading">Loading…</span>
        ) : (
          <span>
            Showing <strong>{rows.length}</strong> of <strong>{totalCount.toLocaleString()}</strong> securities
            {totalCount > 0 && ` · Page ${page + 1} of ${totalPages}`}
          </span>
        )}
      </div>

      {/* ── Error ── */}
      {error && (
        <div className="r6-error-bar">
          ⚠️ {error}
        </div>
      )}

      {/* ── Table ── */}
      <div className="r6-table-wrap">
        <table className="r6-table">
          <thead>
            <tr>
              <th className="r6-th r6-th-isin">ISIN</th>
              <th className="r6-th r6-th-name">Security</th>
              <th className="r6-th r6-th-dir" title="Latest Month Direction">1M</th>
              <th className="r6-th r6-th-dir" title="2 Months Ago">2M</th>
              <th className="r6-th r6-th-dir" title="3 Months Ago">3M</th>
              <th className="r6-th r6-th-dir" title="4 Months Ago">4M</th>
              <th className="r6-th r6-th-dir" title="5 Months Ago">5M</th>
              <th className="r6-th r6-th-dir" title="6 Months Ago">6M</th>
              <th className="r6-th r6-th-dir" title="7 Months Ago">7M</th>
              <th className="r6-th r6-th-count r6-green-header">🟢</th>
              <th className="r6-th r6-th-count r6-red-header">🔴</th>
              <th className="r6-th r6-th-count r6-neutral-header">⚪</th>
              <th className="r6-th r6-th-net">Net</th>
              <th className="r6-th" style={{ textAlign: 'center' }}>Explore</th>
            </tr>
          </thead>
          <tbody>
            {dataLoading && rows.length === 0 ? (
              <tr>
                <td colSpan={14} className="r6-td-empty">
                  <div className="r6-spinner" style={{ margin: '2rem auto' }} />
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={14} className="r6-td-empty">
                  <div className="r6-empty-state">
                    <p>No securities match the selected AMC, fund and direction filters.</p>
                    <button
                      type="button"
                      className="btn btn-outline r6-empty-clear-btn"
                      onClick={clearAllFilters}
                    >
                      Clear Filters
                    </button>
                  </div>
                </td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr key={row.isin} className="r6-tr">
                  <td className="r6-td r6-td-isin">{row.isin}</td>
                  <td className="r6-td r6-td-name">{row.security_name}</td>
                  <td className="r6-td r6-td-dir">
                    <DirBadge
                      value={row.amc_direction}
                      periodLabel="1M (Latest Month)"
                      curDate={row.m1_cur_date}
                      prevDate={row.m1_prev_date}
                      curQty={row.m1_cur_qty}
                      prevQty={row.m1_prev_qty}
                      change={row.m1_change}
                    />
                  </td>
                  <td className="r6-td r6-td-dir">
                    <DirBadge
                      value={row.amc_2_direction}
                      periodLabel="2M (2 Months Ago)"
                      curDate={row.m2_cur_date}
                      prevDate={row.m2_prev_date}
                      curQty={row.m2_cur_qty}
                      prevQty={row.m2_prev_qty}
                      change={row.m2_change}
                    />
                  </td>
                  <td className="r6-td r6-td-dir">
                    <DirBadge
                      value={row.amc_3_direction}
                      periodLabel="3M (3 Months Ago)"
                      curDate={row.m3_cur_date}
                      prevDate={row.m3_prev_date}
                      curQty={row.m3_cur_qty}
                      prevQty={row.m3_prev_qty}
                      change={row.m3_change}
                    />
                  </td>
                  <td className="r6-td r6-td-dir">
                    <DirBadge
                      value={row.amc_4_direction}
                      periodLabel="4M (4 Months Ago)"
                      curDate={row.m4_cur_date}
                      prevDate={row.m4_prev_date}
                      curQty={row.m4_cur_qty}
                      prevQty={row.m4_prev_qty}
                      change={row.m4_change}
                    />
                  </td>
                  <td className="r6-td r6-td-dir">
                    <DirBadge
                      value={row.amc_5_direction}
                      periodLabel="5M (5 Months Ago)"
                      curDate={row.m5_cur_date}
                      prevDate={row.m5_prev_date}
                      curQty={row.m5_cur_qty}
                      prevQty={row.m5_prev_qty}
                      change={row.m5_change}
                    />
                  </td>
                  <td className="r6-td r6-td-dir">
                    <DirBadge
                      value={row.amc_6_direction}
                      periodLabel="6M (6 Months Ago)"
                      curDate={row.m6_cur_date}
                      prevDate={row.m6_prev_date}
                      curQty={row.m6_cur_qty}
                      prevQty={row.m6_prev_qty}
                      change={row.m6_change}
                    />
                  </td>
                  <td className="r6-td r6-td-dir">
                    <DirBadge
                      value={row.amc_7_direction}
                      periodLabel="7M (7 Months Ago)"
                      curDate={row.m7_cur_date}
                      prevDate={row.m7_prev_date}
                      curQty={row.m7_cur_qty}
                      prevQty={row.m7_prev_qty}
                      change={row.m7_change}
                    />
                  </td>
                  <td className="r6-td r6-td-count r6-count-g">{row.amc_green_count ?? 0}</td>
                  <td className="r6-td r6-td-count r6-count-r">{row.amc_red_count ?? 0}</td>
                  <td className="r6-td r6-td-count r6-count-n">{row.amc_neutral_count ?? 0}</td>
                  <td className={`r6-td r6-td-net ${
                    row.amc_net > 0 ? 'r6-net-pos' :
                    row.amc_net < 0 ? 'r6-net-neg' : 'r6-net-zero'
                  }`}>
                    {row.amc_net > 0 ? `+${row.amc_net}` : row.amc_net}
                  </td>
                  <td className="r6-td" style={{ textAlign: 'center' }}>
                    <Link
                      href={`/report3?isin=${row.isin}`}
                      className="r5-action-link"
                      title={`View ${row.security_name} in Report 3`}
                      style={{ fontSize: '0.78rem', padding: '0.2rem 0.55rem', textDecoration: 'none' }}
                    >
                      Trend 📈
                    </Link>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* ── Pagination ── */}
      {totalPages > 1 && (
        <div className="r6-pagination">
          <button
            className="btn btn-outline r6-page-btn"
            onClick={() => setPage(0)}
            disabled={page === 0 || dataLoading}
          >
            «
          </button>
          <button
            className="btn btn-outline r6-page-btn"
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0 || dataLoading}
          >
            ‹ Prev
          </button>
          <span className="r6-page-info">
            Page {page + 1} / {totalPages}
          </span>
          <button
            className="btn btn-outline r6-page-btn"
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1 || dataLoading}
          >
            Next ›
          </button>
          <button
            className="btn btn-outline r6-page-btn"
            onClick={() => setPage(totalPages - 1)}
            disabled={page >= totalPages - 1 || dataLoading}
          >
            »
          </button>
        </div>
      )}

      {/* ── Report Documentation Modal ── */}
      <ReportGuideModal
        reportId="report6"
        isOpen={showGuide}
        onClose={() => setShowGuide(false)}
      />
    </div>
  );
}
