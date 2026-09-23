import os
import uuid
import shutil
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import User, Document, Application
from app.schemas import DocumentRead, VaultStats
from app.auth import get_current_user
from app.documents.extract import extract_document_fields
from sqlalchemy import func

router = APIRouter(prefix="", tags=["Documents"])

@router.get("/documents/", response_model=List[DocumentRead], include_in_schema=False)
@router.get("/api/documents/", response_model=List[DocumentRead])
async def list_my_documents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Document).where(Document.user_id == current_user.id).order_by(Document.created_at.desc())
    )
    return result.scalars().all()


@router.get("/documents/vault-stats", response_model=VaultStats, include_in_schema=False)
@router.get("/api/documents/vault-stats", response_model=VaultStats)
async def get_vault_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    from app.models import Application, Consent
    from app.workflows.engine import ApplicationState

    result_total = await db.execute(select(func.count(Document.id)).where(Document.user_id == current_user.id))
    total = result_total.scalar() or 0

    result_verified = await db.execute(
        select(func.count(Document.id)).where(Document.user_id == current_user.id, Document.verification_status == "VERIFIED")
    )
    verified = result_verified.scalar() or 0

    result_apps = await db.execute(
        select(Application.id).where(
            Application.user_id == current_user.id,
            Application.status.in_([ApplicationState.SUBMITTED, ApplicationState.TRACKING, ApplicationState.COMPLETED])
        )
    )
    app_ids = result_apps.scalars().all()

    shared = 0
    if app_ids:
        result_consents = await db.execute(
            select(Consent.data_snapshot).where(
                Consent.application_id.in_(app_ids),
                Consent.status == "APPROVED"
            )
        )
        consents = result_consents.scalars().all()
        shared_docs = set()
        for snap in consents:
            docs = snap.get("documents", [])
            shared_docs.update(docs)
        shared = len(shared_docs)

    return VaultStats(total=total, verified=verified, shared=shared)


@router.post("/documents/upload", response_model=DocumentRead)
@router.post("/api/documents/upload", response_model=DocumentRead, include_in_schema=False)
async def upload_document(
    file: UploadFile = File(...),
    document_type: str = Form(...),
    citizen_id: str = Form(...),
    application_id: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Security check: citizen_id must match current_user.id
    if str(current_user.id) != citizen_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Cannot upload documents for another citizen."
        )

    app_uuid = None
    if application_id:
        try:
            app_uuid = uuid.UUID(application_id)
        except ValueError:
            pass

    import re
    file_id = str(uuid.uuid4())

    # 1. ACTUAL FILENAME SANITIZATION
    # Get basename to prevent path traversal
    base_name = os.path.basename(file.filename or "document")
    # Replace anything not alphanumeric, dot, underscore, dash with underscore
    sanitized_base = re.sub(r'[^A-Za-z0-9._-]', '_', base_name)
    safe_filename = f"{file_id}_{sanitized_base}"

    tmp_path = os.path.join("/tmp", safe_filename)

    with open(tmp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    file_size = os.path.getsize(tmp_path)

    from app.config import settings
    object_key = f"documents/{citizen_id}/{file_id}/{safe_filename}"
    db_committed = False
    sb_uploaded = False
    sb_client = None

    try:
        # 3. UPLOAD / DATABASE TRANSACTION ORDER
        if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
            from supabase import create_client
            sb_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
            sb_client.storage.from_(settings.SUPABASE_STORAGE_BUCKET).upload(
                file=tmp_path,
                path=object_key
            )
            sb_uploaded = True

        # Initial Document row with status PENDING
        doc = Document(
            id=uuid.UUID(file_id),
            user_id=current_user.id,
            application_id=app_uuid,
            document_type=document_type,
            title=file.filename or document_type,
            file_path=object_key,
            file_size=file_size,
            mime_type=file.content_type,
            verified=False,
            verification_status="PENDING",
            extracted_data=None
        )
        db.add(doc)
        await db.commit()
        db_committed = True
        await db.refresh(doc)

        # Run extraction engine
        extracted = await extract_document_fields(tmp_path, document_type)
        doc.extracted_data = extracted
        doc.verification_status = "VERIFIED"
        doc.verified = True

        await db.commit()
        await db.refresh(doc)

        if app_uuid:
            from app.workflows.engine import WorkflowEngine
            await WorkflowEngine(db).advance_application(app_uuid)

        return doc
    except Exception as e:
        if not db_committed and sb_uploaded and sb_client:
            try:
                sb_client.storage.from_(settings.SUPABASE_STORAGE_BUCKET).remove([object_key])
            except Exception:
                pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document processing failed."
        )
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
