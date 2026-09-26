"""
SEVA AI - Intent Recognition and Service Matching Engine

Classifies citizen intents, maps natural language phrases and domain synonyms to official services,
extracts entities (application references, document types, jurisdictions), and flags ambiguities.
"""

import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from app.nlp.normalizer import NormalizationResult, normalize_text


class Intent:
    APPLY_SERVICE = "APPLY_SERVICE"
    CHECK_REQUIREMENTS = "CHECK_REQUIREMENTS"
    CHECK_STATUS_OR_MISSING = "CHECK_STATUS_OR_MISSING"
    DOCUMENT_UPLOADED_FOLLOWUP = "DOCUMENT_UPLOADED_FOLLOWUP"
    PREPARE_OR_SUBMIT = "PREPARE_OR_SUBMIT"
    AMBIGUOUS_SERVICE = "AMBIGUOUS_SERVICE"
    GENERAL_INQUIRY = "GENERAL_INQUIRY"


@dataclass
class IntentMatchResult:
    intent: str
    service_code: Optional[str] = None
    confidence: float = 0.0
    entities: Dict[str, Any] = field(default_factory=dict)
    clarification_needed: bool = False
    clarification_prompt: Optional[str] = None
    clarification_options: List[str] = field(default_factory=list)


def match_intent_and_service(
    normalized_result: NormalizationResult,
    has_active_apps: bool = False,
    active_service_codes: Optional[List[str]] = None
) -> IntentMatchResult:
    """
    Analyzes normalized text to identify the citizen's intent, target service code,
    and associated parameters.
    """
    text = normalized_result.normalized_text.lower().strip()
    entities: Dict[str, Any] = {}

    # Extract SEVA application numbers (e.g., SEVA-123456)
    seva_refs = [ref.upper() for ref in re.findall(r"\bseva-\d+\b", text, flags=re.IGNORECASE)]
    if seva_refs:
        entities["application_numbers"] = seva_refs

    # Detect document types mentioned
    doc_types = []
    if "aadhaar" in text or "id proof" in text or "identity" in text or "voter" in text or "pan" in text or "passport" in text or "my id" in text:
        doc_types.append("identity_proof")
    if "address" in text or "utility bill" in text or "electricity bill" in text or "ration card" in text:
        doc_types.append("address_proof")
    if "income proof" in text or "salary slip" in text or "form 16" in text or "itr" in text or "pay slip" in text:
        doc_types.append("income_proof")
    if "hospital" in text or "birth report" in text or "discharge summary" in text:
        doc_types.append("hospital_certificate")
    if "photo" in text or "photograph" in text:
        doc_types.append("photograph")
    if "medical" in text or "fitness" in text:
        doc_types.append("medical_declaration")
    entities["mentioned_document_types"] = doc_types

    # Service Recognition logic
    detected_service: Optional[str] = None
    service_confidence = 0.0

    # 1. Driving License Matching
    if any(k in text for k in [
        "driving licence", "driving license", "driver licence", "driver license",
        "drive vehicle", "drive car", "rto licence", "learner licence", "learning licence"
    ]):
        detected_service = "driving_license"
        service_confidence = 0.95
    elif "driving" in text or "licence" in text or "license" in text:
        detected_service = "driving_license"
        service_confidence = 0.90

    # 2. Birth Certificate Matching
    elif any(k in text for k in [
        "birth certificate", "birth cert", "newborn", "new born",
        "baby birth", "child birth", "born certificate", "janma praman"
    ]):
        detected_service = "birth_certificate"
        service_confidence = 0.95
    elif "birth" in text and ("child" in text or "baby" in text or "certificate" in text or "register" in text):
        detected_service = "birth_certificate"
        service_confidence = 0.90

    # 3. Income Certificate Matching
    elif any(k in text for k in [
        "income certificate", "income cert", "family income", "prove family income",
        "income proof", "salary certificate", "earnings certificate", "revenue certificate"
    ]):
        detected_service = "income_certificate"
        service_confidence = 0.95
    elif "scholarship" in text or "scholership" in text:
        # User asking about scholarship documentation / proof
        detected_service = "income_certificate"
        service_confidence = 0.85
        entities["reason"] = "scholarship_eligibility"
    elif "income" in text:
        detected_service = "income_certificate"
        service_confidence = 0.85

    # Intent Classification

    # A. Prepare / Submit Application
    if any(k in text for k in [
        "prepare my application", "submit my application", "prepare it", "submit it",
        "ready for review", "ready to submit", "proceed with submission", "submit seva-", "prepare seva-"
    ]) or ("submit" in text and ("application" in text or bool(seva_refs))) or ("prepare" in text and ("application" in text or bool(seva_refs))):
        return IntentMatchResult(
            intent=Intent.PREPARE_OR_SUBMIT,
            service_code=detected_service,
            confidence=0.95,
            entities=entities
        )

    # B. Document Uploaded Follow-up ("i already uploaded my id", "i uploaded my income proof")
    if any(k in text for k in [
        "already uploaded", "i uploaded", "uploaded my", "i have uploaded",
        "check my document", "check my docs", "uploaded id", "already submitted my"
    ]):
        return IntentMatchResult(
            intent=Intent.DOCUMENT_UPLOADED_FOLLOWUP,
            service_code=detected_service or (active_service_codes[0] if active_service_codes and len(active_service_codes) == 1 else None),
            confidence=0.90,
            entities=entities
        )

    # C. Missing requirements / Status check ("what am i missing?", "what is pending?", "what do i still need?")
    if any(k in text for k in [
        "what am i missing", "what is missing", "what am i still missing",
        "what is pending", "what do i still need", "missing docs", "missing documents",
        "status of my application", "how is my application going"
    ]):
        return IntentMatchResult(
            intent=Intent.CHECK_STATUS_OR_MISSING,
            service_code=detected_service or (active_service_codes[0] if active_service_codes and len(active_service_codes) == 1 else None),
            confidence=0.92,
            entities=entities
        )

    # D. Requirements Inquiry ("what papers do i need", "how can i prove my family income", "where do i get income proof")
    if any(k in text for k in [
        "what papers do i need", "what documents are required", "what documents do i need",
        "which papers do i need", "what proof is needed", "how can i prove",
        "where do i get", "how to prove", "requirements for"
    ]) or (("what" in text or "which" in text) and ("documents" in text or "papers" in text or "proof" in text)):
        return IntentMatchResult(
            intent=Intent.CHECK_REQUIREMENTS,
            service_code=detected_service or (active_service_codes[0] if active_service_codes and len(active_service_codes) == 1 else None),
            confidence=0.90,
            entities=entities
        )

    # E. Apply for Service (explicit desire to obtain or apply for a service)
    if detected_service and (
        any(k in text for k in ["need", "want", "apply", "get", "issue", "make", "create", "help with", "for my"])
        or len(text.split()) <= 4  # Short commands like "need income cert", "incom certificate"
    ):
        return IntentMatchResult(
            intent=Intent.APPLY_SERVICE,
            service_code=detected_service,
            confidence=service_confidence,
            entities=entities
        )

    # F. Ambiguous Government Request (e.g. "I need a government certificate", "I need government help")
    if any(k in text for k in [
        "government certificate", "govt certificate", "some certificate",
        "official certificate", "need a certificate", "apply for certificate"
    ]) and not detected_service:
        return IntentMatchResult(
            intent=Intent.AMBIGUOUS_SERVICE,
            service_code=None,
            confidence=0.80,
            entities=entities,
            clarification_needed=True,
            clarification_prompt="Could you please specify which service you would like to apply for?",
            clarification_options=["Income Certificate", "Birth Certificate", "Driving License"]
        )

    # Fallback to detected service or general inquiry
    if detected_service:
        return IntentMatchResult(
            intent=Intent.APPLY_SERVICE,
            service_code=detected_service,
            confidence=service_confidence,
            entities=entities
        )

    return IntentMatchResult(
        intent=Intent.GENERAL_INQUIRY,
        service_code=None,
        confidence=0.5,
        entities=entities,
        clarification_needed=True,
        clarification_prompt="Could you please specify which service you would like to apply for?",
        clarification_options=["Income Certificate", "Birth Certificate", "Driving License"]
    )
