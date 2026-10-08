'use client';

import { useState, useEffect, useCallback, useMemo, useRef, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  LabelList,
} from 'recharts';
import { supabase, getValidSession } from '@/lib/supabase';
import { getCachedSubscription, checkUserSubscription } from '@/lib/subscriptionCache';
import ReportGuideModal from '@/app/components/ReportGuideModal';

// ─── Stable Categorical Colors for AMCs ─────────────────────────────
const AMC_COLOR_MAP = {
  'HDFC Mutual Fund': '#0a4d68',
  'ICICI Prudential Mutual Fund': '#d9381e',
  'SBI MF': '#198754',
  'Nippon India Mutual Fund': '#e67e22',
  'Kotak MF': '#6f42c1',
  'AXIS': '#b02a37',
  'QUANT': '#05bfdb',
  'PPFAS Mutual Fund': '#20c997',
  'DSP Mutual Fund': '#0dcaf0',
  'ABSL': '#fd7e14',
  'JIO_BLACKROCK': '#212529',
  'Bank Of India': '#6610f2',
  'Invesco Mutual Fund': '#084298',
};

const FALLBACK_PALETTE = [
  '#0a4d68', '#05bfdb', '#d9381e', '#198754', '#e67e22',
  '#6f42c1', '#20c997', '#b02a37', '#0dcaf0', '#fd7e14',
  '#6610f2', '#084298', '#d63384', '#6c757d', '#3d5a80'
];

function getAmcColor(amcName, index = 0) {
  if (AMC_COLOR_MAP[amcName]) return AMC_COLOR_MAP[amcName];
  return FALLBACK_PALETTE[index % FALLBACK_PALETTE.length];
}

// ─── Formatting Helpers ─────────────────────────────────────────────

/** Format quantity into compact financial notation (e.g. 3.6B, 450M, 12.5K) */
function fmtCompactQty(n) {
  if (n == null || isNaN(n)) return '0';
  const val = Number(n);
  const abs = Math.abs(val);
  if (abs >= 1_000_000_000) return (val / 1_000_000_000).toFixed(2) + 'B';
  if (abs >= 1_000_000) return (val / 1_000_000).toFixed(2) + 'M';
  if (abs >= 1_000) return (val / 1_000).toFixed(1) + 'K';
  return val.toLocaleString('en-US');
}

/** Parse YYYY-MM-DD string safely in local time */
function parseLocalDate(dateStr) {
  if (!dateStr) return null;
  const [y, m, d] = String(dateStr).split('-').map(Number);
  return new Date(y, m - 1, d || 1);
}

/** Format date as "Aug-2026" */
function fmtMonthYear(dateStr) {
  const d = parseLocalDate(dateStr);
  if (!d) return dateStr;
  const mon = d.toLocaleString('en-US', { month: 'short' });
  return `${mon}-${d.getFullYear()}`;
}

/**
 * Safely compute rolling 12-calendar-month boundary strings: { startStr, endStr }
 * Given a latest portfolio_date like "2026-08-01", returns:
 * startStr: "2025-09-01" (11 calendar months before latest)
 * endStr:   "2026-08-01"
 */
function getRolling12MonthBounds(latestDateStr) {
  if (!latestDateStr) return null;
  const parts = String(latestDateStr).split('-');
  const y = Number(parts[0]);
  const m = Number(parts[1]);
  if (!y || !m || isNaN(y) || isNaN(m)) return null;

  let startY = y;
  let startM = m - 11;
  while (startM <= 0) {
    startM += 12;
    startY -= 1;
  }
  const startStr = `${startY}-${String(startM).padStart(2, '0')}-01`;
  const endStr = `${y}-${String(m).padStart(2, '0')}-01`;
  return { startStr, endStr };
}

/**
 * Generate an array of the latest 12 calendar month dates ['YYYY-MM-01', ...]
 * anchored to the global latest portfolio_date (e.g. '2026-08-01').
 * Returns exactly 12 distinct dates sorted chronologically:
 * e.g. for '2026-08-01': ['2025-09-01', '2025-10-01', ..., '2026-08-01']
 */
function get12CalendarMonths(latestDateStr) {
  if (!latestDateStr) return [];
  const parts = String(latestDateStr).split('-');
  const y = Number(parts[0]);
  const m = Number(parts[1]);
  if (!y || !m || isNaN(y) || isNaN(m)) return [];

  const months = [];
  for (let offset = 11; offset >= 0; offset--) {
    let curY = y;
    let curM = m - offset;
    while (curM <= 0) {
      curM += 12;
      curY -= 1;
    }
    while (curM > 12) {
      curM -= 12;
      curY += 1;
    }
    months.push(`${curY}-${String(curM).padStart(2, '0')}-01`);
  }
  return months;
}

