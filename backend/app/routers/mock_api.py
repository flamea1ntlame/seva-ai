import uuid
import random
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db

router = APIRouter()

# In-memory storage for mock statuses
mock_db: Dict[str, str] = {}

class SubmitRequest(BaseModel):
    application_id: str
    form_data: Dict[str, Any] = {}
    documents: list[Dict[str, str]] = []

async def _advance_status_helper(reference_id: str, db: AsyncSession, department_name: str, reject: bool = False):
    if reference_id not in mock_db:
        raise HTTPException(status_code=404, detail="Reference ID not found")
        
    current = mock_db[reference_id]
    if current == "SUBMITTED":
        new_gov_status = "UNDER_REVIEW"
    elif current == "UNDER_REVIEW":
        new_gov_status = "REJECTED" if reject else "APPROVED"
    else:
        return {"reference_id": reference_id, "status": current}
        
    mock_db[reference_id] = new_gov_status
    
    from app.models import Application, ApplicationEvent, Service
    from app.events import notifier
    from app.workflows.engine import ApplicationState
    
    result = await db.execute(
        select(Application).where(Application.government_reference == reference_id)
    )
    app = result.scalar_one_or_none()
    
    if app:
        app.government_status = new_gov_status
        old_seva_status = app.status
        new_seva_status = app.status
        if new_gov_status in ["APPROVED", "REJECTED"]:
            new_seva_status = ApplicationState.COMPLETED
            app.status = new_seva_status
            
        event = ApplicationEvent(
            application_id=app.id,
            event_type="APPLICATION_STATUS_CHANGED",
            previous_status=old_seva_status,
            new_status=new_seva_status,
            created_by=app.user_id,
        )
        db.add(event)
        
        from app.audit import log_audit_event
        await log_audit_event(
            db, actor_type="SYSTEM", action="STATUS_CHANGED",
            resource_type="application", resource_id=str(app.id), user_id=app.user_id,
            details=f"Government status changed to {new_gov_status}"
        )
        
        # fetch service code
        result_srv = await db.execute(select(Service).where(Service.id == app.service_id))
        srv = result_srv.scalar_one_or_none()
        service_code = srv.code if srv else department_name
        
        await db.commit()
        
        notifier.broadcast(
            user_id=str(app.user_id),
            event="APPLICATION_STATUS_CHANGED",
            application_id=str(app.id),
            data={
                "seva_status": new_seva_status,
                "government_status": new_gov_status,
                "government_reference": reference_id,
                "service_code": service_code
            }
        )
        
    return {"reference_id": reference_id, "status": new_gov_status}

# Revenue Department
revenue_router = APIRouter(prefix="/mock/revenue", tags=["mock-revenue"])

@revenue_router.post("/submit")
async def submit_revenue(data: SubmitRequest):
    reference_id = f"REV-2026-{random.randint(10000, 99999)}"
    mock_db[reference_id] = "SUBMITTED"
    return {"reference_id": reference_id, "status": "SUBMITTED"}

@revenue_router.get("/status/{reference_id}")
async def get_revenue_status(reference_id: str):
    if reference_id not in mock_db:
        raise HTTPException(status_code=404, detail="Reference ID not found")
    return {"reference_id": reference_id, "status": mock_db[reference_id]}

@revenue_router.post("/admin/advance-status/{reference_id}")
async def advance_revenue_status(reference_id: str, reject: bool = False, db: AsyncSession = Depends(get_db)):
    return await _advance_status_helper(reference_id, db, "revenue", reject)


# Municipal Department
municipal_router = APIRouter(prefix="/mock/municipal", tags=["mock-municipal"])

@municipal_router.post("/submit")
async def submit_municipal(data: SubmitRequest):
    reference_id = f"BC-2026-{random.randint(10000, 99999)}"
    mock_db[reference_id] = "SUBMITTED"
    return {"reference_id": reference_id, "status": "SUBMITTED"}

@municipal_router.get("/status/{reference_id}")
async def get_municipal_status(reference_id: str):
    if reference_id not in mock_db:
        raise HTTPException(status_code=404, detail="Reference ID not found")
    return {"reference_id": reference_id, "status": mock_db[reference_id]}

@municipal_router.post("/admin/advance-status/{reference_id}")
async def advance_municipal_status(reference_id: str, reject: bool = False, db: AsyncSession = Depends(get_db)):
    return await _advance_status_helper(reference_id, db, "municipal", reject)


# Transport Department
transport_router = APIRouter(prefix="/mock/transport", tags=["mock-transport"])

@transport_router.post("/submit")
async def submit_transport(data: SubmitRequest):
    reference_id = f"DL-2026-{random.randint(10000, 99999)}"
    mock_db[reference_id] = "SUBMITTED"
    return {"reference_id": reference_id, "status": "SUBMITTED"}

@transport_router.get("/status/{reference_id}")
async def get_transport_status(reference_id: str):
    if reference_id not in mock_db:
        raise HTTPException(status_code=404, detail="Reference ID not found")
    return {"reference_id": reference_id, "status": mock_db[reference_id]}

@transport_router.post("/admin/advance-status/{reference_id}")
async def advance_transport_status(reference_id: str, reject: bool = False, db: AsyncSession = Depends(get_db)):
    return await _advance_status_helper(reference_id, db, "transport", reject)

router.include_router(revenue_router)
router.include_router(municipal_router)
router.include_router(transport_router)
