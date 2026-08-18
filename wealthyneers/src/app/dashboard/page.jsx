'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { supabase } from '@/lib/supabase';

// ─── Report definitions ──────────────────────────────────────────────
const REPORTS = [
  {
    id: 'report1',
    tag: 'Report 1',
    title: 'Mutual Fund Quantity Trend',
    icon: '📊',
    status: 'live',
    href: '/report1',
    description: 'The foundation report for reconstructing the complete institutional holding history of any security. Shows exactly how much total quantity is held, month by month, across all AMCs and funds.',
  },
  {
    id: 'report2',
    tag: 'Report 2',
    title: 'Monthly Institutional Activity Monitor',
    icon: '⚡',
    status: 'live',
    href: '/report2',
    description: 'Compare the latest mutual-fund portfolio snapshot with the previous month and identify the securities experiencing the largest institutional accumulation, reduction, new positions, or exits.',
  },
  {
    id: 'report3',
    tag: 'Report 3',
    title: 'AMC-wise Stock Intelligence',
    icon: '🏢',
    status: 'live',
    href: '/report3',
    description: 'Isolate any single security and visualize how different mutual-fund AMCs have scaled, held, or liquidated their holdings over time on a multi-line comparison chart.',
  },
  {
    id: 'report4',
    tag: 'Report 4',
    title: 'AMC Direction Matrix',
    icon: '🧭',
    status: 'live',
    href: '/report4',
    description: 'A cross-sectional matrix compressing AMC-level behaviour into directional indicators (🟢 Buying, 🔴 Selling, ⚪ Neutral) across every stock in the equity universe.',
  },
  {
    id: 'report5',
    tag: 'Report 5',
    title: 'Institutional Buying & Selling Rankings',
    icon: '🏆',
    status: 'live',
    href: '/report5',
    description: 'The definitive institutional breadth screener—ranking stocks with the lowest selling pressure first, followed by the highest mutual fund buying consensus.',
  },
  {
    id: 'report6',
    tag: 'Report 6',
    title: '7-Month Institutional Holding Direction',
    icon: '🌐',
    status: 'live',
    href: '/report6',
    description: 'Tracks whether the total institutional quantity held in any security is increasing, decreasing, or flat month-over-month across the 7 most recent consecutive months.',
  },
];

import { getCachedSubscription, checkUserSubscription } from '@/lib/subscriptionCache';

