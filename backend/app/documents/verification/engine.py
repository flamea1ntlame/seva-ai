from typing import Optional, Dict, Any, List
from datetime import datetime

from app.documents.schemas import (
    ExtractionResult,
    DocumentVerificationResult,
    DocumentVerificationStatus,
    VerificationMethod,
)
from app.documents.verification.classifier import classify_document, canonicalize_document_type
from app.documents.verification.validators.base import BaseDocumentValidator, ValidationOutcome
from app.documents.verification.validators.aadhaar import AadhaarValidator
from app.documents.verification.validators.pan import PanValidator
from app.documents.verification.validators.voter_id import VoterIdValidator
from app.documents.verification.validators.driving_licence import DrivingLicenceValidator
from app.documents.verification.qr_analyzer import analyze_qr_barcode
from app.documents.verification.signature import verify_digital_signature
from app.documents.verification.issuer_adapter import DefaultGovernmentIssuerAdapter
from app.documents.verification.digilocker_adapter import DigiLockerAdapter
from app.documents.verification.registry_adapter import GovernmentRegistryAdapter


class DocumentVerificationEngine:
    """
    Central Verification Decision Engine for Government Documents.
    Enforces Evidence Hierarchy:
    STRONG: Cryptographic signature, live issuer verification, live registry match, DigiLocker XML.
    SUPPORTING: QR/barcode consistency, OCR format validation, classification, checksums.
    RULE: Supporting evidence alone NEVER produces VERIFIED.
    """

    def __init__(self, registry_adapter: Optional[GovernmentRegistryAdapter] = None):
        self._validators: Dict[str, BaseDocumentValidator] = {
            "aadhaar": AadhaarValidator(),
            "pan": PanValidator(),
            "voter_id": VoterIdValidator(),
            "driving_licence": DrivingLicenceValidator(),
        }
        self.issuer_adapter = DefaultGovernmentIssuerAdapter()
        self.digilocker_adapter = DigiLockerAdapter()
        self.registry_adapter = registry_adapter or GovernmentRegistryAdapter()

    async def verify(
        self,
        extraction: ExtractionResult,
        file_path: Optional[str] = None,
        sha256_hash: Optional[str] = None,
        external_digilocker_uri: Optional[str] = None
    ) -> DocumentVerificationResult:
        timestamp = datetime.utcnow().isoformat() + "Z"
        methods: List[str] = []
        checks_passed: List[str] = []
        checks_failed: List[str] = []
        risk_flags: List[str] = []
        redacted_fields: Dict[str, str] = {}
        failure_reasons: List[str] = []

        # 1. Document Classification
        detected_type, class_conf, class_flags = classify_document(
            declared_type=extraction.document_type,
            extracted_fields=extraction.extracted_fields,
            raw_text=extraction.raw_text
        )
        methods.append(VerificationMethod.VISUAL_ANALYSIS.value)
        risk_flags.extend(class_flags)

        # Normalize canonical type
        effective_type = detected_type if detected_type in self._validators else canonicalize_document_type(extraction.document_type)

        if effective_type not in self._validators:
            checks_failed.append("unsupported_government_document_type")
            risk_flags.append("UNSUPPORTED_DOCUMENT_TYPE")
            return DocumentVerificationResult(
                status=DocumentVerificationStatus.NOT_VERIFIABLE,
                is_authentic=False,
                methods=methods,
                verified_at=timestamp,
                checks_passed=checks_passed,
                checks_failed=checks_failed,
                risk_flags=risk_flags,
                failure_reason=f"Document type '{extraction.document_type}' is not a supported mandatory government identity document."
            )

        validator = self._validators[effective_type]
        issuer_name = validator.issuer_name

        # 2. Identifier & Format Validation
        methods.append(VerificationMethod.FORMAT_CHECKSUM.value)
        val_outcome: ValidationOutcome = validator.validate(
            extracted_fields=extraction.extracted_fields,
            raw_text=extraction.raw_text
        )

        checks_passed.extend(val_outcome.checks_passed)
        checks_failed.extend(val_outcome.checks_failed)
        risk_flags.extend(val_outcome.risk_flags)
        redacted_fields.update(val_outcome.redacted_fields)
        if val_outcome.failure_reason:
            failure_reasons.append(val_outcome.failure_reason)

        clean_identifier = val_outcome.clean_identifier

        # If deterministic validation failed (e.g. Verhoeff checksum failure, invalid PAN regex)
        if not val_outcome.is_valid:
            return DocumentVerificationResult(
                status=DocumentVerificationStatus.REJECTED,
                is_authentic=False,
                methods=methods,
                issuer=issuer_name,
                certificate_number=clean_identifier,
                verified_at=timestamp,
                checks_passed=checks_passed,
                checks_failed=checks_failed,
                risk_flags=risk_flags,
                redacted_fields=redacted_fields,
                failure_reason="; ".join(failure_reasons)
            )

        # 3. QR / Barcode Analysis (Supporting evidence)
        qr_matched = False
        if file_path:
            qr_res = analyze_qr_barcode(file_path, extracted_identifier=clean_identifier)
            if qr_res.qr_detected or qr_res.barcode_detected:
                methods.append(VerificationMethod.QR_ANALYSIS.value)
                checks_passed.extend(qr_res.checks_passed)
                checks_failed.extend(qr_res.checks_failed)
                risk_flags.extend(qr_res.risk_flags)
                if "qr_identifier_cross_check_matched" in qr_res.checks_passed:
                    qr_matched = True

        # 4. Digital Signature Analysis (Strong evidence candidate)
        sig_valid = False
        if file_path:
            sig_res = verify_digital_signature(file_path)
            if sig_res.has_signature:
                methods.append(VerificationMethod.DIGITAL_SIGNATURE.value)
                checks_passed.extend(sig_res.checks_passed)
                checks_failed.extend(sig_res.checks_failed)
                risk_flags.extend(sig_res.risk_flags)
                if sig_res.is_valid and sig_res.is_verifiable:
                    sig_valid = True

        # 5. Issuer Verification Adapter (Strong evidence candidate)
        issuer_res = await self.issuer_adapter.verify(effective_type, clean_identifier or "")
        methods.append(VerificationMethod.ISSUER_VERIFICATION.value)
        checks_passed.extend(issuer_res.checks_passed)
        checks_failed.extend(issuer_res.checks_failed)
        risk_flags.extend(issuer_res.risk_flags)

        # 6. DigiLocker Verification Adapter (Strong evidence candidate)
        digi_res = await self.digilocker_adapter.verify_uri(external_digilocker_uri, effective_type)
        if external_digilocker_uri:
            methods.append(VerificationMethod.DIGILOCKER.value)
            checks_passed.extend(digi_res.checks_passed)
            checks_failed.extend(digi_res.checks_failed)
            risk_flags.extend(digi_res.risk_flags)

        # 7. Registry Matching Adapter (Strong evidence candidate)
        reg_res = await self.registry_adapter.lookup(
            effective_type,
            clean_identifier or "",
            metadata={"extracted_fields": extraction.extracted_fields, "details": val_outcome.details}
        )
        methods.append(VerificationMethod.REGISTRY_MATCH.value)
        checks_passed.extend(reg_res.checks_passed)
        checks_failed.extend(reg_res.checks_failed)
        risk_flags.extend(reg_res.risk_flags)

        # 8. SHA-256 Hash Integrity Recording
        if sha256_hash:
            checks_passed.append("file_sha256_integrity_recorded")

        # -------------------------------------------------------------
        # 9. EVIDENCE HIERARCHY EVALUATION
        # -------------------------------------------------------------
        # Strong evidence sources:
        has_strong_evidence = (
            sig_valid
            or issuer_res.is_verified
            or reg_res.is_matched
            or digi_res.is_verified
        )

        has_critical_suspicion = any(
            f in risk_flags for f in (
                "QR_IDENTIFIER_MISMATCH",
                "VERHOEFF_CHECKSUM_FAILED",
                "SUSPICIOUS_NUMBER_SEQUENCE",
                "INVALID_PAN_ENTITY_CODE"
            )
        )

        final_status = DocumentVerificationStatus.NEEDS_REVIEW
        is_authentic = False

        if has_critical_suspicion:
            final_status = DocumentVerificationStatus.SUSPICIOUS
            failure_reasons.append("Critical risk flags detected indicating potential tampering or inconsistency.")
        elif has_strong_evidence:
            final_status = DocumentVerificationStatus.VERIFIED
            is_authentic = True
        else:
            # Format/checksum validation passed, but visual/OCR alone CANNOT produce VERIFIED!
            final_status = DocumentVerificationStatus.NEEDS_REVIEW
            failure_reasons.append(
                "Document format and checksum valid, but requires authoritative registry or officer confirmation."
            )

        return DocumentVerificationResult(
            status=final_status,
            is_authentic=is_authentic,
            methods=sorted(list(set(methods))),
            issuer=issuer_name,
            certificate_number=clean_identifier,
            verified_at=timestamp,
            checks_passed=sorted(list(set(checks_passed))),
            checks_failed=sorted(list(set(checks_failed))),
            risk_flags=sorted(list(set(risk_flags))),
            redacted_fields=redacted_fields,
            failure_reason="; ".join(failure_reasons) if failure_reasons else None,
            details={
                "detected_type": detected_type,
                "classification_confidence": class_conf,
                "has_strong_evidence": has_strong_evidence,
                "sha256_hash": sha256_hash,
                "verification_source": reg_res.details.get("source") if reg_res.is_matched else None,
                "registry_details": reg_res.details,
            }
        )
