import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import { getClientIp, checkRateLimit, rateLimitExceededResponse } from '@/lib/rateLimit';
import { sendEmail } from '@/lib/email';

// Rate Limiting Policy: 3 submissions per 60 minutes per user & per IP
const RATE_LIMIT_WINDOW_MS = 60 * 60 * 1000; // 1 hour
const RATE_LIMIT_MAX_REQUESTS = 3;

// Downstream Google Form Endpoint
const GOOGLE_FORM_RESPONSE_URL =
  'https://docs.google.com/forms/d/e/1FAIpQLScKNYzxq7k0FIDupJlV5O3CriIZv_4mAvviinENNUc8mbqVig/formResponse';

// Exact 22 Question Google Entry IDs
const GOOGLE_ENTRY_IDS = {
  full_name: 'entry.1375558614',
  mobile_number: 'entry.2127674691',
  email_address: 'entry.1982925898',
  age_group: 'entry.344139151',
  investing_for: 'entry.1906568948',
  primary_goal: 'entry.1433604488',
  primary_goal_amount: 'entry.1819781148',
  primary_goal_timeline: 'entry.923522605',
  primary_goal_importance: 'entry.1313325434',
  available_funds_sources: 'entry.181461661',
  lump_sum_amount: 'entry.1194398697',
  monthly_sip_amount: 'entry.274757880',
  emergency_reserve_duration: 'entry.374875586',
  fixed_obligations_percentage: 'entry.64816438',
  income_stability: 'entry.1864313884',
  unexpected_need_likelihood: 'entry.2015117880',
  investment_experience: 'entry.923528941',
  market_reaction_scenario: 'entry.509950908',
  tolerable_drawdown: 'entry.888211208',
  risk_attitude_statements: 'entry.197251102',
  risk_profile_self_assessment: 'entry.1660736136',
  declaration_confirmations: 'entry.1968251437',
};

// Required declaration statements from the official assessment
const REQUIRED_DECLARATIONS = [
  'I confirm that the information provided is true and complete to the best of my knowledge.',
  'I understand that Mutual Fund investments are market-linked and returns are not guaranteed.',
  'I understand that this assessment is based on the information provided by me.',
  'I consent to my information being processed for preparing and maintaining my Mutual Fund investor profile.',
];

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function formatCurrency(val) {
  if (!val || val === '0') return 'Not specified';
  const num = Number(String(val).replace(/[^0-9.]/g, ''));
  if (isNaN(num) || num === 0) return String(val);
  return `₹${num.toLocaleString('en-IN')}`;
}

function renderFieldHtml(val) {
  if (Array.isArray(val)) {
    if (val.length === 0) return '<span style="color:#94a3b8;">Not specified</span>';
    return `<ul style="margin:4px 0 0 0;padding-left:18px;color:#cbd5e1;line-height:1.5;">${val
      .map((item) => `<li style="margin-bottom:3px;">${escapeHtml(String(item))}</li>`)
      .join('')}</ul>`;
  }
  if (val === null || val === undefined || val === '') {
    return '<span style="color:#94a3b8;">Not specified</span>';
  }
  return `<span style="color:#ffffff;font-weight:500;">${escapeHtml(String(val))}</span>`;
}

function renderFieldText(val) {
  if (Array.isArray(val)) {
    if (val.length === 0) return 'Not specified';
    return val.map((item) => `  • ${item}`).join('\n');
  }
  if (val === null || val === undefined || val === '') {
    return 'Not specified';
  }
  return String(val);
}

function getSupabaseClient(authToken) {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

  if (authToken) {
    return createClient(url, anonKey, {
      global: { headers: { Authorization: `Bearer ${authToken}` } },
      auth: { persistSession: false },
    });
  }

  if (serviceKey) {
    return createClient(url, serviceKey, {
      auth: { persistSession: false },
    });
  }

  return createClient(url, anonKey, {
    auth: { persistSession: false },
  });
}

function sanitizeNumericAmount(val) {
  if (typeof val === 'number') return String(val);
  if (!val || typeof val !== 'string') return '0';
  const cleaned = val.replace(/[^0-9.]/g, '');
  return cleaned.length > 0 ? cleaned : '0';
}

