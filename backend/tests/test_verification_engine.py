import pytest
import os
import hashlib
from app.documents.schemas import ExtractionResult, DocumentVerificationStatus
from app.documents.verification.engine import DocumentVerificationEngine
from app.documents.verification.classifier import classify_document
from app.documents.verification.algorithms.verhoeff import validate_verhoeff, generate_verhoeff


# ---------------------------------------------------------------------------
# 1. Verhoeff Dihedral D5 Checksum Tests
# ---------------------------------------------------------------------------

def test_verhoeff_checksum_valid():
    # Aadhaar format test
    assert validate_verhoeff("883920491122") is True
    assert validate_verhoeff("234567890120") is False

    # Checksum generation and validation loop
    base_num = "12345678901"
    with_checksum = generate_verhoeff(base_num)
    assert validate_verhoeff(with_checksum) is True


def test_verhoeff_single_digit_mutation():
    valid = "883920491122"
    assert validate_verhoeff(valid) is True
    # Mutating any single digit must be detected
    for i in range(len(valid)):
        for d in "0123456789":
            if d != valid[i]:
                mutated = valid[:i] + d + valid[i+1:]
                assert validate_verhoeff(mutated) is False


def test_verhoeff_adjacent_transposition():
    valid = "883920491122"
    # Swapping adjacent digits
    for i in range(len(valid) - 1):
        if valid[i] != valid[i+1]:
            transposed = valid[:i] + valid[i+1] + valid[i] + valid[i+2:]
            assert validate_verhoeff(transposed) is False


# ---------------------------------------------------------------------------
# 2. Document Classification Tests
# ---------------------------------------------------------------------------

def test_classification_aadhaar():
    detected, conf, flags = classify_document(
        declared_type="identity_proof",
        extracted_fields={"id_number": "883920491122"},
        raw_text="GOVERNMENT OF INDIA UNIQUE IDENTIFICATION AUTHORITY OF INDIA MERA AADHAAR"
    )
    assert detected == "aadhaar"
    assert conf >= 0.70


def test_classification_pan():
    detected, conf, flags = classify_document(
        declared_type="income_proof",
        extracted_fields={"pan_number": "ABCDE1234F"},
        raw_text="INCOME TAX DEPARTMENT PERMANENT ACCOUNT NUMBER CARD"
    )
    assert detected == "pan"
    assert conf >= 0.70


def test_classification_voter_id():
    detected, conf, flags = classify_document(
        declared_type="identity_proof",
        extracted_fields={"epic_number": "WBF1234567"},
        raw_text="ELECTION COMMISSION OF INDIA ELECTOR PHOTO IDENTITY CARD"
    )
    assert detected == "voter_id"


def test_classification_driving_licence():
    detected, conf, flags = classify_document(
        declared_type="driving_licence",
        extracted_fields={"dl_number": "DL0120190001234"},
        raw_text="TRANSPORT DEPARTMENT UNION OF INDIA DRIVING LICENCE"
    )
    assert detected == "driving_licence"


def test_classification_unknown():
    detected, conf, flags = classify_document(
        declared_type="random_certificate",
        extracted_fields={"content": "some text"},
        raw_text="This is an informal letter without government markings."
    )
    assert detected == "unknown"
    assert "UNKNOWN_DOCUMENT_TYPE" in flags


# ---------------------------------------------------------------------------
# 3. Document Identifier & Engine Verification Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_aadhaar_valid_format_needs_review():
    engine = DocumentVerificationEngine()
    extraction = ExtractionResult(
        document_type="aadhaar",
        extracted_fields={"name": "Rahul Kumar", "id_number": "883920491122"},
        raw_text="GOVERNMENT OF INDIA AADHAAR 8839 2049 1122"
    )
    res = await engine.verify(extraction)

    # Format & Verhoeff valid, but supporting evidence alone MUST NOT be VERIFIED!
    assert res.status == DocumentVerificationStatus.NEEDS_REVIEW
    assert res.is_authentic is False
    assert "aadhaar_verhoeff_checksum" in res.checks_passed
    assert res.redacted_fields["id_number"] == "XXXXXXXX1122"
    assert "883920491122" not in res.redacted_fields.values()


@pytest.mark.asyncio
async def test_aadhaar_verhoeff_checksum_failure_rejected():
    engine = DocumentVerificationEngine()
    # 883920491123 has bad Verhoeff checksum digit
    extraction = ExtractionResult(
        document_type="aadhaar",
        extracted_fields={"name": "Rahul Kumar", "id_number": "883920491123"},
        raw_text="GOVERNMENT OF INDIA AADHAAR 8839 2049 1123"
    )
    res = await engine.verify(extraction)
    assert res.status == DocumentVerificationStatus.REJECTED
    assert res.is_authentic is False
    assert "aadhaar_verhoeff_checksum" in res.checks_failed
    assert "VERHOEFF_CHECKSUM_FAILED" in res.risk_flags


