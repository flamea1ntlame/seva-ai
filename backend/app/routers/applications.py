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
from app.workflows.engine import ApplicationState

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

    initial_status = ApplicationState.COLLECTING_DOCUMENTS
    app_obj = Application(
        application_number=generate_application_number(),
        user_id=current_user.id,
        service_id=app_in.service_id,
        status=initial_status,
        form_data=app_in.form_data or {},
        remarks=app_in.remarks,
    )
    db.add(app_obj)
    await db.flush()

    event = ApplicationEvent(
        application_id=app_obj.id,
        event_type="application_created",
        previous_status=None,
        new_status=initial_status,
        created_by=current_user.id,
    )
    db.add(event)

    from app.audit import log_audit_event
    await log_audit_event(
        db,
        actor_type="CITIZEN",
        action="CREATE_APPLICATION",
        resource_type="application",
        resource_id=str(app_obj.id),
        user_id=current_user.id,
        details={"service_code": service.code}
    )

    await db.commit()
    await db.refresh(app_obj)

    # Advance workflow based on citizen's verified documents/fields
    from app.workflows.engine import WorkflowEngine
    engine = WorkflowEngine(db)
    await engine.advance_application(app_obj.id)
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
        .options(selectinload(Application.service), selectinload(Application.linked_documents))
        .where(Application.id == application_id)
    )
    app = result.scalar_one_or_none()
    
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
        
    if app.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this application")
        
    documents = app.linked_documents
    
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
    result = await db.execute(
        select(Application)
        .options(selectinload(Application.linked_documents))
        .where(Application.id == application_id)
    )
    app = result.scalar_one_or_none()
    
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
        
    if app.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this application")
        
    from app.models import AuditLog, Consent, Document
    from sqlalchemy import or_

    consent_result = await db.execute(
        select(Consent.id).where(Consent.application_id == app.id)
    )
    consent_ids = [str(cid) for cid in consent_result.scalars().all()]

    doc_result = await db.execute(
        select(Document.id).where(Document.application_id == app.id)
    )
    doc_ids = set(str(did) for did in doc_result.scalars().all())
    if app.linked_documents:
        for d in app.linked_documents:
            doc_ids.add(str(d.id))

    app_id_str = str(app.id)
    conditions = [
        (AuditLog.resource_type == "application") & (AuditLog.resource_id == app_id_str)
    ]
    if consent_ids:
        conditions.append(
            (AuditLog.resource_type == "consent") & (AuditLog.resource_id.in_(consent_ids))
        )
    if doc_ids:
        conditions.append(
            (AuditLog.resource_type == "document") & (AuditLog.resource_id.in_(list(doc_ids)))
        )

    result = await db.execute(
        select(AuditLog)
        .where(
            or_(*conditions),
            (AuditLog.user_id == current_user.id) | (AuditLog.user_id.is_(None))
        )
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
        .options(selectinload(Application.service), selectinload(Application.linked_documents))
        .where(Application.id == application_id)
    )
    app = result.scalar_one_or_none()
    
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
        
    if app.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    documents = app.linked_documents
    
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