function buildGoogleFormData(profile) {
  const params = new URLSearchParams();

  const appendField = (key, value) => {
    const entryId = GOOGLE_ENTRY_IDS[key];
    if (!entryId) return;

    if (Array.isArray(value)) {
      value.forEach((v) => {
        if (v && typeof v === 'string' && v.trim().length > 0) {
          params.append(entryId, v.trim());
        }
      });
    } else if (value !== null && value !== undefined && typeof value === 'string') {
      params.append(entryId, value.trim());
    }
  };

  appendField('full_name', profile.full_name);
  appendField('mobile_number', profile.mobile_number);
  appendField('email_address', profile.email_address || '');
  appendField('age_group', profile.age_group);
  appendField('investing_for', profile.investing_for);
  appendField('primary_goal', profile.primary_goal);
  appendField('primary_goal_amount', sanitizeNumericAmount(profile.primary_goal_amount));
  appendField('primary_goal_timeline', profile.primary_goal_timeline);
  appendField('primary_goal_importance', profile.primary_goal_importance);
  appendField('available_funds_sources', profile.available_funds_sources);
  appendField('lump_sum_amount', sanitizeNumericAmount(profile.lump_sum_amount));
  appendField('monthly_sip_amount', sanitizeNumericAmount(profile.monthly_sip_amount));
  appendField('emergency_reserve_duration', profile.emergency_reserve_duration);
  appendField('fixed_obligations_percentage', profile.fixed_obligations_percentage);
  appendField('income_stability', profile.income_stability);
  appendField('unexpected_need_likelihood', profile.unexpected_need_likelihood);
  appendField('investment_experience', profile.investment_experience);
  appendField('market_reaction_scenario', profile.market_reaction_scenario);
  appendField('tolerable_drawdown', profile.tolerable_drawdown);
  appendField('risk_attitude_statements', profile.risk_attitude_statements);
  appendField('risk_profile_self_assessment', profile.risk_profile_self_assessment);
  appendField('declaration_confirmations', profile.declaration_confirmations);

  return params;
}

async function syncToGoogleForms(profile, syncRecordId, client) {
  try {
    const formData = buildGoogleFormData(profile);

    const response = await fetch(GOOGLE_FORM_RESPONSE_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: formData.toString(),
    });

    const isSuccess = response.ok || response.status === 200 || response.status === 302 || response.status === 303;

    if (syncRecordId && client) {
      await client
        .from('investor_profile_google_sync')
        .update({
          status: isSuccess ? 'submitted' : 'failed',
          http_status: response.status,
          attempts: 1,
          submitted_at: isSuccess ? new Date().toISOString() : null,
          last_attempt_at: new Date().toISOString(),
          error_message: isSuccess ? null : `Google Forms returned HTTP ${response.status}`,
          updated_at: new Date().toISOString(),
        })
        .eq('id', syncRecordId);
    }

    return { success: isSuccess, status: response.status };
  } catch (err) {
    console.error('Google Form sync network error:', err?.message || err);
    if (syncRecordId && client) {
      await client
        .from('investor_profile_google_sync')
        .update({
          status: 'failed',
          attempts: 1,
          last_attempt_at: new Date().toISOString(),
          error_message: err?.message || 'Network error during Google Form dispatch',
          updated_at: new Date().toISOString(),
        })
        .eq('id', syncRecordId);
    }
    return { success: false, status: 0 };
  }
}

/**
 * Builds HTML confirmation email for the submitting user.
 */
