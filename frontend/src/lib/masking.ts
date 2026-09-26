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
 * Mask any sensitive PII embedded inside longer strings (free text, notes, remarks).
 */
export function maskEmbeddedPII(text: string): string {
  if (!text || typeof text !== "string") return text;

  // 1. Aadhaar with space or hyphen: e.g. "1234 5678 9012" or "1234-5678-9012"
  let masked = text.replace(/\b\d{4}[\s-]\d{4}[\s-](\d{4})\b/g, "XXXX XXXX $1");

  // 2. 12-digit continuous Aadhaar: e.g. "123456789012"
  masked = masked.replace(/\b\d{8}(\d{4})\b/g, "XXXX XXXX $1");

  // 3. Indian PAN: e.g. "ABCDE1234F" -> "ABXXXXXX4F"
  masked = masked.replace(/\b([A-Za-z]{2})[A-Za-z]{3}\d{3}(\d[A-Za-z])\b/g, (match, p1, p2) => {
    return `${p1.toUpperCase()}XXXXXX${p2.toUpperCase()}`;
  });

  // 4. Indian Phone (+91 or 10-digit starting with 6-9)
  masked = masked.replace(/\b(\+91[\s-]?)?[6-9]\d{5}(\d{4})\b/g, (match, prefix, last4) => {
    const p = prefix ? "+91 " : "";
    return `${p}******${last4}`;
  });

  return masked;
}

/**
 * Recursively masks sensitive fields inside an object or array.
 */
export function maskSensitiveObject(obj: any): any {
  if (obj === null || obj === undefined) return obj;
  if (typeof obj !== "object") {
    return maskEmbeddedPII(String(obj));
  }

  if (Array.isArray(obj)) {
    return obj.map((item) => maskSensitiveObject(item));
  }

  const result: Record<string, any> = {};
  for (const [k, v] of Object.entries(obj)) {
    const normK = k.toLowerCase();
    if (typeof v === "object" && v !== null) {
      result[k] = maskSensitiveObject(v);
    } else if (normK.includes("aadhaar") || normK.includes("aadhar") || normK.includes("uid")) {
      result[k] = maskAadhaar(String(v));
    } else if (normK.includes("pan")) {
      result[k] = maskPan(String(v));
    } else if (normK.includes("phone") || normK.includes("mobile") || normK.includes("contact")) {
      result[k] = maskPhoneNumber(String(v));
    } else {
      result[k] = maskEmbeddedPII(String(v));
    }
  }
  return result;
}

/**
 * General presentation masking helper.
 * Inspects key names, object structures, and value patterns to mask sensitive identifiers,
 * preserving all non-sensitive text (names, dates, amounts, addresses) intact.
 */
export function maskSensitiveValue(key: string, value: any): string {
  if (value === null || value === undefined) return "";
  
  if (typeof value === "object") {
    const maskedObj = maskSensitiveObject(value);
    return JSON.stringify(maskedObj);
  }

  const strVal = String(value);
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

  // 2. Exact Value pattern detection (for generic keys like "id_number", "document_number", "val")
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

  // 3. Embedded PII in longer strings (e.g. "Citizen Aadhaar is 1234 5678 9012")
  return maskEmbeddedPII(strVal);
}

