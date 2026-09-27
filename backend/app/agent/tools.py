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
from app.agent.dependencies import get_service_prerequisites, check_citizen_prerequisites


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
        "description": "Processes an uploaded document with pretrained OCR, extracts key structured fields, updates verification_status to OCR_EXTRACTED, and returns extracted data.",
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
    },
    {
        "name": "update_application_field",
        "description": "Updates a citizen-declared form data field on an active application (e.g. 'annual_income', 'occupation', 'blood_group', 'vehicle_class'). Strictly prohibited for document/OCR-derived fields such as date_of_birth, applicant_name, father_name, mother_name, or place_of_birth, which require official document upload.",
        "input_schema": {
            "type": "object",
            "properties": {
                "application_id": {
                    "type": "string",
                    "description": "The unique UUID string of the application."
                },
                "field": {
                    "type": "string",
                    "description": "The name of the field to update (e.g. 'annual_income', 'occupation', 'blood_group', 'vehicle_class')."
                },
                "value": {
                    "type": "string",
                    "description": "The value provided by the citizen."
                }
            },
            "required": ["application_id", "field", "value"]
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
    from app.service_rules import get_requirements as get_rules_requirements
    result = await db.execute(select(Service).where(Service.code == service_code))
    service = result.scalar_one_or_none()
    if not service:
        return {
            "error": f"Service '{service_code}' not found.",
            "service_code": service_code
        }
    
    prereqs = get_service_prerequisites(service_code)
    rules_data = await get_rules_requirements(service.code, db=db)

    # Inspect authoritative local service catalog JSON if present for rich structured requirements
    import json
    import os
    kb_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "service_catalog", "services", "karnataka", f"{service_code}.json"))
    
    raw_docs = service.required_documents or rules_data.get("required_documents", [])
    required_docs = [d for d in raw_docs if d != "unknown_requirements"]
    conditional_reqs = []
    alt_groups = []

    if os.path.exists(kb_path):
        try:
            with open(kb_path, "r") as f:
                kb_data = json.load(f)
            for req in kb_data.get("requirements", []):
                if req.get("type") in ["UNKNOWN", "NOT_VERIFIED"] or req.get("citizen_exposure") == "DO_NOT_EXPOSE":
                    continue
                if req.get("type") == "REQUIRED":
                    if req.get("document") not in required_docs:
                        required_docs.append(req.get("document"))
                elif req.get("type") == "CONDITIONAL":
                    conditional_reqs.append({
                        "document": req.get("document"),
                        "condition": req.get("condition_description"),
                        "evidence_refs": req.get("evidence_refs", [])
                    })
                elif req.get("type") == "ALTERNATIVE_GROUP":
                    alt_groups.append({
                        "group_id": req.get("group_id"),
                        "minimum_required": req.get("minimum_required", 1),
                        "documents": [d.get("document") for d in req.get("documents", [])]
                    })
        except Exception:
            pass
    
    return {
        "service_code": service.code,
        "service_name": service.title,
        "department": service.department,
        "required_documents": required_docs,
        "conditional_requirements": conditional_reqs,
        "alternative_groups": alt_groups,
        "prerequisites": prereqs,
        "required_fields": service.required_fields or rules_data.get("required_fields", []),
        "description": service.description or rules_data.get("description", ""),
        "fee_amount": float(service.fee_amount),
        "processing_time_days": service.processing_time_days,
        "document_options": rules_data.get("document_options", {}),
        "document_dependencies": rules_data.get("document_dependencies", []),
        "responsible_authority": rules_data.get("responsible_authority", {}),
        "jurisdiction": rules_data.get("jurisdiction", {}),
        "scholarship_guidance": rules_data.get("scholarship_guidance"),
    }


