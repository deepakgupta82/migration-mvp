"""
Lightweight Agent log streaming utilities for AI Agent service
Decoupled from backend implementation. Safe no-op if no websocket.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, Optional

try:
    from langchain.callbacks.base import BaseCallbackHandler  # type: ignore
except Exception:  # Fallback if langchain not present in this service
    class BaseCallbackHandler:  # type: ignore
        pass


class AgentLogStreamHandler(BaseCallbackHandler):
    """Minimal callback handler to stream agent interactions via WebSocket"""

    def __init__(self, websocket: Optional[Any] = None):
        super().__init__()
        self.websocket = websocket
        self.current_agent = None

    async def _send_text(self, text: str):
        if self.websocket is None:
            return
        try:
            await self.websocket.send_text(text)
        except Exception:
            # swallow errors to avoid breaking agent flow
            pass

    async def _send_json(self, data: Dict[str, Any]):
        await self._send_text(json.dumps(data))

    def on_agent_start(self, agent, **kwargs: Any) -> Any:
        self.current_agent = agent
        data = {
            "type": "agent_start",
            "timestamp": datetime.utcnow().isoformat(),
            "agent_name": getattr(agent, "role", "Agent"),
            "goal": getattr(agent, "goal", ""),
        }
        if self.websocket:
            asyncio.create_task(self._send_json(data))

    def on_agent_finish(self, finish, **kwargs: Any) -> Any:
        name = getattr(self.current_agent, "role", "Agent")
        data = {
            "type": "agent_finish",
            "timestamp": datetime.utcnow().isoformat(),
            "agent_name": name,
            "output": str(getattr(finish, "return_values", finish))[:1000],
        }
        if self.websocket:
            asyncio.create_task(self._send_json(data))

    def on_tool_end(self, output: str, **kwargs: Any) -> Any:
        name = getattr(self.current_agent, "role", "Agent")
        data = {
            "type": "tool_result",
            "timestamp": datetime.utcnow().isoformat(),
            "agent_name": name,
            "output": str(output)[:1000],
        }
        if self.websocket:
            asyncio.create_task(self._send_json(data))

    def set_current_agent(self, agent):
        self.current_agent = agent
