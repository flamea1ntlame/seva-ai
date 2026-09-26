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
    import re
    import hashlib
    import tempfile

    # 1. Citizen authorization check
    if str(current_user.id) != citizen_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Cannot upload documents for another citizen."
        )

    # 2. Application IDOR / Ownership check
    app_uuid = None
    if application_id:
        try:
            app_uuid = uuid.UUID(application_id)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid application_id format."
            )
        
        # Verify that application belongs to current_user
        app_res = await db.execute(
            select(Application).where(Application.id == app_uuid, Application.user_id == current_user.id)
        )
        owned_app = app_res.scalar_one_or_none()
        if not owned_app:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Application not found or does not belong to you."
            )

    # 3. Filename Sanitization
    file_id = str(uuid.uuid4())
    base_name = os.path.basename(file.filename or "document")
    sanitized_base = re.sub(r'[^A-Za-z0-9._-]', '_', base_name)
    safe_filename = f"{file_id}_{sanitized_base}"

    # 4. Stream upload with 10 MB limit & SHA-256 calculation & Cross-platform Temp File
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
    CHUNK_SIZE = 64 * 1024  # 64 KB

    hasher = hashlib.sha256()
    total_bytes = 0
    header_bytes = bytearray()

    temp_dir = tempfile.gettempdir()
    tmp_path = os.path.join(temp_dir, safe_filename)

    try:
        with open(tmp_path, "wb") as buffer:
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds maximum allowed size of {MAX_FILE_SIZE // (1024 * 1024)}MB."
                    )
                if len(header_bytes) < 8:
                    header_bytes.extend(chunk[: 8 - len(header_bytes)])
                hasher.update(chunk)
                buffer.write(chunk)

        if total_bytes == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty."
            )

        sha256_hash = hasher.hexdigest()

        # 5. Magic Byte / File Content Validation (PDF, JPEG, PNG only)
        # PDF starts with %PDF- (0x25 0x50 0x44 0x46)
        # JPEG starts with 0xFF 0xD8 0xFF
        # PNG starts with 0x89 0x50 0x4E 0x47 0x0D 0x0A 0x1A 0x0A
        detected_mime = None
        if header_bytes.startswith(b"%PDF-"):
            detected_mime = "application/pdf"
        elif header_bytes.startswith(b"\xff\xd8\xff"):
            detected_mime = "image/jpeg"
        elif header_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            detected_mime = "image/png"
        else:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Unsupported file format. Only PDF, JPEG, and PNG files are allowed."
            )

        # 6. Duplicate File Intake Handling
        # Check if user already uploaded this exact file
        dup_query = await db.execute(
            select(Document).where(
                Document.user_id == current_user.id,
                Document.sha256_hash == sha256_hash
            )
        )
        existing_doc = dup_query.scalars().first()
        if existing_doc:
            # If uploaded for a new application and the existing record has no application, associate it
            if app_uuid and not existing_doc.application_id:
                existing_doc.application_id = app_uuid
                await db.commit()
                await db.refresh(existing_doc)
            return existing_doc

        file_size = total_bytes
        from app.config import settings
        object_key = f"documents/{citizen_id}/{file_id}/{safe_filename}"
        db_committed = False
        sb_uploaded = False
        sb_client = None

        try:
            # Upload to Supabase Storage if configured
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
                mime_type=detected_mime,
                sha256_hash=sha256_hash,
                verification_details=None,
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

            # -----------------------------------------------------------------
            # RUN COMPLETE VERIFICATION ENGINE
            # -----------------------------------------------------------------
            from app.documents.schemas import ExtractionResult
            from app.documents.verification.engine import DocumentVerificationEngine

            extraction_contract = ExtractionResult(
                document_type=document_type,
                extracted_fields=extracted if isinstance(extracted, dict) else {},
                raw_text=str(extracted.get("extracted_text") or "") if isinstance(extracted, dict) else None,
                confidence=float(extracted.get("confidence", 0.95)) if isinstance(extracted, dict) else 0.95
            )

            verifier = DocumentVerificationEngine()
            verification_result = await verifier.verify(
                extraction=extraction_contract,
                file_path=tmp_path,
                sha256_hash=sha256_hash
            )

            # Persist explicit verification status & rich structured evidence
            doc.verification_status = verification_result.status.value
            doc.verified = verification_result.is_authentic
            doc.verification_details = verification_result.model_dump()

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


@router.get("/documents/{document_id}/verification", response_model=dict)
@router.get("/api/documents/{document_id}/verification", response_model=dict, include_in_schema=False)
async def get_document_verification(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves rich verification details and risk flags for a specific document.
    Enforces tenant ownership.
    """
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.user_id == current_user.id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or access denied."
        )

    return {
        "document_id": str(doc.id),
        "document_type": doc.document_type,
        "verification_status": doc.verification_status,
        "verified": doc.verified,
        "sha256_hash": doc.sha256_hash,
        "verification_details": doc.verification_details or {}
    }


@router.post("/documents/{document_id}/reverify", response_model=DocumentRead)
@router.post("/api/documents/{document_id}/reverify", response_model=DocumentRead, include_in_schema=False)
async def reverify_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Reruns the verification decision engine on an existing document record.
    """
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.user_id == current_user.id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or access denied."
        )

    from app.documents.schemas import ExtractionResult
    from app.documents.verification.engine import DocumentVerificationEngine

    extraction_contract = ExtractionResult(
        document_type=doc.document_type,
        extracted_fields=doc.extracted_data if isinstance(doc.extracted_data, dict) else {},
        raw_text=str(doc.extracted_data.get("extracted_text") or "") if isinstance(doc.extracted_data, dict) else None,
        confidence=0.95
    )

    verifier = DocumentVerificationEngine()
    verification_result = await verifier.verify(
        extraction=extraction_contract,
        sha256_hash=doc.sha256_hash
    )

    doc.verification_status = verification_result.status.value
    doc.verified = verification_result.is_authentic
    doc.verification_details = verification_result.model_dump()

    await db.commit()
    await db.refresh(doc)
    return doc
