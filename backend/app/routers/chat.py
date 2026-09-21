from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.schemas import ChatRequest, ChatResponse
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
    )
