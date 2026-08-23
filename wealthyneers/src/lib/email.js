import nodemailer from 'nodemailer';

/**
 * Server-only email dispatch utility for Wealthyneers.
 * Uses GoDaddy SMTP (or custom SMTP configuration via environment variables).
 * 
 * IMPORTANT:
 * - This module must ONLY be imported and executed in server-side contexts (Route Handlers, Server Actions).
 * - Never import this file into Client Components.
 * - Credentials must remain strictly server-side (never use NEXT_PUBLIC_ variables).
 */

function getTransporter() {
  const host = (process.env.SMTP_HOST || 'smtpout.secureserver.net').trim();
  const port = parseInt(process.env.SMTP_PORT || '465', 10);
  const user = (process.env.SMTP_USER || 'admin@wealthyneers.com').trim();
  const pass = (process.env.SMTP_PASS || '').trim();

  if (!pass) {
    throw new Error('[email] SMTP_PASS environment variable is missing. Email dispatch aborted.');
  }

  const isSecure = port === 465;

  return nodemailer.createTransport({
    host,
    port,
    secure: isSecure,
    auth: {
      user,
      pass,
    },
    // Connection pool settings for efficient serverless execution
    pool: true,
    maxConnections: 3,
    maxMessages: 50,
  });
}

/**
 * Sends a transactional or notification email.
 *
 * @param {Object} options
 * @param {string} options.to - Recipient email address
 * @param {string} options.subject - Email subject line
 * @param {string} options.html - HTML formatted email body
 * @param {string} [options.text] - Optional plain text version
 * @param {string} [options.from] - Optional sender display (defaults to Wealthyneers <admin@wealthyneers.com>)
 * @returns {Promise<{ messageId: string, accepted: string[] }>}
 */
export async function sendEmail({ to, subject, html, text, from }) {
  if (!to || typeof to !== 'string' || !to.includes('@')) {
    throw new Error('[email] Invalid recipient email address.');
  }

  if (!subject || typeof subject !== 'string') {
    throw new Error('[email] Email subject is required.');
  }

  if (!html && !text) {
    throw new Error('[email] Email body (HTML or plain text) is required.');
  }

  const senderUser = (process.env.SMTP_USER || 'admin@wealthyneers.com').trim();
  const defaultFrom = `Wealthyneers <${senderUser}>`;

  const transporter = getTransporter();

  const mailOptions = {
    from: from || defaultFrom,
    to: to.trim().toLowerCase(),
    subject: subject.trim(),
    html: html || undefined,
    text: text || undefined,
  };

  try {
    const info = await transporter.sendMail(mailOptions);
    return {
      messageId: info.messageId,
      accepted: info.accepted || [to],
    };
  } catch (error) {
    // Sanitize error logging: log error code and message without exposing secrets
    console.error('[email] SMTP dispatch failed:', error?.code || error?.message || 'Unknown error');
    throw error;
  }
}
