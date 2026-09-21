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
    assert doc_data["verification_status"] == "VERIFIED"
    assert doc_data["extracted_data"]["name"] == "Rahul Kumar"
    assert doc_data["extracted_data"]["id_number"] == "AADHAAR-8839-2049-1122"

    # 2. Test tool_get_citizen_profile
    profile = await tool_get_citizen_profile(db_session, user_id)
    assert "Rahul Kumar" in profile["merged_profile"].values()
    assert "identity_proof" in profile["uploaded_document_types"]

    # 3. Test Chat Agent reasoning with extracted profile
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
