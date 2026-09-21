import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, Any, AsyncGenerator

class EventNotifier:
    def __init__(self):
        # Maps user_id (str) to a list of asyncio.Queue
        self.listeners: Dict[str, list[asyncio.Queue]] = {}

    async def subscribe(self, user_id: str) -> AsyncGenerator[str, None]:
        queue = asyncio.Queue()
        if user_id not in self.listeners:
            self.listeners[user_id] = []
        self.listeners[user_id].append(queue)
        
        try:
            while True:
                # Wait for next event in queue
                event_data = await queue.get()
                # Yield in SSE format
                yield f"data: {json.dumps(event_data)}\n\n"
        finally:
            self.remove_listener(user_id, queue)

    def remove_listener(self, user_id: str, queue: asyncio.Queue):
        if user_id in self.listeners:
            if queue in self.listeners[user_id]:
                self.listeners[user_id].remove(queue)
            if not self.listeners[user_id]:
                del self.listeners[user_id]

    def broadcast(self, user_id: str, event: str, application_id: str, data: Dict[str, Any]):
        if user_id not in self.listeners:
            return
            
        payload = {
            "event": event,
            "application_id": application_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data
        }
        
        for queue in self.listeners[user_id]:
            queue.put_nowait(payload)

# Global singleton
notifier = EventNotifier()
