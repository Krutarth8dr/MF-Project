import Link from 'next/link';

export const metadata = {
  title: 'Contact & Support | Wealthyneers',
  description: 'Get in touch with the Wealthyneers team for technical support, billing inquiries, or account assistance.',
};

export default function ContactPage() {
  return (
    <div className="legal-page">
      <div className="legal-header">
        <span className="legal-badge">Help &amp; Inquiries</span>
        <h1 className="legal-title">Contact &amp; Support</h1>
        <div className="legal-meta">
          We&apos;re here to assist you with account access, subscriptions, and platform questions.
        </div>
      </div>

      <div className="legal-card" style={{ marginBottom: '2rem' }}>
        <div className="legal-section">
          <h2>Direct Support Channels</h2>
          <p>
            Have a question about your subscription, data reports, or technical issues? Choose the relevant channel below:
          </p>

          <div className="contact-grid">
            <div className="contact-card-item">
              <div className="contact-card-icon">✉️</div>
              <div className="contact-card-title">General &amp; Technical Support</div>
              <div className="contact-card-desc">
                For account verification, password recovery, report questions, or feature feedback.
              </div>
              <a href="mailto:support@wealthyneers.com?subject=General%20%26%20Technical%20Support" className="contact-card-link">
                support@wealthyneers.com →
              </a>
            </div>

            <div className="contact-card-item">
              <div className="contact-card-icon">💳</div>
              <div className="contact-card-title">Billing &amp; Subscriptions</div>
              <div className="contact-card-desc">
                For Razorpay invoice assistance, payment confirmations, or duplicate charge inquiries.
              </div>
              <a href="mailto:support@wealthyneers.com?subject=Billing%20Inquiry" className="contact-card-link">
                support@wealthyneers.com →
              </a>
            </div>

            <div className="contact-card-item">
              <div className="contact-card-icon">⏱️</div>
              <div className="contact-card-title">Support Hours &amp; Response</div>
              <div className="contact-card-desc">
                Monday – Friday: 9:30 AM to 6:30 PM IST.<br />
                Typical response turnaround: <strong>within 24 to 48 hours</strong>.
              </div>
              <span style={{ fontSize: '0.85rem', color: 'var(--secondary)', marginTop: 'auto', paddingTop: '0.5rem' }}>
                Online Support Desk
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Frequently Asked Questions Card */}
      <div className="legal-card">
        <div className="legal-section">
          <h2>Frequently Asked Questions</h2>

          <h3>How soon is my subscription activated after payment?</h3>
          <p>
            Subscription activation is fully automated and instantaneous. As soon as your Razorpay transaction completes,
            your account status flips to Active and all 6 reports and Dashboard features unlock immediately.
          </p>

          <h3>How do I reset my account password?</h3>
          <p>
            You can request a password reset link at any time from our <Link href="/forgot-password" style={{ color: 'var(--primary)', fontWeight: 600 }}>Forgot Password Page</Link>.
            If you are already logged in, you can update your password directly on your <Link href="/profile" style={{ color: 'var(--primary)', fontWeight: 600 }}>Account Profile</Link>.
          </p>

          <h3>Where does Wealthyneers get its mutual fund holding data?</h3>
          <p>
            Our analytics engines aggregate and synthesize monthly portfolio disclosures published by registered Indian Asset Management
            Companies (AMCs) and mutual fund houses in compliance with statutory disclosure norms.
          </p>

          <h3>Need to review our legal terms or refund guidelines?</h3>
          <p>
            Please visit our <Link href="/terms" style={{ color: 'var(--primary)', fontWeight: 600 }}>Terms &amp; Conditions</Link>,{' '}
            <Link href="/privacy" style={{ color: 'var(--primary)', fontWeight: 600 }}>Privacy Policy</Link>, and{' '}
            <Link href="/refund" style={{ color: 'var(--primary)', fontWeight: 600 }}>Refund Policy</Link> for detailed documentation.
          </p>
        </div>
      </div>
    </div>
  );
}
