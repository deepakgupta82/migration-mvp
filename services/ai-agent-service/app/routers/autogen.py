"""
AutoGen Co-pilot REST API Routes
Provides endpoints for conversational AI assistance using Microsoft AutoGen
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request
import asyncio
from typing import Dict, List, Any, Optional, Tuple
import logging
import uuid
from datetime import datetime
from pydantic import BaseModel, Field
import httpx

from ..core.autogen_copilot import AutoGenCopilot
from ..websockets.autogen_ws import websocket_manager
from ..repository.conversations import get_conversation_repository, ConversationRepository
from ..core.mcp_adapter import list_all_tools, call_tool
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
from services.shared.service_client import get_service_client

logger = logging.getLogger("autogen-api")

router = APIRouter()

# Request/Response Models
class ConversationRequest(BaseModel):
    """Request model for starting a new conversation"""
    message: str = Field(..., description="User's question or request")
    context: Optional[Dict[str, Any]] = Field(None, description="Project context information")
    selected_agents: Optional[List[str]] = Field(None, description="Specific agents to include in conversation")
    session_id: Optional[str] = Field(None, description="Optional session ID (auto-generated if not provided)")
    project_id: str = Field(..., description="Project identifier used to resolve LLM configuration")

class FollowUpRequest(BaseModel):
    """Request model for follow-up messages"""
    message: str = Field(..., description="Follow-up question or request")
    session_id: str = Field(..., description="Session ID from previous conversation")
    project_id: str = Field(..., description="Project identifier used to resolve LLM configuration")

class ConversationResponse(BaseModel):
    """Response model for conversation results"""
    status: str
    session_id: Optional[str] = None
    timestamp: Optional[str] = None
    duration_seconds: Optional[float] = None
    participating_agents: Optional[List[str]] = None
    message_count: Optional[int] = None
    recommendations: Optional[List[Dict[str, str]]] = None
    action_items: Optional[List[Dict[str, str]]] = None
    summary: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class AgentsListResponse(BaseModel):
    """Response model for available agents"""
    available_agents: Dict[str, str]
    total_count: int

class DiscussionStartRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None
    selected_agents: Optional[List[str]] = None
    session_id: Optional[str] = None
    project_id: str

class DiscussionQueryRequest(BaseModel):
    message: str
    session_id: str
    override_agents: Optional[List[str]] = None
    fetch_context: bool = True
    project_id: str

class DiscussionResponse(BaseModel):
    status: str
    session_id: str
    analysis: Dict[str, Any]
    participating_agents: List[str]
    result: Dict[str, Any]
    gathered_context: Optional[Dict[str, Any]] = None
    timestamp: str
    error: Optional[str] = None

# --- Chat Bubble Models ---
class ChatRequest(BaseModel):
    """Request model for chat bubble queries"""
    message: str = Field(..., description="User's question")
    session_id: Optional[str] = Field(None, description="Session ID for conversation memory (auto-generated if not provided)")
    project_id: str = Field(..., description="Project identifier for LLM config resolution")
    process_type: Optional[str] = Field(None, description="Optional process type for process-specific LLM config")

class ChatResponse(BaseModel):
    """Response model for chat bubble queries"""
    status: str
    session_id: str
    answer: str
    sources: List[Dict[str, Any]] = Field(default_factory=list, description="Source citations from vector/graph/docs")
    graph_entities: List[Dict[str, Any]] = Field(default_factory=list, description="Related knowledge graph entities")
    timestamp: str
    conversation_context: Dict[str, Any] = Field(default_factory=dict, description="Current conversation state")
    error: Optional[str] = None
    error_code: Optional[str] = None

# --- Simple MCP passthrough for AutoGen consumers ---
class MCPExecuteRequest(BaseModel):
    server_id: str
    tool: str
    args: Dict[str, Any] = Field(default_factory=dict)

@router.get("/mcp/tools")
async def autogen_mcp_list():
    tools = await list_all_tools()
    return [t.model_dump() for t in tools]

@router.post("/mcp/execute")
async def autogen_mcp_execute(req: MCPExecuteRequest):
    try:
        out = await call_tool(req.server_id, req.tool, req.args)
        return {"success": True, "output": out}
    except Exception as e:
        return {"success": False, "error": str(e)}

# Lightweight in-module query analysis & context gathering stubs
def _analyze_query(message: str, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Very lightweight keyword heuristic query analysis (placeholder)."""
    lowered = message.lower()
    domains = []
    if any(k in lowered for k in ["cost", "budget", "price"]):
        domains.append("cost")
    if any(k in lowered for k in ["secure", "security", "iam", "compliance"]):
        domains.append("security")
    if any(k in lowered for k in ["migrate", "migration", "lift", "refactor"]):
        domains.append("migration")
    if any(k in lowered for k in ["data", "database", "etl", "warehouse"]):
        domains.append("data")
    if any(k in lowered for k in ["modern", "microservice", "container", "kubernetes"]):
        domains.append("modernization")

    complexity = "simple"
    if len(message) > 140 or any(k in lowered for k in ["strategy", "architecture", "comprehensive", "plan"]):
        complexity = "complex"
    elif len(message) > 70:
        complexity = "moderate"

    return {
        "domains": domains or ["general"],
        "complexity": complexity,
        "intent": "analysis" if "analy" in lowered else "question",
        "tokens": len(message.split()),
    }

def _select_agents(analysis: Dict[str, Any]) -> List[str]:
    mapping = {
        "cost": "cost_optimizer",
        "security": "security_expert",
        "migration": "migration_architect",
        "data": "data_expert",
        "modernization": "app_modernization",
    }
    agents = []
    for d in analysis.get("domains", []):
        if d in mapping and mapping[d] not in agents:
            agents.append(mapping[d])
    # Always ensure at least migration_architect present
    if not agents:
        agents.append("migration_architect")
    # Add devops_expert for complex queries
    if analysis.get("complexity") == "complex" and "devops_expert" not in agents:
        agents.append("devops_expert")
    return agents

