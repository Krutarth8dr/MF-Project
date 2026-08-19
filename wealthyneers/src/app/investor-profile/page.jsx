'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { supabase } from '@/lib/supabase';

// ── Options Data from Official Assessment ──────────────────────────────────
const AGE_GROUPS = ['Under 18', '18–30', '31–45', '46–60', 'Above 60'];

const GOAL_OPTIONS = [
  'Creating long-term wealth',
  'Retirement',
  "Children's education",
  "Children's marriage",
  'Buying a house/property',
  'Buying a vehicle',
  'Regular income',
  'Emergency reserve',
  'Travel / lifestyle goal',
  'Tax planning',
];

const TIMELINE_OPTIONS = [
  'Within 1 year',
  '1–3 years',
  '3–5 years',
  '5–7 years',
  '7–10 years',
  'More than 10 years',
];

const IMPORTANCE_OPTIONS = [
  'Essential — I cannot compromise this goal',
  'Important — some flexibility is possible',
  'Aspirational — I can postpone/reduce the goal',
  'I am not sure',
];

const FUND_SOURCES = [
  'Existing bank balance / surplus cash',
  'Fixed deposit maturity',
  'Business surplus',
  'Bonus / incentive',
  'Sale of property / asset',
  'Existing investments being reinvested',
  'Inheritance / one-time receipt',
  'Monthly income surplus',
  'This amount represents most/all of my liquid savings',
  'This money is borrowed',
];

const EMERGENCY_RESERVE_OPTIONS = [
  'No emergency reserve',
  'Less than 1 month of expenses',
  '1–3 months',
  '3–6 months',
  '6–12 months',
  'More than 12 months',
];

const FIXED_OBLIGATIONS_OPTIONS = [
  'More than 50%',
  '35%–50%',
  '20%–35%',
  '10%–20%',
  'Less than 10%',
  'I do not have significant fixed obligations',
];

const INCOME_SITUATION_OPTIONS = [
  'My income is highly predictable',
  'My income is reasonably stable',
  'My income changes significantly month to month',
  'My income is seasonal / business dependent',
  'I may experience periods with little or no income',
  'I have multiple independent sources of income',
  'I am retired / primarily dependent on investments',
  'Other / mixed situation',
];

const UNEXPECTED_NEED_OPTIONS = [
  'Very likely — I may need it anytime',
  'Possible within the next year',
  'Possible within 1–3 years',
  'Unlikely before my stated goal',
  'I have adequate separate liquidity for emergencies',
];

const INVESTMENT_EXPERIENCE_OPTIONS = [
  'I have never invested before',
  'Bank FD / RD',
  'PPF / Post Office / Government savings',
  'Debt Mutual Funds',
  'Hybrid Mutual Funds',
  'Equity Mutual Funds',
  'SIP in Equity Mutual Funds',
  'Direct Shares',
  'PMS / AIF / other market-linked investments',
];

const MARKET_REACTION_OPTIONS = [
  'Redeem everything immediately',
  'Redeem most of the investment',
  'Reduce some exposure',
  'Wait until I understand what is happening',
  'Remain invested',
  'Continue my SIP',
  'Invest additional money if the investment remains suitable',
  'I genuinely do not know how I would react',
];

const TOLERABLE_DRAWDOWN_OPTIONS = [
  'I do not want meaningful capital fluctuation',
  'Around 5%',
  'Around 10%',
  'Around 15%',
  'Around 20%',
  'Around 25%',
  'More than 25%',
];

const RISK_ATTITUDE_OPTIONS = [
  'Protecting capital is my highest priority',
  'I prefer predictable / stable investments',
  'I can accept some fluctuations for better long-term growth',
  'Long-term wealth creation is more important than short-term volatility',
  'I am comfortable with substantial fluctuations if long-term potential is attractive',
  'Seeing a temporary loss makes me very uncomfortable',
  'I generally remain calm during market corrections',
];

const RISK_PROFILES = [
  { label: 'Very Conservative', desc: 'Focus strictly on capital safety with zero-to-low volatility tolerance.' },
  { label: 'Conservative', desc: 'Priority on capital preservation with modest stable income.' },
  { label: 'Moderate', desc: 'Balanced approach seeking capital appreciation with moderate risk.' },
  { label: 'Growth-oriented', desc: 'Willing to accept significant volatility for higher wealth generation.' },
  { label: 'Aggressive', desc: 'Maximum growth focus, comfortable with high market fluctuations.' },
  { label: 'I am not sure', desc: 'Let Wealthyneers analyze your suitability parameters.' },
];

const DECLARATION_STATEMENTS = [
  'I confirm that the information provided is true and complete to the best of my knowledge.',
  'I understand that Mutual Fund investments are market-linked and returns are not guaranteed.',
  'I understand that this assessment is based on the information provided by me.',
  'I consent to my information being processed for preparing and maintaining my Mutual Fund investor profile.',
];

