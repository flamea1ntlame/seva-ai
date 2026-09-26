import re
from typing import Dict, Any, Optional
from app.documents.verification.validators.base import BaseDocumentValidator, ValidationOutcome


class PanValidator(BaseDocumentValidator):
    @property
    def document_type(self) -> str:
        return "pan"

    @property
    def issuer_name(self) -> str:
        return "Income Tax Department, Government of India"

    def validate(self, extracted_fields: Dict[str, Any], raw_text: Optional[str] = None) -> ValidationOutcome:
        checks_passed = []
        checks_failed = []
        risk_flags = []
        redacted = {}
        failure_reason = None

        raw_id = (
            extracted_fields.get("pan_number")
            or extracted_fields.get("id_number")
            or extracted_fields.get("pan")
        )

        clean_id = None
        if raw_id:
            candidate = str(raw_id).strip().upper()
            if re.match(r"^[A-Z0-9]{10}$", candidate):
                clean_id = candidate

        if not clean_id and raw_text:
            match = re.search(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", raw_text.upper())
            if match:
                clean_id = match.group(0)

        if not clean_id:
            checks_failed.append("pan_identifier_found")
            risk_flags.append("IDENTIFIER_MISSING")
            return ValidationOutcome(
                is_valid=False,
                checks_passed=checks_passed,
                checks_failed=checks_failed,
                risk_flags=risk_flags,
                failure_reason="PAN number could not be extracted or is not 10 alphanumeric characters."
            )

        checks_passed.append("pan_identifier_found")

        # 1. Strict PAN Structure: 5 letters, 4 numbers, 1 letter
        if re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]$", clean_id):
            checks_passed.append("pan_format_regex")
        else:
            checks_failed.append("pan_format_regex")
            risk_flags.append("INVALID_PAN_FORMAT")

        # 2. 4th Character Entity Validation
        # P = Individual, C = Company, H = HUF, F = Firm, A = AOP, T = Trust, B = BOI, L = Local Authority, J = AJP, G = Government
        valid_entities = ("P", "C", "H", "F", "A", "T", "B", "L", "J", "G")
        entity_code = clean_id[3] if len(clean_id) >= 4 else ""
        if entity_code in valid_entities:
            checks_passed.append("pan_entity_type_valid")
        else:
            checks_failed.append("pan_entity_type_valid")
            risk_flags.append("INVALID_PAN_ENTITY_CODE")

        # 3. 5th Character surname consistency check (if surname extracted)
        name = str(extracted_fields.get("name") or extracted_fields.get("full_name") or "").strip()
        if name and len(clean_id) >= 5:
            tokens = name.split()
            if tokens:
                surname = tokens[-1].upper()
                if surname and surname[0] == clean_id[4]:
                    checks_passed.append("pan_surname_initial_match")
                else:
                    # Supporting check: Not a hard rejection since single names exist, but logged as check
                    checks_passed.append("pan_surname_evaluated")

        # Safe PII Redaction: Mask first 5 characters (XXXXX1234A)
        masked_pan = f"XXXXX{clean_id[5:]}"
        redacted["pan_number"] = masked_pan
        redacted["id_number"] = masked_pan

        if "name" in extracted_fields:
            redacted["name"] = str(extracted_fields["name"])
        if "dob" in extracted_fields:
            redacted["dob"] = str(extracted_fields["dob"])

        is_valid = len(checks_failed) == 0
        if not is_valid:
            failure_reason = f"PAN validation failed checks: {', '.join(checks_failed)}"

        return ValidationOutcome(
            is_valid=is_valid,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            risk_flags=risk_flags,
            redacted_fields=redacted,
            clean_identifier=masked_pan,
            failure_reason=failure_reason,
            details={"entity_type": entity_code}
        )