async def _gather_context(message: str, context: Optional[Dict[str, Any]], project_id: Optional[str] = None, correlation_id: Optional[str] = None) -> Dict[str, Any]:
    """Gather contextual signals from vector, graph, and document services.

    Returns a dict with limited, relevance-oriented snippets to keep prompt size controlled.
    Any per-source failure is logged and surfaced in 'errors' list without aborting the whole call.
    """
    client = await get_service_client()
    errors: List[str] = []
    vector_snippets: List[Dict[str, Any]] = []
    graph_facts: List[Dict[str, Any]] = []
    doc_insights: List[Dict[str, Any]] = []
    project_id = project_id or (context or {}).get("project_id")
    # Hard caps
    VECTOR_LIMIT = 5
    FACT_LIMIT = 8
    INSIGHT_LIMIT = 5

    async def fetch_vectors():
        if not project_id:
            return
        try:
            payload = {"query": message[:400], "limit": VECTOR_LIMIT, "include_metadata": True}
            # Use vector-service standardized API path
            res = await client.post("vector", f"/api/vectors/projects/{project_id}/search", json=payload, allow_status=[404])
            status = res.get("status_code", 200) if isinstance(res, dict) else 200
            if status == 404:
                # Attempt lazy collection creation then stop silently
                try:
                    await client.post("vector", f"/api/vectors/projects/{project_id}/collection")
                except Exception:
                    pass  # non-fatal
                return
            items = res.get("results", []) if isinstance(res, dict) else []
            for r in items[:VECTOR_LIMIT]:
                vector_snippets.append({
                    "text": r.get("content") or r.get("text") or "",
                    "score": r.get("score"),
                    "metadata": r.get("metadata", {})
                })
        except Exception as e:
            # Only record as error if not a benign 404 handled above
            msg = str(e)
            if "404" in msg:
                return  # suppress noisy expected absence
            errors.append(f"vector:{type(e).__name__}:{e}")

    async def fetch_graph():
        if not project_id:
            return
        try:
            # Use graph-service standardized API path
            res = await client.get("graph", f"/api/graphs/projects/{project_id}/discoveries", allow_status=[404])
            discs = res.get("discoveries", []) if isinstance(res, dict) else []
            for d in discs[:FACT_LIMIT]:
                graph_facts.append({
                    "text": d.get("text"),
                    "category": d.get("category"),
                    "confidence": d.get("confidence")
                })
        except Exception as e:
            msg = str(e)
            if "404" in msg:
                return
            errors.append(f"graph:{type(e).__name__}:{e}")

    async def fetch_graph_counts_if_needed():
        """If the query asks for counts (e.g., 'how many' / 'count'), fetch from graph-service count endpoints."""
        if not project_id:
            return
        low = (message or "").lower()
        if ("how many" in low) or ("count" in low):
            try:
                # If OS mentioned, prefer servers-by-os; else total Server nodes
                os_q = None
                for token in ["windows", "linux", "red hat", "ubuntu", "rhel", "centos", "suse"]:
                    if token in low:
                        os_q = token
                        break
                if os_q:
                    res = await client.get("graph", f"/api/graphs/projects/{project_id}/counts/servers/by-os", params={"q": os_q})
                    cnt = res.get("count", 0) if isinstance(res, dict) else 0
                    graph_facts.append({
                        "text": f"There are {cnt} servers matching OS contains '{os_q}'.",
                        "category": "count",
                        "confidence": 0.99
                    })
                else:
                    res = await client.get("graph", f"/api/graphs/projects/{project_id}/counts/nodes", params={"node_type": "Server"})
                    cnt = res.get("count", 0) if isinstance(res, dict) else 0
                    graph_facts.append({
                        "text": f"There are {cnt} Server nodes in the project graph.",
                        "category": "count",
                        "confidence": 0.99
                    })
            except Exception as e:
                errors.append(f"graph_count:{type(e).__name__}:{e}")

    async def fetch_docs():
        if not project_id:
            return
        try:
            # Try primary documented path first
            paths = [
                f"/api/documents/{project_id}/insights",           # current
                f"/api/documents/analysis/{project_id}/insights",  # potential alt prefix
            ]
            last_exc: Optional[Exception] = None
            for p in paths:
                try:
                    res = await client.get("document", p, params={"allow_analysis": "false"}, allow_status=[404, 422, 403])
                    status = res.get("status_code", 200) if isinstance(res, dict) else 200
                    # Treat 404 / 403 / 422 as benign: no insights available yet
                    if status in (404, 403, 422):
                        if status == 422:
                            logger.warning(f"Insights endpoint validation 422 at {p} project={project_id} (benign skip)")
                        if status == 403:
                            logger.info(f"Insights endpoint requires allow_analysis but was denied at {p} (skip)")
                        continue
                    insights = res.get("insights", []) if isinstance(res, dict) else []
                    for ins in insights[:INSIGHT_LIMIT]:
                        doc_insights.append({
                            "title": ins.get("title") or ins.get("category") or ins.get("key") or f"Insight {len(doc_insights)+1}",
                            "summary": ins.get("summary") or ins.get("text") or ins.get("content_summary") or ins.get("description"),
                            "category": ins.get("category") or ins.get("type")
                        })
                    # if we got any insights, stop trying more paths
                    if doc_insights:
                        break
                except Exception as inner:
                    last_exc = inner
                    continue
            if last_exc and not doc_insights:
                # Only record one condensed error entry
                errors.append(f"document:{type(last_exc).__name__}:{last_exc}")
        except Exception as e:
            msg = str(e)
            # Suppress benign 404/422 from service client noise
            if "404" in msg or "422" in msg:
                return
            errors.append(f"document:{type(e).__name__}:{e}")

    # Run in parallel
    await asyncio.gather(fetch_vectors(), fetch_graph(), fetch_docs(), fetch_graph_counts_if_needed())

    context_result = {
        "vector_snippets": vector_snippets,
        "graph_facts": graph_facts,
        "document_insights": doc_insights,
        "provided_context": context or {},
        "errors": errors,
        "counts": {
            "vector_snippets": len(vector_snippets),
            "graph_facts": len(graph_facts),
            "document_insights": len(doc_insights)
        }
    }
    try:
        logger.debug(
            "context_gather project=%s counts=%s errors=%d raw_errors=%s", 
            project_id, context_result.get("counts"), len(errors), errors[:3]
        )
    except Exception:
        pass
    return context_result

