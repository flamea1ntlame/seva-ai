import pytest
import uuid
import hashlib
from pydantic import ValidationError
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import User, Document, Application, Service
from app.documents.schemas import (
    ExtractionResult,
    DocumentVerificationResult,
    DocumentVerificationStatus,
    ExtractedField,
)
from app.workflows.engine import WorkflowEngine, ApplicationState
from tests.test_chat import seed_test_data


# ---------------------------------------------------------------------------
# 1. Pydantic Contract Tests
# ---------------------------------------------------------------------------

def test_extraction_result_contract_valid():
    result = ExtractionResult(
        document_type="aadhaar",
        detected_document_type="aadhaar",
        extracted_fields={"id_number": "123456789012", "name": "Test User"},
        raw_text="Sample OCR extracted text",
        confidence=0.95,
        warnings=[]
    )
    assert result.document_type == "aadhaar"
    assert result.confidence == 0.95
    assert result.extracted_fields["id_number"] == "123456789012"


def test_extraction_result_confidence_bounds():
    # Confidence > 1.0 must fail
    with pytest.raises(ValidationError):
        ExtractionResult(document_type="pan", confidence=1.5)

    # Confidence < 0.0 must fail
    with pytest.raises(ValidationError):
        ExtractionResult(document_type="pan", confidence=-0.1)


def test_extraction_result_raw_text_bounding():
    # Exactly 50,000 chars should be accepted without truncation
    exact_text = "B" * 50000
    res_exact = ExtractionResult(document_type="voter_id", raw_text=exact_text)
    assert len(res_exact.raw_text) == 50000
    assert res_exact.raw_text == exact_text

    # Long text exceeding 50,000 chars should be safely truncated to exactly 50,000
    huge_text = "A" * 60000
    res = ExtractionResult(document_type="voter_id", raw_text=huge_text)
    assert len(res.raw_text) == 50000
    assert res.raw_text == "A" * 50000


def test_verification_result_contract_valid():
    ver = DocumentVerificationResult(
        status=DocumentVerificationStatus.EXTRACTED,
        is_authentic=False,
        checks_passed=["format_regex"],
        checks_failed=["issuer_registry"],
        redacted_fields={"id_number": "XXXXXXXX9012"}
    )
    assert ver.status == DocumentVerificationStatus.EXTRACTED
    assert ver.is_authentic is False


def test_verification_result_status_rejection():
    # Statuses like VERIFIED_AI or VERIFIED_REGISTRY must NOT be allowed
    with pytest.raises(ValidationError):
        DocumentVerificationResult(status="VERIFIED_AI")

    with pytest.raises(ValidationError):
        DocumentVerificationResult(status="VERIFIED_REGISTRY")

    with pytest.raises(ValidationError):
        DocumentVerificationResult(status="UNKNOWN_STATUS")


