"""
AutoGen Co-pilot REST API Routes
Provides endpoints for conversational AI assistance using Microsoft AutoGen
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, List, Any, Optional, Tuple
import logging
import uuid
from datetime import datetime
from pydantic import BaseModel, Field
import httpx

from ..core.autogen_copilot import AutoGenCopilot
from ..repository.conversations import get_conversation_repository, ConversationRepository
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

async def _gather_context(message: str, context: Optional[Dict[str, Any]], correlation_id: Optional[str] = None) -> Dict[str, Any]:
    """Placeholder multi-source context gathering – integrate real services later."""
    # In production: parallel calls to vector, graph, storage services.
    return {
        "vector_snippets": [],
        "graph_entities": [],
        "documents": [],
        "provided_context": context or {},
        "note": "Context gathering placeholder – integrate vector/graph/storage services",
    }

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
        # Attempt primary endpoint
        resp = await client.get("project", f"/api/projects/{project_id}/llm-config")
        if resp.status_code == 404:
            # Fallback older style endpoint if present
            resp = await client.get("project", f"/api/projects/{project_id}")
        if resp.status_code >= 400:
            raise ProjectLLMConfigError(f"Project service returned {resp.status_code}: {resp.text}")
        data = resp.json()
        # Try to standardize structure
        llm_cfg = data.get("default_llm") or data.get("llm") or data.get("llm_config")
        if not llm_cfg:
            raise ProjectLLMConfigError("No default_llm configuration found for project")
        missing = [k for k in ("model", "api_key") if k not in llm_cfg or not llm_cfg.get(k)]
        if missing:
            raise ProjectLLMConfigError(f"Project LLM config missing fields: {', '.join(missing)}")
        # provider optional; default to openai for now
        if "provider" not in llm_cfg:
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
            copilot.apply_project_llm_config(llm_cfg["api_key"], llm_cfg["model"], provider=llm_cfg.get("provider", "openai"))
            copilot._current_model = llm_cfg["model"]  # track
            copilot._current_key_hash = key_hash
            applied = True
    except AttributeError:
        # Older copilot version or structure changed; just apply
        copilot.apply_project_llm_config(llm_cfg["api_key"], llm_cfg["model"], provider=llm_cfg.get("provider", "openai"))
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

@router.post("/discussions/start", response_model=DiscussionResponse)
async def start_discussion(
    req: DiscussionStartRequest,
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
        session_id = req.session_id or str(uuid.uuid4())
        analysis = _analyze_query(req.message, req.context)
        selected = req.selected_agents or _select_agents(analysis)
        gathered_context = await _gather_context(req.message, req.context)
        result = await copilot.start_conversation(
            user_message=req.message,
            session_id=session_id,
            context=gathered_context.get("provided_context"),
            selected_agents=selected,
        )
        # Persist via existing path (already done inside start_conversation route logic – replicate minimal)
        try:
            repo = get_conversation_repository()
            repo.save_conversation_result(session_id, req.message, req.context, result)
        except Exception as pe:
            logger.warning(f"Discussion persistence failed {session_id}: {pe}")
        return DiscussionResponse(
            status=result.get("status", "unknown"),
            session_id=session_id,
            analysis=analysis,
            participating_agents=result.get("participating_agents", selected),
            result=result,
            gathered_context=gathered_context,
            timestamp=datetime.utcnow().isoformat(),
        )
    except Exception as e:
        logger.error(f"Failed to start discussion: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/discussions/{session_id}/query", response_model=DiscussionResponse)
async def discussion_query(
    session_id: str,
    req: DiscussionQueryRequest,
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
        gathered_context = await _gather_context(req.message, None) if req.fetch_context else None
        result = await copilot.continue_conversation(session_id=session_id, follow_up_message=req.message)
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
        return DiscussionResponse(
            status=result.get("status", "unknown"),
            session_id=session_id,
            analysis=analysis,
            participating_agents=result.get("participating_agents", agents),
            result=result,
            gathered_context=gathered_context,
            timestamp=datetime.utcnow().isoformat(),
        )
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