# Global AutoGen instance (will be initialized in main.py)
autogen_copilot: Optional[AutoGenCopilot] = None

def get_autogen_copilot() -> AutoGenCopilot:
    """Dependency to get AutoGen copilot instance"""
    if autogen_copilot is None:
        raise HTTPException(status_code=503, detail="AutoGen copilot not available")
    return autogen_copilot

def set_autogen_copilot(copilot: AutoGenCopilot):
    """Set the global AutoGen copilot instance"""
    global autogen_copilot
    autogen_copilot = copilot

# ---------------- Project LLM Config Helpers -----------------
class ProjectLLMConfigError(Exception):
    pass

async def _fetch_project_llm_config(project_id: str) -> Dict[str, Any]:
    """Fetch the project's default LLM configuration from project-service.

    Expects project-service to expose endpoint returning something like:
    {
       "project_id": "...",
       "default_llm": { "provider": "openai", "model": "gpt-4o-mini", "api_key": "sk-..." }
    }
    Adjust the path if actual service differs.
    """
    if not project_id:
        raise ProjectLLMConfigError("project_id is required")
    try:
        client = await get_service_client()
        # Attempt primary endpoint (returns dict, not httpx.Response)
        data = await client.get("project", f"/api/projects/{project_id}/llm-config")
        status_code = data.get("status_code", 200)
        if status_code == 404:
            # Fallback older style endpoint: project object containing columns
            project_data = await client.get("project", f"/api/projects/{project_id}")
            status_code = project_data.get("status_code", 200)
            if status_code >= 400:
                raise ProjectLLMConfigError(f"Project service returned {status_code}")
            # Derive config from project columns if possible
            llm_cfg = {
                "provider": project_data.get("llm_provider"),
                "model": project_data.get("llm_model"),
                "api_key": None,  # cannot retrieve raw key from project row
            }
        else:
            # Expect normalized wrapper with default_llm
            if status_code >= 400:
                raise ProjectLLMConfigError(f"Project service returned {status_code}")
            llm_cfg = data.get("default_llm") or data.get("llm") or data.get("llm_config")

        # STRICT ENFORCEMENT: No fallback to global/shared configs. Project must have complete config.
        if not llm_cfg:
            raise ProjectLLMConfigError("Project has no default LLM configuration (default_llm not set).")

        missing = [k for k in ("model", "api_key") if k not in llm_cfg or not llm_cfg.get(k)]
        if missing:
            # Explicitly instruct caller what to do
            raise ProjectLLMConfigError(
                "Incomplete project LLM configuration: missing " + ", ".join(missing) +
                ". Please set the project's default LLM (provider, model, api_key) before using discussions."
            )

        if "provider" not in llm_cfg or not llm_cfg.get("provider"):
            llm_cfg["provider"] = "openai"
        return llm_cfg
    except ProjectLLMConfigError:
        raise
    except Exception as e:
        raise ProjectLLMConfigError(f"Failed to fetch project LLM config: {e}")

async def _ensure_project_llm(project_id: str, copilot: AutoGenCopilot) -> Tuple[Dict[str, Any], bool]:
    """Ensure copilot has been configured for this project's LLM settings.

    Returns (llm_config, applied_now) where applied_now indicates whether a new configuration
    was applied (triggering agent (re)initialization).
    """
    llm_cfg = await _fetch_project_llm_config(project_id)
    # Decide whether to (re)apply: if copilot currently has no model client or differs in model/api key.
    applied = False
    try:
        current_model = getattr(copilot, "_current_model", None)
        current_key_hash = getattr(copilot, "_current_key_hash", None)
        import hashlib
        key_hash = hashlib.sha256(llm_cfg["api_key"].encode()).hexdigest()
        if (current_model != llm_cfg["model"]) or (current_key_hash != key_hash):
            # Apply using project-aware signature (project_id, llm_config dict)
            copilot.apply_project_llm_config(project_id, {
                "api_key": llm_cfg["api_key"],
                "model": llm_cfg["model"],
                "provider": llm_cfg.get("provider", "openai"),
                "temperature": llm_cfg.get("temperature"),
                "max_tokens": llm_cfg.get("max_tokens")
            })
            copilot._current_model = llm_cfg["model"]  # track
            copilot._current_key_hash = key_hash
            applied = True
    except AttributeError:
        # Older copilot version or structure changed; just apply
        copilot.apply_project_llm_config(project_id, {
            "api_key": llm_cfg["api_key"],
            "model": llm_cfg["model"],
            "provider": llm_cfg.get("provider", "openai"),
            "temperature": llm_cfg.get("temperature"),
            "max_tokens": llm_cfg.get("max_tokens")
        })
        applied = True
    return llm_cfg, applied

@router.get("/agents", response_model=AgentsListResponse)
async def get_available_agents(
    copilot: AutoGenCopilot = Depends(get_autogen_copilot)
):
    """Get list of available AutoGen agents and their descriptions"""
    try:
        agents = copilot.get_available_agents()
        return AgentsListResponse(
            available_agents=agents,
            total_count=len(agents)
        )
    except Exception as e:
        logger.error(f"Error getting available agents: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get available agents: {str(e)}")