async def tool_create_application(
    db: AsyncSession,
    service_code: str,
    citizen_id: str,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    try:
        user_uuid = uuid.UUID(citizen_id)
    except ValueError:
        return {"error": "Invalid citizen_id UUID format."}

    result = await db.execute(select(Service).where(Service.code == service_code))
    service = result.scalar_one_or_none()
    if not service:
        return {"error": f"Service code '{service_code}' does not exist."}

    # 1. Statutory Prerequisite Verification
    prereq_res = await check_citizen_prerequisites(db, user_uuid, service_code, context)
    if not prereq_res["satisfied"]:
        primary = prereq_res["primary_prerequisite"]
        return {
            "error": "PREREQUISITE_NOT_MET",
            "service_code": service.code,
            "service_name": service.title,
            "prerequisite_service": primary["service_code"],
            "prerequisite_title": primary["title"],
            "description": primary["description"],
            "evidence_refs": primary.get("evidence_refs", []),
            "message": f"Prerequisite requirement not met: You must first obtain a valid {primary['title']} before applying for {service.title}. {primary['description']}"
        }

    # 2. Idempotency check: reuse existing active application for this citizen and service
    existing_res = await db.execute(
        select(Application).where(
            Application.user_id == user_uuid,
            Application.service_id == service.id,
            Application.status.in_([
                "DISCOVER", "COLLECTING_DOCUMENTS", "EXTRACTING",
                "VALIDATING", "MISSING_INFORMATION", "READY_FOR_REVIEW",
                "CONSENT_REQUIRED", "SUBMITTING", "SUBMITTED", "TRACKING"
            ])
        ).order_by(Application.created_at.desc())
    )
    existing_app = existing_res.scalars().first()
    if existing_app:
        return {
            "application_id": str(existing_app.id),
            "application_number": existing_app.application_number,
            "current_status": existing_app.status,
            "service": service.title,
            "service_code": service.code,
            "department": service.department,
            "message": "Existing active application retrieved."
        }

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
        ocr_status = extracted.get("_ocr_status", "OCR_EXTRACTED") if isinstance(extracted, dict) else "OCR_EXTRACTED"
        doc.verification_status = ocr_status
        # OCR extraction does NOT confer authenticity verification
        doc.verified = False

    await log_audit_event(
        db, actor_type="AI_AGENT", action="DOCUMENT_OCR_EXTRACTED",
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
            Document.user_id == user_uuid
        )
    )
    docs = result.scalars().all()

    merged_profile: Dict[str, Any] = {}
    verified_document_types = set()
    received_document_types = set()
    review_needed_document_types = set()

    for doc in docs:
        received_document_types.add(doc.document_type)
        if doc.verification_status == "VERIFIED":
            verified_document_types.add(doc.document_type)
            if doc.extracted_data and isinstance(doc.extracted_data, dict):
                for key, val in doc.extracted_data.items():
                    if val is not None and str(val).strip() != "" and key not in merged_profile:
                        merged_profile[key] = val
        elif doc.verification_status in ("NEEDS_REVIEW", "OCR_EXTRACTED", "NOT_CHECKED"):
            review_needed_document_types.add(doc.document_type)

    return {
        "citizen_id": citizen_id,
        "merged_profile": merged_profile,
        "uploaded_document_types": sorted(list(verified_document_types)),
        "verified_document_types": sorted(list(verified_document_types)),
        "received_document_types": sorted(list(received_document_types)),
        "review_needed_document_types": sorted(list(review_needed_document_types)),
    }


async def tool_request_consent(
    db: AsyncSession,
    application_id: str,
    data_requested: List[str],
    requesting_department: str,
    purpose: str,
    citizen_id: Optional[str] = None
) -> Dict[str, Any]:
    try:
        app_uuid = uuid.UUID(str(application_id))
    except (ValueError, TypeError):
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

    # Ownership check: Application.user_id must match authenticated citizen_id
    if citizen_id is not None and str(app.user_id) != str(citizen_id):
        return {"error": "Unauthorized: Application does not belong to the authenticated citizen."}

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


