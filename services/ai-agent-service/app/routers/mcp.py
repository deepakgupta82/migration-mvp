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
from datetime import datetime

from common.mcp import (
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


@router.get("/servers/{server_id}", response_model=MCPServerConfig)
async def get_server(server_id: str):
    """Get a specific MCP server by ID."""
    reg = get_registry()
    cfg = reg.get(server_id)
    if not cfg:
        raise HTTPException(status_code=404, detail="Server not found")
    return cfg


@router.post("/servers", response_model=MCPServerConfig)
async def create_server(cfg: MCPServerConfig):
    """
    Create a new MCP server with credential validation.
    
    Validates that required credentials are provided based on provider type:
    - Azure: AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID
    - GCP: GOOGLE_APPLICATION_CREDENTIALS
    - AWS: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
    """
    # Validate provider-specific credentials
    if cfg.provider == "azure":
        required_azure_creds = [
            "AZURE_CLIENT_ID",
            "AZURE_CLIENT_SECRET", 
            "AZURE_TENANT_ID"
        ]
        missing = [k for k in required_azure_creds if not cfg.env or not cfg.env.get(k)]
        if missing:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Missing required Azure credentials",
                    "missing_fields": missing,
                    "message": (
                        "Azure MCP server requires: AZURE_CLIENT_ID, "
                        "AZURE_CLIENT_SECRET, and AZURE_TENANT_ID. "
                        "Please configure these in the environment variables section."
                    )
                }
            )
    
    elif cfg.provider == "gcp":
        if not cfg.env or not cfg.env.get("GOOGLE_APPLICATION_CREDENTIALS"):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Missing required GCP credentials",
                    "missing_fields": ["GOOGLE_APPLICATION_CREDENTIALS"],
                    "message": (
                        "GCP MCP server requires: GOOGLE_APPLICATION_CREDENTIALS "
                        "(path to service account JSON key file). "
                        "Please configure this in the environment variables section."
                    )
                }
            )
    
    elif cfg.provider == "aws":
        required_aws_creds = [
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY"
        ]
        missing = [k for k in required_aws_creds if not cfg.env or not cfg.env.get(k)]
        if missing:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Missing required AWS credentials",
                    "missing_fields": missing,
                    "message": (
                        "AWS MCP server requires: AWS_ACCESS_KEY_ID and "
                        "AWS_SECRET_ACCESS_KEY. AWS_DEFAULT_REGION is recommended. "
                        "Please configure these in the environment variables section."
                    )
                }
            )
    
    # Validate transport configuration
    if not cfg.connection or not cfg.connection.transport:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Missing transport configuration",
                "message": (
                    "MCP server requires transport configuration. "
                    "Please select STDIO, WebSocket (ws), or SSE."
                )
            }
        )
    
    # Validate STDIO transport
    if cfg.connection.transport == "stdio":
        if not cfg.connection.stdio or not cfg.connection.stdio.command:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Missing STDIO command",
                    "message": (
                        "STDIO transport requires a command to execute. "
                        "Example: npx -y @azure/mcp-server"
                    )
                }
            )
    
    # Validate WebSocket transport
    elif cfg.connection.transport == "ws":
        if not cfg.connection.ws or not cfg.connection.ws.url:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Missing WebSocket URL",
                    "message": "WebSocket transport requires a URL (e.g., ws://localhost:8080)"
                }
            )
    
    # Validate SSE transport
    elif cfg.connection.transport == "sse":
        if not cfg.connection.sse or not cfg.connection.sse.url:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Missing SSE URL",
                    "message": "SSE transport requires a URL (e.g., http://localhost:8080/events)"
                }
            )
    
    # Store server configuration
    reg = get_registry()
    reg.upsert(cfg)
    
    logger.info(
        f"Created MCP server: {cfg.name} (provider={cfg.provider}, "
        f"transport={cfg.connection.transport})"
    )
    
    return cfg