@router.post("/chat", response_model=ChatResponse)
async def chat_query(
    request: ChatRequest,
    http_request: Request,
    copilot: AutoGenCopilot = Depends(get_autogen_copilot)
):
    """
    Lightweight conversational agent for chat bubble
    - Single agent (Project Assistant)
    - Session-based conversation memory
    - Full context gathering (vector + graph + docs)
    - Project/process-specific LLM (NO global fallback)
    - Structured response with sources
    """
    try:
        # Generate session ID if not provided
        session_id = request.session_id or str(uuid.uuid4())
        
        logger.info(f"Chat query for session {session_id}, project {request.project_id}")
        
        # Enforce project/process LLM config (NO global fallback)
        try:
            llm_cfg, applied = await _ensure_project_llm(request.project_id, copilot)
            if applied:
                logger.info(f"Applied project LLM config for chat session {session_id} (model={llm_cfg.get('model')})")
        except ProjectLLMConfigError as ce:
            logger.warning(f"Chat query rejected - no LLM config for project {request.project_id}: {ce}")
            return ChatResponse(
                status="error",
                session_id=session_id,
                answer="",
                timestamp=datetime.utcnow().isoformat(),
                error=f"No LLM configuration found for this project. Please configure a default LLM in Project Settings → LLM Configuration.",
                error_code="LLM_CONFIG_REQUIRED"
            )
        except Exception as ce:
            logger.error(f"Failed to apply project LLM config for chat: {ce}")
            raise HTTPException(status_code=500, detail=f"Failed to apply project LLM config: {ce}")
        
        # Gather context from vector, graph, and document services
        gathered_context = await _gather_context(request.message, None, project_id=request.project_id)
        
        logger.info(
            f"Chat context gathered for session {session_id}: "
            f"vectors={gathered_context.get('counts', {}).get('vector_snippets', 0)}, "
            f"facts={gathered_context.get('counts', {}).get('graph_facts', 0)}, "
            f"insights={gathered_context.get('counts', {}).get('document_insights', 0)}"
        )
        
        # Call copilot chat_query method
        result = await copilot.chat_query(
            user_message=request.message,
            session_id=session_id,
            project_id=request.project_id,
            context=gathered_context,
            process_type=request.process_type
        )
        
        # Return structured response
        return ChatResponse(
            status=result.get("status", "success"),
            session_id=result.get("session_id", session_id),
            answer=result.get("answer", ""),
            sources=result.get("sources", []),
            graph_entities=result.get("graph_entities", []),
            timestamp=result.get("timestamp", datetime.utcnow().isoformat()),
            conversation_context=result.get("conversation_context", {}),
            error=result.get("error"),
            error_code=result.get("error_code")
        )
        
    except Exception as e:
        logger.error(f"Chat query failed for session {session_id}: {e}")
        return ChatResponse(
            status="error",
            session_id=session_id,
            answer="",
            timestamp=datetime.utcnow().isoformat(),
            error=f"An error occurred while processing your question: {str(e)}",
            error_code="INTERNAL_ERROR"
        )

@router.post("/discussions/start", response_model=DiscussionResponse)
async def start_discussion(
    req: DiscussionStartRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    copilot: AutoGenCopilot = Depends(get_autogen_copilot)
):
    """Start a discussion (intelligent wrapper around conversation start with agent selection & context)."""
    try:
        # Ensure project LLM config applied
        try:
            llm_cfg, applied = await _ensure_project_llm(req.project_id, copilot)
            if applied:
                logger.info(f"Applied project LLM config for project {req.project_id} (model={llm_cfg.get('model')})")
        except ProjectLLMConfigError as ce:
            raise HTTPException(status_code=400, detail=f"LLM config error: {ce}")
        except Exception as ce:
            raise HTTPException(status_code=500, detail=f"Failed to apply project LLM config: {ce}")
        # Determine or infer session id
        session_id = req.session_id
        if not session_id:
            # Try to infer from the most recent WS connection (same origin, if any)
            try:
                states = websocket_manager.conversation_states
                if states:
                    req_origin = request.headers.get("origin") or request.headers.get("Origin")
                    # Prefer sessions matching the same origin
                    matching = [
                        (sid, st) for sid, st in states.items()
                        if st.get("origin") and req_origin and st.get("origin") == req_origin
                    ]
                    if matching:
                        session_id = max(matching, key=lambda kv: kv[1].get("start_time", ""))[0]
                    else:
                        # Fallback: pick the latest connected session
                        session_id = max(states.items(), key=lambda kv: kv[1].get("start_time", ""))[0]
            except Exception:
                session_id = None
        session_id = session_id or str(uuid.uuid4())
        analysis = _analyze_query(req.message, req.context)
        selected = req.selected_agents or _select_agents(analysis)
        gathered_context = await _gather_context(req.message, req.context, project_id=req.project_id)
        try:
            logger.info(
                "gathered_context project=%s vectors=%d facts=%d doc_insights=%d errors=%d",
                req.project_id,
                gathered_context.get("counts", {}).get("vector_snippets", 0),
                gathered_context.get("counts", {}).get("graph_facts", 0),
                gathered_context.get("counts", {}).get("document_insights", 0),
                len(gathered_context.get("errors", [])),
            )
        except Exception:
            pass

        # Check if WebSocket streaming is available for this session, with short retry to avoid races
        websocket_available = copilot.has_websocket_connection(session_id)
        # If not found, try to alias this session to the latest WS from same Origin
        if not websocket_available:
            try:
                req_origin = request.headers.get("origin") or request.headers.get("Origin")
                target_sid = websocket_manager.find_latest_session_by_origin(req_origin)
                if target_sid and target_sid != session_id:
                    websocket_manager.register_alias(session_id, target_sid)
                    websocket_available = copilot.has_websocket_connection(session_id)
            except Exception:
                pass
        if not websocket_available:
            # Briefly wait for registration if the client opened WS just before this REST call
            for _ in range(3):
                await asyncio.sleep(0.1)
                if copilot.has_websocket_connection(session_id):
                    websocket_available = True
                    break
        if websocket_available:
            logger.info(f"WebSocket connection detected for discussion session {session_id}, enabling streaming")

            # Start discussion in background for streaming
            background_tasks.add_task(
                _run_discussion_with_streaming,
                copilot,
                req.message,
                session_id,
                gathered_context,
                selected,
                req.project_id,
                analysis
            )

            # Return immediate response for WebSocket streaming
            return DiscussionResponse(
                status="streaming",
                session_id=session_id,
                analysis=analysis,
                participating_agents=selected,
                result={"status": "streaming", "message": "Discussion started with WebSocket streaming enabled"},
                gathered_context=gathered_context,
                timestamp=datetime.utcnow().isoformat(),
            )
        else:
            # No WebSocket, run synchronously
            logger.info(f"No WebSocket connection for discussion session {session_id}, running synchronously")

            # Provide entire gathered_context so formatting function can embed sections
            result = await copilot.start_conversation(
                user_message=req.message,
                session_id=session_id,
                context=gathered_context,
                selected_agents=selected,
            )
            # Persist via existing path (already done inside start_conversation route logic – replicate minimal)
            try:
                repo = get_conversation_repository()
                repo.save_conversation_result(session_id, req.message, req.context, result)
            except Exception as pe:
                logger.warning(f"Discussion persistence failed {session_id}: {pe}")
            resp = DiscussionResponse(
                status=result.get("status", "unknown"),
                session_id=session_id,
                analysis=analysis,
                participating_agents=result.get("participating_agents", selected),
                result=result,
                gathered_context=gathered_context,
                timestamp=datetime.utcnow().isoformat(),
            )
            # If a WS connects late within a brief window, emit the final result so UI displays it
            try:
                await asyncio.sleep(0.1)
                if copilot.has_websocket_connection(session_id):
                    await copilot.stream_message_to_websocket(session_id, "conversation_completed", {"result": result})
            except Exception:
                pass
            return resp
    except Exception as e:
        logger.error(f"Failed to start discussion: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/discussions/{session_id}/query", response_model=DiscussionResponse)
