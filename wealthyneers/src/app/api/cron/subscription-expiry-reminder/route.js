import crypto from 'crypto';
import { NextResponse } from 'next/server';
import { supabaseAdmin } from '@/lib/supabaseAdmin';
import { sendEmail } from '@/lib/email';

export const dynamic = 'force-dynamic';

/**
 * Validates the CRON_SECRET authorization header using timing-safe comparison.
 */
function isAuthorized(request) {
  const cronSecret = (process.env.CRON_SECRET || '').trim();
  if (!cronSecret) {
    console.error('[cron/subscription-expiry] CRON_SECRET is not configured on the server.');
    return false;
  }

  const authHeader = request.headers.get('authorization') || '';
  if (!authHeader.startsWith('Bearer ')) {
    return false;
  }

  const providedSecret = authHeader.substring(7).trim();

  const expectedBuf = Buffer.from(cronSecret, 'utf8');
  const providedBuf = Buffer.from(providedSecret, 'utf8');

  if (expectedBuf.length !== providedBuf.length) {
    return false;
  }

  return crypto.timingSafeEqual(expectedBuf, providedBuf);
}

/**
 * Generates the HTML email body for expired subscription notification.
 */
function buildExpiredEmailHtml({ fullName, renewUrl }) {
  const displayName = fullName ? fullName.split(' ')[0] : 'Investor';

  return `
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Your Wealthyneers access has expired</title>
</head>
<body style="margin:0;padding:0;background-color:#061A23;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#e2e8f0;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#061A23;padding:40px 15px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" style="max-width:560px;background-color:#0A2635;border-radius:12px;border:1px solid #14425A;padding:36px 32px;text-align:left;">
          <tr>
            <td align="center" style="padding-bottom:24px;">
              <div style="font-size:24px;font-weight:800;letter-spacing:1px;color:#05BFDB;">
                WEALTHYNEERS
              </div>
              <div style="font-size:12px;letter-spacing:2px;color:#94a3b8;text-transform:uppercase;margin-top:4px;">
                Institutional Mutual Fund Research
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding-bottom:20px;">
              <h2 style="margin:0 0 12px 0;font-size:20px;font-weight:700;color:#ffffff;">
                Your Access Has Expired
              </h2>
              <p style="margin:0 0 16px 0;font-size:15px;line-height:1.6;color:#cbd5e1;">
                Hello ${displayName},
              </p>
              <p style="margin:0 0 16px 0;font-size:15px;line-height:1.6;color:#cbd5e1;">
                Your Wealthyneers Premium access has now expired.
              </p>
              <p style="margin:0 0 16px 0;font-size:15px;line-height:1.6;color:#cbd5e1;">
                We hope you found Wealthyneers useful and that our research helped you gain better insights into institutional activity, mutual fund holdings, and market trends.
              </p>
              <p style="margin:0 0 16px 0;font-size:15px;line-height:1.6;color:#cbd5e1;">
                Your account is still active, but access to the premium research reports and interactive dashboard is currently locked.
              </p>
              <p style="margin:0 0 24px 0;font-size:15px;line-height:1.6;color:#cbd5e1;">
                If you would like to continue using Wealthyneers, you can renew your access for ₹30 and get another 30 days of premium access.
              </p>
            </td>
          </tr>
          <tr>
            <td align="center" style="padding-bottom:28px;">
              <a href="${renewUrl}" target="_blank" style="display:inline-block;background-color:#05BFDB;color:#061A23;font-size:15px;font-weight:700;text-decoration:none;padding:14px 32px;border-radius:8px;letter-spacing:0.3px;">
                Renew for ₹30 &rarr;
              </a>
            </td>
          </tr>
          <tr>
            <td style="padding-bottom:24px;">
              <p style="margin:0 0 4px 0;font-size:15px;line-height:1.6;color:#cbd5e1;">
                We&apos;d be happy to have you back.
              </p>
              <p style="margin:0;font-size:15px;line-height:1.6;color:#94a3b8;font-weight:600;">
                &mdash; Team Wealthyneers
              </p>
            </td>
          </tr>
          <tr>
            <td style="border-top:1px solid #14425A;padding-top:20px;text-align:center;">
              <p style="margin:0;font-size:12px;color:#64748b;line-height:1.5;">
                Wealthyneers &bull; Institutional-Grade Mutual Fund Portfolio Intelligence<br>
                Need assistance? Contact <a href="mailto:support@wealthyneers.com" style="color:#05BFDB;text-decoration:none;">support@wealthyneers.com</a>
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
 * Generates the plain text email fallback for expired subscription notification.
 */
function buildExpiredEmailText({ fullName, renewUrl }) {
  const displayName = fullName ? fullName.split(' ')[0] : 'Investor';

  return `
WEALTHYNEERS - Institutional Mutual Fund Research

Hello ${displayName},

Your Wealthyneers Premium access has now expired.

We hope you found Wealthyneers useful and that our research helped you gain better insights into institutional activity, mutual fund holdings, and market trends.

Your account is still active, but access to the premium research reports and interactive dashboard is currently locked.

If you would like to continue using Wealthyneers, you can renew your access for ₹30 and get another 30 days of premium access:
${renewUrl}

We'd be happy to have you back.

— Team Wealthyneers

Need assistance? Contact support@wealthyneers.com
  `.trim();
}

export async function GET(request) {
  return handleExpiryCron(request);
}

export async function POST(request) {
  return handleExpiryCron(request);
}

async function handleExpiryCron(request) {
  // 1. Validate Secret Authorization
  if (!isAuthorized(request)) {
    return NextResponse.json(
      { error: 'Unauthorized: Invalid or missing CRON_SECRET.' },
      { status: 401 }
    );
  }

  const isTestMode = process.env.EMAIL_TEST_MODE === 'true';
  const testUserId = (process.env.EMAIL_TEST_USER_ID || '').trim();

  const siteUrl = (process.env.NEXT_PUBLIC_SITE_URL || 'https://wealthyneers.com').replace(/\/$/, '');
  const renewUrl = `${siteUrl}/#pricing`;

  const counts = {
    processed: 0,
    sent: 0,
    failed: 0,
    skipped: 0,
    test_mode: isTestMode,
  };

  try {
    const now = new Date().toISOString();

    // 2. Query Subscriptions that have ALREADY EXPIRED (subscription_end_date < NOW)
    let subQuery = supabaseAdmin
      .from('subscriptions')
      .select('id, user_id, full_name, subscription_end_date, payment_status')
      .eq('payment_status', 'completed')
      .lt('subscription_end_date', now);

    // If Test Mode is active, restrict query strictly to the specified test user ID
    if (isTestMode) {
      if (!testUserId) {
        console.warn('[cron/subscription-expiry] TEST_MODE is enabled but EMAIL_TEST_USER_ID is not configured.');
        return NextResponse.json({
          success: false,
          error: 'EMAIL_TEST_MODE is true, but EMAIL_TEST_USER_ID is missing or empty.',
          ...counts,
        });
      }
      subQuery = subQuery.eq('user_id', testUserId);
    }

    const { data: expiredSubs, error: subError } = await subQuery;

    if (subError) {
      console.error('[cron/subscription-expiry] Failed to query expired subscriptions:', subError.message);
      return NextResponse.json(
        { success: false, error: 'Database query failed.', ...counts },
        { status: 500 }
      );
    }

    if (!expiredSubs || expiredSubs.length === 0) {
      return NextResponse.json({
        success: true,
        message: 'No subscriptions pending expiry reminder.',
        ...counts,
      });
    }

    // 3. Process Each Expired Subscription
    for (const sub of expiredSubs) {
      counts.processed += 1;

      // In test mode, strictly ensure no other user is processed
      if (isTestMode && sub.user_id !== testUserId) {
        counts.skipped += 1;
        continue;
      }

      let recipientEmail = '';
      try {
        // 3a. Check public.email_logs for existing notification for this specific subscription ID
        const { data: existingLog, error: logCheckError } = await supabaseAdmin
          .from('email_logs')
          .select('id, status')
          .eq('user_id', sub.user_id)
          .eq('email_type', 'subscription_expired')
          .eq('reference_id', sub.id)
          .eq('status', 'sent')
          .maybeSingle();

        if (logCheckError) {
          console.warn('[cron/subscription-expiry] Email log lookup warning:', logCheckError.message);
        }

        if (existingLog) {
          // Already sent for this subscription cycle — skip to prevent repeated emails
          counts.skipped += 1;
          continue;
        }

        // 3b. Verify user email and email confirmation status from Supabase Auth
        const { data: authUserData, error: authUserError } = await supabaseAdmin.auth.admin.getUserById(sub.user_id);

        if (authUserError || !authUserData?.user) {
          console.warn(`[cron/subscription-expiry] User not found in auth.users for sub ${sub.id}`);
          counts.skipped += 1;
          continue;
        }

        const authUser = authUserData.user;
        recipientEmail = authUser.email || '';
        const isEmailConfirmed = !!authUser.email_confirmed_at;

        // Strictly send ONLY to verified email accounts
        if (!recipientEmail || !isEmailConfirmed) {
          counts.skipped += 1;
          continue;
        }

        const fullName = sub.full_name || authUser.user_metadata?.full_name || '';

        const html = buildExpiredEmailHtml({
          fullName,
          renewUrl,
        });

        const text = buildExpiredEmailText({
          fullName,
          renewUrl,
        });

        // 3c. Dispatch Email via SMTP
        await sendEmail({
          to: recipientEmail,
          subject: 'Your Wealthyneers access has expired',
          html,
          text,
        });

        // 3d. Record Successful Dispatch in public.email_logs
        await supabaseAdmin
          .from('email_logs')
          .upsert(
            {
              user_id: sub.user_id,
              email_type: 'subscription_expired',
              reference_id: sub.id,
              recipient_email: recipientEmail,
              status: 'sent',
              error_message: null,
              sent_at: new Date().toISOString(),
            },
            { onConflict: 'user_id,email_type,reference_id' }
          );

        counts.sent += 1;
      } catch (sendErr) {
        counts.failed += 1;
        const errMsg = sendErr?.message || 'SMTP dispatch error';
        console.error(`[cron/subscription-expiry] Failed to send expired notice for subscription ${sub.id}:`, errMsg);

        // Record failed attempt in email_logs without blocking or altering subscriptions
        try {
          await supabaseAdmin
            .from('email_logs')
            .upsert(
              {
                user_id: sub.user_id,
                email_type: 'subscription_expired',
                reference_id: sub.id,
                recipient_email: recipientEmail || 'unknown',
                status: 'failed',
                error_message: errMsg.substring(0, 500),
                sent_at: new Date().toISOString(),
              },
              { onConflict: 'user_id,email_type,reference_id' }
            );
        } catch (_) {}
      }
    }

    return NextResponse.json({
      success: true,
      ...counts,
    });
  } catch (globalError) {
    console.error('[cron/subscription-expiry] Fatal execution error:', globalError?.message || globalError);
    return NextResponse.json(
      { success: false, error: 'Internal cron execution error.', ...counts },
      { status: 500 }
    );
  }
}
