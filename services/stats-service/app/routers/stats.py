"""
Statistics API Router
Provides REST endpoints for retrieving platform and project statistics
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

logger = logging.getLogger("stats-router")

router = APIRouter()

# Dependency to get stats processor
async def get_stats_processor():
    from app.main import get_stats_processor
    processor = get_stats_processor()
    if not processor:
        raise HTTPException(status_code=503, detail="Stats service not available")
    return processor

@router.get("/platform", summary="Get platform-wide statistics")
async def get_platform_stats(
    stats_processor = Depends(get_stats_processor)
) -> Dict[str, Any]:
    """
    Get comprehensive platform statistics including:
    - Total projects, documents, embeddings
    - Service health status
    - Performance metrics
    """
    try:
        stats = await stats_processor.get_platform_stats()
        return {
            "status": "success",
            "data": stats,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get platform stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve platform statistics: {str(e)}")

@router.get("/projects", summary="Get statistics for all projects")
async def get_all_projects_stats(
    stats_processor = Depends(get_stats_processor)
) -> Dict[str, Any]:
    """
    Get statistics for all projects in the platform
    """
    try:
        project_stats = await stats_processor.get_all_project_stats()
        return {
            "status": "success",
            "data": {
                "projects": project_stats,
                "total_count": len(project_stats)
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get all project stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve project statistics: {str(e)}")

@router.get("/projects/{project_id}", summary="Get statistics for a specific project")
async def get_project_stats(
    project_id: str,
    stats_processor = Depends(get_stats_processor)
) -> Dict[str, Any]:
    """
    Get detailed statistics for a specific project including:
    - Document count and processing status
    - Embeddings and graph data
    - Assessment progress
    """
    try:
        stats = await stats_processor.get_project_stats(project_id)
        
        if "error" in stats:
            raise HTTPException(status_code=404, detail=f"Project {project_id} not found or stats unavailable")
            
        return {
            "status": "success",
            "data": stats,
            "timestamp": datetime.utcnow().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get project stats for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve statistics for project {project_id}: {str(e)}")

# =================================================================================
# Manual update endpoints (for testing and manual triggers)
# =================================================================================

@router.post("/events/autogen-conversation", summary="Track AutoGen conversation event")
async def track_autogen_conversation(
    event_data: Dict[str, Any],
    stats_processor = Depends(get_stats_processor)
) -> Dict[str, Any]:
    """
    Track AutoGen conversation events for analytics
    Expected payload: {
        "session_id": "...",
        "project_id": "...",
        "message_count": 5,
        "agent_count": 3,
        "duration_seconds": 12.5
    }
    """
    try:
        # Log the event (can be enhanced to store in DB for analytics)
        logger.info(f"AutoGen conversation event: {event_data}")
        
        # Optionally update project stats
        project_id = event_data.get("project_id")
        if project_id:
            # Could track conversation metrics here
            pass
            
        return {
            "status": "success",
            "message": "AutoGen conversation event tracked",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to track AutoGen conversation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to track event: {str(e)}")

@router.post("/projects/{project_id}/events/document-processed", summary="Trigger document processed event")
async def trigger_document_processed(
    project_id: str,
    document_info: Dict[str, Any],
    stats_processor = Depends(get_stats_processor)
) -> Dict[str, Any]:
    """
    Manually trigger a document processed event for testing
    """
    try:
        await stats_processor.handle_document_processed(project_id, document_info)
        return {
            "status": "success",
            "message": f"Document processed event triggered for project {project_id}",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to trigger document processed event: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger event: {str(e)}")

@router.post("/projects/{project_id}/events/document-uploaded", summary="Trigger document uploaded event")
async def trigger_document_uploaded(
    project_id: str,
    document_info: Dict[str, Any],
    stats_processor = Depends(get_stats_processor)
) -> Dict[str, Any]:
    """
    Manually trigger a document uploaded event (increments files count)
    """
    try:
        await stats_processor.handle_document_uploaded(project_id, document_info)
        return {
            "status": "success",
            "message": f"Document uploaded event triggered for project {project_id}",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to trigger document uploaded event: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger event: {str(e)}")

@router.post("/projects/{project_id}/events/embeddings-updated", summary="Trigger embeddings updated event")
async def trigger_embeddings_updated(
    project_id: str,
    embeddings_info: Dict[str, Any],
    stats_processor = Depends(get_stats_processor)
) -> Dict[str, Any]:
    """
    Manually trigger an embeddings updated event for testing
    """
    try:
        await stats_processor.handle_embeddings_updated(project_id, embeddings_info)
        return {
            "status": "success",
            "message": f"Embeddings updated event triggered for project {project_id}",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to trigger embeddings updated event: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger event: {str(e)}")

@router.post("/projects/{project_id}/events/graph-updated", summary="Trigger graph updated event")
async def trigger_graph_updated(
    project_id: str,
    graph_info: Dict[str, Any],
    stats_processor = Depends(get_stats_processor)
) -> Dict[str, Any]:
    """
    Manually trigger a graph updated event for testing
    """
    try:
        await stats_processor.handle_graph_updated(project_id, graph_info)
        return {
            "status": "success",
            "message": f"Graph updated event triggered for project {project_id}",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to trigger graph updated event: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger event: {str(e)}")

@router.post("/projects/{project_id}/events/assessment-status", summary="Update assessment status")
async def update_assessment_status(
    project_id: str,
    status_data: Dict[str, str],
    stats_processor = Depends(get_stats_processor)
) -> Dict[str, Any]:
    """
    Update assessment status for a project
    Expected payload: {"status": "running|completed|failed|not_started"}
    """
    try:
        status = status_data.get("status")
        if not status:
            raise HTTPException(status_code=400, detail="Status is required")
            
        await stats_processor.handle_assessment_status_changed(project_id, status)
        return {
            "status": "success",
            "message": f"Assessment status updated for project {project_id}: {status}",
            "timestamp": datetime.utcnow().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update assessment status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update assessment status: {str(e)}")

@router.post("/services/{service_name}/health", summary="Update service health status")
async def update_service_health(
    service_name: str,
    health_data: Dict[str, str],
    stats_processor = Depends(get_stats_processor)
) -> Dict[str, Any]:
    """
    Update health status for a service
    Expected payload: {"status": "healthy|unhealthy|degraded|unknown"}
    """
    try:
        status = health_data.get("status", "unknown")
        await stats_processor.update_service_health(service_name, status)
        return {
            "status": "success",
            "message": f"Service health updated: {service_name} = {status}",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to update service health: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update service health: {str(e)}")

# =================================================================================
# Admin endpoints
# =================================================================================

@router.post("/admin/reset", summary="Reset all statistics (admin only)")
async def reset_all_stats(
    stats_processor = Depends(get_stats_processor)
) -> Dict[str, Any]:
    """
    Reset all platform and project statistics (use with caution)
    """
    try:
        # Re-initialize platform stats
        await stats_processor._initialize_platform_stats()
        
        # Sync projects from project service
        await stats_processor._sync_project_list()
        
        return {
            "status": "success",
            "message": "All statistics have been reset and re-synchronized",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to reset stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reset statistics: {str(e)}")

@router.get("/admin/cache-info", summary="Get cache information")
async def get_cache_info(
    stats_processor = Depends(get_stats_processor)
) -> Dict[str, Any]:
    """
    Get information about the Redis cache status
    """
    try:
        # Get Redis info
        redis_info = await stats_processor.redis.info()
        
        # Get all cached project IDs
        project_ids = await stats_processor._get_all_project_ids()
        
        return {
            "status": "success",
            "data": {
                "redis_connected": True,
                "redis_memory_used": redis_info.get("used_memory_human", "unknown"),
                "cached_projects_count": len(project_ids),
                "cached_project_ids": project_ids
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get cache info: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get cache information: {str(e)}")