// ─── Custom Data Label Component with Halo for Legibility ───────────
function R3DataLabel({ x, y, value, stroke }) {
  if (value == null || value === 0) return null;
  return (
    <g>
      {/* Background halo for crystal-clear readability over lines */}
      <text
        x={x}
        y={y - 8}
        textAnchor="middle"
        fontSize={8.5}
        fontWeight="800"
        stroke="var(--card-bg)"
        strokeWidth={3.5}
        strokeLinejoin="round"
        fill="none"
        style={{ userSelect: 'none', pointerEvents: 'none' }}
      >
        {fmtCompactQty(value)}
      </text>
      {/* Foreground label */}
      <text
        x={x}
        y={y - 8}
        textAnchor="middle"
        fontSize={8.5}
        fontWeight="700"
        fill={stroke || 'var(--foreground)'}
        style={{ userSelect: 'none', pointerEvents: 'none' }}
      >
        {fmtCompactQty(value)}
      </text>
    </g>
  );
}

// ─── Controlled Stable AMC Tooltip Panel Component ──────────────────
function R3TooltipPanel({
  data,
  isPinned,
  onClose,
  onMouseEnter,
  onMouseLeave,
}) {
  if (!data || !data.sortedPayload?.length) return null;

  return (
    <div
      className={`r3-tooltip-panel ${isPinned ? 'is-pinned' : ''}`}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
    >
      <div className="r3-tooltip-header">
        <div className="r3-tooltip-title-wrap">
          <span className="r3-tooltip-month">{fmtMonthYear(data.label)}</span>
          {isPinned ? (
            <span className="r3-tooltip-pin-badge">📌 Pinned</span>
          ) : (
            <span className="r3-tooltip-hover-badge">Click chart to pin</span>
          )}
        </div>
        <div className="r3-tooltip-header-right">
          <span className="r3-tooltip-total">
            Total: <strong>{fmtCompactQty(data.total)}</strong>
          </span>
          <button
            type="button"
            className="r3-tooltip-close-btn"
            onClick={onClose}
            title="Close details (or click/hover another month)"
            aria-label="Close"
          >
            ×
          </button>
        </div>
      </div>
      <div className="r3-tooltip-list">
        {data.sortedPayload.map((entry) => (
          <div key={entry.dataKey} className="r3-tooltip-row">
            <div className="r3-tooltip-amc">
              <span
                className="r3-tooltip-dot"
                style={{ backgroundColor: entry.color }}
              />
              <span className="r3-tooltip-name" title={entry.name}>
                {entry.name}
              </span>
            </div>
            <div className="r3-tooltip-values">
              <span className="r3-tooltip-compact">{fmtCompactQty(entry.value)}</span>
              <span className="r3-tooltip-exact">
                ({Number(entry.value).toLocaleString('en-US')})
              </span>
            </div>
          </div>
        ))}
      </div>
      <div className="r3-tooltip-footer">
        <span>{data.sortedPayload.length} holding AMCs · Scroll for more</span>
      </div>
    </div>
  );
}

// ─── Constants ──────────────────────────────────────────────────────
const SEARCH_DEBOUNCE = 300;

