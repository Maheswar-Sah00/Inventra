/** Client-side checks that mirror the backend rules, so users get feedback before submitting. */

export type FieldErrors = Record<string, string>;

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function validateEmail(email: string): string | null {
  if (!email.trim()) return "Email is required";
  if (!EMAIL_PATTERN.test(email.trim())) return "Enter a valid email address";
  return null;
}

export function validateName(name: string): string | null {
  const cleaned = name.trim().replace(/\s+/g, " ");
  if (!cleaned) return "Name is required";
  if (cleaned.length < 2) return "Name must be at least 2 characters";
  if (cleaned.length > 100) return "Name must be at most 100 characters";
  return null;
}

export function validatePassword(password: string): string | null {
  if (!password) return "Password is required";
  if (password.length < 8) return "Password must be at least 8 characters";
  if (password.length > 128) return "Password must be at most 128 characters";
  if (!/[A-Za-z]/.test(password) || !/\d/.test(password)) return "Password must contain at least one letter and one number";
  if (password !== password.trim()) return "Password must not start or end with a space";
  return null;
}

export function validatePasswordConfirmation(password: string, confirmation: string): string | null {
  if (!confirmation) return "Please confirm your password";
  if (password !== confirmation) return "Passwords do not match";
  return null;
}

export function validateOtp(otp: string, length = 6): string | null {
  if (!otp.trim()) return "Enter the verification code";
  if (!new RegExp(`^\\d{${length}}$`).test(otp.trim())) return `The code is ${length} digits`;
  return null;
}

/** Drop null entries so an empty object means "valid". */
export function collectErrors(errors: Record<string, string | null>): FieldErrors {
  return Object.fromEntries(Object.entries(errors).filter((entry): entry is [string, string] => entry[1] !== null));
}
