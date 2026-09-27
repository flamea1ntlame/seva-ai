import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import User, Service, CitizenProfile, Document
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

    # Seed verified learner_licence for this workflow test to satisfy DL prerequisite
    ll_doc = Document(
        user_id=uuid.UUID(user_id),
        document_type="learner_licence",
        title="Learner's Licence",
        file_path="documents/test_ll.pdf",
        verified=True,
        verification_status="VERIFIED"
    )
    db_session.add(ll_doc)
    await db_session.commit()

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

from app.models import Application

@pytest.mark.asyncio
async def test_chat_existing_ready_for_review(client: AsyncClient, db_session: AsyncSession):
    await seed_test_data(db_session)

    # Login
    login_res = await client.post("/api/auth/login", json={"email": "citizen@example.com", "password": "password123"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me_res = await client.get("/api/auth/me", headers=headers)
    user_id = me_res.json()["id"]

    # Get service
    res_s = await db_session.execute(select(Service).where(Service.code == "income_certificate"))
    service = res_s.scalar_one()

    # Create READY_FOR_REVIEW application
    app_num = "SEVA-999111"
    application = Application(
        application_number=app_num,
        user_id=uuid.UUID(user_id),
        service_id=service.id,
        status="READY_FOR_REVIEW",
        form_data={},
        remarks="Test app"
    )
    db_session.add(application)
    await db_session.commit()
    await db_session.refresh(application)

    # Test generic submit request
    payload = {
        "citizen_id": user_id,
        "message": "I have uploaded everything. Please prepare my application for submission."
    }
    res = await client.post("/api/chat", json=payload, headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()

    # Should resolve to the existing application and progress to CONSENT_REQUIRED
    assert data["application_id"] == str(application.id)
    assert "consent" in data["reply"].lower() or "prepare" in data["reply"].lower() or data["status"] in ["CONSENT_REQUIRED", "READY_FOR_REVIEW"]

    # Cleanup for next test
    await db_session.delete(application)
    await db_session.commit()

@pytest.mark.asyncio
async def test_chat_multiple_active_applications(client: AsyncClient, db_session: AsyncSession):
    await seed_test_data(db_session)

    # Login
    login_res = await client.post("/api/auth/login", json={"email": "citizen@example.com", "password": "password123"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me_res = await client.get("/api/auth/me", headers=headers)
    user_id = me_res.json()["id"]

    # Get services
    res_s1 = await db_session.execute(select(Service).where(Service.code == "income_certificate"))
    res_s2 = await db_session.execute(select(Service).where(Service.code == "birth_certificate"))
    service1 = res_s1.scalar_one()
    service2 = res_s2.scalar_one()

    # Create two active applications
    app1 = Application(application_number="SEVA-999222", user_id=uuid.UUID(user_id), service_id=service1.id, status="READY_FOR_REVIEW")
    app2 = Application(application_number="SEVA-999333", user_id=uuid.UUID(user_id), service_id=service2.id, status="READY_FOR_REVIEW")
    db_session.add_all([app1, app2])
    await db_session.commit()

    # Test ambiguous request
    payload = {
        "citizen_id": user_id,
        "message": "Please prepare my application."
    }
    res = await client.post("/api/chat", json=payload, headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()

    # Should ask for clarification
    assert "Which" in data["reply"] or "specify" in data["reply"] or "multiple" in data["reply"] or "Could you please specify" in data["reply"]

    # Cleanup
    await db_session.delete(app1)
    await db_session.delete(app2)
    await db_session.commit()

@pytest.mark.asyncio
async def test_chat_existing_consent_required(client: AsyncClient, db_session: AsyncSession):
    await seed_test_data(db_session)

    # Login
    login_res = await client.post('/api/auth/login', json={'email': 'citizen@example.com', 'password': 'password123'})
    token = login_res.json()['access_token']
    headers = {'Authorization': f'Bearer {token}'}
    # Wait, the response might not have id in the root, it has id in me_res
    me_res = await client.get('/api/auth/me', headers=headers)
    user_id = me_res.json()['id']

    # Get service
    res_s = await db_session.execute(select(Service).where(Service.code == 'income_certificate'))
    service = res_s.scalar_one()

    # Create CONSENT_REQUIRED application
    app_num = 'SEVA-999444'
    application = Application(
        application_number=app_num,
        user_id=uuid.UUID(user_id),
        service_id=service.id,
        status='CONSENT_REQUIRED',
        form_data={},
        remarks='Test app'
    )
    db_session.add(application)
    await db_session.commit()

    # Test generic submit request
    payload = {
        'citizen_id': user_id,
        'message': 'Please prepare my application.'
    }
    res = await client.post('/api/chat', json=payload, headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()

    # Should resolve to the existing application and preserve status
    assert data['application_id'] == str(application.id)
    assert 'consent' in data['reply'].lower() or 'approve' in data['reply'].lower()

    # Cleanup
    await db_session.delete(application)
    await db_session.commit()

@pytest.mark.asyncio
async def test_chat_multiple_active_apps_explicit_intent(client: AsyncClient, db_session: AsyncSession):
    await seed_test_data(db_session)

    # Login
    login_res = await client.post('/api/auth/login', json={'email': 'citizen@example.com', 'password': 'password123'})
    token = login_res.json()['access_token']
    headers = {'Authorization': f'Bearer {token}'}
    me_res = await client.get('/api/auth/me', headers=headers)
    user_id = me_res.json()['id']

    # Get services
    res_s1 = await db_session.execute(select(Service).where(Service.code == 'income_certificate'))
    res_s2 = await db_session.execute(select(Service).where(Service.code == 'birth_certificate'))
    service1 = res_s1.scalar_one()
    service2 = res_s2.scalar_one()

    # Create two active applications
    app1 = Application(application_number='SEVA-999555', user_id=uuid.UUID(user_id), service_id=service1.id, status='READY_FOR_REVIEW')
    app2 = Application(application_number='SEVA-999666', user_id=uuid.UUID(user_id), service_id=service2.id, status='READY_FOR_REVIEW')
    db_session.add_all([app1, app2])
    await db_session.commit()

    # Test explicit request
    payload = {
        'citizen_id': user_id,
        'message': 'Prepare my Income Certificate application for submission.'
    }
    res = await client.post('/api/chat', json=payload, headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()

    # Should resolve strictly to the Income Certificate (app1)
    assert data['application_id'] == str(app1.id)
    assert data['status'] == 'CONSENT_REQUIRED'
    assert 'consent' in data['reply'].lower() or 'approve' in data['reply'].lower()

    # Cleanup
    await db_session.delete(app1)
    await db_session.delete(app2)
    await db_session.commit()

@pytest.mark.asyncio
async def test_chat_generic_info_request_with_existing_app(client: AsyncClient, db_session: AsyncSession):
    await seed_test_data(db_session)

    # Login
    login_res = await client.post('/api/auth/login', json={'email': 'citizen@example.com', 'password': 'password123'})
    token = login_res.json()['access_token']
    headers = {'Authorization': f'Bearer {token}'}
    me_res = await client.get('/api/auth/me', headers=headers)
    user_id = me_res.json()['id']

    # Get service
    res_s = await db_session.execute(select(Service).where(Service.code == 'income_certificate'))
    service = res_s.scalar_one()

    # Create READY_FOR_REVIEW application
    app_num = 'SEVA-999777'
    application = Application(
        application_number=app_num,
        user_id=uuid.UUID(user_id),
        service_id=service.id,
        status='READY_FOR_REVIEW',
        form_data={},
        remarks='Test app'
    )
    db_session.add(application)
    await db_session.commit()

    # Test info request
    payload = {
        'citizen_id': user_id,
        'message': 'What documents are required for an Income Certificate?'
    }
    res = await client.post('/api/chat', json=payload, headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()

    # Should NOT submit or request consent, just provide info but link to existing app
    assert data['application_id'] == str(application.id)
    assert data['status'] == 'READY_FOR_REVIEW'
    assert 'consent' not in data['reply'].lower()

    # Cleanup
    await db_session.delete(application)
    await db_session.commit()

@pytest.mark.asyncio
async def test_chat_multiple_active_apps_explicit_seva_ref(client: AsyncClient, db_session: AsyncSession):
    await seed_test_data(db_session)

    login_res = await client.post('/api/auth/login', json={'email': 'citizen@example.com', 'password': 'password123'})
    token = login_res.json()['access_token']
    headers = {'Authorization': f'Bearer {token}'}
    me_res = await client.get('/api/auth/me', headers=headers)
    user_id = me_res.json()['id']

    res_s1 = await db_session.execute(select(Service).where(Service.code == 'income_certificate'))
    service1 = res_s1.scalar_one()

    # Create two active applications of the SAME service
    app1 = Application(application_number='SEVA-999888', user_id=uuid.UUID(user_id), service_id=service1.id, status='READY_FOR_REVIEW')
    app2 = Application(application_number='SEVA-999999', user_id=uuid.UUID(user_id), service_id=service1.id, status='READY_FOR_REVIEW')
    db_session.add_all([app1, app2])
    await db_session.commit()

    # Test explicit SEVA reference
    payload = {
        'citizen_id': user_id,
        'message': 'Prepare application SEVA-999888 for submission.'
    }
    res = await client.post('/api/chat', json=payload, headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()

    # Should resolve strictly to app1
    assert data['application_id'] == str(app1.id)
    assert data['status'] == 'CONSENT_REQUIRED'
    assert 'consent' in data['reply'].lower() or 'approve' in data['reply'].lower()

    # Test invalid SEVA reference
    payload_invalid = {
        'citizen_id': user_id,
        'message': 'Prepare application SEVA-111111 for submission.'
    }
    res_invalid = await client.post('/api/chat', json=payload_invalid, headers=headers)
    assert res_invalid.status_code == 200, res_invalid.text
    data_invalid = res_invalid.json()

    assert data_invalid['application_id'] is None
    assert "couldn't find" in data_invalid['reply'].lower()

    # Cleanup
    await db_session.delete(app1)
    await db_session.delete(app2)
    await db_session.commit()

@pytest.mark.asyncio
async def test_chat_cross_user_reference(client: AsyncClient, db_session: AsyncSession):
    await seed_test_data(db_session)

    # Login as citizen
    login_res = await client.post('/api/auth/login', json={'email': 'citizen@example.com', 'password': 'password123'})
    token = login_res.json()['access_token']
    headers = {'Authorization': f'Bearer {token}'}
    me_res = await client.get('/api/auth/me', headers=headers)
    user_id = me_res.json()['id']

    res_s1 = await db_session.execute(select(Service).where(Service.code == 'income_certificate'))
    service1 = res_s1.scalar_one()

    # Create an app for ANOTHER user
    other_user_id = str(uuid.uuid4())
    app_other = Application(application_number='SEVA-222333', user_id=uuid.UUID(other_user_id), service_id=service1.id, status='READY_FOR_REVIEW')
    db_session.add(app_other)
    await db_session.commit()

    payload = {
        'citizen_id': user_id,
        'message': 'Prepare application SEVA-222333 for submission.'
    }
    res = await client.post('/api/chat', json=payload, headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()

    assert data['application_id'] is None
    assert "couldn't find" in data['reply'].lower()

    await db_session.delete(app_other)
    await db_session.commit()


@pytest.mark.asyncio
async def test_chat_multiple_references(client: AsyncClient, db_session: AsyncSession):
    await seed_test_data(db_session)

    login_res = await client.post('/api/auth/login', json={'email': 'citizen@example.com', 'password': 'password123'})
    token = login_res.json()['access_token']
    headers = {'Authorization': f'Bearer {token}'}
    me_res = await client.get('/api/auth/me', headers=headers)
    user_id = me_res.json()['id']

    payload = {
        'citizen_id': user_id,
        'message': 'Prepare SEVA-111111 and SEVA-222222 for submission.'
    }
    res = await client.post('/api/chat', json=payload, headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()

    assert data['application_id'] is None
    assert 'multiple application numbers' in data['reply'].lower()


@pytest.mark.asyncio
async def test_chat_punctuation_reference(client: AsyncClient, db_session: AsyncSession):
    await seed_test_data(db_session)

    login_res = await client.post('/api/auth/login', json={'email': 'citizen@example.com', 'password': 'password123'})
    token = login_res.json()['access_token']
    headers = {'Authorization': f'Bearer {token}'}
    me_res = await client.get('/api/auth/me', headers=headers)
    user_id = me_res.json()['id']

    res_s1 = await db_session.execute(select(Service).where(Service.code == 'income_certificate'))
    service1 = res_s1.scalar_one()

    app_punct = Application(application_number='SEVA-123456', user_id=uuid.UUID(user_id), service_id=service1.id, status='READY_FOR_REVIEW')
    db_session.add(app_punct)
    await db_session.commit()

    payload = {
        'citizen_id': user_id,
        'message': 'Please submit SEVA-123456.'
    }
    res = await client.post('/api/chat', json=payload, headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()

    assert data['application_id'] == str(app_punct.id)
    assert data['status'] == 'CONSENT_REQUIRED'

    await db_session.delete(app_punct)
    await db_session.commit()


@pytest.mark.asyncio
async def test_chat_field_persistence_and_loop_prevention(client: AsyncClient, db_session: AsyncSession):
    """
    Regression test proving:
    - a valid chat-answerable field is saved to Application.form_data
    - missing_fields changes after saving
    - the chatbot does not repeat the same question forever
    """
    await seed_test_data(db_session)

    login_res = await client.post('/api/auth/login', json={'email': 'citizen@example.com', 'password': 'password123'})
    token = login_res.json()['access_token']
    headers = {'Authorization': f'Bearer {token}'}
    me_res = await client.get('/api/auth/me', headers=headers)
    user_id = me_res.json()['id']

    # Step 1: Create an active application for income_certificate
    res_s = await db_session.execute(select(Service).where(Service.code == 'income_certificate'))
    service = res_s.scalar_one()

    app = Application(
        application_number='SEVA-998877',
        user_id=uuid.UUID(user_id),
        service_id=service.id,
        status='MISSING_INFORMATION',
        form_data={}
    )
    db_session.add(app)
    await db_session.commit()

    # Step 2: Citizen provides annual_income via chat
    payload1 = {
        'citizen_id': user_id,
        'application_id': str(app.id),
        'message': 'My annual income is 150000'
    }
    res1 = await client.post('/api/chat', json=payload1, headers=headers)
    assert res1.status_code == 200, res1.text
    data1 = res1.json()

    # Verify field persisted in DB
    await db_session.refresh(app)
    assert app.form_data is not None
    assert app.form_data.get('annual_income') == '150000'

    # Verify missing_fields changed (annual_income is no longer missing)
    assert 'annual_income' not in data1.get('required_fields', [])
    assert 'annual_income' not in (data1.get('missing_fields') or [])
    assert 'occupation' in data1['reply'].lower() or 'occupation' in data1.get('required_fields', [])
    assert '150000' in data1['reply'] or 'saved' in data1['reply'].lower() or 'recorded' in data1['reply'].lower()

    # Step 3: Citizen provides occupation via chat
    payload2 = {
        'citizen_id': user_id,
        'application_id': str(app.id),
        'message': 'My occupation is farmer'
    }
    res2 = await client.post('/api/chat', json=payload2, headers=headers)
    assert res2.status_code == 200, res2.text
    data2 = res2.json()

    # Verify second field persisted in DB
    await db_session.refresh(app)
    assert app.form_data.get('occupation') == 'Farmer'

    # Verify all required fields for income certificate are now satisfied!
    assert 'annual_income' not in (data2.get('missing_fields') or [])
    assert 'occupation' not in (data2.get('missing_fields') or [])
    # Chatbot does NOT repeat asking for annual income or occupation
    assert 'please provide your annual income' not in data2['reply'].lower()
    assert 'please provide your occupation' not in data2['reply'].lower()

    # Clean up
    await db_session.delete(app)
    await db_session.commit()


@pytest.mark.asyncio
async def test_chat_field_annual_income_repeat_question_prevention(client: AsyncClient, db_session: AsyncSession):
    """
    Focused regression test for repeating-question bug:
    Turn 1: 'I want an Income Certificate'
    Turn 2: 'My annual income is 50000'
    Turn 3: '50000'
    Asserts:
    - Application created
    - annual_income persisted
    - annual_income is NOT in missing_fields / required_fields
    - Chatbot does NOT repeat asking for annual income
    - Application ID remains present across turns
    - Turn 3 does not corrupt or overwrite satisfied annual_income
    - Next legitimate missing field ('occupation') is requested
    """
    await seed_test_data(db_session)

    login_res = await client.post('/api/auth/login', json={'email': 'citizen@example.com', 'password': 'password123'})
    token = login_res.json()['access_token']
    headers = {'Authorization': f'Bearer {token}'}
    me_res = await client.get('/api/auth/me', headers=headers)
    user_id = me_res.json()['id']

    # Turn 1: Citizen initiates Income Certificate
    res1 = await client.post('/api/chat', json={
        'citizen_id': user_id,
        'message': 'I want an Income Certificate'
    }, headers=headers)
    assert res1.status_code == 200, res1.text
    data1 = res1.json()
    app_id = data1.get('application_id')
    assert app_id is not None
    assert data1['service_code'] == 'income_certificate'

    # Turn 2: Citizen provides annual income
    res2 = await client.post('/api/chat', json={
        'citizen_id': user_id,
        'application_id': app_id,
        'message': 'My annual income is 50000'
    }, headers=headers)
    assert res2.status_code == 200, res2.text
    data2 = res2.json()

    # Application ID preserved
    assert data2.get('application_id') == app_id

    # Verify annual_income persisted in DB
    app_res = await db_session.execute(select(Application).where(Application.id == uuid.UUID(app_id)))
    app = app_res.scalar_one()
    assert app.form_data is not None
    assert app.form_data.get('annual_income') == '50000'

    # annual_income NOT in missing_fields / required_fields
    assert 'annual_income' not in (data2.get('missing_fields') or [])
    assert 'annual_income' not in data2.get('required_fields', [])

    # Chatbot does NOT ask for annual income again, but advances to occupation
    assert 'please provide your annual income' not in data2['reply'].lower()
    assert 'occupation' in data2['reply'].lower() or 'occupation' in data2.get('required_fields', [])

    # Turn 3: Citizen sends '50000' (standalone number)
    res3 = await client.post('/api/chat', json={
        'citizen_id': user_id,
        'application_id': app_id,
        'message': '50000'
    }, headers=headers)
    assert res3.status_code == 200, res3.text
    data3 = res3.json()

    # Application ID preserved
    assert data3.get('application_id') == app_id

    # Verify annual_income was NOT corrupted
    await db_session.refresh(app)
    assert app.form_data.get('annual_income') == '50000'

    # Chatbot still does not ask for annual income and asks for occupation
    assert 'please provide your annual income' not in data3['reply'].lower()
    assert 'occupation' in data3['reply'].lower()
    assert 'annual_income' not in (data3.get('missing_fields') or [])

    # Clean up
    await db_session.delete(app)
    await db_session.commit()


@pytest.mark.asyncio
async def test_chat_ocr_only_fields_cannot_be_satisfied_via_chat(client: AsyncClient, db_session: AsyncSession):
    """
    Regression test proving:
    - OCR/document-only fields (e.g. date_of_birth, applicant_name) cannot be satisfied by arbitrary chat text
    - update_application_field explicitly rejects document/OCR-only fields
    - Chat response informs citizen that official document upload is required
    """
    from app.agent.tools import update_application_field

    await seed_test_data(db_session)

    login_res = await client.post('/api/auth/login', json={'email': 'citizen@example.com', 'password': 'password123'})
    token = login_res.json()['access_token']
    headers = {'Authorization': f'Bearer {token}'}
    me_res = await client.get('/api/auth/me', headers=headers)
    user_id = me_res.json()['id']

    res_s = await db_session.execute(select(Service).where(Service.code == 'birth_certificate'))
    service = res_s.scalar_one()

    app = Application(
        application_number='SEVA-887766',
        user_id=uuid.UUID(user_id),
        service_id=service.id,
        status='COLLECTING_DOCUMENTS',
        form_data={}
    )
    db_session.add(app)
    await db_session.commit()

    # 1. Direct tool invocation check: update_application_field MUST reject document-only fields
    tool_res = await update_application_field(db_session, str(app.id), "date_of_birth", "2000-01-01")
    assert "error" in tool_res
    assert tool_res.get("allowed") is False

    tool_res_name = await update_application_field(db_session, str(app.id), "applicant_name", "Alice Doe")
    assert "error" in tool_res_name
    assert tool_res_name.get("allowed") is False

    # 2. Chat workflow check: citizen typing date of birth does NOT populate form_data
    payload = {
        'citizen_id': user_id,
        'application_id': str(app.id),
        'message': 'My date of birth is 1995-05-12'
    }
    res = await client.post('/api/chat', json=payload, headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()

    # Verify form_data remains empty of date_of_birth
    await db_session.refresh(app)
    assert 'date_of_birth' not in (app.form_data or {})

    # Verify reply explicitly requires document upload
    reply_lower = data['reply'].lower()
    assert 'document' in reply_lower or 'upload' in reply_lower
    assert 'cannot be populated via chat' in reply_lower or 'cannot be accepted via chat' in reply_lower or 'verification required' in reply_lower or 'official document' in reply_lower

    # Clean up
    await db_session.delete(app)
    await db_session.commit()


@pytest.mark.asyncio
async def test_application_ownership_idor_protection(db_session: AsyncSession):
    """
    Security regression test for IDOR protection:
    - Citizen A owns Application A
    - Citizen B attempts to call tool_request_consent, tool_submit_application, or update_application_field
      on Application A
    - Citizen B is strictly rejected
    - Citizen A succeeds
    """
    from app.agent.tools import tool_request_consent, tool_submit_application, update_application_field
    from app.workflows.engine import ApplicationState

    await seed_test_data(db_session)

    citizen_a_id = uuid.uuid4()
    citizen_b_id = uuid.uuid4()

    user_a = User(id=citizen_a_id, email=f"user_a_{citizen_a_id.hex[:6]}@example.com", password_hash="hash", full_name="User A", role="citizen")
    user_b = User(id=citizen_b_id, email=f"user_b_{citizen_b_id.hex[:6]}@example.com", password_hash="hash", full_name="User B", role="citizen")
    db_session.add_all([user_a, user_b])
    await db_session.flush()

    res_s = await db_session.execute(select(Service).where(Service.code == 'income_certificate'))
    service = res_s.scalar_one()

    # Application owned by Citizen A
    app_a = Application(
        application_number='SEVA-IDOR-001',
        user_id=citizen_a_id,
        service_id=service.id,
        status=ApplicationState.READY_FOR_REVIEW,
        form_data={"annual_income": 50000, "occupation": "Farmer"}
    )
    db_session.add(app_a)
    await db_session.commit()

    # 1. Citizen B (attacker) attempts to request consent for Application A -> MUST FAIL
    res_consent_b = await tool_request_consent(
        db=db_session,
        application_id=str(app_a.id),
        data_requested=["annual_income"],
        requesting_department="Revenue",
        purpose="Verification",
        citizen_id=str(citizen_b_id)
    )
    assert "error" in res_consent_b
    assert "unauthorized" in res_consent_b["error"].lower()

    # Verify status unchanged
    await db_session.refresh(app_a)
    assert app_a.status == ApplicationState.READY_FOR_REVIEW

    # 2. Citizen B attempts to update field on Application A -> MUST FAIL
    res_update_b = await update_application_field(
        db=db_session,
        application_id=str(app_a.id),
        field="annual_income",
        value=999999,
        citizen_id=str(citizen_b_id)
    )
    assert "error" in res_update_b
    assert "unauthorized" in res_update_b["error"].lower()

    # 3. Citizen B attempts to submit Application A -> MUST FAIL
    res_submit_b = await tool_submit_application(
        db=db_session,
        application_id=str(app_a.id),
        citizen_id=str(citizen_b_id)
    )
    assert "error" in res_submit_b
    assert "unauthorized" in res_submit_b["error"].lower()

    # 4. Citizen A (legitimate owner) requests consent -> SUCCEEDS
    res_consent_a = await tool_request_consent(
        db=db_session,
        application_id=str(app_a.id),
        data_requested=["annual_income"],
        requesting_department="Revenue",
        purpose="Verification",
        citizen_id=str(citizen_a_id)
    )
    assert "error" not in res_consent_a
    assert res_consent_a["status"] == ApplicationState.CONSENT_REQUIRED


@pytest.mark.asyncio
async def test_gemini_latency_bounded_and_falls_back(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    """
    Regression test proving:
    - Gemini requests that timeout or fail transiently are bounded by timeout & retry limits
    - Orchestrator cleanly falls back to internal rules engine without hanging
    """
    import asyncio
    from app.agent import orchestrator

    await seed_test_data(db_session)
    login_res = await client.post('/api/auth/login', json={'email': 'citizen@example.com', 'password': 'password123'})
    token = login_res.json()['access_token']
    headers = {'Authorization': f'Bearer {token}'}
    me_res = await client.get('/api/auth/me', headers=headers)
    user_id = me_res.json()['id']

    # Simulate Gemini timing out
    async def mock_timeout_gemini(*args, **kwargs):
        raise asyncio.TimeoutError("Simulated Gemini timeout")

    monkeypatch.setenv("GEMINI_API_KEY", "mock-key-for-test")
    monkeypatch.setattr(orchestrator, "_run_gemini_tool_workflow", mock_timeout_gemini)

    payload = {
        'citizen_id': user_id,
        'message': 'I want an income certificate'
    }

    start = asyncio.get_event_loop().time()
    res = await client.post('/api/chat', json=payload, headers=headers)
    duration = asyncio.get_event_loop().time() - start

    assert res.status_code == 200
    data = res.json()
    assert data["service_code"] == "income_certificate"
    assert "Income Certificate" in data["reply"]
    assert duration < 5.0, f"Request took too long: {duration}s"