async def tool_submit_application(
    db: AsyncSession,
    application_id: str,
    citizen_id: Optional[str] = None
) -> Dict[str, Any]:
    try:
        app_uuid = uuid.UUID(str(application_id))
    except (ValueError, TypeError):
        return {"error": "Invalid application_id UUID format."}

    result = await db.execute(
        select(Application).where(Application.id == app_uuid)
    )
    app = result.scalar_one_or_none()
    if not app:
        return {"error": f"Application '{application_id}' not found."}

    # Ownership check: Application.user_id must match authenticated citizen_id
    if citizen_id is not None and str(app.user_id) != str(citizen_id):
        return {"error": "Unauthorized: Application does not belong to the authenticated citizen."}

    submission_service = ApplicationSubmissionService(db)
    return await submission_service.submit(app_uuid, actor_type="AI_AGENT")


DOCUMENT_ONLY_FIELDS = {
    "date_of_birth", "dob", "applicant_name", "name",
    "father_name", "mother_name", "place_of_birth",
    "aadhaar_number", "pan_number", "id_number", "passport_number",
    "driving_license_number"
}

ALLOWED_CHAT_FIELDS = {
    "annual_income", "occupation", "blood_group", "vehicle_class",
    "remarks", "declared_income", "employment_type"
}


async def update_application_field(
    db: AsyncSession,
    application_id: str,
    field: str,
    value: Any,
    citizen_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Persists a citizen-provided form data field to Application.form_data.
    Rejects document/OCR-only fields to preserve authoritative evidence integrity.
    Recomputes application readiness and missing fields.
    """
    try:
        app_uuid = uuid.UUID(str(application_id))
    except ValueError:
        return {"error": "Invalid application_id UUID format."}

    field_clean = field.strip().lower()

    if field_clean in DOCUMENT_ONLY_FIELDS or field_clean not in ALLOWED_CHAT_FIELDS:
        return {
            "error": f"Field '{field}' cannot be provided via chat. Official document verification is required.",
            "field": field,
            "allowed": False
        }

    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Application)
        .options(selectinload(Application.service), selectinload(Application.linked_documents))
        .where(Application.id == app_uuid)
    )
    app = result.scalar_one_or_none()
    if not app:
        return {"error": f"Application '{application_id}' not found."}

    # Ownership check: Application.user_id must match authenticated citizen_id
    if citizen_id is not None and str(app.user_id) != str(citizen_id):
        return {"error": "Unauthorized: Application does not belong to the authenticated citizen."}

    service_code = app.service.code if app.service else None

    # Persist the field in app.form_data
    form_data = dict(app.form_data or {})
    form_data[field_clean] = value
    app.form_data = form_data

    # Re-evaluate application state with workflow engine
    engine = WorkflowEngine(db)
    await engine.advance_application(app.id)

    await db.commit()
    await db.refresh(app)

    # Directly query verified documents linked to this application without triggering relationship lazy loads
    doc_res = await db.execute(
        select(Document).where(
            Document.application_id == app.id,
            Document.verification_status == "VERIFIED"
        )
    )
    verified_docs = doc_res.scalars().all()

    # Recompute missing fields using shared helper combining form_data and verified documents
    from app.service_rules import get_requirements as get_rules_requirements, compute_application_missing_fields
    reqs = await get_rules_requirements(service_code or "income_certificate", db=db)
    required_fields = reqs.get("required_fields", [])
    remaining_missing_fields = compute_application_missing_fields(
        required_fields, app.form_data, verified_docs
    )

    await log_audit_event(
        db,
        actor_type="CITIZEN",
        action="UPDATE_APPLICATION_FIELD",
        resource_type="application",
        resource_id=str(app.id),
        user_id=app.user_id,
        details={"field": field_clean, "value": str(value)}
    )

    return {
        "success": True,
        "application_id": str(app.id),
        "field": field_clean,
        "value": value,
        "status": app.status,
        "form_data": app.form_data,
        "missing_fields": remaining_missing_fields,
        "message": f"Field '{field_clean}' successfully saved."
    }


tool_update_application_field = update_application_field