@pytest.mark.asyncio
async def test_pan_valid_format_needs_review():
    engine = DocumentVerificationEngine()
    extraction = ExtractionResult(
        document_type="pan",
        extracted_fields={"name": "Rahul Sharma", "id_number": "ABCPS1234F"},
        raw_text="INCOME TAX DEPARTMENT GOVT OF INDIA PAN ABCPS1234F"
    )
    res = await engine.verify(extraction)
    assert res.status == DocumentVerificationStatus.NEEDS_REVIEW
    assert res.is_authentic is False
    assert "pan_format_regex" in res.checks_passed
    assert "pan_entity_type_valid" in res.checks_passed
    assert res.redacted_fields["id_number"] == "XXXXX1234F"


@pytest.mark.asyncio
async def test_pan_invalid_format_rejected():
    engine = DocumentVerificationEngine()
    # Invalid 4th character ('Z' is not a valid entity)
    extraction = ExtractionResult(
        document_type="pan",
        extracted_fields={"name": "Rahul Sharma", "id_number": "ABCZS1234F"},
        raw_text="INCOME TAX DEPARTMENT PAN ABCZS1234F"
    )
    res = await engine.verify(extraction)
    assert res.status == DocumentVerificationStatus.REJECTED
    assert "pan_entity_type_valid" in res.checks_failed


@pytest.mark.asyncio
async def test_voter_id_valid_and_invalid():
    engine = DocumentVerificationEngine()
    # Valid EPIC: 3 letters + 7 numbers
    valid_extraction = ExtractionResult(
        document_type="voter_id",
        extracted_fields={"id_number": "WBF1234567", "name": "Voter Name"},
        raw_text="ELECTION COMMISSION OF INDIA WBF1234567"
    )
    res_valid = await engine.verify(valid_extraction)
    assert res_valid.status == DocumentVerificationStatus.NEEDS_REVIEW
    assert "voter_id_format_valid" in res_valid.checks_passed
    assert res_valid.redacted_fields["id_number"] == "WBF****567"

    # Malformed EPIC
    invalid_extraction = ExtractionResult(
        document_type="voter_id",
        extracted_fields={"id_number": "123INVALID"},
        raw_text="VOTER CARD"
    )
    res_invalid = await engine.verify(invalid_extraction)
    assert res_invalid.status == DocumentVerificationStatus.REJECTED


@pytest.mark.asyncio
async def test_driving_licence_valid_and_invalid():
    engine = DocumentVerificationEngine()
    # Valid DL format: KA01-2018-0001234
    valid_extraction = ExtractionResult(
        document_type="driving_licence",
        extracted_fields={"id_number": "KA0120180001234", "name": "Driver Name"},
        raw_text="UNION OF INDIA DRIVING LICENCE KA0120180001234"
    )
    res_valid = await engine.verify(valid_extraction)
    assert res_valid.status == DocumentVerificationStatus.NEEDS_REVIEW
    assert "dl_format_regex" in res_valid.checks_passed
    assert "dl_state_code_valid" in res_valid.checks_passed

    # Invalid State code (ZZ)
    invalid_extraction = ExtractionResult(
        document_type="driving_licence",
        extracted_fields={"id_number": "ZZ0120180001234"},
        raw_text="DRIVING LICENCE ZZ0120180001234"
    )
    res_invalid = await engine.verify(invalid_extraction)
    assert res_invalid.status == DocumentVerificationStatus.REJECTED
    assert "dl_state_code_valid" in res_invalid.checks_failed


@pytest.mark.asyncio
async def test_unsupported_document_type():
    engine = DocumentVerificationEngine()
    extraction = ExtractionResult(
        document_type="gym_membership",
        extracted_fields={"id_number": "GYM-99"},
        raw_text="Local Fitness Club"
    )
    res = await engine.verify(extraction)
    assert res.status == DocumentVerificationStatus.NOT_VERIFIABLE
    assert "UNSUPPORTED_DOCUMENT_TYPE" in res.risk_flags


@pytest.mark.asyncio
async def test_ocr_only_evidence_never_verified():
    """
    CRITICAL HARD REQUIREMENT:
    OCR/Visual extraction alone MUST NEVER produce status VERIFIED.
    """
    engine = DocumentVerificationEngine()
    for doc_type, sample_id in [
        ("aadhaar", "883920491122"),
        ("pan", "ABCPE1234F"),
        ("voter_id", "WBF1234567"),
        ("driving_licence", "DL0420190001234")
    ]:
        extraction = ExtractionResult(
            document_type=doc_type,
            extracted_fields={"id_number": sample_id, "name": "Citizen User"},
            raw_text=f"Official {doc_type} text with valid number {sample_id}"
        )
        res = await engine.verify(extraction)
        assert res.status != DocumentVerificationStatus.VERIFIED
        assert res.is_authentic is False
        assert res.status == DocumentVerificationStatus.NEEDS_REVIEW
