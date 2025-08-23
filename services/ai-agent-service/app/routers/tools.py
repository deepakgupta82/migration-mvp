"""
AI Agent Tools Router
Expose simple endpoints to exercise migrated tools (hybrid search, graph queries) within ai-agent-service.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import logging

from app.tools.hybrid_search_tool import HybridSearchTool
from app.tools.graph_query_tool import GraphQueryTool

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
