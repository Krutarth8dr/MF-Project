'use client';

import { useState } from 'react';

export const REPORT_GUIDES = {
  report1: {
    id: 'report1',
    num: 1,
    badge: 'Report 1',
    title: 'Mutual Fund Quantity Trend',
    subtitle: 'Longitudinal Institutional Volume & Historical Position Tracker',
    summary:
      'Report 1 provides a comprehensive multi-year historical view of aggregate mutual fund shareholdings for any security. It visualizes whether domestic institutions have been steadily accumulating, holding, or distributing positions over monthly regulatory disclosure cycles.',
    interactiveControls: [
      {
        control: 'Security Name & Alias Typeahead',
        action: 'Type any stock name or alias (e.g. "Adani", "ITC", "KSB") into the search box. The system searches across 20 canonical alias columns and provides real-time autocomplete suggestions.',
      },
      {
        control: 'ISIN Direct Lookup',
        action: 'Enter an authoritative 12-character ISIN (e.g. "INE423A01024") to instantly isolate and load the historical dataset for that specific financial asset.',
      },
      {
        control: 'Select AMCs Multi-Filter',
        action: 'Click the "Select AMCs" dropdown to check/uncheck specific asset management companies (e.g. select only HDFC and ICICI to isolate their combined trendline).',
      },
      {
        control: 'Scheme & Rating Filters',
        action: 'Filter data by specific mutual fund schemes or bond/credit ratings to analyze fund-category allocations.',
      },
      {
        control: 'Interactive Chart Hover',
        action: 'Hover over any data point on the volume curve to view exact share quantities and historical month-year timestamps.',
      },
      {
        control: 'Historical Data Table',
        action: 'View exact month-by-month share counts below the chart in a paginated, sortable tabular format.',
      },
    ],
    keyFeatures: [
      {
        title: 'Interactive Volume Trend Chart',
        desc: 'Visualizes the total quantity of shares held across all mutual fund schemes over 30+ monthly disclosure cycles with responsive tooltips.',
      },
      {
        title: 'Multi-Dimensional Institutional Filtering',
        desc: 'Filter by specific AMCs (e.g. HDFC, ICICI Prudential, SBI), individual mutual fund schemes, or industry credit ratings.',
      },
      {
        title: 'Smart Security Name & ISIN Search',
        desc: 'Search across 20 canonical alias name variations or query directly using the authoritative 12-character ISIN.',
      },
      {
        title: 'Historical Tabular Breakdown',
        desc: 'Access exact monthly share counts and date points in a paginated, sortable data table below the chart.',
      },
    ],
    howToInterpret: [
      {
        label: 'Upward Sloping Trend',
        detail: 'Sustained institutional accumulation over consecutive months indicates growing fund manager conviction.',
      },
      {
        label: 'Downward Sloping Trend',
        detail: 'Systematic institutional profit booking or risk offloading across multiple disclosure cycles.',
      },
      {
        label: 'Plateau / Rangebound Trend',
        detail: 'Passive holding phase where fund managers are maintaining existing allocations without major capital deployment.',
      },
    ],
    useCases: [
      'Validate price breakouts by checking if institutional share volumes are expanding alongside price appreciation.',
      'Identify early smart-money accumulation in under-the-radar mid-cap and small-cap companies before public retail awareness.',
      'Check institutional conviction during market corrections — stocks where MFs add quantity during dips often lead the next market leg.',
    ],
  },

  report2: {
    id: 'report2',
    num: 2,
    badge: 'Report 2',
    title: 'Monthly Institutional Activity Monitor',
    subtitle: 'Month-over-Month Differential Scanner & Position Shift Analyzer',
    summary:
      'Report 2 compares the latest mutual fund portfolio snapshot with the previous month across the entire investment universe. It instantly flags where institutional capital flowed in the most recent monthly disclosure cycle.',
    interactiveControls: [
      {
        control: 'Click "Net Quantity Change" Column Header',
        action: 'Click the "Net Quantity Change" header to sort the entire database from the largest institutional accumulations (highest positive share additions) to the largest reductions.',
      },
      {
        control: 'Click "% Change" Column Header',
        action: 'Click the "% Change" header to sort by the highest percentage expansion or steepest contraction relative to previous holdings.',
      },
      {
        control: 'Click "Current Qty" or "Previous Qty" Headers',
        action: 'Click these headers to sort by total absolute position volume held across the mutual fund industry.',
      },
      {
        control: 'Quick-Filter Presets Tabs',
        action: 'Click "🟢 Net Accumulation" (all stocks with net positive share additions), "🔴 Net Reduction" (net negative), "🆕 New Positions" (initiated from 0 shares), or "🚪 Exits" (completely liquidated to 0).',
      },
      {
        control: 'Click "Report 1" or "Report 3" Action Buttons',
        action: 'Click the "Report 1" button in any stock row to open its multi-year quantity trend, or click "Report 3" to view its AMC-by-AMC holding breakdown.',
      },
      {
        control: 'Select AMCs Filter',
        action: 'Filter the scanner to isolate activity within specific fund houses (e.g. check only Kotak or Nippon).',
      },
    ],
    keyFeatures: [
      {
        title: 'Classification Engine (4 Action Types)',
        desc: 'Categorizes every security into NEW (fresh position entry), EXIT (complete liquidation), INCREASE (accumulation), or DECREASE (reduction).',
      },
      {
        title: 'Quick Filter Presets',
        desc: 'One-click filter tabs to isolate Net Accumulations, Net Reductions, Fresh Entries, or Complete Liquidations across the market.',
      },
      {
        title: 'KPI Summary Metrics',
        desc: 'Real-time counters showing total active securities evaluated, net buyers, net sellers, fresh entries, and full exits.',
      },
      {
        title: 'Multi-Column Sorting & Pagination',
        desc: 'Sort by absolute share quantity change, percentage change (% Change), current quantity, previous quantity, or security name.',
      },
    ],
    howToInterpret: [
      {
        label: 'NEW (Fresh Entry)',
        detail: 'Mutual funds initiated brand new holdings in this security during the latest month where previously they held 0 shares.',
      },
      {
        label: 'EXIT (Full Liquidation)',
        detail: 'Mutual funds completely eliminated their position, reducing total institutional share quantity to 0.',
      },
      {
        label: 'INCREASE (Net Accumulation)',
        detail: 'Aggregate quantity of shares held across evaluated funds increased compared to the previous month.',
      },
      {
        label: 'DECREASE (Net Reduction)',
        detail: 'Aggregate quantity of shares held decreased compared to the previous month.',
      },
    ],
    useCases: [
      'Screen for top institutional buying ideas each month as soon as AMC monthly portfolio disclosures are published.',
      'Identify institutional exit warnings — spot stocks being aggressively offloaded by mutual funds before retail sentiment turns.',
      'Analyze specific AMC behavior (e.g. isolate Nippon or Kotak to see what top fund managers bought or sold this month).',
    ],
  },

  report3: {
    id: 'report3',
    num: 3,
    badge: 'Report 3',
    title: 'AMC Intelligence & Historical Deep Dive',
    subtitle: 'Asset Manager Breakdown & Institutional Market Share Shifts',
    summary:
      'Report 3 breaks down the institutional ownership of any single security by individual asset management companies. It reveals which specific fund houses hold the largest stakes and how their respective allocations have evolved over time.',
    interactiveControls: [
      {
        control: 'Click AMC Names in Chart Legend',
        action: 'Click any fund house name (e.g. "HDFC Mutual Fund", "SBI MF", "ICICI Prudential") in the interactive chart legend to toggle that AMC line on or off for clear head-to-head comparison.',
      },
      {
        control: 'Click "Full Width / Wide Canvas" Toggle',
        action: 'Expand the timeline horizontally across your screen to analyze high-density historical timelines comfortably.',
      },
      {
        control: 'Click "Show Data Labels" Toggle',
        action: 'Display exact share volume numbers directly on top of the trend lines for rapid visual scanning without hovering.',
      },
      {
        control: 'Search Security Name or Enter ISIN',
        action: 'Quickly switch securities using the smart alias typeahead or authoritative ISIN input.',
      },
      {
        control: 'Historical Per-AMC Data Table',
        action: 'Inspect exact historical share counts per AMC across all disclosure dates in a dedicated breakdown table below.',
      },
    ],
    keyFeatures: [
      {
        title: 'Per-AMC Historical Allocation Grid',
        desc: 'Displays the exact share counts held by each individual AMC across all historical monthly portfolio dates.',
      },
      {
        title: 'Interactive Multi-Line AMC Chart',
        desc: 'Visualizes the trajectory and volume distribution among top fund houses (e.g. HDFC vs ICICI vs SBI vs Axis).',
      },
      {
        title: 'Canonical Security Identification',
        desc: 'Displays standardized security metadata, ISIN, alternative aliases, and the total count of holding AMCs.',
      },
      {
        title: 'Direct Navigation Links',
        desc: 'Jump directly to Report 1 (Total Trend) or explore other securities in Report 4 with one click.',
      },
    ],
    howToInterpret: [
      {
        label: 'Broad Institutional Ownership',
        detail: 'Shares distributed evenly across 10+ major fund houses signifies high institutional consensus and liquidity.',
      },
      {
        label: 'Concentrated Ownership',
        detail: 'A single fund house holding 60%+ of the institutional float implies higher sensitivity to that specific fund manager\'s actions.',
      },
      {
        label: 'Divergent Manager Sentiment',
        detail: 'Identify situations where one AMC is aggressively buying while another is selling, revealing tactical fund manager divergence.',
      },
    ],
    useCases: [
      'Analyze the institutional backing of core portfolio holdings.',
      'Track smart-money leadership by monitoring whether premier asset managers (e.g. HDFC, ICICI) are increasing exposure.',
      'Assess liquidity risks before taking large equity positions.',
    ],
  },

  report4: {
    id: 'report4',
    num: 4,
    badge: 'Report 4',
    title: 'Institutional Cross-AMC Direction Matrix',
    subtitle: 'Cross-Institutional Consensus Heatmap & Signal Matrix',
    summary:
      'Report 4 provides a high-density, multi-AMC matrix comparing the latest and previous month portfolio changes across all 13 evaluated asset managers. It enables instant identification of multi-fund consensus buying and selling.',
    interactiveControls: [
      {
        control: 'Click "Buying AMCs (🟢 Count)" Column Header',
        action: 'Click the "Buying AMCs" header to sort all securities by the highest number of accumulating fund houses descending (e.g. stocks with 10, 9, 8 buying AMCs appear first).',
      },
      {
        control: 'Click "Selling AMCs (🔴 Count)" Column Header',
        action: 'Click the "Selling AMCs" header to sort by the highest number of distributing fund houses descending.',
      },
      {
        control: 'Click "Neutral AMCs (⚪ Count)" Column Header',
        action: 'Click to sort securities by unchanged/flat AMC holding counts.',
      },
      {
        control: 'Click "Security Name" Column Header',
        action: 'Sort securities alphabetically from A to Z or Z to A.',
      },
      {
        control: 'Hover Over Any AMC Badge Cell (🟢, 🔴, ⚪)',
        action: 'Hover over any AMC cell badge to view an interactive tooltip showing: Current Month Shares, Previous Month Shares, and Exact Net Share Change for that fund house.',
      },
      {
        control: 'Click Summary KPI Cards or "Overall Direction" Dropdown',
        action: 'Click the "🟢 Overall Net Buying", "🔴 Overall Net Selling", or "⚪ Overall Neutral" cards to filter the matrix immediately.',
      },
      {
        control: 'Click Stock Row Action Links',
        action: 'Click the quick links on any stock row to open its long-term quantity curve in Report 1 or AMC breakdown in Report 3.',
      },
    ],
    keyFeatures: [
      {
        title: 'Color-Coded AMC Signal Badges',
        desc: 'Every AMC column displays a visual indicator: 🟢 Green (Increased holdings), 🔴 Red (Decreased holdings), or ⚪ Neutral (Unchanged/Flat holding).',
      },
      {
        title: 'Interactive Cell Inspection',
        desc: 'Hover over any AMC badge to view a tooltip showing the exact Current Shares, Previous Shares, and Net Change for that AMC.',
      },
      {
        title: 'Consensus Direction Counters',
        desc: 'Dedicated columns tally the Green Count (number of buying AMCs), Red Count (selling AMCs), and Neutral Count for every stock.',
      },
      {
        title: 'Overall Direction Indicator',
        desc: 'Computes the net aggregate direction across all AMCs combined to show net accumulation or net reduction.',
      },
    ],
    howToInterpret: [
      {
        label: '🟢 Green Signal',
        detail: 'The specific AMC increased its share holding in this stock compared to the previous month.',
      },
      {
        label: '🔴 Red Signal',
        detail: 'The specific AMC reduced its share holding in this stock compared to the previous month.',
      },
      {
        label: '⚪ Neutral Signal',
        detail: 'The specific AMC maintained flat holdings or did not hold shares during the comparison window.',
      },
      {
        label: 'High Green Count (e.g. 6+ Green, 0 Red)',
        detail: 'Widespread multi-AMC institutional consensus accumulation — powerful bullish smart-money signal.',
      },
    ],
    useCases: [
      'Filter for stocks where 5 or more AMCs are buying simultaneously with zero AMCs selling.',
      'Detect contrarian plays where a single dominant fund house is accumulating against broader market trimming.',
      'Sort by Green Count descending to instantly surface the highest-consensus institutional conviction ideas.',
    ],
  },

  report5: {
    id: 'report5',
    num: 5,
    badge: 'Report 5',
    title: 'AMC Buying Breadth Rankings',
    subtitle: 'Institutional Breadth Scoring & Smart-Money Conviction Ranking',
    summary:
      'Report 5 ranks all evaluated securities by institutional breadth conviction. It measures how many independent asset managers are accumulating a security relative to those selling, providing an objective consensus leaderboard.',
    interactiveControls: [
      {
        control: 'Click "Buying AMCs" Column Header',
        action: 'Click the "Buying AMCs" header to sort all securities by the highest number of buying fund houses descending.',
      },
      {
        control: 'Click "Selling AMCs" Column Header',
        action: 'Click the "Selling AMCs" header to sort by the highest number of selling fund houses descending.',
      },
      {
        control: 'Click "Net Buying Score" Column Header',
        action: 'Click the "Net Buying Score" header to sort by the net breadth balance (Buying AMCs − Selling AMCs), bubbling top institutional consensus to the top.',
      },
      {
        control: 'Click "🔥 Strongest Buying" Ranking Mode Button',
        action: 'Toggle this mode on to activate hierarchical conviction sorting: Ranks all stocks with 0 selling AMCs first (Zero Selling Club), sorted from highest buying AMC count downward.',
      },
      {
        control: 'Click Preset Filter Tabs & Clickable KPI Cards',
        action: 'Click "🟢 Zero Selling (0 Selling)", "🏆 Broad Consensus (5+ Buying)", or "📈 Net Accumulation (Net Score > 0)" to instantly filter the leaderboard.',
      },
      {
        control: 'Click "Reset Filters" Button',
        action: 'Clears active search and preset selections to restore the full ranking leaderboard view.',
      },
    ],
    keyFeatures: [
      {
        title: 'Net Buying Score Calculation',
        desc: 'Calculated as: (Buying AMCs Count − Selling AMCs Count). A higher positive score indicates superior institutional breadth.',
      },
      {
        title: '🔥 Strongest Buying Priority Mode',
        desc: 'Ranks securities with 0 selling AMCs first (Zero Selling Club), sorted from highest buying AMC count downward.',
      },
      {
        title: 'Strategic Conviction Presets',
        desc: 'One-click filters for "Zero Selling (0 Selling)", "Broad Consensus (5+ Buying)", and "Net Accumulation (Net Score > 0)".',
      },
      {
        title: 'KPI Breadth Cards',
        desc: 'Displays the total count of securities currently qualifying for the Zero Selling Club, Broad Consensus tier, and Net Accumulating category.',
      },
    ],
    howToInterpret: [
      {
        label: 'Zero Selling Club (High Conviction)',
        detail: 'Stocks with multiple AMCs buying and exactly 0 AMCs selling. Represents the lowest institutional selling resistance.',
      },
      {
        label: 'Broad Consensus Tier',
        detail: 'Securities being accumulated by 5 or more independent asset management companies in the same monthly cycle.',
      },
      {
        label: 'Net Buying Score',
        detail: 'Measures net institutional sentiment (+7 = 7 more AMCs buying than selling; −5 = heavy institutional distribution).',
      },
    ],
    useCases: [
      'Find the highest quality institutional accumulation candidates without having to manually check each fund house.',
      'Filter out "mixed sentiment" stocks where buying by one fund is offset by aggressive selling from multiple other funds.',
      'Use the Zero Selling filter to construct a high-conviction institutional momentum watchlist.',
    ],
  },

  report6: {
    id: 'report6',
    num: 6,
    badge: 'Report 6',
    title: '7-Month Institutional Holding Direction',
    subtitle: 'Multi-Month Longitudinal Momentum & Sustained Conviction Matrix',
    summary:
      'Report 6 tracks the monthly institutional holding direction (Increase / Decrease / Flat) across the latest 7 consecutive monthly disclosure cycles (1M through 7M). It separates short-term monthly noise from sustained multi-quarter institutional accumulation.',
    interactiveControls: [
      {
        control: '1M through 7M Direction Dropdowns',
        action: 'Filter by any specific month\'s directional signal (e.g. set 1M=Green, 2M=Green, 3M=Green to find stocks accumulated consecutively for the last 3 months).',
      },
      {
        control: 'Click "View Details" Button on Any Stock Row',
        action: 'Click the "View Details" button to open an interactive modal displaying the complete 7-month audit trail with exact disclosure dates, holding quantities, and monthly changes.',
      },
      {
        control: 'Hover Over Any 1M–7M Signal Badge (🟢, 🔴, ⚪)',
        action: 'Hover over any badge in the table to view the comparison period, current quantity, previous quantity, and net share change.',
      },
      {
        control: 'Click "Clear Filters" Button',
        action: 'Resets all 7 monthly direction dropdowns and security search inputs back to the default full view.',
      },
      {
        control: 'Pagination Controls',
        action: 'Navigate across all 20+ pages of tracked institutional securities using the Prev / Next page controls.',
      },
    ],
    keyFeatures: [
      {
        title: '7-Month Consecutive Direction Sequence',
        desc: 'Displays monthly directional signals (1M = Latest month, 2M = Month −1, ..., 7M = Month −6) for each security.',
      },
      {
        title: 'Cumulative Directional Counters',
        desc: 'Tracks total Green Months (accumulations), Red Months (reductions), Neutral Months, and the Net 7M Consensus Score.',
      },
      {
        title: 'Independent 7-Month Filter Matrix',
        desc: 'Filter by exact direction conditions across any individual month (e.g. 1M = Green AND 2M = Green AND 3M = Green).',
      },
      {
        title: 'Comprehensive Detail Modal',
        desc: 'Click "View Details" on any row to open the complete 7-month breakdown with exact dates, share quantities, and monthly changes.',
      },
    ],
    howToInterpret: [
      {
        label: 'Consecutive Green Months (e.g. 5M–7M Green)',
        detail: 'Indicates systematic, long-term institutional accumulation across multiple quarters — prime candidate for sustained uptrends.',
      },
      {
        label: 'Turnaround Signal (Red to Green Transition)',
        detail: 'When a stock transitions from multiple Red months (distribution) to fresh Green signals in 1M and 2M, indicating institutional re-accumulation.',
      },
      {
        label: 'Exhaustion Signal (Green to Red Transition)',
        detail: 'When a long accumulation streak ends and institutional managers begin distributing shares.',
      },
    ],
    useCases: [
      'Identify long-term institutional compounders that mutual funds have accumulated month-after-month for over half a year.',
      'Catch trend reversals early by screening for stocks that turned Green in the latest month after prolonged selling.',
      'Confirm multi-quarter institutional sponsorship before initiating long-term equity investments.',
    ],
  },
};

