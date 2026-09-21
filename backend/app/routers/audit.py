import uuid
from typing import List, Any
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import User, AuditLog
from app.auth import get_current_user

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("/")
@router.get("/api/audit/", include_in_schema=False)
async def list_audit_logs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.user_id == current_user.id)
        .order_by(AuditLog.created_at.desc())
    )
    logs = result.scalars().all()
    
    # Format the logs for the frontend
    formatted_logs = []
    for log in logs:
        formatted_logs.append({
            "id": str(log.id),
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "details": log.details,
            "created_at": log.created_at
        })
        
    return formatted_logs
