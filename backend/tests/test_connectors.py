import pytest
import uuid
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.testclient import TestClient

from app.models import User, Service, Application, Document, ApplicationEvent
from app.connectors.registry import get_connector
from app.connectors.base import GovernmentConnector
from app.workflows.engine import ApplicationState
from app.agent.tools import tool_submit_application
from app.main import app
import httpx

@pytest.fixture
async def connector_user(db_session: AsyncSession) -> User:
    user = User(
        email=f"connector_{uuid.uuid4()}@example.com",
        password_hash="hashed_password",
        full_name="Connector User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

@pytest.fixture
async def connector_service(db_session: AsyncSession) -> Service:
    service = Service(
        code="income_certificate",
        title="Income Certificate",
        department="revenue",
        required_documents=["id_proof"],
        required_fields=["name"],
    )
    db_session.add(service)
    await db_session.commit()
    await db_session.refresh(service)
    return service


def test_mock_api_revenue():
    client = TestClient(app)
    # Test submit
    resp = client.post("/mock/revenue/submit", json={"application_id": "test", "form_data": {}, "documents": []})
    assert resp.status_code == 200
    data = resp.json()
    assert "reference_id" in data
    assert data["reference_id"].startswith("REV-2026-")
    assert data["status"] == "SUBMITTED"
    ref_id = data["reference_id"]
    
    # Test status
    resp = client.get(f"/mock/revenue/status/{ref_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "SUBMITTED"
    
    # Test admin advance
    resp = client.post(f"/mock/revenue/admin/advance-status/{ref_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "UNDER_REVIEW"


@pytest.mark.asyncio
async def test_get_connector():
    c = get_connector("income_certificate")
    assert isinstance(c, GovernmentConnector)
    
    with pytest.raises(ValueError):
        get_connector("invalid_code")


@pytest.mark.asyncio
async def test_submit_application_idempotency(db_session: AsyncSession, connector_user: User, connector_service: Service):
    app_record = Application(
        application_number=f"APP-{uuid.uuid4()}",
        user_id=connector_user.id,
        service_id=connector_service.id,
        status=ApplicationState.SUBMITTED,
        government_reference="REV-2026-TEST1"
    )
    db_session.add(app_record)
    await db_session.commit()
    await db_session.refresh(app_record)
    
    res = await tool_submit_application(db_session, str(app_record.id))
    assert res["status"] == ApplicationState.SUBMITTED
    assert res["government_reference"] == "REV-2026-TEST1"
    assert "already submitted" in res.get("message", "")


@pytest.mark.asyncio
async def test_submit_application_without_consent_fails(db_session: AsyncSession, connector_user: User, connector_service: Service):
    app_record = Application(
        application_number=f"APP-{uuid.uuid4()}",
        user_id=connector_user.id,
        service_id=connector_service.id,
        status=ApplicationState.READY_FOR_REVIEW,
    )
    db_session.add(app_record)
    await db_session.commit()
    await db_session.refresh(app_record)
    
    res = await tool_submit_application(db_session, str(app_record.id))
    assert "error" in res
    assert "No approved consent found" in res["error"]
