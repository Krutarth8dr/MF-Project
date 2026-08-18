'use client';

import { useState } from 'react';
import { supabase } from '@/lib/supabase';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

export default function SignUp() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [signedUp, setSignedUp] = useState(false);
  const router = useRouter();

  const handleSignUp = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const { data, error } = await supabase.auth.signUp({
      email: email.trim(),
      password,
      options: {
        data: {
          full_name: fullName.trim(),
        },
      },
    });

    if (error) {
      setError(error.message || 'Failed to create account.');
      setLoading(false);
    } else {
      // If auto-confirmed or session is active, redirect to home
      if (data?.session) {
        router.push('/');
        router.refresh();
      } else {
        // Email confirmation is required by Supabase
        setSignedUp(true);
        setLoading(false);
      }
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h1>Create Account</h1>
        <p>Join Wealthyneers to get premium insights</p>

        {error && (
          <div
            style={{
              color: '#dc2626',
              backgroundColor: 'rgba(220, 38, 38, 0.08)',
              border: '1px solid rgba(220, 38, 38, 0.25)',
              padding: '0.75rem 1rem',
              borderRadius: '0.5rem',
              fontSize: '0.875rem',
              marginBottom: '1.25rem',
              lineHeight: 1.45,
            }}
          >
            ⚠️ {error}
          </div>
        )}

        {signedUp ? (
          <div>
            <div
              style={{
                color: '#059669',
                backgroundColor: 'rgba(5, 150, 105, 0.08)',
                border: '1px solid rgba(5, 150, 105, 0.25)',
                padding: '1.25rem',
                borderRadius: '0.5rem',
                fontSize: '0.9rem',
                lineHeight: 1.5,
                marginBottom: '1.5rem',
              }}
            >
              <strong>✓ Account Successfully Created!</strong>
              <p style={{ margin: '0.5rem 0 0', color: 'inherit', fontSize: '0.85rem' }}>
                We have sent a verification email to <strong>{email}</strong>.
                Please check your inbox and click the confirmation link to activate your access.
              </p>
            </div>

            <Link
              href="/login"
              className="btn btn-primary"
              style={{ width: '100%', display: 'block', textAlign: 'center', textDecoration: 'none' }}
            >
              Proceed to Log In
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSignUp}>
            <div className="form-group">
              <label htmlFor="fullName">Full Name</label>
              <input
                id="fullName"
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="John Doe"
                autoComplete="name"
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="email">Email Address</label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                autoComplete="email"
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="password">Password</label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                autoComplete="new-password"
                required
                minLength={6}
              />
            </div>

            <button
              type="submit"
              className="btn btn-primary"
              style={{ width: '100%', marginTop: '1rem' }}
              disabled={loading}
            >
              {loading ? 'Creating Account...' : 'Sign Up'}
            </button>

            <div className="auth-link">
              Already have an account? <Link href="/login">Log in</Link>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
