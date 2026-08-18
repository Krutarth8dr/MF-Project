'use client';

import { useState } from 'react';
import { supabase } from '@/lib/supabase';
import Link from 'next/link';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);

  const handleResetRequest = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccess(false);

    const cleanEmail = email.trim();
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!cleanEmail || !emailRegex.test(cleanEmail)) {
      setError('Please enter a valid email address.');
      setLoading(false);
      return;
    }

    try {
      // Determine redirectTo based on environment
      const redirectToUrl = typeof window !== 'undefined'
        ? `${window.location.origin}/reset-password`
        : 'https://wealthyneers.com/reset-password';

      const { error: resetError } = await supabase.auth.resetPasswordForEmail(cleanEmail, {
        redirectTo: redirectToUrl,
      });

      if (resetError) {
        setError(resetError.message || 'Unable to send password reset email. Please try again.');
      } else {
        setSuccess(true);
      }
    } catch (err) {
      console.error('Password reset request error:', err);
      setError('An unexpected error occurred. Please try again later.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h1>Forgot Password</h1>
        <p>Enter your account email to receive a password reset link</p>

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

        {success ? (
          <div>
            <div
              style={{
                color: '#059669',
                backgroundColor: 'rgba(5, 150, 105, 0.08)',
                border: '1px solid rgba(5, 150, 105, 0.25)',
                padding: '1rem',
                borderRadius: '0.5rem',
                fontSize: '0.9rem',
                lineHeight: 1.5,
                marginBottom: '1.5rem',
              }}
            >
              <strong>✓ Password Reset Email Sent</strong>
              <p style={{ margin: '0.5rem 0 0', color: 'inherit', fontSize: '0.85rem', textAlign: 'left' }}>
                If an account exists for <strong>{email}</strong>, we have sent instructions to reset your password.
                Please check your inbox and spam folder.
              </p>
            </div>

            <Link
              href="/login"
              className="btn btn-primary"
              style={{ width: '100%', display: 'block', textAlign: 'center', textDecoration: 'none' }}
            >
              Return to Log In
            </Link>
          </div>
        ) : (
          <form onSubmit={handleResetRequest}>
            <div className="form-group">
              <label htmlFor="email">Registered Email Address</label>
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

            <button
              type="submit"
              className="btn btn-primary"
              style={{ width: '100%', marginTop: '0.5rem' }}
              disabled={loading}
            >
              {loading ? 'Sending Reset Link…' : 'Send Password Reset Link'}
            </button>

            <div className="auth-link">
              Remember your password? <Link href="/login">Back to Log In</Link>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
