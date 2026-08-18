import "./globals.css";
import Link from "next/link";
import Image from "next/image";
import Script from "next/script";
import AuthNav from "./components/AuthNav";
import ReportsNav from "./components/ReportsNav";

export const metadata = {
  title: "Wealthyneers | Premium Data Reports",
  description: "Exclusive, actionable institutional mutual fund data reports to power your investment decisions.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <Script
          src="https://checkout.razorpay.com/v1/checkout.js"
          strategy="afterInteractive"
        />
        {/* ── Global Header ── */}
        <header className="header">
          <div className="container header-content">
            <div className="logo">
              <Link href="/" style={{ display: "flex", alignItems: "center", textDecoration: "none" }}>
                <Image
                  src="/wealthyneers-logo.png"
                  alt="Wealthyneers — Seizing Future"
                  width={180}
                  height={54}
                  style={{ objectFit: "contain", height: "44px", width: "auto" }}
                  priority
                />
              </Link>
            </div>
            <AuthNav />
          </div>
        </header>

        {/* ── Secondary Reports Tab Bar (visible on dashboard & report routes) ── */}
        <ReportsNav />

        {/* ── Main Route Content ── */}
        {children}

        {/* ── Production Footer ── */}
        <footer className="site-footer">
          <div className="container">
            <div className="footer-top">
              {/* Brand Col */}
              <div className="footer-brand">
                <Link href="/" className="footer-logo">
                  <Image
                    src="/wealthyneers-logo.png"
                    alt="Wealthyneers — Seizing Future"
                    width={160}
                    height={48}
                    style={{ objectFit: "contain", height: "40px", width: "auto" }}
                  />
                </Link>
                <p className="footer-tagline">
                  Actionable institutional mutual fund intelligence, historical quantity trends,
                  cross-AMC directional matrices, and conviction breadth screeners.
                </p>
              </div>

              {/* Research Reports Col */}
              <div className="footer-col">
                <h4>Research Reports</h4>
                <ul className="footer-links">
                  <li><Link href="/dashboard">Dashboard</Link></li>
                  <li><Link href="/report1">Report 1 · Quantity Trend</Link></li>
                  <li><Link href="/report2">Report 2 · Activity Monitor</Link></li>
                  <li><Link href="/report3">Report 3 · AMC Intelligence</Link></li>
                  <li><Link href="/report4">Report 4 · Direction Matrix</Link></li>
                  <li><Link href="/report5">Report 5 · Breadth Rankings</Link></li>
                  <li><Link href="/report6">Report 6 · 7-Month Consensus</Link></li>
                </ul>
              </div>

              {/* Legal & Policies Col */}
              <div className="footer-col">
                <h4>Legal &amp; Policies</h4>
                <ul className="footer-links">
                  <li><Link href="/terms">Terms &amp; Conditions</Link></li>
                  <li><Link href="/privacy">Privacy Policy</Link></li>
                  <li><Link href="/refund">Refund Policy</Link></li>
                  <li><Link href="/contact">Contact &amp; Support</Link></li>
                </ul>
              </div>

              {/* Account & Platform Col */}
              <div className="footer-col">
                <h4>Platform</h4>
                <ul className="footer-links">
                  <li><Link href="/invest">Invest in Mutual Funds</Link></li>
                  <li><Link href="/#pricing">Subscription (₹30/mo)</Link></li>
                  <li><Link href="/profile">My Account &amp; Profile</Link></li>
                  <li><Link href="/login">Subscriber Login</Link></li>
                  <li><Link href="/signup">Create Account</Link></li>
                  <li><Link href="/forgot-password">Forgot Password</Link></li>
                </ul>
              </div>
            </div>

            {/* Disclaimer Bar */}
            <div className="footer-disclaimer-wrap">
              <p className="footer-disclaimer">
                <strong>Disclaimer:</strong> Wealthyneers is a financial research, analytical data intelligence, and visualization platform
                developed for informational and educational purposes only. Wealthyneers is not a SEBI-registered investment advisor or portfolio
                manager. All mutual fund holding distributions and directional analytics are compiled from public statutory disclosures. Securities
                investments are subject to market risks. Please consult a qualified financial professional before making investment decisions.
              </p>
            </div>

            {/* Bottom Row */}
            <div className="footer-bottom">
              <div>
                © {new Date().getFullYear()} Wealthyneers. All rights reserved.
              </div>
              <div style={{ display: "flex", gap: "1.5rem" }}>
                <Link href="/terms" style={{ color: "inherit", textDecoration: "none" }}>Terms</Link>
                <Link href="/privacy" style={{ color: "inherit", textDecoration: "none" }}>Privacy</Link>
                <Link href="/refund" style={{ color: "inherit", textDecoration: "none" }}>Refunds</Link>
                <Link href="/contact" style={{ color: "inherit", textDecoration: "none" }}>Contact</Link>
              </div>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
