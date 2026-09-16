'use client';

import { useState, useEffect, useMemo, useId } from 'react';

export default function AMCFundCoverage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [expandedAmcs, setExpandedAmcs] = useState({});
  const searchInputId = useId();

  useEffect(() => {
    let mounted = true;

    async function fetchCoverage() {
      try {
        setLoading(true);
        const res = await fetch('/api/coverage');
        if (!res.ok) throw new Error('Coverage fetch failed');
        const json = await res.json();
        if (mounted) {
          setData(json);
          setError(false);
        }
      } catch (err) {
        console.warn('Coverage loading error:', err);
        if (mounted) setError(true);
      } finally {
        if (mounted) setLoading(false);
      }
    }

    fetchCoverage();

    return () => {
      mounted = false;
    };
  }, []);

  const amcList = useMemo(() => {
    if (!data?.amcs) return [];
    return [...data.amcs].sort((a, b) => a.localeCompare(b));
  }, [data]);

  const amcFundsMap = useMemo(() => {
    return data?.amcFundsMap || {};
  }, [data]);

  // Search filtering matching AMC names OR Fund names
  const filteredData = useMemo(() => {
    const q = searchTerm.trim().toLowerCase();
    if (!q) {
      return {
        matchedAmcs: amcList,
        amcFundFilteredMap: amcFundsMap,
        totalMatchedFunds: data?.fundCount || 0,
      };
    }

    const matchedAmcs = [];
    const amcFundFilteredMap = {};
    let totalMatchedFunds = 0;

    amcList.forEach((amc) => {
      const amcMatches = amc.toLowerCase().includes(q);
      const funds = amcFundsMap[amc] || [];
      const matchedFunds = amcMatches
        ? funds
        : funds.filter((f) => f.toLowerCase().includes(q));

      if (amcMatches || matchedFunds.length > 0) {
        matchedAmcs.push(amc);
        amcFundFilteredMap[amc] = matchedFunds;
        totalMatchedFunds += matchedFunds.length;
      }
    });

    return {
      matchedAmcs,
      amcFundFilteredMap,
      totalMatchedFunds,
    };
  }, [amcList, amcFundsMap, searchTerm, data]);

  // Auto-expand matched AMCs during search
  useEffect(() => {
    if (searchTerm.trim().length > 0) {
      const autoExp = {};
      filteredData.matchedAmcs.forEach((amc) => {
        autoExp[amc] = true;
      });
      setExpandedAmcs(autoExp);
    }
  }, [searchTerm, filteredData.matchedAmcs]);

  const toggleAmc = (amc) => {
    setExpandedAmcs((prev) => ({
      ...prev,
      [amc]: !prev[amc],
    }));
  };

  const expandAll = () => {
    const all = {};
    filteredData.matchedAmcs.forEach((amc) => {
      all[amc] = true;
    });
    setExpandedAmcs(all);
  };

  const collapseAll = () => {
    setExpandedAmcs({});
  };

  const amcCountDisplay = data?.amcCount ?? 24;
  const fundCountDisplay = data?.fundCount ?? 386;

  return (
    <section className="cov-section" id="coverage" aria-labelledby="cov-heading">
      <div className="container cov-container">
        {/* ── Section Header ── */}
        <div className="cov-header">
          <div className="cov-title-row">
            <h2 id="cov-heading" className="cov-title">
              Our AMC &amp; Fund Coverage
            </h2>
            <div className="cov-badges" aria-label="Coverage Statistics">
              <span className="cov-badge cov-badge-amc">
                <strong>{amcCountDisplay}</strong> AMCs
              </span>
              <span className="cov-badge cov-badge-fund">
                <strong>{fundCountDisplay}</strong> Funds
              </span>
            </div>
          </div>
          <p className="cov-subtitle">
            We currently track {amcCountDisplay} AMCs and {fundCountDisplay} funds. Explore the AMCs and their associated funds below.
          </p>
        </div>

        {/* ── Loading State ── */}
        {loading && !data && (
          <div className="cov-loading" role="status" aria-live="polite">
            <div className="cov-spinner" />
            <p>Loading AMC &amp; fund coverage…</p>
          </div>
        )}

        {/* ── Error Fallback ── */}
        {error && !data && (
          <div className="cov-error" role="alert">
            <p>Coverage information is temporarily unavailable.</p>
          </div>
        )}

        {/* ── Interactive Accordion Content ── */}
        {data && (
          <div className="cov-content-card">
            {/* Toolbar: Search + Expand/Collapse */}
            <div className="cov-toolbar">
              <div className="cov-search-wrap">
                <svg
                  className="cov-search-icon"
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <circle cx="11" cy="11" r="8" />
                  <line x1="21" y1="21" x2="16.65" y2="16.65" />
                </svg>
                <input
                  id={searchInputId}
                  type="text"
                  className="cov-search-input"
                  placeholder="Search AMCs or Funds (e.g. HDFC, Flexi Cap, SBI)..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  aria-label="Search AMCs or Funds"
                />
                {searchTerm && (
                  <button
                    type="button"
                    className="cov-search-clear"
                    onClick={() => setSearchTerm('')}
                    aria-label="Clear search"
                    title="Clear search"
                  >
                    ×
                  </button>
                )}
              </div>

              <div className="cov-actions">
                <button
                  type="button"
                  className="cov-action-btn"
                  onClick={expandAll}
                  aria-label="Expand all AMCs"
                >
                  Expand All
                </button>
                <span className="cov-action-sep" aria-hidden="true">|</span>
                <button
                  type="button"
                  className="cov-action-btn"
                  onClick={collapseAll}
                  aria-label="Collapse all AMCs"
                >
                  Collapse All
                </button>
              </div>
            </div>

            {/* Search Match Feedback */}
            {searchTerm.trim() && (
              <div className="cov-search-meta" aria-live="polite">
                Showing <strong>{filteredData.matchedAmcs.length}</strong> AMCs and <strong>{filteredData.totalMatchedFunds}</strong> matching funds for &ldquo;{searchTerm}&rdquo;
              </div>
            )}

            {/* Zero Results State */}
            {filteredData.matchedAmcs.length === 0 && (
              <div className="cov-no-results">
                <p>No AMCs or funds match &ldquo;{searchTerm}&rdquo;.</p>
                <button
                  type="button"
                  className="btn btn-outline cov-reset-btn"
                  onClick={() => setSearchTerm('')}
                >
                  Clear Search
                </button>
              </div>
            )}

            {/* Accordion List */}
            <div className="cov-accordion" role="region" aria-label="AMC Accordion">
              {filteredData.matchedAmcs.map((amc, index) => {
                const isExpanded = !!expandedAmcs[amc];
                const funds = filteredData.amcFundFilteredMap[amc] || [];
                const panelId = `cov-panel-${index}`;
                const buttonId = `cov-btn-${index}`;

                return (
                  <div key={amc} className={`cov-accordion-item ${isExpanded ? 'is-expanded' : ''}`}>
                    <h3>
                      <button
                        type="button"
                        id={buttonId}
                        className="cov-accordion-btn"
                        onClick={() => toggleAmc(amc)}
                        aria-expanded={isExpanded}
                        aria-controls={panelId}
                      >
                        <div className="cov-amc-left">
                          <span className="cov-chevron" aria-hidden="true">
                            {isExpanded ? '▼' : '▶'}
                          </span>
                          <span className="cov-amc-name">{amc}</span>
                        </div>
                        <span className="cov-fund-count-chip">
                          {funds.length} {funds.length === 1 ? 'Fund' : 'Funds'}
                        </span>
                      </button>
                    </h3>

                    {isExpanded && (
                      <div
                        id={panelId}
                        role="region"
                        aria-labelledby={buttonId}
                        className="cov-accordion-panel"
                      >
                        <div className="cov-funds-grid">
                          {funds.map((fund) => (
                            <div key={fund} className="cov-fund-item">
                              <span className="cov-fund-bullet" aria-hidden="true">•</span>
                              <span className="cov-fund-name">{fund}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
