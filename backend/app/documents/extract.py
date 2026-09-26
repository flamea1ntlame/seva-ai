"""
SEVA AI - Document Field Extraction Pipeline

Primary: Pretrained PaddleOCR with OpenCV/PIL image preprocessing
         and document-specific layout parsers (Aadhaar, PAN, Driving Licence, Generic).
Secondary Fallback: Gemini Vision API (only if configured and OCR yields insufficient fields).
Failure Result: Returns real failure / NEEDS_REVIEW status without inventing citizen data.

RULE: Never return hardcoded citizen identity values (e.g. Rahul Kumar).
RULE: Never log raw PII numbers (Aadhaar, PAN, DL).
"""

import os
import json
import logging
from typing import Dict, Any, Optional

from app.documents.ocr import perform_ocr, OCRResult, OCRLine
from app.documents.parsers import get_parser_for_document_type, DocumentParserResult

logger = logging.getLogger(__name__)


async def extract_document_fields(file_path: str, document_type: str) -> Dict[str, Any]:
    """
    Extracts structured fields from an uploaded document using a pretrained OCR engine
    and document-specific rule parsers. Falls back to Gemini Vision if configured
    and primary OCR yields insufficient fields.
    """
    if not os.path.exists(file_path):
        logger.error("Document extraction failed: file not found at path %s", file_path)
        return {
            "_ocr_status": "NEEDS_REVIEW",
            "_ocr_engine": "none",
            "_confidence_score": 0.0,
            "_warnings": ["Document file does not exist on disk."],
            "fields": {},
        }

    ext = os.path.splitext(file_path)[1].lower()

    # 1. Primary Extraction Path: Pretrained OCR
    ocr_result: Optional[OCRResult] = None
    try:
        if ext == ".txt":
            # Support text fixtures for unit tests and synthetic seed files
            lines = []
            full_text_parts = []
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    stripped = line.strip()
                    if stripped:
                        lines.append(OCRLine(text=stripped, confidence=0.99, bbox=[0, 0, 0, 0], page=1))
                        full_text_parts.append(stripped)
            ocr_result = OCRResult(
                text="\n".join(full_text_parts),
                lines=lines,
                average_confidence=0.99,
                page_count=1,
                engine="text_reader"
            )
        else:
            ocr_result = perform_ocr(file_path)
    except Exception as e:
        logger.warning("Primary OCR pipeline raised exception on %s: %s", ext, e)

    # Run document-specific parser on OCR result
    if ocr_result and ocr_result.lines:
        parser = get_parser_for_document_type(document_type)
        parser_res: DocumentParserResult = parser.parse(ocr_result)

        logger.info(
            "Document parsed (%s): status=%s, fields_count=%d, confidence=%.3f, engine=%s",
            document_type,
            parser_res.status,
            len(parser_res.fields),
            parser_res.confidence_score,
            parser_res.ocr_engine
        )

        # If primary OCR extracted confident fields, format and return immediately
        if parser_res.fields and parser_res.confidence_score >= 0.50:
            return _format_extraction_response(parser_res)

        # If fields were extracted but low confidence, keep parser_res for fallback comparison
        best_parser_res = parser_res
    else:
        best_parser_res = None

    # 2. Secondary Fallback: Gemini Vision (if configured and primary OCR yielded insufficient fields)
    from app.config import settings
    api_key = settings.GEMINI_API_KEY
    model_name = settings.GEMINI_MODEL

    if api_key:
        try:
            logger.info("Attempting secondary Gemini Vision fallback for document_type=%s", document_type)
            gemini_fields = await _extract_with_gemini_vision(file_path, document_type, api_key, model_name)
            if gemini_fields and any(v for v in gemini_fields.values() if v is not None):
                # Construct formatted output with field confidences
                formatted_fields = {}
                for k, v in gemini_fields.items():
                    if v is not None:
                        formatted_fields[k] = {"value": v, "confidence": 0.85}

                return {
                    **gemini_fields,
                    "fields": formatted_fields,
                    "_confidence": {k: 0.85 for k in gemini_fields},
                    "_confidence_score": 0.85,
                    "_ocr_status": "OCR_EXTRACTED",
                    "_ocr_engine": "gemini_vision",
                    "_warnings": ["Extracted using secondary Gemini Vision fallback."],
                }
        except Exception as e:
            logger.warning("Secondary Gemini Vision fallback failed: %s", e)

    # 3. If primary OCR produced partial fields, return with NEEDS_REVIEW
    if best_parser_res and best_parser_res.fields:
        return _format_extraction_response(best_parser_res)

    # 4. Real Failure: No fields could be extracted
    logger.warning("OCR and fallback extraction failed completely for %s (type: %s)", file_path, document_type)
    return {
        "_ocr_status": "NEEDS_REVIEW",
        "_ocr_engine": ocr_result.engine if ocr_result else "none",
        "_confidence_score": 0.0,
        "_warnings": ["Failed to extract required fields from the document. Please verify image clarity and re-upload."],
        "fields": {},
    }


