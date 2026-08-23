import crypto from 'crypto';
import { NextResponse } from 'next/server';
import { supabaseAdmin } from '@/lib/supabaseAdmin';
import { sendEmail } from '@/lib/email';

export const dynamic = 'force-dynamic';

// Minimum record threshold required to consider a monthly cycle ready
const DATA_READINESS_MIN_RECORDS = 1000;

/**
 * Validates the CRON_SECRET authorization header using timing-safe comparison.
 */
function isAuthorized(request) {
  const cronSecret = (process.env.CRON_SECRET || '').trim();
  if (!cronSecret) {
    console.error('[cron/monthly-data-announcement] CRON_SECRET is not configured on the server.');
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
 * Generates the HTML email body for monthly data announcement.
 */
function buildMonthlyAnnouncementHtml({ fullName, exploreUrl }) {
  const displayName = fullName ? fullName.split(' ')[0] : 'Investor';

  return `
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>New Wealthyneers Research Data Is Now Available</title>
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
                New Monthly Research Data Is Now Available
              </h2>
              <p style="margin:0 0 16px 0;font-size:15px;line-height:1.6;color:#cbd5e1;">
                Hi ${displayName},
              </p>
              <p style="margin:0 0 16px 0;font-size:15px;line-height:1.6;color:#cbd5e1;">
                New monthly mutual fund data is now available on Wealthyneers.
              </p>
              <p style="margin:0 0 16px 0;font-size:15px;line-height:1.6;color:#cbd5e1;">
                Our latest institutional portfolio data has been added to the research platform, giving you access to the newest monthly insights across mutual funds and AMCs.
              </p>
              <p style="margin:0 0 24px 0;font-size:15px;line-height:1.6;color:#cbd5e1;">
                Log in to explore the latest data and research reports.
              </p>
            </td>
          </tr>
          <tr>
            <td align="center" style="padding-bottom:28px;">
              <a href="${exploreUrl}" target="_blank" style="display:inline-block;background-color:#05BFDB;color:#061A23;font-size:15px;font-weight:700;text-decoration:none;padding:14px 32px;border-radius:8px;letter-spacing:0.3px;">
                Go to Wealthyneers &rarr;
              </a>
            </td>
          </tr>
          <tr>
            <td style="padding-bottom:24px;">
              <p style="margin:0 0 4px 0;font-size:15px;line-height:1.6;color:#cbd5e1;">
                Regards,
              </p>
              <p style="margin:0;font-size:15px;line-height:1.6;color:#ffffff;font-weight:700;">
                Wealthyneers
              </p>
              <p style="margin:2px 0 0 0;font-size:13px;line-height:1.4;color:#94a3b8;">
                Seizing the Future
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
 * Generates the plain text email fallback for monthly data announcement.
 */
function buildMonthlyAnnouncementText({ fullName, exploreUrl }) {
  const displayName = fullName ? fullName.split(' ')[0] : 'Investor';

  return `
WEALTHYNEERS - Institutional Mutual Fund Research

Hi ${displayName},

New monthly mutual fund data is now available on Wealthyneers.

Our latest institutional portfolio data has been added to the research platform, giving you access to the newest monthly insights across mutual funds and AMCs.

Log in to explore the latest data and research reports:
${exploreUrl}

Regards,
Wealthyneers
Seizing the Future

Need assistance? Contact support@wealthyneers.com
  `.trim();
}

export async function GET(request) {
  return handleMonthlyAnnouncementCron(request);
}

export async function POST(request) {
  return handleMonthlyAnnouncementCron(request);
}

async function handleMonthlyAnnouncementCron(request) {
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
  const exploreUrl = `${siteUrl}/login`;

  const counts = {
    processed: 0,
    sent: 0,
    failed: 0,
    skipped: 0,
    test_mode: isTestMode,
  };

  try {
    // 2. Query Authoritative Latest Portfolio Date in public.fund_holdings
    // Uses aggregate read: retrieves only the single latest portfolio_date (0 holdings records exposed)
    const { data: latestDateRow, error: latestDateError } = await supabaseAdmin
      .from('fund_holdings')
      .select('portfolio_date')
      .order('portfolio_date', { ascending: false })
      .limit(1)
      .maybeSingle();

    if (latestDateError) {
      console.error('[cron/monthly-data-announcement] Failed to query latest portfolio_date:', latestDateError.message);
      return NextResponse.json(
        { success: false, error: 'Database query failed.', ...counts },
        { status: 500 }
      );
    }

    if (!latestDateRow || !latestDateRow.portfolio_date) {
      return NextResponse.json({
        success: true,
        message: 'No portfolio data found in database.',
        new_data: false,
        ...counts,
      });
    }

    const latestPortfolioDate = latestDateRow.portfolio_date;

    // 3. Verify Data-Readiness Threshold (Count >= 1,000 records for the latest portfolio_date)
    // Uses head: true to count exact matching rows without downloading any proprietary records
    const { count: recordCount, error: countError } = await supabaseAdmin
      .from('fund_holdings')
      .select('*', { count: 'exact', head: true })
      .eq('portfolio_date', latestPortfolioDate);

    if (countError) {
      console.error('[cron/monthly-data-announcement] Failed to count latest cycle records:', countError.message);
      return NextResponse.json(
        { success: false, error: 'Failed to verify record count.', ...counts },
        { status: 500 }
      );
    }

    const totalRecords = recordCount || 0;

    // Check if the latest cycle has passed the readiness threshold of 1,000 records
    if (totalRecords < DATA_READINESS_MIN_RECORDS) {
      return NextResponse.json({
        success: true,
        latest_portfolio_date: latestPortfolioDate,
        record_count: totalRecords,
        new_data: false,
        message: `Latest cycle record count (${totalRecords}) is below readiness threshold (${DATA_READINESS_MIN_RECORDS}). Announcement deferred.`,
        ...counts,
      });
    }

    // 4. Generate the Monthly Reference ID in YYYY-MM format
    const referenceId = latestPortfolioDate.substring(0, 7);

    // 5. Query Verified Target Users
    let targetUsers = [];

    if (isTestMode) {
      if (!testUserId) {
        console.warn('[cron/monthly-data-announcement] TEST_MODE is enabled but EMAIL_TEST_USER_ID is not configured.');
        return NextResponse.json({
          success: false,
          error: 'EMAIL_TEST_MODE is true, but EMAIL_TEST_USER_ID is missing or empty.',
          latest_portfolio_date: latestPortfolioDate,
          record_count: totalRecords,
          new_data: true,
          ...counts,
        });
      }

      // In test mode, fetch only the specified test user
      const { data: testUserData, error: testUserError } = await supabaseAdmin.auth.admin.getUserById(testUserId);
      if (testUserError || !testUserData?.user) {
        console.warn(`[cron/monthly-data-announcement] Test user ${testUserId} not found in auth.users.`);
        return NextResponse.json({
          success: false,
          error: `Test user ${testUserId} not found.`,
          latest_portfolio_date: latestPortfolioDate,
          record_count: totalRecords,
          new_data: true,
          ...counts,
        });
      }

      targetUsers = [testUserData.user];
    } else {
      // In production mode, fetch all users from Supabase Auth
      // Pagination support: fetch up to 1000 users per page
      let page = 1;
      let hasMore = true;

      while (hasMore) {
        const { data: pageData, error: pageError } = await supabaseAdmin.auth.admin.listUsers({
          page,
          perPage: 1000,
        });

        if (pageError) {
          console.error('[cron/monthly-data-announcement] Failed to list auth users:', pageError.message);
          return NextResponse.json(
            { success: false, error: 'Failed to retrieve user list.', ...counts },
            { status: 500 }
          );
        }

        const users = pageData?.users || [];
        targetUsers.push(...users);

        if (users.length < 1000) {
          hasMore = false;
        } else {
          page += 1;
        }
      }
    }

    // 6. Process Recipients and Send Announcements
    for (const user of targetUsers) {
      counts.processed += 1;

      // In test mode, strictly ensure no other user is processed
      if (isTestMode && user.id !== testUserId) {
        counts.skipped += 1;
        continue;
      }

      const recipientEmail = (user.email || '').trim().toLowerCase();
      const isEmailConfirmed = !!user.email_confirmed_at;

      // Strictly send ONLY to verified email accounts
      if (!recipientEmail || !isEmailConfirmed) {
        counts.skipped += 1;
        continue;
      }

      try {
        // 6a. Check public.email_logs to verify if this user already received an announcement for this cycle
        const { data: existingLog, error: logCheckError } = await supabaseAdmin
          .from('email_logs')
          .select('id, status')
          .eq('user_id', user.id)
          .eq('email_type', 'monthly_data_announcement')
          .eq('reference_id', referenceId)
          .eq('status', 'sent')
          .maybeSingle();

        if (logCheckError) {
          console.warn('[cron/monthly-data-announcement] Email log lookup warning:', logCheckError.message);
        }

        if (existingLog) {
          // Already successfully sent for this monthly cycle — skip to prevent duplicates
          counts.skipped += 1;
          continue;
        }

        const fullName = user.user_metadata?.full_name || '';

        const html = buildMonthlyAnnouncementHtml({
          fullName,
          exploreUrl,
        });

        const text = buildMonthlyAnnouncementText({
          fullName,
          exploreUrl,
        });

        // 6b. Dispatch Email via GoDaddy SMTP
        await sendEmail({
          to: recipientEmail,
          subject: 'New Wealthyneers Research Data Is Now Available',
          html,
          text,
        });

        // 6c. Record Successful Dispatch in public.email_logs
        await supabaseAdmin
          .from('email_logs')
          .upsert(
            {
              user_id: user.id,
              email_type: 'monthly_data_announcement',
              reference_id: referenceId,
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
        console.error(`[cron/monthly-data-announcement] Failed to send announcement to user ${user.id}:`, errMsg);

        // Record failed attempt in email_logs without altering user state
        try {
          await supabaseAdmin
            .from('email_logs')
            .upsert(
              {
                user_id: user.id,
                email_type: 'monthly_data_announcement',
                reference_id: referenceId,
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
      latest_portfolio_date: latestPortfolioDate,
      record_count: totalRecords,
      new_data: counts.sent > 0 || counts.processed > counts.skipped,
      ...counts,
    });
  } catch (globalError) {
    console.error('[cron/monthly-data-announcement] Fatal execution error:', globalError?.message || globalError);
    return NextResponse.json(
      { success: false, error: 'Internal cron execution error.', ...counts },
      { status: 500 }
    );
  }
}
