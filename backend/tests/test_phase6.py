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


@pytest.mark.asyncio
async def test_application_audit_scope(db_session: AsyncSession, test_citizen, test_service, client):
    from app.models import AuditLog
    from app.audit import log_audit_event

    # Create User 2
    user2 = User(
        email=f"citizen2_{uuid.uuid4()}@example.com",
        full_name="Citizen Two",
        password_hash="hash",
        role="CITIZEN",
        is_active=True
    )
    db_session.add(user2)
    await db_session.commit()
    await db_session.refresh(user2)

    # Citizen 1 has Application 1
    app1 = Application(
        id=uuid.uuid4(),
        application_number="TEST-APP-AUDIT-1",
        user_id=test_citizen.id,
        service_id=test_service.id,
        status=ApplicationState.COLLECTING_DOCUMENTS
    )
    # Citizen 1 also has Application 2
    app2 = Application(
        id=uuid.uuid4(),
        application_number="TEST-APP-AUDIT-2",
        user_id=test_citizen.id,
        service_id=test_service.id,
        status=ApplicationState.COLLECTING_DOCUMENTS
    )
    db_session.add_all([app1, app2])
    await db_session.commit()

    # Log audit events for Application 1
    await log_audit_event(
        db_session, actor_type="CITIZEN", action="CREATE_APPLICATION",
        resource_type="application", resource_id=str(app1.id),
        user_id=test_citizen.id, details={"app": "1"}
    )
    await log_audit_event(
        db_session, actor_type="SYSTEM", action="DOCUMENTS_REQUIRED",
        resource_type="application", resource_id=str(app1.id),
        user_id=test_citizen.id, details={"app": "1"}
    )

    # Log audit events for Application 2
    await log_audit_event(
        db_session, actor_type="CITIZEN", action="CREATE_APPLICATION",
        resource_type="application", resource_id=str(app2.id),
        user_id=test_citizen.id, details={"app": "2"}
    )
    await log_audit_event(
        db_session, actor_type="SYSTEM", action="WORKFLOW_STATE_CHANGE",
        resource_type="application", resource_id=str(app2.id),
        user_id=test_citizen.id, details={"app": "2"}
    )
    await db_session.commit()

    token1 = create_access_token({"sub": str(test_citizen.id)})
    token2 = create_access_token({"sub": str(user2.id)})

    # 1. GET /api/applications/{app1.id}/audit MUST return ONLY App 1 logs (2 logs, none for App 2)
    res1 = await client.get(
        f"/api/applications/{app1.id}/audit",
        headers={"Authorization": f"Bearer {token1}"}
    )
    assert res1.status_code == 200, res1.text
    logs1 = res1.json()
    assert len(logs1) == 2
    for log in logs1:
        assert log["resource_id"] == str(app1.id)
        assert log["resource_id"] != str(app2.id)

    # 2. Accessing App 1 as Citizen 2 MUST return 403 Forbidden
    res_forbidden = await client.get(
        f"/api/applications/{app1.id}/audit",
        headers={"Authorization": f"Bearer {token2}"}
    )
    assert res_forbidden.status_code == 403

    # 3. Accessing non-existent application MUST return 404
    non_existent = uuid.uuid4()
    res_not_found = await client.get(
        f"/api/applications/{non_existent}/audit",
        headers={"Authorization": f"Bearer {token1}"}
    )
    assert res_not_found.status_code == 404

