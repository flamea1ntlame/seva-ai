import re
from typing import Dict, Any, Optional
from app.documents.verification.validators.base import BaseDocumentValidator, ValidationOutcome

# Recognized Indian State / UT prefix codes for Voter ID (EPIC)
_VALID_STATE_PREFIXES = {
    "AP", "AR", "AS", "BR", "CG", "GA", "GJ", "HR", "HP", "JH",
    "KA", "KL", "MP", "MH", "MN", "ML", "MZ", "NL", "OD", "PB",
    "RJ", "SK", "TN", "TS", "TR", "UP", "UK", "WB", "DL", "JK",
    "LA", "PY", "CH", "DN", "DD", "AN", "LD"
}


class VoterIdValidator(BaseDocumentValidator):
    @property
    def document_type(self) -> str:
        return "voter_id"

    @property
    def issuer_name(self) -> str:
        return "Election Commission of India (ECI)"

    def validate(self, extracted_fields: Dict[str, Any], raw_text: Optional[str] = None) -> ValidationOutcome:
        checks_passed = []
        checks_failed = []
        risk_flags = []
        redacted = {}
        failure_reason = None

        raw_id = (
            extracted_fields.get("voter_id")
            or extracted_fields.get("epic_number")
            or extracted_fields.get("id_number")
        )

        clean_id = None
        if raw_id:
            candidate = re.sub(r"[^A-Za-z0-9]", "", str(raw_id)).upper()
            if 10 <= len(candidate) <= 16:
                clean_id = candidate

        if not clean_id and raw_text:
            # Match standard 3-letter + 7-digit pattern: e.g. WBF1234567 or XYZ1234567
            match = re.search(r"\b[A-Z]{3}[0-9]{7}\b", raw_text.upper())
            if match:
                clean_id = match.group(0)

        if not clean_id:
            checks_failed.append("voter_id_identifier_found")
            risk_flags.append("IDENTIFIER_MISSING")
            return ValidationOutcome(
                is_valid=False,
                checks_passed=checks_passed,
                checks_failed=checks_failed,
                risk_flags=risk_flags,
                failure_reason="Voter ID (EPIC) number could not be extracted."
            )

        checks_passed.append("voter_id_identifier_found")

        # 1. Standard EPIC format: 3 letters + 7 numbers (or legacy 2-3 letters + 7-8 numbers)
        if re.match(r"^[A-Z]{2,3}[0-9]{7,8}$", clean_id):
            checks_passed.append("voter_id_format_valid")
        else:
            checks_failed.append("voter_id_format_valid")
            risk_flags.append("INVALID_VOTER_ID_FORMAT")

        # 2. State Prefix Validation
        prefix_2 = clean_id[:2]
        if prefix_2 in _VALID_STATE_PREFIXES or clean_id[:3].isalpha():
            checks_passed.append("voter_id_prefix_valid")
        else:
            checks_failed.append("voter_id_prefix_valid")
            risk_flags.append("UNRECOGNIZED_EPIC_PREFIX")

        # Safe PII Redaction: Mask middle serial number (e.g. WBF****567)
        if len(clean_id) >= 7:
            masked_epic = f"{clean_id[:3]}****{clean_id[-3:]}"
        else:
            masked_epic = f"****{clean_id[-4:]}"

        redacted["voter_id"] = masked_epic
        redacted["id_number"] = masked_epic

        if "name" in extracted_fields:
            redacted["name"] = str(extracted_fields["name"])

        is_valid = len(checks_failed) == 0
        if not is_valid:
            failure_reason = f"Voter ID validation failed checks: {', '.join(checks_failed)}"

        return ValidationOutcome(
            is_valid=is_valid,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            risk_flags=risk_flags,
            redacted_fields=redacted,
            clean_identifier=masked_epic,
            failure_reason=failure_reason
        )
