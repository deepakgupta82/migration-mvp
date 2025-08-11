"""Simple in-process event bus for stats delta updates (Phase 2)."""
import asyncio
import logging
from typing import Callable, Dict, List, Any

logger = logging.getLogger(__name__)

class EventBus:
    def __init__(self):
        self.handlers: Dict[str, List[Callable[[dict], Any]]] = {}
    def subscribe(self, event_type: str, handler: Callable[[dict], Any]):
        self.handlers.setdefault(event_type, []).append(handler)
    async def publish(self, event_type: str, payload: dict):
        handlers = self.handlers.get(event_type, [])
        logger.debug(f"Publishing event {event_type} to {len(handlers)} handlers")
        for h in handlers:
            try:
                res = h(payload)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                logger.error(f"Handler error for {event_type}: {e}")

_event_bus = EventBus()

def get_event_bus() -> EventBus:
    return _event_bus
