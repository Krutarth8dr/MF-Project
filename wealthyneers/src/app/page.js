'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from "next/link";
import { supabase } from '@/lib/supabase';

import { startRazorpayCheckout, loadRazorpaySDK } from '@/lib/razorpay';
import { getCachedSubscription, checkUserSubscription, setCachedSubscription } from '@/lib/subscriptionCache';

export default function Home() {
  const router = useRouter();
  const [user, setUser] = useState(null);
  const [isSubscribed, setIsSubscribed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [paying, setPaying] = useState(false);

  useEffect(() => {
    let mounted = true;

    const syncUserSubscription = async (currentUser) => {
      if (!currentUser) {
        if (mounted) {
          setUser(null);
          setIsSubscribed(false);
          setLoading(false);
        }
        return;
      }

      if (mounted) {
        setUser(currentUser);
        // 1. Instant 0ms cache check (prevents locked flash)
        const cached = getCachedSubscription(currentUser.id);
        if (cached) {
          setIsSubscribed(true);
        }
        setLoading(false);
      }

      // 2. Silent background validation with Supabase
      try {
        const active = await checkUserSubscription(currentUser.id);
        if (mounted) {
          setIsSubscribed(active);
        }
      } catch (e) {
        console.warn('Subscription background check error:', e);
      }
    };

    // Initial session lookup
    supabase.auth.getSession().then(({ data: { session } }) => {
      syncUserSubscription(session?.user ?? null);
    }).catch(() => {
      if (mounted) setLoading(false);
    });

    // Auth listener (only runs on state change)
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      syncUserSubscription(session?.user ?? null);
    });

    // Pre-warm Razorpay SDK in background
    loadRazorpaySDK().catch(() => {});

    return () => {
      mounted = false;
      subscription?.unsubscribe();
    };
  }, []);

  const [checkoutError, setCheckoutError] = useState(null);

  const handleSubscribe = () => {
    if (!user) {
      router.push('/signup');
      return;
    }

    setPaying(true);
    setCheckoutError(null);

    // Fallback safety timeout so button never gets stuck
    const safetyTimer = setTimeout(() => {
      setPaying((current) => {
        if (current) {
          setCheckoutError('Checkout is taking longer than expected. Please check your internet connection or reload.');
          return false;
        }
        return current;
      });
    }, 12000);

    startRazorpayCheckout({
      user,
      onOpen: () => {
        clearTimeout(safetyTimer);
        setPaying(false);
      },
      onSuccess: () => {
        clearTimeout(safetyTimer);
        setIsSubscribed(true);
        setPaying(false);
        router.push('/dashboard');
      },
      onError: (msg) => {
        clearTimeout(safetyTimer);
        setCheckoutError(msg || 'Payment failed or was declined.');
        setPaying(false);
      },
      onDismiss: () => {
        clearTimeout(safetyTimer);
        setPaying(false);
      },
    });
  };

  const reports = [
    {
      id: 1,
      tag: "Report 1",
      title: "Mutual Fund Quantity Trend",
      desc: "The foundation report for reconstructing institutional holding history of any security. Filter by security, AMC, fund, and industry to analyze long-term accumulation, distribution, and turning points.",
      icon: "📊",
      href: "/report1",
    },
    {
      id: 2,
      tag: "Report 2",
      title: "Monthly Institutional Activity Monitor",
      desc: "Compares the latest portfolio snapshot with previous months. A practical buying and selling scanner tracking largest increases, decreases, new positions, and total exits.",
      icon: "⚡",
      href: "/report2",
    },
    {
      id: 3,
      tag: "Report 3",
      title: "AMC-wise Stock Intelligence",
      desc: "Isolates a single security and compares how different AMCs have changed positions over time. See which AMC accumulated first, exposure levels, and institutional agreement.",
      icon: "🏢",
      href: "/report3",
    },
    {
      id: 4,
      tag: "Report 4",
      title: "AMC Direction Matrix",
      desc: "A cross-sectional matrix compressing AMC-level behaviour into directional indicators across the equity universe, making institutional alignment or disagreement easy to scan.",
      icon: "🧭",
      href: "/report4",
    },
    {
      id: 5,
      tag: "Report 5",
      title: "Institutional Buying & Selling Rankings",
      desc: "The ranking engine converting AMC activity into actionable shortlists using Total Buying/Selling AMC Counts, Net Buying Scores, and conviction breadth.",
      icon: "🏆",
      href: "/report5",
    },
    {
      id: 6,
      tag: "Report 6",
      title: "7-Month Institutional Holding Direction",
      desc: "A universe-level view highlighting how widely an institutional thesis is shared across asset managers. Identify broad high-consensus names and divergent debate candidates.",
      icon: "🌐",
      href: "/report6",
    },
  ];

  return (
    <main>
      {!loading && !user && (
        <section className="hero">
          <div className="container">
            <h1>See what top DIIs of India doing</h1>
            <p style={{ marginBottom: '0.85rem' }}>
              Get exclusive access to our 6 proprietary institutional research reports, designed for serious investors who demand institutional-grade insights.
            </p>
            <p style={{ marginBottom: '2.5rem' }}>
              Track what leading AMCs are buying, holding, and selling through interactive reports.
            </p>
            <div className="hero-cta">
              <Link href="/signup" className="btn btn-primary" style={{ fontSize: '1.25rem', padding: '1rem 2.5rem' }}>
                Get Started Free
              </Link>
              <Link href="/login" className="btn btn-outline" style={{ fontSize: '1.1rem', padding: '0.85rem 2rem' }}>
                Log In →
              </Link>
            </div>
            <p className="hero-subtext">Already have an account? <Link href="/login">Sign in here</Link></p>
          </div>
        </section>
      )}

      <section id="reports" className="reports">
        <div className="container">
          {!loading && !isSubscribed && (
            <div className="reports-teaser-box">
              <h3 className="reports-teaser-title">
                Top 5 Most Bought Securities Last Month
              </h3>
              <div className="reports-teaser-list">
                <span className="teaser-sec">Adani Enterprises Ltd.</span>
                <span className="teaser-sep" aria-hidden="true">|</span>
                <span className="teaser-sec">Torrent Pharmaceuticals Ltd.</span>
                <span className="teaser-sep" aria-hidden="true">|</span>
                <span className="teaser-sec">PB Fintech Ltd.</span>
                <span className="teaser-sep" aria-hidden="true">|</span>
                <span className="teaser-sec">SBI Funds Management Ltd.</span>
                <span className="teaser-sep" aria-hidden="true">|</span>
                <span className="teaser-sec">Indo-MIM Ltd.</span>
              </div>
              <div className="reports-teaser-cta-wrap">
                <Link href="#pricing" className="reports-teaser-cta">
                  Subscribe for more →
                </Link>
              </div>
            </div>
          )}

          <h2 className="section-title">Our Premium Research Reports</h2>

          {!loading && user && isSubscribed && (
            <div className="reports-sub-banner" style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
              <p style={{ fontSize: '1.1rem', color: 'var(--secondary)', marginBottom: '0.5rem' }}>
                You have active premium access to all 6 institutional reports.
              </p>
              <p style={{ fontSize: '1.1rem', color: 'var(--secondary)', marginBottom: '1.5rem' }}>
                Track what leading AMCs are buying, holding, and selling through interactive reports.
              </p>
              <Link
                href="/dashboard"
                className="btn btn-primary"
                style={{ fontSize: '1rem', padding: '0.65rem 1.75rem', display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}
              >
                Head over to Dashboard →
              </Link>
            </div>
          )}

          <div className="reports-grid">
            {reports.map((report) => (
              <div key={report.id} className="report-card" style={{ display: 'flex', flexDirection: 'column' }}>
                <div className="report-top" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <div className="report-icon">{report.icon}</div>
                      <span className="report-badge">{report.tag}</span>
                      <Link
                        href={`/report-description/${report.id}`}
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          padding: '0.2rem 0.65rem',
                          borderRadius: '0.375rem',
                          background: 'rgba(56, 189, 248, 0.1)',
                          border: '1px solid rgba(56, 189, 248, 0.3)',
                          color: '#38bdf8',
                          fontSize: '0.75rem',
                          fontWeight: 600,
                          textDecoration: 'none',
                          whiteSpace: 'nowrap',
                        }}
                        title={`Read ${report.tag} How To Use Guide`}
                      >
                        How To Use
                      </Link>
                    </div>
                </div>
                <h3 className="report-title">{report.title}</h3>
                <p className="report-desc">{report.desc}</p>
                
                {!isSubscribed ? (
                  <div className="locked" style={{ marginTop: 'auto', paddingTop: '1rem' }}>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                      <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                    </svg>
                    Subscribers Only
                  </div>
                ) : (
                  <div style={{ marginTop: 'auto', paddingTop: '1rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <Link
                      href={report.href}
                      style={{ fontSize: '0.88rem', fontWeight: 600, color: 'var(--primary, #0284c7)', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}
                    >
                      Open {report.tag} →
                    </Link>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

        <section id="pricing" className="pricing">
          <div className="container">
            <div className="pricing-card">
              <span className="pricing-plan-tag">
                {isSubscribed ? '● Active Access' : '30-Day Institutional Access'}
              </span>
              <h2 style={{ marginTop: '0.5rem', marginBottom: '0.25rem' }}>Wealthyneers 30-Day Access</h2>
              <p style={{ color: 'var(--secondary)', fontSize: '0.95rem' }}>
                {isSubscribed
                  ? 'Your institutional intelligence access is currently active.'
                  : 'One simple one-time payment. Complete access to all six institutional research reports for 30 days.'}
              </p>
              
              <div className="price-single-wrap">
                <span className="price-single-currency">₹</span>
                <span className="price-single-val">30</span>
                <span className="price-single-period">for 30 days</span>
              </div>
              
              <ul className="features">
                <li>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#05bfdb" strokeWidth="2"><polyline points="20 6 9 17 4 12"/></svg>
                  <span>Complete access to <strong>all 6 institutional reports</strong> (Reports 1 to 6)</span>
                </li>
                <li>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#05bfdb" strokeWidth="2"><polyline points="20 6 9 17 4 12"/></svg>
                  <span>Comprehensive monthly coverage across <strong>13+ AMCs and 225+ funds</strong></span>
                </li>
                <li>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#05bfdb" strokeWidth="2"><polyline points="20 6 9 17 4 12"/></svg>
                  <span>Historical quantity trends, directional matrices &amp; breadth rankings</span>
                </li>
                <li>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#05bfdb" strokeWidth="2"><polyline points="20 6 9 17 4 12"/></svg>
                  <span>Interactive web dashboards with custom filters &amp; multi-AMC comparison tools</span>
                </li>
              </ul>

              {checkoutError && (
                <div
                  style={{
                    color: '#dc2626',
                    backgroundColor: 'rgba(220, 38, 38, 0.08)',
                    border: '1px solid rgba(220, 38, 38, 0.25)',
                    padding: '0.75rem 1rem',
                    borderRadius: '0.5rem',
                    fontSize: '0.875rem',
                    marginBottom: '1rem',
                    textAlign: 'left',
                    lineHeight: 1.45,
                  }}
                >
                  ⚠️ {checkoutError}
                </div>
              )}

              {isSubscribed ? (
                <Link
                  href="/dashboard"
                  className="btn btn-primary"
                  style={{ width: '100%', fontSize: '1.2rem', padding: '0.9rem', display: 'block', textAlign: 'center', fontWeight: 700, textDecoration: 'none' }}
                >
                  Go to Research Dashboard →
                </Link>
              ) : user ? (
                <button
                  type="button"
                  onClick={handleSubscribe}
                  disabled={paying}
                  className="btn btn-primary"
                  style={{ width: '100%', fontSize: '1.2rem', padding: '0.9rem', display: 'block', textAlign: 'center', fontWeight: 700 }}
                >
                  {paying ? 'Opening Checkout…' : 'Get Access Now — ₹30 for 30 days'}
                </button>
              ) : (
                <Link
                  href="/signup"
                  className="btn btn-primary"
                  style={{ width: '100%', fontSize: '1.2rem', padding: '0.9rem', display: 'block', textAlign: 'center', fontWeight: 700, textDecoration: 'none' }}
                >
                  Get Access Now — ₹30 for 30 days
                </Link>
              )}
              <div className="upi-badge">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
                Instant Access via Razorpay (Supports all UPI Apps)
              </div>
            </div>
          </div>
        </section>
    </main>
  );
}
