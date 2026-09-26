import re
from typing import Dict, Any, Optional, Tuple


def canonicalize_document_type(raw_type: str) -> str:
    """Normalizes document types to canonical identifiers."""
    clean = (raw_type or "").lower().strip()
    if any(k in clean for k in ("aadhaar", "uid", "adhaar", "aadhar")):
        return "aadhaar"
    if "pan" in clean:
        return "pan"
    if any(k in clean for k in ("voter", "epic", "election")):
        return "voter_id"
    if any(k in clean for k in ("driving", "license", "licence", "dl", "sarathi")):
        return "driving_licence"
    if "identity_proof" in clean or "id_proof" in clean:
        return "identity_proof"
    return clean


def classify_document(
    declared_type: str,
    extracted_fields: Dict[str, Any],
    raw_text: Optional[str] = None
) -> Tuple[str, float, list[str]]:
    """
    Deterministic classification of government document types based on textual/field signatures.
    Returns: (detected_document_type, confidence, risk_flags)
    """
    risk_flags = []
    text = (raw_text or "").upper()
    fields_str = " ".join(f"{k}:{v}" for k, v in extracted_fields.items()).upper()
    combined = f"{text} {fields_str}"

    scores = {
        "aadhaar": 0,
        "pan": 0,
        "voter_id": 0,
        "driving_licence": 0
    }

    # Aadhaar signatures
    if "GOVERNMENT OF INDIA" in combined or "BHARAT SARKAR" in combined or "UIDAI" in combined:
        scores["aadhaar"] += 3
    if "AADHAAR" in combined or "MERA AADHAAR" in combined or "UNIQUE IDENTIFICATION" in combined:
        scores["aadhaar"] += 4
    if re.search(r"\b[2-9]{1}[0-9]{3}[ \-]?[0-9]{4}[ \-]?[0-9]{4}\b", combined):
        scores["aadhaar"] += 4

    # PAN signatures
    if "INCOME TAX DEPARTMENT" in combined or "AAYAKAR" in combined:
        scores["pan"] += 4
    if "PERMANENT ACCOUNT NUMBER" in combined or "PAN" in combined:
        scores["pan"] += 3
    if re.search(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", combined):
        scores["pan"] += 5

    # Voter ID signatures
    if "ELECTION COMMISSION OF INDIA" in combined or "BHARAT NIRVACHAN" in combined:
        scores["voter_id"] += 4
    if "ELECTOR PHOTO IDENTITY CARD" in combined or "EPIC" in combined:
        scores["voter_id"] += 4
    if re.search(r"\b[A-Z]{3}[0-9]{7}\b", combined):
        scores["voter_id"] += 4

    # Driving Licence signatures
    if "DRIVING LICENCE" in combined or "DRIVING LICENSE" in combined or "MOTOR VEHICLES" in combined:
        scores["driving_licence"] += 4
    if "UNION OF INDIA" in combined or "TRANSPORT DEPARTMENT" in combined or "RTO" in combined:
        scores["driving_licence"] += 3
    if re.search(r"\b[A-Z]{2}[0-9]{2}[0-9]{4}[0-9]{7}\b", combined):
        scores["driving_licence"] += 5

    # Find highest scoring type
    best_type = max(scores, key=scores.get)
    best_score = scores[best_type]

    canonical_declared = canonicalize_document_type(declared_type)

    if best_score >= 3:
        confidence = min(0.99, 0.60 + (best_score * 0.05))
        detected = best_type
    else:
        # If visual evidence is insufficient to detect, fall back to declared type if supported
        if canonical_declared in scores:
            detected = canonical_declared
            confidence = 0.50
        else:
            detected = "unknown"
            confidence = 0.20
            risk_flags.append("UNKNOWN_DOCUMENT_TYPE")

    # Mismatch warning
    if canonical_declared in scores and detected in scores and canonical_declared != detected:
        risk_flags.append(f"DOCUMENT_TYPE_MISMATCH_DECLARED_{canonical_declared.upper()}_DETECTED_{detected.upper()}")

    return detected, confidence, risk_flags