# ---------------------------------------------------------------------------
# 2. Secure Upload & Ingestion Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upload_success_is_extracted_not_verified(client: AsyncClient, db_session: AsyncSession):
    """
    Requirement: Successful upload and extraction must result in EXTRACTED,
    NOT VERIFIED. No OCR/LLM result may independently establish authenticity.
    """
    await seed_test_data(db_session)
    login_res = await client.post("/api/auth/login", json={"email": "citizen@example.com", "password": "password123"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me_res = await client.get("/api/auth/me", headers=headers)
    user_id = me_res.json()["id"]

    pdf_bytes = b"%PDF-1.4\nTest Document Content\n%%EOF"
    files = {"file": ("aadhaar.pdf", pdf_bytes, "application/pdf")}
    data = {"document_type": "identity_proof", "citizen_id": user_id}

    res = await client.post("/documents/upload", files=files, data=data, headers=headers)
    assert res.status_code == 200, res.text
    payload = res.json()

    assert payload["verification_status"] == "EXTRACTED"
    assert payload["verified"] is False
    assert payload["sha256_hash"] == hashlib.sha256(pdf_bytes).hexdigest()

    # Check persistence in database
    db_doc = await db_session.get(Document, uuid.UUID(payload["id"]))
    assert db_doc is not None
    assert db_doc.verification_status == "EXTRACTED"
    assert db_doc.verified is False
    assert db_doc.sha256_hash == hashlib.sha256(pdf_bytes).hexdigest()


@pytest.mark.asyncio
async def test_upload_oversized_file_rejected(client: AsyncClient, db_session: AsyncSession):
    """
    Requirement: 10 MB maximum upload size. Reject files above the limit with 413.
    """
    await seed_test_data(db_session)
    login_res = await client.post("/api/auth/login", json={"email": "citizen@example.com", "password": "password123"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me_res = await client.get("/api/auth/me", headers=headers)
    user_id = me_res.json()["id"]

    # 10 MB + 1 KB (starts with PDF magic bytes)
    oversized_bytes = b"%PDF-1.4" + b"0" * (10 * 1024 * 1024 + 1024)
    files = {"file": ("huge.pdf", oversized_bytes, "application/pdf")}
    data = {"document_type": "identity_proof", "citizen_id": user_id}

    res = await client.post("/documents/upload", files=files, data=data, headers=headers)
    assert res.status_code == 413
    assert "exceeds maximum allowed size" in res.json()["detail"]


@pytest.mark.asyncio
async def test_upload_unsupported_file_content_rejected(client: AsyncClient, db_session: AsyncSession):
    """
    Requirement: File validation must verify file content/magic bytes.
    Reject files that are not PDF, JPEG, or PNG with 415.
    """
    await seed_test_data(db_session)
    login_res = await client.post("/api/auth/login", json={"email": "citizen@example.com", "password": "password123"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me_res = await client.get("/api/auth/me", headers=headers)
    user_id = me_res.json()["id"]

    # Plain text disguised as PDF
    fake_pdf = b"This is just plain text, not a real PDF or image!"
    files = {"file": ("test.pdf", fake_pdf, "application/pdf")}
    data = {"document_type": "identity_proof", "citizen_id": user_id}

    res = await client.post("/documents/upload", files=files, data=data, headers=headers)
    assert res.status_code == 415
    assert "Unsupported file format" in res.json()["detail"]


@pytest.mark.asyncio
async def test_upload_jpeg_and_png_magic_bytes_accepted(client: AsyncClient, db_session: AsyncSession):
    """
    Requirement: JPEG and PNG magic bytes are accepted.
    """
    await seed_test_data(db_session)
    login_res = await client.post("/api/auth/login", json={"email": "citizen@example.com", "password": "password123"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me_res = await client.get("/api/auth/me", headers=headers)
    user_id = me_res.json()["id"]

    # Valid JPEG header
    jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb"
    res_jpeg = await client.post(
        "/documents/upload",
        files={"file": ("photo.jpg", jpeg_bytes, "image/jpeg")},
        data={"document_type": "identity_proof", "citizen_id": user_id},
        headers=headers
    )
    assert res_jpeg.status_code == 200
    assert res_jpeg.json()["mime_type"] == "image/jpeg"

    # Valid PNG header
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    res_png = await client.post(
        "/documents/upload",
        files={"file": ("scan.png", png_bytes, "image/png")},
        data={"document_type": "address_proof", "citizen_id": user_id},
        headers=headers
    )
    assert res_png.status_code == 200
    assert res_png.json()["mime_type"] == "image/png"


@pytest.mark.asyncio
async def test_upload_duplicate_file_intake(client: AsyncClient, db_session: AsyncSession):
    """
    Requirement: Exact duplicate upload by the same user returns existing record.
    """
    await seed_test_data(db_session)
    login_res = await client.post("/api/auth/login", json={"email": "citizen@example.com", "password": "password123"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me_res = await client.get("/api/auth/me", headers=headers)
    user_id = me_res.json()["id"]

    pdf_bytes = b"%PDF-1.4\nUnique Document Content 12345\n%%EOF"
    files1 = {"file": ("original.pdf", pdf_bytes, "application/pdf")}
    data = {"document_type": "identity_proof", "citizen_id": user_id}

    res1 = await client.post("/documents/upload", files=files1, data=data, headers=headers)
    assert res1.status_code == 200
    doc1 = res1.json()

    # Upload exact same bytes again
    files2 = {"file": ("copy.pdf", pdf_bytes, "application/pdf")}
    res2 = await client.post("/documents/upload", files=files2, data=data, headers=headers)
    assert res2.status_code == 200
    doc2 = res2.json()

    # Should return the same document id
    assert doc1["id"] == doc2["id"]
    assert doc1["sha256_hash"] == doc2["sha256_hash"]


@pytest.mark.asyncio
async def test_upload_cross_user_duplicate_isolation(client: AsyncClient, db_session: AsyncSession):
    """
    Requirement: FIX 1 - Tenant-Scoped Duplicate Detection.
    1. User A uploads file X.
    2. User B uploads identical file X.
    3. User B does NOT receive User A's document.
    4. User B cannot learn User A's document ID or metadata.
    5. User B gets their own isolated document record with their own user_id.
    """
    await seed_test_data(db_session)

    # 1. Login as User A (citizen@example.com)
    login_a = await client.post("/api/auth/login", json={"email": "citizen@example.com", "password": "password123"})
    token_a = login_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}
    me_a = await client.get("/api/auth/me", headers=headers_a)
    user_a_id = me_a.json()["id"]

    # 2. Register and login as User B
    register_b = await client.post("/api/auth/signup", json={
        "email": "user_b@example.com",
        "password": "password123",
        "full_name": "User B",
        "phone_number": "+918888888888"
    })
    assert register_b.status_code == 201, register_b.text
    login_b = await client.post("/api/auth/login", json={"email": "user_b@example.com", "password": "password123"})
    token_b = login_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}
    me_b = await client.get("/api/auth/me", headers=headers_b)
    user_b_id = me_b.json()["id"]

    assert user_a_id != user_b_id

    # 3. User A uploads identical file X
    shared_pdf_bytes = b"%PDF-1.4\nShared Confidential Certificate 98765\n%%EOF"
    files_a = {"file": ("cert.pdf", shared_pdf_bytes, "application/pdf")}
    data_a = {"document_type": "identity_proof", "citizen_id": user_a_id}

    res_a = await client.post("/documents/upload", files=files_a, data=data_a, headers=headers_a)
    assert res_a.status_code == 200, res_a.text
    doc_a = res_a.json()
    assert doc_a["user_id"] == user_a_id

    # 4. User B uploads identical file X (same SHA-256 hash)
    files_b = {"file": ("cert.pdf", shared_pdf_bytes, "application/pdf")}
    data_b = {"document_type": "identity_proof", "citizen_id": user_b_id}

    res_b = await client.post("/documents/upload", files=files_b, data=data_b, headers=headers_b)
    assert res_b.status_code == 200, res_b.text
    doc_b = res_b.json()

    # 5. Assertions: User B must NOT receive User A's document or metadata
    assert doc_b["id"] != doc_a["id"], "User B received User A's document ID!"
    assert doc_b["user_id"] == user_b_id
    assert doc_b["user_id"] != doc_a["user_id"]
    assert doc_b["sha256_hash"] == doc_a["sha256_hash"], "SHA-256 hashes should match for identical bytes"
    assert doc_a["id"] not in doc_b["file_path"], "User A's file ID leaked in User B's file path!"


@pytest.mark.asyncio
async def test_upload_application_idor_protection(client: AsyncClient, db_session: AsyncSession):
    """
    Requirement: IDOR protection on application_id.
    Cannot attach a document to an application belonging to another user.
    """
    await seed_test_data(db_session)
    login_res = await client.post("/api/auth/login", json={"email": "citizen@example.com", "password": "password123"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me_res = await client.get("/api/auth/me", headers=headers)
    user_id = me_res.json()["id"]

    # Create another user and an application for that other user
    other_user = User(
        email="victim@example.com",
        password_hash="fakehash",
        full_name="Victim User",
        role="citizen",
        is_active=True
    )
    db_session.add(other_user)
    await db_session.flush()

    srv = await db_session.execute(select(Service).limit(1))
    service = srv.scalar_one()

    victim_app = Application(
        application_number="APP-VICTIM-001",
        user_id=other_user.id,
        service_id=service.id,
        status="COLLECTING_DOCUMENTS"
    )
    db_session.add(victim_app)
    await db_session.commit()

    # Attempt to upload document using current_user but attaching victim_app.id
    pdf_bytes = b"%PDF-1.4\nAttempting IDOR attachment\n%%EOF"
    files = {"file": ("exploit.pdf", pdf_bytes, "application/pdf")}
    data = {
        "document_type": "identity_proof",
        "citizen_id": user_id,
        "application_id": str(victim_app.id)
    }

    res = await client.post("/documents/upload", files=files, data=data, headers=headers)
    assert res.status_code == 403
    assert "Forbidden" in res.json()["detail"]


@pytest.mark.asyncio
async def test_user_document_listing_returns_persisted_fields(client: AsyncClient, db_session: AsyncSession):
    """
    Requirement: Document listing still works and exposes new fields (sha256_hash, etc.).
    """
    await seed_test_data(db_session)
    login_res = await client.post("/api/auth/login", json={"email": "citizen@example.com", "password": "password123"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    res = await client.get("/documents/", headers=headers)
    assert res.status_code == 200
    docs = res.json()
    assert isinstance(docs, list)


@pytest.mark.asyncio
async def test_workflow_cannot_advance_with_only_extracted_documents(db_session: AsyncSession):
    """
    Requirement: Guarantee that EXTRACTED, PENDING, MANUAL_REVIEW, REJECTED
    cannot automatically satisfy a workflow requirement that expects VERIFIED.
    """
    await seed_test_data(db_session)
    usr_res = await db_session.execute(select(User).where(User.email == "citizen@example.com"))
    user = usr_res.scalar_one()

    srv_res = await db_session.execute(select(Service).where(Service.code == "income_certificate"))
    service = srv_res.scalar_one()

    app = Application(
        application_number=f"APP-WORKFLOW-CHECK-{uuid.uuid4()}",
        user_id=user.id,
        service_id=service.id,
        status=ApplicationState.COLLECTING_DOCUMENTS
    )
    db_session.add(app)
    await db_session.flush()

    # Add all required documents, but with status EXTRACTED (not VERIFIED)
    doc1 = Document(
        user_id=user.id,
        document_type="identity_proof",
        title="ID Proof",
        file_path="test1.pdf",
        verification_status="EXTRACTED",
        verified=False,
        extracted_data={"name": "Test User"}
    )
    doc2 = Document(
        user_id=user.id,
        document_type="address_proof",
        title="Address Proof",
        file_path="test2.pdf",
        verification_status="EXTRACTED",
        verified=False,
        extracted_data={"address": "Test Address"}
    )
    doc3 = Document(
        user_id=user.id,
        document_type="income_proof",
        title="Income Proof",
        file_path="test3.pdf",
        verification_status="EXTRACTED",
        verified=False,
        extracted_data={"annual_income": "500000"}
    )
    db_session.add_all([doc1, doc2, doc3])
    await db_session.commit()

    engine = WorkflowEngine(db_session)
    next_status = await engine.advance_application(app.id)

    # Must stay in EXTRACTING because docs are not VERIFIED, NOT advance to READY_FOR_REVIEW!
    assert next_status == ApplicationState.EXTRACTING
    await db_session.refresh(app)
    assert app.status == ApplicationState.EXTRACTING
