from typing import Dict, Any, Optional
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import Application, Service, Document, ApplicationEvent, Consent
from app.workflows.engine import ApplicationState
from app.connectors.registry import get_connector
from app.audit import log_audit_event
from datetime import datetime

class ApplicationSubmissionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def submit(self, application_id: uuid.UUID, actor_type: str = "SYSTEM", actor_id: Optional[str] = None) -> Dict[str, Any]:
        result = await self.db.execute(
            select(Application)
            .options(selectinload(Application.service), selectinload(Application.linked_documents))
            .where(Application.id == application_id)
        )
        app = result.scalar_one_or_none()
        if not app:
            return {"error": f"Application '{application_id}' not found."}

        # Idempotency check
        if app.government_reference and app.status in [ApplicationState.SUBMITTED, ApplicationState.TRACKING, ApplicationState.COMPLETED]:
            return {
                "application_id": str(app.id),
                "status": app.status,
                "government_reference": app.government_reference,
                "message": "Application is already submitted."
            }

        # Consent checks: verify if there is an APPROVED consent
        result = await self.db.execute(
            select(Consent).where(
                Consent.application_id == app.id,
                Consent.status == "APPROVED"
            ).order_by(Consent.responded_at.desc())
        )
        approved_consent = result.scalars().first()
        if not approved_consent:
            return {"error": "No approved consent found for this application."}

        # Service
        service = app.service
        if not service:
            result = await self.db.execute(select(Service).where(Service.id == app.service_id))
            service = result.scalar_one_or_none()
        if not service:
            return {"error": "Service associated with application not found."}

        # Application-scoped document set (strictly linked documents, matching tool_request_consent)
        docs = app.linked_documents or []
        doc_identities = []
        for doc in sorted(docs, key=lambda d: str(d.id)):
            doc_identities.append({"id": str(doc.id), "type": doc.document_type})

        current_data = {
            "application_id": str(app.id),
            "form_data": app.form_data or {},
            "documents": doc_identities
        }

        # Strict deterministic equality with consent snapshot
        snapshot = approved_consent.data_snapshot
        if snapshot != current_data:
            return {"error": "CONSENT_INVALIDATED_DATA_CHANGED"}

        # Perform Submission
        await log_audit_event(
            self.db, actor_type=actor_type, actor_id=actor_id, user_id=app.user_id,
            action="SUBMISSION_STARTED", resource_type="application", resource_id=str(app.id)
        )
        app.status = ApplicationState.SUBMITTING
        
        try:
            connector = get_connector(service.code)
            submission_data = current_data
            response = await connector.submit_application(submission_data)
            ref_id = response.get("reference_id")
            connector_status = response.get("status")
        except Exception as e:
            return {"error": f"Failed to submit to government department: {str(e)}"}

        await log_audit_event(
            self.db, actor_type="GOVERNMENT_CONNECTOR", actor_id=service.department, user_id=app.user_id,
            action="GOVERNMENT_REFERENCE_RECEIVED", resource_type="application", resource_id=str(app.id),
            details={"reference_id": ref_id}
        )

        old_status = app.status
        app.government_reference = ref_id
        app.status = ApplicationState.SUBMITTED

        event2 = ApplicationEvent(
            application_id=app.id,
            event_type="SUBMITTED",
            previous_status=old_status,
            new_status=ApplicationState.SUBMITTED,
            created_by=app.user_id,
        )
        self.db.add(event2)

        await log_audit_event(
            self.db, actor_type=actor_type, actor_id=actor_id, user_id=app.user_id,
            action="SUBMIT_APPLICATION", resource_type="application", resource_id=str(app.id),
            details={"government_reference": ref_id}
        )

        await self.db.commit()
        await self.db.refresh(app)

        return {
            "application_id": str(app.id),
            "status": app.status,
            "government_reference": app.government_reference,
            "department_status": connector_status
        }
