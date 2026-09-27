"""
SEVA AI - Driving Licence (DL) Document Parser

Extracts structured fields (Licence number, holder name, DOB, vehicle classes, validity)
from raw OCR text lines with per-field confidence scoring.
"""

import re
from typing import Dict, Any, List, Optional
from app.documents.ocr import OCRResult
from app.documents.parsers.base import BaseDocumentParser, DocumentParserResult, ExtractedField


# Indian Driving Licence pattern:
# State code (2 letters) + RTO (2 digits) + optional space/dash + Year (4 digits) + 7 digits
# or legacy formats (e.g. KA-01-2019-0012345, DL-0420110123456, MH0220180012345)
DL_REGEX = re.compile(r"\b([A-Z]{2}[-\s]?[0-9]{2}[-\s]?[0-9]{4}[-\s]?[0-9]{7})\b")
DL_ALT_REGEX = re.compile(r"\b([A-Z]{2}[0-9]{13,15})\b")

# Indian Vehicle Classes
VEHICLE_CLASSES = ["MCWG", "MCWOG", "LMV", "TRANS", "HMV", "HGMV", "HPMV", "3W-NT", "3W-CAB", "LMV-NT"]


class DrivingLicenseParser(BaseDocumentParser):
    def __init__(self):
        super().__init__("driving_license")

    def parse(self, ocr_result: OCRResult) -> DocumentParserResult:
        fields: Dict[str, Dict[str, Any]] = {}
        warnings: List[str] = []

        lines = ocr_result.lines
        full_text = ocr_result.text

        # 1. Extract Driving Licence Number
        dl_val = None
        for line in lines:
            txt = line.text.strip().upper()
            match = DL_REGEX.search(txt) or DL_ALT_REGEX.search(txt)
            if match:
                raw_dl = match.group(1).replace("-", " ").strip()
                # Clean up multiple spaces
                dl_val = re.sub(r"\s+", " ", raw_dl)
                fields["id_number"] = ExtractedField(value=dl_val, confidence=line.confidence, source_line=line.text).to_dict()
                fields["license_number"] = fields["id_number"]
                break

        # 2. Extract Date of Birth
        for line in lines:
            txt = line.text.strip()
            if re.search(r"(DOB|Birth|जन्म|D\.O\.B)", txt, re.IGNORECASE):
                d = self.extract_date(txt)
                if d:
                    fields["dob"] = ExtractedField(value=d, confidence=line.confidence, source_line=txt).to_dict()
                    fields["date_of_birth"] = fields["dob"]
                    break

        # 3. Extract Name
        for i, line in enumerate(lines):
            txt = line.text.strip()
            if re.search(r"^Name\s*[:\-]\s*", txt, re.IGNORECASE):
                cleaned = self.clean_name(txt)
                if len(cleaned) >= 3:
                    fields["name"] = ExtractedField(value=cleaned, confidence=line.confidence, source_line=txt).to_dict()
                    break

        if "name" not in fields:
            # Look for lines following header words
            for line in lines:
                txt = line.text.strip()
                if re.search(r"(UNION|DRIVING|LICENCE|LICENSE|TRANSPORT|DEPARTMENT|MOTOR|VEHICLES|INDIA|GOVT)", txt, re.IGNORECASE):
                    continue
                if DL_REGEX.search(txt.upper()) or self.extract_date(txt):
                    continue
                cleaned = self.clean_name(txt)
                if len(cleaned) >= 3 and not re.search(r"\d", cleaned):
                    fields["name"] = ExtractedField(value=cleaned, confidence=line.confidence * 0.85, source_line=txt).to_dict()
                    break

        # 4. Extract Vehicle Classes (e.g. LMV, MCWG)
        found_classes = set()
        for line in lines:
            txt = line.text.upper()
            for vc in VEHICLE_CLASSES:
                if re.search(r"\b" + vc + r"\b", txt):
                    found_classes.add(vc)

        if found_classes:
            classes_str = ", ".join(sorted(found_classes))
            fields["vehicle_class"] = ExtractedField(value=classes_str, confidence=0.90).to_dict()

        # 5. Extract Validity / Expiry Date
        for line in lines:
            txt = line.text.strip()
            if re.search(r"(Valid|Validity|Expiry|Expires|Till)", txt, re.IGNORECASE):
                d = self.extract_date(txt)
                if d:
                    fields["valid_until"] = ExtractedField(value=d, confidence=line.confidence, source_line=txt).to_dict()
                    break

        # Status Assessment
        has_id = "id_number" in fields
        has_name = "name" in fields

        field_confidences = {k: v["confidence"] for k, v in fields.items()}
        avg_conf = (sum(field_confidences.values()) / len(field_confidences)) if field_confidences else 0.0

        if has_id and has_name and avg_conf >= 0.65:
            status = "OCR_EXTRACTED"
        else:
            status = "NEEDS_REVIEW"
            if not has_id:
                warnings.append("Could not identify valid Driving Licence number.")
            if not has_name:
                warnings.append("Could not confidently identify driver name.")
            if avg_conf < 0.65:
                warnings.append("OCR confidence is below standard threshold.")

        return DocumentParserResult(
            fields=fields,
            status=status,
            document_type="driving_license",
            confidence_score=round(avg_conf, 4),
            warnings=warnings,
            field_confidence=field_confidences,
            ocr_engine=ocr_result.engine,
        )