async def discussion_query(
    session_id: str,
    req: DiscussionQueryRequest,
    background_tasks: BackgroundTasks,
    copilot: AutoGenCopilot = Depends(get_autogen_copilot)
):
    if session_id != req.session_id:
        raise HTTPException(status_code=400, detail="Session ID mismatch")
    try:
        # Ensure project LLM config applied
        try:
            llm_cfg, applied = await _ensure_project_llm(req.project_id, copilot)
            if applied:
                logger.info(f"Applied project LLM config for project {req.project_id} (model={llm_cfg.get('model')})")
        except ProjectLLMConfigError as ce:
            raise HTTPException(status_code=400, detail=f"LLM config error: {ce}")
        except Exception as ce:
            raise HTTPException(status_code=500, detail=f"Failed to apply project LLM config: {ce}")
        analysis = _analyze_query(req.message, None)
        agents = req.override_agents or _select_agents(analysis)
        gathered_context = await _gather_context(req.message, None, project_id=req.project_id) if req.fetch_context else None
        if gathered_context:
            try:
                logger.info(
                    "follow_up_context project=%s vectors=%d facts=%d doc_insights=%d errors=%d",
                    req.project_id,
                    gathered_context.get("counts", {}).get("vector_snippets", 0),
                    gathered_context.get("counts", {}).get("graph_facts", 0),
                    gathered_context.get("counts", {}).get("document_insights", 0),
                    len(gathered_context.get("errors", [])),
                )
            except Exception:
                pass

        # Check if WebSocket streaming is available for this session with a short retry window
        websocket_available = copilot.has_websocket_connection(session_id)
        if not websocket_available:
            # Try to alias this session to an active same-origin WS (no Request here, so we skip origin match)
            try:
                # Best-effort: just bind to latest active if none found for exact ID
                target_sid = websocket_manager.find_latest_session_by_origin(None)
                if target_sid and target_sid != session_id:
                    websocket_manager.register_alias(session_id, target_sid)
                    websocket_available = copilot.has_websocket_connection(session_id)
            except Exception:
                pass
        if not websocket_available:
            for _ in range(3):
                await asyncio.sleep(0.1)
                if copilot.has_websocket_connection(session_id):
                    websocket_available = True
                    break
        if websocket_available:
            logger.info(f"WebSocket connection detected for discussion query session {session_id}, enabling streaming")

            # Start discussion query in background for streaming
            background_tasks.add_task(
                _run_discussion_query_with_streaming,
                copilot,
                session_id,
                req.message,
                agents,
                gathered_context,
                req.project_id,
                analysis
            )

            # Return immediate response for WebSocket streaming
            return DiscussionResponse(
                status="streaming",
                session_id=session_id,
                analysis=analysis,
                participating_agents=agents,
                result={"status": "streaming", "message": "Discussion query started with WebSocket streaming enabled"},
                gathered_context=gathered_context,
                timestamp=datetime.utcnow().isoformat(),
            )
        else:
            # No WebSocket, run synchronously
            logger.info(f"No WebSocket connection for discussion query session {session_id}, running synchronously")

            logger.info(f"Continuing discussion for session {session_id} with message: {req.message[:100]}...")
            result = await copilot.continue_conversation(session_id=session_id, follow_up_message=req.message)
            logger.info(f"Discussion continuation completed with status: {result.get('status', 'unknown')}")

            # Persist follow-up
            try:
                repo = get_conversation_repository()
                repo.save_conversation_result(session_id, req.message, None, result)
            except Exception as pe:
                logger.warning(f"Discussion follow-up persistence failed {session_id}: {pe}")

            # Augment participating agents if dynamic
            if agents:
                existing = set(result.get("participating_agents", []))
                result["participating_agents"] = list(existing.union(agents))

            logger.info(f"Returning discussion response with {len(result.get('participating_agents', []))} agents")

            resp = DiscussionResponse(
                status=result.get("status", "unknown"),
                session_id=session_id,
                analysis=analysis,
                participating_agents=result.get("participating_agents", agents),
                result=result,
                gathered_context=gathered_context,
                timestamp=datetime.utcnow().isoformat(),
            )
            # Posthoc-stream if WS connected late
            try:
                await asyncio.sleep(0.1)
                if copilot.has_websocket_connection(session_id):
                    await copilot.stream_message_to_websocket(session_id, "conversation_completed", {"result": result})
            except Exception:
                pass
            return resp
    except Exception as e:
        logger.error(f"Failed discussion query for {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/conversations/start", response_model=ConversationResponse)
