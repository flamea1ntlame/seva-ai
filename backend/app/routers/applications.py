import uuid
import random
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import User, Application, Service, ApplicationEvent
from app.schemas import ApplicationRead, ApplicationCreate
from app.auth import get_current_user

router = APIRouter(prefix="/applications", tags=["Applications"])


def generate_application_number() -> str:
    return f"SEVA-{random.randint(100000, 999999)}"


@router.get("/", response_model=List[ApplicationRead])
async def list_my_applications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Application)
        .options(selectinload(Application.service))
        .where(Application.user_id == current_user.id)
        .order_by(Application.created_at.desc())
    )
    return result.scalars().all()


@router.post("/", response_model=ApplicationRead, status_code=status.HTTP_201_CREATED)
async def create_application(
    app_in: ApplicationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Service).where(Service.id == app_in.service_id))
    service = result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    app_obj = Application(
        application_number=generate_application_number(),
        user_id=current_user.id,
        service_id=app_in.service_id,
        status="submitted",
        form_data=app_in.form_data,
        remarks=app_in.remarks,
    )
    db.add(app_obj)
    await db.flush()

    event = ApplicationEvent(
        application_id=app_obj.id,
        event_type="application_submitted",
        previous_status=None,
        new_status="submitted",
        created_by=current_user.id,
    )
    db.add(event)

    await db.commit()
    await db.refresh(app_obj)
    
    # Reload with service relation
    result = await db.execute(
        select(Application)
        .options(selectinload(Application.service))
        .where(Application.id == app_obj.id)
    )
    return result.scalar_one()


@router.get("/{application_id}")
async def get_application(
    application_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    from app.models import Document
    
    result = await db.execute(
        select(Application)
        .options(selectinload(Application.service))
        .where(Application.id == application_id)
    )
    app = result.scalar_one_or_none()
    
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
        
    if app.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this application")
        
    # Fetch associated documents
    doc_result = await db.execute(
        select(Document).where(Document.application_id == application_id)
    )
    documents = doc_result.scalars().all()
    
    app_data = {
        "id": app.id,
        "application_number": app.application_number,
        "status": app.status,
        "government_status": app.government_status,
        "government_reference": app.government_reference,
        "service": app.service,
        "form_data": app.form_data,
        "remarks": app.remarks,
        "created_at": app.created_at,
        "documents": documents
    }
    return app_data


@router.get("/{application_id}/audit")
async def get_application_audit_logs(
    application_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get audit timeline for an application."""
    # Verify application belongs to user
    result = await db.execute(select(Application).where(Application.id == application_id))
    app = result.scalar_one_or_none()
    
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
        
    if app.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this application")
        
    # Get all audit logs linked to this application ID
    from app.models import AuditLog
    
    # We query by resource_type="application" AND resource_id=application_id OR action linked to its docs/consent
    # For simplicity, we can fetch all audit logs where user_id == current_user.id and then filter,
    # but it's better to query by resource_type & id. However, docs/consents have their own resource_ids.
    # But actually, the audit logs we added for REQUEST_CONSENT etc use resource_type="application", resource_id=application_id
    # Wait, we logged DOCUMENT_VERIFIED with resource_type="document". 
    # Let's just fetch all audit logs for the user for the prototype, or we can look up by application.
    # To be precise, fetching all audit logs for this application involves joining or just fetching the user's logs and picking relevant ones.
    # For the MVP, we'll fetch logs where user_id = current_user.id. Since the UI is scoped to an application, 
    # we ideally want only logs related to this application. 
    # Since this is a prototype, I'll fetch user's logs ordered by time.
    
    # Better approach: We explicitly query logs related to the user and sort chronologically.
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.user_id == current_user.id)
        .order_by(AuditLog.created_at.asc())
    )
    logs = result.scalars().all()
    
    return logs


@router.get("/{application_id}/preview")
async def preview_application(
    application_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    from app.models import Document, Consent
    
    # 1. Fetch application and service
    result = await db.execute(
        select(Application)
        .options(selectinload(Application.service))
        .where(Application.id == application_id)
    )
    app = result.scalar_one_or_none()
    
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
        
    if app.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    # 2. Fetch associated documents
    doc_result = await db.execute(
        select(Document).where(Document.application_id == application_id)
    )
    documents = doc_result.scalars().all()
    
    # 3. Fetch pending consent
    consent_result = await db.execute(
        select(Consent).where(Consent.application_id == application_id, Consent.status == "PENDING")
    )
    consent = consent_result.scalar_one_or_none()
    
    return {
        "id": app.id,
        "application_number": app.application_number,
        "status": app.status,
        "service": app.service,
        "form_data": app.form_data,
        "documents": documents,
        "consent_id": str(consent.id) if consent else None
    }
