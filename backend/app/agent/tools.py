import uuid
import random
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Service, Application, ApplicationEvent, Document, Consent
from app.documents.extract import extract_document_fields
from app.workflows.engine import ApplicationState, WorkflowEngine
from app.connectors.registry import get_connector
from app.workflows.application_submission import ApplicationSubmissionService
from app.audit import log_audit_event


TOOLS_SCHEMA = [
    {
        "name": "list_services",
        "description": "Lists all available government services currently offered on the SEVA AI platform.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_service_requirements",
        "description": "Retrieves official document requirements, data fields, department, and processing details for a specific service code.",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_code": {
                    "type": "string",
                    "description": "The unique code of the service (e.g. 'income_certificate', 'birth_certificate', 'driving_license')."
                }
            },
            "required": ["service_code"]
        }
    },
    {
        "name": "create_application",
        "description": "Creates a new government service application workflow for the citizen in DISCOVER status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_code": {
                    "type": "string",
                    "description": "The unique service code to apply for."
                },
                "citizen_id": {
                    "type": "string",
                    "description": "The authenticated citizen's UUID string."
                }
            },
            "required": ["service_code", "citizen_id"]
        }
    },
    {
        "name": "extract_document_data",
        "description": "Processes an uploaded document with Vision OCR, extracts key structured fields, updates verification_status to VERIFIED, and returns extracted data.",
        "input_schema": {
            "type": "object",
            "properties": {
                "document_id": {
                    "type": "string",
                    "description": "The unique UUID string of the uploaded document."
                }
            },
            "required": ["document_id"]
        }
    },
    {
        "name": "get_citizen_profile",
        "description": "Merges all VERIFIED extracted_data across a citizen's uploaded documents into one consolidated profile object.",
        "input_schema": {
            "type": "object",
            "properties": {
                "citizen_id": {
                    "type": "string",
                    "description": "The authenticated citizen's UUID string."
                }
            },
            "required": ["citizen_id"]
        }
    },
    {
        "name": "request_consent",
        "description": "Requests citizen consent to share their verified data with a government department.",
        "input_schema": {
            "type": "object",
            "properties": {
                "application_id": {
                    "type": "string",
                    "description": "The unique UUID string of the application."
                },
                "data_requested": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of data fields and documents being shared."
                },
                "requesting_department": {
                    "type": "string",
                    "description": "The department requesting the data."
                },
                "purpose": {
                    "type": "string",
                    "description": "The purpose for data sharing."
                }
            },
            "required": ["application_id", "data_requested", "requesting_department", "purpose"]
        }
    },
    {
        "name": "submit_application",
        "description": "Validates and submits the application to the relevant government department.",
        "input_schema": {
            "type": "object",
            "properties": {
                "application_id": {
                    "type": "string",
                    "description": "The unique UUID string of the application."
                }
            },
            "required": ["application_id"]
        }
    }
]


async def tool_list_services(db: AsyncSession) -> List[Dict[str, Any]]:
    result = await db.execute(select(Service).where(Service.is_active == True))
    services = result.scalars().all()
    return [
        {
            "code": s.code,
            "title": s.title,
            "department": s.department,
            "description": s.description,
            "required_documents": s.required_documents or [],
            "required_fields": s.required_fields or [],
            "processing_time_days": s.processing_time_days,
            "fee_amount": float(s.fee_amount),
        }
        for s in services
    ]


async def tool_get_service_requirements(db: AsyncSession, service_code: str) -> Dict[str, Any]:
    result = await db.execute(select(Service).where(Service.code == service_code))
    service = result.scalar_one_or_none()
    if not service:
        return {
            "error": f"Service '{service_code}' not found.",
            "service_code": service_code
        }
    
    return {
        "service_code": service.code,
        "service_name": service.title,
        "department": service.department,
        "required_documents": service.required_documents or [],
        "required_fields": service.required_fields or [],
        "description": service.description,
        "fee_amount": float(service.fee_amount),
        "processing_time_days": service.processing_time_days,
    }


async def tool_create_application(db: AsyncSession, service_code: str, citizen_id: str) -> Dict[str, Any]:
    try:
        user_uuid = uuid.UUID(citizen_id)
    except ValueError:
        return {"error": "Invalid citizen_id UUID format."}

    result = await db.execute(select(Service).where(Service.code == service_code))
    service = result.scalar_one_or_none()
    if not service:
        return {"error": f"Service code '{service_code}' does not exist."}

    app_num = f"SEVA-{random.randint(100000, 999999)}"

    application = Application(
        application_number=app_num,
        user_id=user_uuid,
        service_id=service.id,
        status="DISCOVER",
        form_data={},
        remarks="Initialized via SEVA AI Assistant",
    )
    db.add(application)
    await db.flush()

    event = ApplicationEvent(
        application_id=application.id,
        event_type="application_created",
        previous_status=None,
        new_status="DISCOVER",
        created_by=user_uuid,
    )
    db.add(event)

    await log_audit_event(
        db, actor_type="AI_AGENT", action="CREATE_APPLICATION",
        resource_type="application", resource_id=str(application.id),
        user_id=user_uuid, details={"service_code": service.code}
    )

    await db.commit()
    await db.refresh(application)

    from app.workflows.engine import WorkflowEngine
    await WorkflowEngine(db).advance_application(application.id)
    await db.refresh(application)

    return {
        "application_id": str(application.id),
        "application_number": application.application_number,
        "service": service.title,
        "service_code": service.code,
        "department": service.department,
        "current_status": application.status,
    }


