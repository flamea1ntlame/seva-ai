"""
SEVA AI - Privacy & PII Protection Module

Redacts and masks sensitive identifiers (Aadhaar, PAN, phone numbers) before audit
persistence and before dispatching outbound requests to LLMs (Gemini API).
Preserves necessary context (e.g. last 4 digits) for audit/debugging.
"""

import re
from typing import Dict, Any


# Aadhaar: 12-digit number (e.g. 1234 5678 9012 or 123456789012 or 1234-5678-9012)
AADHAAR_REGEX = re.compile(r"\b(\d{4})[\s\-_]?(\d{4})[\s\-_]?(\d{4})\b")

# PAN: 5 letters, 4 digits, 1 letter (e.g. ABCDE1234F)
PAN_REGEX = re.compile(r"\b([A-Za-z]{5})[\s\-_]?(\d{4})[\s\-_]?([A-Za-z])\b")

# Indian Phone Numbers: 10 digits starting with 6-9, with optional +91, 91, or 0 prefix and spaces/dashes
PHONE_REGEX = re.compile(r"(?:\+91[\s\-_]?|\b91[\s\-_]?)?(?:\b0)?([6-9]\d{1,5})[\s\-_]?(\d{1,5})[\s\-_]?(\d{4})\b")


def mask_pii(text: str) -> str:
    """
    Masks sensitive personally identifiable information (PII) in text:
    - Aadhaar: XXXX-XXXX-9012
    - PAN: XXXXX1234F
    - Phone: XXXXXX3210
    """
    if not text:
        return ""

    masked = str(text)

    # Mask Aadhaar
    def _mask_aadhaar(match):
        last4 = match.group(3)
        return f"XXXX-XXXX-{last4}"

    masked = AADHAAR_REGEX.sub(_mask_aadhaar, masked)

    # Mask PAN
    def _mask_pan(match):
        digits = match.group(2)
        last_char = match.group(3).upper()
        return f"XXXXX{digits}{last_char}"

    masked = PAN_REGEX.sub(_mask_pan, masked)

    # Mask Phone
    def _mask_phone(match):
        digits = match.group(0)
        last4 = re.findall(r"\d", digits)[-4:]
        return f"XXXXXX" + "".join(last4)

    masked = PHONE_REGEX.sub(_mask_phone, masked)

    return masked


def sanitize_audit_details(details: Any) -> Any:
    """
    Recursively sanitizes data structures (dicts, lists, strings) to redact sensitive PII.
    """
    if isinstance(details, str):
        return mask_pii(details)
    elif isinstance(details, dict):
        return {k: sanitize_audit_details(v) for k, v in details.items()}
    elif isinstance(details, list):
        return [sanitize_audit_details(item) for item in details]
    elif isinstance(details, tuple):
        return tuple(sanitize_audit_details(item) for item in details)
    else:
        return details
