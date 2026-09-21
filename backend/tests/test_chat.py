import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import User, Service, CitizenProfile
from app.auth import get_password_hash


async def seed_test_data(db: AsyncSession):
    # Seed Demo User
    res = await db.execute(select(User).where(User.email == "citizen@example.com"))
    user = res.scalar_one_or_none()
    if not user:
        user = User(
            email="citizen@example.com",
            password_hash=get_password_hash("password123"),
            full_name="Ramesh Kumar",
            phone_number="+919876543210",
            role="citizen",
            is_active=True,
        )
        db.add(user)
        await db.flush()
        profile = CitizenProfile(user_id=user.id)
        db.add(profile)

    # Seed 3 Services
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

    for s_data in services_data:
        res_s = await db.execute(select(Service).where(Service.code == s_data["code"]))
        if not res_s.scalar_one_or_none():
            service = Service(
                code=s_data["code"],
                title=s_data["title"],
                department=s_data["department"],
                description=s_data["description"],
                required_documents=s_data["required_documents"],
                required_fields=s_data["required_fields"],
                processing_time_days=s_data["processing_time_days"],
                fee_amount=s_data["fee_amount"],
                is_active=True,
            )
            db.add(service)

    await db.commit()


@pytest.mark.asyncio
async def test_chat_agent_workflows(client: AsyncClient, db_session: AsyncSession):
    await seed_test_data(db_session)

    # Login to get JWT
    login_res = await client.post("/api/auth/login", json={
        "email": "citizen@example.com",
        "password": "password123"
    })
    assert login_res.status_code == 200, login_res.text
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch user ID
    me_res = await client.get("/api/auth/me", headers=headers)
    assert me_res.status_code == 200
    user_id = me_res.json()["id"]

    # Test 1: Driving License request
    payload_1 = {
        "citizen_id": user_id,
        "message": "I want to apply for a driving licence"
    }
    res_1 = await client.post("/api/chat", json=payload_1, headers=headers)
    assert res_1.status_code == 200, res_1.text
    data_1 = res_1.json()
    assert data_1["service_code"] == "driving_license"
    assert data_1["status"] == "COLLECTING_DOCUMENTS"
    assert "photograph" in data_1["required_documents"]
    assert "vehicle_class" in data_1["required_fields"]
    assert data_1["application_id"] is not None

    # Test 2: Income Certificate request
    payload_2 = {
        "citizen_id": user_id,
        "message": "I need an income certificate"
    }
    res_2 = await client.post("/api/chat", json=payload_2, headers=headers)
    assert res_2.status_code == 200, res_2.text
    data_2 = res_2.json()
    assert data_2["service_code"] == "income_certificate"
    assert data_2["status"] == "COLLECTING_DOCUMENTS"
    assert "income_proof" in data_2["required_documents"]
    assert "annual_income" in data_2["required_fields"]

    # Test 3: Birth Certificate request
    payload_3 = {
        "citizen_id": user_id,
        "message": "I need a birth certificate for my child"
    }
    res_3 = await client.post("/api/chat", json=payload_3, headers=headers)
    assert res_3.status_code == 200, res_3.text
    data_3 = res_3.json()
    assert data_3["service_code"] == "birth_certificate"
    assert data_3["status"] == "COLLECTING_DOCUMENTS"
    assert "hospital_certificate" in data_3["required_documents"]
    assert "applicant_name" in data_3["required_fields"]

    # Test 4: Ambiguous request -> asks clarification
    payload_4 = {
        "citizen_id": user_id,
        "message": "I need a government certificate"
    }
    res_4 = await client.post("/api/chat", json=payload_4, headers=headers)
    assert res_4.status_code == 200, res_4.text
    data_4 = res_4.json()
    assert data_4["service_code"] is None
    assert data_4["application_id"] is None
    assert "Could you please specify" in data_4["reply"]


@pytest.mark.asyncio
async def test_chat_forbidden_for_other_citizen(client: AsyncClient, db_session: AsyncSession):
    await seed_test_data(db_session)

    login_res = await client.post("/api/auth/login", json={
        "email": "citizen@example.com",
        "password": "password123"
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Attempt to pass a random fake citizen_id
    other_citizen_id = str(uuid.uuid4())
    payload = {
        "citizen_id": other_citizen_id,
        "message": "I need an income certificate"
    }
    res = await client.post("/api/chat", json=payload, headers=headers)
    assert res.status_code == 403
    assert "Forbidden" in res.json()["detail"]
