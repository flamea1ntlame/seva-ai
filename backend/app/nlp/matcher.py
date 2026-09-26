"""
SEVA AI - Intent Recognition and Service Matching Engine

Classifies citizen intents, maps natural language phrases and domain synonyms to official services,
extracts entities (application references, document types, jurisdictions), handles contradictory statements,
and flags ambiguities.
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
    and associated parameters. Handles contradictory user messages and extracts jurisdictions.
    """
    text = normalized_result.normalized_text.lower().strip()
    entities: Dict[str, Any] = {}

    # Extract SEVA application numbers (e.g., SEVA-123456)
    seva_refs = [ref.upper() for ref in re.findall(r"\bseva-\d+\b", text, flags=re.IGNORECASE)]
    if seva_refs:
        entities["application_numbers"] = seva_refs

    # Detect jurisdiction mentioned
    known_states = [
        "karnataka", "maharashtra", "delhi", "kerala", "tamil nadu",
        "rajasthan", "gujarat", "uttar pradesh", "punjab", "haryana",
        "west bengal", "andhra pradesh", "telangana", "bihar", "odisha", "assam"
    ]
    for state in known_states:
        if state in text:
            entities["jurisdiction"] = state
            break

    # Detect document types mentioned (differentiating parent ID vs applicant ID)
    doc_types = []
    if "parent" in text and ("aadhaar" in text or "id" in text or "voter" in text or "passport" in text or "pan" in text):
        doc_types.append("parent_identity_proof")
    elif any(k in text for k in ["aadhaar", "id proof", "identity", "voter", "pan", "passport", "my id"]):
        doc_types.append("identity_proof")

    if any(k in text for k in ["address", "utility bill", "electricity bill", "water bill", "ration card", "domicile"]):
        doc_types.append("address_proof")
    if any(k in text for k in ["income proof", "salary slip", "salary slips", "form 16", "itr", "pay slip", "family income"]):
        doc_types.append("income_proof")
    if any(k in text for k in ["hospital", "birth report", "discharge summary", "birth notification"]):
        doc_types.append("hospital_certificate")
    if "photo" in text or "photograph" in text:
        doc_types.append("photograph")
    if "medical" in text or "fitness" in text:
        doc_types.append("medical_declaration")
    entities["mentioned_document_types"] = doc_types

    # Service Candidates & Contradiction Resolution
    # e.g., "actually I don't want income cert, I want driving license instead"
    services_found = []
    
    # Driving License
    if any(k in text for k in [
        "driving licence", "driving license", "driver licence", "driver license",
        "drive vehicle", "drive car", "rto licence", "learner licence", "learning licence"
    ]) or "driving" in text or "licence" in text or "license" in text:
        services_found.append(("driving_license", 0.95))

    # Birth Certificate
    if any(k in text for k in [
        "birth certificate", "birth cert", "newborn", "new born",
        "baby birth", "child birth", "born certificate", "janma praman"
    ]) or ("birth" in text and any(k in text for k in ["child", "baby", "certificate", "register"])):
        services_found.append(("birth_certificate", 0.95))

    # Income Certificate
    if any(k in text for k in [
        "income certificate", "income cert", "family income", "prove family income",
        "income proof", "salary certificate", "earnings certificate", "revenue certificate"
    ]) or "income" in text or "scholarship" in text or "scholership" in text:
        services_found.append(("income_certificate", 0.90))
        if "scholarship" in text or "scholership" in text:
            entities["reason"] = "scholarship_eligibility"

    detected_service: Optional[str] = None
    service_confidence = 0.0

    if len(services_found) == 1:
        detected_service, service_confidence = services_found[0]
    elif len(services_found) > 1:
        # Check for contradictions or corrections: "not <A>, I want <B>", "instead", "rather"
        # Find which service comes after contradiction markers like "instead", "want", "actually"
        corrected_service = None
        for svc_code, _ in services_found:
            negation_pattern = rf"(?:not|don\'t want|cancel)\s+(?:an?\s+)?{svc_code.replace('_', ' ')}"
            if re.search(negation_pattern, text):
                continue
            corrected_service = svc_code

        if corrected_service:
            detected_service = corrected_service
            service_confidence = 0.92
        else:
            # Take the last mentioned service as the recency override
            detected_service, service_confidence = services_found[-1]

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
        or len(text.split()) <= 5
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
