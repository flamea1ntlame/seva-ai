import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import User, Service, Application, Document, CitizenProfile
from app.auth import get_password_hash, create_access_token


async def seed_test_context(db_session: AsyncSession):
    # Seed Citizen A
    res = await db_session.execute(select(User).where(User.email == "citizen_ctx_a@example.com"))
    user_a = res.scalar_one_or_none()
    if not user_a:
        user_a = User(
            email="citizen_ctx_a@example.com",
            password_hash=get_password_hash("password123"),
            full_name="Aarav Patel",
            role="citizen",
            is_active=True,
        )
        db_session.add(user_a)
        await db_session.flush()
        db_session.add(CitizenProfile(user_id=user_a.id, state="Karnataka", address="Bengaluru"))

    # Seed Citizen B
    res_b = await db_session.execute(select(User).where(User.email == "citizen_ctx_b@example.com"))
    user_b = res_b.scalar_one_or_none()
    if not user_b:
        user_b = User(
            email="citizen_ctx_b@example.com",
            password_hash=get_password_hash("password123"),
            full_name="Bhavna Rao",
            role="citizen",
            is_active=True,
        )
        db_session.add(user_b)
        await db_session.flush()
        db_session.add(CitizenProfile(user_id=user_b.id, state="Karnataka", address="Mysuru"))

    # Seed Services if not present
    for code, title, dept, docs, fields in [
        ("income_certificate", "Income Certificate", "revenue", ["identity_proof", "income_proof"], ["annual_income"]),
        ("birth_certificate", "Birth Certificate", "municipal", ["hospital_certificate", "parent_identity_proof"], ["date_of_birth"]),
    ]:
        s_res = await db_session.execute(select(Service).where(Service.code == code))
        if not s_res.scalar_one_or_none():
            db_session.add(Service(
                code=code,
                title=title,
                department=dept,
                required_documents=docs,
                required_fields=fields,
                processing_time_days=7,
                fee_amount=50.0,
                is_active=True,
            ))

    await db_session.commit()
    await db_session.refresh(user_a)
    await db_session.refresh(user_b)
    return user_a, user_b


