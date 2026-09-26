/** Client-side checks mirroring the API rules. The API stays authoritative. */

const CODE_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._/-]*$/;
const QUANTITY_PATTERN = /^\d+(\.\d{1,3})?$/;
const MAX_QUANTITY = 99_999_999_999.999;

export function requiredText(value: string, label: string, maxLength = 100): string | null {
  const cleaned = value.trim();
  if (!cleaned) return `${label} is required`;
  if (cleaned.length > maxLength) return `${label} must be at most ${maxLength} characters`;
  return null;
}

export function validateCode(value: string, label = "Code", maxLength = 32): string | null {
  const cleaned = value.trim();
  if (!cleaned) return `${label} is required`;
  if (cleaned.length > maxLength) return `${label} must be at most ${maxLength} characters`;
  if (!CODE_PATTERN.test(cleaned)) return "Use letters, numbers and . _ / - only, starting with a letter or number";
  return null;
}

export function requiredSelection(value: string | number | null | undefined, label: string): string | null {
  return value === "" || value === null || value === undefined ? `Select a ${label}` : null;
}

/** Non-negative decimal with at most 3 decimal places. Empty is allowed when `optional`. */
export function validateQuantity(value: string, label: string, { optional = false } = {}): string | null {
  const cleaned = value.trim();
  if (!cleaned) return optional ? null : `${label} is required`;
  if (cleaned.startsWith("-")) return `${label} cannot be negative`;
  if (!QUANTITY_PATTERN.test(cleaned)) return `${label} must be a number with up to 3 decimals`;
  if (Number(cleaned) > MAX_QUANTITY) return `${label} is too large`;
  return null;
}

export function validateTarget(minimum: string, target: string): string | null {
  const error = validateQuantity(target, "Target quantity");
  if (error) return error;
  if (!validateQuantity(minimum, "Minimum quantity") && Number(target) < Number(minimum)) {
    return "Target quantity must be greater than or equal to the minimum quantity";
  }
  return null;
}
