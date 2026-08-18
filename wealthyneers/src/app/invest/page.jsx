import Link from 'next/link';

export const metadata = {
  title: 'Invest in Mutual Funds Guided By Wealthyneers | Distribution & Advisory Intelligence',
  description: 'Partner with Wealthyneers for data-backed mutual fund distribution, institutional analytics guidance, curated scheme selection, and comprehensive portfolio management.',
};

export default function InvestPage() {
  return (
    <div className="invest-page">
      {/* Hero Section */}
      <div className="invest-hero">
        <div className="invest-badge">
          ✦ Mutual Fund Distribution &amp; Guided Analytics
        </div>
        <h1 className="invest-title">
          Invest in Mutual Funds Guided By Wealthyneers
        </h1>
        <p className="invest-subtitle">
          Experience transparent, research-driven mutual fund distribution. We combine institutional-grade
          data intelligence with personalized guidance to help you build, optimize, and manage
          high-conviction portfolios aligned with your long-term wealth goals.
        </p>
      </div>

      {/* Value Pillars: How Wealthyneers Guides Your Investments */}
      <div className="invest-section-heading">
        <h2>Why Invest with Wealthyneers Guidance?</h2>
        <p>
          We bridge the gap between complex institutional market intelligence and practical, goal-oriented mutual fund investing.
        </p>
      </div>

      <div className="invest-benefits-grid">
        <div className="invest-benefit-card">
          <span className="invest-benefit-icon">🏢</span>
          <h3>Institutional Data-Backed Selection</h3>
          <p>
            We don&apos;t rely on marketing claims. Our scheme recommendations are backed by continuous tracking of
            month-over-month holding shifts, buying breadth rankings, and portfolio conviction across all top Indian AMCs.
          </p>
        </div>

        <div className="invest-benefit-card">
          <span className="invest-benefit-icon">🎯</span>
          <h3>Goal-Aligned Asset Allocation</h3>
          <p>
            Whether you are planning for retirement, wealth compounding, or tax efficiency, we design a customized
            equity and debt mutual fund allocation tailored specifically to your risk tolerance and time horizon.
          </p>
        </div>

        <div className="invest-benefit-card">
          <span className="invest-benefit-icon">⚡</span>
          <h3>Seamless Onboarding &amp; Execution</h3>
          <p>
            Enjoy paperless KYC processing, rapid folio creation, and automated SIP setups with complete
            operational support from our dedicated investor desk at every stage.
          </p>
        </div>

        <div className="invest-benefit-card">
          <span className="invest-benefit-icon">🔄</span>
          <h3>Active Reviews &amp; Rebalancing</h3>
          <p>
            Markets and fund managers evolve. We continuously monitor scheme health and institutional capital
            flows, alerting you whenever your portfolio requires disciplined rebalancing or reallocation.
          </p>
        </div>
      </div>

      {/* Featured Resource Section (Google Doc Questionnaire) */}
      <div className="invest-resources-wrap">
        <div className="invest-section-heading">
          <h2>Investor Profiling &amp; Planning Questionnaire</h2>
          <p>
            Submit your financial parameters to receive a customized portfolio allocation and review.
          </p>
        </div>

        <div className="invest-resources-grid">
          {/* Resource: Google Doc Questionnaire */}
          <div className="invest-resource-card">
            <span className="invest-resource-tag tag-doc">
              📋 Investor Form &amp; Planning Doc
            </span>
            <h3>Profile Review &amp; Goal Planning Questionnaire</h3>
            <p>
              A form designed to capture your financial targets, audit existing mutual fund folios,
              calculate your optimal asset allocation, and request a personalized distribution portfolio review from our team.
            </p>
            <Link
              href="/investor-profile"
              className="invest-btn-doc"
            >
              📋 Start Investor Assessment →
            </Link>
          </div>
        </div>
      </div>

      {/* Step-by-step Guided Process */}
      <div className="invest-steps-card">
        <h3 style={{ fontSize: '1.4rem', fontWeight: 800, marginBottom: '1.5rem', color: 'var(--foreground)' }}>
          Our 4-Step Guided Investment Process
        </h3>

        <div className="invest-step-item">
          <div className="invest-step-number">1</div>
          <div className="invest-step-content">
            <h4>Goal Discovery &amp; Risk Profiling</h4>
            <p>
              We evaluate your investment horizon, liquidity needs, and risk tolerance through our structured planning framework.
            </p>
          </div>
        </div>

        <div className="invest-step-item">
          <div className="invest-step-number">2</div>
          <div className="invest-step-content">
            <h4>Research-Backed Portfolio Curation</h4>
            <p>
              We curate a focused basket of mutual fund schemes selected using Wealthyneers institutional buying breadth and conviction analytics.
            </p>
          </div>
        </div>

        <div className="invest-step-item">
          <div className="invest-step-number">3</div>
          <div className="invest-step-content">
            <h4>Assisted Onboarding &amp; Execution</h4>
            <p>
              We facilitate swift, paperless account creation, verify online KYC, and establish your recurring SIPs or lump-sum investments.
            </p>
          </div>
        </div>

        <div className="invest-step-item">
          <div className="invest-step-number">4</div>
          <div className="invest-step-content">
            <h4>Ongoing Monitoring &amp; Reporting</h4>
            <p>
              Receive regular performance updates, market trend analysis, and rebalancing recommendations whenever fund management dynamics shift.
            </p>
          </div>
        </div>
      </div>

      {/* Bottom CTA Banner */}
      <div className="invest-cta-banner">
        <h2>Start Your Guided Investment Journey Today</h2>
        <p>
          Let Wealthyneers data intelligence and expert distribution power your wealth creation.
        </p>
        <div className="invest-cta-buttons">
          <Link href="/contact" className="btn btn-primary" style={{ backgroundColor: '#c39354', color: '#083344', fontWeight: 700 }}>
            ✉️ Contact Investment Desk →
          </Link>
          <Link href="/dashboard" className="btn btn-outline" style={{ borderColor: 'rgba(255,255,255,0.4)', color: '#ffffff' }}>
            📊 Explore Research Dashboard
          </Link>
        </div>
      </div>
    </div>
  );
}
