"""
AutoGen Co-pilot REST API Routes
Provides endpoints for conversational AI assistance using Microsoft AutoGen
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, List, Any, Optional
import logging
import uuid
from datetime import datetime
from pydantic import BaseModel, Field

from ..core.autogen_copilot import AutoGenCopilot

logger = logging.getLogger("autogen-api")

router = APIRouter()

# Request/Response Models
class ConversationRequest(BaseModel):
    """Request model for starting a new conversation"""
    message: str = Field(..., description="User's question or request")
    context: Optional[Dict[str, Any]] = Field(None, description="Project context information")
    selected_agents: Optional[List[str]] = Field(None, description="Specific agents to include in conversation")
    session_id: Optional[str] = Field(None, description="Optional session ID (auto-generated if not provided)")

class FollowUpRequest(BaseModel):
    """Request model for follow-up messages"""
    message: str = Field(..., description="Follow-up question or request")
    session_id: str = Field(..., description="Session ID from previous conversation")

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
        logger.info(f"Continuing conversation for session {request.session_id}")
        
        result = await copilot.continue_conversation(
            session_id=request.session_id,
            follow_up_message=request.message
        )
        
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
        all_history = copilot.get_conversation_history()
        
        # Apply pagination
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
        # Remove from conversation history
        original_count = len(copilot.conversation_history)
        copilot.conversation_history = [
            conv for conv in copilot.conversation_history 
            if conv["session_id"] != session_id
        ]
        
        deleted_count = original_count - len(copilot.conversation_history)
        
        if deleted_count == 0:
            raise HTTPException(status_code=404, detail=f"No conversation found for session {session_id}")
        
        return {
            "status": "success",
            "message": f"Deleted {deleted_count} conversation(s) for session {session_id}"
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
        import httpx
        
        event_data = {
            "session_id": session_id,
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "agent_count": len(result.get("participating_agents", [])),
            "message_count": result.get("message_count", 0),
            "status": result.get("status", "unknown")
        }
        
        # Send to stats service (fire and forget)
        async with httpx.AsyncClient() as client:
            await client.post(
                "http://localhost:8004/api/stats/events/autogen-conversation",
                json=event_data,
                timeout=5.0
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
