"""
SEVA AI - Permanent Account Number (PAN) Document Parser

Extracts structured fields (PAN number, holder name, father's name, DOB)
from raw OCR text lines with per-field confidence scoring.
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from app.documents.ocr import OCRResult
from app.documents.parsers.base import BaseDocumentParser, DocumentParserResult, ExtractedField


# Standard Indian PAN format: 5 letters, 4 digits, 1 letter (e.g. ABCDE1234F)
PAN_REGEX = re.compile(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b")


class PANParser(BaseDocumentParser):
    def __init__(self):
        super().__init__("identity_proof")

    def parse(self, ocr_result: OCRResult) -> DocumentParserResult:
        fields: Dict[str, Dict[str, Any]] = {}
        warnings: List[str] = []

        lines = ocr_result.lines
        full_text = ocr_result.text

        # 1. Extract PAN Number
        pan_val = None
        for line in lines:
            txt = line.text.strip().upper()
            match = PAN_REGEX.search(txt)
            if match:
                pan_val = match.group(1)
                # Boost confidence if 4th char is valid status code (P, C, H, F, A, T, B, L, J, G)
                status_char = pan_val[3]
                boost = 1.0 if status_char in "PCHFATBLJG" else 0.85
                conf = min(0.99, line.confidence * boost)
                fields["id_number"] = ExtractedField(value=pan_val, confidence=conf, source_line=line.text).to_dict()
                fields["pan_number"] = fields["id_number"]
                break

        # 2. Extract Date of Birth
        for line in lines:
            txt = line.text.strip()
            # Often labeled as "Date of Birth" or "DOB"
            if re.search(r"(Date of Birth|DOB|Birth)", txt, re.IGNORECASE):
                d = self.extract_date(txt)
                if d:
                    fields["dob"] = ExtractedField(value=d, confidence=line.confidence, source_line=txt).to_dict()
                    fields["date_of_birth"] = fields["dob"]
                    break

        if "dob" not in fields:
            # Fallback scan across all lines for DD/MM/YYYY
            for line in lines:
                d = self.extract_date(line.text)
                if d:
                    fields["dob"] = ExtractedField(value=d, confidence=line.confidence * 0.8, source_line=line.text).to_dict()
                    fields["date_of_birth"] = fields["dob"]
                    break

        # 3. Extract Name & Father's Name
        # In Indian PAN cards, the standard layout is:
        # Header: INCOME TAX DEPARTMENT / GOVT. OF INDIA
        # Line: Name
        # Line: Father's Name
        # Line: Date of Birth
        # Line: Permanent Account Number (or below photo)
        names_found: List[Tuple[str, float, str]] = []
        for line in lines:
            txt = line.text.strip()
            # Skip headers, titles, numbers, dates
            if re.search(r"(INCOME|TAX|DEPARTMENT|GOVT|INDIA|PERMANENT|ACCOUNT|NUMBER|SIGNATURE|CARD)", txt, re.IGNORECASE):
                continue
            if PAN_REGEX.search(txt.upper()):
                continue
            if self.extract_date(txt):
                continue

            cleaned = self.clean_name(txt)
            # A valid name should have at least 1 word and be alphabetic
            if len(cleaned) >= 3 and not re.search(r"\d", cleaned):
                names_found.append((cleaned, line.confidence, txt))

        if len(names_found) >= 1:
            name_val, conf_val, src = names_found[0]
            fields["name"] = ExtractedField(value=name_val, confidence=conf_val, source_line=src).to_dict()

        if len(names_found) >= 2:
            father_val, f_conf, src = names_found[1]
            fields["father_name"] = ExtractedField(value=father_val, confidence=f_conf, source_line=src).to_dict()

        # Status Assessment
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
                warnings.append("Could not identify valid 10-character PAN number.")
            if not has_name:
                warnings.append("Could not confidently identify PAN cardholder name.")
            if avg_conf < 0.65:
                warnings.append("OCR confidence is below standard threshold.")

        return DocumentParserResult(
            fields=fields,
            status=status,
            document_type="identity_proof",
            confidence_score=round(avg_conf, 4),
            warnings=warnings,
            field_confidence=field_confidences,
            ocr_engine=ocr_result.engine,
        )