export default function ReportGuideModal({ reportId, isOpen, onClose }) {
  const [activeTab, setActiveTab] = useState(reportId || 'report1');

  if (!isOpen) return null;

  const currentGuide = REPORT_GUIDES[activeTab] || REPORT_GUIDES[reportId] || REPORT_GUIDES.report1;

  return (
    <div className="guide-modal-overlay" onClick={onClose} role="dialog" aria-modal="true">
      <div className="guide-modal-container" onClick={(e) => e.stopPropagation()}>
        {/* Modal Header */}
        <div className="guide-modal-header">
          <div className="guide-header-title-wrap">
            <span className="guide-badge-pill">{currentGuide.badge} Documentation</span>
            <h2 className="guide-modal-title">{currentGuide.title}</h2>
            <p className="guide-modal-subtitle">{currentGuide.subtitle}</p>
          </div>
          <button
            type="button"
            className="guide-modal-close"
            onClick={onClose}
            aria-label="Close guide"
          >
            ×
          </button>
        </div>

        {/* Report Selector Tabs Bar */}
        <div className="guide-tabs-nav">
          {Object.values(REPORT_GUIDES).map((guide) => (
            <button
              key={guide.id}
              type="button"
              className={`guide-tab-btn ${activeTab === guide.id ? 'guide-tab-active' : ''}`}
              onClick={() => setActiveTab(guide.id)}
            >
              Report {guide.num}
            </button>
          ))}
        </div>

        {/* Modal Scrollable Body */}
        <div className="guide-modal-body">
          {/* Executive Overview */}
          <section className="guide-section">
            <h3 className="guide-section-title">📌 Executive Overview</h3>
            <p className="guide-text-lead">{currentGuide.summary}</p>
          </section>

          {/* Interactive Column Sorting & Controls Guide */}
          <section className="guide-section">
            <h3 className="guide-section-title">🎮 How to Use Interactive Controls & Column Sorting</h3>
            <div className="guide-controls-grid">
              {currentGuide.interactiveControls.map((ctrl, idx) => (
                <div key={idx} className="guide-control-card">
                  <div className="guide-control-badge">{ctrl.control}</div>
                  <p className="guide-control-action">{ctrl.action}</p>
                </div>
              ))}
            </div>
          </section>

          {/* Key Functionalities */}
          <section className="guide-section">
            <h3 className="guide-section-title">⚡ Core Capabilities & Features</h3>
            <div className="guide-features-grid">
              {currentGuide.keyFeatures.map((feat, idx) => (
                <div key={idx} className="guide-feature-card">
                  <h4 className="guide-feature-title">{feat.title}</h4>
                  <p className="guide-feature-desc">{feat.desc}</p>
                </div>
              ))}
            </div>
          </section>

          {/* How to Interpret */}
          <section className="guide-section">
            <h3 className="guide-section-title">🔍 Signal Interpretation & Analysis</h3>
            <div className="guide-interpret-list">
              {currentGuide.howToInterpret.map((item, idx) => (
                <div key={idx} className="guide-interpret-item">
                  <div className="guide-interpret-label">{item.label}</div>
                  <div className="guide-interpret-detail">{item.detail}</div>
                </div>
              ))}
            </div>
          </section>

          {/* Institutional Use Cases */}
          <section className="guide-section">
            <h3 className="guide-section-title">🎯 Actionable Institutional Use Cases</h3>
            <ul className="guide-usecases-list">
              {currentGuide.useCases.map((uc, idx) => (
                <li key={idx} className="guide-usecase-item">
                  <span className="guide-check-bullet">✓</span>
                  <span>{uc}</span>
                </li>
              ))}
            </ul>
          </section>
        </div>

        {/* Modal Footer */}
        <div className="guide-modal-footer">
          <span className="guide-footer-note">
            Wealthyneers Institutional Intelligence Engine • Monthly Disclosures Analytics
          </span>
          <button type="button" className="btn btn-primary guide-footer-btn" onClick={onClose}>
            Back to Report
          </button>
        </div>
      </div>
    </div>
  );
}