@pytest.mark.asyncio
async def test_selected_service_upload_status_request_keeps_context(client: AsyncClient, db_session: AsyncSession):
    """
    Regression Test 1:
    Citizen selects service + uploads document + sends 'I uploaded my identity proof. Check my application status.'
    Chatbot MUST preserve and use existing application/service context instead of asking to specify service again.
    """
    user_a, _ = await seed_test_context(db_session)
    token = create_access_token(data={"sub": str(user_a.id)})
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Citizen creates/starts Income Certificate application
    s_res = await db_session.execute(select(Service).where(Service.code == "income_certificate"))
    income_service = s_res.scalar_one()

    app_income = Application(
        user_id=user_a.id,
        service_id=income_service.id,
        application_number=f"SEVA-CTX-{uuid.uuid4().hex[:4].upper()}",
        status="COLLECTING_DOCUMENTS",
        form_data={},
    )
    db_session.add(app_income)
    await db_session.flush()

    # 2. Citizen uploads identity proof document linked to application
    doc = Document(
        user_id=user_a.id,
        application_id=app_income.id,
        document_type="identity_proof",
        title="Aadhaar Card",
        file_path="/tmp/aadhaar.pdf",
        verified=True,
        verification_status="VERIFIED",
    )
    db_session.add(doc)
    await db_session.commit()

    # 3. Citizen sends status follow-up message with application_id
    payload = {
        "citizen_id": str(user_a.id),
        "message": "I uploaded my identity proof. Check my application status.",
        "application_id": str(app_income.id),
    }

    res = await client.post("/api/chat", json=payload, headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()

    # MUST keep Income Certificate context
    assert data["service_code"] == "income_certificate"
    assert data["application_id"] == str(app_income.id)
    # MUST NOT ask citizen to specify which service they want
    assert "specify which service you would like to apply for" not in data["reply"].lower()
    # MUST discuss income certificate and recorded document or remaining document
    assert "income certificate" in data["reply"].lower()


@pytest.mark.asyncio
async def test_existing_application_context_prevents_unnecessary_clarification(client: AsyncClient, db_session: AsyncSession):
    """
    Regression Test 2:
    Existing application context prevents unnecessary service clarification when citizen asks for status.
    """
    user_a, _ = await seed_test_context(db_session)
    token = create_access_token(data={"sub": str(user_a.id)})
    headers = {"Authorization": f"Bearer {token}"}

    # Clear previous apps for clean test
    existing = await db_session.execute(select(Application).where(Application.user_id == user_a.id))
    for a in existing.scalars().all():
        await db_session.delete(a)
    await db_session.commit()

    s_res = await db_session.execute(select(Service).where(Service.code == "income_certificate"))
    income_service = s_res.scalar_one()

    app_income = Application(
        user_id=user_a.id,
        service_id=income_service.id,
        application_number=f"SEVA-CTX-{uuid.uuid4().hex[:4].upper()}",
        status="COLLECTING_DOCUMENTS",
        form_data={},
    )
    db_session.add(app_income)
    await db_session.commit()

    # Citizen simply asks status without repeating service name or providing explicit ID in payload
    payload = {
        "citizen_id": str(user_a.id),
        "message": "Check my application status",
    }

    res = await client.post("/api/chat", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["service_code"] == "income_certificate"
    assert data["application_id"] == str(app_income.id)
    assert "specify which service" not in data["reply"].lower()
    assert "income certificate" in data["reply"].lower()


@pytest.mark.asyncio
async def test_multiple_active_applications_behave_deterministically(client: AsyncClient, db_session: AsyncSession):
    """
    Regression Test 3:
    Multiple active applications behave deterministically:
    - If application_id provided: directly resolves to that application context.
    - If not provided: asks to disambiguate between existing applications, not generic service catalog.
    """
    user_a, _ = await seed_test_context(db_session)
    token = create_access_token(data={"sub": str(user_a.id)})
    headers = {"Authorization": f"Bearer {token}"}

    # Clear previous apps
    existing = await db_session.execute(select(Application).where(Application.user_id == user_a.id))
    for a in existing.scalars().all():
        await db_session.delete(a)
    await db_session.commit()

    s_inc = (await db_session.execute(select(Service).where(Service.code == "income_certificate"))).scalar_one()
    s_birth = (await db_session.execute(select(Service).where(Service.code == "birth_certificate"))).scalar_one()

    app1 = Application(
        user_id=user_a.id,
        service_id=s_inc.id,
        application_number="SEVA-INC-99",
        status="COLLECTING_DOCUMENTS",
        form_data={},
    )
    app2 = Application(
        user_id=user_a.id,
        service_id=s_birth.id,
        application_number="SEVA-BRT-99",
        status="VALIDATING",
        form_data={},
    )
    db_session.add(app1)
    db_session.add(app2)
    await db_session.commit()

    # Case A: Explicit application_id for app2 supplied in chat payload -> deterministic resolution to app2
    payload_a = {
        "citizen_id": str(user_a.id),
        "message": "Check my application status",
        "application_id": str(app2.id),
    }
    res_a = await client.post("/api/chat", json=payload_a, headers=headers)
    assert res_a.status_code == 200
    data_a = res_a.json()
    assert data_a["application_id"] == str(app2.id)
    assert data_a["service_code"] == "birth_certificate"
    assert "SEVA-BRT-99" in data_a["reply"]

    # Case B: Explicit application_id for app1 supplied in chat payload -> deterministic resolution to app1
    payload_b = {
        "citizen_id": str(user_a.id),
        "message": "Check my application status",
        "application_id": str(app1.id),
    }
    res_b = await client.post("/api/chat", json=payload_b, headers=headers)
    assert res_b.status_code == 200
    data_b = res_b.json()
    assert data_b["application_id"] == str(app1.id)
    assert data_b["service_code"] == "income_certificate"
    assert "SEVA-INC-99" in data_b["reply"]

    # Case C: Service-specific query deterministically routes to the matching application
    payload_c = {
        "citizen_id": str(user_a.id),
        "message": "What documents are needed for my income certificate?",
    }
    res_c = await client.post("/api/chat", json=payload_c, headers=headers)
    assert res_c.status_code == 200
    data_c = res_c.json()
    assert data_c["application_id"] == str(app1.id)
    assert data_c["service_code"] == "income_certificate"
    assert "SEVA-INC-99" in data_c["reply"]

    # Case D: Without explicit ID or service name, deterministically resolves to most recent active app (app2)
    payload_d = {
        "citizen_id": str(user_a.id),
        "message": "Check my application status",
    }
    res_d = await client.post("/api/chat", json=payload_d, headers=headers)
    assert res_d.status_code == 200
    data_d = res_d.json()
    assert data_d["application_id"] == str(app2.id)
    assert data_d["service_code"] == "birth_certificate"
    assert "SEVA-BRT-99" in data_d["reply"]


@pytest.mark.asyncio
async def test_no_cross_citizen_application_context_leakage(client: AsyncClient, db_session: AsyncSession):
    """
    Regression Test 4:
    Citizen B passing Citizen A's application_id must NOT be able to access Citizen A's application context.
    """
    user_a, user_b = await seed_test_context(db_session)
    token_b = create_access_token(data={"sub": str(user_b.id)})
    headers_b = {"Authorization": f"Bearer {token_b}"}

    s_inc = (await db_session.execute(select(Service).where(Service.code == "income_certificate"))).scalar_one()

    # Create private app for Citizen A
    app_a = Application(
        user_id=user_a.id,
        service_id=s_inc.id,
        application_number="SEVA-SECRET-CITIZEN-A",
        status="READY_FOR_REVIEW",
        form_data={"confidential_notes": "Private to Citizen A"},
    )
    db_session.add(app_a)
    await db_session.commit()

    # Citizen B attempts to pass Citizen A's application_id
    payload = {
        "citizen_id": str(user_b.id),
        "message": "Check my application status",
        "application_id": str(app_a.id),
    }

    res = await client.post("/api/chat", json=payload, headers=headers_b)
    assert res.status_code == 200
    data = res.json()

    # Citizen B must NOT inherit Citizen A's application ID or reference number
    assert data.get("application_id") != str(app_a.id)
    assert "SEVA-SECRET-CITIZEN-A" not in data.get("reply", "")
