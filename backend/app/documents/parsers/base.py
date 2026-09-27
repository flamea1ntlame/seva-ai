"""
SEVA AI - Base Document Parser

Defines standardized field extraction results, confidence calculation,
date extraction utilities, and validation interfaces for government documents.
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Tuple
from app.documents.ocr import OCRResult, OCRLine


@dataclass
class ExtractedField:
    value: Any
    confidence: float
    source_line: Optional[str] = None
    bbox: Optional[List[int]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": self.value,
            "confidence": round(float(self.confidence), 4),
        }


@dataclass
class DocumentParserResult:
    fields: Dict[str, Dict[str, Any]]  # {"name": {"value": "...", "confidence": 0.95}}
    status: str                         # "OCR_EXTRACTED" or "NEEDS_REVIEW"
    document_type: str
    confidence_score: float
    warnings: List[str] = field(default_factory=list)
    field_confidence: Dict[str, float] = field(default_factory=dict)
    ocr_engine: str = "paddleocr"

    def to_extracted_data(self) -> Dict[str, Any]:
        """
        Flattens fields into the dictionary structure expected by SEVA models & workflows,
        while maintaining confidence metadata.
        """
        flattened: Dict[str, Any] = {}
        for k, v in self.fields.items():
            if isinstance(v, dict) and "value" in v:
                flattened[k] = v["value"]
            else:
                flattened[k] = v
        # Attach confidence scores dictionary for transparency & auditing
        flattened["_confidence"] = {k: v.get("confidence", 1.0) if isinstance(v, dict) else 1.0 for k, v in self.fields.items()}
        flattened["_ocr_status"] = self.status
        flattened["_ocr_engine"] = self.ocr_engine
        return flattened


class BaseDocumentParser(ABC):
    def __init__(self, document_type: str):
        self.document_type = document_type

    @abstractmethod
    def parse(self, ocr_result: OCRResult) -> DocumentParserResult:
        """Parses raw OCR output into typed government document fields."""
        pass

    @staticmethod
    def extract_date(text: str) -> Optional[str]:
        """Extracts standard dates (DD/MM/YYYY, YYYY-MM-DD, DD-MM-YYYY)."""
        patterns = [
            r"\b(\d{2})[/.-](\d{2})[/.-](\d{4})\b",  # DD/MM/YYYY
            r"\b(\d{4})[/.-](\d{2})[/.-](\d{2})\b",  # YYYY/MM/DD
        ]
        for pat in patterns:
            match = re.search(pat, text)
            if match:
                parts = match.groups()
                if len(parts[0]) == 4:
                    return f"{parts[0]}-{parts[1]}-{parts[2]}"
                else:
                    return f"{parts[2]}-{parts[1]}-{parts[0]}"
        return None

    @staticmethod
    def clean_name(name_candidate: str) -> str:
        """Sanitizes names: removes titles, non-alphabetic chars, extra whitespace."""
        name = re.sub(r"^(Name|नाम|Mr\.?|Mrs\.?|Ms\.?|Dr\.?|Shri|Smt\.?)\s*[:\-\.]?\s*", "", name_candidate, flags=re.IGNORECASE)
        name = re.sub(r"[^A-Za-z\s\.]", "", name)
        name = re.sub(r"\s+", " ", name).strip()
        return name
