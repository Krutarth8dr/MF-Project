'use client';

import Link from 'next/link';
import { useEffect, useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { supabase } from '@/lib/supabase';

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
  const currentUserIdRef = useRef(null);
  const router = useRouter();

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

  const handleLogout = async () => {
    try {
      await supabase.auth.signOut();
    } catch (e) {
      console.warn('Sign out error:', e);
    } finally {
      try {
        localStorage.clear();
        sessionStorage.clear();
        // Clear all cookies
        document.cookie.split(';').forEach((c) => {
          document.cookie = c
            .replace(/^ +/, '')
            .replace(/=.*/, '=;expires=' + new Date(0).toUTCString() + ';path=/');
        });
      } catch (_) {}
      setUser(null);
      window.location.replace('/login');
    }
  };

  const initials = getInitials(displayName, user?.email);

  return (
    <nav className="nav-links" style={{ minHeight: '40px', display: 'flex', alignItems: 'center' }}>
      {!initialized ? (
        // Invisible placeholder during initial 50ms hydration to prevent navbar collapse/flicker
        <div style={{ display: 'flex', gap: '1rem', opacity: 0, pointerEvents: 'none' }}>
          <span style={{ fontSize: '0.92rem' }}>Dashboard</span>
          <span style={{ fontSize: '0.92rem' }}>Invest with Us</span>
          <span style={{ width: '80px', height: '32px' }} />
        </div>
      ) : user ? (
        <>
          <Link href="/dashboard" style={{ fontWeight: 600, fontSize: '0.92rem' }}>
            Dashboard
          </Link>
          <Link href="/invest" style={{ fontSize: '0.92rem' }}>
            Invest with Us
          </Link>
          <Link href="/profile" className="nav-profile-pill" title="View Account & Subscription Profile">
            <span className="nav-avatar-circle">{initials}</span>
            <span>{displayName}</span>
          </Link>
          <button
            type="button"
            onClick={handleLogout}
            className="btn btn-outline"
            style={{ padding: '0.45rem 1rem', fontSize: '0.85rem' }}
          >
            Log Out
          </button>
        </>
      ) : (
        <>
          <Link href="/#reports">Reports</Link>
          <Link href="/#pricing">Pricing</Link>
          <Link href="/invest">Invest with Us</Link>
          <Link href="/login" className="btn btn-outline">
            Log In
          </Link>
          <Link href="/signup" className="btn btn-primary">
            Sign Up
          </Link>
        </>
      )}
    </nav>
  );
}
