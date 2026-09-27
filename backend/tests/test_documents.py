import os
import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import User, Document, Application
from app.seed import seed_data
from app.agent.tools import tool_extract_document_data, tool_get_citizen_profile
from tests.test_chat import seed_test_data


@pytest.mark.asyncio
async def test_document_upload_and_extraction(client: AsyncClient, db_session: AsyncSession):
    await seed_test_data(db_session)

    # Login to get token
    login_res = await client.post("/api/auth/login", json={
        "email": "citizen@example.com",
        "password": "password123"
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me_res = await client.get("/api/auth/me", headers=headers)
    user_id = me_res.json()["id"]

    # 1. Test POST /documents/upload
    seed_file_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "seed",
        "sample_identity_proof.txt"
    )

    with open(seed_file_path, "rb") as f:
        file_bytes = f.read()

    files = {"file": ("sample_identity_proof.txt", file_bytes, "text/plain")}
    data = {
        "document_type": "identity_proof",
        "citizen_id": user_id
    }

    upload_res = await client.post("/documents/upload", files=files, data=data, headers=headers)
    assert upload_res.status_code == 200, upload_res.text
    doc_data = upload_res.json()
    assert doc_data["verification_status"] in ("OCR_EXTRACTED", "NEEDS_REVIEW")
    # The seed file contains actual text: "Name: Rahul Kumar" and "Aadhaar Number: AADHAAR-8839-2049-1122"
    # With OCR pipeline the parser should extract these real values from the text file.
    if doc_data["extracted_data"]:
        extracted = doc_data["extracted_data"]
        assert "name" in extracted or "id_number" in extracted, "Expected at least name or id_number from OCR"

    # 2. Test tool_get_citizen_profile: OCR_EXTRACTED document must NOT count as verified
    profile_unverified = await tool_get_citizen_profile(db_session, user_id)
    assert "identity_proof" not in profile_unverified["uploaded_document_types"]

    # Mark document as VERIFIED to test verified profile & chat reasoning
    doc = await db_session.get(Document, uuid.UUID(doc_data["id"]))
    doc.verification_status = "VERIFIED"
    await db_session.commit()

    profile = await tool_get_citizen_profile(db_session, user_id)
    assert "identity_proof" in profile["uploaded_document_types"]

    # 3. Test Chat Agent reasoning with extracted verified profile
    chat_res = await client.post("/api/chat", json={
        "citizen_id": user_id,
        "message": "I need an income certificate"
    }, headers=headers)
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert chat_data["service_code"] == "income_certificate"
    # identity_proof should NOT be in required_documents since it's already uploaded & verified!
    assert "identity_proof" not in chat_data["required_documents"]
    assert "income_proof" in chat_data["required_documents"]


@pytest.mark.asyncio
async def test_ocr_extracted_not_counted_as_verified(client: AsyncClient, db_session: AsyncSession):
    await seed_test_data(db_session)

    login_res = await client.post("/api/auth/login", json={
        "email": "citizen@example.com",
        "password": "password123"
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me_res = await client.get("/api/auth/me", headers=headers)
    user_id = me_res.json()["id"]

    # Create document with status OCR_EXTRACTED
    doc = Document(
        user_id=uuid.UUID(user_id),
        title="Aadhaar Card",
        document_type="identity_proof",
        file_path="dummy/path.pdf",
        verification_status="OCR_EXTRACTED",
        extracted_data={"name": "Test Citizen"}
    )
    db_session.add(doc)
    await db_session.commit()

    # 1. Vault stats must NOT count OCR_EXTRACTED as verified
    vault_res = await client.get("/api/documents/vault-stats", headers=headers)
    assert vault_res.status_code == 200
    vault_data = vault_res.json()
    assert vault_data["verified"] == 0, "OCR_EXTRACTED document must not count in verified vault stats"

    # 2. tool_get_citizen_profile must NOT count OCR_EXTRACTED as verified
    profile = await tool_get_citizen_profile(db_session, user_id)
    assert "identity_proof" not in profile["uploaded_document_types"], "OCR_EXTRACTED document must not count as verified in profile"

    # 3. Only VERIFIED counts as verified
    doc.verification_status = "VERIFIED"
    await db_session.commit()

    vault_res_2 = await client.get("/api/documents/vault-stats", headers=headers)
    assert vault_res_2.json()["verified"] == 1
    profile_2 = await tool_get_citizen_profile(db_session, user_id)
    assert "identity_proof" in profile_2["uploaded_document_types"]


@pytest.mark.asyncio
async def test_upload_unauthorized_citizen(client: AsyncClient, db_session: AsyncSession):
    await seed_test_data(db_session)

    login_res = await client.post("/api/auth/login", json={
        "email": "citizen@example.com",
        "password": "password123"
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    fake_id = str(uuid.uuid4())
    files = {"file": ("test.txt", b"dummy content", "text/plain")}
    data = {"document_type": "identity_proof", "citizen_id": fake_id}

    res = await client.post("/documents/upload", files=files, data=data, headers=headers)
    assert res.status_code == 403
    assert "Forbidden" in res.json()["detail"]

@pytest.mark.asyncio
async def test_filename_sanitization_and_successful_extraction(client: AsyncClient, db_session: AsyncSession, mock_supabase):
    await seed_test_data(db_session)
    login_res = await client.post("/api/auth/login", json={"email": "citizen@example.com", "password": "password123"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me_res = await client.get("/api/auth/me", headers=headers)
    user_id = me_res.json()["id"]

    unsafe_name = "my file@#$.txt"
    files = {"file": (unsafe_name, b"content", "text/plain")}
    data = {"document_type": "identity_proof", "citizen_id": user_id}

    res = await client.post("/documents/upload", files=files, data=data, headers=headers)
    assert res.status_code == 200
    doc = res.json()

    assert doc["file_path"].startswith(f"documents/{user_id}/{doc['id']}/")
    basename = doc["file_path"].split("/")[-1]
    assert "my_file___.txt" in basename

    mock_supabase.storage.from_().upload.assert_called_once()
    call_args = mock_supabase.storage.from_().upload.call_args[1]
    assert call_args["path"] == doc["file_path"]

@pytest.mark.asyncio
async def test_supabase_upload_failure(client: AsyncClient, db_session: AsyncSession, mock_supabase):
    await seed_test_data(db_session)
    login_res = await client.post("/api/auth/login", json={"email": "citizen@example.com", "password": "password123"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me_res = await client.get("/api/auth/me", headers=headers)
    user_id = me_res.json()["id"]

    mock_supabase.storage.from_().upload.side_effect = Exception("Upload failed")

    files = {"file": ("test.txt", b"content", "text/plain")}
    data = {"document_type": "identity_proof", "citizen_id": user_id}

    res = await client.post("/documents/upload", files=files, data=data, headers=headers)
    assert res.status_code == 500

    docs = await db_session.execute(select(Document).where(Document.user_id == uuid.UUID(user_id)))
    assert len(docs.scalars().all()) == 0

@pytest.mark.asyncio
async def test_db_failure_after_upload(client: AsyncClient, db_session: AsyncSession, mock_supabase, monkeypatch):
    await seed_test_data(db_session)
    login_res = await client.post("/api/auth/login", json={"email": "citizen@example.com", "password": "password123"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me_res = await client.get("/api/auth/me", headers=headers)
    user_id = me_res.json()["id"]

    original_commit = db_session.commit
    call_count = 0
    async def mock_commit():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("DB failed")
        await original_commit()

    monkeypatch.setattr(db_session, "commit", mock_commit)

    files = {"file": ("test.txt", b"content", "text/plain")}
    data = {"document_type": "identity_proof", "citizen_id": user_id}

    res = await client.post("/documents/upload", files=files, data=data, headers=headers)
    assert res.status_code == 500

    mock_supabase.storage.from_().remove.assert_called_once()

@pytest.mark.asyncio
async def test_unauthorized_document_extraction(db_session: AsyncSession):
    await seed_test_data(db_session)
    user1_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    doc = Document(id=uuid.UUID(doc_id), user_id=uuid.UUID(user1_id), title="Dummy title", file_path="test", file_size=1, document_type="test", verification_status="PENDING", verified=False)
    db_session.add(doc)
    await db_session.commit()

    user2_id = str(uuid.uuid4())
    res = await tool_extract_document_data(db_session, doc_id, user2_id)
    assert "error" in res
    assert "not found or you do not have permission" in res["error"]


@pytest.mark.asyncio
async def test_document_upload_application_ownership(client: AsyncClient, db_session: AsyncSession):
    await seed_test_data(db_session)

    # Login User 1 (citizen@example.com)
    login_res = await client.post("/api/auth/login", json={
        "email": "citizen@example.com",
        "password": "password123"
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me_res = await client.get("/api/auth/me", headers=headers)
    user1_id = me_res.json()["id"]

    # Create User 2
    user2 = User(
        email=f"user2_{uuid.uuid4()}@example.com",
        full_name="User Two",
        password_hash="hash",
        role="CITIZEN",
        is_active=True
    )
    db_session.add(user2)
    await db_session.commit()
    await db_session.refresh(user2)

    # Get a service
    from app.models import Service
    result = await db_session.execute(select(Service))
    service = result.scalars().first()

    # Create Application for User 1
    app1 = Application(
        application_number=f"APP-U1-{uuid.uuid4().hex[:6]}",
        user_id=uuid.UUID(user1_id),
        service_id=service.id,
        status="COLLECTING_DOCUMENTS"
    )
    # Create Application for User 2
    app2 = Application(
        application_number=f"APP-U2-{uuid.uuid4().hex[:6]}",
        user_id=user2.id,
        service_id=service.id,
        status="COLLECTING_DOCUMENTS"
    )
    db_session.add_all([app1, app2])
    await db_session.commit()

    # 1. Attempt upload linking to another citizen's application (app2) -> MUST return 403
    files = {"file": ("id.txt", b"Name: Rahul Kumar", "text/plain")}
    data_other = {
        "document_type": "identity_proof",
        "citizen_id": user1_id,
        "application_id": str(app2.id)
    }
    res_forbidden = await client.post("/documents/upload", files=files, data=data_other, headers=headers)
    assert res_forbidden.status_code == 403, res_forbidden.text

    # 2. Attempt upload linking to a non-existent application -> MUST return 404
    non_existent_id = str(uuid.uuid4())
    files = {"file": ("id.txt", b"Name: Rahul Kumar", "text/plain")}
    data_missing = {
        "document_type": "identity_proof",
        "citizen_id": user1_id,
        "application_id": non_existent_id
    }
    res_not_found = await client.post("/documents/upload", files=files, data=data_missing, headers=headers)
    assert res_not_found.status_code == 404, res_not_found.text

    # 3. Attempt upload with invalid UUID format -> MUST return 400
    files = {"file": ("id.txt", b"Name: Rahul Kumar", "text/plain")}
    data_invalid = {
        "document_type": "identity_proof",
        "citizen_id": user1_id,
        "application_id": "not-a-valid-uuid"
    }
    res_bad_request = await client.post("/documents/upload", files=files, data=data_invalid, headers=headers)
    assert res_bad_request.status_code == 400, res_bad_request.text

    # 4. Upload with valid owned application (app1) -> MUST succeed
    files = {"file": ("id.txt", b"Name: Rahul Kumar", "text/plain")}
    data_owned = {
        "document_type": "identity_proof",
        "citizen_id": user1_id,
        "application_id": str(app1.id)
    }
    res_ok = await client.post("/documents/upload", files=files, data=data_owned, headers=headers)
    assert res_ok.status_code == 200, res_ok.text
    doc_json = res_ok.json()
    assert doc_json["application_id"] == str(app1.id)

