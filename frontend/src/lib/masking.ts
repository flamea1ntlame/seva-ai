/**
 * Frontend PII Masking Utilities for SEVA AI.
 * 
 * Masks sensitive identifiers (Aadhaar, PAN, phone numbers) before rendering
 * in citizen-facing presentation layers.
 * 
 * RULE: Does NOT alter underlying data; applies only to display output.
 * Non-sensitive fields (names, addresses, income amounts, dates) remain unmasked.
 */

/**
 * Mask 12-digit Aadhaar number
 * Input: "1234 5678 9012" or "123456789012"
 * Output: "XXXX XXXX 9012"
 */
export function maskAadhaar(value: string): string {
  if (!value) return "";
  const cleaned = String(value).replace(/[\s-]/g, "");
  if (cleaned.length === 12 && /^\d{12}$/.test(cleaned)) {
    const last4 = cleaned.slice(-4);
    return `XXXX XXXX ${last4}`;
  }
  // If partial or formatted differently with 12 chars
  if (cleaned.length >= 8) {
    const last4 = cleaned.slice(-4);
    return `XXXXXXXX${last4}`;
  }
  return value;
}

/**
 * Mask 10-character Indian Permanent Account Number (PAN)
 * Format: 5 letters, 4 digits, 1 letter (e.g. "ABCDE1234F")
 * Output: "XXXXXX1234F" or "ABXXXXXX4F"
 */
export function maskPan(value: string): string {
  if (!value) return "";
  const cleaned = String(value).trim().toUpperCase();
  if (cleaned.length === 10 && /^[A-Z]{5}\d{4}[A-Z]$/.test(cleaned)) {
    const first2 = cleaned.slice(0, 2);
    const last2 = cleaned.slice(-2);
    return `${first2}XXXXXX${last2}`;
  }
  if (cleaned.length >= 6) {
    const last3 = cleaned.slice(-3);
    return `XXXXXXX${last3}`;
  }
  return value;
}

/**
 * Mask 10-digit Indian phone/mobile number
 * Input: "+91 9876543210" or "9876543210"
 * Output: "+91 ******3210" or "******3210"
 */
export function maskPhoneNumber(value: string): string {
  if (!value) return "";
  const str = String(value).trim();
  const digitsOnly = str.replace(/[^\d]/g, "");

  if (digitsOnly.length === 10) {
    const last4 = digitsOnly.slice(-4);
    const hasCountryCode = str.startsWith("+91");
    return hasCountryCode ? `+91 ******${last4}` : `******${last4}`;
  }

  if (digitsOnly.length === 12 && digitsOnly.startsWith("91")) {
    const last4 = digitsOnly.slice(-4);
    return `+91 ******${last4}`;
  }

  if (digitsOnly.length > 6) {
    const last3 = digitsOnly.slice(-3);
    return `******${last3}`;
  }

  return value;
}

/**
 * General presentation masking helper.
 * Inspects key names and/or value patterns to mask sensitive identifiers,
 * preserving all non-sensitive text (names, dates, amounts, addresses) intact.
 */
export function maskSensitiveValue(key: string, value: any): string {
  if (value === null || value === undefined) return "";
  const strVal = typeof value === "object" ? JSON.stringify(value) : String(value);
  if (!strVal.trim()) return "";

  const normKey = (key || "").toLowerCase();

  // 1. Key-based detection
  if (normKey.includes("aadhaar") || normKey.includes("aadhar") || normKey.includes("uid")) {
    return maskAadhaar(strVal);
  }

  if (normKey.includes("pan") || normKey.includes("pan_card") || normKey.includes("pan_number")) {
    return maskPan(strVal);
  }

  if (normKey.includes("phone") || normKey.includes("mobile") || normKey.includes("contact")) {
    return maskPhoneNumber(strVal);
  }

  // 2. Value pattern detection (for generic keys like "id_number", "document_number", "val")
  const cleanedDigits = strVal.replace(/[\s-]/g, "");
  if (/^\d{12}$/.test(cleanedDigits)) {
    return maskAadhaar(strVal);
  }

  if (/^[A-Za-z]{5}\d{4}[A-Za-z]$/.test(strVal.trim())) {
    return maskPan(strVal);
  }

  if (/^(\+91[\s-]?)?[6-9]\d{9}$/.test(strVal.trim().replace(/[\s-]/g, ""))) {
    return maskPhoneNumber(strVal);
  }

  // Non-sensitive values remain completely readable
  return strVal;
}
