import asyncio
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

from app.database import AsyncSessionLocal
from app.models import User
from sqlalchemy import select
from httpx import AsyncClient

async def test():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(User).where(User.email == "citizen@example.com"))
        user = res.scalar_one()
        user_id = str(user.id)
        
    async with AsyncClient() as client:
        # Simulate chat endpoint to create DL
        res = await client.post("http://localhost:8000/api/chat", json={
            "message": "I want a Driving Licence",
            "citizen_id": user_id
        })
        print("Chat Response:", res.json())
        app_id = res.json().get("application_id")
        
        # Verify app created
        print("Created App ID:", app_id)
        
if __name__ == "__main__":
    asyncio.run(test())