function buildUserConfirmationHtml({ profile }) {
  const displayName = profile.full_name ? profile.full_name.split(' ')[0] : 'Investor';

  return `
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Thank you for submitting your Investor Profile — Wealthyneers</title>
</head>
<body style="margin:0;padding:0;background-color:#061A23;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#e2e8f0;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#061A23;padding:30px 15px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" style="max-width:600px;background-color:#0A2635;border-radius:12px;border:1px solid #14425A;padding:32px 28px;text-align:left;">
          <tr>
            <td align="center" style="padding-bottom:20px;">
              <div style="font-size:22px;font-weight:800;letter-spacing:1px;color:#05BFDB;">
                WEALTHYNEERS
              </div>
              <div style="font-size:11px;letter-spacing:2px;color:#94a3b8;text-transform:uppercase;margin-top:3px;">
                Mutual Fund Suitability Assessment &bull; ARN-310735
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding-bottom:20px;">
              <h2 style="margin:0 0 10px 0;font-size:19px;font-weight:700;color:#ffffff;">
                Investor Profile Submitted Successfully
              </h2>
              <p style="margin:0 0 12px 0;font-size:14px;line-height:1.6;color:#cbd5e1;">
                Hello ${displayName},
              </p>
              <p style="margin:0 0 16px 0;font-size:14px;line-height:1.6;color:#cbd5e1;">
                Thank you for completing your Mutual Fund Investor Profile and Suitability Assessment on Wealthyneers. Your profile has been recorded in our system.
              </p>
              <p style="margin:0 0 16px 0;font-size:14px;line-height:1.6;color:#cbd5e1;">
                Here is a summary of the investment details and preferences you submitted:
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding-bottom:24px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#061A23;border-radius:8px;border:1px solid #14425A;padding:16px 18px;font-size:13px;">
                <tr>
                  <td style="padding:6px 0;color:#94a3b8;width:40%;">Full Name:</td>
                  <td style="padding:6px 0;color:#ffffff;font-weight:600;">${escapeHtml(profile.full_name)}</td>
                </tr>
                <tr>
                  <td style="padding:6px 0;color:#94a3b8;">Primary Goal:</td>
                  <td style="padding:6px 0;color:#ffffff;font-weight:600;">${escapeHtml(profile.primary_goal)}</td>
                </tr>
                <tr>
                  <td style="padding:6px 0;color:#94a3b8;">Target Goal Amount:</td>
                  <td style="padding:6px 0;color:#05BFDB;font-weight:700;">${formatCurrency(profile.primary_goal_amount)}</td>
                </tr>
                <tr>
                  <td style="padding:6px 0;color:#94a3b8;">Investment Horizon:</td>
                  <td style="padding:6px 0;color:#ffffff;font-weight:600;">${escapeHtml(profile.primary_goal_timeline)}</td>
                </tr>
                <tr>
                  <td style="padding:6px 0;color:#94a3b8;">Planned Lump Sum:</td>
                  <td style="padding:6px 0;color:#ffffff;font-weight:600;">${formatCurrency(profile.lump_sum_amount)}</td>
                </tr>
                <tr>
                  <td style="padding:6px 0;color:#94a3b8;">Planned Monthly SIP:</td>
                  <td style="padding:6px 0;color:#ffffff;font-weight:600;">${formatCurrency(profile.monthly_sip_amount)}</td>
                </tr>
                <tr>
                  <td style="padding:6px 0;color:#94a3b8;">Emergency Reserves:</td>
                  <td style="padding:6px 0;color:#ffffff;font-weight:600;">${escapeHtml(profile.emergency_reserve_duration)}</td>
                </tr>
                <tr>
                  <td style="padding:6px 0;color:#94a3b8;">Fixed Obligations:</td>
                  <td style="padding:6px 0;color:#ffffff;font-weight:600;">${escapeHtml(profile.fixed_obligations_percentage)}</td>
                </tr>
                <tr>
                  <td style="padding:6px 0;color:#94a3b8;vertical-align:top;">Income Stability:</td>
                  <td style="padding:6px 0;">${renderFieldHtml(profile.income_stability)}</td>
                </tr>
                <tr>
                  <td style="padding:6px 0;color:#94a3b8;vertical-align:top;">Investment Experience:</td>
                  <td style="padding:6px 0;">${renderFieldHtml(profile.investment_experience)}</td>
                </tr>
                <tr>
                  <td style="padding:6px 0;color:#94a3b8;">Self-Assessed Risk Profile:</td>
                  <td style="padding:6px 0;color:#05BFDB;font-weight:700;">${escapeHtml(profile.risk_profile_self_assessment)}</td>
                </tr>
                <tr>
                  <td style="padding:6px 0;color:#94a3b8;">Tolerable Drawdown:</td>
                  <td style="padding:6px 0;color:#ffffff;font-weight:600;">${escapeHtml(profile.tolerable_drawdown)}</td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding-bottom:20px;">
              <p style="margin:0 0 12px 0;font-size:14px;line-height:1.6;color:#cbd5e1;">
                Our advisory desk will review your profile to help align mutual fund research with your suitability parameters.
              </p>
              <p style="margin:0 0 4px 0;font-size:14px;line-height:1.6;color:#cbd5e1;">
                If you have questions or wish to discuss portfolio allocations, please contact us at <a href="mailto:support@wealthyneers.com" style="color:#05BFDB;text-decoration:none;">support@wealthyneers.com</a>.
              </p>
              <p style="margin:16px 0 0 0;font-size:14px;line-height:1.6;color:#94a3b8;font-weight:600;">
                &mdash; Team Wealthyneers
              </p>
            </td>
          </tr>
          <tr>
            <td style="border-top:1px solid #14425A;padding-top:18px;text-align:center;">
              <p style="margin:0;font-size:11px;color:#64748b;line-height:1.5;">
                Wealthyneers &bull; AMFI Registered Mutual Fund Distributor (ARN-310735)<br>
                Mutual Fund investments are subject to market risks. Read all scheme related documents carefully.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
  `.trim();
}

/**
 * Builds plain text confirmation email for the submitting user.
 */
function buildUserConfirmationText({ profile }) {
  const displayName = profile.full_name ? profile.full_name.split(' ')[0] : 'Investor';

  return `
WEALTHYNEERS - Mutual Fund Suitability Assessment (ARN-310735)

Hello ${displayName},

Thank you for completing your Mutual Fund Investor Profile and Suitability Assessment on Wealthyneers. Your profile has been recorded in our system.

SUMMARY OF SUBMITTED DETAILS:
--------------------------------------------------
• Full Name: ${profile.full_name}
• Primary Goal: ${profile.primary_goal}
• Target Goal Amount: ${formatCurrency(profile.primary_goal_amount)}
• Investment Horizon: ${profile.primary_goal_timeline}
• Planned Lump Sum: ${formatCurrency(profile.lump_sum_amount)}
• Planned Monthly SIP: ${formatCurrency(profile.monthly_sip_amount)}
• Emergency Reserves: ${profile.emergency_reserve_duration}
• Fixed Obligations: ${profile.fixed_obligations_percentage}
• Income Stability:
${renderFieldText(profile.income_stability)}
• Investment Experience:
${renderFieldText(profile.investment_experience)}
• Self-Assessed Risk Profile: ${profile.risk_profile_self_assessment}
• Tolerable Drawdown: ${profile.tolerable_drawdown}
--------------------------------------------------

Our advisory desk will review your profile to help align mutual fund research with your suitability parameters.

Need assistance or have questions? Contact support@wealthyneers.com.

— Team Wealthyneers
AMFI Registered Mutual Fund Distributor (ARN-310735)
  `.trim();
}

