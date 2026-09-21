import asyncio
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from app.auth import get_current_user
from app.models import User
from app.events import notifier

router = APIRouter(prefix="/events", tags=["Events"])

@router.get("/stream")
async def stream_events(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """
    SSE Endpoint for real-time events scoped to the authenticated user.
    """
    async def event_generator():
        # Listen for events on this connection
        try:
            async for event in notifier.subscribe(str(current_user.id)):
                # If client disconnected, Request.is_disconnected() might be true
                if await request.is_disconnected():
                    break
                yield event
        except asyncio.CancelledError:
            pass

    return StreamingResponse(event_generator(), media_type="text/event-stream")
