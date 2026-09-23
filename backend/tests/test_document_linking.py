import pytest
import uuid
import asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.main import app
from app.models import User, Application, Document, Consent, Service
from app.workflows.engine import WorkflowEngine, ApplicationState
from app.database import Base


@pytest.fixture
async def sample_service(db_session):
    service = Service(
        id=uuid.uuid4(),
        code="TEST_LINKING",
        title="Test Linking Service",
        department="Test Dept",
        required_documents=["identity_proof", "income_proof"],
        required_fields=["full_name", "annual_income"]
    )
    db_session.add(service)
    await db_session.commit()
    await db_session.refresh(service)
    return service

@pytest.fixture
async def sample_user(db_session):
    user = User(
        id=uuid.uuid4(),
        email="test_linking@example.com",
        password_hash="hash",
        full_name="Test User",
        role="citizen"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

@pytest.mark.asyncio
async def test_document_linking_and_form_data(db_session, sample_service, sample_user):
    # Setup two documents of the same type
    doc1 = Document(
        id=uuid.uuid4(),
        user_id=sample_user.id,
        document_type="identity_proof",
        title="Old ID",
        file_path="old.pdf",
        verification_status="VERIFIED",
        extracted_data={"full_name": "Old Name", "dob": "1990-01-01"}
    )
    doc2 = Document(
        id=uuid.uuid4(),
        user_id=sample_user.id,
        document_type="identity_proof",
        title="New ID",
        file_path="new.pdf",
        verification_status="VERIFIED",
        extracted_data={"full_name": "New Name", "dob": "1990-01-01"}
    )
    doc3 = Document(
        id=uuid.uuid4(),
        user_id=sample_user.id,
        document_type="income_proof",
        title="Income",
        file_path="inc.pdf",
        verification_status="VERIFIED",
        extracted_data={"annual_income": "50000"}
    )
    
    # Unauthorized document (belongs to another user)
    other_user_id = uuid.uuid4()
    doc_unauth = Document(
        id=uuid.uuid4(),
        user_id=other_user_id,
        document_type="income_proof",
        title="Secret Income",
        file_path="secret.pdf",
        verification_status="VERIFIED",
        extracted_data={"annual_income": "1000000"}
    )
    
    db_session.add_all([doc1, doc2, doc3, doc_unauth])
    await db_session.commit()
    
    # Create application with pre-existing form_data
    app1 = Application(
        id=uuid.uuid4(),
        application_number="TEST-APP-1",
        user_id=sample_user.id,
        service_id=sample_service.id,
        status="DISCOVER",
        form_data={"full_name": "Explicit Name", "notes": "Pre-existing"}
    )
    db_session.add(app1)
    await db_session.commit()
    
    # Run workflow engine
    engine = WorkflowEngine(db_session)
    new_status = await engine.advance_application(app1.id)
    assert new_status == ApplicationState.READY_FOR_REVIEW
    
    # Reload application with linked_documents
    result = await db_session.execute(
        select(Application).options(selectinload(Application.linked_documents)).where(Application.id == app1.id)
    )
    app1_reloaded = result.scalar_one()
    
    # Verify EXACT document selection (one of each required type)
    assert len(app1_reloaded.linked_documents) == 2
    doc_types = {d.document_type for d in app1_reloaded.linked_documents}
    assert doc_types == {"identity_proof", "income_proof"}
    
    # Verify form data merging precedence
    form_data = app1_reloaded.form_data
    assert form_data["notes"] == "Pre-existing" # Preserved
    assert form_data["full_name"] == "Explicit Name" # Precedence over extracted 'New Name' or 'Old Name'
    assert form_data["dob"] == "1990-01-01" # Filled missing
    assert form_data["annual_income"] == "50000" # Filled missing
    
    # Verify unauthorized document was not surfaced
    doc_ids = {d.id for d in app1_reloaded.linked_documents}
    assert doc_unauth.id not in doc_ids
    
    # Multi-application isolation
    app2 = Application(
        id=uuid.uuid4(),
        application_number="TEST-APP-2",
        user_id=sample_user.id,
        service_id=sample_service.id,
        status="DISCOVER",
        form_data={}
    )
    db_session.add(app2)
    await db_session.commit()
    await engine.advance_application(app2.id)
    
    result2 = await db_session.execute(
        select(Application).options(selectinload(Application.linked_documents)).where(Application.id == app2.id)
    )
    app2_reloaded = result2.scalar_one()
    assert len(app2_reloaded.linked_documents) == 2
    
    # Now simulate consent
    from app.agent.tools import tool_request_consent
    consent_res = await tool_request_consent(
        db_session, 
        application_id=str(app1.id), 
        data_requested=["all"], 
        requesting_department="Test", 
        purpose="Test Purpose"
    )
    assert "error" not in consent_res
    
    consent_id = consent_res["consent_id"]
    result3 = await db_session.execute(select(Consent).where(Consent.id == uuid.UUID(consent_id)))
    consent = result3.scalar_one()
    
    # Refetch app to avoid MissingGreenlet after commit
    result4 = await db_session.execute(
        select(Application).options(selectinload(Application.linked_documents)).where(Application.id == app1.id)
    )
    app1_refetched = result4.scalar_one()
    
    snapshot_doc_ids = {uuid.UUID(d["id"]) for d in consent.data_snapshot["documents"]}
    linked_doc_ids = {d.id for d in app1_refetched.linked_documents}
    assert snapshot_doc_ids == linked_doc_ids
    
    from datetime import datetime
    
    # Upload a new document to change the selected document ID and trigger invalidation
    doc4 = Document(
        id=uuid.uuid4(),
        user_id=sample_user.id,
        document_type="income_proof",
        title="New Income",
        file_path="new_inc.pdf",
        verification_status="VERIFIED",
        extracted_data={"annual_income": "60000"},
        created_at=datetime.utcnow()
    )
    db_session.add(doc4)
    await db_session.commit()
    
    # Re-run engine
    await engine.advance_application(app1.id)
    await db_session.refresh(consent)
    # The consent should be invalidated because data_snapshot doesn't match new current_data
    assert consent.status == "DENIED"

