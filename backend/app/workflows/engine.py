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
        from sqlalchemy.orm import selectinload
        result = await self.db.execute(
            select(Application)
            .options(selectinload(Application.linked_documents))
            .where(Application.id == application_id)
        )
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

        # EXACT SELECTION: Pick the deterministic "best" document for each required type
        # We sort by created_at desc, then ID to ensure stability
        docs_by_type = {}
        from datetime import datetime
        for doc in sorted(docs, key=lambda d: (d.created_at or datetime.min, str(d.id)), reverse=True):
            if doc.document_type not in docs_by_type:
                docs_by_type[doc.document_type] = []
            docs_by_type[doc.document_type].append(doc)

        selected_docs = []
        uploaded_doc_types = set()
        has_unverified = False

        for req_type in required_docs:
            if req_type in docs_by_type:
                uploaded_doc_types.add(req_type)
                # prioritize verified, otherwise take latest unverified
                verified_for_type = [d for d in docs_by_type[req_type] if d.verification_status == "VERIFIED"]
                if verified_for_type:
                    selected_docs.append(verified_for_type[0])
                else:
                    selected_docs.append(docs_by_type[req_type][0])
                    has_unverified = True

        verified_selected_docs = [doc for doc in selected_docs if doc.verification_status == "VERIFIED"]

        # Merge profile carefully
        merged_profile = {}
        for doc in verified_selected_docs:
            if doc.extracted_data and isinstance(doc.extracted_data, dict):
                for key, val in doc.extracted_data.items():
                    if val is not None and key not in merged_profile:
                        merged_profile[key] = val

        missing_docs = [doc for doc in required_docs if doc not in uploaded_doc_types]
        missing_fields = [field for field in required_fields if field not in merged_profile]

        # Persist selected documents and form_data ONLY if we are updating state
        # Actually, let's always keep it up to date
        app.linked_documents = selected_docs

        # Safe form_data merge: preserve existing
        existing_form_data = app.form_data or {}
        new_form_data = dict(existing_form_data)
        for k, v in merged_profile.items():
            if k not in new_form_data or not new_form_data[k]:
                new_form_data[k] = v
        app.form_data = new_form_data

        doc_identities = []
        for doc in sorted(verified_selected_docs, key=lambda d: str(d.id)):
            doc_identities.append({"id": str(doc.id), "type": doc.document_type})

        current_data = {
            "application_id": str(app.id),
            "form_data": new_form_data,
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
                if latest_consent.data_snapshot != current_data:
                    # Invalidate
                    latest_consent.status = "DENIED"
                    app.status = ApplicationState.READY_FOR_REVIEW
                    # Log audit event with sanitized details
                    await log_audit_event(
                        self.db, actor_type="SYSTEM", action="CONSENT_INVALIDATED_DATA_CHANGED",
                        resource_type="consent", resource_id=str(latest_consent.id), user_id=app.user_id,
                        details={"application_id": str(app.id), "reason": "Data modified after consent granted"}
                    )
                    await self.db.commit()

        # Identify documents needing review or rejected
        needs_review_docs = [
            d for d in selected_docs
            if d.verification_status in ["NEEDS_REVIEW", "NOT_VERIFIABLE", "MANUAL_REVIEW"]
        ]
        rejected_docs = [
            d for d in selected_docs
            if d.verification_status in ["REJECTED", "SUSPICIOUS"]
        ]

        new_status = app.status
        status_event_details: Optional[Dict[str, Any]] = None

        if missing_docs:
            new_status = ApplicationState.COLLECTING_DOCUMENTS
        elif rejected_docs:
            # Uploaded document failed deterministic validation or was flagged suspicious
            new_status = ApplicationState.COLLECTING_DOCUMENTS
            status_event_details = {
                "reason": "DOCUMENTS_REJECTED",
                "message": "One or more uploaded documents were rejected during validation.",
                "rejected_documents": [
                    {"id": str(d.id), "type": d.document_type, "status": d.verification_status}
                    for d in rejected_docs
                ]
            }
        elif needs_review_docs:
            # Document validation succeeded format/checksum, but external government verification is unavailable
            # or requires officer review. Explicitly hold/transition to VALIDATING with clear actionable state.
            new_status = ApplicationState.VALIDATING
            status_event_details = {
                "reason": "DOCUMENTS_REQUIRE_REVIEW",
                "message": "Your document could not be independently verified with the available government verification service. It requires review before submission.",
                "documents_needing_review": [
                    {
                        "id": str(d.id),
                        "type": d.document_type,
                        "status": d.verification_status,
                        "reason": (d.verification_details or {}).get("failure_reason") if isinstance(d.verification_details, dict) else None
                    }
                    for d in needs_review_docs
                ]
            }
        elif has_unverified:
            # Documents still pending extraction or initial intake
            new_status = ApplicationState.EXTRACTING
        elif missing_fields:
            new_status = ApplicationState.MISSING_INFORMATION
        elif app.status not in [ApplicationState.CONSENT_REQUIRED, ApplicationState.SUBMITTING, ApplicationState.SUBMITTED, ApplicationState.TRACKING, ApplicationState.COMPLETED]:
            new_status = ApplicationState.READY_FOR_REVIEW

        if new_status != app.status:
            await self._change_status(app, new_status, status_event_details)
        else:
            self.db.add(app)
            await self.db.commit()
            await self.db.refresh(app)

        return app.status

    async def _change_status(self, app: Application, new_status: str, event_details: Optional[Dict[str, Any]] = None):
        old_status = app.status
        app.status = new_status

        event_name = f"APPLICATION_{new_status}"
        if new_status == ApplicationState.READY_FOR_REVIEW:
            event_name = "APPLICATION_READY_FOR_REVIEW"
        elif new_status == ApplicationState.COLLECTING_DOCUMENTS:
            event_name = "DOCUMENTS_REQUIRED"
        elif new_status == ApplicationState.VALIDATING:
            event_name = "DOCUMENTS_REQUIRE_REVIEW"

        event = ApplicationEvent(
            application_id=app.id,
            event_type=event_name,
            previous_status=old_status,
            new_status=new_status,
            created_by=app.user_id,
        )
        self.db.add(event)

        audit_details = {"previous": old_status, "new": new_status}
        if event_details:
            audit_details.update(event_details)

        await log_audit_event(
            self.db, actor_type="SYSTEM", action="WORKFLOW_STATE_CHANGE",
            resource_type="application", resource_id=str(app.id), user_id=app.user_id,
            details=audit_details
        )

        await self.db.commit()
        await self.db.refresh(app)
