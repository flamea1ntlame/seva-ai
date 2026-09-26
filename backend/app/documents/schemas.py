from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class DocumentVerificationStatus(str, Enum):
    # Core lifecycle states
    NOT_CHECKED = "NOT_CHECKED"
    PENDING = "PENDING"
    EXTRACTED = "EXTRACTED"
    OCR_EXTRACTED = "OCR_EXTRACTED"
    SIGNATURE_VALID = "SIGNATURE_VALID"
    ISSUER_VERIFIED = "ISSUER_VERIFIED"
    REGISTRY_MATCHED = "REGISTRY_MATCHED"
    VERIFIED = "VERIFIED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    SUSPICIOUS = "SUSPICIOUS"
    NOT_VERIFIABLE = "NOT_VERIFIABLE"
    REJECTED = "REJECTED"


class VerificationMethod(str, Enum):
    DIGITAL_SIGNATURE = "DIGITAL_SIGNATURE"
    ISSUER_VERIFICATION = "ISSUER_VERIFICATION"
    REGISTRY_MATCH = "REGISTRY_MATCH"
    DIGILOCKER = "DIGILOCKER"
    QR_ANALYSIS = "QR_ANALYSIS"
    FORMAT_CHECKSUM = "FORMAT_CHECKSUM"
    VISUAL_ANALYSIS = "VISUAL_ANALYSIS"


class ExtractedField(BaseModel):
    """
    Representation of an individual extracted field with optional confidence,
    redaction state, and raw visual value.
    """
    field_name: str
    value: Any
    redacted_value: Optional[str] = None
    is_sensitive: bool = False
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class ExtractionResult(BaseModel):
    """
    Strict contract returned by document extractors (e.g. Charitha's OCR/LLM engine).
    """
    document_type: str = Field(
        ...,
        description="Declared document type (e.g., aadhaar, pan, voter_id, driving_licence)."
    )
    detected_document_type: Optional[str] = Field(
        default=None,
        description="Document type visually or textually inferred by the extractor."
    )
    extracted_fields: Dict[str, Any] = Field(
        default_factory=dict,
        description="Dictionary of structured key-value pairs extracted from document."
    )
    raw_text: Optional[str] = Field(
        default=None,
        max_length=50000,
        description="Bounded raw OCR text output. Max 50,000 characters to prevent memory exhaustion."
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Overall extraction confidence score strictly bounded between 0.0 and 1.0."
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Any warnings or extraction anomalies encountered."
    )

    @field_validator("raw_text", mode="before")
    @classmethod
    def truncate_or_bound_raw_text(cls, v: Any) -> Optional[str]:
        if isinstance(v, str) and len(v) > 50000:
            return v[:50000]
        return v


class DocumentVerificationResult(BaseModel):
    """
    Strict contract representing the verification state of a document,
    integrating multi-tier cryptographic, registry, and supporting visual evidence.
    """
    status: DocumentVerificationStatus = Field(
        default=DocumentVerificationStatus.PENDING,
        description="Explicit verification state."
    )
    is_authentic: bool = Field(
        default=False,
        description="True ONLY if verified through cryptographic or official issuer/registry evidence."
    )
    methods: List[str] = Field(
        default_factory=list,
        description="Evidence methods used during verification."
    )
    issuer: Optional[str] = Field(
        default=None,
        description="Recognized issuing authority (e.g. UIDAI, Income Tax Department, etc.)."
    )
    certificate_number: Optional[str] = Field(
        default=None,
        description="Redacted document / certificate identifier."
    )
    verified_at: Optional[str] = Field(
        default=None,
        description="ISO timestamp of verification evaluation."
    )
    risk_flags: List[str] = Field(
        default_factory=list,
        description="Tamper or anomaly risk flags identified during analysis."
    )
    checks_passed: List[str] = Field(
        default_factory=list,
        description="List of verification check identifiers that passed."
    )
    checks_failed: List[str] = Field(
        default_factory=list,
        description="List of verification check identifiers that failed."
    )
    redacted_fields: Dict[str, str] = Field(
        default_factory=dict,
        description="Fields safe for citizen or UI presentation with sensitive PII masked."
    )
    failure_reason: Optional[str] = Field(
        default=None,
        description="Reason for rejection or escalation to manual review."
    )
    details: Dict[str, Any] = Field(
        default_factory=dict,
        description="Granular evaluation details for officer review."
    )
