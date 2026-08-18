import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import { getClientIp, checkRateLimit, rateLimitExceededResponse } from '@/lib/rateLimit';

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
    return { success: false, error: err?.message };
  }
}

export async function POST(request) {
  try {
    // 1. Extract Authorization Token
    const authHeader = request.headers.get('authorization') || '';
    const token = authHeader.startsWith('Bearer ') ? authHeader.substring(7).trim() : null;

    if (!token) {
      return NextResponse.json(
        { error: 'Authentication required. Please log in to submit your investor profile.' },
        { status: 401 }
      );
    }

    // 2. Verify Authenticated User via Supabase
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

    // 3. Server-Side Rate Limiting (Dual Dimension: User UUID + Client IP)
    const clientIp = getClientIp(request);
    const userLimit = checkRateLimit(`profile:user:${userId}`, RATE_LIMIT_MAX_REQUESTS, RATE_LIMIT_WINDOW_MS);
    if (!userLimit.allowed) {
      return rateLimitExceededResponse(
        userLimit.resetInMs,
        'Too many profile submission attempts. Please wait before submitting again.'
      );
    }

    const ipLimit = checkRateLimit(`profile:ip:${clientIp}`, RATE_LIMIT_MAX_REQUESTS, RATE_LIMIT_WINDOW_MS);
    if (!ipLimit.allowed) {
      return rateLimitExceededResponse(
        ipLimit.resetInMs,
        'Too many profile submission requests from this network. Please wait.'
      );
    }

    // 4. Parse Request Body
    const body = await request.json();
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

    // 4. Server-side Validation of All Required Fields
    if (!full_name || typeof full_name !== 'string' || full_name.trim().length < 2) {
      return NextResponse.json({ error: 'Please provide a valid full name.' }, { status: 400 });
    }

    if (!mobile_number || !/^\+?[0-9]{10,13}$/.test(mobile_number.replace(/[\s-]/g, ''))) {
      return NextResponse.json(
        { error: 'Please provide a valid 10-digit mobile number.' },
        { status: 400 }
      );
    }

    if (!age_group) {
      return NextResponse.json({ error: 'Please select your age group.' }, { status: 400 });
    }

    if (!Array.isArray(investing_for) || investing_for.length === 0) {
      return NextResponse.json(
        { error: 'Please select at least one investment goal.' },
        { status: 400 }
      );
    }

    if (!primary_goal) {
      return NextResponse.json({ error: 'Please select your primary goal.' }, { status: 400 });
    }

    if (!primary_goal_amount || primary_goal_amount.trim().length === 0) {
      return NextResponse.json(
        { error: 'Please specify the approximate amount required for your primary goal.' },
        { status: 400 }
      );
    }

    if (!primary_goal_timeline) {
      return NextResponse.json(
        { error: 'Please select your primary goal time horizon.' },
        { status: 400 }
      );
    }

    if (!primary_goal_importance) {
      return NextResponse.json(
        { error: 'Please select the importance of your primary goal.' },
        { status: 400 }
      );
    }

    if (!Array.isArray(available_funds_sources) || available_funds_sources.length === 0) {
      return NextResponse.json(
        { error: 'Please select the sources of funds available for investment.' },
        { status: 400 }
      );
    }

    if (!lump_sum_amount || lump_sum_amount.trim().length === 0) {
      return NextResponse.json(
        { error: 'Please specify the lump sum available (enter 0 if none).' },
        { status: 400 }
      );
    }

    if (!monthly_sip_amount || monthly_sip_amount.trim().length === 0) {
      return NextResponse.json(
        { error: 'Please specify the monthly SIP capacity (enter 0 if none).' },
        { status: 400 }
      );
    }

    if (!emergency_reserve_duration) {
      return NextResponse.json(
        { error: 'Please select your emergency reserve duration.' },
        { status: 400 }
      );
    }

    if (!fixed_obligations_percentage) {
      return NextResponse.json(
        { error: 'Please select your monthly fixed obligations percentage.' },
        { status: 400 }
      );
    }

    if (!Array.isArray(income_stability) || income_stability.length === 0) {
      return NextResponse.json(
        { error: 'Please describe your income situation.' },
        { status: 400 }
      );
    }

    if (!unexpected_need_likelihood) {
      return NextResponse.json(
        { error: 'Please indicate how likely you may need these funds unexpectedly.' },
        { status: 400 }
      );
    }

    if (!Array.isArray(investment_experience) || investment_experience.length === 0) {
      return NextResponse.json(
        { error: 'Please select your investment experience.' },
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

    // 10. Return HTTP 201 Success Response
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
