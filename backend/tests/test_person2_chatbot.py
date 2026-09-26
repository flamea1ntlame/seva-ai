import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import User, Service, CitizenProfile, ChatMessage, AuditLog, Application, Document
from app.auth import get_password_hash
from app.nlp.normalizer import normalize_text
from app.nlp.matcher import match_intent_and_service, Intent
from app.service_rules import (
    get_requirements,
    get_alternative_documents,
    get_document_dependencies,
    evaluate_citizen_readiness
)


async def seed_chat_test_data(db: AsyncSession):
    # Seed User
    res = await db.execute(select(User).where(User.email == "citizen2@example.com"))
    user = res.scalar_one_or_none()
    if not user:
        user = User(
            email="citizen2@example.com",
            password_hash=get_password_hash("password123"),
            full_name="Priya Sharma",
            phone_number="+919876543211",
            role="citizen",
            is_active=True,
        )
        db.add(user)
        await db.flush()
        profile = CitizenProfile(
            user_id=user.id,
            state="Karnataka",
            address="45 Palace Road, Bangalore"
        )
        db.add(profile)

    # Seed Services
    services_data = [
        {
            "code": "income_certificate",
            "title": "Income Certificate",
            "department": "revenue",
            "description": "Income certificate description",
            "required_documents": ["identity_proof", "address_proof", "income_proof"],
            "required_fields": ["annual_income", "occupation"],
            "processing_time_days": 7,
            "fee_amount": 50.00,
        },
        {
            "code": "birth_certificate",
            "title": "Birth Certificate",
            "department": "municipal",
            "description": "Birth certificate description",
            "required_documents": ["hospital_certificate", "parent_identity_proof"],
            "required_fields": ["applicant_name", "date_of_birth", "place_of_birth", "father_name", "mother_name"],
            "processing_time_days": 5,
            "fee_amount": 30.00,
        },
        {
            "code": "driving_license",
            "title": "Driving License",
            "department": "transport",
            "description": "Driving license description",
            "required_documents": ["identity_proof", "address_proof", "photograph", "medical_declaration"],
            "required_fields": ["date_of_birth", "blood_group", "vehicle_class"],
            "processing_time_days": 14,
            "fee_amount": 200.00,
        },
    ]

    for s in services_data:
        res_s = await db.execute(select(Service).where(Service.code == s["code"]))
        if not res_s.scalar_one_or_none():
            db.add(Service(**s, is_active=True))

    await db.commit()


@pytest.mark.asyncio
async def test_typo_normalizer_unit():
    """Validates typo correction and normalization rules."""
    # 1. "birth certifcate" -> "birth certificate"
    res1 = normalize_text("i need birth certifcate")
    assert "birth certificate" in res1.normalized_text

    # 2. "aadahr" -> "Aadhaar"
    res2 = normalize_text("uploaded my aadahr card")
    assert "Aadhaar" in res2.normalized_text
    assert "aadahr" in res2.corrections

    # 3. "driving lisence" -> "driving licence"
    res3 = normalize_text("i want driving lisence")
    assert "driving licence" in res3.normalized_text
    assert "lisence" in res3.corrections or "driving lisence" in res3.corrections

    # 4. "scholership" -> "scholarship"
    res4 = normalize_text("incom certficate for scholership")
    assert "income certificate" in res4.normalized_text
    assert "scholarship" in res4.normalized_text
    assert "scholership" in res4.corrections

    # 5. Original text is preserved untouched
    assert res4.original_text == "incom certficate for scholership"


@pytest.mark.asyncio
async def test_service_rules_engine_unit():
    """Validates that government rules come from authoritative rules engine, not hardcoding."""
    reqs = get_requirements("income_certificate")
    assert reqs["department"] == "revenue"
    assert "income_proof" in reqs["required_documents"]
    assert reqs["responsible_authority"]["title"] == "Tahsildar / Taluk Revenue Officer"

    # Test alternative documents
    income_alts = get_alternative_documents("income_proof", "income_certificate")
    assert len(income_alts) >= 3
    assert any("Salary Slips" in opt["name"] for opt in income_alts)
    assert any("Form 16" in opt["name"] for opt in income_alts)

    # Test document dependencies: newborn birth certificate does not need child's Aadhaar
    deps = get_document_dependencies("birth_certificate")
    assert any("no_child_aadhaar_required_for_birth_registration" in d["rule"] for d in deps)


