"""
MCP Connection Manager (skeleton)

Supports:
- stdio subprocess launch (Node-based servers like AWS labs)
- ws/sse placeholders (to be implemented)

Provides tool discovery stub and execute stub to be fleshed out later.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import logging
from typing import Dict, Any, List, Optional
from asyncio.subprocess import create_subprocess_exec

from app.core.mcp_models import MCPServerConfig, UnifiedToolSchema

logger = logging.getLogger("mcp-conn")


class MCPConnectionManager:
    def __init__(self):
        self._processes: Dict[str, asyncio.subprocess.Process] = {}
        self._locks: Dict[str, asyncio.Lock] = {}

    def _get_lock(self, server_id: str) -> asyncio.Lock:
        if server_id not in self._locks:
            self._locks[server_id] = asyncio.Lock()
        return self._locks[server_id]

    async def connect_and_discover(self, cfg: MCPServerConfig) -> List[UnifiedToolSchema]:
        """Connect to the MCP server and return discovered tools.

        For MVP: if stdio, spawn the process and assume a well-known set of tools
        for known servers (e.g., AWS labs). We will refine to real MCP handshake later.
        """
        if cfg.connection.transport == "stdio":
            return await self._spawn_stdio_and_mock_discover(cfg)
        else:
            # ws/sse not yet implemented; return empty
            logger.info(f"Transport {cfg.connection.transport} not implemented; returning no tools")
            return []

    async def _spawn_stdio_and_mock_discover(self, cfg: MCPServerConfig) -> List[UnifiedToolSchema]:
        lock = self._get_lock(cfg.id)
        async with lock:
            if cfg.id in self._processes and self._processes[cfg.id] and self._processes[cfg.id].returncode is None:
                logger.info(f"MCP stdio process already running for {cfg.name}")
            else:
                try:
                    env = os.environ.copy()
                    env.update(cfg.env or {})
                    cmd = [cfg.connection.stdio.command] + (cfg.connection.stdio.args or [])
                    logger.info(f"Launching MCP stdio server: {cmd} cwd={cfg.connection.stdio.cwd}")
                    proc = await create_subprocess_exec(
                        *cmd,
                        cwd=cfg.connection.stdio.cwd or None,
                        env=env,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    self._processes[cfg.id] = proc
                    # Brief delay to allow startup
                    await asyncio.sleep(0.3)
                except Exception as e:
                    logger.error(f"Failed to launch MCP server {cfg.name}: {e}")
                    return []

        # MOCK discovery: return basic tool list tags based on provider to unblock UI/adapter
        tools: List[UnifiedToolSchema] = []
        prov = cfg.provider
        if prov == "aws":
            names = [
                "cost_explorer.query_costs",
                "pricing.get_price",
                "resource_graph.search",
                "documentation.lookup",
                "knowledge.search",
            ]
        elif prov == "azure":
            names = [
                "resource_graph.query",
                "cost_management.actuals",
                "pricing.retail_rates",
                "docs.search",
            ]
        elif prov == "gcp":
            names = [
                "asset_inventory.search",
                "billing.costs",
                "pricing.catalog",
                "docs.search",
            ]
        else:
            names = ["echo.run", "docs.search"]

        for n in names:
            # Apply allow/deny filters
            if cfg.tool_allowlist and n not in cfg.tool_allowlist:
                continue
            if cfg.tool_denylist and n in cfg.tool_denylist:
                continue
            tools.append(
                UnifiedToolSchema(
                    name=n,
                    description=f"Tool {n} from {cfg.name}",
                    input_schema=None,
                    server_id=cfg.id,
                    provider=cfg.provider,
                )
            )
        return tools

    async def execute(self, cfg: MCPServerConfig, tool: str, args: Dict[str, Any]) -> Any:
        """Execute a tool call via MCP.

        MVP: return a mocked response to unblock wiring. Real protocol to be added later.
        """
        # Apply allow/deny
        if cfg.tool_allowlist and tool not in cfg.tool_allowlist:
            raise RuntimeError("Tool not permitted by allowlist")
        if cfg.tool_denylist and tool in cfg.tool_denylist:
            raise RuntimeError("Tool denied by policy")

        # For now, echo back
        return {
            "tool": tool,
            "args": args,
            "server": cfg.name,
            "provider": cfg.provider,
            "note": "MCP execution mocked (wire protocol to be implemented)",
        }


# Singleton
_mgr: Optional[MCPConnectionManager] = None


def get_connection_manager() -> MCPConnectionManager:
    global _mgr
    if _mgr is None:
        _mgr = MCPConnectionManager()
    return _mgr
