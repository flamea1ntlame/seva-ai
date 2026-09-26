import pytest
import uuid
import re
from unittest.mock import AsyncMock, patch

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import Service, User, Application
from app.agent.tools import tool_create_application
from google.genai import types

@pytest.fixture
async def test_user(db_session: AsyncSession):
    user = User(
        email="test@example.com",
        full_name="Test User",
        password_hash="hashed_password",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

class FakeFunctionCall:
    def __init__(self, name, args):
        self.name = name
        self.args = args

class FakePart:
    def __init__(self, text="", function_call=None):
        self.text = text
        self.function_call = function_call

class FakeContent:
    def __init__(self, parts):
        self.parts = parts

class FakeCandidate:
    def __init__(self, parts):
        self.content = FakeContent(parts)

class FakeModelResponse:
    def __init__(self, text="", function_calls=None):
        self.text = text
        self.function_calls = function_calls or []
        parts = []
        if text:
            parts.append(FakePart(text=text))
        if self.function_calls:
            for fc in self.function_calls:
                parts.append(FakePart(function_call=fc))
        self.candidates = [FakeCandidate(parts)]

class FakeModels:
    def __init__(self, client):
        self.client = client
        
    async def generate_content(self, model, contents, config):
        if self.client.call_count < len(self.client.responses):
            resp = self.client.responses[self.client.call_count]
            self.client.call_count += 1
            return resp
        return FakeModelResponse(text="Fallback response")

class FakeAIO:
    def __init__(self, client):
        self.models = FakeModels(client)

class FakeClient:
    def __init__(self, responses, *args, **kwargs):
        self.responses = responses
        self.call_count = 0
        self.aio = FakeAIO(self)
    
    def __call__(self, *args, **kwargs):
        return self

@pytest.mark.asyncio
async def test_a_create_application_succeeds(db_session: AsyncSession, test_user: User):
    service = Service(
        code="test_service",
        title="Test Service",
        department="Revenue",
        required_documents=[],
        required_fields=[]
    )
    db_session.add(service)
    await db_session.commit()

    result = await tool_create_application(db_session, "test_service", str(test_user.id))
    
    assert "error" not in result
    assert "application_id" in result
    assert "application_number" in result
    assert result["application_number"].startswith("SEVA-")

@pytest.mark.asyncio
async def test_b_create_application_fails_service_not_found(db_session: AsyncSession, test_user: User):
    result = await tool_create_application(db_session, "invalid_service", str(test_user.id))
    
    assert "error" in result
    assert "application_id" not in result

@pytest.mark.asyncio
async def test_c_orchestrator_prevents_hallucination(db_session: AsyncSession, test_user: User):
    responses = [
        FakeModelResponse(function_calls=[
            FakeFunctionCall(name="create_application", args={"service_code": "non_existent_service", "citizen_id": str(test_user.id)})
        ]),
        FakeModelResponse(text="I have created your application. Application Reference ID: SEVA-999999. Status: READY_FOR_REVIEW")
    ]
    
    model_patcher = patch('google.genai.Client', return_value=FakeClient(responses))
    model_patcher.start()
    
    try:
        from app.agent.orchestrator import _run_gemini_tool_workflow
        result = await _run_gemini_tool_workflow(
            message="Apply for non existent service",
            citizen_id=str(test_user.id),
            db=db_session,
            api_key="fake",
            model_name="fake",
            app_context_str=""
        )
        
        assert result.get("application_id") is None
        assert result.get("status") is None
    finally:
        model_patcher.stop()

@pytest.mark.asyncio
async def test_d_successful_creation_propagation(db_session: AsyncSession, test_user: User):
    service = Service(
        code="test_service_2",
        title="Test Service 2",
        department="Revenue",
        required_documents=[],
        required_fields=[]
    )
    db_session.add(service)
    await db_session.commit()

    responses = [
        FakeModelResponse(function_calls=[
            FakeFunctionCall(name="create_application", args={"service_code": "test_service_2", "citizen_id": str(test_user.id)})
        ]),
        FakeModelResponse(text="Application created.")
    ]
    
    model_patcher = patch('google.genai.Client', return_value=FakeClient(responses))
    model_patcher.start()
    
    try:
        from app.agent.orchestrator import _run_gemini_tool_workflow
        result = await _run_gemini_tool_workflow(
            message="Apply for test service 2",
            citizen_id=str(test_user.id),
            db=db_session,
            api_key="fake",
            model_name="fake",
            app_context_str=""
        )
        
        assert result.get("application_id") is not None
        assert result.get("status") == "READY_FOR_REVIEW"
    finally:
        model_patcher.stop()
