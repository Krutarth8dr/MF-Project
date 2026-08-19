/**
 * Validation utilities for User Full Name & Password Security Requirements.
 * Wealthyneers Authentication Security System.
 */

/**
 * Validates a user's full name.
 * Requirements:
 * - English letters A-Z / a-z, spaces, hyphens (-), apostrophes (')
 * - Min 2 characters, max 100 characters
 * - Trimmed leading/trailing whitespace
 * - Rejects numbers, special characters, html/scripts, or symbols
 *
 * @param {string} name
 * @returns {{ valid: boolean, error: string | null, value: string }}
 */
export function validateFullName(name) {
  if (!name || typeof name !== 'string') {
    return { valid: false, error: 'Please enter a valid full name.', value: '' };
  }

  // Normalize spaces
  const trimmed = name.trim().replace(/\s+/g, ' ');

  if (trimmed.length < 2 || trimmed.length > 100) {
    return { valid: false, error: 'Please enter a valid full name.', value: trimmed };
  }

  // Regex allows English letters, spaces, hyphens, and apostrophes between letter sequences.
  // Must start and end with a letter.
  const nameRegex = /^[A-Za-z]+(?:[' -][A-Za-z]+)*$/;
  if (!nameRegex.test(trimmed)) {
    return { valid: false, error: 'Please enter a valid full name.', value: trimmed };
  }

  return { valid: true, error: null, value: trimmed };
}

/**
 * Evaluates password security criteria.
 * Requirements:
 * - Minimum 8 characters
 * - At least 1 uppercase letter (A-Z)
 * - At least 1 lowercase letter (a-z)
 * - At least 1 number (0-9)
 * - At least 1 special character (!@#$%^&*()_+-=[]{};':"|,.<>/?`~)
 *
 * @param {string} pw
 * @returns {{
 *   minLength: boolean,
 *   hasUpper: boolean,
 *   hasLower: boolean,
 *   hasNumber: boolean,
 *   hasSpecial: boolean,
 *   isValid: boolean,
 *   error: string | null
 * }}
 */
export function checkPasswordRequirements(pw) {
  const password = typeof pw === 'string' ? pw : '';

  const minLength = password.length >= 8;
  const hasUpper = /[A-Z]/.test(password);
  const hasLower = /[a-z]/.test(password);
  const hasNumber = /[0-9]/.test(password);
  // Any non-alphanumeric character is considered a special character
  const hasSpecial = /[^A-Za-z0-9]/.test(password);

  const isValid = minLength && hasUpper && hasLower && hasNumber && hasSpecial;

  return {
    minLength,
    hasUpper,
    hasLower,
    hasNumber,
    hasSpecial,
    isValid,
    error: isValid ? null : 'Password does not meet the requirements.',
  };
}
