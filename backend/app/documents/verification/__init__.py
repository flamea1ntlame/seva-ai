# Verification package exports
from app.documents.verification.engine import DocumentVerificationEngine
from app.documents.verification.classifier import classify_document, canonicalize_document_type
from app.documents.verification.algorithms.verhoeff import validate_verhoeff, generate_verhoeff

__all__ = [
    "DocumentVerificationEngine",
    "classify_document",
    "canonicalize_document_type",
    "validate_verhoeff",
    "generate_verhoeff"
]