def _format_extraction_response(parser_res: DocumentParserResult) -> Dict[str, Any]:
    """
    Formats DocumentParserResult into the dictionary structure expected by SEVA models,
    routers, and workflows, exposing both flat values and field-level confidence.
    """
    response: Dict[str, Any] = {}
    for k, v in parser_res.fields.items():
        if isinstance(v, dict) and "value" in v:
            response[k] = v["value"]
        else:
            response[k] = v

    response["fields"] = parser_res.fields
    response["_confidence"] = parser_res.field_confidence
    response["_confidence_score"] = parser_res.confidence_score
    response["_ocr_status"] = parser_res.status
    response["_ocr_engine"] = parser_res.ocr_engine
    response["_warnings"] = parser_res.warnings
    return response


async def _extract_with_gemini_vision(
    file_path: str,
    document_type: str,
    api_key: str,
    model_name: str
) -> Dict[str, Any]:
    """Secondary fallback: Gemini Vision API for document understanding."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    ext = os.path.splitext(file_path)[1].lower()
    media_type = None
    if ext in [".jpg", ".jpeg"]:
        media_type = "image/jpeg"
    elif ext == ".png":
        media_type = "image/png"
    elif ext == ".webp":
        media_type = "image/webp"
    elif ext == ".pdf":
        media_type = "application/pdf"

    if not media_type:
        return {}

    schemas = {
        "identity_proof": {
            "type": "OBJECT",
            "properties": {
                "name": {"type": "STRING"},
                "dob": {"type": "STRING"},
                "address": {"type": "STRING"},
                "id_number": {"type": "STRING"}
            }
        },
        "income_proof": {
            "type": "OBJECT",
            "properties": {
                "annual_income": {"type": "NUMBER"},
                "employer": {"type": "STRING"}
            }
        },
        "address_proof": {
            "type": "OBJECT",
            "properties": {
                "address": {"type": "STRING"}
            }
        },
        "hospital_certificate": {
            "type": "OBJECT",
            "properties": {
                "applicant_name": {"type": "STRING"},
                "date_of_birth": {"type": "STRING"},
                "place_of_birth": {"type": "STRING"},
                "mother_name": {"type": "STRING"},
                "father_name": {"type": "STRING"}
            }
        },
        "medical_declaration": {
            "type": "OBJECT",
            "properties": {
                "blood_group": {"type": "STRING"},
                "fitness_confirmed": {"type": "BOOLEAN"}
            }
        }
    }

    req_schema = schemas.get(document_type, {"type": "OBJECT", "properties": {"extracted_text": {"type": "STRING"}}})

    prompt = (
        f"You are a document OCR and extraction AI for official government documents.\n"
        f"Extract key fields for document type '{document_type}'.\n"
        f"Do NOT invent or hallucinate citizen data. If a field is missing, return null."
    )

    contents = [
        types.Part.from_bytes(data=file_bytes, mime_type=media_type),
        prompt
    ]

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=req_schema,
        temperature=0.0
    )

    response = await client.aio.models.generate_content(
        model=model_name,
        contents=contents,
        config=config
    )
    text_resp = response.text if response.text else "{}"

    text_resp = text_resp.strip()
    if text_resp.startswith("```json"):
        text_resp = text_resp[7:]
    if text_resp.startswith("```"):
        text_resp = text_resp[3:]
    if text_resp.endswith("```"):
        text_resp = text_resp[:-3]

    return json.loads(text_resp.strip())
