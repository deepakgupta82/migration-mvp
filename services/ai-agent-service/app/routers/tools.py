"""
AI Agent Tools Router
Expose simple endpoints to exercise migrated tools (hybrid search, graph queries) within ai-agent-service.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Callable
import logging

from app.tools.hybrid_search_tool import HybridSearchTool
from app.tools.graph_query_tool import GraphQueryTool
from app.tools.rag_query_tool import RAGQueryTool

# Simple in-process tool registry (Phase C7 minimal)
_TOOL_REGISTRY: Dict[str, Callable[..., Any]] = {}

def _register_tools():
    if _TOOL_REGISTRY:
        return
    # Map simple slugs -> factory lambdas (can expand later with dependency injection)
    _TOOL_REGISTRY["hybrid_search"] = lambda project_id=None: HybridSearchTool(project_id=project_id)
    _TOOL_REGISTRY["graph_query"] = lambda project_id=None: GraphQueryTool(project_id=project_id)
    _TOOL_REGISTRY["rag_query"] = lambda project_id=None: RAGQueryTool()

_register_tools()

logger = logging.getLogger("ai-agent-tools")
router = APIRouter(prefix="/api/tools", tags=["tools"])

class HybridSearchRequest(BaseModel):
    project_id: str
    query: str

class HybridSearchResponse(BaseModel):
    project_id: str
    query: str
    result: str

@router.post("/hybrid-search", response_model=HybridSearchResponse)
async def hybrid_search(req: HybridSearchRequest):
    try:
        tool = HybridSearchTool(project_id=req.project_id)
        result = tool.run(req.query)
        return HybridSearchResponse(project_id=req.project_id, query=req.query, result=result)
    except Exception as e:
        logger.error(f"Hybrid search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class GraphQueryRequest(BaseModel):
    project_id: str
    command: str = Field(..., description="nodes|relationships|neighborhood + flags")

class GraphQueryResponse(BaseModel):
    project_id: str
    command: str
    result: str

@router.post("/graph-query", response_model=GraphQueryResponse)
async def graph_query(req: GraphQueryRequest):
    try:
        tool = GraphQueryTool(project_id=req.project_id)
        result = tool.run(req.command)
        return GraphQueryResponse(project_id=req.project_id, command=req.command, result=result)
    except Exception as e:
        logger.error(f"Graph query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ---------------- Generic Tool Registry Endpoints (C7) -----------------
class ToolInfo(BaseModel):
    slug: str
    name: str
    description: str

class ExecuteToolRequest(BaseModel):
    project_id: Optional[str] = Field(None, description="Project context (if required by tool)")
    input: str = Field(..., description="Primary input or prompt for the tool")

class ExecuteToolResponse(BaseModel):
    tool: str
    project_id: Optional[str]
    output: str
    success: bool
    error: Optional[str] = None

@router.get("/registry", response_model=List[ToolInfo])
async def list_tools():
    """List available tools in the agent service (minimal registry)."""
    out: List[ToolInfo] = []
    for slug, factory in _TOOL_REGISTRY.items():
        try:
            inst = factory(project_id=None)
            name = getattr(inst, "name", slug)
            desc = getattr(inst, "description", "(no description)")
            out.append(ToolInfo(slug=slug, name=name, description=desc))
        except Exception:
            out.append(ToolInfo(slug=slug, name=slug, description="(failed to instantiate for introspection)"))
    return out

@router.post("/{tool_slug}/execute", response_model=ExecuteToolResponse)
async def execute_tool(tool_slug: str, req: ExecuteToolRequest):
    """Execute a registered tool by slug.

    This is a synchronous convenience wrapper: in future we may add async streaming or structured
    multi-arg payloads. For now, tools expose `_run` or `run` expecting a single string input.
    """
    if tool_slug not in _TOOL_REGISTRY:
        raise HTTPException(status_code=404, detail="Tool not found")
    try:
        inst = _TOOL_REGISTRY[tool_slug](project_id=req.project_id)
        runner = getattr(inst, "run", None) or getattr(inst, "_run", None)
        if not callable(runner):
            raise RuntimeError("Tool missing run/_run method")
        output = runner(req.input)
        if output is None:
            output = "(no output)"
        return ExecuteToolResponse(tool=tool_slug, project_id=req.project_id, output=str(output)[:8000], success=True)
    except Exception as e:
        logger.error(f"Tool execution failed slug={tool_slug}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