async def start_conversation(
    request: ConversationRequest,
    background_tasks: BackgroundTasks,
    copilot: AutoGenCopilot = Depends(get_autogen_copilot)
):
    """
    Start a new AutoGen conversation with cloud migration experts

    This endpoint initiates a multi-agent conversation to provide comprehensive
    assistance with cloud migration questions and planning.
    """
    try:
        # Enforce project LLM config before starting
        try:
            llm_cfg, applied = await _ensure_project_llm(request.project_id, copilot)
            if applied:
                logger.info(f"Applied project LLM config for project {request.project_id} (model={llm_cfg.get('model')})")
        except ProjectLLMConfigError as ce:
            raise HTTPException(status_code=400, detail=f"LLM config error: {ce}")
        except Exception as ce:
            raise HTTPException(status_code=500, detail=f"Failed to apply project LLM config: {ce}")
        # Generate session ID if not provided
        session_id = request.session_id or str(uuid.uuid4())

        logger.info(f"Starting AutoGen conversation for session {session_id}")

        # Check if WebSocket streaming is available for this session
        websocket_available = copilot.has_websocket_connection(session_id)
        if websocket_available:
            logger.info(f"WebSocket connection detected for session {session_id}, enabling streaming")

            # Start conversation in background for streaming
            background_tasks.add_task(
                _run_conversation_with_streaming,
                copilot,
                request.message,
                session_id,
                request.context,
                request.selected_agents,
                request.project_id
            )

            # Return immediate response for WebSocket streaming
            return ConversationResponse(
                status="streaming",
                session_id=session_id,
                timestamp=datetime.utcnow().isoformat(),
                message="Conversation started with WebSocket streaming enabled"
            )
        else:
            # No WebSocket, run synchronously
            logger.info(f"No WebSocket connection for session {session_id}, running synchronously")

            # Start the conversation
            result = await copilot.start_conversation(
                user_message=request.message,
                session_id=session_id,
                context=request.context,
                selected_agents=request.selected_agents
            )

            # Persist conversation (best effort)
            try:
                repo: ConversationRepository = get_conversation_repository()
                repo.save_conversation_result(
                    session_id=session_id,
                    user_message=request.message,
                    context=request.context,
                    structured_result=result,
                )
            except Exception as pe:
                logger.warning(f"Conversation persistence failed for {session_id}: {pe}")

            # Publish conversation event to stats service in background
            background_tasks.add_task(
                _publish_conversation_event,
                session_id,
                "conversation_started",
                result
            )

            return ConversationResponse(**result)

    except Exception as e:
        logger.error(f"Error starting conversation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start conversation: {str(e)}")

@router.post("/conversations/follow-up", response_model=ConversationResponse)
async def follow_up_conversation(
    request: FollowUpRequest,
    background_tasks: BackgroundTasks,
    copilot: AutoGenCopilot = Depends(get_autogen_copilot)
):
    """
    Continue an existing conversation with a follow-up message
    """
    try:
        # Enforce project LLM config prior to continuation
        try:
            llm_cfg, applied = await _ensure_project_llm(request.project_id, copilot)
            if applied:
                logger.info(f"Applied project LLM config for project {request.project_id} (model={llm_cfg.get('model')})")
        except ProjectLLMConfigError as ce:
            raise HTTPException(status_code=400, detail=f"LLM config error: {ce}")
        except Exception as ce:
            raise HTTPException(status_code=500, detail=f"Failed to apply project LLM config: {ce}")

        logger.info(f"Continuing conversation for session {request.session_id}")

        # Check if WebSocket streaming is available for this session
        websocket_available = copilot.has_websocket_connection(request.session_id)
        if websocket_available:
            logger.info(f"WebSocket connection detected for follow-up session {request.session_id}, enabling streaming")

            # Start follow-up conversation in background for streaming
            background_tasks.add_task(
                _run_follow_up_with_streaming,
                copilot,
                request.session_id,
                request.message,
                request.project_id
            )

            # Return immediate response for WebSocket streaming
            return ConversationResponse(
                status="streaming",
                session_id=request.session_id,
                timestamp=datetime.utcnow().isoformat(),
                message="Follow-up conversation started with WebSocket streaming enabled"
            )
        else:
            # No WebSocket, run synchronously
            logger.info(f"No WebSocket connection for follow-up session {request.session_id}, running synchronously")

            result = await copilot.continue_conversation(
                session_id=request.session_id,
                follow_up_message=request.message
            )

            # Persist appended conversation
            try:
                repo: ConversationRepository = get_conversation_repository()
                repo.save_conversation_result(
                    session_id=request.session_id,
                    user_message=request.message,
                    context=None,  # context stored on first interaction
                    structured_result=result,
                )
            except Exception as pe:
                logger.warning(f"Persistence follow-up failed for {request.session_id}: {pe}")

            # Publish follow-up event to stats service
            background_tasks.add_task(
                _publish_conversation_event,
                request.session_id,
                "conversation_continued",
                result
            )

            return ConversationResponse(**result)

    except Exception as e:
        logger.error(f"Error in follow-up conversation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to continue conversation: {str(e)}")

