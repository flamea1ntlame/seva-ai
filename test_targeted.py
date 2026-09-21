import asyncio
import httpx
from httpx import AsyncClient

async def run_targeted_test():
    async with AsyncClient(base_url="http://localhost:8000") as client:
        # 1. Login
        res = await client.post("/api/auth/login", json={
            "email": "citizen@example.com",
            "password": "password123"
        })
        token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Fetch user
        me = await client.get("/api/auth/me", headers=headers)
        user_id = me.json()["id"]

        # 2. Create Application (Income Certificate)
        res = await client.post("/api/chat", json={
            "citizen_id": user_id,
            "message": "I need an income certificate"
        }, headers=headers)
        data = res.json()
        app_id = data["application_id"]
        status = data["status"]
        
        print(f"Created application: {app_id}, Status: {status}")
        assert status == "COLLECTING_DOCUMENTS", "Failed test 1"

        # 3. Upload non-final document (identity_proof)
        with open("../test_data/test.pdf", "rb") as f:
            files = {"file": ("test.pdf", f, "application/pdf")}
            data_upload = {
                "document_type": "identity_proof",
                "citizen_id": user_id,
                "application_id": app_id
            }
            res = await client.post("/api/documents/upload", data=data_upload, files=files, headers=headers)
        
        # Check status
        res = await client.get(f"/api/applications/{app_id}", headers=headers)
        status = res.json()["status"]
        print(f"Status after 1 upload: {status}")
        assert status == "COLLECTING_DOCUMENTS", "Failed test 2"

        # 4. Upload final required document (income_proof)
        with open("../test_data/test.pdf", "rb") as f:
            files = {"file": ("test.pdf", f, "application/pdf")}
            data_upload = {
                "document_type": "income_proof",
                "citizen_id": user_id,
                "application_id": app_id
            }
            res = await client.post("/api/documents/upload", data=data_upload, files=files, headers=headers)

        # 5. Upload remaining required document (address_proof)
        with open("../test_data/test.pdf", "rb") as f:
            files = {"file": ("test.pdf", f, "application/pdf")}
            data_upload = {
                "document_type": "address_proof",
                "citizen_id": user_id,
                "application_id": app_id
            }
            res = await client.post("/api/documents/upload", data=data_upload, files=files, headers=headers)
            
        # Check status again
        res = await client.get(f"/api/applications/{app_id}", headers=headers)
        status = res.json()["status"]
        print(f"Status after all uploads: {status}")
        assert status == "READY_FOR_REVIEW", "Failed test 3"
        print("ALL TESTS PASSED")

if __name__ == "__main__":
    asyncio.run(run_targeted_test())
