'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const REPORTS = [
  { href: '/dashboard', label: 'Dashboard', icon: '📊', id: 'dashboard' },
  { href: '/invest', label: 'Invest with Us', title: 'Guided Mutual Funds', icon: '🎯', id: 'invest' },
  { href: '/report1', label: 'Report 1', title: 'Quantity Trend', icon: '📈', id: 'report1' },
  { href: '/report2', label: 'Report 2', title: 'Activity Monitor', icon: '⚡', id: 'report2' },
  { href: '/report3', label: 'Report 3', title: 'AMC Intelligence', icon: '🏢', id: 'report3' },
  { href: '/report4', label: 'Report 4', title: 'Direction Matrix', icon: '🧭', id: 'report4' },
  { href: '/report5', label: 'Report 5', title: 'Breadth Rankings', icon: '🏆', id: 'report5' },
  { href: '/report6', label: 'Report 6', title: '7-Month Consensus', icon: '🌐', id: 'report6' },
];

export default function ReportsNav() {
  const pathname = usePathname();

  // Display this navigation bar on dashboard, invest, and report pages
  const isReportOrDash = pathname === '/dashboard' || pathname === '/invest' || pathname?.startsWith('/report');
  if (!isReportOrDash) return null;

  return (
    <nav className="global-reports-nav">
      <div className="global-reports-nav-inner">
        {REPORTS.map((r) => {
          const reportNum = r.id?.startsWith('report') ? r.id.replace('report', '') : null;
          const isActive =
            pathname === r.href ||
            (reportNum &&
              (pathname === `/report-description/${reportNum}` ||
                pathname === `/reports/report-${reportNum}`));
          return (
            <Link
              key={r.href}
              href={r.href}
              className={`global-nav-tab ${isActive ? 'global-nav-tab-active' : ''}`}
              title={r.title ? `${r.label} — ${r.title}` : r.label}
            >
              <span className="global-nav-icon">{r.icon}</span>
              <span className="global-nav-text">
                <span className="global-nav-label">{r.label}</span>
                {r.title && <span className="global-nav-sub">{r.title}</span>}
              </span>
              {isActive && <span className="global-nav-active-pill" />}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
