import pytest
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Application, User, Consent, Document, Service
from app.workflows.engine import ApplicationState
from app.auth import create_access_token

@pytest.fixture
async def test_citizen(db_session: AsyncSession):
    user = User(
        email=f"citizen_{uuid.uuid4()}@example.com",
        full_name="Citizen",
        password_hash="hash",
        role="CITIZEN",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

@pytest.fixture
async def test_service(db_session: AsyncSession):
    service = Service(
        code="income_certificate",
        title="Income Certificate",
        department="Revenue",
        required_documents=["identity_proof"],
        required_fields=["annual_income"]
    )
    db_session.add(service)
    await db_session.commit()
    await db_session.refresh(service)
    return service


@pytest.mark.asyncio
async def test_vault_stats(db_session: AsyncSession, test_citizen, test_service, client):
    app_id = uuid.uuid4()
    app = Application(
        id=app_id,
        application_number="TEST-APP-PHASE6",
        user_id=test_citizen.id,
        service_id=test_service.id,
        status=ApplicationState.SUBMITTED
    )
    db_session.add(app)
    
    doc1 = Document(
        id=uuid.uuid4(),
        user_id=test_citizen.id,
        application_id=app_id,
        document_type="identity_proof",
        title="ID",
        file_path="/dummy.pdf",
        verification_status="VERIFIED"
    )
    doc2 = Document(
        id=uuid.uuid4(),
        user_id=test_citizen.id,
        application_id=app_id,
        document_type="income_proof",
        title="Income",
        file_path="/dummy.pdf",
        verification_status="PENDING"
    )
    db_session.add_all([doc1, doc2])
    
    consent = Consent(
        id=uuid.uuid4(),
        user_id=test_citizen.id,
        application_id=app_id,
        purpose="Test",
        requesting_department="Test Dept",
        data_requested=[],
        data_snapshot={"fields": {}, "documents": ["identity_proof"]},
        status="APPROVED"
    )
    db_session.add(consent)
    await db_session.commit()
    
    token = create_access_token({"sub": str(test_citizen.id)})
    
    res = await client.get(
        "/api/documents/vault-stats",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 2
    assert data["verified"] == 1
    assert data["shared"] == 1

@pytest.mark.asyncio
async def test_mock_advance_updates_government_status(db_session: AsyncSession, test_citizen, test_service, client):
    app_id = uuid.uuid4()
    app = Application(
        id=app_id,
        application_number="TEST-APP-PHASE6-2",
        user_id=test_citizen.id,
        service_id=test_service.id,
        status=ApplicationState.TRACKING,
        government_reference="REV-TEST-999"
    )
    db_session.add(app)
    await db_session.commit()
    
    from app.routers.mock_api import mock_db
    mock_db["REV-TEST-999"] = "SUBMITTED"
    
    res = await client.post("/mock/revenue/admin/advance-status/REV-TEST-999")
    assert res.status_code == 200
    
    await db_session.refresh(app)
    assert app.government_status == "UNDER_REVIEW"
    assert app.status == ApplicationState.TRACKING
    
    res = await client.post("/mock/revenue/admin/advance-status/REV-TEST-999")
    assert res.status_code == 200
    
    await db_session.refresh(app)
    assert app.government_status == "APPROVED"
    assert app.status == ApplicationState.COMPLETED
