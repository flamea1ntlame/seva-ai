import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_signup_login_and_me(client: AsyncClient):
    # 1. Test Signup
    signup_payload = {
        "email": "testuser@example.com",
        "password": "testpassword123",
        "full_name": "Test User",
        "phone_number": "+919999999999"
    }
    response = await client.post("/api/auth/signup", json=signup_payload)
    assert response.status_code == 201, response.text
    user_data = response.json()
    assert user_data["email"] == "testuser@example.com"
    assert user_data["full_name"] == "Test User"
    assert "id" in user_data

    # 2. Test Duplicate Signup
    response_dup = await client.post("/api/auth/signup", json=signup_payload)
    assert response_dup.status_code == 400

    # 3. Test Login
    login_payload = {
        "email": "testuser@example.com",
        "password": "testpassword123"
    }
    response_login = await client.post("/api/auth/login", json=login_payload)
    assert response_login.status_code == 200, response_login.text
    token_data = response_login.json()
    assert "access_token" in token_data
    token = token_data["access_token"]

    # 4. Test GET /api/auth/me (Protected)
    headers = {"Authorization": f"Bearer {token}"}
    response_me = await client.get("/api/auth/me", headers=headers)
    assert response_me.status_code == 200, response_me.text
    me_data = response_me.json()
    assert me_data["email"] == "testuser@example.com"


@pytest.mark.asyncio
async def test_protected_endpoints_unauthorized(client: AsyncClient):
    response_me = await client.get("/api/auth/me")
    assert response_me.status_code == 401

    response_profile = await client.get("/api/profile/me")
    assert response_profile.status_code == 401

    response_docs = await client.get("/api/documents/")
    assert response_docs.status_code == 401

    response_apps = await client.get("/api/applications/")
    assert response_apps.status_code == 401
