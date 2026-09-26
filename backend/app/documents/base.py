from abc import ABC, abstractmethod
from typing import Optional
from app.documents.schemas import ExtractionResult


class BaseDocumentExtractor(ABC):
    """
    Abstract interface for document extraction engines.
    Charitha's future OCR/AI/Vision implementation will subclass this extractor
    without modifying router security, database persistence, or verification layers.
    """

    @abstractmethod
    async def extract(
        self,
        file_bytes: bytes,
        mime_type: str,
        document_type: str,
        filename: Optional[str] = None
    ) -> ExtractionResult:
        """
        Extract structured fields and metadata from document raw bytes.

        :param file_bytes: In-memory raw bytes of the uploaded file.
        :param mime_type: Verified MIME type (e.g. application/pdf, image/jpeg, image/png).
        :param document_type: Declared document category/type from user.
        :param filename: Optional sanitized original filename.
        :return: Standardized ExtractionResult contract.
        """
        pass
