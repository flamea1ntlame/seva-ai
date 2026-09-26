from typing import Optional, Dict, Any, List
from enum import Enum
from pydantic import BaseModel, Field, field_validator


class DocumentVerificationStatus(str, Enum):
    PENDING = "PENDING"
    EXTRACTED = "EXTRACTED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    MANUAL_REVIEW = "MANUAL_REVIEW"


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
    Strict contract representing the verification state of a document.
    """
    status: DocumentVerificationStatus = Field(
        default=DocumentVerificationStatus.PENDING,
        description="Strict verification status. Allowed: PENDING, EXTRACTED, VERIFIED, REJECTED, MANUAL_REVIEW."
    )
    is_authentic: bool = Field(
        default=False,
        description="True ONLY if verified through cryptographic or official issuer/registry evidence."
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
