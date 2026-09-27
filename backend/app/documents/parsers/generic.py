"""
SEVA AI - Generic Government Document Parser

Handles secondary document types (income proof, hospital certificate, medical declaration,
address proof, etc.) using deterministic regex/pattern heuristics with confidence scoring.
"""

import re
from typing import Dict, Any, List, Optional
from app.documents.ocr import OCRResult
from app.documents.parsers.base import BaseDocumentParser, DocumentParserResult, ExtractedField


class GenericDocumentParser(BaseDocumentParser):
    def parse(self, ocr_result: OCRResult) -> DocumentParserResult:
        fields: Dict[str, Dict[str, Any]] = {}
        warnings: List[str] = []

        lines = ocr_result.lines
        full_text = ocr_result.text

        doc_type = self.document_type.lower()

        if doc_type in ["income_proof", "income_certificate", "salary_slip"]:
            # Extract Annual Gross Income / Salary
            # Pattern: Rs. / INR / Gross / Income: 4,50,000 or 450000
            income_match = re.search(r"(?:Income|Salary|Gross|Rs\.?|INR)\s*[:\-\s]?\s*(?:Rs\.?|INR)?\s*([0-9,]+(?:\.[0-9]{2})?)", full_text, re.IGNORECASE)
            if income_match:
                raw_amt = income_match.group(1).replace(",", "")
                try:
                    val = float(raw_amt)
                    fields["annual_income"] = ExtractedField(value=val, confidence=0.85).to_dict()
                except ValueError:
                    pass

            # Extract Employer Name
            for line in lines:
                if re.search(r"Employer\s*[:\-]\s*", line.text, re.IGNORECASE):
                    emp = re.sub(r"Employer\s*[:\-]\s*", "", line.text, flags=re.IGNORECASE).strip()
                    if emp:
                        fields["employer"] = ExtractedField(value=emp, confidence=line.confidence).to_dict()
                        break

            # Date
            for line in lines:
                d = self.extract_date(line.text)
                if d:
                    fields["assessment_date"] = ExtractedField(value=d, confidence=line.confidence).to_dict()
                    break

        elif doc_type in ["hospital_certificate", "birth_certificate", "proof_of_birth"]:
            # Hospital Certificate / Birth Notification
            for line in lines:
                if re.search(r"(Child|Applicant|Patient)\s*Name\s*[:\-]\s*", line.text, re.IGNORECASE):
                    name = re.sub(r"(Child|Applicant|Patient)\s*Name\s*[:\-]\s*", "", line.text, flags=re.IGNORECASE).strip()
                    if name:
                        fields["applicant_name"] = ExtractedField(value=self.clean_name(name), confidence=line.confidence).to_dict()
                elif re.search(r"Father(?:'s)?\s*Name\s*[:\-]\s*", line.text, re.IGNORECASE):
                    fn = re.sub(r"Father(?:'s)?\s*Name\s*[:\-]\s*", "", line.text, flags=re.IGNORECASE).strip()
                    if fn:
                        fields["father_name"] = ExtractedField(value=self.clean_name(fn), confidence=line.confidence).to_dict()
                elif re.search(r"Mother(?:'s)?\s*Name\s*[:\-]\s*", line.text, re.IGNORECASE):
                    mn = re.sub(r"Mother(?:'s)?\s*Name\s*[:\-]\s*", "", line.text, flags=re.IGNORECASE).strip()
                    if mn:
                        fields["mother_name"] = ExtractedField(value=self.clean_name(mn), confidence=line.confidence).to_dict()
                elif re.search(r"(Place|Hospital)\s*[:\-]\s*", line.text, re.IGNORECASE):
                    p = re.sub(r"(Place|Hospital)\s*[:\-]\s*", "", line.text, flags=re.IGNORECASE).strip()
                    if p:
                        fields["place_of_birth"] = ExtractedField(value=p, confidence=line.confidence).to_dict()

            # Date of Birth
            for line in lines:
                if re.search(r"(Birth|DOB)", line.text, re.IGNORECASE):
                    d = self.extract_date(line.text)
                    if d:
                        fields["date_of_birth"] = ExtractedField(value=d, confidence=line.confidence).to_dict()
                        break

        elif doc_type in ["medical_declaration", "medical_certificate"]:
            # Blood Group
            bg_match = re.search(r"\b((?:AB|A|B|O)[+-])", full_text, re.IGNORECASE)
            if bg_match:
                fields["blood_group"] = ExtractedField(value=bg_match.group(0).upper(), confidence=0.92).to_dict()

            # Fitness
            if re.search(r"\b(FIT|CONFIRMED|HEALTHY)\b", full_text, re.IGNORECASE):
                fields["fitness_confirmed"] = ExtractedField(value=True, confidence=0.88).to_dict()

        elif doc_type in ["address_proof", "utility_bill"]:
            # Address line and Pincode
            pin_match = re.search(r"\b([1-9]\d{5})\b", full_text)
            if pin_match:
                fields["pincode"] = ExtractedField(value=pin_match.group(1), confidence=0.90).to_dict()

            for line in lines:
                if re.search(r"Address\s*[:\-]\s*", line.text, re.IGNORECASE):
                    addr = re.sub(r"Address\s*[:\-]\s*", "", line.text, flags=re.IGNORECASE).strip()
                    if len(addr) >= 5:
                        fields["address"] = ExtractedField(value=addr, confidence=line.confidence).to_dict()
                        break

        # Fallback raw line snippet if no specific fields matched
        if not fields and lines:
            valid_lines = [l.text.strip() for l in lines if len(l.text.strip()) > 3]
            if valid_lines:
                fields["extracted_summary"] = ExtractedField(
                    value="; ".join(valid_lines[:3]),
                    confidence=min(0.70, ocr_result.average_confidence)
                ).to_dict()

        field_confidences = {k: v["confidence"] for k, v in fields.items()}
        avg_conf = (sum(field_confidences.values()) / len(field_confidences)) if field_confidences else 0.0

        status = "OCR_EXTRACTED" if fields and avg_conf >= 0.50 else "NEEDS_REVIEW"
        if not fields:
            warnings.append(f"No structured fields recognized for document type '{self.document_type}'.")

        return DocumentParserResult(
            fields=fields,
            status=status,
            document_type=self.document_type,
            confidence_score=round(avg_conf, 4),
            warnings=warnings,
            field_confidence=field_confidences,
            ocr_engine=ocr_result.engine,
        )
