from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class ValidationOutcome(BaseModel):
    is_valid: bool
    checks_passed: List[str] = Field(default_factory=list)
    checks_failed: List[str] = Field(default_factory=list)
    risk_flags: List[str] = Field(default_factory=list)
    redacted_fields: Dict[str, str] = Field(default_factory=dict)
    clean_identifier: Optional[str] = None
    failure_reason: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class BaseDocumentValidator(ABC):
    """
    Abstract interface for document-specific deterministic validators.
    """

    @property
    @abstractmethod
    def document_type(self) -> str:
        """The canonical document type this validator handles."""
        pass

    @property
    @abstractmethod
    def issuer_name(self) -> str:
        """The official issuing authority name."""
        pass

    @abstractmethod
    def validate(self, extracted_fields: Dict[str, Any], raw_text: Optional[str] = None) -> ValidationOutcome:
        """
        Executes deterministic identifier, structure, and consistency checks.
        """
        pass