export default function InvestorProfilePage() {
  const router = useRouter();
  const [authLoading, setAuthLoading] = useState(true);
  const [user, setUser] = useState(null);
  const [existingProfile, setExistingProfile] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [submissionSuccess, setSubmissionSuccess] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);
  const [fieldErrors, setFieldErrors] = useState({});

  // Pre-form Warning Acknowledgement State (UX-only)
  const [acknowledgedWarning, setAcknowledgedWarning] = useState(false);
  const [understoodOneTime, setUnderstoodOneTime] = useState(false);

  // Form State
  const [formData, setFormData] = useState({
    full_name: '',
    mobile_number: '',
    email_address: '',
    age_group: '',
    investing_for: [],
    primary_goal: '',
    primary_goal_amount: '',
    primary_goal_timeline: '',
    primary_goal_importance: '',
    available_funds_sources: [],
    lump_sum_amount: '',
    monthly_sip_amount: '',
    emergency_reserve_duration: '',
    fixed_obligations_percentage: '',
    income_stability: [],
    unexpected_need_likelihood: '',
    investment_experience: [],
    market_reaction_scenario: [],
    tolerable_drawdown: '',
    risk_attitude_statements: [],
    risk_profile_self_assessment: '',
    declaration_confirmations: [],
  });

  // 1. Authenticate & Check for Existing Submission
  useEffect(() => {
    let mounted = true;

    async function checkAuthAndProfile() {
      try {
        const {
          data: { session },
        } = await supabase.auth.getSession();

        if (!session || !session.user) {
          router.replace('/login?redirect=/investor-profile');
          return;
        }

        if (mounted) {
          setUser(session.user);
          const userName =
            session.user.user_metadata?.full_name ||
            session.user.user_metadata?.name ||
            '';
          setFormData((prev) => ({
            ...prev,
            full_name: userName,
            email_address: session.user.email || '',
          }));

          // Check if this user has already submitted a profile
          const { data: profile } = await supabase
            .from('investor_profiles')
            .select('id, submitted_at, full_name, primary_goal, status')
            .eq('user_id', session.user.id)
            .maybeSingle();

          if (profile) {
            setExistingProfile(profile);
          }
        }
      } catch (err) {
        console.error('Error checking profile session:', err);
      } finally {
        if (mounted) setAuthLoading(false);
      }
    }

    checkAuthAndProfile();

    return () => {
      mounted = false;
    };
  }, [router]);

  // Helper for multi-select checkbox toggle with automatic error clearing
  const toggleArrayItem = (fieldName, item) => {
    setFormData((prev) => {
      const current = prev[fieldName] || [];
      const exists = current.includes(item);
      const updated = exists ? current.filter((x) => x !== item) : [...current, item];
      return { ...prev, [fieldName]: updated };
    });
    setFieldErrors((prev) => {
      if (!prev[fieldName]) return prev;
      const copy = { ...prev };
      delete copy[fieldName];
      return copy;
    });
  };

  // Helper for radio single select with automatic error clearing
  const setSingleValue = (fieldName, value) => {
    setFormData((prev) => ({ ...prev, [fieldName]: value }));
    setFieldErrors((prev) => {
      if (!prev[fieldName]) return prev;
      const copy = { ...prev };
      delete copy[fieldName];
      return copy;
    });
  };

  // Form Validation Logic (ordered from top to bottom)
  const validateForm = (data) => {
    const errors = {};
    const order = [];

    // Section 01
    if (!data.full_name || data.full_name.trim().length < 2) {
      errors.full_name = 'Please provide your full name.';
      order.push('q-field-full_name');
    }
    if (!data.mobile_number || !/^\+?[0-9]{10,13}$/.test(data.mobile_number.replace(/[\s-]/g, ''))) {
      errors.mobile_number = 'Please provide a valid 10-digit mobile number.';
      order.push('q-field-mobile_number');
    }
    if (!data.age_group) {
      errors.age_group = 'Please select your age group.';
      order.push('q-field-age_group');
    }

    // Section 02
    if (!Array.isArray(data.investing_for) || data.investing_for.length === 0) {
      errors.investing_for = 'Please select at least one investment goal.';
      order.push('q-field-investing_for');
    }
    if (!data.primary_goal) {
      errors.primary_goal = 'Please select your primary goal.';
      order.push('q-field-primary_goal');
    }
    if (!data.primary_goal_amount || !data.primary_goal_amount.trim()) {
      errors.primary_goal_amount = 'Please specify the approximate amount required for your primary goal.';
      order.push('q-field-primary_goal_amount');
    }
    if (!data.primary_goal_timeline) {
      errors.primary_goal_timeline = 'Please select the timeline for your primary goal.';
      order.push('q-field-primary_goal_timeline');
    }
    if (!data.primary_goal_importance) {
      errors.primary_goal_importance = 'Please select the importance of your primary goal.';
      order.push('q-field-primary_goal_importance');
    }

    // Section 03
    if (!Array.isArray(data.available_funds_sources) || data.available_funds_sources.length === 0) {
      errors.available_funds_sources = 'Please select the sources of available money.';
      order.push('q-field-available_funds_sources');
    }
    if (!data.lump_sum_amount || !data.lump_sum_amount.trim()) {
      errors.lump_sum_amount = 'Please specify the lump sum amount (enter 0 if none).';
      order.push('q-field-lump_sum_amount');
    }
    if (!data.monthly_sip_amount || !data.monthly_sip_amount.trim()) {
      errors.monthly_sip_amount = 'Please specify your monthly SIP capacity (enter 0 if none).';
      order.push('q-field-monthly_sip_amount');
    }
    if (!data.emergency_reserve_duration) {
      errors.emergency_reserve_duration = 'Please select your emergency reserve duration.';
      order.push('q-field-emergency_reserve_duration');
    }
    if (!data.fixed_obligations_percentage) {
      errors.fixed_obligations_percentage = 'Please select your monthly fixed obligations percentage.';
      order.push('q-field-fixed_obligations_percentage');
    }
    if (!Array.isArray(data.income_stability) || data.income_stability.length === 0) {
      errors.income_stability = 'Please describe your income situation.';
      order.push('q-field-income_stability');
    }
    if (!data.unexpected_need_likelihood) {
      errors.unexpected_need_likelihood = 'Please indicate the likelihood of needing money unexpectedly.';
      order.push('q-field-unexpected_need_likelihood');
    }

    // Section 04
    if (!Array.isArray(data.investment_experience) || data.investment_experience.length === 0) {
      errors.investment_experience = 'Please select the investment products you have used.';
      order.push('q-field-investment_experience');
    }
    if (!Array.isArray(data.market_reaction_scenario) || data.market_reaction_scenario.length === 0) {
      errors.market_reaction_scenario = 'Please select your reaction to a market correction.';
      order.push('q-field-market_reaction_scenario');
    }
    if (!data.tolerable_drawdown) {
      errors.tolerable_drawdown = 'Please select your tolerable level of decline.';
      order.push('q-field-tolerable_drawdown');
    }
    if (!Array.isArray(data.risk_attitude_statements) || data.risk_attitude_statements.length === 0) {
      errors.risk_attitude_statements = 'Please select statements describing your risk attitude.';
      order.push('q-field-risk_attitude_statements');
    }
    if (!data.risk_profile_self_assessment) {
      errors.risk_profile_self_assessment = 'Please select your self-assessed risk profile.';
      order.push('q-field-risk_profile_self_assessment');
    }

    // Section 05
    if (!Array.isArray(data.declaration_confirmations) || data.declaration_confirmations.length < DECLARATION_STATEMENTS.length) {
      errors.declaration_confirmations = 'Please confirm all 4 statutory statements before submitting.';
      order.push('q-field-declaration_confirmations');
    }

    return { errors, firstErrorId: order[0] || null };
  };

  // Submit Handler
  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg(null);

    // Run client-side validation
    const { errors, firstErrorId } = validateForm(formData);

    if (firstErrorId) {
      setFieldErrors(errors);
      setErrorMsg('Please complete the highlighted required fields before submitting.');

      // Automatically scroll to the FIRST missing/invalid field
      setTimeout(() => {
        const el = document.getElementById(firstErrorId);
        if (el) {
          const yOffset = -100;
          const y = el.getBoundingClientRect().top + window.pageYOffset + yOffset;
          window.scrollTo({ top: y, behavior: 'smooth' });

          const focusable = el.querySelector('input, select, button');
          if (focusable) {
            focusable.focus({ preventScroll: true });
          }
        }
      }, 50);
      return;
    }

    setFieldErrors({});
    setSubmitting(true);

    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();

      if (!session) {
        throw new Error('Your session has expired. Please log in again.');
      }

      const res = await fetch('/api/submit-investor-profile', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${session.access_token}`,
        },
        body: JSON.stringify({
          ...formData,
          consent_accepted: true,
        }),
      });

      const json = await res.json();

      if (!res.ok) {
        if (res.status === 409) {
          setExistingProfile({
            submitted_at: json.submitted_at || new Date().toISOString(),
            full_name: formData.full_name,
            primary_goal: formData.primary_goal,
          });
          return;
        }
        throw new Error(json.error || 'Failed to submit investor profile.');
      }

      setSubmissionSuccess(json.profile || true);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (err) {
      console.error('Submission error:', err);
      setErrorMsg(err.message || 'An error occurred during submission. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  // ── Render Loading State ──────────────────────────────────────────────────
  if (authLoading) {
    return (
      <div className="invest-page">
        <div className="r6-status-msg" style={{ minHeight: '50vh' }}>
          <div className="r6-spinner" />
          <p>Verifying investor profile session…</p>
        </div>
      </div>
    );
  }

  // ── Render Already Submitted State ────────────────────────────────────────
  if (existingProfile) {
    const formattedDate = new Date(existingProfile.submitted_at).toLocaleDateString('en-IN', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    });

    return (
      <div className="invest-page">
        <div className="container" style={{ maxWidth: '840px', padding: '3rem 1.5rem' }}>
          <div className="profile-submitted-card">
            <div className="profile-submitted-badge">✅ Profile Already Received</div>
            <h2>Investor Profile on Record</h2>
            <p className="profile-submitted-intro">
              Thank you, <strong>{existingProfile.full_name || user?.user_metadata?.full_name || 'Investor'}</strong>.
              Your Mutual Fund Suitability Assessment was successfully recorded on <strong>{formattedDate}</strong>.
            </p>

            <div className="profile-submitted-summary">
              <div className="profile-summary-row">
                <span>AMFI ARN Registration:</span>
                <strong>ARN-310735 (Wealthyneers)</strong>
              </div>
              {existingProfile.primary_goal && (
                <div className="profile-summary-row">
                  <span>Primary Recorded Goal:</span>
                  <strong>{existingProfile.primary_goal}</strong>
                </div>
              )}
              <div className="profile-summary-row">
                <span>Assessment Status:</span>
                <span className="status-pill status-active">Active Profile</span>
              </div>
            </div>

            <div className="profile-submitted-notice">
              <p>
                To maintain regulatory compliance and audit trails, investor suitability questionnaires are limited to
                one active submission per account. If your financial goals, liquidity needs, or risk parameters have
                changed, please connect directly with our advisory desk.
              </p>
            </div>

            <div className="profile-submitted-actions">
              <Link href="/contact" className="btn btn-primary">
                📞 Contact Investment Desk
              </Link>
              <Link href="/dashboard" className="btn btn-outline">
                📊 Open Dashboard
              </Link>
              <Link href="/invest" className="btn btn-secondary">
                🎯 Invest with Us Guide
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ── Render Submission Success State ───────────────────────────────────────
  if (submissionSuccess) {
    return (
      <div className="invest-page">
        <div className="container" style={{ maxWidth: '840px', padding: '3rem 1.5rem' }}>
          <div className="profile-submitted-card success-gradient">
            <div className="profile-submitted-badge">🎉 Assessment Submitted</div>
            <h2>Investor Profile Successfully Recorded</h2>
            <p className="profile-submitted-intro">
              Thank you for completing your suitability assessment. Our research and distribution desk has received your
              financial parameters and will prepare your tailored mutual fund asset allocation review.
            </p>

            <div className="profile-submitted-summary">
              <div className="profile-summary-row">
                <span>Investor Name:</span>
                <strong>{formData.full_name}</strong>
              </div>
              <div className="profile-summary-row">
                <span>Primary Goal:</span>
                <strong>{formData.primary_goal}</strong>
              </div>
              <div className="profile-summary-row">
                <span>Target Horizon:</span>
                <strong>{formData.primary_goal_timeline}</strong>
              </div>
            </div>

            <div className="profile-submitted-actions">
              <Link href="/dashboard" className="btn btn-primary">
                📊 Explore Research Dashboard
              </Link>
              <Link href="/invest" className="btn btn-outline">
                🎯 Return to Invest with Us
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ── Render Pre-Form Warning Acknowledgement Screen ───────────────────────
  if (!acknowledgedWarning) {
    return (
      <div className="invest-page">
        <div className="container" style={{ maxWidth: '780px', padding: '3rem 1.5rem 5rem' }}>
          <div className="pre-warning-card">
            <div className="pre-warning-badge">
              <span>ONE-TIME SUBMISSION</span>
            </div>
            <h1
              style={{
                fontSize: '2rem',
                fontWeight: 800,
                color: 'var(--foreground)',
                marginBottom: '1rem',
                letterSpacing: '-0.02em',
              }}
            >
              Before You Begin
            </h1>
            <p
              style={{
                fontSize: '1.05rem',
                color: 'var(--secondary)',
                lineHeight: 1.65,
                marginBottom: '1.25rem',
              }}
            >
              This investor profile can be submitted <strong>only once</strong>.
            </p>
            <p
              style={{
                fontSize: '0.96rem',
                color: 'var(--secondary)',
                lineHeight: 1.65,
                marginBottom: '1.25rem',
              }}
            >
              Please take your time and answer each question carefully. Your responses will help us understand your
              investment objectives, financial situation, investment experience, and risk preferences.
            </p>
            <p
              style={{
                fontSize: '0.96rem',
                color: 'var(--foreground)',
                fontWeight: 600,
                lineHeight: 1.6,
                marginBottom: '1.5rem',
              }}
            >
              Once submitted, your responses cannot be edited or resubmitted.
            </p>

            <div className="pre-warning-callout">
              <div className="pre-warning-item">
                <span style={{ fontSize: '1.2rem' }}>📋</span>
                <div>
                  <strong>5-Section Assessment:</strong> Covers your goals, time horizon, financial capacity, market reaction, and risk profile.
                </div>
              </div>
              <div className="pre-warning-item">
                <span style={{ fontSize: '1.2rem' }}>🔒</span>
                <div>
                  <strong>Single Submission per Account:</strong> Designed to maintain a clear and consistent investor profile for your account.
                </div>
              </div>
              <div className="pre-warning-item">
                <span style={{ fontSize: '1.2rem' }}>⚖️</span>
                <div>
                  <strong>Non-Editable After Submission:</strong> Please double-check your numbers and selections before final submission.
                </div>
              </div>
            </div>

            <label className="pre-warning-ack" htmlFor="oneTimeAckCheckbox">
              <input
                id="oneTimeAckCheckbox"
                type="checkbox"
                checked={understoodOneTime}
                onChange={(e) => setUnderstoodOneTime(e.target.checked)}
                aria-label="I understand that I can submit this profile only once and that I will not be able to edit my responses after submission."
              />
              <span>
                I understand that I can submit this profile only once and that I will not be able to edit my responses after submission.
              </span>
            </label>

            <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
              <button
                type="button"
                disabled={!understoodOneTime}
                onClick={() => {
                  setAcknowledgedWarning(true);
                  window.scrollTo({ top: 0, behavior: 'smooth' });
                }}
                className="btn btn-primary"
                style={{
                  padding: '0.85rem 2rem',
                  fontSize: '1rem',
                  fontWeight: 600,
                  opacity: understoodOneTime ? 1 : 0.45,
                  cursor: understoodOneTime ? 'pointer' : 'not-allowed',
                  transition: 'all 0.2s ease',
                }}
                aria-disabled={!understoodOneTime}
              >
                Continue to Investor Profile →
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ── Render Native Questionnaire Form ─────────────────────────────────────
  return (
    <div className="invest-page">
      <div className="container" style={{ maxWidth: '880px', padding: '2.5rem 1.25rem 5rem' }}>
        {/* Header Title & Branding */}
        <div className="questionnaire-header">
          <div className="invest-badge">ARN-310735 · AMFI Registered Distributor</div>
          <h1>Investor Profile &amp; Mutual Fund Suitability Assessment</h1>
          <p className="questionnaire-desc">
            This assessment records your goals, time horizon, financial capacity, investment experience, and risk-related
            preferences to generate an indicative suitability profile and asset allocation strategy for discussion with our
            distribution team.
          </p>
        </div>

        {/* Introductory Guidance Section */}
        <div
          className="q-guidance-card"
          style={{
            background: 'var(--card-bg, #ffffff)',
            border: '1px solid var(--border, #e2e8f0)',
            borderRadius: '1rem',
            padding: '1.25rem 1.5rem',
            marginBottom: '2rem',
            boxShadow: '0 2px 8px rgba(0, 0, 0, 0.02)',
          }}
        >
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '0.85rem',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.85rem' }}>
              <span
                style={{
                  width: '1.5rem',
                  height: '1.5rem',
                  borderRadius: '50%',
                  backgroundColor: 'rgba(10, 77, 104, 0.09)',
                  color: 'var(--primary, #0a4d68)',
                  fontSize: '0.8rem',
                  fontWeight: 700,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                  marginTop: '0.1rem',
                }}
              >
                1
              </span>
              <p style={{ margin: 0, fontSize: '0.94rem', color: 'var(--foreground)', lineHeight: 1.55, fontWeight: 500 }}>
                Glad you have taken the first step.
              </p>
            </div>

            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.85rem' }}>
              <span
                style={{
                  width: '1.5rem',
                  height: '1.5rem',
                  borderRadius: '50%',
                  backgroundColor: 'rgba(10, 77, 104, 0.09)',
                  color: 'var(--primary, #0a4d68)',
                  fontSize: '0.8rem',
                  fontWeight: 700,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                  marginTop: '0.1rem',
                }}
              >
                2
              </span>
              <p style={{ margin: 0, fontSize: '0.94rem', color: 'var(--foreground)', lineHeight: 1.55, fontWeight: 500 }}>
                Let&apos;s navigate through some questions. We have to understand your investment objectives, goals and mindset.
              </p>
            </div>

            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.85rem' }}>
              <span
                style={{
                  width: '1.5rem',
                  height: '1.5rem',
                  borderRadius: '50%',
                  backgroundColor: 'rgba(10, 77, 104, 0.09)',
                  color: 'var(--primary, #0a4d68)',
                  fontSize: '0.8rem',
                  fontWeight: 700,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                  marginTop: '0.1rem',
                }}
              >
                3
              </span>
              <p style={{ margin: 0, fontSize: '0.94rem', color: 'var(--foreground)', lineHeight: 1.55, fontWeight: 500 }}>
                This will give clarity to both of us and we will be able to discuss wealth management more effectively.
              </p>
            </div>
          </div>
        </div>

        {/* Global Error Banner */}
        {errorMsg && (
          <div className="r6-error-bar" style={{ marginBottom: '2rem' }}>
            ⚠️ {errorMsg}
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate className="questionnaire-form">
          {/* ── SECTION 01: INVESTOR DETAILS ─────────────────────────────── */}
          <div className="q-section-card">
            <div className="q-section-header">
              <span className="q-section-num">01</span>
              <div>
                <h2>Investor Details</h2>
                <p>Primary identification details for portfolio registration.</p>
              </div>
            </div>

            <div className="q-grid-2">
              <div
                id="q-field-full_name"
                className={fieldErrors.full_name ? 'q-field q-field-has-error' : 'q-field'}
              >
                <label>
                  Investor Name <span className="req-star">*</span>
                </label>
                <input
                  type="text"
                  placeholder="e.g. Rahul Sharma"
                  value={formData.full_name}
                  onChange={(e) => setSingleValue('full_name', e.target.value)}
                  className={`q-input ${fieldErrors.full_name ? 'q-input-error' : ''}`}
                  aria-invalid={Boolean(fieldErrors.full_name)}
                  required
                />
                {fieldErrors.full_name && (
                  <div className="q-field-error-msg">
                    <span>⚠️</span> {fieldErrors.full_name}
                  </div>
                )}
              </div>

              <div
                id="q-field-mobile_number"
                className={fieldErrors.mobile_number ? 'q-field q-field-has-error' : 'q-field'}
              >
                <label>
                  Mobile Number <span className="req-star">*</span>
                </label>
                <input
                  type="tel"
                  placeholder="10-digit mobile number"
                  value={formData.mobile_number}
                  onChange={(e) => setSingleValue('mobile_number', e.target.value)}
                  className={`q-input ${fieldErrors.mobile_number ? 'q-input-error' : ''}`}
                  aria-invalid={Boolean(fieldErrors.mobile_number)}
                  required
                />
                {fieldErrors.mobile_number && (
                  <div className="q-field-error-msg">
                    <span>⚠️</span> {fieldErrors.mobile_number}
                  </div>
                )}
              </div>
            </div>

            <div className="q-field" style={{ marginTop: '1.25rem' }}>
              <label>Email Address</label>
              <input
                type="email"
                placeholder="investor@example.com"
                value={formData.email_address}
                onChange={(e) => setSingleValue('email_address', e.target.value)}
                className="q-input"
              />
              <span className="q-hint">Associated with your Wealthyneers account.</span>
            </div>

            <div
              id="q-field-age_group"
              className={fieldErrors.age_group ? 'q-field q-field-has-error' : 'q-field'}
              style={{ marginTop: '1.5rem' }}
            >
              <label>
                Age Group <span className="req-star">*</span>
              </label>
              <div className="q-options-grid cols-5">
                {AGE_GROUPS.map((opt) => (
                  <button
                    type="button"
                    key={opt}
                    onClick={() => setSingleValue('age_group', opt)}
                    className={`q-opt-btn ${formData.age_group === opt ? 'q-opt-btn-selected' : ''}`}
                  >
                    {opt}
                  </button>
                ))}
              </div>
              {fieldErrors.age_group && (
                <div className="q-field-error-msg">
                  <span>⚠️</span> {fieldErrors.age_group}
                </div>
              )}
            </div>
          </div>

          {/* ── SECTION 02: YOUR GOALS ───────────────────────────────────── */}
          <div className="q-section-card">
            <div className="q-section-header">
              <span className="q-section-num">02</span>
              <div>
                <h2>Your Financial Goals</h2>
                <p>Define your wealth objectives, timeline, and priorities.</p>
              </div>
            </div>

            <div
              id="q-field-investing_for"
              className={fieldErrors.investing_for ? 'q-field q-field-has-error' : 'q-field'}
            >
              <label>
                What are you investing for? (Select all that apply) <span className="req-star">*</span>
              </label>
              <div className="q-options-grid cols-2">
                {GOAL_OPTIONS.map((opt) => {
                  const isChecked = formData.investing_for.includes(opt);
                  return (
                    <button
                      type="button"
                      key={opt}
                      onClick={() => toggleArrayItem('investing_for', opt)}
                      className={`q-check-card ${isChecked ? 'q-check-card-selected' : ''}`}
                    >
                      <span className="q-checkbox-box">{isChecked ? '✓' : ''}</span>
                      <span>{opt}</span>
                    </button>
                  );
                })}
              </div>
              {fieldErrors.investing_for && (
                <div className="q-field-error-msg">
                  <span>⚠️</span> {fieldErrors.investing_for}
                </div>
              )}
            </div>

            <div
              id="q-field-primary_goal"
              className={fieldErrors.primary_goal ? 'q-field q-field-has-error' : 'q-field'}
              style={{ marginTop: '1.75rem' }}
            >
              <label>
                Which one is your primary goal for this assessment? <span className="req-star">*</span>
              </label>
              <select
                value={formData.primary_goal}
                onChange={(e) => setSingleValue('primary_goal', e.target.value)}
                className={`q-select ${fieldErrors.primary_goal ? 'q-input-error' : ''}`}
                aria-invalid={Boolean(fieldErrors.primary_goal)}
                required
              >
                <option value="">-- Select your primary goal --</option>
                {GOAL_OPTIONS.map((opt) => (
                  <option key={opt} value={opt}>
                    {opt}
                  </option>
                ))}
              </select>
              {fieldErrors.primary_goal && (
                <div className="q-field-error-msg">
                  <span>⚠️</span> {fieldErrors.primary_goal}
                </div>
              )}
            </div>

            <div
              id="q-field-primary_goal_amount"
              className={fieldErrors.primary_goal_amount ? 'q-field q-field-has-error' : 'q-field'}
              style={{ marginTop: '1.5rem' }}
            >
              <label>
                Approximately how much will you require for your primary goal? (₹) <span className="req-star">*</span>
              </label>
              <input
                type="text"
                placeholder="e.g. ₹25,00,000 or 50 Lakhs"
                value={formData.primary_goal_amount}
                onChange={(e) => setSingleValue('primary_goal_amount', e.target.value)}
                className={`q-input ${fieldErrors.primary_goal_amount ? 'q-input-error' : ''}`}
                aria-invalid={Boolean(fieldErrors.primary_goal_amount)}
                required
              />
              {fieldErrors.primary_goal_amount && (
                <div className="q-field-error-msg">
                  <span>⚠️</span> {fieldErrors.primary_goal_amount}
                </div>
              )}
            </div>

            <div
              id="q-field-primary_goal_timeline"
              className={fieldErrors.primary_goal_timeline ? 'q-field q-field-has-error' : 'q-field'}
              style={{ marginTop: '1.5rem' }}
            >
              <label>
                When will you require money for your primary goal? <span className="req-star">*</span>
              </label>
              <div className="q-options-grid cols-3">
                {TIMELINE_OPTIONS.map((opt) => (
                  <button
                    type="button"
                    key={opt}
                    onClick={() => setSingleValue('primary_goal_timeline', opt)}
                    className={`q-opt-btn ${formData.primary_goal_timeline === opt ? 'q-opt-btn-selected' : ''}`}
                  >
                    {opt}
                  </button>
                ))}
              </div>
              {fieldErrors.primary_goal_timeline && (
                <div className="q-field-error-msg">
                  <span>⚠️</span> {fieldErrors.primary_goal_timeline}
                </div>
              )}
            </div>

            <div
              id="q-field-primary_goal_importance"
              className={fieldErrors.primary_goal_importance ? 'q-field q-field-has-error' : 'q-field'}
              style={{ marginTop: '1.5rem' }}
            >
              <label>
                How important is this primary goal? <span className="req-star">*</span>
              </label>
              <div className="q-options-grid cols-1">
                {IMPORTANCE_OPTIONS.map((opt) => (
                  <button
                    type="button"
                    key={opt}
                    onClick={() => setSingleValue('primary_goal_importance', opt)}
                    className={`q-radio-card ${formData.primary_goal_importance === opt ? 'q-radio-card-selected' : ''}`}
                  >
                    <span className="q-radio-dot">{formData.primary_goal_importance === opt && <span />}</span>
                    <span>{opt}</span>
                  </button>
                ))}
              </div>
              {fieldErrors.primary_goal_importance && (
                <div className="q-field-error-msg">
                  <span>⚠️</span> {fieldErrors.primary_goal_importance}
                </div>
              )}
            </div>
          </div>

          {/* ── SECTION 03: FINANCIAL CAPACITY ──────────────────────────── */}
          <div className="q-section-card">
            <div className="q-section-header">
              <span className="q-section-num">03</span>
              <div>
                <h2>Available Funds &amp; Financial Capacity</h2>
                <p>Assess your investment liquidity, cash flow, and emergency buffer.</p>
              </div>
            </div>

            <div
              id="q-field-available_funds_sources"
              className={fieldErrors.available_funds_sources ? 'q-field q-field-has-error' : 'q-field'}
            >
              <label>
                Which statements describe the money available for investment? (Select all that apply){' '}
                <span className="req-star">*</span>
              </label>
              <div className="q-options-grid cols-2">
                {FUND_SOURCES.map((opt) => {
                  const isChecked = formData.available_funds_sources.includes(opt);
                  return (
                    <button
                      type="button"
                      key={opt}
                      onClick={() => toggleArrayItem('available_funds_sources', opt)}
                      className={`q-check-card ${isChecked ? 'q-check-card-selected' : ''}`}
                    >
                      <span className="q-checkbox-box">{isChecked ? '✓' : ''}</span>
                      <span>{opt}</span>
                    </button>
                  );
                })}
              </div>
              {fieldErrors.available_funds_sources && (
                <div className="q-field-error-msg">
                  <span>⚠️</span> {fieldErrors.available_funds_sources}
                </div>
              )}
            </div>

            <div className="q-grid-2" style={{ marginTop: '1.5rem' }}>
              <div
                id="q-field-lump_sum_amount"
                className={fieldErrors.lump_sum_amount ? 'q-field q-field-has-error' : 'q-field'}
              >
                <label>
                  Lump sum genuinely available today (₹) <span className="req-star">*</span>
                </label>
                <input
                  type="text"
                  placeholder="e.g. ₹5,00,000 (enter 0 if none)"
                  value={formData.lump_sum_amount}
                  onChange={(e) => setSingleValue('lump_sum_amount', e.target.value)}
                  className={`q-input ${fieldErrors.lump_sum_amount ? 'q-input-error' : ''}`}
                  aria-invalid={Boolean(fieldErrors.lump_sum_amount)}
                  required
                />
                {fieldErrors.lump_sum_amount && (
                  <div className="q-field-error-msg">
                    <span>⚠️</span> {fieldErrors.lump_sum_amount}
                  </div>
                )}
              </div>

              <div
                id="q-field-monthly_sip_amount"
                className={fieldErrors.monthly_sip_amount ? 'q-field q-field-has-error' : 'q-field'}
              >
                <label>
                  Monthly SIP capacity (₹) <span className="req-star">*</span>
                </label>
                <input
                  type="text"
                  placeholder="e.g. ₹25,000 / month (enter 0 if none)"
                  value={formData.monthly_sip_amount}
                  onChange={(e) => setSingleValue('monthly_sip_amount', e.target.value)}
                  className={`q-input ${fieldErrors.monthly_sip_amount ? 'q-input-error' : ''}`}
                  aria-invalid={Boolean(fieldErrors.monthly_sip_amount)}
                  required
                />
                {fieldErrors.monthly_sip_amount && (
                  <div className="q-field-error-msg">
                    <span>⚠️</span> {fieldErrors.monthly_sip_amount}
                  </div>
                )}
              </div>
            </div>

            <div
              id="q-field-emergency_reserve_duration"
              className={fieldErrors.emergency_reserve_duration ? 'q-field q-field-has-error' : 'q-field'}
              style={{ marginTop: '1.5rem' }}
            >
              <label>
                How much emergency reserve do you currently maintain? <span className="req-star">*</span>
              </label>
              <div className="q-options-grid cols-3">
                {EMERGENCY_RESERVE_OPTIONS.map((opt) => (
                  <button
                    type="button"
                    key={opt}
                    onClick={() => setSingleValue('emergency_reserve_duration', opt)}
                    className={`q-opt-btn ${formData.emergency_reserve_duration === opt ? 'q-opt-btn-selected' : ''}`}
                  >
                    {opt}
                  </button>
                ))}
              </div>
              {fieldErrors.emergency_reserve_duration && (
                <div className="q-field-error-msg">
                  <span>⚠️</span> {fieldErrors.emergency_reserve_duration}
                </div>
              )}
            </div>

            <div
              id="q-field-fixed_obligations_percentage"
              className={fieldErrors.fixed_obligations_percentage ? 'q-field q-field-has-error' : 'q-field'}
              style={{ marginTop: '1.5rem' }}
            >
              <label>
                How much of your monthly income is committed to EMIs and fixed obligations?{' '}
                <span className="req-star">*</span>
              </label>
              <div className="q-options-grid cols-3">
                {FIXED_OBLIGATIONS_OPTIONS.map((opt) => (
                  <button
                    type="button"
                    key={opt}
                    onClick={() => setSingleValue('fixed_obligations_percentage', opt)}
                    className={`q-opt-btn ${formData.fixed_obligations_percentage === opt ? 'q-opt-btn-selected' : ''}`}
                  >
                    {opt}
                  </button>
                ))}
              </div>
              {fieldErrors.fixed_obligations_percentage && (
                <div className="q-field-error-msg">
                  <span>⚠️</span> {fieldErrors.fixed_obligations_percentage}
                </div>
              )}
            </div>

            <div
              id="q-field-income_stability"
              className={fieldErrors.income_stability ? 'q-field q-field-has-error' : 'q-field'}
              style={{ marginTop: '1.5rem' }}
            >
              <label>
                Which statements best describe your income situation? (Select all that apply){' '}
                <span className="req-star">*</span>
              </label>
              <div className="q-options-grid cols-2">
                {INCOME_SITUATION_OPTIONS.map((opt) => {
                  const isChecked = formData.income_stability.includes(opt);
                  return (
                    <button
                      type="button"
                      key={opt}
                      onClick={() => toggleArrayItem('income_stability', opt)}
                      className={`q-check-card ${isChecked ? 'q-check-card-selected' : ''}`}
                    >
                      <span className="q-checkbox-box">{isChecked ? '✓' : ''}</span>
                      <span>{opt}</span>
                    </button>
                  );
                })}
              </div>
              {fieldErrors.income_stability && (
                <div className="q-field-error-msg">
                  <span>⚠️</span> {fieldErrors.income_stability}
                </div>
              )}
            </div>

            <div
              id="q-field-unexpected_need_likelihood"
              className={fieldErrors.unexpected_need_likelihood ? 'q-field q-field-has-error' : 'q-field'}
              style={{ marginTop: '1.5rem' }}
            >
              <label>
                How likely are you to need part of this investment unexpectedly? <span className="req-star">*</span>
              </label>
              <div className="q-options-grid cols-1">
                {UNEXPECTED_NEED_OPTIONS.map((opt) => (
                  <button
                    type="button"
                    key={opt}
                    onClick={() => setSingleValue('unexpected_need_likelihood', opt)}
                    className={`q-radio-card ${formData.unexpected_need_likelihood === opt ? 'q-radio-card-selected' : ''}`}
                  >
                    <span className="q-radio-dot">{formData.unexpected_need_likelihood === opt && <span />}</span>
                    <span>{opt}</span>
                  </button>
                ))}
              </div>
              {fieldErrors.unexpected_need_likelihood && (
                <div className="q-field-error-msg">
                  <span>⚠️</span> {fieldErrors.unexpected_need_likelihood}
                </div>
              )}
            </div>
          </div>

          {/* ── SECTION 04: EXPERIENCE & RISK BEHAVIOUR ─────────────────── */}
          <div className="q-section-card">
            <div className="q-section-header">
              <span className="q-section-num">04</span>
              <div>
                <h2>Investment Experience &amp; Risk Behaviour</h2>
                <p>Gauge your market exposure and emotional comfort with volatility.</p>
              </div>
            </div>

            <div
              id="q-field-investment_experience"
              className={fieldErrors.investment_experience ? 'q-field q-field-has-error' : 'q-field'}
            >
              <label>
                Which investments have you personally used? (Select all that apply) <span className="req-star">*</span>
              </label>
              <div className="q-options-grid cols-3">
                {INVESTMENT_EXPERIENCE_OPTIONS.map((opt) => {
                  const isChecked = formData.investment_experience.includes(opt);
                  return (
                    <button
                      type="button"
                      key={opt}
                      onClick={() => toggleArrayItem('investment_experience', opt)}
                      className={`q-check-card ${isChecked ? 'q-check-card-selected' : ''}`}
                    >
                      <span className="q-checkbox-box">{isChecked ? '✓' : ''}</span>
                      <span>{opt}</span>
                    </button>
                  );
                })}
              </div>
              {fieldErrors.investment_experience && (
                <div className="q-field-error-msg">
                  <span>⚠️</span> {fieldErrors.investment_experience}
                </div>
              )}
            </div>

            <div
              id="q-field-market_reaction_scenario"
              className={fieldErrors.market_reaction_scenario ? 'q-field q-field-has-error' : 'q-field'}
              style={{ marginTop: '1.75rem' }}
            >
              <label>
                If ₹10 lakh invested for a long-term goal temporarily falls to ₹8 lakh, what could you see yourself
                doing? <span className="req-star">*</span>
              </label>
              <div className="q-options-grid cols-2">
                {MARKET_REACTION_OPTIONS.map((opt) => {
                  const isChecked = formData.market_reaction_scenario.includes(opt);
                  return (
                    <button
                      type="button"
                      key={opt}
                      onClick={() => toggleArrayItem('market_reaction_scenario', opt)}
                      className={`q-check-card ${isChecked ? 'q-check-card-selected' : ''}`}
                    >
                      <span className="q-checkbox-box">{isChecked ? '✓' : ''}</span>
                      <span>{opt}</span>
                    </button>
                  );
                })}
              </div>
              {fieldErrors.market_reaction_scenario && (
                <div className="q-field-error-msg">
                  <span>⚠️</span> {fieldErrors.market_reaction_scenario}
                </div>
              )}
            </div>

            <div
              id="q-field-tolerable_drawdown"
              className={fieldErrors.tolerable_drawdown ? 'q-field q-field-has-error' : 'q-field'}
              style={{ marginTop: '1.75rem' }}
            >
              <label>
                Which levels of temporary decline do you believe you could tolerate without abandoning your investment
                plan? <span className="req-star">*</span>
              </label>
              <div className="q-options-grid cols-4">
                {TOLERABLE_DRAWDOWN_OPTIONS.map((opt) => (
                  <button
                    type="button"
                    key={opt}
                    onClick={() => setSingleValue('tolerable_drawdown', opt)}
                    className={`q-opt-btn ${formData.tolerable_drawdown === opt ? 'q-opt-btn-selected' : ''}`}
                  >
                    {opt}
                  </button>
                ))}
              </div>
              {fieldErrors.tolerable_drawdown && (
                <div className="q-field-error-msg">
                  <span>⚠️</span> {fieldErrors.tolerable_drawdown}
                </div>
              )}
            </div>

            <div
              id="q-field-risk_attitude_statements"
              className={fieldErrors.risk_attitude_statements ? 'q-field q-field-has-error' : 'q-field'}
              style={{ marginTop: '1.75rem' }}
            >
              <label>
                Which statements genuinely describe you? (Select all that apply) <span className="req-star">*</span>
              </label>
              <div className="q-options-grid cols-1">
                {RISK_ATTITUDE_OPTIONS.map((opt) => {
                  const isChecked = formData.risk_attitude_statements.includes(opt);
                  return (
                    <button
                      type="button"
                      key={opt}
                      onClick={() => toggleArrayItem('risk_attitude_statements', opt)}
                      className={`q-check-card ${isChecked ? 'q-check-card-selected' : ''}`}
                    >
                      <span className="q-checkbox-box">{isChecked ? '✓' : ''}</span>
                      <span>{opt}</span>
                    </button>
                  );
                })}
              </div>
              {fieldErrors.risk_attitude_statements && (
                <div className="q-field-error-msg">
                  <span>⚠️</span> {fieldErrors.risk_attitude_statements}
                </div>
              )}
            </div>

            <div
              id="q-field-risk_profile_self_assessment"
              className={fieldErrors.risk_profile_self_assessment ? 'q-field q-field-has-error' : 'q-field'}
              style={{ marginTop: '1.75rem' }}
            >
              <label>
                How would you describe yourself? <span className="req-star">*</span>
              </label>
              <div className="q-options-grid cols-2">
                {RISK_PROFILES.map((p) => (
                  <button
                    type="button"
                    key={p.label}
                    onClick={() => setSingleValue('risk_profile_self_assessment', p.label)}
                    className={`q-radio-card-rich ${formData.risk_profile_self_assessment === p.label ? 'q-radio-card-rich-selected' : ''}`}
                  >
                    <div className="q-radio-rich-header">
                      <span className="q-radio-dot">
                        {formData.risk_profile_self_assessment === p.label && <span />}
                      </span>
                      <strong>{p.label}</strong>
                    </div>
                    <p className="q-radio-rich-desc">{p.desc}</p>
                  </button>
                ))}
              </div>
              {fieldErrors.risk_profile_self_assessment && (
                <div className="q-field-error-msg">
                  <span>⚠️</span> {fieldErrors.risk_profile_self_assessment}
                </div>
              )}
            </div>
          </div>

          {/* ── SECTION 05: STATUTORY DECLARATION ───────────────────────── */}
          <div className="q-section-card declaration-card">
            <div className="q-section-header">
              <span className="q-section-num">05</span>
              <div>
                <h2>Declaration &amp; Client Consent</h2>
                <p>Please confirm the statutory mutual fund disclosures below before submitting.</p>
              </div>
            </div>

            <div
              id="q-field-declaration_confirmations"
              className={fieldErrors.declaration_confirmations ? 'declaration-list q-field-has-error' : 'declaration-list'}
            >
              {DECLARATION_STATEMENTS.map((stmt, idx) => {
                const isChecked = formData.declaration_confirmations.includes(stmt);
                return (
                  <label key={idx} className="declaration-item">
                    <input
                      type="checkbox"
                      checked={isChecked}
                      onChange={() => toggleArrayItem('declaration_confirmations', stmt)}
                      className="declaration-checkbox"
                    />
                    <span className="declaration-text">{stmt}</span>
                  </label>
                );
              })}
            </div>
            {fieldErrors.declaration_confirmations && (
              <div className="q-field-error-msg" style={{ marginTop: '0.75rem' }}>
                <span>⚠️</span> {fieldErrors.declaration_confirmations}
              </div>
            )}

            <div className="declaration-legal-footer">
              <p>
                By submitting this suitability assessment, you acknowledge Wealthyneers&apos;{' '}
                <Link href="/privacy" target="_blank" className="legal-link">
                  Privacy Policy
                </Link>{' '}
                and{' '}
                <Link href="/terms" target="_blank" className="legal-link">
                  Terms of Service
                </Link>
                . Mutual fund investments are subject to market risks, read all scheme related documents carefully.
              </p>
            </div>

            {/* Final Submission Reminder */}
            <div className="final-check-box">
              <h4>
                <span>⚠️</span> Final Check
              </h4>
              <p>
                Please review your answers carefully before submitting. Once submitted, your investor profile cannot
                be edited or submitted again.
              </p>
            </div>

            {/* Viewport Error Banner for Submit Action */}
            {errorMsg && (
              <div className="q-submit-error-banner">
                <span>⚠️</span> {errorMsg}
              </div>
            )}

            <div className="q-submit-wrap">
              <button type="submit" disabled={submitting} className="btn btn-primary q-submit-btn">
                {submitting ? (
                  <>
                    <span className="q-btn-spinner" /> Recording Assessment…
                  </>
                ) : (
                  'Submit Investor Profile →'
                )}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