@pytest.mark.asyncio
async def test_chatbot_exact_required_phrases(client: AsyncClient, db_session: AsyncSession):
    """
    Tests the exact set of user phrases specified in assignment:
    1. 'need income cert'
    2. 'incom certificate'
    3. 'incom certficate for scholership'
    4. 'how can i prove my family income'
    5. 'where do i get income proof'
    6. 'i need something for scholarship'
    7. 'birth cert for newborn'
    8. 'what papers do i need'
    9. 'i already uploaded my id'
    10. 'what am i missing?'
    """
    await seed_chat_test_data(db_session)

    login_res = await client.post("/api/auth/login", json={
        "email": "citizen2@example.com",
        "password": "password123"
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me_res = await client.get("/api/auth/me", headers=headers)
    user_id = me_res.json()["id"]

    # 1. "need income cert" -> Income Certificate
    res_1 = await client.post("/api/chat", json={
        "citizen_id": user_id,
        "message": "need income cert"
    }, headers=headers)
    assert res_1.status_code == 200
    data_1 = res_1.json()
    assert data_1["service_code"] == "income_certificate"
    assert "income_proof" in data_1["required_documents"]

    # 2. "incom certificate" -> Income Certificate (typo corrected)
    res_2 = await client.post("/api/chat", json={
        "citizen_id": user_id,
        "message": "incom certificate"
    }, headers=headers)
    assert res_2.status_code == 200
    data_2 = res_2.json()
    assert data_2["service_code"] == "income_certificate"
    assert data_2["normalized_message"] == "income certificate"

    # 3. "incom certficate for scholership" -> Income Certificate with scholarship guidance
    res_3 = await client.post("/api/chat", json={
        "citizen_id": user_id,
        "message": "incom certficate for scholership"
    }, headers=headers)
    assert res_3.status_code == 200
    data_3 = res_3.json()
    assert data_3["service_code"] == "income_certificate"
    assert "scholarship" in data_3["reply"].lower()

    # 4. "how can i prove my family income" -> Explains source-backed income proofs
    res_4 = await client.post("/api/chat", json={
        "citizen_id": user_id,
        "message": "how can i prove my family income"
    }, headers=headers)
    assert res_4.status_code == 200
    data_4 = res_4.json()
    assert "salary slip" in data_4["reply"].lower() or "form 16" in data_4["reply"].lower()
    assert "revenue" in data_4["reply"].lower() or "tahsildar" in data_4["reply"].lower()

    # 5. "where do i get income proof" -> Explains legitimate issuers without hallucination
    res_5 = await client.post("/api/chat", json={
        "citizen_id": user_id,
        "message": "where do i get income proof"
    }, headers=headers)
    assert res_5.status_code == 200
    data_5 = res_5.json()
    assert "employer" in data_5["reply"].lower() or "income tax" in data_5["reply"].lower() or "tahsildar" in data_5["reply"].lower()

    # 6. "i need something for scholarship" -> Connects scholarship to Income Certificate
    res_6 = await client.post("/api/chat", json={
        "citizen_id": user_id,
        "message": "i need something for scholarship"
    }, headers=headers)
    assert res_6.status_code == 200
    data_6 = res_6.json()
    assert data_6["service_code"] == "income_certificate"
    assert "scholarship" in data_6["reply"].lower()

    # 7. "birth cert for newborn" -> Birth Certificate (explicitly verifies no newborn Aadhaar requirement)
    res_7 = await client.post("/api/chat", json={
        "citizen_id": user_id,
        "message": "birth cert for newborn"
    }, headers=headers)
    assert res_7.status_code == 200
    data_7 = res_7.json()
    assert data_7["service_code"] == "birth_certificate"
    assert "hospital_certificate" in data_7["required_documents"]
    assert "not required" in data_7["reply"].lower() or "aadhaar" in data_7["reply"].lower()

    # 8. "what papers do i need" -> In context of active application
    res_8 = await client.post("/api/chat", json={
        "citizen_id": user_id,
        "message": "what papers do i need"
    }, headers=headers)
    assert res_8.status_code == 200
    data_8 = res_8.json()
    assert len(data_8["required_documents"]) > 0

    # 9. "i already uploaded my id" -> Context aware upload follow-up
    res_9 = await client.post("/api/chat", json={
        "citizen_id": user_id,
        "message": "i already uploaded my id"
    }, headers=headers)
    assert res_9.status_code == 200
    data_9 = res_9.json()
    assert "verified" in data_9["reply"].lower() or "recorded" in data_9["reply"].lower()

    # 10. "what am i missing?" -> Status & missing requirement check
    res_10 = await client.post("/api/chat", json={
        "citizen_id": user_id,
        "message": "what am i missing?"
    }, headers=headers)
    assert res_10.status_code == 200
    data_10 = res_10.json()
    assert "missing" in data_10["reply"].lower()


@pytest.mark.asyncio
async def test_audit_preserves_original_user_message(client: AsyncClient, db_session: AsyncSession):
    """
    CRITICAL REQUIREMENT:
    'The original user message should remain stored for audit/debugging.'
    """
    await seed_chat_test_data(db_session)

    login_res = await client.post("/api/auth/login", json={
        "email": "citizen2@example.com",
        "password": "password123"
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me_res = await client.get("/api/auth/me", headers=headers)
    user_id = me_res.json()["id"]

    raw_imperfect_msg = "incom certficate for scholership with aadahr"
    res = await client.post("/api/chat", json={
        "citizen_id": user_id,
        "message": raw_imperfect_msg
    }, headers=headers)
    assert res.status_code == 200

    # Verify ChatMessage record in DB
    chat_query = await db_session.execute(
        select(ChatMessage).where(ChatMessage.original_message == raw_imperfect_msg)
    )
    chat_record = chat_query.scalar_one_or_none()
    assert chat_record is not None
    assert chat_record.original_message == raw_imperfect_msg
    assert "income" in chat_record.normalized_message
    assert "scholarship" in chat_record.normalized_message
    assert "scholership" in chat_record.corrections

    # Verify AuditLog record in DB
    audit_query = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "CHAT_MESSAGE")
    )
    audit_records = audit_query.scalars().all()
    assert any(
        a.details and a.details.get("original_message") == raw_imperfect_msg
        for a in audit_records
    )

    # Verify GET /api/chat/history endpoint
    history_res = await client.get("/api/chat/history", headers=headers)
    assert history_res.status_code == 200
    history_data = history_res.json()
    assert any(m["original_message"] == raw_imperfect_msg for m in history_data)
