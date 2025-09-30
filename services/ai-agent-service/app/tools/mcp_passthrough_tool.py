"""
CrewAI tool wrapper to call MCP tools via ai-agent-service REST API.

This avoids event loop issues by making HTTP calls to our own service endpoints.
"""
from __future__ import annotations

import os
import json
import logging
from typing import Optional, Dict, Any

from crewai.tools import BaseTool

try:
    import requests
except Exception:  # pragma: no cover
    requests = None

logger = logging.getLogger(__name__)


class MCPPassthroughTool(BaseTool):
    name: str = "MCP Tool"
    description: str = (
        "Calls a configured Model Context Protocol (MCP) tool. "
        "Input should be a JSON object with fields appropriate for the tool."
    )

    def __init__(self, server_id: str, tool_name: str, provider: str, **kwargs):
        super().__init__(**kwargs)
        self.server_id = server_id
        self.tool_name = tool_name
        self.provider = provider
        # Improve tool metadata
        self.name = f"mcp::{provider}::{tool_name}"
        self.description = f"Invoke MCP tool '{tool_name}' on server provider={provider}. Supply JSON args."

    class Config:
        arbitrary_types_allowed = True

    def run(self, args_json: str) -> str:
        if requests is None:
            return "requests library not available"
        base = os.getenv("AI_AGENT_BASE_URL", "http://localhost:8008")
        url = f"{base.rstrip('/')}/api/mcp/tools/execute"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
        }
        try:
            if isinstance(args_json, str) and args_json.strip():
                try:
                    args: Dict[str, Any] = json.loads(args_json)
                except Exception:
                    # accept simple text as {query: ...}
                    args = {"query": args_json}
            else:
                args = {}
            payload = {"server_id": self.server_id, "tool": self.tool_name, "args": args}
            resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
            if not resp.ok:
                return f"MCP call failed: HTTP {resp.status_code}: {resp.text[:500]}"
            data = resp.json()
            if data.get("success"):
                return json.dumps(data.get("output"), ensure_ascii=False)
            return f"MCP error: {data.get('error')}"
        except Exception as e:
            logger.error(f"MCPPassthroughTool error: {e}")
            return f"MCP call exception: {e}"