@router.put("/servers/{server_id}", response_model=MCPServerConfig)
async def update_server(server_id: str, cfg: MCPServerConfig):
    """
    Update an existing MCP server configuration with validation.
    
    Validates that required credentials are provided based on provider type.
    """
    if cfg.id != server_id:
        raise HTTPException(status_code=400, detail="ID mismatch")
    
    # Run same validation as create_server
    # Validate provider-specific credentials
    if cfg.provider == "azure":
        required_azure_creds = [
            "AZURE_CLIENT_ID",
            "AZURE_CLIENT_SECRET", 
            "AZURE_TENANT_ID"
        ]
        missing = [k for k in required_azure_creds if not cfg.env or not cfg.env.get(k)]
        if missing:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Missing required Azure credentials",
                    "missing_fields": missing,
                    "message": (
                        "Azure MCP server requires: AZURE_CLIENT_ID, "
                        "AZURE_CLIENT_SECRET, and AZURE_TENANT_ID. "
                        "Please configure these in the environment variables section."
                    )
                }
            )
    
    elif cfg.provider == "gcp":
        if not cfg.env or not cfg.env.get("GOOGLE_APPLICATION_CREDENTIALS"):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Missing required GCP credentials",
                    "missing_fields": ["GOOGLE_APPLICATION_CREDENTIALS"],
                    "message": (
                        "GCP MCP server requires: GOOGLE_APPLICATION_CREDENTIALS "
                        "(path to service account JSON key file). "
                        "Please configure this in the environment variables section."
                    )
                }
            )
    
    elif cfg.provider == "aws":
        required_aws_creds = [
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY"
        ]
        missing = [k for k in required_aws_creds if not cfg.env or not cfg.env.get(k)]
        if missing:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Missing required AWS credentials",
                    "missing_fields": missing,
                    "message": (
                        "AWS MCP server requires: AWS_ACCESS_KEY_ID and "
                        "AWS_SECRET_ACCESS_KEY. AWS_DEFAULT_REGION is recommended. "
                        "Please configure these in the environment variables section."
                    )
                }
            )
    
    reg = get_registry()
    reg.upsert(cfg)
    
    logger.info(f"Updated MCP server: {cfg.name} (id={server_id})")
    
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
    # Mark health based on ability to connect (mock: treat as healthy even if 0 tools for now)
    try:
        cfg.health_status = "healthy"
        cfg.last_discovered_at = datetime.utcnow().isoformat()
        reg.upsert(cfg)
    except Exception:
        pass
    reg.set_tools(server_id, tools)
    return tools


@router.get("/servers/{server_id}/tools", response_model=List[UnifiedToolSchema])
async def get_tools(server_id: str):
    reg = get_registry()
    if not reg.get(server_id):
        raise HTTPException(status_code=404, detail="Server not found")
    cfg = reg.get(server_id)
    age = reg.tools_cache_age(server_id)
    # If TTL expired, attempt background refresh (best-effort)
    try:
        ttl = (cfg.discovery_cache_ttl_sec or 900)
        if age is None or age > ttl:
            try:
                mgr = get_connection_manager()
                tools = await mgr.connect_and_discover(cfg)
                cfg.health_status = "healthy"
                cfg.last_discovered_at = datetime.utcnow().isoformat()
                reg.upsert(cfg)
                reg.set_tools(server_id, tools)
            except Exception as e:
                logger.warning(f"Background tools refresh failed for {server_id}: {e}")
    except Exception:
        pass
    return reg.get_tools(server_id)


@router.get("/tools", response_model=List[UnifiedToolSchema])
async def list_all_tools(server_id: str = None, provider: str = None):
    """
    List all available MCP tools across servers with optional filters.
    
    Args:
        server_id: Optional filter by server ID
        provider: Optional filter by provider (aws, azure, gcp, custom)
    """
    reg = get_registry()
    all_tools = []
    
    servers_to_query = [reg.get(server_id)] if server_id else reg.list()
    
    for server in servers_to_query:
        if not server:
            continue
        if provider and server.provider != provider:
            continue
        if not server.is_enabled:
            continue
        
        tools = reg.get_tools(server.id)
        all_tools.extend(tools)
    
    return all_tools


@router.get("/servers/{server_id}/health")
async def server_health(server_id: str):
    reg = get_registry()
    cfg = reg.get(server_id)
    if not cfg:
        raise HTTPException(status_code=404, detail="Server not found")
    # Health is derived from last discovery success for now
    return {
        "id": cfg.id,
        "name": cfg.name,
        "status": cfg.health_status or "unknown",
        "last_discovered_at": cfg.last_discovered_at,
        "last_health_check_at": cfg.last_health_check_at,
    }


@router.post("/execute", response_model=ExecuteToolResponse)
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
