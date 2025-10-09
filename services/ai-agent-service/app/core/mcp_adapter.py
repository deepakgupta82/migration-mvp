"""
Adapters to expose MCP tools to CrewAI and AutoGen in a uniform way.

For now, we expose a simple function to list all tools across enabled servers,
and a call function to execute a tool via connection manager.
"""

from __future__ import annotations

from typing import List, Dict, Any

from app.repository.mcp_registry import get_registry
from app.core.mcp_connection import get_connection_manager
from common.mcp import UnifiedToolSchema
from app.tools.mcp_passthrough_tool import MCPPassthroughTool


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


def build_crewai_tools() -> List[object]:
    """Build CrewAI tool instances as MCP passthrough tools from cached registry tools.

    Only uses cached tool discovery to avoid blocking. UI should trigger discovery.
    """
    reg = get_registry()
    crew_tools: List[object] = []
    for s in reg.list():
        if not s.is_enabled:
            continue
        for t in reg.get_tools(s.id):
            crew_tools.append(MCPPassthroughTool(server_id=s.id, tool_name=t.name, provider=t.provider))
    return crew_tools
