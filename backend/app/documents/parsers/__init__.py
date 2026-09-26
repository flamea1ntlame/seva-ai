"""
SEVA AI - Document Parsers Package

Exports specialized parsers for Aadhaar, PAN, Driving Licence,
and generic document types.
"""

from typing import Dict, Type
from app.documents.parsers.base import BaseDocumentParser, DocumentParserResult, ExtractedField
from app.documents.parsers.aadhaar import AadhaarParser
from app.documents.parsers.pan import PANParser
from app.documents.parsers.driving_license import DrivingLicenseParser
from app.documents.parsers.generic import GenericDocumentParser

PARSER_REGISTRY: Dict[str, Type[BaseDocumentParser]] = {
    "identity_proof": AadhaarParser,
    "aadhaar": AadhaarParser,
    "aadhaar_card": AadhaarParser,
    "parent_identity_proof": AadhaarParser,
    "pan": PANParser,
    "pan_card": PANParser,
    "driving_license": DrivingLicenseParser,
    "driving_licence": DrivingLicenseParser,
    "dl": DrivingLicenseParser,
}


def get_parser_for_document_type(document_type: str) -> BaseDocumentParser:
    """
    Returns the appropriate document parser for the given document type.
    """
    norm_type = (document_type or "").lower().strip()
    parser_cls = PARSER_REGISTRY.get(norm_type)
    if parser_cls:
        return parser_cls()
    return GenericDocumentParser(norm_type)


__all__ = [
    "BaseDocumentParser",
    "DocumentParserResult",
    "ExtractedField",
    "AadhaarParser",
    "PANParser",
    "DrivingLicenseParser",
    "GenericDocumentParser",
    "get_parser_for_document_type",
]