/**
 * Builds HTML notification email for the administrator.
 */
function buildAdminNotificationHtml({ profile, verifiedEmail, submittedAt }) {
  const formattedDate = new Date(submittedAt || Date.now()).toLocaleString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Asia/Kolkata',
  });

  return `
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>New Investor Profile Submission — ${escapeHtml(profile.full_name)}</title>
</head>
<body style="margin:0;padding:0;background-color:#061A23;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#e2e8f0;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#061A23;padding:30px 15px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" style="max-width:640px;background-color:#0A2635;border-radius:12px;border:1px solid #14425A;padding:32px 28px;text-align:left;">
          <tr>
            <td style="padding-bottom:16px;">
              <div style="font-size:20px;font-weight:800;letter-spacing:1px;color:#05BFDB;">
                WEALTHYNEERS ADMIN
              </div>
              <h2 style="margin:6px 0 0 0;font-size:18px;font-weight:700;color:#ffffff;">
                New Investor Profile Submitted
              </h2>
            </td>
          </tr>

          <!-- Submitter Metadata Card -->
          <tr>
            <td style="padding-bottom:20px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#061A23;border-radius:8px;border:1px solid #05BFDB;padding:14px 16px;font-size:13px;">
                <tr>
                  <td style="padding:4px 0;color:#94a3b8;width:35%;">Full Name:</td>
                  <td style="padding:4px 0;color:#ffffff;font-weight:700;font-size:14px;">${escapeHtml(profile.full_name)}</td>
                </tr>
                <tr>
                  <td style="padding:4px 0;color:#94a3b8;">Verified Email:</td>
                  <td style="padding:4px 0;color:#05BFDB;font-weight:600;">${escapeHtml(verifiedEmail)}</td>
                </tr>
                <tr>
                  <td style="padding:4px 0;color:#94a3b8;">Mobile Number:</td>
                  <td style="padding:4px 0;color:#ffffff;font-weight:600;">${escapeHtml(profile.mobile_number)}</td>
                </tr>
                <tr>
                  <td style="padding:4px 0;color:#94a3b8;">Submitted At:</td>
                  <td style="padding:4px 0;color:#cbd5e1;">${formattedDate} IST</td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Section 1 -->
          <tr>
            <td style="padding-bottom:16px;">
              <h3 style="margin:0 0 8px 0;font-size:14px;color:#05BFDB;text-transform:uppercase;letter-spacing:1px;">
                Section 1 &mdash; Personal Information
              </h3>
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#061A23;border-radius:6px;border:1px solid #14425A;padding:10px 14px;font-size:13px;">
                <tr><td style="padding:4px 0;color:#94a3b8;width:40%;">Full Name:</td><td style="padding:4px 0;">${renderFieldHtml(profile.full_name)}</td></tr>
                <tr><td style="padding:4px 0;color:#94a3b8;">Mobile Number:</td><td style="padding:4px 0;">${renderFieldHtml(profile.mobile_number)}</td></tr>
                <tr><td style="padding:4px 0;color:#94a3b8;">Email Address (Form):</td><td style="padding:4px 0;">${renderFieldHtml(profile.email_address)}</td></tr>
                <tr><td style="padding:4px 0;color:#94a3b8;">Age Group:</td><td style="padding:4px 0;">${renderFieldHtml(profile.age_group)}</td></tr>
              </table>
            </td>
          </tr>

          <!-- Section 2 -->
          <tr>
            <td style="padding-bottom:16px;">
              <h3 style="margin:0 0 8px 0;font-size:14px;color:#05BFDB;text-transform:uppercase;letter-spacing:1px;">
                Section 2 &mdash; Investment Goals &amp; Horizon
              </h3>
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#061A23;border-radius:6px;border:1px solid #14425A;padding:10px 14px;font-size:13px;">
                <tr><td style="padding:4px 0;color:#94a3b8;width:40%;vertical-align:top;">Investing For:</td><td style="padding:4px 0;">${renderFieldHtml(profile.investing_for)}</td></tr>
                <tr><td style="padding:4px 0;color:#94a3b8;">Primary Goal:</td><td style="padding:4px 0;">${renderFieldHtml(profile.primary_goal)}</td></tr>
                <tr><td style="padding:4px 0;color:#94a3b8;">Goal Amount:</td><td style="padding:4px 0;color:#05BFDB;font-weight:700;">${formatCurrency(profile.primary_goal_amount)}</td></tr>
                <tr><td style="padding:4px 0;color:#94a3b8;">Timeline:</td><td style="padding:4px 0;">${renderFieldHtml(profile.primary_goal_timeline)}</td></tr>
                <tr><td style="padding:4px 0;color:#94a3b8;">Importance:</td><td style="padding:4px 0;">${renderFieldHtml(profile.primary_goal_importance)}</td></tr>
              </table>
            </td>
          </tr>

          <!-- Section 3 -->
          <tr>
            <td style="padding-bottom:16px;">
              <h3 style="margin:0 0 8px 0;font-size:14px;color:#05BFDB;text-transform:uppercase;letter-spacing:1px;">
                Section 3 &mdash; Financial Situation &amp; Liquidity
              </h3>
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#061A23;border-radius:6px;border:1px solid #14425A;padding:10px 14px;font-size:13px;">
                <tr><td style="padding:4px 0;color:#94a3b8;width:40%;vertical-align:top;">Available Funds Sources:</td><td style="padding:4px 0;">${renderFieldHtml(profile.available_funds_sources)}</td></tr>
                <tr><td style="padding:4px 0;color:#94a3b8;">Lump Sum Amount:</td><td style="padding:4px 0;color:#05BFDB;font-weight:700;">${formatCurrency(profile.lump_sum_amount)}</td></tr>
                <tr><td style="padding:4px 0;color:#94a3b8;">Monthly SIP Amount:</td><td style="padding:4px 0;color:#05BFDB;font-weight:700;">${formatCurrency(profile.monthly_sip_amount)}</td></tr>
                <tr><td style="padding:4px 0;color:#94a3b8;">Emergency Reserve:</td><td style="padding:4px 0;">${renderFieldHtml(profile.emergency_reserve_duration)}</td></tr>
                <tr><td style="padding:4px 0;color:#94a3b8;">Fixed Obligations %:</td><td style="padding:4px 0;">${renderFieldHtml(profile.fixed_obligations_percentage)}</td></tr>
                <tr><td style="padding:4px 0;color:#94a3b8;vertical-align:top;">Income Stability:</td><td style="padding:4px 0;">${renderFieldHtml(profile.income_stability)}</td></tr>
                <tr><td style="padding:4px 0;color:#94a3b8;">Unexpected Need Likelihood:</td><td style="padding:4px 0;">${renderFieldHtml(profile.unexpected_need_likelihood)}</td></tr>
              </table>
            </td>
          </tr>

          <!-- Section 4 -->
          <tr>
            <td style="padding-bottom:16px;">
              <h3 style="margin:0 0 8px 0;font-size:14px;color:#05BFDB;text-transform:uppercase;letter-spacing:1px;">
                Section 4 &mdash; Risk Tolerance &amp; Investment Experience
              </h3>
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#061A23;border-radius:6px;border:1px solid #14425A;padding:10px 14px;font-size:13px;">
                <tr><td style="padding:4px 0;color:#94a3b8;width:40%;vertical-align:top;">Investment Experience:</td><td style="padding:4px 0;">${renderFieldHtml(profile.investment_experience)}</td></tr>
                <tr><td style="padding:4px 0;color:#94a3b8;vertical-align:top;">Market Reaction:</td><td style="padding:4px 0;">${renderFieldHtml(profile.market_reaction_scenario)}</td></tr>
                <tr><td style="padding:4px 0;color:#94a3b8;">Tolerable Drawdown:</td><td style="padding:4px 0;color:#05BFDB;font-weight:700;">${renderFieldHtml(profile.tolerable_drawdown)}</td></tr>
                <tr><td style="padding:4px 0;color:#94a3b8;vertical-align:top;">Risk Attitude:</td><td style="padding:4px 0;">${renderFieldHtml(profile.risk_attitude_statements)}</td></tr>
                <tr><td style="padding:4px 0;color:#94a3b8;">Self-Assessed Risk:</td><td style="padding:4px 0;color:#05BFDB;font-weight:700;">${renderFieldHtml(profile.risk_profile_self_assessment)}</td></tr>
              </table>
            </td>
          </tr>

          <!-- Section 5 -->
          <tr>
            <td style="padding-bottom:20px;">
              <h3 style="margin:0 0 8px 0;font-size:14px;color:#05BFDB;text-transform:uppercase;letter-spacing:1px;">
                Section 5 &mdash; Statutory Declarations &amp; Consent
              </h3>
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#061A23;border-radius:6px;border:1px solid #14425A;padding:10px 14px;font-size:13px;">
                <tr><td style="padding:4px 0;color:#94a3b8;width:40%;vertical-align:top;">Declarations Confirmed:</td><td style="padding:4px 0;">${renderFieldHtml(profile.declaration_confirmations)}</td></tr>
                <tr><td style="padding:4px 0;color:#94a3b8;">Consent Accepted:</td><td style="padding:4px 0;color:#22c55e;font-weight:700;">Yes (Confirmed)</td></tr>
              </table>
            </td>
          </tr>

          <tr>
            <td style="border-top:1px solid #14425A;padding-top:16px;text-align:center;">
              <p style="margin:0;font-size:11px;color:#64748b;line-height:1.5;">
                Wealthyneers Internal System Notification &bull; Confidential
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
  `.trim();
}

