"""
SEVA AI - Privacy & PII Protection Module

Redacts and masks sensitive identifiers (Aadhaar, PAN, phone numbers) before audit
persistence and logging, in compliance with DPDP and UIDAI guidelines.
Preserves necessary context (e.g. last 4 digits) for audit/debugging.
"""

import re
from typing import Dict, Any


# Aadhaar: 12-digit number (e.g. 1234 5678 9012 or 123456789012 or 1234-5678-9012)
AADHAAR_REGEX = re.compile(r"\b(\d{4})[ -]?(\d{4})[ -]?(\d{4})\b")

# PAN: 5 uppercase letters, 4 digits, 1 uppercase letter (e.g. ABCDE1234F)
PAN_REGEX = re.compile(r"\b([A-Z]{5})(\d{4})([A-Z])\b", re.IGNORECASE)

# Indian Phone Numbers: 10 digits starting with 6-9, optionally with +91 or 0 prefix
PHONE_REGEX = re.compile(r"\b(?:\+91[\-\s]?|0)?([6-9]\d{5})(\d{4})\b")


def mask_pii(text: str) -> str:
    """
    Masks sensitive personally identifiable information (PII) in text:
    - Aadhaar: XXXX-XXXX-9012
    - PAN: XXXXX1234F
    - Phone: XXXXXX3210
    """
    if not text:
        return ""

    masked = text

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
        last4 = match.group(2)
        return f"XXXXXX{last4}"

    masked = PHONE_REGEX.sub(_mask_phone, masked)

    return masked


def sanitize_audit_details(details: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns a copy of audit details with all string values masked for PII.
    """
    sanitized = {}
    for k, v in details.items():
        if isinstance(v, str):
            sanitized[k] = mask_pii(v)
        elif isinstance(v, dict):
            sanitized[k] = sanitize_audit_details(v)
        elif isinstance(v, list):
            sanitized[k] = [mask_pii(item) if isinstance(item, str) else item for item in v]
        else:
            sanitized[k] = v
    return sanitized
