from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import User, ChatMessage
from app.schemas import ChatRequest, ChatResponse, ChatMessageRead
from app.auth import get_current_user
from app.agent.orchestrator import run_agent_workflow

router = APIRouter(prefix="", tags=["Chat"])


@router.post("/chat", response_model=ChatResponse)
@router.post("/api/chat", response_model=ChatResponse, include_in_schema=False)
async def chat_endpoint(
    chat_in: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Validate citizen_id ownership
    if chat_in.citizen_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You cannot initiate applications for another citizen."
        )

    result = await run_agent_workflow(
        message=chat_in.message,
        citizen_id=str(current_user.id),
        db=db
    )

    return ChatResponse(
        reply=result["reply"],
        application_id=result.get("application_id"),
        service_code=result.get("service_code"),
        status=result.get("status"),
        required_documents=result.get("required_documents", []),
        required_fields=result.get("required_fields", []),
        detected_intent=result.get("detected_intent"),
        normalized_message=result.get("normalized_message"),
        missing_documents=result.get("missing_documents", result.get("required_documents", [])),
        verified_documents=result.get("verified_documents", []),
        clarification_options=result.get("clarification_options", []),
        jurisdiction=result.get("jurisdiction"),
        responsible_officer=result.get("responsible_officer"),
    )


@router.get("/chat/history", response_model=List[ChatMessageRead])
@router.get("/api/chat/history", response_model=List[ChatMessageRead], include_in_schema=False)
async def get_chat_history(
    application_id: Optional[uuid.UUID] = Query(None, description="Optional application filter"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns stored chat messages for the current authenticated citizen,
    including original user messages and normalized text for auditing.
    """
    query = select(ChatMessage).where(ChatMessage.user_id == current_user.id)
    if application_id:
        query = query.where(ChatMessage.application_id == application_id)
    query = query.order_by(ChatMessage.created_at.asc())

    res = await db.execute(query)
    messages = res.scalars().all()
    return messages
