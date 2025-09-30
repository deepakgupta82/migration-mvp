"""
MCP Registry API

Endpoints:
- GET/POST/PUT/DELETE /api/mcp/servers
- POST /api/mcp/servers/{id}/discover -> caches tool list
- GET /api/mcp/servers/{id}/tools
- POST /api/mcp/tools/execute
"""

from fastapi import APIRouter, HTTPException
from typing import List
import logging

from app.core.mcp_models import (
    MCPServerConfig,
    MCPServerWithTools,
    UnifiedToolSchema,
    ExecuteToolRequest,
    ExecuteToolResponse,
)
from app.repository.mcp_registry import get_registry
from app.core.mcp_connection import get_connection_manager

logger = logging.getLogger("mcp-router")

router = APIRouter(prefix="/api/mcp", tags=["MCP"])


@router.get("/servers", response_model=List[MCPServerConfig])
async def list_servers():
    reg = get_registry()
    return reg.list()


@router.post("/servers", response_model=MCPServerConfig)
async def create_server(cfg: MCPServerConfig):
    reg = get_registry()
    reg.upsert(cfg)
    return cfg


@router.put("/servers/{server_id}", response_model=MCPServerConfig)
async def update_server(server_id: str, cfg: MCPServerConfig):
    if cfg.id != server_id:
        raise HTTPException(status_code=400, detail="ID mismatch")
    reg = get_registry()
    reg.upsert(cfg)
    return cfg


@router.delete("/servers/{server_id}")
async def delete_server(server_id: str):
    reg = get_registry()
    ok = reg.delete(server_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Not found")
    return {"deleted": True}


@router.post("/servers/{server_id}/discover", response_model=List[UnifiedToolSchema])
async def discover_tools(server_id: str):
    reg = get_registry()
    cfg = reg.get(server_id)
    if not cfg:
        raise HTTPException(status_code=404, detail="Server not found")
    mgr = get_connection_manager()
    tools = await mgr.connect_and_discover(cfg)
    reg.set_tools(server_id, tools)
    return tools


@router.get("/servers/{server_id}/tools", response_model=List[UnifiedToolSchema])
async def get_tools(server_id: str):
    reg = get_registry()
    if not reg.get(server_id):
        raise HTTPException(status_code=404, detail="Server not found")
    return reg.get_tools(server_id)


@router.post("/tools/execute", response_model=ExecuteToolResponse)
async def execute_tool(req: ExecuteToolRequest):
    reg = get_registry()
    cfg = reg.get(req.server_id)
    if not cfg:
        raise HTTPException(status_code=404, detail="Server not found")
    mgr = get_connection_manager()
    try:
        out = await mgr.execute(cfg, req.tool, req.args)
        return ExecuteToolResponse(success=True, output=out)
    except Exception as e:
        logger.error(f"MCP tool execution failed: {e}")
        return ExecuteToolResponse(success=False, error=str(e))
