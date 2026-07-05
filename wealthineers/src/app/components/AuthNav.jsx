'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { supabase } from '@/lib/supabase';

export default function AuthNav() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    let mounted = true;

    const loadSession = async () => {
      const {
        data: { session },
      } = await supabase.auth.getSession();

      if (mounted) {
        setUser(session?.user ?? null);
        setLoading(false);
      }
    };

    loadSession();

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
      setLoading(false);
    });

    return () => {
      mounted = false;
      subscription.unsubscribe();
    };
  }, []);

  const handleLogout = async () => {
    await supabase.auth.signOut();
    setUser(null);
    router.push('/');
    router.refresh();
  };

  return (
    <nav className="nav-links">
      <Link href="/#reports">Reports</Link>
      <Link href="/#pricing">Pricing</Link>
      <Link href="/dashboard">Dashboard</Link>

      {loading ? null : user ? (
        <button type="button" onClick={handleLogout} className="btn btn-outline">
          Log Out
        </button>
      ) : (
        <>
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
