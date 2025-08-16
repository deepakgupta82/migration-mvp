#!/usr/bin/env python3
"""
AI Agent Router - API endpoints for AI agent orchestration
Handles single agents and multi-agent crew workflows
"""

from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
import logging

from ..core.agent_processor import AIAgentProcessor

logger = logging.getLogger("ai-agent-service")
router = APIRouter()

# Initialize processor
agent_processor = AIAgentProcessor()

# Pydantic models
class AgentTaskRequest(BaseModel):
    input_data: Dict[str, Any] = Field(..., description="Input data for the agent")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Additional parameters")
    priority: Optional[str] = Field("normal", description="Task priority (low, normal, high)")

class CrewWorkflowRequest(BaseModel):
    input_data: Dict[str, Any] = Field(..., description="Input data for the crew workflow")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Workflow parameters")
    priority: Optional[str] = Field("normal", description="Workflow priority")

class HealthResponse(BaseModel):
    service: str
    status: str
    dependencies: Dict[str, bool]
    active_jobs: int
    port: int
    version: str

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    try:
        dependencies = await agent_processor.verify_dependencies()
        active_jobs = await agent_processor.get_active_jobs()
        
        return HealthResponse(
            service="ai-agent-orchestration",
            status="healthy" if all(dependencies.values()) else "degraded",
            dependencies=dependencies,
            active_jobs=active_jobs.get("total_active", 0),
            port=8008,
            version="1.0.0"
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            service="ai-agent-orchestration",
            status="unhealthy",
            dependencies={},
            active_jobs=0,
            port=8008,
            version="1.0.0"
        )

@router.get("/list")
async def get_available_agents():
    """Get list of available AI agents"""
    try:
        agents = await agent_processor.get_available_agents()
        return {
            "agents": agents,
            "total_count": len(agents)
        }
    except Exception as e:
        logger.error(f"Error getting agents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/crews")
async def get_available_crews():
    """Get list of available AI crews"""
    try:
        crews = await agent_processor.get_available_crews()
        return {
            "crews": crews,
            "total_count": len(crews)
        }
    except Exception as e:
        logger.error(f"Error getting crews: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{agent_id}/tasks")
async def start_agent_task(agent_id: str, request: AgentTaskRequest):
    """Start a single agent task"""
    try:
        task_config = {
            "input_data": request.input_data,
            "parameters": request.parameters or {},
            "priority": request.priority
        }
        
        result = await agent_processor.start_agent_task(agent_id, task_config)
        
        if result.get("success"):
            return {
                "success": True,
                "job_id": result.get("job_id"),
                "agent_id": agent_id,
                "status": result.get("status"),
                "message": result.get("message"),
                "status_endpoint": f"/api/agents/tasks/{result.get('job_id')}/status"
            }
        else:
            raise HTTPException(status_code=400, detail=result.get("error"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting agent task: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/crews/{crew_id}/workflows")
async def start_crew_workflow(crew_id: str, request: CrewWorkflowRequest):
    """Start a multi-agent crew workflow"""
    try:
        workflow_config = {
            "input_data": request.input_data,
            "parameters": request.parameters or {},
            "priority": request.priority
        }
        
        result = await agent_processor.start_crew_workflow(crew_id, workflow_config)
        
        if result.get("success"):
            return {
                "success": True,
                "job_id": result.get("job_id"),
                "crew_id": crew_id,
                "status": result.get("status"),
                "estimated_time_minutes": result.get("estimated_time_minutes"),
                "message": result.get("message"),
                "status_endpoint": f"/api/agents/workflows/{result.get('job_id')}/status"
            }
        else:
            raise HTTPException(status_code=400, detail=result.get("error"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting crew workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tasks/{job_id}/status")
async def get_agent_task_status(job_id: str):
    """Get status of a running agent task"""
    try:
        status = await agent_processor.get_task_status(job_id)
        
        if status:
            return status
        else:
            raise HTTPException(status_code=404, detail="Task not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting task status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/workflows/{job_id}/status")
async def get_crew_workflow_status(job_id: str):
    """Get status of a running crew workflow"""
    try:
        status = await agent_processor.get_workflow_status(job_id)
        
        if status:
            return status
        else:
            raise HTTPException(status_code=404, detail="Workflow not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting workflow status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/jobs/active")
async def get_active_jobs():
    """Get all active AI jobs (tasks and workflows)"""
    try:
        active_jobs = await agent_processor.get_active_jobs()
        return active_jobs
    except Exception as e:
        logger.error(f"Error getting active jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Debug endpoints
@router.get("/debug/cache-status")
async def get_cache_status():
    """Debug: Get Redis cache status"""
    try:
        cache_info = {
            "redis_connected": agent_processor.redis_client.ping() if agent_processor.redis_client else False,
            "cache_keys": [],
            "memory_usage": "unknown"
        }
        
        if agent_processor.redis_client:
            # Get agent-related cache keys
            task_keys = agent_processor.redis_client.keys("agent_task:*")
            workflow_keys = agent_processor.redis_client.keys("crew_workflow:*")
            cache_info["cache_keys"] = {
                "agent_tasks": len(task_keys),
                "crew_workflows": len(workflow_keys),
                "total": len(task_keys) + len(workflow_keys)
            }
            cache_info["memory_usage"] = agent_processor.redis_client.info("memory").get("used_memory_human", "unknown")
            
        return cache_info
    except Exception as e:
        logger.error(f"Error getting cache status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/debug/system-status")
async def get_system_status():
    """Debug: Get AI agent system status"""
    try:
        dependencies = await agent_processor.verify_dependencies()
        active_jobs = await agent_processor.get_active_jobs()
        
        return {
            "dependencies": dependencies,
            "active_jobs_count": active_jobs.get("total_active", 0),
            "active_crews": len(agent_processor.active_crews),
            "system_healthy": all(dependencies.values()),
            "timestamp": "2025-08-16T00:00:00Z"
        }
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
