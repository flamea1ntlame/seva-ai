import pytest
import uuid
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.testclient import TestClient

from app.models import User, Service, Application, Document, ApplicationEvent
from app.workflows.engine import WorkflowEngine, ApplicationState
from app.main import app

@pytest.fixture
async def workflow_user(db_session: AsyncSession) -> User:
    user = User(
        email=f"workflow_{uuid.uuid4()}@example.com",
        password_hash="hashed_password",
        full_name="Workflow User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

@pytest.fixture
async def workflow_service(db_session: AsyncSession) -> Service:
    service = Service(
        code=f"srv_{uuid.uuid4()}",
        title="Test Workflow Service",
        department="test_dept",
        required_documents=["id_proof", "address_proof"],
        required_fields=["name", "dob"],
        processing_time_days=10,
        fee_amount=100.0,
    )
    db_session.add(service)
    await db_session.commit()
    await db_session.refresh(service)
    return service


@pytest.mark.asyncio
async def test_workflow_engine_missing_docs(db_session: AsyncSession, workflow_user: User, workflow_service: Service):
    app_record = Application(
        application_number=f"APP-{uuid.uuid4()}",
        user_id=workflow_user.id,
        service_id=workflow_service.id,
        status=ApplicationState.DISCOVER,
    )
    db_session.add(app_record)
    await db_session.commit()
    await db_session.refresh(app_record)

    engine = WorkflowEngine(db_session)
    status = await engine.advance_application(app_record.id)
    
    assert status == ApplicationState.COLLECTING_DOCUMENTS
    await db_session.refresh(app_record)
    assert app_record.status == ApplicationState.COLLECTING_DOCUMENTS


@pytest.mark.asyncio
async def test_workflow_engine_extracting(db_session: AsyncSession, workflow_user: User, workflow_service: Service):
    app_record = Application(
        application_number=f"APP-{uuid.uuid4()}",
        user_id=workflow_user.id,
        service_id=workflow_service.id,
        status=ApplicationState.COLLECTING_DOCUMENTS,
    )
    db_session.add(app_record)
    
    # Add documents but pending
    doc1 = Document(user_id=workflow_user.id, document_type="id_proof", title="ID", file_path="path", verification_status="PENDING", verified=False)
    doc2 = Document(user_id=workflow_user.id, document_type="address_proof", title="ADDR", file_path="path2", verification_status="VERIFIED", verified=True, extracted_data={"name": "Test"})
    db_session.add_all([doc1, doc2])
    
    await db_session.commit()
    await db_session.refresh(app_record)

    engine = WorkflowEngine(db_session)
    status = await engine.advance_application(app_record.id)
    
    assert status == ApplicationState.EXTRACTING
    await db_session.refresh(app_record)
    assert app_record.status == ApplicationState.EXTRACTING


@pytest.mark.asyncio
async def test_workflow_engine_missing_fields(db_session: AsyncSession, workflow_user: User, workflow_service: Service):
    app_record = Application(
        application_number=f"APP-{uuid.uuid4()}",
        user_id=workflow_user.id,
        service_id=workflow_service.id,
        status=ApplicationState.EXTRACTING,
    )
    db_session.add(app_record)
    
    # Add verified docs but missing dob
    doc1 = Document(user_id=workflow_user.id, document_type="id_proof", title="ID", file_path="path", verification_status="VERIFIED", verified=True, extracted_data={"name": "Test"})
    doc2 = Document(user_id=workflow_user.id, document_type="address_proof", title="ADDR", file_path="path2", verification_status="VERIFIED", verified=True)
    db_session.add_all([doc1, doc2])
    
    await db_session.commit()
    await db_session.refresh(app_record)

    engine = WorkflowEngine(db_session)
    status = await engine.advance_application(app_record.id)
    
    assert status == ApplicationState.MISSING_INFORMATION
    await db_session.refresh(app_record)
    assert app_record.status == ApplicationState.MISSING_INFORMATION


@pytest.mark.asyncio
async def test_workflow_engine_ready_for_review(db_session: AsyncSession, workflow_user: User, workflow_service: Service):
    app_record = Application(
        application_number=f"APP-{uuid.uuid4()}",
        user_id=workflow_user.id,
        service_id=workflow_service.id,
        status=ApplicationState.MISSING_INFORMATION,
    )
    db_session.add(app_record)
    
    # Add verified docs with all required fields
    doc1 = Document(user_id=workflow_user.id, document_type="id_proof", title="ID", file_path="path", verification_status="VERIFIED", verified=True, extracted_data={"name": "Test", "dob": "1990-01-01"})
    doc2 = Document(user_id=workflow_user.id, document_type="address_proof", title="ADDR", file_path="path2", verification_status="VERIFIED", verified=True)
    db_session.add_all([doc1, doc2])
    
    await db_session.commit()
    await db_session.refresh(app_record)

    engine = WorkflowEngine(db_session)
    status = await engine.advance_application(app_record.id)
    
    assert status == ApplicationState.READY_FOR_REVIEW
    await db_session.refresh(app_record)
    assert app_record.status == ApplicationState.READY_FOR_REVIEW