// ─── Main Dashboard ──────────────────────────────────────────────────
export default function DashboardPage() {
  const router = useRouter();
  const [authLoading, setAuthLoading] = useState(true);
  const [isSubscribed, setIsSubscribed] = useState(false);

  // ── Auth + subscription check ──────────────────────────────────────
  useEffect(() => {
    let mounted = true;

    const checkAuth = async () => {
      try {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) {
          if (mounted) router.push('/login');
          return;
        }

        // 1. Instant 0ms cache read
        const cached = getCachedSubscription(session.user.id);
        if (cached && mounted) {
          setIsSubscribed(true);
          setAuthLoading(false);
        }

        // 2. Validate in background / resolve if not cached
        const active = await checkUserSubscription(session.user.id);
        if (mounted) {
          setIsSubscribed(active);
          setAuthLoading(false);
        }
      } catch (err) {
        console.error('Dashboard auth check error:', err);
        if (mounted) setAuthLoading(false);
      }
    };
    checkAuth();

    return () => {
      mounted = false;
    };
  }, [router]);

  // ── Loading ──────────────────────────────────────────────────────
  if (authLoading) {
    return (
      <div className="dash-loading">
        <div className="r6-spinner" />
        <p>Loading your dashboard…</p>
      </div>
    );
  }

  // ── Not subscribed ────────────────────────────────────────────────
  if (!isSubscribed) {
    return (
      <div className="dash-locked">
        <div className="dash-locked-icon">🔒</div>
        <h1>Dashboard Locked</h1>
        <p>Subscribe to Wealthyneers Premium to unlock all six institutional research reports and the interactive dashboard.</p>
        <Link href="/#pricing" className="btn btn-primary" style={{ marginTop: '1.5rem', display: 'inline-block' }}>
          Subscribe Now
        </Link>
      </div>
    );
  }

  // ── Subscribed: Clean Dashboard Grid ──────────────────────────────
  return (
    <div className="dash-page">
      <div className="dash-content">
        <div className="dash-overview">
          <div className="dash-overview-header">
            <h1>Your Research Dashboard</h1>
            <p>Select a report below or from the top navigation bar to explore institutional fund holdings analytics.</p>
          </div>
          <div className="dash-report-grid">
            {REPORTS.map((r) => {
              const reportNum = r.id.replace('report', '');
              return (
                <div
                  key={r.id}
                  className="dash-report-tile dash-tile-live"
                  style={{ display: 'flex', flexDirection: 'column' }}
                >
                  <div
                    className="dash-tile-top"
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: '0.75rem',
                      marginBottom: '1rem',
                      flexWrap: 'wrap',
                    }}
                  >
                    {/* Left: Report Icon + Stacked Tag */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                      <span className="dash-tile-icon" style={{ fontSize: '1.85rem', lineHeight: 1 }}>{r.icon}</span>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.05rem' }}>
                        <span style={{ fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--secondary)' }}>
                          REPORT
                        </span>
                        <span style={{ fontSize: '1rem', fontWeight: 800, color: 'var(--foreground)', lineHeight: 1 }}>
                          {reportNum}
                        </span>
                      </div>
                    </div>

                    {/* Right: Report Description Button + Live Badge */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexShrink: 0 }}>
                      <Link
                        href={`/report-description/${reportNum}`}
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          padding: '0.22rem 0.55rem',
                          borderRadius: '0.375rem',
                          background: 'rgba(56, 189, 248, 0.1)',
                          border: '1px solid rgba(56, 189, 248, 0.28)',
                          color: '#38bdf8',
                          fontSize: '0.72rem',
                          fontWeight: 600,
                          textDecoration: 'none',
                          transition: 'all 0.15s ease',
                          whiteSpace: 'nowrap',
                          letterSpacing: '0.01em',
                        }}
                        title={`View ${r.tag} Description & Visual Preview`}
                      >
                        Report Description
                      </Link>
                      <span
                        className="dash-tile-badge dash-badge-live"
                        style={{
                          fontSize: '0.68rem',
                          fontWeight: 700,
                          padding: '0.2rem 0.55rem',
                          borderRadius: '2rem',
                          letterSpacing: '0.05em',
                        }}
                      >
                        Live
                      </span>
                    </div>
                  </div>
                  <div className="dash-tile-title" style={{ marginTop: '0.25rem' }}>{r.title}</div>
                  <div className="dash-tile-desc">{r.description}</div>
                  <div style={{ marginTop: 'auto', paddingTop: '1.25rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <Link
                      href={r.href}
                      style={{ color: 'var(--primary, #0284c7)', fontWeight: 600, fontSize: '0.875rem', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}
                    >
                      Open {r.tag} →
                    </Link>
                    <Link
                      href={`/report-description/${reportNum}`}
                      style={{ color: 'var(--muted, #94a3b8)', fontSize: '0.8rem', textDecoration: 'none' }}
                    >
                      Preview ↗
                    </Link>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Custom Report / Raw Data Notice */}
          <div className="dash-custom-notice" style={{
            marginTop: '2.5rem',
            padding: '1.5rem 1.75rem',
            background: 'var(--card-bg, #111827)',
            border: '1px solid var(--border, #1f2937)',
            borderRadius: '0.875rem',
            display: 'flex',
            alignItems: 'flex-start',
            gap: '1.25rem',
          }}>
            <div style={{ fontSize: '1.5rem', lineHeight: 1, marginTop: '0.125rem' }}>💡</div>
            <div>
              <h3 style={{ fontSize: '1.0625rem', fontWeight: 600, color: 'var(--foreground, #f9fafb)', margin: '0 0 0.375rem 0' }}>
                Need a custom analysis?
              </h3>
              <p style={{ fontSize: '0.9375rem', color: 'var(--muted, #9ca3af)', margin: 0, lineHeight: 1.6 }}>
                Our reports provide structured insights from our proprietary mutual fund data. If you require raw portfolio data or would like us to create a custom report or analysis, please{' '}
                <Link href="/contact" style={{ color: 'var(--primary, #38bdf8)', textDecoration: 'underline', fontWeight: 500 }}>
                  contact support
                </Link>.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
