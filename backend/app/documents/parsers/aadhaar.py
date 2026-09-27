"""
SEVA AI - Aadhaar Card Document Parser

Extracts structured fields (Aadhaar number, name, DOB, gender, address)
from raw OCR text lines with per-field confidence scoring.
"""

import re
from typing import Dict, Any, List, Optional
from app.documents.ocr import OCRResult, OCRLine
from app.documents.parsers.base import BaseDocumentParser, DocumentParserResult, ExtractedField


# Verhoeff algorithm multiplication and permutation tables for Aadhaar checksum verification
VERHOEFF_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]

VERHOEFF_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]


def validate_verhoeff(num_str: str) -> bool:
    """Validates 12-digit Aadhaar number against Verhoeff checksum."""
    digits = re.sub(r"\D", "", num_str)
    if len(digits) != 12:
        return False
    c = 0
    for idx, d in enumerate(reversed(digits)):
        c = VERHOEFF_D[c][VERHOEFF_P[idx % 8][int(d)]]
    return c == 0


class AadhaarParser(BaseDocumentParser):
    def __init__(self):
        super().__init__("identity_proof")

    def parse(self, ocr_result: OCRResult) -> DocumentParserResult:
        fields: Dict[str, Dict[str, Any]] = {}
        warnings: List[str] = []

        lines = ocr_result.lines
        full_text = ocr_result.text

        # 1. Extract Aadhaar Number (12 digits, often in 4-digit groups)
        aadhaar_candidate = None
        aadhaar_conf = 0.0

        for line in lines:
            txt = line.text.strip()
            # Match prefixed format like AADHAAR-1234-5678-9012
            prefixed = re.search(r"\b(AADHAAR[-\s]\d{4}[-\s]\d{4}[-\s]\d{4})\b", txt, re.IGNORECASE)
            if prefixed:
                val = prefixed.group(1).upper()
                aadhaar_candidate = val
                aadhaar_conf = line.confidence
                fields["id_number"] = ExtractedField(value=val, confidence=line.confidence, source_line=txt).to_dict()
                break

            # Match 4-4-4 digit pattern or 12 continuous digits
            match = re.search(r"\b(\d{4})[\s\-](\d{4})[\s\-](\d{4})\b", txt)
            if not match:
                match = re.search(r"\b(\d{12})\b", txt)

            if match:
                raw_digits = "".join(match.groups()) if len(match.groups()) > 1 else match.group(1)
                is_valid = validate_verhoeff(raw_digits)
                score = line.confidence if is_valid else max(0.5, line.confidence * 0.8)
                formatted = f"{raw_digits[:4]} {raw_digits[4:8]} {raw_digits[8:]}"

                aadhaar_candidate = formatted
                aadhaar_conf = score
                fields["id_number"] = ExtractedField(value=formatted, confidence=score, source_line=txt).to_dict()
                break

        # Also support masked Aadhaar (e.g. XXXX-XXXX-1234 or **** **** 1234)
        if not aadhaar_candidate:
            masked_match = re.search(r"(?:[xX*]{4}[\s\-]?){2}(\d{4})", full_text)
            if masked_match:
                masked_val = f"XXXX-XXXX-{masked_match.group(1)}"
                fields["id_number"] = ExtractedField(value=masked_val, confidence=0.85).to_dict()
                aadhaar_candidate = masked_val

        # 2. Extract Date of Birth
        dob_val = None
        dob_conf = 0.0
        for line in lines:
            txt = line.text.strip()
            if re.search(r"(DOB|D\.O\.B|Birth|जन्म)", txt, re.IGNORECASE):
                d = self.extract_date(txt)
                if d:
                    dob_val = d
                    dob_conf = line.confidence
                    fields["dob"] = ExtractedField(value=d, confidence=dob_conf, source_line=txt).to_dict()
                    fields["date_of_birth"] = fields["dob"]
                    break

        if not dob_val:
            # Fallback: scan for any standard date in the document
            for line in lines:
                d = self.extract_date(line.text)
                if d:
                    fields["dob"] = ExtractedField(value=d, confidence=line.confidence * 0.75, source_line=line.text).to_dict()
                    fields["date_of_birth"] = fields["dob"]
                    break

        # 3. Extract Gender
        for line in lines:
            txt = line.text.upper()
            if "FEMALE" in txt or "महिला" in txt:
                fields["gender"] = ExtractedField(value="FEMALE", confidence=line.confidence).to_dict()
                break
            elif "TRANSGENDER" in txt:
                fields["gender"] = ExtractedField(value="TRANSGENDER", confidence=line.confidence).to_dict()
                break
            elif "MALE" in txt or "पुरुष" in txt:
                fields["gender"] = ExtractedField(value="MALE", confidence=line.confidence).to_dict()
                break

        # 4. Extract Name
        # In Aadhaar cards, the English name typically appears either after "Government of India" / "To"
        # or immediately preceding the "DOB" line.
        name_val = None
        for i, line in enumerate(lines):
            txt = line.text.strip()
            # If line is explicitly prefixed with "Name:"
            if re.search(r"^Name\s*[:\-]\s*", txt, re.IGNORECASE):
                cleaned = self.clean_name(txt)
                if len(cleaned.split()) >= 1 and len(cleaned) >= 3:
                    name_val = cleaned
                    fields["name"] = ExtractedField(value=name_val, confidence=line.confidence, source_line=txt).to_dict()
                    break

            # Check for name following "To"
            if re.search(r"^To$", txt, re.IGNORECASE):
                for next_line in lines[i + 1: i + 4]:
                    cand = self.clean_name(next_line.text)
                    if len(cand.split()) >= 2 and not re.search(r"(Government|India|Unique|Enrolment)", cand, re.IGNORECASE):
                        name_val = cand
                        fields["name"] = ExtractedField(value=name_val, confidence=0.95, source_line=next_line.text).to_dict()
                        break
                if name_val:
                    break

            # If line preceding DOB (within 1 or 2 lines) contains candidate name
            for offset in (1, 2):
                if i + offset < len(lines) and re.search(r"(DOB|Birth|जन्म|ಂಕ)", lines[i + offset].text, re.IGNORECASE):
                    candidate = self.clean_name(txt)
                    if candidate and not re.search(r"(Government|India|Authority|UIDAI|Enrolment|Details|issued|Address|To)", candidate, re.IGNORECASE):
                        if len(candidate) >= 3 and len(candidate.split()) >= 1:
                            name_val = candidate
                            fields["name"] = ExtractedField(value=name_val, confidence=line.confidence * 0.95, source_line=txt).to_dict()
                            break
            if name_val:
                break

        # 5. Extract Address (if available, e.g. "Address:" line or postal PIN code)
        pin_match = re.search(r"\b([1-9]\d{5})\b", full_text)
        if pin_match:
            fields["pincode"] = ExtractedField(value=pin_match.group(1), confidence=0.95).to_dict()

        for idx, line in enumerate(lines):
            line_str = line.text.strip()
            if re.search(r"^Address\s*[:\-]?\s*$", line_str, re.IGNORECASE) or re.search(r"^Address\s*[:\-]\s*", line_str, re.IGNORECASE):
                addr_text = re.sub(r"^Address\s*[:\-]\s*", "", line_str, flags=re.IGNORECASE).strip()
                addr_parts = [addr_text] if addr_text else []
                # Grab following lines until empty or footer/Aadhaar number
                for next_line in lines[idx + 1: idx + 8]:
                    nxt = next_line.text.strip()
                    if not nxt or re.search(r"\b\d{4}\s\d{4}\s\d{4}\b", nxt) or re.search(r"(VID|help@uidai|www\.uidai|1947)", nxt, re.IGNORECASE):
                        break
                    addr_parts.append(nxt)
                combined_addr = " ".join(addr_parts).strip()
                if len(combined_addr) > 5:
                    fields["address"] = ExtractedField(value=combined_addr, confidence=0.95).to_dict()
                    # Also extract S/O or father name if present in address block
                    so_match = re.search(r"(?:S/O|D/O|W/O|C/O)\s*[:\-]?\s*([A-Za-z\s]+?)(?:,|$)", combined_addr, re.IGNORECASE)
                    if so_match:
                        care_of = so_match.group(1).strip()
                        if len(care_of) >= 3:
                            fields["father_name"] = ExtractedField(value=care_of, confidence=0.92).to_dict()
                            fields["care_of"] = fields["father_name"]
                    # Extract state
                    state_match = re.search(r"\b(Karnataka|Maharashtra|Tamil Nadu|Delhi|Kerala|Gujarat|Telangana|Andhra Pradesh)\b", combined_addr, re.IGNORECASE)
                    if state_match:
                        fields["state"] = ExtractedField(value=state_match.group(1), confidence=0.95).to_dict()
                    break

        # Status Assessment
        # Requirements for confident extraction: must have id_number and at least name or dob
        has_id = "id_number" in fields
        has_name = "name" in fields
        has_dob = "dob" in fields

        field_confidences = {k: v["confidence"] for k, v in fields.items()}
        avg_conf = (sum(field_confidences.values()) / len(field_confidences)) if field_confidences else 0.0

        if has_id and (has_name or has_dob) and avg_conf >= 0.65:
            status = "OCR_EXTRACTED"
        else:
            status = "NEEDS_REVIEW"
            if not has_id:
                warnings.append("Could not confidently identify 12-digit Aadhaar number.")
            if not has_name:
                warnings.append("Could not confidently identify citizen name.")
            if avg_conf < 0.65:
                warnings.append("Overall OCR confidence is below standard threshold.")

        return DocumentParserResult(
            fields=fields,
            status=status,
            document_type="identity_proof",
            confidence_score=round(avg_conf, 4),
            warnings=warnings,
            field_confidence=field_confidences,
            ocr_engine=ocr_result.engine,
        )
