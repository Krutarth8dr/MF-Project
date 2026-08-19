'use client';

import { useState, useEffect, useMemo } from 'react';
import { supabase } from '@/lib/supabase';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { checkPasswordRequirements } from '@/lib/validation';

export default function ResetPasswordPage() {
  const router = useRouter();
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [sessionChecking, setSessionChecking] = useState(true);
  const [hasValidSession, setHasValidSession] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    let mounted = true;

    // Check if an active recovery session exists
    const verifyRecoverySession = async () => {
      try {
        const {
          data: { session },
        } = await supabase.auth.getSession();

        if (mounted) {
          if (session) {
            setHasValidSession(true);
          }
          setSessionChecking(false);
        }
      } catch (err) {
        if (mounted) {
          setHasValidSession(false);
          setSessionChecking(false);
        }
      }
    };

    verifyRecoverySession();

    // Listen for PASSWORD_RECOVERY auth state event
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === 'PASSWORD_RECOVERY' || (event === 'SIGNED_IN' && session)) {
        if (mounted) {
          setHasValidSession(true);
          setSessionChecking(false);
        }
      }
    });

    return () => {
      mounted = false;
      subscription?.unsubscribe();
    };
  }, []);

  const pwCheck = useMemo(() => checkPasswordRequirements(password), [password]);

  const handleUpdatePassword = async (e) => {
    e.preventDefault();
    setError(null);

    if (!pwCheck.isValid) {
      setError('Password does not meet the requirements.');
      return;
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match. Please re-enter.');
      return;
    }

    setLoading(true);

    try {
      const { error: updateError } = await supabase.auth.updateUser({
        password: password,
      });

      if (updateError) {
        setError(updateError.message || 'Failed to update password. Your reset link may have expired.');
      } else {
        setSuccess(true);
        // Automatically sign out recovery session and redirect to login
        setTimeout(async () => {
          await supabase.auth.signOut();
          router.push('/login');
        }, 2500);
      }
    } catch (err) {
      console.error('Password reset update error:', err);
      setError('An unexpected error occurred while resetting your password.');
    } finally {
      setLoading(false);
    }
  };

  if (sessionChecking) {
    return (
      <div className="auth-container">
        <div className="auth-card" style={{ textAlign: 'center' }}>
          <div className="r6-spinner" style={{ margin: '0 auto 1rem' }} />
          <p>Verifying password reset link…</p>
        </div>
      </div>
    );
  }

  if (!hasValidSession && !success) {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <h1>Link Expired or Invalid</h1>
          <p>
            This password reset link is invalid, expired, or has already been used.
          </p>

          <div
            style={{
              color: '#d97706',
              backgroundColor: 'rgba(217, 119, 6, 0.08)',
              border: '1px solid rgba(217, 119, 6, 0.25)',
              padding: '1rem',
              borderRadius: '0.5rem',
              fontSize: '0.875rem',
              lineHeight: 1.45,
              marginBottom: '1.5rem',
            }}
          >
            Please request a fresh password reset link below.
          </div>

          <Link
            href="/forgot-password"
            className="btn btn-primary"
            style={{ width: '100%', display: 'block', textAlign: 'center', textDecoration: 'none' }}
          >
            Request New Reset Link
          </Link>

          <div className="auth-link">
            <Link href="/login">Return to Log In</Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h1>Set New Password</h1>
        <p>Create a secure password for your Wealthyneers account</p>

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
              <strong>✓ Password Updated Successfully</strong>
              <p style={{ margin: '0.5rem 0 0', color: 'inherit', fontSize: '0.85rem' }}>
                Your password has been changed. Redirecting to login page…
              </p>
            </div>

            <Link
              href="/login"
              className="btn btn-primary"
              style={{ width: '100%', display: 'block', textAlign: 'center', textDecoration: 'none' }}
            >
              Go to Log In Now
            </Link>
          </div>
        ) : (
          <form onSubmit={handleUpdatePassword}>
            <div className="form-group">
              <label htmlFor="password">New Password</label>
              <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  autoComplete="new-password"
                  required
                  minLength={8}
                  style={{ width: '100%', paddingRight: '4.5rem' }}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  style={{
                    position: 'absolute',
                    right: '0.75rem',
                    background: 'none',
                    border: 'none',
                    color: 'var(--secondary)',
                    fontSize: '0.8rem',
                    cursor: 'pointer',
                    fontWeight: 600,
                    padding: '0.25rem 0.5rem',
                  }}
                >
                  {showPassword ? 'Hide' : 'Show'}
                </button>
              </div>

              {/* Dynamic Password Requirements Checklist */}
              <div
                style={{
                  marginTop: '0.65rem',
                  padding: '0.65rem 0.85rem',
                  borderRadius: '0.5rem',
                  backgroundColor: 'rgba(10, 77, 104, 0.03)',
                  border: '1px solid var(--border)',
                  fontSize: '0.78rem',
                  lineHeight: 1.4,
                }}
              >
                <div style={{ fontWeight: 600, color: 'var(--secondary)', marginBottom: '0.35rem' }}>
                  Password must contain:
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', color: pwCheck.minLength ? '#059669' : 'var(--secondary)' }}>
                    <span style={{ fontWeight: 700, fontSize: '0.82rem', width: '12px' }}>{pwCheck.minLength ? '✓' : '○'}</span>
                    <span>At least 8 characters</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', color: pwCheck.hasUpper ? '#059669' : 'var(--secondary)' }}>
                    <span style={{ fontWeight: 700, fontSize: '0.82rem', width: '12px' }}>{pwCheck.hasUpper ? '✓' : '○'}</span>
                    <span>One uppercase letter</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', color: pwCheck.hasLower ? '#059669' : 'var(--secondary)' }}>
                    <span style={{ fontWeight: 700, fontSize: '0.82rem', width: '12px' }}>{pwCheck.hasLower ? '✓' : '○'}</span>
                    <span>One lowercase letter</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', color: pwCheck.hasNumber ? '#059669' : 'var(--secondary)' }}>
                    <span style={{ fontWeight: 700, fontSize: '0.82rem', width: '12px' }}>{pwCheck.hasNumber ? '✓' : '○'}</span>
                    <span>One number</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', color: pwCheck.hasSpecial ? '#059669' : 'var(--secondary)' }}>
                    <span style={{ fontWeight: 700, fontSize: '0.82rem', width: '12px' }}>{pwCheck.hasSpecial ? '✓' : '○'}</span>
                    <span>One special character</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="confirmPassword">Confirm New Password</label>
              <div style={{ position: 'relative' }}>
                <input
                  id="confirmPassword"
                  type={showPassword ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Re-type new password"
                  autoComplete="new-password"
                  required
                  minLength={6}
                  style={{ width: '100%', paddingRight: '4.5rem' }}
                />
              </div>
            </div>

            <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1.25rem' }}>
              <button
                type="submit"
                className="btn btn-primary"
                style={{ flex: 1 }}
                disabled={loading}
              >
                {loading ? 'Saving Password…' : 'Reset Password'}
              </button>
              <Link
                href="/login"
                className="btn btn-outline"
                style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', textDecoration: 'none' }}
              >
                Cancel
              </Link>
            </div>

            <div className="auth-link" style={{ marginTop: '1.25rem' }}>
              <Link href="/login">Return to Log In</Link>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
