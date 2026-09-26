import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import User, Service, CitizenProfile, ChatMessage, AuditLog, Application, Document
from app.auth import get_password_hash
from app.nlp.normalizer import normalize_text
from app.nlp.matcher import match_intent_and_service, Intent
from app.nlp.pii import mask_pii
from app.service_rules import (
    get_requirements,
    get_alternative_documents,
    get_document_dependencies,
    evaluate_citizen_readiness,
    is_requirement_satisfied
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
    """Validates typo correction, Indic preservation, and absence of semantic mutations."""
    # 1. Typo correction
    res1 = normalize_text("i need birth certifcate")
    assert "birth certificate" in res1.normalized_text

    # 2. Aadhaar typo
    res2 = normalize_text("uploaded my aadahr card")
    assert "Aadhaar" in res2.normalized_text
    assert "aadahr" in res2.corrections

    # 3. Driving licence typo
    res3 = normalize_text("i want driving lisence")
    assert "driving licence" in res3.normalized_text

    # 4. Scholarship typo
    res4 = normalize_text("incom certficate for scholership")
    assert "income certificate" in res4.normalized_text
    assert "scholarship" in res4.normalized_text

    # 5. NO semantic mutation: 'earning' must NOT become 'income'
    res5 = normalize_text("I am earning 50000 per month")
    assert "earning" in res5.normalized_text
    assert "income" not in res5.normalized_text

    # 6. Native Devanagari script preservation & phrase normalization
    res_hi = normalize_text("मुझे आय प्रमाण पत्र चाहिए")
    assert "income certificate" in res_hi.normalized_text
    assert "मुझे" in res_hi.normalized_text

    # 7. Native Kannada script preservation & phrase normalization
    res_kn = normalize_text("ನನಗೆ ಆದಾಯ ಪ್ರಮಾಣಪತ್ರ ಬೇಕು")
    assert "income certificate" in res_kn.normalized_text
    assert "ನನಗೆ" in res_kn.normalized_text


@pytest.mark.asyncio
async def test_service_rules_async_and_no_silent_fallback():
    """Validates async protocol, jurisdiction checks, and semantic satisfaction."""
    # 1. Supported jurisdiction
    reqs_ka = await get_requirements("income_certificate", jurisdiction="karnataka")
    assert reqs_ka["jurisdiction_supported"] is True
    assert "Nadakacheri" in reqs_ka["jurisdiction"]["portal"]
    assert "income_proof" in reqs_ka["required_documents"]

    # 2. Unsupported jurisdiction must return jurisdiction_supported=False (NO silent fallback)
    reqs_unsupported = await get_requirements("income_certificate", jurisdiction="kerala")
    assert reqs_unsupported["jurisdiction_supported"] is False
    assert "not currently verified" in reqs_unsupported["error"]
    assert "Karnataka" in reqs_unsupported["supported_jurisdictions"]

    # 3. Document satisfaction: Parent identity proof satisfied by legitimate parent ID (Aadhaar / Voter ID)
    assert is_requirement_satisfied("parent_identity_proof", ["identity_proof"]) is True
    assert is_requirement_satisfied("parent_identity_proof", ["aadhaar"]) is True
    assert is_requirement_satisfied("parent_identity_proof", ["voter_id"]) is True
    # Child's identity CANNOT satisfy parent identity proof
    assert is_requirement_satisfied("parent_identity_proof", ["child_aadhaar"]) is False


@pytest.mark.asyncio
async def test_pii_masking_unit():
    """Validates masking of Aadhaar, PAN, and phone numbers."""
    raw = "My Aadhaar is 1234 5678 9012, PAN is ABCDE1234F and phone is 9876543210"
    masked = mask_pii(raw)
    assert "1234 5678" not in masked
    assert "XXXX-XXXX-9012" in masked
    assert "ABCDE1234F" not in masked
    assert "XXXXX1234F" in masked
    assert "9876543210" not in masked
    assert "XXXXXX3210" in masked


@pytest.mark.asyncio
async def test_duplicate_application_prevention_on_multi_app(client: AsyncClient, db_session: AsyncSession):
    """
    CRITICAL BLOCKER 1 REGRESSION TEST:
    Ensures that when a user already has multiple active applications (e.g. app 0 is birth_cert,
    app 1 is income_cert), sending an income cert message REUSES app 1 instead of creating a duplicate.
    """
    await seed_chat_test_data(db_session)

    login_res = await client.post("/api/auth/login", json={"email": "citizen2@example.com", "password": "password123"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me_res = await client.get("/api/auth/me", headers=headers)
    user_id = me_res.json()["id"]

    # Get services
    s_birth = (await db_session.execute(select(Service).where(Service.code == "birth_certificate"))).scalar_one()
    s_income = (await db_session.execute(select(Service).where(Service.code == "income_certificate"))).scalar_one()

    # Pre-populate 2 active applications:
    # app_0 is birth certificate (at index 0)
    # app_1 is income certificate (at index 1)
    app_0 = Application(application_number="SEVA-888001", user_id=uuid.UUID(user_id), service_id=s_birth.id, status="COLLECTING_DOCUMENTS")
    app_1 = Application(application_number="SEVA-888002", user_id=uuid.UUID(user_id), service_id=s_income.id, status="COLLECTING_DOCUMENTS")
    db_session.add_all([app_0, app_1])
    await db_session.commit()

    # Now citizen requests income certificate
    res = await client.post("/api/chat", json={
        "citizen_id": user_id,
        "message": "need income cert"
    }, headers=headers)
    assert res.status_code == 200
    data = res.json()

    # Must reuse app_1 (SEVA-888002) and NOT create a new duplicate application!
    assert data["application_id"] == str(app_1.id)
    assert "SEVA-888002" in data["reply"]

    # Count income certificate applications for this citizen: exactly 1
    total_income_apps = (await db_session.execute(
        select(Application).where(Application.user_id == uuid.UUID(user_id), Application.service_id == s_income.id)
    )).scalars().all()
    assert len(total_income_apps) == 1

    # Cleanup
    await db_session.delete(app_0)
    await db_session.delete(app_1)
    await db_session.commit()


@pytest.mark.asyncio
async def test_unsupported_jurisdiction_chat(client: AsyncClient, db_session: AsyncSession):
    """Validates that an unsupported jurisdiction request honestly reports verification inability."""
    await seed_chat_test_data(db_session)

    login_res = await client.post("/api/auth/login", json={"email": "citizen2@example.com", "password": "password123"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me_res = await client.get("/api/auth/me", headers=headers)
    user_id = me_res.json()["id"]

    res = await client.post("/api/chat", json={
        "citizen_id": user_id,
        "message": "I need an income certificate in Kerala"
    }, headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert "jurisdiction notice" in data["reply"].lower()
    assert "kerala" in data["reply"].lower()
    assert "karnataka" in data["reply"].lower()
    assert data["application_id"] is None


@pytest.mark.asyncio
async def test_contradictory_user_statement(client: AsyncClient, db_session: AsyncSession):
    """Validates handling of contradictory user statements (e.g. negation / change of mind)."""
    await seed_chat_test_data(db_session)

    login_res = await client.post("/api/auth/login", json={"email": "citizen2@example.com", "password": "password123"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me_res = await client.get("/api/auth/me", headers=headers)
    user_id = me_res.json()["id"]

    # Contradictory message
    res = await client.post("/api/chat", json={
        "citizen_id": user_id,
        "message": "Actually I don't want an income certificate, I want a driving license instead"
    }, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["service_code"] == "driving_license"
    assert "driving license" in data["reply"].lower()


@pytest.mark.asyncio
async def test_audit_masks_pii(client: AsyncClient, db_session: AsyncSession):
    """Validates that PII (Aadhaar, PAN, phone) in user messages is masked before database persistence."""
    await seed_chat_test_data(db_session)

    login_res = await client.post("/api/auth/login", json={"email": "citizen2@example.com", "password": "password123"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me_res = await client.get("/api/auth/me", headers=headers)
    user_id = me_res.json()["id"]

    sensitive_msg = "My Aadhaar is 9999 8888 7777 and PAN is ABCDE9876Z. Please make income cert."
    res = await client.post("/api/chat", json={
        "citizen_id": user_id,
        "message": sensitive_msg
    }, headers=headers)
    assert res.status_code == 200

    # Query ChatMessage table
    chat_rows = (await db_session.execute(
        select(ChatMessage).where(ChatMessage.user_id == uuid.UUID(user_id)).order_by(ChatMessage.created_at.desc())
    )).scalars().all()
    user_chat = next(c for c in chat_rows if c.role == "user")

    # Raw PII must NOT be present in database!
    assert "9999 8888 7777" not in user_chat.original_message
    assert "XXXX-XXXX-7777" in user_chat.original_message
    assert "ABCDE9876Z" not in user_chat.original_message
    assert "XXXXX9876Z" in user_chat.original_message


@pytest.mark.asyncio
async def test_birth_registration_parent_id_satisfaction(client: AsyncClient, db_session: AsyncSession):
    """
    Validates document semantics:
    Uploading 'identity_proof' satisfies 'parent_identity_proof' requirement for birth certificate.
    """
    await seed_chat_test_data(db_session)

    login_res = await client.post("/api/auth/login", json={"email": "citizen2@example.com", "password": "password123"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me_res = await client.get("/api/auth/me", headers=headers)
    user_id = me_res.json()["id"]

    # 1. Citizen applies for birth certificate
    res_init = await client.post("/api/chat", json={
        "citizen_id": user_id,
        "message": "birth cert for newborn"
    }, headers=headers)
    assert res_init.status_code == 200
    app_id = res_init.json()["application_id"]

    # 2. Simulate citizen uploading parent identity proof tagged as 'identity_proof'
    doc = Document(
        user_id=uuid.UUID(user_id),
        application_id=uuid.UUID(app_id),
        document_type="identity_proof",
        title="Father Aadhaar Card",
        file_path="mock/father_aadhaar.pdf",
        verified=True,
        verification_status="VERIFIED",
        extracted_data={"name": "Priya Sharma"}
    )
    db_session.add(doc)
    await db_session.commit()

    # 3. Ask what is missing
    res_missing = await client.post("/api/chat", json={
        "citizen_id": user_id,
        "message": "what am i missing?"
    }, headers=headers)
    assert res_missing.status_code == 200
    data_missing = res_missing.json()

    # parent_identity_proof must be satisfied! Only hospital_certificate should be in missing_documents
    assert "hospital_certificate" in data_missing["required_documents"]
    assert "parent_identity_proof" not in data_missing["required_documents"]
