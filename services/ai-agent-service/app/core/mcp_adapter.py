"""
Adapters to expose MCP tools to CrewAI and AutoGen in a uniform way.

For now, we expose a simple function to list all tools across enabled servers,
and a call function to execute a tool via connection manager.
"""

from __future__ import annotations

from typing import List, Dict, Any

from app.repository.mcp_registry import get_registry
from app.core.mcp_connection import get_connection_manager
from app.core.mcp_models import UnifiedToolSchema


async def list_all_tools() -> List[UnifiedToolSchema]:
    reg = get_registry()
    tools: List[UnifiedToolSchema] = []
    for s in reg.list():
        if not s.is_enabled:
            continue
        cached = reg.get_tools(s.id)
        if cached:
            tools.extend(cached)
    return tools


async def call_tool(server_id: str, tool: str, args: Dict[str, Any]) -> Any:
    reg = get_registry()
    cfg = reg.get(server_id)
    if not cfg:
        raise RuntimeError("Server not found")
    mgr = get_connection_manager()
    return await mgr.execute(cfg, tool, args)
