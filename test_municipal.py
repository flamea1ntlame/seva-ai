import asyncio
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

from app.database import AsyncSessionLocal
from app.models import Application, User, Service
from sqlalchemy import select
from app.workflows.engine import WorkflowEngine
from app.connectors.registry import get_connector
import uuid

async def test():
    async with AsyncSessionLocal() as db:
        # Get user
        res = await db.execute(select(User).where(User.email == "citizen@example.com"))
        user = res.scalar_one()
        
        # Get service
        res = await db.execute(select(Service).where(Service.code == "birth_certificate"))
        service = res.scalar_one()
        
        print(f"User: {user.id}, Service: {service.id} ({service.department})")
        
        # Connector
        connector = get_connector(service.code)
        print("Connector:", type(connector))
        
        # Submit
        res = await connector.submit_application({"application_id": "123e4567-e89b-12d3-a456-426614174000"})
        print("Submit Result:", res)
        gov_ref = res["reference_id"]
        
        # Status
        status = await connector.get_status(gov_ref)
        print("Gov Status:", status)
        
        # Advance status via HTTP is easiest, but let's test it
        
if __name__ == "__main__":
    asyncio.run(test())
