export default function Home() {
  const reports = [
    { id: 1, title: "Market Momentum Pulse", desc: "Daily analysis of sector-wise momentum shifts and breakout candidates.", icon: "📈" },
    { id: 2, title: "Insider Activity Tracker", desc: "Real-time updates on significant promoter buying and selling activities.", icon: "🕵️" },
    { id: 3, title: "Dividend Yield Stars", desc: "Monthly curated list of high-yield, fundamentally strong dividend stocks.", icon: "💰" },
    { id: 4, title: "Smallcap Hidden Gems", desc: "In-depth research on undiscovered smallcaps with high growth potential.", icon: "💎" },
    { id: 5, title: "Macro Risk Radar", desc: "Weekly macro-economic risk assessment impacting the Indian markets.", icon: "🌍" },
  ];

  return (
    <main>
      <section className="hero">
        <div className="container">
          <h1>Navigate Markets with Precision</h1>
          <p>Get exclusive access to our 5 proprietary data reports, designed for serious investors who demand institutional-grade insights.</p>
          <a href="#pricing" className="btn btn-primary" style={{ fontSize: '1.25rem', padding: '1rem 2.5rem' }}>
            Get Full Access
          </a>
        </div>
      </section>

      <section id="reports" className="reports">
        <div className="container">
          <h2 className="section-title">Our Premium Reports</h2>
          <div className="reports-grid">
            {reports.map((report) => (
              <div key={report.id} className="report-card">
                <div className="report-icon">{report.icon}</div>
                <h3 className="report-title">{report.title}</h3>
                <p className="report-desc">{report.desc}</p>
                <div className="locked">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                  Subscribers Only
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="pricing" className="pricing">
        <div className="container">
          <div className="pricing-card">
            <h2>Unlimited Access</h2>
            <div className="price">₹4,999<span>/year</span></div>
            <p>One subscription. All five premium reports.</p>
            
            <ul className="features">
              <li><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#05bfdb" strokeWidth="2"><polyline points="20 6 9 17 4 12"/></svg> Daily updates directly to your dashboard</li>
              <li><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#05bfdb" strokeWidth="2"><polyline points="20 6 9 17 4 12"/></svg> Downloadable PDF and CSV formats</li>
              <li><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#05bfdb" strokeWidth="2"><polyline points="20 6 9 17 4 12"/></svg> Cancel anytime, no questions asked</li>
            </ul>

            <button className="btn btn-primary" style={{ width: '100%', fontSize: '1.25rem' }}>
              Subscribe Now
            </button>
            <div className="upi-badge">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
              Supports UPI AutoPay, Credit Cards & Net Banking
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
