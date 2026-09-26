import re
from datetime import datetime
from typing import Dict, Any, Optional
from app.documents.verification.validators.base import BaseDocumentValidator, ValidationOutcome

_VALID_DL_STATES = {
    "AN", "AP", "AR", "AS", "BR", "CH", "CG", "DD", "DL", "DN",
    "GA", "GJ", "HP", "HR", "JH", "JK", "KA", "KL", "LA", "LD",
    "MH", "ML", "MN", "MP", "MZ", "NL", "OD", "PB", "PY", "RJ",
    "SK", "TN", "TR", "TS", "UK", "UP", "WB"
}


class DrivingLicenceValidator(BaseDocumentValidator):
    @property
    def document_type(self) -> str:
        return "driving_licence"

    @property
    def issuer_name(self) -> str:
        return "Ministry of Road Transport and Highways (MoRTH) / State RTO"

    def validate(self, extracted_fields: Dict[str, Any], raw_text: Optional[str] = None) -> ValidationOutcome:
        checks_passed = []
        checks_failed = []
        risk_flags = []
        redacted = {}
        failure_reason = None

        raw_id = (
            extracted_fields.get("dl_number")
            or extracted_fields.get("driving_licence_number")
            or extracted_fields.get("id_number")
        )

        clean_id = None
        if raw_id:
            # Strip spaces, hyphens
            candidate = re.sub(r"[^A-Za-z0-9]", "", str(raw_id)).upper()
            if 14 <= len(candidate) <= 16:
                clean_id = candidate

        if not clean_id and raw_text:
            # Standard DL pattern: 2 letters (state) + 2 digits (RTO) + 4 digits (year) + 7 digits (serial)
            match = re.search(r"\b[A-Z]{2}[ \-]?[0-9]{2}[ \-]?[0-9]{4}[ \-]?[0-9]{7}\b", raw_text.upper())
            if match:
                clean_id = re.sub(r"[^A-Za-z0-9]", "", match.group(0))

        if not clean_id:
            checks_failed.append("dl_identifier_found")
            risk_flags.append("IDENTIFIER_MISSING")
            return ValidationOutcome(
                is_valid=False,
                checks_passed=checks_passed,
                checks_failed=checks_failed,
                risk_flags=risk_flags,
                failure_reason="Driving Licence number could not be extracted or does not match standard 15-16 character length."
            )

        checks_passed.append("dl_identifier_found")

        # 1. State Code Check (first 2 chars)
        state_code = clean_id[:2]
        if state_code in _VALID_DL_STATES:
            checks_passed.append("dl_state_code_valid")
        else:
            checks_failed.append("dl_state_code_valid")
            risk_flags.append("INVALID_DL_STATE_CODE")

        # 2. Format validation: 2 letters + 13-14 digits
        if re.match(r"^[A-Z]{2}[0-9]{12,14}$", clean_id):
            checks_passed.append("dl_format_regex")
        else:
            checks_failed.append("dl_format_regex")
            risk_flags.append("INVALID_DL_FORMAT")

        # 3. Issue year check (positions 4 to 8 in standard Sarathi DL: SS-RRO-YYYY-NNNNNNN)
        current_year = datetime.now().year
        if len(clean_id) >= 8 and clean_id[4:8].isdigit():
            issue_year = int(clean_id[4:8])
            if 1950 <= issue_year <= current_year:
                checks_passed.append("dl_issue_year_valid")
            else:
                checks_failed.append("dl_issue_year_valid")
                risk_flags.append("SUSPICIOUS_DL_ISSUE_YEAR")
        else:
            checks_passed.append("dl_issue_year_evaluated")

        # Safe PII Redaction: e.g. KA01-2018-*******
        masked_dl = f"{clean_id[:8]}*******" if len(clean_id) >= 8 else f"{clean_id[:4]}*******"
        redacted["dl_number"] = masked_dl
        redacted["id_number"] = masked_dl

        if "name" in extracted_fields:
            redacted["name"] = str(extracted_fields["name"])

        is_valid = len(checks_failed) == 0
        if not is_valid:
            failure_reason = f"Driving Licence validation failed checks: {', '.join(checks_failed)}"

        return ValidationOutcome(
            is_valid=is_valid,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            risk_flags=risk_flags,
            redacted_fields=redacted,
            clean_identifier=masked_dl,
            failure_reason=failure_reason
        )
