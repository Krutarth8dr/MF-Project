'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { supabase } from '@/lib/supabase';
import { startRazorpayCheckout, loadRazorpaySDK } from '@/lib/razorpay';
import { setCachedSubscription, clearSubscriptionCache } from '@/lib/subscriptionCache';

// ─── Date Formatter Helper ───────────────────────────────────────────
function formatDate(dateStr) {
  if (!dateStr) return '—';
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return d.toLocaleDateString('en-IN', {
      day: '2-digit',
      month: 'long',
      year: 'numeric',
    });
  } catch {
    return dateStr;
  }
}

// ─── Extract Initials Helper ─────────────────────────────────────────
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

export default function ProfilePage() {
  const router = useRouter();

  // ── States ─────────────────────────────────────────────────────────
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [user, setUser] = useState(null);
  const [profileName, setProfileName] = useState('');
  const [subscriptions, setSubscriptions] = useState([]);
  const [currentSub, setCurrentSub] = useState(null);
  const [subStatus, setSubStatus] = useState('inactive'); // 'active' | 'expired' | 'pending' | 'failed' | 'inactive'

  // ── Password Change Form States ────────────────────────────────────
  const [showPasswordForm, setShowPasswordForm] = useState(false);
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPasswordText, setShowPasswordText] = useState(false);
  const [pwLoading, setPwLoading] = useState(false);
  const [pwError, setPwError] = useState(null);
  const [pwSuccess, setPwSuccess] = useState(null);
  const [paying, setPaying] = useState(false);
  const [checkoutError, setCheckoutError] = useState(null);

  // ── Handle Instant Razorpay Subscription ────────────────────────────
  const handleProfileSubscribe = () => {
    if (!user) return;
    setPaying(true);
    setCheckoutError(null);

    const safetyTimer = setTimeout(() => {
      setPaying((current) => {
        if (current) {
          setCheckoutError('Checkout is taking longer than expected. Please check your connection or reload.');
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
      onSuccess: async () => {
        clearTimeout(safetyTimer);
        setPaying(false);
        // Refresh subscription records from database
        const { data: refreshedSubs } = await supabase
          .from('subscriptions')
          .select('*')
          .eq('user_id', user.id)
          .order('subscription_end_date', { ascending: false, nullsFirst: false });

        const subs = refreshedSubs || [];
        setSubscriptions(subs);

        const active = subs.find(
          (s) =>
            s.payment_status === 'completed' &&
            (s.subscription_end_date === null ||
              new Date(s.subscription_end_date) > new Date())
        );

        if (active) {
          setCurrentSub(active);
          setSubStatus('active');
        }
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

  // ── Load User & Subscription Information ───────────────────────────
  useEffect(() => {
    let isMounted = true;

    // Pre-warm Razorpay SDK in background
    loadRazorpaySDK().catch(() => {});

    const fetchUserData = async (authUser) => {
      if (!authUser || !isMounted) return;
      setUser(authUser);

      let resolvedName =
        authUser.user_metadata?.full_name ||
        authUser.user_metadata?.name ||
        authUser.email?.split('@')[0] ||
        'Account';
      setProfileName(resolvedName);

      try {
        const [userResult, subResult] = await Promise.allSettled([
          supabase
            .from('users')
            .select('full_name')
            .eq('id', authUser.id)
            .maybeSingle(),
          supabase
            .from('subscriptions')
            .select('*')
            .eq('user_id', authUser.id)
            .order('subscription_end_date', { ascending: false, nullsFirst: false }),
        ]);

        if (userResult.status === 'fulfilled' && userResult.value?.data?.full_name) {
          if (isMounted) setProfileName(userResult.value.data.full_name);
        }

        const subs = (subResult.status === 'fulfilled' && subResult.value?.data) || [];
        if (!isMounted) return;
        setSubscriptions(subs);

        // Determine Active Subscription
        const active = subs.find(
          (s) =>
            s.payment_status === 'completed' &&
            (s.subscription_end_date === null ||
              new Date(s.subscription_end_date) > new Date())
        );

        if (active) {
          setCurrentSub(active);
          setSubStatus('active');
          setCachedSubscription(authUser.id, true, active.subscription_end_date);
        } else if (subs.length > 0) {
          const latest = subs[0];
          setCurrentSub(latest);
          if (latest.payment_status === 'pending') {
            setSubStatus('pending');
            setCachedSubscription(authUser.id, false);
          } else if (
            latest.payment_status === 'completed' &&
            latest.subscription_end_date &&
            new Date(latest.subscription_end_date) <= new Date()
          ) {
            setSubStatus('expired');
            setCachedSubscription(authUser.id, false);
          } else if (latest.payment_status === 'failed') {
            setSubStatus('failed');
            setCachedSubscription(authUser.id, false);
          } else {
            setSubStatus('inactive');
            setCachedSubscription(authUser.id, false);
          }
        } else {
          setCurrentSub(null);
          setSubStatus('inactive');
          setCachedSubscription(authUser.id, false);
        }
      } catch (err) {
        console.error('Profile data error:', err);
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    // 1. Check Session & User
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session?.user) {
        fetchUserData(session.user);
      } else {
        supabase.auth.getUser().then(({ data: { user } }) => {
          if (user) {
            fetchUserData(user);
          } else if (isMounted) {
            setLoading(false);
          }
        }).catch(() => {
          if (isMounted) setLoading(false);
        });
      }
    }).catch(() => {
      if (isMounted) setLoading(false);
    });

    // 2. Auth state change listener
    const {
      data: { subscription: authListener },
    } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === 'SIGNED_OUT') {
        setUser(null);
        clearSubscriptionCache();
        router.push('/login');
      } else if (session?.user) {
        fetchUserData(session.user);
      }
    });

    return () => {
      isMounted = false;
      authListener?.unsubscribe();
    };
  }, [router]);

  // ── Handle Sign Out ────────────────────────────────────────────────
  const handleSignOut = async () => {
    try {
      setUser(null);
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

      supabase.auth.signOut({ scope: 'local' }).catch(() => {});
      supabase.auth.signOut().catch(() => {});
    } finally {
      window.location.replace('/login');
    }
  };

  // ── Handle Password Change ─────────────────────────────────────────
  const handleChangePassword = async (e) => {
    e.preventDefault();
    setPwError(null);
    setPwSuccess(null);

    if (!newPassword || newPassword.length < 6) {
      setPwError('New password must be at least 6 characters long.');
      return;
    }

    if (newPassword !== confirmPassword) {
      setPwError('Passwords do not match. Please re-enter.');
      return;
    }

    setPwLoading(true);
    try {
      const { error: updateError } = await supabase.auth.updateUser({
        password: newPassword,
      });

      if (updateError) {
        setPwError(updateError.message || 'Failed to update password.');
      } else {
        setPwSuccess('Your password has been changed successfully!');
        setNewPassword('');
        setConfirmPassword('');
        setShowPasswordForm(false);
      }
    } catch {
      setPwError('An unexpected error occurred while updating your password.');
    } finally {
      setPwLoading(false);
    }
  };

  // ── Loading Skeleton ───────────────────────────────────────────────
  if (loading) {
    return (
      <div className="profile-page">
        <div className="dash-loading" style={{ minHeight: '60vh' }}>
          <div className="r6-spinner" />
          <p>Loading your profile and subscription details…</p>
        </div>
      </div>
    );
  }

  // ── Error State ────────────────────────────────────────────────────
  if (error || !user) {
    return (
      <div className="profile-page">
        <div className="dash-locked">
          <div className="dash-locked-icon">⚠️</div>
          <h2>Account Information Unavailable</h2>
          <p>{error || 'Please log in to view your profile.'}</p>
          <Link href="/login" className="btn btn-primary" style={{ marginTop: '1.5rem', display: 'inline-block' }}>
            Go to Login
          </Link>
        </div>
      </div>
    );
  }

  const initials = getInitials(profileName, user.email);

  return (
    <div className="profile-page">
      {/* ── Top Hero Card ── */}
      <div className="profile-hero">
        <div className="profile-hero-left">
          <div className="profile-avatar-large">{initials}</div>
          <div className="profile-hero-info">
            <h1>{profileName || 'Wealthyneers User'}</h1>
            <div className="profile-hero-email">{user.email}</div>
            <div className="profile-hero-badges">
              {subStatus === 'active' && (
                <span className="profile-badge-pill badge-active">
                  ● Active Subscriber
                </span>
              )}
              {subStatus === 'expired' && (
                <span className="profile-badge-pill badge-expired">
                  ● Subscription Expired
                </span>
              )}
              {subStatus === 'pending' && (
                <span className="profile-badge-pill badge-pending">
                  ● Payment Pending
                </span>
              )}
              {subStatus === 'inactive' && (
                <span className="profile-badge-pill badge-inactive">
                  ○ Free Account
                </span>
              )}
              <span className="profile-badge-pill badge-created">
                Member since {formatDate(user.created_at)}
              </span>
            </div>
          </div>
        </div>

        <div className="profile-hero-right">
          {subStatus === 'active' ? (
            <Link href="/dashboard" className="btn btn-primary">
              Open Dashboard →
            </Link>
          ) : (
            <button
              type="button"
              onClick={handleProfileSubscribe}
              disabled={paying}
              className="btn btn-primary"
            >
              {paying ? 'Opening Checkout…' : 'Subscribe — ₹30/month'}
            </button>
          )}
        </div>
      </div>

      {/* ── 2-Column Details Grid ── */}
      <div className="profile-grid">
        {/* 1. Personal Information Card */}
        <div className="profile-card">
          <div className="profile-card-header">
            <div className="profile-card-title">
              <span className="profile-card-title-icon">👤</span>
              <span>Personal Information</span>
            </div>
          </div>

          <div className="profile-info-list">
            <div className="profile-info-item">
              <span className="profile-info-label">Full Name</span>
              <span className="profile-info-value">
                <strong>{profileName || '—'}</strong>
              </span>
            </div>

            <div className="profile-info-item">
              <span className="profile-info-label">Email Address</span>
              <span className="profile-info-value">{user.email}</span>
            </div>

            <div className="profile-info-item">
              <span className="profile-info-label">Account Created</span>
              <span className="profile-info-value">
                {formatDate(user.created_at)}
              </span>
            </div>

            <div className="profile-info-item">
              <span className="profile-info-label">Email Verification</span>
              <span className="profile-info-value" style={{ color: user.email_confirmed_at ? '#059669' : '#d97706', fontWeight: 600 }}>
                {user.email_confirmed_at ? '✓ Verified' : 'Pending Verification'}
              </span>
            </div>
          </div>
        </div>

        {/* 2. Subscription Details Card */}
        <div className="profile-card">
          <div className="profile-card-header">
            <div className="profile-card-title">
              <span className="profile-card-title-icon">💳</span>
              <span>Subscription Status</span>
            </div>
            {subStatus === 'active' && (
              <span className="profile-badge-pill badge-active">● Active</span>
            )}
            {subStatus === 'expired' && (
              <span className="profile-badge-pill badge-expired">● Expired</span>
            )}
            {subStatus === 'pending' && (
              <span className="profile-badge-pill badge-pending">● Pending</span>
            )}
            {subStatus === 'inactive' && (
              <span className="profile-badge-pill badge-inactive">○ Inactive</span>
            )}
          </div>

          <div className="profile-info-list">
            <div className="profile-info-item">
              <span className="profile-info-label">Current Plan</span>
              <span className="profile-info-value">
                <strong>
                  {subStatus === 'active'
                    ? 'Monthly Institutional Access'
                    : currentSub?.plan_type === 'monthly_30'
                    ? 'Monthly Institutional Access'
                    : currentSub?.plan_type || 'No active plan'}
                </strong>
              </span>
            </div>

            <div className="profile-info-item">
              <span className="profile-info-label">Subscription Started</span>
              <span className="profile-info-value">
                {currentSub?.subscription_start_date
                  ? formatDate(currentSub.subscription_start_date)
                  : '—'}
              </span>
            </div>

            <div className="profile-info-item">
              <span className="profile-info-label">Subscription Valid Until</span>
              <span className="profile-info-value">
                {currentSub?.subscription_end_date
                  ? formatDate(currentSub.subscription_end_date)
                  : subStatus === 'active'
                  ? 'Active (Continuous)'
                  : '—'}
              </span>
            </div>

            <div className="profile-info-item">
              <span className="profile-info-label">Auto Renewal</span>
              <span className="profile-info-value">
                {currentSub?.auto_renew === true ? 'Enabled' : 'Disabled'}
              </span>
            </div>

            {currentSub && (
              <div className="profile-info-item">
                <span className="profile-info-label">Amount Paid</span>
                <span className="profile-info-value">
                  {currentSub.currency === 'INR' || !currentSub.currency ? '₹' : currentSub.currency + ' '}
                  {Number(currentSub.amount_paid || currentSub.amount || 30).toFixed(2)}
                </span>
              </div>
            )}
          </div>

          <div style={{ marginTop: '1.5rem', paddingTop: '1rem', borderTop: '1px solid var(--border)' }}>
            {checkoutError && (
              <div
                style={{
                  color: '#dc2626',
                  backgroundColor: 'rgba(220, 38, 38, 0.08)',
                  border: '1px solid rgba(220, 38, 38, 0.25)',
                  padding: '0.75rem 1rem',
                  borderRadius: '0.5rem',
                  fontSize: '0.85rem',
                  marginBottom: '1rem',
                  textAlign: 'left',
                  lineHeight: 1.45,
                }}
              >
                ⚠️ {checkoutError}
              </div>
            )}

            {subStatus === 'active' ? (
              <Link href="/dashboard" className="btn btn-outline" style={{ width: '100%' }}>
                Access Institutional Reports →
              </Link>
            ) : (
              <button
                type="button"
                onClick={handleProfileSubscribe}
                disabled={paying}
                className="btn btn-primary"
                style={{ width: '100%' }}
              >
                {paying ? 'Opening Checkout…' : 'Subscribe Now — ₹30/month'}
              </button>
            )}
          </div>
        </div>

        {/* 3. Account Security & Password Management Card */}
        <div className="profile-card">
          <div className="profile-card-header">
            <div className="profile-card-title">
              <span className="profile-card-title-icon">🔒</span>
              <span>Account Security</span>
            </div>
          </div>

          {pwSuccess && (
            <div className="profile-alert profile-alert-success" style={{ marginBottom: '1rem' }}>
              ✓ {pwSuccess}
            </div>
          )}

          {pwError && (
            <div className="profile-alert profile-alert-error" style={{ marginBottom: '1rem' }}>
              ⚠️ {pwError}
            </div>
          )}

          {!showPasswordForm ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', flex: 1, justifyContent: 'space-between' }}>
              <p style={{ fontSize: '0.9rem', color: 'var(--secondary)', lineHeight: 1.5 }}>
                Ensure your account is protected with a secure password. You can change your password at any time.
              </p>
              <button
                type="button"
                className="btn btn-outline"
                onClick={() => {
                  setShowPasswordForm(true);
                  setPwError(null);
                  setPwSuccess(null);
                }}
              >
                Change Password
              </button>
            </div>
          ) : (
            <form onSubmit={handleChangePassword} className="profile-pw-form">
              <div className="profile-pw-field">
                <label htmlFor="newPassword">New Password</label>
                <div className="profile-pw-input-wrap">
                  <input
                    id="newPassword"
                    type={showPasswordText ? 'text' : 'password'}
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="Enter new password (min. 6 chars)"
                    className="profile-pw-input"
                    required
                    minLength={6}
                  />
                  <button
                    type="button"
                    className="profile-pw-toggle"
                    onClick={() => setShowPasswordText(!showPasswordText)}
                  >
                    {showPasswordText ? 'Hide' : 'Show'}
                  </button>
                </div>
              </div>

              <div className="profile-pw-field">
                <label htmlFor="confirmPassword">Confirm New Password</label>
                <div className="profile-pw-input-wrap">
                  <input
                    id="confirmPassword"
                    type={showPasswordText ? 'text' : 'password'}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Re-type new password"
                    className="profile-pw-input"
                    required
                    minLength={6}
                  />
                </div>
              </div>

              <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.5rem' }}>
                <button
                  type="submit"
                  disabled={pwLoading}
                  className="btn btn-primary"
                  style={{ flex: 1 }}
                >
                  {pwLoading ? 'Updating…' : 'Save Password'}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowPasswordForm(false);
                    setPwError(null);
                  }}
                  className="btn btn-outline"
                >
                  Cancel
                </button>
              </div>
            </form>
          )}
        </div>

        {/* 4. Session & Sign Out Card */}
        <div className="profile-card">
          <div className="profile-card-header">
            <div className="profile-card-title">
              <span className="profile-card-title-icon">🚪</span>
              <span>Session &amp; Actions</span>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', flex: 1, justifyContent: 'space-between' }}>
            <div>
              <p style={{ fontSize: '0.9rem', color: 'var(--secondary)', lineHeight: 1.5, marginBottom: '0.75rem' }}>
                Logged in as <strong>{user.email}</strong>.
              </p>
              <p style={{ fontSize: '0.82rem', color: 'var(--secondary)' }}>
                Signing out will end your current session across this browser.
              </p>
            </div>

            <button
              type="button"
              onClick={handleSignOut}
              className="btn btn-outline"
              style={{
                width: '100%',
                color: '#dc2626',
                borderColor: 'rgba(220, 38, 38, 0.3)',
                fontWeight: 600,
              }}
            >
              Sign Out of Wealthyneers
            </button>
          </div>
        </div>

        {/* 5. Subscription History (if records exist) */}
        {subscriptions.length > 0 && (
          <div className="profile-history-card">
            <div className="profile-card-header">
              <div className="profile-card-title">
                <span className="profile-card-title-icon">📜</span>
                <span>Subscription &amp; Payment Records</span>
              </div>
            </div>

            <div className="profile-table-wrap">
              <table className="profile-table">
                <thead>
                  <tr>
                    <th>Plan</th>
                    <th>Start Date</th>
                    <th>End Date</th>
                    <th>Amount</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {subscriptions.map((sub, idx) => (
                    <tr key={sub.id || idx}>
                      <td>
                        <strong>
                          {sub.plan_name ||
                            (sub.plan_type === 'monthly_30'
                              ? 'Monthly Institutional Access'
                              : sub.plan_type || 'Monthly')}
                        </strong>
                      </td>
                      <td>{formatDate(sub.subscription_start_date || sub.created_at)}</td>
                      <td>{formatDate(sub.subscription_end_date)}</td>
                      <td>
                        {sub.currency === 'INR' || !sub.currency ? '₹' : sub.currency + ' '}
                        {Number(sub.amount_paid || sub.amount || 30).toFixed(2)}
                      </td>
                      <td>
                        <span
                          className={`profile-badge-pill ${
                            sub.payment_status === 'completed' &&
                            (sub.subscription_end_date === null ||
                              new Date(sub.subscription_end_date) > new Date())
                              ? 'badge-active'
                              : sub.payment_status === 'pending'
                              ? 'badge-pending'
                              : 'badge-expired'
                          }`}
                        >
                          {sub.payment_status === 'completed' &&
                          (sub.subscription_end_date === null ||
                            new Date(sub.subscription_end_date) > new Date())
                            ? '● Active'
                            : sub.payment_status === 'pending'
                            ? '● Pending'
                            : '● Completed'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
