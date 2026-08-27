import Link from 'next/link';

export const metadata = {
  title: 'Privacy Policy | Wealthyneers',
  description: 'Privacy Policy describing how Wealthyneers collects, handles, and protects your personal and account data.',
};

export default function PrivacyPage() {
  return (
    <div className="legal-page">
      <div className="legal-header">
        <span className="legal-badge">Privacy &amp; Data Protection</span>
        <h1 className="legal-title">Privacy Policy</h1>
        <div className="legal-meta">
          Last Updated: August 16, 2026 · Domain: wealthyneers.com
        </div>
      </div>

      <div className="legal-card">
        <div className="legal-section">
          <h2>1. Introduction</h2>
          <p>
            At <strong>Wealthyneers</strong> (&quot;we&quot;, &quot;our&quot;, or &quot;us&quot;), respecting and protecting your privacy is our core commitment.
            This Privacy Policy explains how we collect, store, utilize, and protect your information when you visit and use our website
            (<a href="https://wealthyneers.com" style={{ color: 'var(--primary)' }}>wealthyneers.com</a>) and our subscription services.
          </p>
        </div>

        <div className="legal-section">
          <h2>2. Information We Collect</h2>
          <p>We collect only the minimal information strictly required to deliver our analytical services:</p>
          <ul>
            <li>
              <strong>Account Information:</strong> Your email address and full name (if provided during signup or profile update)
              required for user authentication, password recovery, and communication.
            </li>
            <li>
              <strong>Payment &amp; Transaction Identifiers:</strong> When you subscribe, our payment partner (Razorpay) generates
              unique payment and order IDs. We record these transaction reference IDs, subscription start/end dates, and payment status
              to authorize your report access. <em>We never store credit/debit card details, bank account credentials, or UPI PINs on our servers.</em>
            </li>
            <li>
              <strong>Technical &amp; Log Data:</strong> Standard access logs, browser type, device information, and IP addresses
              for security monitoring, fraud prevention, and server performance optimization.
            </li>
          </ul>
        </div>

        <div className="legal-section">
          <h2>3. How We Use Your Information</h2>
          <p>Your data is processed exclusively for the following operational purposes:</p>
          <ul>
            <li>Authenticating your user session and managing your subscriber permissions.</li>
            <li>Processing subscription payments and validating active access to Reports 1 through 6.</li>
            <li>Sending critical transactional notices (account verification, password reset links, billing confirmations).</li>
            <li>Maintaining the security, performance, and integrity of the platform.</li>
          </ul>
          <p>
            <strong>We do NOT sell, rent, monetize, or share your personal contact information with third-party advertisers or data brokers.</strong>
          </p>
        </div>

        <div className="legal-section">
          <h2>4. Third-Party Service Providers</h2>
          <p>We partner with vetted, industry-leading infrastructure and payment partners:</p>
          <ul>
            <li>
              <strong>Supabase Inc.:</strong> Cloud database and authentication infrastructure providing encrypted user storage and Row Level Security.
            </li>
            <li>
              <strong>Razorpay Software Pvt. Ltd.:</strong> RBI-authorized payment aggregator managing checkout, UPI, cards, and net banking transactions under PCI-DSS Level 1 compliance.
            </li>
          </ul>
        </div>

        <div className="legal-section">
          <h2>5. Data Security &amp; Retention</h2>
          <p>
            We implement strict security measures, including HTTPS/TLS 1.3 encryption across all website routes, strict HTTP security headers
            (anti-clickjacking, MIME protection), and server-side cryptographic signature verification for payment transactions.
          </p>
          <p>
            We retain account data for as long as your account is active or as necessary to comply with applicable statutory accounting and tax regulations.
          </p>
        </div>

        <div className="legal-section">
          <h2>6. Your Rights &amp; Choices</h2>
          <p>You have full control over your personal account details:</p>
          <ul>
            <li>You can view and update your personal information or change your password at any time via your <Link href="/profile" style={{ color: 'var(--primary)', fontWeight: 600 }}>Profile Page</Link>.</li>
            <li>You can request a copy of your account data or request account deletion by emailing our privacy team.</li>
          </ul>
        </div>

        <div className="legal-section">
          <h2>7. Contact Us</h2>
          <p>
            If you have questions, feedback, or concerns regarding our Privacy Policy or data handling practices, please contact us at:
          </p>
          <p>
            <strong>Email:</strong> <a href="mailto:support@wealthyneers.com" style={{ color: 'var(--primary)' }}>support@wealthyneers.com</a><br />
            <strong>Support Page:</strong> <Link href="/contact" style={{ color: 'var(--primary)' }}>wealthyneers.com/contact</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