/**
 * Builds plain text notification email for the administrator.
 */
function buildAdminNotificationText({ profile, verifiedEmail, submittedAt }) {
  return `
WEALTHYNEERS - NEW INVESTOR PROFILE SUBMISSION
==================================================
Submitter Name:   ${profile.full_name}
Verified Email:   ${verifiedEmail}
Contact Mobile:   ${profile.mobile_number}
Submission Time:  ${submittedAt}
==================================================

SECTION 1 — PERSONAL INFORMATION
--------------------------------------------------
• Full Name: ${profile.full_name}
• Mobile Number: ${profile.mobile_number}
• Email Address (Form): ${profile.email_address}
• Age Group: ${profile.age_group}

SECTION 2 — INVESTMENT GOALS & HORIZON
--------------------------------------------------
• Investing For:
${renderFieldText(profile.investing_for)}
• Primary Goal: ${profile.primary_goal}
• Primary Goal Amount: ${formatCurrency(profile.primary_goal_amount)}
• Primary Goal Timeline: ${profile.primary_goal_timeline}
• Primary Goal Importance: ${profile.primary_goal_importance}

SECTION 3 — FINANCIAL SITUATION & LIQUIDITY
--------------------------------------------------
• Available Funds Sources:
${renderFieldText(profile.available_funds_sources)}
• Lump Sum Amount: ${formatCurrency(profile.lump_sum_amount)}
• Monthly SIP Amount: ${formatCurrency(profile.monthly_sip_amount)}
• Emergency Reserve Duration: ${profile.emergency_reserve_duration}
• Fixed Obligations Percentage: ${profile.fixed_obligations_percentage}
• Income Stability:
${renderFieldText(profile.income_stability)}
• Unexpected Need Likelihood: ${profile.unexpected_need_likelihood}

SECTION 4 — RISK TOLERANCE & INVESTMENT EXPERIENCE
--------------------------------------------------
• Investment Experience:
${renderFieldText(profile.investment_experience)}
• Market Reaction Scenario:
${renderFieldText(profile.market_reaction_scenario)}
• Tolerable Drawdown: ${profile.tolerable_drawdown}
• Risk Attitude Statements:
${renderFieldText(profile.risk_attitude_statements)}
• Risk Profile Self Assessment: ${profile.risk_profile_self_assessment}

SECTION 5 — STATUTORY DECLARATIONS & CONSENT
--------------------------------------------------
• Declarations Confirmed:
${renderFieldText(profile.declaration_confirmations)}
• Consent Accepted: Yes (Confirmed)
==================================================
  `.trim();
}

