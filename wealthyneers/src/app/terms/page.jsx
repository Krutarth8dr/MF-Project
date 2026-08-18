import Link from 'next/link';

export const metadata = {
  title: 'Terms & Conditions | Wealthyneers',
  description: 'Terms and conditions governing the use of Wealthyneers institutional research reports and analytics platform.',
};

export default function TermsPage() {
  return (
    <div className="legal-page">
      <div className="legal-header">
        <span className="legal-badge">Legal Documentation</span>
        <h1 className="legal-title">Terms &amp; Conditions</h1>
        <div className="legal-meta">
          Last Updated: August 16, 2026 · Domain: wealthyneers.com
        </div>
      </div>

      <div className="legal-card">
        <div className="legal-section">
          <h2>1. Acceptance of Terms</h2>
          <p>
            Welcome to <strong>Wealthyneers</strong> (accessible at <a href="https://wealthyneers.com" style={{ color: 'var(--primary)' }}>wealthyneers.com</a>).
            By accessing, browsing, registering for an account, or subscribing to our services, you agree to be bound by these
            Terms and Conditions (&quot;Terms&quot;), our Privacy Policy, and our Refund Policy. If you do not agree with any part
            of these Terms, please do not use our platform.
          </p>
        </div>

        <div className="legal-section">
          <h2>2. Description of Service</h2>
          <p>
            Wealthyneers is a proprietary financial data intelligence and market research platform. We provide interactive data
            visualizations, historical mutual fund holding trends, AMC directional matrices, and institutional breadth rankings
            synthesized from publicly disclosed asset management disclosures in India.
          </p>
          <p>
            Access to our six core research reports (Reports 1 through 6) and analytics dashboard is provided under an active
            paid subscription plan.
          </p>
        </div>

        <div className="legal-section">
          <h2>3. Important Disclaimer — No Investment Advice</h2>
          <div className="legal-callout">
            <strong>⚠️ Educational &amp; Informational Purpose Only:</strong> The analytics, data, rankings, directional indicators,
            and visualizations provided on Wealthyneers are compiled solely for informational, research, and educational purposes.
            Wealthyneers is not a SEBI-registered investment advisor, portfolio manager, or research analyst entity.
          </div>
          <p>
            Nothing on this website constitutes an offer, solicitation, or recommendation to buy, sell, or hold any security, mutual fund
            scheme, commodity, or financial instrument. Securities investments are subject to market risks. Users are strongly advised
            to consult a certified financial advisor before making any investment decisions.
          </p>
        </div>

        <div className="legal-section">
          <h2>4. User Accounts &amp; Security</h2>
          <p>
            To access subscriber-only reports and dashboard features, you must register for an account with a valid email address.
            You agree to:
          </p>
          <ul>
            <li>Provide accurate, current, and complete registration information.</li>
            <li>Maintain the security and confidentiality of your login credentials.</li>
            <li>Promptly notify us of any unauthorized use or security breach of your account.</li>
            <li>Accept full responsibility for all activities occurring under your account.</li>
          </ul>
        </div>

        <div className="legal-section">
          <h2>5. Subscription, Pricing &amp; Billing</h2>
          <p>
            Wealthyneers offers a monthly institutional membership at ₹30 per month (or as specified during checkout).
            Payments are processed securely via authorized third-party payment gateways (Razorpay).
          </p>
          <ul>
            <li>Subscription fees are billed in advance on a recurring monthly cycle unless cancelled.</li>
            <li>Applicable taxes and transaction fees are calculated during checkout.</li>
            <li>Failure to complete renewal payment will result in the suspension of subscriber-only access.</li>
          </ul>
        </div>

        <div className="legal-section">
          <h2>6. Intellectual Property &amp; Acceptable Use</h2>
          <p>
            All original algorithms, software design, user interfaces, logos, graphics, and report formats are the exclusive
            intellectual property of Wealthyneers.
          </p>
          <p>
            You are granted a non-exclusive, non-transferable, revocable license to access the platform for personal or internal
            analytical use. You agree NOT to:
          </p>
          <ul>
            <li>Scrape, crawl, harvest, or extract data systematically through automated bots or APIs.</li>
            <li>Resell, redistribute, broadcast, or republish raw platform datasets to third parties without prior written consent.</li>
            <li>Attempt to reverse-engineer, decompile, or compromise the website infrastructure.</li>
          </ul>
        </div>

        <div className="legal-section">
          <h2>7. Limitation of Liability</h2>
          <p>
            While we strive for accuracy, mutual fund portfolio disclosures are sourced from regulatory filings and third-party
            disclosures. Wealthyneers provides information on an &quot;as-is&quot; and &quot;as-available&quot; basis and makes no warranties,
            express or implied, regarding data completeness, timeliness, or profitability.
          </p>
          <p>
            In no event shall Wealthyneers, its founders, or affiliates be liable for any direct, indirect, incidental, or consequential
            financial loss resulting from reliance on the data or platform downtime.
          </p>
        </div>

        <div className="legal-section">
          <h2>8. Governing Law &amp; Contact</h2>
          <p>
            These Terms shall be governed by and construed in accordance with the laws of India. Any disputes arising out of or
            relating to these Terms shall be subject to the exclusive jurisdiction of the competent courts in India.
          </p>
          <p>
            If you have any questions regarding these Terms, please reach out through our <Link href="/contact" style={{ color: 'var(--primary)', fontWeight: 600 }}>Contact Page</Link> or
            email us at <a href="mailto:support@wealthyneers.com" style={{ color: 'var(--primary)' }}>support@wealthyneers.com</a>.
          </p>
        </div>
      </div>
    </div>
  );
}
