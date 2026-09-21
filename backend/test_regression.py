import asyncio
import httpx
from httpx import AsyncClient
import uuid

async def create_user_and_login(client: AsyncClient):
    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    await client.post("/api/auth/signup", json={
        "email": email,
        "password": "password123",
        "full_name": "Test User",
        "phone_number": "1234567890"
    })
    res = await client.post("/api/auth/login", json={"email": email, "password": "password123"})
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me = await client.get("/api/auth/me", headers=headers)
    return headers, me.json()["id"]

async def run_flow(client: AsyncClient, headers: dict, user_id: str, init_msg: str, expected_service: str, expected_docs: list):
    res = await client.post("/api/chat", json={"citizen_id": user_id, "message": init_msg}, headers=headers)
    app_id = res.json()["application_id"]
    status = res.json()["status"]
    
    print(f"Service {expected_service} - Created application: {app_id}, Status: {status}")
    assert status == "COLLECTING_DOCUMENTS", f"Failed start {expected_service} (status: {status})"

    for i, doc_type in enumerate(expected_docs):
        with open("../test_data/test.pdf", "rb") as f:
            files = {"file": ("test.pdf", f, "application/pdf")}
            data = {"document_type": doc_type, "citizen_id": user_id, "application_id": app_id}
            await client.post("/api/documents/upload", data=data, files=files, headers=headers)
            
        res = await client.get(f"/api/applications/{app_id}", headers=headers)
        status = res.json()["status"]
        print(f"Uploaded {doc_type}, Status: {status}")

    assert status == "READY_FOR_REVIEW", f"Failed ready {expected_service}, ended in {status}"
    print(f"{expected_service} PASSED")

async def run_regression():
    async with AsyncClient(base_url="http://localhost:8000") as client:
        print("--- INCOME CERTIFICATE ---")
        headers, user_id = await create_user_and_login(client)
        await run_flow(client, headers, user_id, "I need an income certificate", "income_certificate", ["identity_proof", "address_proof", "income_proof"])
        
        print("--- BIRTH CERTIFICATE ---")
        headers, user_id = await create_user_and_login(client)
        await run_flow(client, headers, user_id, "I need a birth certificate", "birth_certificate", ["hospital_certificate", "parent_identity_proof"])
        
        print("--- DRIVING LICENCE ---")
        headers, user_id = await create_user_and_login(client)
        await run_flow(client, headers, user_id, "I need a driving licence", "driving_license", ["identity_proof", "address_proof", "photograph", "medical_declaration"])

        print("ALL REGRESSIONS PASSED")

if __name__ == "__main__":
    asyncio.run(run_regression())
