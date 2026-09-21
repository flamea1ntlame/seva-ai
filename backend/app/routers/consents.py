import uuid
from typing import List, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import User, Consent, Application, ApplicationEvent
from app.schemas import ConsentRead, ConsentCreate, ConsentRespond
from app.auth import get_current_user
from app.workflows.engine import ApplicationState
from app.workflows.application_submission import ApplicationSubmissionService
from app.audit import log_audit_event

router = APIRouter(prefix="/consents", tags=["Consents"])


@router.get("/", response_model=List[ConsentRead])
async def list_my_consents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Consent).where(Consent.user_id == current_user.id).order_by(Consent.created_at.desc())
    )
    return result.scalars().all()


@router.post("/{consent_id}/respond")
async def respond_to_consent(
    consent_id: uuid.UUID,
    response: ConsentRespond,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Respond to a pending consent request."""
    # 1 & 2 & 3: Get consent and verify it exists and has application_id
    result = await db.execute(select(Consent).where(Consent.id == consent_id))
    consent = result.scalar_one_or_none()
    
    if not consent:
        raise HTTPException(status_code=404, detail="Consent not found")
        
    if not consent.application_id:
        raise HTTPException(status_code=400, detail="Consent does not belong to an application")

    # 4: Application belongs to authenticated citizen
    result = await db.execute(select(Application).where(Application.id == consent.application_id))
    app = result.scalar_one_or_none()
    
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
        
    if app.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this application")
        
    if consent.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this consent")

    # 5: Consent status is PENDING
    if consent.status != "PENDING":
        raise HTTPException(status_code=400, detail=f"Consent is no longer pending. Current status: {consent.status}")

    # 6: Application status is CONSENT_REQUIRED
    if app.status != ApplicationState.CONSENT_REQUIRED:
        raise HTTPException(status_code=400, detail=f"Application is not waiting for consent. Current status: {app.status}")
        
    # Process Response
    if response.action.lower() == "deny":
        consent.status = "DENIED"
        consent.responded_at = datetime.utcnow()
        
        await log_audit_event(
            db, actor_type="CITIZEN", action="CONSENT_DENIED",
            resource_type="consent", resource_id=str(consent.id), user_id=current_user.id
        )
        
        # Application goes CONSENT_REQUIRED -> READY_FOR_REVIEW
        old_status = app.status
        app.status = ApplicationState.READY_FOR_REVIEW
        
        event = ApplicationEvent(
            application_id=app.id,
            event_type="APPLICATION_READY_FOR_REVIEW",
            previous_status=old_status,
            new_status=app.status,
            created_by=current_user.id,
        )
        db.add(event)
        
        await log_audit_event(
            db, actor_type="SYSTEM", action="WORKFLOW_STATE_CHANGE",
            resource_type="application", resource_id=str(app.id), user_id=current_user.id,
            details={"previous": old_status, "new": app.status}
        )
        
        await db.commit()
        return {"status": "DENIED", "message": "Consent denied. Application returned to review phase."}
        
    elif response.action.lower() == "approve":
        consent.status = "APPROVED"
        consent.responded_at = datetime.utcnow()
        
        await log_audit_event(
            db, actor_type="CITIZEN", action="CONSENT_APPROVED",
            resource_type="consent", resource_id=str(consent.id), user_id=current_user.id
        )
        
        await db.commit() # Commit consent approval first
        
        # Trigger Submission Service
        submission_service = ApplicationSubmissionService(db)
        submission_result = await submission_service.submit(app.id, actor_type="CITIZEN", actor_id=str(current_user.id))
        
        return {
            "status": "APPROVED", 
            "message": "Consent approved.",
            "submission_result": submission_result
        }
    else:
        raise HTTPException(status_code=400, detail="Invalid action. Use 'approve' or 'deny'")
