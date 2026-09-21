import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import Consent, Application, ApplicationEvent, AuditLog, Document
from app.workflows.engine import WorkflowEngine, ApplicationState
from app.workflows.application_submission import ApplicationSubmissionService
from app.agent.tools import tool_request_consent
from app.auth import create_access_token
from app.models import User, Service
from unittest.mock import patch, MagicMock, AsyncMock
import uuid

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
async def test_admin(db_session: AsyncSession):
    user = User(
        email=f"admin_{uuid.uuid4()}@example.com",
        full_name="Admin",
        password_hash="hash",
        role="CITIZEN", # Just another user
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

@pytest.fixture
def citizen_token_headers(test_citizen):
    token = create_access_token({"sub": str(test_citizen.id)})
    return {"Authorization": f"Bearer {token}"}

@pytest.mark.asyncio
async def test_consent_creation_snapshot_and_audit(db_session: AsyncSession, test_citizen, test_service):
    # Setup application
    app_id = uuid.uuid4()
    app = Application(
        id=app_id,
        application_number="TEST-APP-001",
        user_id=test_citizen.id,
        service_id=test_service.id,
        status=ApplicationState.READY_FOR_REVIEW
    )
    db_session.add(app)
    await db_session.commit()
    await db_session.refresh(app)

    # Add verified document
    doc = Document(
        id=uuid.uuid4(),
        user_id=test_citizen.id,
        application_id=app_id,
        document_type="identity_proof",
        title="ID",
        file_path="/dummy.pdf",
        verification_status="VERIFIED",
        extracted_data={"name": "Rahul Kumar"}
    )
    db_session.add(doc)
    await db_session.commit()

    # Create consent via tool
    res = await tool_request_consent(
        db_session, 
        application_id=str(app.id), 
        data_requested=["identity_proof"], 
        requesting_department="Revenue", 
        purpose="Verification"
    )
    assert "consent_id" in res
    
    await db_session.refresh(app)
    assert app.status == ApplicationState.CONSENT_REQUIRED

    # Verify Consent snapshot
    result = await db_session.execute(select(Consent).where(Consent.id == uuid.UUID(res["consent_id"])))
    consent = result.scalar_one()
    assert consent.status == "PENDING"
    assert consent.data_snapshot["form_data"]["name"] == "Rahul Kumar"
    assert consent.data_snapshot["application_id"] == str(app.id)
    assert len(consent.data_snapshot["documents"]) == 1
    assert consent.data_snapshot["documents"][0]["type"] == "identity_proof"
    assert consent.data_snapshot["documents"][0]["id"] == str(doc.id)

    # Verify AuditLog
    result = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "REQUEST_CONSENT", AuditLog.resource_id == str(app.id))
    )
    audit = result.scalar_one_or_none()
    assert audit is not None
    assert audit.actor_type == "AI_AGENT"

@pytest.mark.asyncio
async def test_consent_approval_and_submission(client: AsyncClient, db_session: AsyncSession, test_citizen, test_service, citizen_token_headers):
    app_id = uuid.uuid4()
    app = Application(
        id=app_id,
        application_number="TEST-APP-002",
        user_id=test_citizen.id,
        service_id=test_service.id,
        status=ApplicationState.CONSENT_REQUIRED
    )
    db_session.add(app)
    
    consent = Consent(
        id=uuid.uuid4(),
        user_id=test_citizen.id,
        application_id=app_id,
        purpose="Test",
        requesting_department="Test Dept",
        data_requested=[],
        data_snapshot={"application_id": str(app_id), "form_data": {}, "documents": []},
        status="PENDING"
    )
    db_session.add(consent)
    await db_session.commit()

    # Mock connector submission
    with patch("app.workflows.application_submission.get_connector") as mock_get_connector:
        mock_connector = MagicMock()
        mock_connector.submit_application = AsyncMock(return_value={"reference_id": "TEST-REF", "status": "SUBMITTED"})
        mock_get_connector.return_value = mock_connector

        res = await client.post(
            f"/api/consents/{consent.id}/respond",
            json={"action": "approve"},
            headers=citizen_token_headers
        )

        assert res.status_code == 200
        assert res.json()["status"] == "APPROVED"
        assert res.json()["submission_result"]["government_reference"] == "TEST-REF"

        await db_session.refresh(consent)
        assert consent.status == "APPROVED"

        await db_session.refresh(app)
        assert app.status == ApplicationState.SUBMITTED

