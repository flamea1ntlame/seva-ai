import re
from typing import Dict, Any, Optional
from app.documents.verification.validators.base import BaseDocumentValidator, ValidationOutcome
from app.documents.verification.algorithms.verhoeff import validate_verhoeff


class AadhaarValidator(BaseDocumentValidator):
    @property
    def document_type(self) -> str:
        return "aadhaar"

    @property
    def issuer_name(self) -> str:
        return "Unique Identification Authority of India (UIDAI)"

    def validate(self, extracted_fields: Dict[str, Any], raw_text: Optional[str] = None) -> ValidationOutcome:
        checks_passed = []
        checks_failed = []
        risk_flags = []
        redacted = {}
        failure_reason = None

        # Look for Aadhaar number in extracted_fields or raw_text
        raw_id = (
            extracted_fields.get("aadhaar_number")
            or extracted_fields.get("id_number")
            or extracted_fields.get("aadhaar")
        )

        clean_id = None
        if raw_id:
            # Strip spaces, hyphens, and standard prefixes
            digits = re.sub(r"[^\d]", "", str(raw_id))
            if len(digits) == 12:
                clean_id = digits

        # Fallback to regex search in raw_text if not explicitly extracted
        if not clean_id and raw_text:
            match = re.search(r"\b[2-9]{1}[0-9]{3}[ \-]?[0-9]{4}[ \-]?[0-9]{4}\b", raw_text)
            if match:
                clean_id = re.sub(r"[^\d]", "", match.group(0))

        if not clean_id:
            checks_failed.append("aadhaar_identifier_found")
            risk_flags.append("IDENTIFIER_MISSING")
            return ValidationOutcome(
                is_valid=False,
                checks_passed=checks_passed,
                checks_failed=checks_failed,
                risk_flags=risk_flags,
                failure_reason="Aadhaar number could not be extracted or is not 12 digits."
            )

        checks_passed.append("aadhaar_identifier_found")

        # 1. 12-digit length & format check
        if len(clean_id) == 12 and clean_id[0] not in ("0", "1"):
            checks_passed.append("aadhaar_format_valid")
        else:
            checks_failed.append("aadhaar_format_valid")
            risk_flags.append("INVALID_AADHAAR_FORMAT")

        # 2. Non-trivial sequence heuristic (cannot be all same digits)
        if len(set(clean_id)) > 1 and clean_id != "123456789012":
            checks_passed.append("aadhaar_non_trivial_pattern")
        else:
            checks_failed.append("aadhaar_non_trivial_pattern")
            risk_flags.append("SUSPICIOUS_NUMBER_SEQUENCE")

        # 3. Verhoeff Dihedral D5 Checksum
        if validate_verhoeff(clean_id):
            checks_passed.append("aadhaar_verhoeff_checksum")
        else:
            checks_failed.append("aadhaar_verhoeff_checksum")
            risk_flags.append("VERHOEFF_CHECKSUM_FAILED")

        # Safe PII Redaction: Always mask first 8 digits (XXXXXXXX1234)
        masked_aadhaar = f"XXXXXXXX{clean_id[-4:]}"
        redacted["aadhaar_number"] = masked_aadhaar
        redacted["id_number"] = masked_aadhaar

        if "name" in extracted_fields:
            redacted["name"] = str(extracted_fields["name"])
        if "dob" in extracted_fields:
            redacted["dob"] = str(extracted_fields["dob"])

        is_valid = len(checks_failed) == 0
        if not is_valid:
            failure_reason = f"Aadhaar validation failed checks: {', '.join(checks_failed)}"

        return ValidationOutcome(
            is_valid=is_valid,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            risk_flags=risk_flags,
            redacted_fields=redacted,
            clean_identifier=masked_aadhaar,
            failure_reason=failure_reason,
            details={"verhoeff_valid": "aadhaar_verhoeff_checksum" in checks_passed}
        )
