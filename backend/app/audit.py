from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import AuditLog
import uuid

async def log_audit_event(
    db: AsyncSession,
    actor_type: str,
    action: str,
    resource_type: str,
    actor_id: Optional[str] = None,
    user_id: Optional[uuid.UUID] = None,
    resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None
):
    """
    Helper to easily log audit events.
    actor_type: CITIZEN, AI_AGENT, SYSTEM, GOVERNMENT_CONNECTOR, ADMIN_DEMO
    action: e.g., DOCUMENT_UPLOADED, WORKFLOW_STATE_CHANGE, REQUEST_CONSENT, etc.
    """
    log_entry = AuditLog(
        actor_type=actor_type,
        actor_id=actor_id,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        details=details
    )
    db.add(log_entry)
    # Don't commit here, usually done within the parent transaction.
    # We will await flush if needed, but it's generally fine to just add to session.