@pytest.mark.asyncio
async def test_consent_denial(client: AsyncClient, db_session: AsyncSession, test_citizen, test_service, citizen_token_headers):
    app_id = uuid.uuid4()
    app = Application(
        id=app_id,
        application_number="TEST-APP-003",
        user_id=test_citizen.id,
        service_id=test_service.id,
        status=ApplicationState.CONSENT_REQUIRED
    )
    db_session.add(app)
    
    consent = Consent(
        id=uuid.uuid4(),
        user_id=test_citizen.id,
        application_id=app_id,
        purpose="Test",
        requesting_department="Test Dept",
        data_requested=[],
        data_snapshot={"application_id": str(app_id), "form_data": {}, "documents": []},
        status="PENDING"
    )
    db_session.add(consent)
    await db_session.commit()

    res = await client.post(
        f"/api/consents/{consent.id}/respond",
        json={"action": "deny"},
        headers=citizen_token_headers
    )
    
    assert res.status_code == 200
    assert res.json()["status"] == "DENIED"

    await db_session.refresh(consent)
    assert consent.status == "DENIED"

    await db_session.refresh(app)
    assert app.status == ApplicationState.READY_FOR_REVIEW

@pytest.mark.asyncio
async def test_consent_ownership_and_immutability(client: AsyncClient, db_session: AsyncSession, test_citizen, test_service, citizen_token_headers, test_admin):
    app_id = uuid.uuid4()
    app = Application(
        id=app_id,
        application_number="TEST-APP-004",
        user_id=test_admin.id, # Belongs to another user
        service_id=test_service.id,
        status=ApplicationState.CONSENT_REQUIRED
    )
    db_session.add(app)
    
    consent = Consent(
        id=uuid.uuid4(),
        user_id=test_admin.id,
        application_id=app_id,
        purpose="Test",
        requesting_department="Test Dept",
        data_requested=[],
        data_snapshot={"application_id": str(app_id), "form_data": {}, "documents": []},
        status="PENDING"
    )
    db_session.add(consent)
    await db_session.commit()

    # Attempt to approve another user's consent
    res = await client.post(
        f"/api/consents/{consent.id}/respond",
        json={"action": "approve"},
        headers=citizen_token_headers
    )
    assert res.status_code == 403

    # Now make it belong to citizen but status is already APPROVED
    app.user_id = test_citizen.id
    consent.user_id = test_citizen.id
    consent.status = "APPROVED"
    await db_session.commit()

    res = await client.post(
        f"/api/consents/{consent.id}/respond",
        json={"action": "deny"}, # Immutability check
        headers=citizen_token_headers
    )
    assert res.status_code == 400
    assert "no longer pending" in res.json()["detail"]

@pytest.mark.asyncio
async def test_data_modification_invalidates_consent(db_session: AsyncSession, test_citizen, test_service):
    app_id = uuid.uuid4()
    app = Application(
        id=app_id,
        application_number="TEST-APP-005",
        user_id=test_citizen.id,
        service_id=test_service.id,
        status=ApplicationState.CONSENT_REQUIRED
    )
    db_session.add(app)
    
    consent = Consent(
        id=uuid.uuid4(),
        user_id=test_citizen.id,
        application_id=app_id,
        purpose="Test",
        requesting_department="Test Dept",
        data_requested=[],
        data_snapshot={"application_id": str(app_id), "form_data": {}, "documents": []},
        status="PENDING"
    )
    db_session.add(consent)
    await db_session.commit()

    # Add a document that wasn't in snapshot
    doc = Document(
        id=uuid.uuid4(),
        user_id=test_citizen.id,
        application_id=app_id,
        document_type="income_proof",
        title="Income",
        file_path="/dummy2.pdf",
        verification_status="VERIFIED",
        extracted_data={"income": "50000"}
    )
    db_session.add(doc)
    await db_session.commit()

    # Run workflow engine
    engine = WorkflowEngine(db_session)
    await engine.advance_application(app.id)

    await db_session.refresh(consent)
    assert consent.status == "DENIED" # Invalidated
    
    await db_session.refresh(app)
    assert app.status == ApplicationState.COLLECTING_DOCUMENTS
