import Link from 'next/link';

export const metadata = {
  title: 'Refund & Cancellation Policy | Wealthyneers',
  description: 'Refund, cancellation, and billing policies for Wealthyneers digital research subscriptions.',
};

export default function RefundPage() {
  return (
    <div className="legal-page">
      <div className="legal-header">
        <span className="legal-badge">Billing &amp; Payments</span>
        <h1 className="legal-title">Refund &amp; Cancellation Policy</h1>
        <div className="legal-meta">
          Last Updated: August 16, 2026 · Domain: wealthyneers.com
        </div>
      </div>

      <div className="legal-card">
        <div className="legal-section">
          <h2>1. Overview</h2>
          <p>
            At <strong>Wealthyneers</strong>, we strive to deliver transparent, high-quality institutional research analytics.
            This Refund &amp; Cancellation Policy outlines the terms governing subscription purchases, renewals, cancellations,
            and billing disputes for our services on <a href="https://wealthyneers.com" style={{ color: 'var(--primary)' }}>wealthyneers.com</a>.
          </p>
        </div>

        <div className="legal-section">
          <h2>2. Nature of Digital Analytics Services</h2>
          <p>
            Wealthyneers provides instant, uninhibited digital access to proprietary data reports, historical holding trends,
            directional matrices, and ranking tools immediately upon successful payment confirmation.
          </p>
          <div className="legal-callout">
            <strong>Digital Content Delivery:</strong> Because full analytical datasets and interactive reports are made available
            instantly to your account upon purchase, routine refunds for change of mind or subjective dissatisfaction after access
            has been consumed are generally not provided.
          </div>
        </div>

        <div className="legal-section">
          <h2>3. Subscription Cancellation</h2>
          <p>You may choose to discontinue your membership at any time:</p>
          <ul>
            <li>
              <strong>Active Period Retention:</strong> If you cancel or choose not to renew your monthly plan, you will retain full,
              unrestricted access to all subscriber reports until the end of your current 30-day billing cycle.
            </li>
            <li>
              <strong>No Cancellation Penalties:</strong> There are no cancellation fees, lock-in contracts, or hidden exit charges.
            </li>
            <li>
              <strong>Subsequent Cycles:</strong> Once expired, your account simply transitions to a free tier without automated renewed debits.
            </li>
          </ul>
        </div>

        <div className="legal-section">
          <h2>4. Refund Eligibility &amp; Exceptions</h2>
          <p>We review and grant refunds under the following specific circumstances:</p>
          <ul>
            <li>
              <strong>Duplicate / Multiple Charges:</strong> If an electronic glitch or gateway error causes your account or payment method
              to be debited multiple times for a single monthly subscription cycle, the duplicate amount will be refunded in full.
            </li>
            <li>
              <strong>Technical Non-Delivery:</strong> If a confirmed payment is debited by Razorpay but the platform fails to activate
              your subscription access due to an unresolvable technical fault on our end, and our support team is unable to restore access
              within 48 hours of notification.
            </li>
          </ul>
        </div>

        <div className="legal-section">
          <h2>5. How to Request a Billing Review</h2>
          <p>To request assistance for a duplicate charge or billing discrepancy:</p>
          <ol style={{ paddingLeft: '1.5rem', color: 'var(--secondary)', lineHeight: 1.7, fontSize: '0.94rem' }}>
            <li>Locate your Razorpay Payment ID or Order ID from your receipt or bank SMS/email.</li>
            <li>Email our billing support team at <a href="mailto:support@wealthyneers.com" style={{ color: 'var(--primary)' }}>support@wealthyneers.com</a> within <strong>7 business days</strong> of the transaction date.</li>
            <li>Include your registered account email address, transaction reference, and a brief description of the issue.</li>
          </ol>
          <p style={{ marginTop: '0.75rem' }}>
            Approved refunds will be processed back to the original payment source (UPI account, card, or bank account) within <strong>5 to 7 business days</strong>, subject to your bank&apos;s processing timelines.
          </p>
        </div>

        <div className="legal-section">
          <h2>6. Contact Support</h2>
          <p>
            For any queries regarding your billing status or invoice records, visit our <Link href="/contact" style={{ color: 'var(--primary)', fontWeight: 600 }}>Contact Page</Link> or
            reach out directly to <a href="mailto:support@wealthyneers.com" style={{ color: 'var(--primary)' }}>support@wealthyneers.com</a>.
          </p>
        </div>
      </div>
    </div>
  );
}
