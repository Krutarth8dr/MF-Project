'use client';

import Link from 'next/link';
import { useEffect, useState, useRef } from 'react';
import { usePathname } from 'next/navigation';
import { supabase } from '@/lib/supabase';
import { clearSubscriptionCache } from '@/lib/subscriptionCache';

function getInitials(name, email) {
  if (name && typeof name === 'string' && name.trim().length > 0) {
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) {
      return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    }
    return parts[0].substring(0, 2).toUpperCase();
  }
  if (email && typeof email === 'string') {
    return email.substring(0, 2).toUpperCase();
  }
  return 'U';
}

export default function AuthNav() {
  const [user, setUser] = useState(null);
  const [displayName, setDisplayName] = useState('');
  const [initialized, setInitialized] = useState(false);
  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const pathname = usePathname();

  // Close mobile drawer on route change
  useEffect(() => {
    setIsMobileOpen(false);
  }, [pathname]);

  // Handle Escape key to close mobile drawer
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isMobileOpen) {
        setIsMobileOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isMobileOpen]);

  useEffect(() => {
    let mounted = true;

    const syncUser = (authUser) => {
      if (!mounted) return;
      setUser(authUser);

      if (authUser) {
        const name =
          authUser.user_metadata?.full_name ||
          authUser.user_metadata?.name ||
          authUser.email?.split('@')[0] ||
          'Account';
        setDisplayName(name);
      } else {
        setDisplayName('');
      }
      setInitialized(true);
    };

    // 1. Initial Session Check
    supabase.auth.getSession().then(({ data: { session } }) => {
      syncUser(session?.user ?? null);
    }).catch(() => {
      if (mounted) setInitialized(true);
    });

    // 2. Auth State Listener
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      syncUser(session?.user ?? null);
    });

    return () => {
      mounted = false;
      subscription?.unsubscribe();
    };
  }, []);

  const handleLogout = async (e) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    if (isLoggingOut) return;
    setIsLoggingOut(true);

    try {
      setUser(null);
      setDisplayName('');
      clearSubscriptionCache();
      try {
        localStorage.clear();
        sessionStorage.clear();
        document.cookie.split(';').forEach((c) => {
          const name = c.split('=')[0].trim();
          document.cookie = `${name}=; Max-Age=-99999999; path=/;`;
          if (typeof window !== 'undefined' && window.location.hostname) {
            document.cookie = `${name}=; Max-Age=-99999999; path=/; domain=${window.location.hostname};`;
          }
        });
      } catch (_) {}

      // Fire and forget Supabase signOut so page redirect is never blocked
      supabase.auth.signOut({ scope: 'local' }).catch(() => {});
      supabase.auth.signOut().catch(() => {});
    } finally {
      window.location.href = '/login';
    }
  };

  const initials = getInitials(displayName, user?.email);

  return (
    <>
      {/* ── Desktop Navigation Links (Preserved exactly as baseline on >= 769px) ── */}
      <nav className="nav-links desktop-nav-links" style={{ minHeight: '40px', display: 'flex', alignItems: 'center' }}>
        {!initialized ? (
          // Invisible placeholder during initial hydration
          <div style={{ display: 'flex', gap: '1rem', opacity: 0, pointerEvents: 'none' }}>
            <span style={{ fontSize: '0.92rem' }}>Dashboard</span>
            <span style={{ fontSize: '0.92rem' }}>Build Wealth</span>
            <span style={{ width: '80px', height: '32px' }} />
          </div>
        ) : user ? (
          <>
            <Link href="/dashboard" style={{ fontWeight: 600, fontSize: '0.92rem' }}>
              Dashboard
            </Link>
            <Link href="/invest" style={{ fontSize: '0.92rem' }}>
              Build Wealth
            </Link>
            <Link href="/profile" className="nav-profile-pill" title="View Account & Subscription Profile">
              <span className="nav-avatar-circle">{initials}</span>
              <span>{displayName}</span>
            </Link>
            <button
              type="button"
              onClick={handleLogout}
              disabled={isLoggingOut}
              className="btn btn-outline"
              style={{ padding: '0.45rem 1rem', fontSize: '0.85rem' }}
            >
              {isLoggingOut ? 'Logging Out…' : 'Log Out'}
            </button>
          </>
        ) : (
          <>
            <Link href="/#reports">Reports</Link>
            <Link href="/#pricing">Pricing</Link>
            <Link href="/invest">Build Wealth</Link>
            <Link href="/login" className="btn btn-outline">
              Log In
            </Link>
            <Link href="/signup" className="btn btn-primary">
              Sign Up
            </Link>
          </>
        )}
      </nav>

      {/* ── Mobile Hamburger Button (<= 768px) ── */}
      <button
        type="button"
        className="mobile-nav-toggle"
        onClick={() => setIsMobileOpen((prev) => !prev)}
        aria-label={isMobileOpen ? 'Close Navigation Menu' : 'Open Navigation Menu'}
        aria-expanded={isMobileOpen}
      >
        {isMobileOpen ? (
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        ) : (
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="3" y1="6" x2="21" y2="6" />
            <line x1="3" y1="12" x2="21" y2="12" />
            <line x1="3" y1="18" x2="21" y2="18" />
          </svg>
        )}
      </button>

      {/* ── Mobile Navigation Drawer & Backdrop (<= 768px) ── */}
      {isMobileOpen && (
        <div className="mobile-nav-overlay" onClick={() => setIsMobileOpen(false)}>
          <div className="mobile-nav-drawer" onClick={(e) => e.stopPropagation()}>
            {/* Header User Profile or Brand Info */}
            {user ? (
              <div className="mobile-nav-user-header">
                <Link href="/profile" className="mobile-nav-profile-card" onClick={() => setIsMobileOpen(false)}>
                  <span className="nav-avatar-circle mobile-avatar">{initials}</span>
                  <div className="mobile-user-details">
                    <span className="mobile-user-name">{displayName}</span>
                    <span className="mobile-user-subtext">View Profile &amp; Plan &rarr;</span>
                  </div>
                </Link>
              </div>
            ) : (
              <div className="mobile-nav-guest-header">
                <span className="mobile-guest-badge">Institutional MF Research</span>
              </div>
            )}

            {/* Navigation Rows */}
            <div className="mobile-nav-links-list">
              {user ? (
                <>
                  <Link href="/dashboard" className={`mobile-nav-row ${pathname === '/dashboard' ? 'active' : ''}`} onClick={() => setIsMobileOpen(false)}>
                    <span className="mobile-nav-icon">📊</span>
                    <span>Dashboard</span>
                  </Link>
                  <Link href="/invest" className={`mobile-nav-row ${pathname === '/invest' ? 'active' : ''}`} onClick={() => setIsMobileOpen(false)}>
                    <span className="mobile-nav-icon">🎯</span>
                    <span>Build Wealth (Mutual Funds)</span>
                  </Link>
                  <Link href="/report1" className={`mobile-nav-row ${pathname?.startsWith('/report1') ? 'active' : ''}`} onClick={() => setIsMobileOpen(false)}>
                    <span className="mobile-nav-icon">📈</span>
                    <span>Report 1 &bull; Quantity Trend</span>
                  </Link>
                  <Link href="/report2" className={`mobile-nav-row ${pathname?.startsWith('/report2') ? 'active' : ''}`} onClick={() => setIsMobileOpen(false)}>
                    <span className="mobile-nav-icon">⚡</span>
                    <span>Report 2 &bull; Activity Monitor</span>
                  </Link>
                  <Link href="/report3" className={`mobile-nav-row ${pathname?.startsWith('/report3') ? 'active' : ''}`} onClick={() => setIsMobileOpen(false)}>
                    <span className="mobile-nav-icon">🏢</span>
                    <span>Report 3 &bull; AMC Intelligence</span>
                  </Link>
                  <Link href="/report4" className={`mobile-nav-row ${pathname?.startsWith('/report4') ? 'active' : ''}`} onClick={() => setIsMobileOpen(false)}>
                    <span className="mobile-nav-icon">🧭</span>
                    <span>Report 4 &bull; Direction Matrix</span>
                  </Link>
                  <Link href="/report5" className={`mobile-nav-row ${pathname?.startsWith('/report5') ? 'active' : ''}`} onClick={() => setIsMobileOpen(false)}>
                    <span className="mobile-nav-icon">🏆</span>
                    <span>Report 5 &bull; Breadth Rankings</span>
                  </Link>
                  <Link href="/report6" className={`mobile-nav-row ${pathname?.startsWith('/report6') ? 'active' : ''}`} onClick={() => setIsMobileOpen(false)}>
                    <span className="mobile-nav-icon">🌐</span>
                    <span>Report 6 &bull; 7-Month Consensus</span>
                  </Link>
                  <Link href="/profile" className={`mobile-nav-row ${pathname === '/profile' ? 'active' : ''}`} onClick={() => setIsMobileOpen(false)}>
                    <span className="mobile-nav-icon">👤</span>
                    <span>My Account &amp; Billing</span>
                  </Link>
                  <Link href="/contact" className={`mobile-nav-row ${pathname === '/contact' ? 'active' : ''}`} onClick={() => setIsMobileOpen(false)}>
                    <span className="mobile-nav-icon">💬</span>
                    <span>Support &amp; Advisory Desk</span>
                  </Link>
                </>
              ) : (
                <>
                  <Link href="/#reports" className="mobile-nav-row" onClick={() => setIsMobileOpen(false)}>
                    <span className="mobile-nav-icon">📊</span>
                    <span>Research Reports</span>
                  </Link>
                  <Link href="/#pricing" className="mobile-nav-row" onClick={() => setIsMobileOpen(false)}>
                    <span className="mobile-nav-icon">💎</span>
                    <span>Subscription Plan (₹30/mo)</span>
                  </Link>
                  <Link href="/invest" className="mobile-nav-row" onClick={() => setIsMobileOpen(false)}>
                    <span className="mobile-nav-icon">🎯</span>
                    <span>Build Wealth (Mutual Funds)</span>
                  </Link>
                  <Link href="/contact" className="mobile-nav-row" onClick={() => setIsMobileOpen(false)}>
                    <span className="mobile-nav-icon">💬</span>
                    <span>Contact &amp; Support</span>
                  </Link>
                </>
              )}
            </div>

            {/* Bottom Actions */}
            <div className="mobile-nav-footer">
              {user ? (
                <button
                  type="button"
                  onClick={(e) => {
                    setIsMobileOpen(false);
                    handleLogout(e);
                  }}
                  disabled={isLoggingOut}
                  className="btn btn-outline mobile-logout-btn"
                >
                  {isLoggingOut ? 'Logging Out…' : 'Log Out of Account'}
                </button>
              ) : (
                <div className="mobile-auth-actions">
                  <Link href="/login" className="btn btn-outline mobile-auth-btn" onClick={() => setIsMobileOpen(false)}>
                    Log In
                  </Link>
                  <Link href="/signup" className="btn btn-primary mobile-auth-btn" onClick={() => setIsMobileOpen(false)}>
                    Create Account
                  </Link>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
