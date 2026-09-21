import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Application, Service, Document, ApplicationEvent
from app.audit import log_audit_event

class ApplicationState:
    DISCOVER = "DISCOVER"
    COLLECTING_DOCUMENTS = "COLLECTING_DOCUMENTS"
    EXTRACTING = "EXTRACTING"
    VALIDATING = "VALIDATING"
    MISSING_INFORMATION = "MISSING_INFORMATION"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    CONSENT_REQUIRED = "CONSENT_REQUIRED"
    SUBMITTING = "SUBMITTING"
    SUBMITTED = "SUBMITTED"
    TRACKING = "TRACKING"
    COMPLETED = "COMPLETED"


class WorkflowEngine:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def advance_application(self, application_id: uuid.UUID) -> str:
        """
        Evaluates the current state of an application and advances its status
        if the requirements for the next state are met.
        Only advances automatically up to READY_FOR_REVIEW.
        """
        result = await self.db.execute(select(Application).where(Application.id == application_id))
        app = result.scalar_one_or_none()
        if not app:
            raise ValueError(f"Application {application_id} not found")

        # Do not automatically advance if it is READY_FOR_REVIEW or beyond
        if app.status in [
            ApplicationState.READY_FOR_REVIEW,
            ApplicationState.SUBMITTING,
            ApplicationState.SUBMITTED,
            ApplicationState.TRACKING,
            ApplicationState.COMPLETED
        ]:
            return app.status

        # Get Service
        result = await self.db.execute(select(Service).where(Service.id == app.service_id))
        service = result.scalar_one_or_none()
        if not service:
            raise ValueError(f"Service for application {application_id} not found")

        required_docs = service.required_documents or []
        required_fields = service.required_fields or []

        # Get Documents for user
        result = await self.db.execute(
            select(Document).where(
                Document.user_id == app.user_id,
            )
        )
        docs = result.scalars().all()
        
        uploaded_doc_types = {doc.document_type for doc in docs}
        verified_docs = [doc for doc in docs if doc.verification_status == "VERIFIED"]
        
        # Merge profile
        merged_profile = {}
        for doc in verified_docs:
            if doc.extracted_data and isinstance(doc.extracted_data, dict):
                for key, val in doc.extracted_data.items():
                    if val is not None and key not in merged_profile:
                        merged_profile[key] = val
                        
        missing_docs = [doc for doc in required_docs if doc not in uploaded_doc_types]
        missing_fields = [field for field in required_fields if field not in merged_profile]
        
        has_unverified = any(doc.document_type in required_docs and doc.verification_status == "PENDING" for doc in docs)
        
        doc_identities = []
        for doc in sorted(verified_docs, key=lambda d: str(d.id)):
            doc_identities.append({"id": str(doc.id), "type": doc.document_type})
            
        current_data = {
            "application_id": str(app.id),
            "form_data": merged_profile,
            "documents": doc_identities
        }
        
        # Invalidate consent if data changed
        if app.status == ApplicationState.CONSENT_REQUIRED:
            from app.models import Consent
            # Get latest consent
            result_consent = await self.db.execute(
                select(Consent).where(
                    Consent.application_id == app.id
                ).order_by(Consent.created_at.desc())
            )
            latest_consent = result_consent.scalars().first()
            if latest_consent and latest_consent.status in ["PENDING", "APPROVED"]:
                print("SNAPSHOT:", latest_consent.data_snapshot)
                print("CURRENT:", current_data)
                if latest_consent.data_snapshot != current_data:
                    # Invalidate
                    latest_consent.status = "DENIED" # or some invalid status, but DENIED is safe
                    app.status = ApplicationState.READY_FOR_REVIEW
                    # Log
                    await log_audit_event(
                        self.db, actor_type="SYSTEM", action="CONSENT_INVALIDATED_DATA_CHANGED",
                        resource_type="consent", resource_id=str(latest_consent.id), user_id=app.user_id
                    )
                    await self.db.commit()
        
        new_status = app.status

        if missing_docs:
            print("MISSING DOCS:", missing_docs)
            new_status = ApplicationState.COLLECTING_DOCUMENTS
        elif has_unverified:
            print("UNVERIFIED DOCS")
            new_status = ApplicationState.EXTRACTING
        elif missing_fields:
            print("MISSING FIELDS:", missing_fields)
            new_status = ApplicationState.MISSING_INFORMATION
        elif app.status not in [ApplicationState.CONSENT_REQUIRED, ApplicationState.SUBMITTING, ApplicationState.SUBMITTED, ApplicationState.TRACKING, ApplicationState.COMPLETED]:
            new_status = ApplicationState.READY_FOR_REVIEW
            
        if new_status != app.status:
            await self._change_status(app, new_status)
            
        return app.status

    async def _change_status(self, app: Application, new_status: str):
        old_status = app.status
        app.status = new_status
        
        event_name = f"APPLICATION_{new_status}"
        if new_status == ApplicationState.READY_FOR_REVIEW:
            event_name = "APPLICATION_READY_FOR_REVIEW"
        elif new_status == ApplicationState.COLLECTING_DOCUMENTS:
            event_name = "DOCUMENTS_REQUIRED"
            
        event = ApplicationEvent(
            application_id=app.id,
            event_type=event_name,
            previous_status=old_status,
            new_status=new_status,
            created_by=app.user_id,
        )
        self.db.add(event)
        
        await log_audit_event(
            self.db, actor_type="SYSTEM", action="WORKFLOW_STATE_CHANGE",
            resource_type="application", resource_id=str(app.id), user_id=app.user_id,
            details={"previous": old_status, "new": new_status}
        )

        await self.db.commit()
        await self.db.refresh(app)
