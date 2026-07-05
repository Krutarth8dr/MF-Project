import "./globals.css";
import Link from "next/link";
import AuthNav from "./components/AuthNav";

export const metadata = {
  title: "Wealthineers | Premium Data Reports",
  description: "Exclusive, actionable data reports to power your investment decisions.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <header className="header">
          <div className="container header-content">
            <div className="logo">
              <Link href="/" style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "inherit", textDecoration: "none" }}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" /></svg>
                Wealthineers
              </Link>
            </div>
            <AuthNav />
          </div>
        </header>
        {children}
        <footer className="footer">
          <p>© 2026 Wealthineers. All rights reserved.</p>
        </footer>
      </body>
    </html>
  );
}