export async function POST(request) {
  try {
    // 1. Authenticate Request via Supabase Bearer Token
    const authHeader = request.headers.get('authorization') || '';
    const token = authHeader.startsWith('Bearer ') ? authHeader.substring(7).trim() : null;

    if (!token) {
      return NextResponse.json(
        { error: 'Authentication required. Please log in to submit your investor profile.' },
        { status: 401 }
      );
    }

    const userClient = getSupabaseClient(token);
    const {
      data: { user },
      error: userError,
    } = await userClient.auth.getUser(token);

    if (userError || !user) {
      return NextResponse.json(
        { error: 'Invalid or expired session. Please log in again.' },
        { status: 401 }
      );
    }

    const userId = user.id;

    // 2. Server-Side Rate Limiting (User UUID + Client IP)
    const clientIp = getClientIp(request);
    const userLimit = checkRateLimit(`profile:user:${userId}`, RATE_LIMIT_MAX_REQUESTS, RATE_LIMIT_WINDOW_MS);
    if (!userLimit.allowed) {
      return rateLimitExceededResponse(
        userLimit.resetInMs,
        'Too many profile submissions. Please wait before attempting again.'
      );
    }

    const ipLimit = checkRateLimit(`profile:ip:${clientIp}`, RATE_LIMIT_MAX_REQUESTS * 2, RATE_LIMIT_WINDOW_MS);
    if (!ipLimit.allowed) {
      return rateLimitExceededResponse(
        ipLimit.resetInMs,
        'Too many submissions from your connection. Please wait.'
      );
    }

    // 3. Parse and Sanitize Request Body
    let body;
    try {
      body = await request.json();
    } catch {
      return NextResponse.json({ error: 'Invalid JSON request payload.' }, { status: 400 });
    }

    const {
      full_name,
      mobile_number,
      email_address,
      age_group,
      investing_for,
      primary_goal,
      primary_goal_amount,
      primary_goal_timeline,
      primary_goal_importance,
      available_funds_sources,
      lump_sum_amount,
      monthly_sip_amount,
      emergency_reserve_duration,
      fixed_obligations_percentage,
      income_stability,
      unexpected_need_likelihood,
      investment_experience,
      market_reaction_scenario,
      tolerable_drawdown,
      risk_attitude_statements,
      risk_profile_self_assessment,
      declaration_confirmations,
      consent_accepted,
    } = body;

    // 4. Validate All Required Fields (Server-Side Enforcement)
    if (!full_name || typeof full_name !== 'string' || full_name.trim().length === 0) {
      return NextResponse.json({ error: 'Full name is required.' }, { status: 400 });
    }

    if (!mobile_number || typeof mobile_number !== 'string' || mobile_number.trim().length < 10) {
      return NextResponse.json(
        { error: 'A valid 10-digit mobile number is required.' },
        { status: 400 }
      );
    }

    if (!age_group) {
      return NextResponse.json({ error: 'Please select your age group.' }, { status: 400 });
    }

    if (!Array.isArray(investing_for) || investing_for.length === 0) {
      return NextResponse.json(
        { error: 'Please select at least one investment objective.' },
        { status: 400 }
      );
    }

    if (!primary_goal) {
      return NextResponse.json({ error: 'Please select your primary investment goal.' }, { status: 400 });
    }

    if (!primary_goal_amount || String(primary_goal_amount).trim().length === 0) {
      return NextResponse.json(
        { error: 'Please enter your estimated target amount for your primary goal.' },
        { status: 400 }
      );
    }

    if (!primary_goal_timeline) {
      return NextResponse.json(
        { error: 'Please select your timeline to achieve your primary goal.' },
        { status: 400 }
      );
    }

    if (!primary_goal_importance) {
      return NextResponse.json(
        { error: 'Please select the importance level of this goal.' },
        { status: 400 }
      );
    }

    if (!Array.isArray(available_funds_sources) || available_funds_sources.length === 0) {
      return NextResponse.json(
        { error: 'Please select at least one source of investable funds.' },
        { status: 400 }
      );
    }

    if (!lump_sum_amount || String(lump_sum_amount).trim().length === 0) {
      return NextResponse.json(
        { error: 'Please enter the initial lump-sum amount (or 0 if none).' },
        { status: 400 }
      );
    }

    if (!monthly_sip_amount || String(monthly_sip_amount).trim().length === 0) {
      return NextResponse.json(
        { error: 'Please enter the monthly SIP amount (or 0 if none).' },
        { status: 400 }
      );
    }

    if (!emergency_reserve_duration) {
      return NextResponse.json(
        { error: 'Please select your emergency reserve fund duration.' },
        { status: 400 }
      );
    }

    if (!fixed_obligations_percentage) {
      return NextResponse.json(
        { error: 'Please select your fixed monthly obligations level.' },
        { status: 400 }
      );
    }

    if (!Array.isArray(income_stability) || income_stability.length === 0) {
      return NextResponse.json(
        { error: 'Please select statements describing your income stability.' },
        { status: 400 }
      );
    }

    if (!unexpected_need_likelihood) {
      return NextResponse.json(
        { error: 'Please select the likelihood of needing invested funds unexpectedly.' },
        { status: 400 }
      );
    }

    if (!Array.isArray(investment_experience) || investment_experience.length === 0) {
      return NextResponse.json(
        { error: 'Please select your past investment experience.' },
        { status: 400 }
      );
    }

    if (!Array.isArray(market_reaction_scenario) || market_reaction_scenario.length === 0) {
      return NextResponse.json(
        { error: 'Please answer the market fluctuation scenario question.' },
        { status: 400 }
      );
    }

    if (!tolerable_drawdown) {
      return NextResponse.json(
        { error: 'Please select your tolerable drawdown level.' },
        { status: 400 }
      );
    }

    if (!Array.isArray(risk_attitude_statements) || risk_attitude_statements.length === 0) {
      return NextResponse.json(
        { error: 'Please select statements describing your risk attitude.' },
        { status: 400 }
      );
    }

    if (!risk_profile_self_assessment) {
      return NextResponse.json(
        { error: 'Please select your self-assessed risk profile.' },
        { status: 400 }
      );
    }

    // 5. Verify Declarations & Consent
    if (
      !Array.isArray(declaration_confirmations) ||
      declaration_confirmations.length < REQUIRED_DECLARATIONS.length ||
      !consent_accepted
    ) {
      return NextResponse.json(
        { error: 'You must review and agree to all 4 statutory confirmation statements before submitting.' },
        { status: 400 }
      );
    }

    // 6. Check for existing profile (Single Submission Enforcement)
    const { data: existingProfile } = await userClient
      .from('investor_profiles')
      .select('id, submitted_at')
      .eq('user_id', userId)
      .maybeSingle();

    if (existingProfile) {
      return NextResponse.json(
        {
          error: 'An investor profile has already been submitted for this account. If you need to make changes, please contact our investment desk.',
          already_submitted: true,
          submitted_at: existingProfile.submitted_at,
        },
        { status: 409 }
      );
    }

    // 7. Insert the New Investor Profile into Supabase (Source of Truth)
    const profilePayload = {
      user_id: userId,
      full_name: full_name.trim(),
      mobile_number: mobile_number.trim(),
      email_address: (email_address || user.email || '').trim().toLowerCase(),
      age_group,
      investing_for,
      primary_goal,
      primary_goal_amount: primary_goal_amount.trim(),
      primary_goal_timeline,
      primary_goal_importance,
      available_funds_sources,
      lump_sum_amount: lump_sum_amount.trim(),
      monthly_sip_amount: monthly_sip_amount.trim(),
      emergency_reserve_duration,
      fixed_obligations_percentage,
      income_stability,
      unexpected_need_likelihood,
      investment_experience,
      market_reaction_scenario,
      tolerable_drawdown,
      risk_attitude_statements,
      risk_profile_self_assessment,
      declaration_confirmations,
      consent_accepted: true,
      status: 'submitted',
      submitted_at: new Date().toISOString(),
    };

    const { data: newProfile, error: insertError } = await userClient
      .from('investor_profiles')
      .insert(profilePayload)
      .select('id, submitted_at, full_name, primary_goal')
      .single();

    if (insertError) {
      if (insertError.code === '23505') {
        return NextResponse.json(
          {
            error: 'An investor profile has already been submitted for this account.',
            already_submitted: true,
          },
          { status: 409 }
        );
      }
      console.error('Investor profile insert error:', insertError);
      return NextResponse.json(
        { error: 'Failed to record investor profile. Please try again or contact support.' },
        { status: 500 }
      );
    }

    // 8. Downstream Google Form Synchronization Tracking
    let syncRecordId = null;
    try {
      const { data: syncData } = await userClient
        .from('investor_profile_google_sync')
        .insert({
          investor_profile_id: newProfile.id,
          user_id: userId,
          status: 'pending',
          attempts: 0,
        })
        .select('id')
        .maybeSingle();

      if (syncData) {
        syncRecordId = syncData.id;
      }
    } catch (syncErr) {
      console.error('Note: sync record init notice:', syncErr?.message);
    }

    // 9. Dispatch Server-Side POST to Google Forms
    await syncToGoogleForms(profilePayload, syncRecordId, userClient);

    // 10. Dispatch Dual Email Notifications (Executed ONLY after successful database insertion)
    const verifiedUserEmail = (user.email || '').trim().toLowerCase();
    const adminEmail = (process.env.ADMIN_NOTIFICATION_EMAIL || '').trim().toLowerCase();

    // 10a. Dispatch Submitting User Confirmation Email
    if (verifiedUserEmail) {
      try {
        const userSubject = 'Thank you for submitting your Investor Profile — Wealthyneers';
        const userHtml = buildUserConfirmationHtml({
          profile: profilePayload,
        });
        const userText = buildUserConfirmationText({
          profile: profilePayload,
        });

        await sendEmail({
          to: verifiedUserEmail,
          subject: userSubject,
          html: userHtml,
          text: userText,
        });
      } catch (userEmailErr) {
        console.error('[submit-investor-profile] Failed to send user confirmation email:', userEmailErr?.message || 'SMTP error');
      }
    }

    // 10b. Dispatch Admin Notification Email
    if (adminEmail) {
      try {
        const adminSubject = `New Investor Profile Submission — ${profilePayload.full_name || 'Investor'}`;
        const adminHtml = buildAdminNotificationHtml({
          profile: profilePayload,
          verifiedEmail: verifiedUserEmail,
          submittedAt: profilePayload.submitted_at,
        });
        const adminText = buildAdminNotificationText({
          profile: profilePayload,
          verifiedEmail: verifiedUserEmail,
          submittedAt: profilePayload.submitted_at,
        });

        await sendEmail({
          to: adminEmail,
          subject: adminSubject,
          html: adminHtml,
          text: adminText,
        });
      } catch (adminEmailErr) {
        console.error('[submit-investor-profile] Failed to send admin notification email:', adminEmailErr?.message || 'SMTP error');
      }
    } else {
      console.warn('[submit-investor-profile] ADMIN_NOTIFICATION_EMAIL is not configured. Admin notification email skipped.');
    }

    // 11. Return HTTP 201 Success Response
    return NextResponse.json(
      {
        success: true,
        message: 'Investor profile submitted successfully.',
        profile: newProfile,
      },
      { status: 201 }
    );
  } catch (err) {
    console.error('Unexpected error in /api/submit-investor-profile:', err);
    return NextResponse.json(
      { error: 'An unexpected server error occurred while processing your submission.' },
      { status: 500 }
    );
  }
}