// ─── Main Content Inner Component ──────────────────────────────────
function Report3Content() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryISIN = searchParams ? searchParams.get('isin') : null;

  // Auth & Subscription
  const [authLoading, setAuthLoading] = useState(true);
  const [isSubscribed, setIsSubscribed] = useState(false);

  // Security Search & Selection State
  const [searchText, setSearchText] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [showSearchDrop, setShowSearchDrop] = useState(false);
  const [selectedSecurity, setSelectedSecurity] = useState(null); // { isin, name_1 }
  const [selectedISIN, setSelectedISIN] = useState('');
  const [securityInfo, setSecurityInfo] = useState(null);

  // Global Latest Reporting Month (anchor for rolling 12-calendar-month window)
  const [globalLatestDate, setGlobalLatestDate] = useState(null);
  const globalLatestDateRef = useRef(null);

  // Controlled Tooltip Panel State & Refs
  const [activeTooltipData, setActiveTooltipData] = useState(null);
  const [isTooltipPinned, setIsTooltipPinned] = useState(false);
  const isMouseOverTooltipRef = useRef(false);
  const dismissTimerRef = useRef(null);
  const chartCardRef = useRef(null);

  // Chart Data State
  const [rawTrendData, setRawTrendData] = useState([]);
  const [chartLoading, setChartLoading] = useState(false);
  const [chartError, setChartError] = useState(null);

  // Chart Display Controls
  const [isWideCanvas, setIsWideCanvas] = useState(true);
  const [showLabels, setShowLabels] = useState(true);

  // Legend Active Series Filter (allow clicking legend items to show/hide lines)
  const [hiddenAMCs, setHiddenAMCs] = useState(new Set());

  // Guide modal state
  const [showGuide, setShowGuide] = useState(false);

  // Refs
  const searchWrapRef = useRef(null);
  const searchDebounceRef = useRef(null);

  // ── 1. Auth & Subscription Verification ──────────────────────────
  useEffect(() => {
    let mounted = true;

    const checkAuth = async () => {
      try {
        const session = await getValidSession();
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
        console.error('Report 3 auth check error:', err);
        if (mounted) setAuthLoading(false);
      }
    };
    checkAuth();

    return () => {
      mounted = false;
    };
  }, [router]);

  const lastLoadedISINRef = useRef(null);

  // ── 2. Load Global Latest Reporting Date ─────────────────────────
  useEffect(() => {
    if (authLoading || !isSubscribed) return;
    let mounted = true;

    const loadGlobalLatest = async () => {
      try {
        const { data: latestRow, error: latestErr } = await supabase
          .from('fund_holdings')
          .select('portfolio_date')
          .order('portfolio_date', { ascending: false })
          .limit(1)
          .maybeSingle();

        if (!latestErr && latestRow?.portfolio_date && mounted) {
          globalLatestDateRef.current = latestRow.portfolio_date;
          setGlobalLatestDate(latestRow.portfolio_date);
          return;
        }

        const { data: meta } = await supabase.rpc('get_report5_metadata');
        if (meta?.latest_date && mounted) {
          globalLatestDateRef.current = meta.latest_date;
          setGlobalLatestDate(meta.latest_date);
        }
      } catch (err) {
        console.error('Report 3 global latest date error:', err);
      }
    };
    loadGlobalLatest();

    return () => {
      mounted = false;
    };
  }, [authLoading, isSubscribed]);

  // ── 3. Outside Click Listener (Dismiss Pinned Tooltip) ───────────
  useEffect(() => {
    if (!isTooltipPinned) return;
    const handleOutsideClick = (e) => {
      if (chartCardRef.current && !chartCardRef.current.contains(e.target)) {
        setIsTooltipPinned(false);
        setActiveTooltipData(null);
      }
    };
    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, [isTooltipPinned]);

  // ── 4. Selection & ISIN Change Handlers ───────────────────────────
  const handleSelectSecurity = useCallback((sec) => {
    setSelectedSecurity(sec);
    setSearchText(sec.name_1);
    setSelectedISIN(sec.isin); // Sets authoritative ISIN!
    setShowSearchDrop(false);
    setSearchResults([]);
  }, []);

  const handleClearSecurity = useCallback(() => {
    lastLoadedISINRef.current = null;
    setSelectedSecurity(null);
    setSearchText('');
    setSelectedISIN('');
    setSearchResults([]);
    setShowSearchDrop(false);
    setRawTrendData([]);
    setSecurityInfo(null);
    setIsTooltipPinned(false);
    setActiveTooltipData(null);
    if (dismissTimerRef.current) clearTimeout(dismissTimerRef.current);
    if (queryISIN) {
      router.replace('/report3', { scroll: false });
    }
  }, [queryISIN, router]);

  const handleISINChange = useCallback(async (val) => {
    const cleanISIN = (val || '').trim().toUpperCase();
    setSelectedISIN(cleanISIN);
    if (!cleanISIN) {
      handleClearSecurity();
      return;
    }

    // Lookup canonical name for entered ISIN
    const { data } = await supabase.rpc('lookup_security', { p_isin: cleanISIN });

    if (data && data.isin) {
      setSelectedSecurity(data);
      setSearchText(data.name_1);
    } else {
      setSelectedSecurity({ isin: cleanISIN, name_1: cleanISIN });
      setSearchText(cleanISIN);
    }
  }, [handleClearSecurity]);

  // ── 5. Auto-load from URL Query Parameter (?isin=...) ─────────────
  useEffect(() => {
    if (queryISIN && queryISIN !== lastLoadedISINRef.current) {
      lastLoadedISINRef.current = queryISIN;
      handleISINChange(queryISIN);
    }
  }, [queryISIN, handleISINChange]);

  // ── 6. Comprehensive Security Name Search ─────────────────────────
  useEffect(() => {
    if (selectedSecurity || !searchText.trim()) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSearchResults([]);
      setShowSearchDrop(false);
      return;
    }

    if (searchDebounceRef.current) clearTimeout(searchDebounceRef.current);
    searchDebounceRef.current = setTimeout(async () => {
      try {
        const { data, error: sbErr } = await supabase.rpc('search_security_master', {
          p_search: searchText.trim(),
          p_limit: 25,
        });

        if (sbErr) throw sbErr;
        setSearchResults(data || []);
        setShowSearchDrop((data?.length ?? 0) > 0);
      } catch (err) {
        console.error('Report 3 security search error:', err);
      }
    }, SEARCH_DEBOUNCE);

    return () => clearTimeout(searchDebounceRef.current);
  }, [searchText, selectedSecurity]);

  // Close typeahead when clicking outside
  useEffect(() => {
    const handler = (e) => {
      if (searchWrapRef.current && !searchWrapRef.current.contains(e.target)) {
        setShowSearchDrop(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // ── 7. Fetch AMC Holdings Trend when ISIN is Selected ────────────
  const fetchTrendData = useCallback(async (isinToFetch) => {
    if (!isinToFetch) {
      setRawTrendData([]);
      setSecurityInfo(null);
      return;
    }

    setChartLoading(true);
    setChartError(null);
    setHiddenAMCs(new Set()); // Reset legend visibility on new security
    setIsTooltipPinned(false);
    setActiveTooltipData(null);
    if (dismissTimerRef.current) clearTimeout(dismissTimerRef.current);

    try {
      // Ensure global latest reporting date is known
      if (!globalLatestDateRef.current) {
        const { data: latestRow } = await supabase
          .from('fund_holdings')
          .select('portfolio_date')
          .order('portfolio_date', { ascending: false })
          .limit(1)
          .maybeSingle();

        if (latestRow?.portfolio_date) {
          globalLatestDateRef.current = latestRow.portfolio_date;
          setGlobalLatestDate(latestRow.portfolio_date);
        } else {
          const { data: meta } = await supabase.rpc('get_report5_metadata');
          if (meta?.latest_date) {
            globalLatestDateRef.current = meta.latest_date;
            setGlobalLatestDate(meta.latest_date);
          }
        }
      }

      // 1. Fetch AMC time series
      const { data: trendData, error: trendErr } = await supabase.rpc('get_report3_amc_trend', {
        p_isin: isinToFetch,
      });

      if (trendErr) throw trendErr;
      setRawTrendData(trendData || []);

      // 2. Fetch Security Info metadata
      const { data: infoData, error: infoErr } = await supabase.rpc('get_report3_security_info', {
        p_isin: isinToFetch,
      });

      if (!infoErr && infoData) {
        setSecurityInfo(infoData);
      }
    } catch (err) {
      console.error('Report 3 trend fetch error:', err);
      setChartError(err.message || 'Failed to load AMC holding trend data.');
      setRawTrendData([]);
    } finally {
      setChartLoading(false);
    }
  }, []);

  useEffect(() => {
    if (authLoading || !isSubscribed) return;
    if (selectedISIN) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      fetchTrendData(selectedISIN);
    }
  }, [selectedISIN, authLoading, isSubscribed, fetchTrendData]);

  // ── 8. Transform Raw Data into Rolling 12 Calendar Month Series ──
  const { chartData, amcList } = useMemo(() => {
    if (!rawTrendData || rawTrendData.length === 0) {
      return { chartData: [], amcList: [] };
    }

    // Determine rolling 12-calendar-month anchor
    let anchor = globalLatestDate;
    if (!anchor) {
      for (const row of rawTrendData) {
        if (row.portfolio_date && (!anchor || row.portfolio_date > anchor)) {
          anchor = row.portfolio_date;
        }
      }
    }

    const calendarMonths = get12CalendarMonths(anchor);
    const validMonthSet = new Set(calendarMonths);

    // Set of all distinct AMCs holding this security within the 12-month window
    const amcsSet = new Set();
    // Map of date -> { portfolio_date, [amc]: quantity }
    const dateMap = new Map();

    // Pre-scaffold all 12 calendar months to guarantee both beginning & ending boundaries are anchored
    for (const mStr of calendarMonths) {
      dateMap.set(mStr, { portfolio_date: mStr });
    }

    for (const row of rawTrendData) {
      if (!row.amc || !row.portfolio_date) continue;
      if (calendarMonths.length > 0 && !validMonthSet.has(row.portfolio_date)) continue;

      amcsSet.add(row.amc);

      let point = dateMap.get(row.portfolio_date);
      if (!point) {
        point = { portfolio_date: row.portfolio_date };
        dateMap.set(row.portfolio_date, point);
      }
      point[row.amc] = Number(row.total_quantity || 0);
    }

    const formattedChartData = calendarMonths.length > 0
      ? calendarMonths.map((d) => dateMap.get(d) || { portfolio_date: d })
      : Array.from(dateMap.keys())
          .sort((a, b) => new Date(a).getTime() - new Date(b).getTime())
          .map((d) => dateMap.get(d));

    const sortedAmcList = Array.from(amcsSet).sort();

    return {
      chartData: formattedChartData,
      amcList: sortedAmcList,
    };
  }, [rawTrendData, globalLatestDate]);

  // ── 9. Tooltip Data Builder (Sorted descending by holding quantity) ─
  const buildTooltipData = useCallback((dateStr) => {
    if (!dateStr || !chartData || chartData.length === 0) return null;
    const row = chartData.find((d) => d.portfolio_date === dateStr);
    if (!row) return null;

    const validEntries = [];
    let total = 0;

    for (let i = 0; i < amcList.length; i++) {
      const amc = amcList[i];
      if (hiddenAMCs.has(amc)) continue;
      const qty = Number(row[amc]);
      if (qty != null && !isNaN(qty) && qty > 0) {
        total += qty;
        validEntries.push({
          dataKey: amc,
          name: amc,
          value: qty,
          color: getAmcColor(amc, i),
        });
      }
    }

    if (validEntries.length === 0) {
      return {
        label: dateStr,
        total: 0,
        sortedPayload: [],
      };
    }

    validEntries.sort((a, b) => b.value - a.value);

    return {
      label: dateStr,
      total,
      sortedPayload: validEntries,
    };
  }, [chartData, amcList, hiddenAMCs]);

  // ── 10. Chart Mouse & Click Handlers for Stable Tooltip Inspection ─
  const handleChartMouseMove = useCallback((state) => {
    if (dismissTimerRef.current) {
      clearTimeout(dismissTimerRef.current);
      dismissTimerRef.current = null;
    }
    if (isTooltipPinned) return; // Keep pinned month stable while user inspects

    const dateStr = state?.activeLabel || (state?.activeTooltipIndex != null ? chartData[state.activeTooltipIndex]?.portfolio_date : null);
    if (!dateStr) return;

    const tooltipInfo = buildTooltipData(dateStr);
    if (tooltipInfo && tooltipInfo.sortedPayload.length > 0) {
      setActiveTooltipData(tooltipInfo);
    }
  }, [isTooltipPinned, chartData, buildTooltipData]);

  const handleChartClick = useCallback((state) => {
    const dateStr = state?.activeLabel || (state?.activeTooltipIndex != null ? chartData[state.activeTooltipIndex]?.portfolio_date : null);
    if (!dateStr) return;

    const tooltipInfo = buildTooltipData(dateStr);
    if (tooltipInfo && tooltipInfo.sortedPayload.length > 0) {
      setActiveTooltipData(tooltipInfo);
      setIsTooltipPinned(true);
    }
  }, [chartData, buildTooltipData]);

  const handleChartMouseLeave = useCallback(() => {
    if (isTooltipPinned || isMouseOverTooltipRef.current) return;
    if (dismissTimerRef.current) clearTimeout(dismissTimerRef.current);
    dismissTimerRef.current = setTimeout(() => {
      if (!isTooltipPinned && !isMouseOverTooltipRef.current) {
        setActiveTooltipData(null);
      }
    }, 400);
  }, [isTooltipPinned]);

  const handleTooltipMouseEnter = useCallback(() => {
    isMouseOverTooltipRef.current = true;
    if (dismissTimerRef.current) {
      clearTimeout(dismissTimerRef.current);
      dismissTimerRef.current = null;
    }
  }, []);

  const handleTooltipMouseLeave = useCallback(() => {
    isMouseOverTooltipRef.current = false;
    if (!isTooltipPinned) {
      if (dismissTimerRef.current) clearTimeout(dismissTimerRef.current);
      dismissTimerRef.current = setTimeout(() => {
        if (!isTooltipPinned && !isMouseOverTooltipRef.current) {
          setActiveTooltipData(null);
        }
      }, 350);
    }
  }, [isTooltipPinned]);

  const handleCloseTooltip = useCallback(() => {
    if (dismissTimerRef.current) clearTimeout(dismissTimerRef.current);
    setIsTooltipPinned(false);
    setActiveTooltipData(null);
  }, []);

  // ── 6. Toggle AMC Visibility in Legend ───────────────────────────
  const toggleAmcVisibility = (amcName) => {
    setHiddenAMCs((prev) => {
      const next = new Set(prev);
      if (next.has(amcName)) {
        next.delete(amcName);
      } else {
        next.add(amcName);
      }
      return next;
    });
  };

  // ── Y-Axis Dynamic Bounds ────────────────────────────────────────
  const { yMin, yMax, yPad } = useMemo(() => {
    let maxVal = 0;
    for (const d of chartData) {
      for (const amc of amcList) {
        if (!hiddenAMCs.has(amc) && d[amc] != null) {
          maxVal = Math.max(maxVal, d[amc]);
        }
      }
    }
    const pad = Math.max(maxVal * 0.20, 1000);
    return { yMin: 0, yMax: maxVal, yPad: pad };
  }, [chartData, amcList, hiddenAMCs]);

  // ── Render: Loading ──────────────────────────────────────────────
  if (authLoading) {
    return (
      <div className="r3-page">
        <div className="r6-status-msg">
          <div className="r6-spinner" />
          <p>Verifying access to Report 3…</p>
        </div>
      </div>
    );
  }

  // ── Render: Not Subscribed ───────────────────────────────────────
  if (!isSubscribed) {
    return (
      <div className="r3-page">
        <div className="r6-locked-container">
          <div className="r6-locked-icon">🔒</div>
          <h1>Report 3 is Subscribers Only</h1>
          <p>
            Subscribe to Wealthyneers Premium to unlock the AMC Holding Trend report and analyze
            historical AMC-level position changes for every security in the mutual fund universe.
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

  // ── Render: Main Report 3 ────────────────────────────────────────
  return (
    <div className="r3-page">

      {/* ── Page Header ── */}
      <div className="r3-header">
        <div className="r3-badges">
          <span className="report-badge">Report 3</span>
          <button
            type="button"
            className="report-desc-btn"
            onClick={() => setShowGuide(true)}
            title="View comprehensive report documentation & guide"
            aria-label="How To Use Guide"
          >
            📖 How To Use
          </button>
          <span className="r3-live-tag">🏢 AMC Holding Trend</span>
        </div>
        <h1 className="r3-title">AMC-wise Stock Intelligence</h1>
        <p className="r3-subtitle">
          Isolate any security and track how individual mutual-fund AMCs have scaled, maintained,
          or liquidated their holdings over time. Compare accumulation timing, conviction levels, and institutional agreement.
        </p>
      </div>

      {/* ── Filter Bar: Security Name & ISIN ── */}
      <div className="r3-filter-bar">

        {/* Security Name Search (Searches all name_1 to name_20 columns) */}
        <div className="r3-filter-group r3-sec-group" ref={searchWrapRef}>
          <label className="r3-filter-label">
            Search Security Name <span className="r3-label-hint">(Searches all AMC name aliases)</span>
          </label>
          {selectedSecurity ? (
            <div className="r3-selected-chip">
              <span className="r3-chip-text">{selectedSecurity.name_1}</span>
              <button
                className="r3-chip-x"
                onClick={handleClearSecurity}
                aria-label="Remove security"
                type="button"
              >
                ×
              </button>
            </div>
          ) : (
            <div className="r3-search-wrap">
              <svg className="r3-search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <input
                type="text"
                className="r3-search-input"
                placeholder="Search stock name (e.g. ITC Ltd, KSB, HDFC Bank)…"
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
                onFocus={() => searchResults.length > 0 && setShowSearchDrop(true)}
              />
              {searchText && (
                <button
                  className="r3-search-clear"
                  type="button"
                  onClick={() => {
                    setSearchText('');
                    setSearchResults([]);
                    setShowSearchDrop(false);
                  }}
                >
                  ×
                </button>
              )}
              {showSearchDrop && (
                <ul className="r3-sec-dropdown">
                  {searchResults.map((s) => {
                    const isAliasMatch = s.matched_name && s.matched_name.toLowerCase() !== s.name_1.toLowerCase();
                    return (
                      <li
                        key={s.isin}
                        className="r3-sec-opt"
                        onMouseDown={() => handleSelectSecurity(s)}
                      >
                        <div className="r3-sec-opt-left">
                          <span className="r3-sec-opt-name">{s.name_1}</span>
                          {isAliasMatch && (
                            <span className="r3-sec-opt-alias">Matched alias: &ldquo;{s.matched_name}&rdquo;</span>
                          )}
                        </div>
                        <span className="r3-sec-opt-isin">{s.isin}</span>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          )}
        </div>

        {/* ISIN Selector / Input (Authoritative Security Identifier) */}
        <div className="r3-filter-group r3-isin-group">
          <label className="r3-filter-label">ISIN (Authoritative Key)</label>
          <div className="r3-search-wrap">
            <input
              type="text"
              className="r3-search-input r3-isin-input"
              placeholder="e.g. INE154A01025"
              value={selectedISIN}
              onChange={(e) => handleISINChange(e.target.value)}
            />
            {selectedISIN && (
              <button
                className="r3-search-clear"
                type="button"
                onClick={handleClearSecurity}
              >
                ×
              </button>
            )}
          </div>
        </div>

        {/* Clear Button */}
        <div className="r3-filter-group r3-clear-group">
          <button
            type="button"
            className="btn btn-outline r3-clear-btn"
            onClick={handleClearSecurity}
          >
            Clear
          </button>
        </div>
      </div>

      {/* ── Security Info Card (Appears once a security is selected) ── */}
      {selectedSecurity && (
        <div className="r3-info-card">
          <div className="r3-info-main">
            <div>
              <div className="r3-info-label">Canonical Security</div>
              <h2 className="r3-info-name">{securityInfo?.name_1 || selectedSecurity.name_1}</h2>
            </div>
            <div className="r3-info-pills">
              <span className="r3-isin-pill">{selectedISIN}</span>
              {securityInfo?.total_amcs > 0 && (
                <span className="r3-amc-count-pill">
                  🏢 {securityInfo.total_amcs} Active AMCs
                </span>
              )}
            </div>
          </div>

          {/* Alternative Name Aliases */}
          {securityInfo?.alt_names && securityInfo.alt_names.length > 0 && (
            <div className="r3-alt-names-wrap">
              <span className="r3-alt-label">Recognized AMC Filing Names:</span>
              <div className="r3-alt-chips">
                {securityInfo.alt_names.map((alt, idx) => (
                  <span key={idx} className="r3-alt-chip">{alt}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Line Chart Card ── */}
      <div className="r3-chart-card" ref={chartCardRef}>
        <div className="r3-chart-header">
          <div className="r3-chart-title-wrap">
            <h2 className="r3-chart-title">Sum of Quantity by Month and AMC</h2>
            <p className="r3-chart-subtitle">
              Each line represents one Asset Management Company (AMC) aggregating all underlying funds.
            </p>
          </div>

          <div className="r3-chart-controls">
            {/* Wide View Toggle */}
            <div className="r3-btn-group">
              <button
                type="button"
                className={`r3-ctrl-btn ${isWideCanvas ? 'r3-ctrl-active' : ''}`}
                onClick={() => setIsWideCanvas(true)}
                title="Expanded scrollable canvas with maximum breathing room for all 12 months"
              >
                ↔ Wide Canvas
              </button>
              <button
                type="button"
                className={`r3-ctrl-btn ${!isWideCanvas ? 'r3-ctrl-active' : ''}`}
                onClick={() => setIsWideCanvas(false)}
                title="Fit chart into screen width"
              >
                ⊡ Fit Screen
              </button>
            </div>

            {/* Data Labels Toggle */}
            <div className="r3-btn-group">
              <button
                type="button"
                className={`r3-ctrl-btn ${showLabels ? 'r3-ctrl-active' : ''}`}
                onClick={() => setShowLabels(!showLabels)}
                title="Toggle always-visible quantity values directly on chart nodes"
              >
                {showLabels ? '🏷️ Labels: ON' : '🏷️ Labels: OFF'}
              </button>
            </div>

            {selectedSecurity && amcList.length > 0 && (
              <div className="r3-chart-meta">
                <span>Last 12 Months</span> · <span>{amcList.length} AMCs</span>
              </div>
            )}
          </div>
        </div>

        {/* Controlled Stable AMC Tooltip Panel */}
        {activeTooltipData && (
          <R3TooltipPanel
            data={activeTooltipData}
            isPinned={isTooltipPinned}
            onClose={handleCloseTooltip}
            onMouseEnter={handleTooltipMouseEnter}
            onMouseLeave={handleTooltipMouseLeave}
          />
        )}

        {/* Loading State */}
        {chartLoading && (
          <div className="r3-chart-state">
            <div className="r6-spinner" />
            <p>Loading historical AMC holding lines…</p>
          </div>
        )}

        {/* Error State */}
        {!chartLoading && chartError && (
          <div className="r6-error-bar" style={{ margin: '1.5rem' }}>
            ⚠️ {chartError}
          </div>
        )}

        {/* Empty State: No Security Selected */}
        {!chartLoading && !chartError && !selectedISIN && (
          <div className="r3-chart-state">
            <span className="r3-empty-icon">🔍</span>
            <p className="r3-empty-title">Select a security to view AMC-level holding trends</p>
            <p className="r3-empty-desc">
              Search by any known security name (e.g. &ldquo;ITC Ltd&rdquo;, &ldquo;KSB Limited&rdquo;) or enter an ISIN above to generate the multi-AMC trend line chart.
            </p>
          </div>
        )}

        {/* Empty State: Security Selected but no data */}
        {!chartLoading && !chartError && selectedISIN && chartData.length === 0 && (
          <div className="r3-chart-state">
            <span className="r3-empty-icon">📭</span>
            <p className="r3-empty-title">No AMC holding data found for ISIN {selectedISIN}</p>
            <p className="r3-empty-desc">
              This security does not currently appear in mutual-fund disclosure files.
            </p>
          </div>
        )}

        {/* Main Recharts Multi-Line Chart */}
        {!chartLoading && !chartError && chartData.length > 0 && (
          <div className={`r3-chart-outer-scroll ${isWideCanvas ? 'r3-wide-scroll' : ''}`}>
            <div
              className="r3-chart-inner-canvas"
              style={{
                minWidth: isWideCanvas ? Math.max(1400, chartData.length * 110) : '100%',
                height: 780,
              }}
            >
              <ResponsiveContainer width="100%" height={780}>
                <LineChart
                  data={chartData}
                  margin={{ top: 45, right: 50, left: 30, bottom: 100 }}
                  onMouseMove={handleChartMouseMove}
                  onClick={handleChartClick}
                  onMouseLeave={handleChartMouseLeave}
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="var(--border)"
                    vertical={false}
                  />
                  <XAxis
                    dataKey="portfolio_date"
                    tickFormatter={fmtMonthYear}
                    tick={{ fontSize: 10.5, fill: 'var(--secondary)', fontWeight: 600 }}
                    angle={-55}
                    textAnchor="end"
                    height={90}
                    interval={0}
                  />
                  <YAxis
                    tickFormatter={fmtCompactQty}
                    tick={{ fontSize: 11.5, fill: 'var(--secondary)', fontWeight: 600 }}
                    width={110}
                    domain={[yMin, Math.ceil(yMax + yPad)]}
                  />
                  <Tooltip
                    cursor={{
                      stroke: 'var(--primary)',
                      strokeWidth: 1.5,
                      strokeDasharray: '4 4',
                    }}
                    content={() => null}
                  />
                  <Legend
                    verticalAlign="top"
                    align="left"
                    wrapperStyle={{ paddingBottom: '1.75rem', fontSize: '0.88rem' }}
                    onClick={(e) => toggleAmcVisibility(e.dataKey)}
                    formatter={(value) => {
                      const isHidden = hiddenAMCs.has(value);
                      return (
                        <span
                          style={{
                            color: isHidden ? 'var(--secondary)' : 'var(--foreground)',
                            textDecoration: isHidden ? 'line-through' : 'none',
                            cursor: 'pointer',
                            fontWeight: isHidden ? 'normal' : 600,
                            marginRight: '0.95rem',
                          }}
                        >
                          {value}
                        </span>
                      );
                    }}
                  />

                  {/* Render one Line per AMC */}
                  {amcList.map((amc, idx) => {
                    const color = getAmcColor(amc, idx);
                    const isHidden = hiddenAMCs.has(amc);

                    return (
                      <Line
                        key={amc}
                        type="monotone"
                        dataKey={amc}
                        name={amc}
                        stroke={color}
                        strokeWidth={2.4}
                        dot={{ r: 4, fill: color, stroke: 'white', strokeWidth: 1.5 }}
                        activeDot={{ r: 6, fill: color, stroke: 'white', strokeWidth: 2 }}
                        hide={isHidden}
                        isAnimationActive
                        animationDuration={600}
                        connectNulls={false}
                      >
                        {/* Always-visible Data Labels */}
                        {showLabels && (
                          <LabelList
                            dataKey={amc}
                            content={<R3DataLabel stroke={color} />}
                          />
                        )}
                      </Line>
                    );
                  })}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </div>

      {/* ── Research Methodology & Information Box ── */}
      <div className="r3-method-card">
        <div className="r3-method-header">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="16" x2="12" y2="12" />
            <line x1="12" y1="8" x2="12.01" y2="8" />
          </svg>
          <h3>Report 3 Analytical Guide &amp; Legend Controls</h3>
        </div>
        <div className="r3-method-grid">
          <div className="r3-method-item">
            <strong>Cross-AMC Identification:</strong> Filings from all AMCs are joined strictly by <code>ISIN</code>. Variations in reported stock names across funds (e.g. &ldquo;ITC LIMITED&rdquo; vs &ldquo;ITC Ltd&rdquo;) are unified into the canonical security.
          </div>
          <div className="r3-method-item">
            <strong>AMC Aggregation:</strong> Each colored line represents an entire AMC aggregating all constituent mutual fund schemes. It does not split into separate fund lines.
          </div>
          <div className="r3-method-item">
            <strong>Interactive Legend:</strong> Click any AMC name in the chart legend to toggle that AMC&apos;s line on or off, allowing easy visual comparison between specific fund houses.
          </div>
          <div className="r3-method-item">
            <strong>Reported Disclosures:</strong> Data points reflect actual disclosed share holdings per month. Missing data points denote months where no holdings were reported by that AMC.
          </div>
        </div>
      </div>

      {/* ── Report Documentation Modal ── */}
      <ReportGuideModal
        reportId="report3"
        isOpen={showGuide}
        onClose={() => setShowGuide(false)}
      />
    </div>
  );
}

export default function Report3Page() {
  return (
    <Suspense
      fallback={
        <div className="r3-page">
          <div className="r6-status-msg">
            <div className="r6-spinner" />
            <p>Loading Report 3…</p>
          </div>
        </div>
      }
    >
      <Report3Content />
    </Suspense>
  );
}