async def tool_extract_document_data(db: AsyncSession, document_id: str, citizen_id: str) -> Dict[str, Any]:
    try:
        doc_uuid = uuid.UUID(document_id)
        user_uuid = uuid.UUID(citizen_id)
    except ValueError:
        return {"error": "Invalid UUID format."}

    result = await db.execute(select(Document).where(Document.id == doc_uuid, Document.user_id == user_uuid))
    doc = result.scalar_one_or_none()
    if not doc:
        return {"error": f"Document with ID '{document_id}' not found or you do not have permission to access it."}

    import os
    from app.config import settings
    tmp_path = os.path.join("/tmp", f"{uuid.uuid4()}_extract.pdf")
    extracted = None

    try:
        # Download from Supabase
        if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY and doc.file_path.startswith("documents/"):
            from supabase import create_client
            sb_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
            res = sb_client.storage.from_(settings.SUPABASE_STORAGE_BUCKET).download(doc.file_path)
            with open(tmp_path, "wb") as f:
                f.write(res)
        else:
            # Fallback for old local files if any (e.g., seed data)
            tmp_path = doc.file_path

        extracted = await extract_document_fields(tmp_path, doc.document_type)
    except Exception as e:
        return {"error": f"Failed to process document: {str(e)}"}
    finally:
        if tmp_path.startswith("/tmp") and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

    if extracted is not None:
        doc.extracted_data = extracted
        doc.verification_status = "VERIFIED"
        doc.verified = True

    await log_audit_event(
        db, actor_type="AI_AGENT", action="DOCUMENT_VERIFIED",
        resource_type="document", resource_id=str(doc.id),
        user_id=doc.user_id, details={"document_type": doc.document_type}
    )

    await db.commit()
    await db.refresh(doc)

    if doc.application_id:
        from app.workflows.engine import WorkflowEngine
        await WorkflowEngine(db).advance_application(doc.application_id)

    return {
        "document_id": str(doc.id),
        "document_type": doc.document_type,
        "verification_status": doc.verification_status,
        "extracted_data": doc.extracted_data,
    }


async def tool_get_citizen_profile(db: AsyncSession, citizen_id: str) -> Dict[str, Any]:
    try:
        user_uuid = uuid.UUID(citizen_id)
    except ValueError:
        return {"error": "Invalid citizen_id UUID format."}

    result = await db.execute(
        select(Document).where(
            Document.user_id == user_uuid,
            Document.verification_status == "VERIFIED"
        )
    )
    docs = result.scalars().all()

    merged_profile: Dict[str, Any] = {}
    uploaded_document_types = set()

    for doc in docs:
        uploaded_document_types.add(doc.document_type)
        if doc.extracted_data and isinstance(doc.extracted_data, dict):
            for key, val in doc.extracted_data.items():
                if val is not None and key not in merged_profile:
                    merged_profile[key] = val

    return {
        "citizen_id": citizen_id,
        "merged_profile": merged_profile,
        "uploaded_document_types": list(uploaded_document_types),
    }


async def tool_request_consent(db: AsyncSession, application_id: str, data_requested: List[str], requesting_department: str, purpose: str) -> Dict[str, Any]:
    try:
        app_uuid = uuid.UUID(application_id)
    except ValueError:
        return {"error": "Invalid application_id UUID format."}

    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Application)
        .options(selectinload(Application.linked_documents))
        .where(Application.id == app_uuid)
    )
    app = result.scalar_one_or_none()
    if not app:
        return {"error": f"Application '{application_id}' not found."}

    if app.status != ApplicationState.READY_FOR_REVIEW:
        return {"error": f"Application must be in READY_FOR_REVIEW state to request consent. Current status is {app.status}."}

    # Gather data snapshot from exactly the linked documents
    docs = app.linked_documents
    
    doc_identities = []
    
    # Sort docs by ID to ensure deterministic comparison
    for doc in sorted(docs, key=lambda d: str(d.id)):
        doc_identities.append({"id": str(doc.id), "type": doc.document_type})

    snapshot = {
        "application_id": str(app.id),
        "form_data": app.form_data or {},
        "documents": doc_identities
    }

    consent = Consent(
        user_id=app.user_id,
        application_id=app.id,
        purpose=purpose,
        requesting_department=requesting_department,
        data_requested=data_requested,
        data_snapshot=snapshot,
        status="PENDING"
    )
    db.add(consent)

    old_status = app.status
    app.status = ApplicationState.CONSENT_REQUIRED

    event = ApplicationEvent(
        application_id=app.id,
        event_type="APPLICATION_CONSENT_REQUIRED",
        previous_status=old_status,
        new_status=app.status,
        created_by=app.user_id,
    )
    db.add(event)

    await log_audit_event(
        db, actor_type="AI_AGENT", action="REQUEST_CONSENT",
        resource_type="application", resource_id=str(app.id),
        user_id=app.user_id, details={"purpose": purpose, "department": requesting_department}
    )

    await db.commit()
    await db.refresh(app)
    await db.refresh(consent)

    return {
        "consent_id": str(consent.id),
        "status": app.status,
        "message": "Consent request created. Waiting for citizen approval."
    }


async def tool_submit_application(db: AsyncSession, application_id: str) -> Dict[str, Any]:
    try:
        app_uuid = uuid.UUID(application_id)
    except ValueError:
        return {"error": "Invalid application_id UUID format."}
        
    submission_service = ApplicationSubmissionService(db)
    return await submission_service.submit(app_uuid, actor_type="AI_AGENT")
