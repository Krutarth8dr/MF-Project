'use client';

import { useState, useMemo } from 'react';
import { supabase } from '@/lib/supabase';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { validateFullName, checkPasswordRequirements } from '@/lib/validation';

export default function SignUp() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [fullName, setFullName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [signedUp, setSignedUp] = useState(false);
  const router = useRouter();

  // Dynamic real-time password requirements evaluation
  const pwCheck = useMemo(() => checkPasswordRequirements(password), [password]);

  const handleSignUp = async (e) => {
    e.preventDefault();
    setError(null);

    // 1. Full Name Validation
    const nameValidation = validateFullName(fullName);
    if (!nameValidation.valid) {
      setError(nameValidation.error);
      return;
    }

    // 2. Password Security Validation
    if (!pwCheck.isValid) {
      setError('Password does not meet the requirements.');
      return;
    }

    setLoading(true);

    const { data, error: signUpError } = await supabase.auth.signUp({
      email: email.trim(),
      password,
      options: {
        data: {
          full_name: nameValidation.value,
        },
      },
    });

    if (signUpError) {
      setError(signUpError.message || 'Failed to create account.');
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
              </p>
              <p style={{ margin: '0.5rem 0 0', color: 'inherit', fontSize: '0.85rem' }}>
                If an email account exists for the address you entered, you will receive a confirmation link there. Please check your inbox and click the confirmation link to activate your access.
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
                    fontWeight: 600,
                    cursor: 'pointer',
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
