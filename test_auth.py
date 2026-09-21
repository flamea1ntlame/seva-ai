import asyncio
import httpx

async def main():
    async with httpx.AsyncClient() as client:
        # Try login
        r = await client.post("http://localhost:8000/api/auth/login", json={
            "email": "citizen@example.com",
            "password": "password123"
        })
        print("Login status:", r.status_code)
        print("Login response:", r.text)
        
        if r.status_code == 200:
            token = r.json()["access_token"]
            r2 = await client.get("http://localhost:8000/api/auth/me", headers={
                "Authorization": f"Bearer {token}"
            })
            print("Me status:", r2.status_code)
            print("Me response:", r2.text)

asyncio.run(main())