@router.get("/conversations/{session_id}/history")
async def get_conversation_history(
    session_id: str,
    copilot: AutoGenCopilot = Depends(get_autogen_copilot)
):
    """Get the conversation history for a specific session"""
    try:
        repo = None
        try:
            repo = get_conversation_repository()
        except Exception:
            pass

        # Prefer DB if available
        if repo:
            session_meta = repo.get_session(session_id)
            if not session_meta:
                raise HTTPException(status_code=404, detail=f"No conversation found for session {session_id}")
            messages = repo.get_session_history(session_id)
            return {
                "status": "success",
                "session_id": session_id,
                "conversation_count": len(messages),
                "session": session_meta,
                "messages": messages,
            }
        else:
            history = copilot.get_conversation_history(session_id)
            if not history:
                raise HTTPException(status_code=404, detail=f"No conversation found for session {session_id}")
            return {
                "status": "success",
                "session_id": session_id,
                "conversation_count": len(history),
                "conversations": history
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get conversation history: {str(e)}")

@router.get("/conversations/history")
async def get_all_conversation_history(
    limit: int = 50,
    offset: int = 0,
    copilot: AutoGenCopilot = Depends(get_autogen_copilot)
):
    """Get all conversation history with pagination"""
    try:
        try:
            repo = get_conversation_repository()
            sessions = repo.list_sessions(limit=limit, offset=offset)
            return {
                "status": "success",
                "total_conversations": len(sessions),  # count limited view
                "limit": limit,
                "offset": offset,
                "sessions": sessions,
            }
        except Exception:
            # Fallback to in-memory
            all_history = copilot.get_conversation_history()
            total_count = len(all_history)
            paginated_history = all_history[offset:offset + limit]
            return {
                "status": "success",
                "total_conversations": total_count,
                "limit": limit,
                "offset": offset,
                "conversations": paginated_history
            }
        
    except Exception as e:
        logger.error(f"Error getting all conversation history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get conversation history: {str(e)}")

@router.post("/conversations/{session_id}/export")
async def export_conversation(
    session_id: str,
    format: str = "json",
    copilot: AutoGenCopilot = Depends(get_autogen_copilot)
):
    """Export a conversation in various formats (json, markdown, pdf)"""
    try:
        history = copilot.get_conversation_history(session_id)
        
        if not history:
            raise HTTPException(status_code=404, detail=f"No conversation found for session {session_id}")
        
        if format.lower() == "json":
            return {
                "status": "success",
                "format": "json",
                "data": history
            }
        elif format.lower() == "markdown":
            markdown_content = _convert_to_markdown(history)
            return {
                "status": "success",
                "format": "markdown",
                "content": markdown_content
            }
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting conversation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to export conversation: {str(e)}")

@router.delete("/conversations/{session_id}")
async def delete_conversation(
    session_id: str,
    copilot: AutoGenCopilot = Depends(get_autogen_copilot)
):
    """Delete a conversation session"""
    try:
        deleted_db = 0
        try:
            repo = get_conversation_repository()
            deleted_db = repo.delete_session(session_id)
        except Exception:
            pass

        # Always also prune in-memory copy
        original_count = len(copilot.conversation_history)
        copilot.conversation_history = [conv for conv in copilot.conversation_history if conv["session_id"] != session_id]
        deleted_mem = original_count - len(copilot.conversation_history)

        if not deleted_db and not deleted_mem:
            raise HTTPException(status_code=404, detail=f"No conversation found for session {session_id}")

        return {
            "status": "success",
            "message": f"Deleted session {session_id} (messages_db={deleted_db}, mem={deleted_mem})"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting conversation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete conversation: {str(e)}")

@router.post("/test-agent/{agent_name}")
async def test_agent(
    agent_name: str,
    test_message: str = "Hello, can you help me with cloud migration planning?",
    copilot: AutoGenCopilot = Depends(get_autogen_copilot)
):
    """Test a specific AutoGen agent to verify it's working properly"""
    try:
        logger.info(f"Testing agent: {agent_name}")
        result = await copilot.test_agent_response(agent_name, test_message)

        return {
            "status": result["status"],
            "agent": agent_name,
            "test_message": test_message,
            "response": result,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Agent test failed: {e}")
        return {
            "status": "error",
            "agent": agent_name,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

@router.get("/health")
async def health_check():
    """Health check endpoint for AutoGen copilot"""
    try:
        if autogen_copilot is None:
            return {
                "status": "unhealthy",
                "message": "AutoGen copilot not initialized",
                "timestamp": datetime.utcnow().isoformat()
            }

        # Check if we can access agents
        agents = autogen_copilot.get_available_agents()

        return {
            "status": "healthy",
            "message": "AutoGen copilot is operational",
            "available_agents": len(agents),
            "conversation_history_count": len(autogen_copilot.conversation_history),
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "message": f"Health check failed: {str(e)}",
            "timestamp": datetime.utcnow().isoformat()
        }

# Helper functions

async def _publish_conversation_event(session_id: str, event_type: str, result: Dict[str, Any]):
    """Publish conversation events to the stats service for analytics"""
    try:
        event_data = {
            "session_id": session_id,
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "agent_count": len(result.get("participating_agents", [])),
            "message_count": result.get("message_count", 0),
            "status": result.get("status", "unknown")
        }

        # Send to stats service (fire and forget)
        client = await get_service_client()
        await client.post(
            "stats",
            "/api/stats/events/autogen-conversation",
            json=event_data
        )

    except Exception as e:
        logger.warning(f"Failed to publish conversation event: {e}")

async def _run_conversation_with_streaming(
    copilot: AutoGenCopilot,
    message: str,
    session_id: str,
    context: Optional[Dict[str, Any]],
    selected_agents: Optional[List[str]],
    project_id: str
):
    """Run conversation with WebSocket streaming in background"""
    try:
        logger.info(f"Running background conversation for session {session_id}")

        # Ensure project LLM config is applied for background task
        try:
            await _ensure_project_llm(project_id, copilot)
        except Exception as e:
            logger.error(f"Failed to apply project LLM config in background: {e}")
            return

        # Run the conversation (this will handle WebSocket streaming internally)
        result = await copilot.start_conversation(
            user_message=message,
            session_id=session_id,
            context=context,
            selected_agents=selected_agents
        )

        # Persist conversation result
        try:
            repo: ConversationRepository = get_conversation_repository()
            repo.save_conversation_result(
                session_id=session_id,
                user_message=message,
                context=context,
                structured_result=result,
            )
            logger.info(f"Background conversation persisted for session {session_id}")
        except Exception as pe:
            logger.warning(f"Background conversation persistence failed for {session_id}: {pe}")

        # Publish completion event
        await _publish_conversation_event(session_id, "conversation_completed", result)

        logger.info(f"Background conversation completed for session {session_id}")

    except Exception as e:
        logger.error(f"Error in background conversation for session {session_id}: {e}")

        # Publish error event
        error_result = {"status": "error", "error": str(e)}
        await _publish_conversation_event(session_id, "conversation_error", error_result)

async def _run_follow_up_with_streaming(
    copilot: AutoGenCopilot,
    session_id: str,
    message: str,
    project_id: str
):
    """Run follow-up conversation with WebSocket streaming in background"""
    try:
        logger.info(f"Running background follow-up conversation for session {session_id}")

        # Ensure project LLM config is applied for background task
        try:
            await _ensure_project_llm(project_id, copilot)
        except Exception as e:
            logger.error(f"Failed to apply project LLM config in background follow-up: {e}")
            return

        # Run the follow-up conversation (this will handle WebSocket streaming internally)
        result = await copilot.continue_conversation(
            session_id=session_id,
            follow_up_message=message
        )

        # Persist follow-up conversation result
        try:
            repo: ConversationRepository = get_conversation_repository()
            repo.save_conversation_result(
                session_id=session_id,
                user_message=message,
                context=None,  # context stored on first interaction
                structured_result=result,
            )
            logger.info(f"Background follow-up conversation persisted for session {session_id}")
        except Exception as pe:
            logger.warning(f"Background follow-up persistence failed for {session_id}: {pe}")

        # Publish completion event
        await _publish_conversation_event(session_id, "conversation_follow_up_completed", result)

        logger.info(f"Background follow-up conversation completed for session {session_id}")

    except Exception as e:
        logger.error(f"Error in background follow-up conversation for session {session_id}: {e}")

        # Publish error event
        error_result = {"status": "error", "error": str(e)}
        await _publish_conversation_event(session_id, "conversation_follow_up_error", error_result)

async def _run_discussion_with_streaming(
    copilot: AutoGenCopilot,
    message: str,
    session_id: str,
    gathered_context: Dict[str, Any],
    selected_agents: List[str],
    project_id: str,
    analysis: Dict[str, Any]
):
    """Run discussion with WebSocket streaming in background"""
    try:
        logger.info(f"Running background discussion for session {session_id}")

        # Ensure project LLM config is applied for background task
        try:
            await _ensure_project_llm(project_id, copilot)
        except Exception as e:
            logger.error(f"Failed to apply project LLM config in background discussion: {e}")
            return

        # Run the discussion (this will handle WebSocket streaming internally)
        result = await copilot.start_conversation(
            user_message=message,
            session_id=session_id,
            context=gathered_context,
            selected_agents=selected_agents,
        )

        # Persist discussion result
        try:
            repo = get_conversation_repository()
            repo.save_conversation_result(session_id, message, gathered_context, result)
            logger.info(f"Background discussion persisted for session {session_id}")
        except Exception as pe:
            logger.warning(f"Background discussion persistence failed for {session_id}: {pe}")

        # Publish completion event
        await _publish_conversation_event(session_id, "discussion_completed", result)

        logger.info(f"Background discussion completed for session {session_id}")

    except Exception as e:
        logger.error(f"Error in background discussion for session {session_id}: {e}")

        # Publish error event
        error_result = {"status": "error", "error": str(e)}
        await _publish_conversation_event(session_id, "discussion_error", error_result)

async def _run_discussion_query_with_streaming(
    copilot: AutoGenCopilot,
    session_id: str,
    message: str,
    agents: List[str],
    gathered_context: Optional[Dict[str, Any]],
    project_id: str,
    analysis: Dict[str, Any]
):
    """Run discussion query with WebSocket streaming in background"""
    try:
        logger.info(f"Running background discussion query for session {session_id}")

        # Ensure project LLM config is applied for background task
        try:
            await _ensure_project_llm(project_id, copilot)
        except Exception as e:
            logger.error(f"Failed to apply project LLM config in background discussion query: {e}")
            return

        # Run the discussion query (this will handle WebSocket streaming internally)
        result = await copilot.continue_conversation(session_id=session_id, follow_up_message=message)

        # Augment participating agents if dynamic
        if agents:
            existing = set(result.get("participating_agents", []))
            result["participating_agents"] = list(existing.union(agents))

        # Persist discussion query result
        try:
            repo = get_conversation_repository()
            repo.save_conversation_result(session_id, message, gathered_context, result)
            logger.info(f"Background discussion query persisted for session {session_id}")
        except Exception as pe:
            logger.warning(f"Background discussion query persistence failed for {session_id}: {pe}")

        # Publish completion event
        await _publish_conversation_event(session_id, "discussion_query_completed", result)

        logger.info(f"Background discussion query completed for session {session_id}")

    except Exception as e:
        logger.error(f"Error in background discussion query for session {session_id}: {e}")

        # Publish error event
        error_result = {"status": "error", "error": str(e)}
        await _publish_conversation_event(session_id, "discussion_query_error", error_result)

def _convert_to_markdown(conversation_history: List[Dict[str, Any]]) -> str:
    """Convert conversation history to markdown format"""
    
    markdown_lines = []
    
    for conv in conversation_history:
        markdown_lines.append(f"# Conversation Session: {conv['session_id']}")
        markdown_lines.append(f"**Timestamp:** {conv['timestamp']}")
        markdown_lines.append(f"**User Message:** {conv['user_message']}")
        markdown_lines.append("")
        
        if conv.get("context"):
            markdown_lines.append("## Project Context")
            for key, value in conv["context"].items():
                markdown_lines.append(f"- **{key.replace('_', ' ').title()}:** {value}")
            markdown_lines.append("")
        
        result = conv.get("result", {})
        
        if result.get("participating_agents"):
            markdown_lines.append("## Participating Agents")
            for agent in result["participating_agents"]:
                markdown_lines.append(f"- {agent}")
            markdown_lines.append("")
        
        if result.get("recommendations"):
            markdown_lines.append("## Recommendations")
            for i, rec in enumerate(result["recommendations"], 1):
                markdown_lines.append(f"{i}. **{rec.get('agent', 'Unknown')}:** {rec.get('recommendation', '')}")
            markdown_lines.append("")
        
        if result.get("action_items"):
            markdown_lines.append("## Action Items")
            for i, action in enumerate(result["action_items"], 1):
                markdown_lines.append(f"{i}. **{action.get('agent', 'Unknown')}:** {action.get('action', '')}")
            markdown_lines.append("")
        
        if result.get("summary"):
            summary = result["summary"]
            markdown_lines.append("## Summary")
            markdown_lines.append(f"**Topics Discussed:** {', '.join(summary.get('key_topics_discussed', []))}")
            markdown_lines.append(f"**Implementation Complexity:** {summary.get('implementation_complexity', 'Unknown')}")
            if summary.get("estimated_timeline"):
                markdown_lines.append(f"**Estimated Timeline:** {summary['estimated_timeline']}")
            markdown_lines.append("")
        
        markdown_lines.append("---")
        markdown_lines.append("")
    
    return "\n".join(markdown_lines)
