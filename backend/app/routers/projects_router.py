from fastapi import APIRouter, HTTPException, Request, Body, Query
from typing import List, Optional
from app.core.project_service import get_project_service, ProjectCreate
import logging
import requests
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.crew_logger import get_db
from app.models.crew_interaction import CrewInteractionModel

logger = logging.getLogger("platform.projects_router")

router = APIRouter(prefix="/api/projects", tags=["projects"])

@router.get("", include_in_schema=False)
async def list_projects_no_slash():
    return await list_projects()

@router.get("/", summary="List all projects")
async def list_projects():
    try:
        project_service = get_project_service()
        projects = project_service.list_projects()
        return projects
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list projects: {str(e)}")

@router.post("/", summary="Create a new project")
async def create_project(request: dict):
    try:
        project_service = get_project_service()
        project = project_service.create_project(ProjectCreate(**request))
        return project
    except Exception as e:
        logger.error(f"Project creation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create project: {str(e)}")

@router.delete("/{project_id}", summary="Delete a project")
async def delete_project(project_id: str):
    try:
        project_service = get_project_service()
        result = project_service.delete_project(project_id)
        return result
    except Exception as e:
        logger.error(f"Error deleting project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete project: {str(e)}")


from app.core.llm_config import get_llm_configurations_from_db

@router.get("/stats", summary="Get project statistics")
async def get_projects_stats():
    try:
        project_service = get_project_service()
        projects = project_service.list_projects()
        total_projects = len(projects)
        status_counts = {}
        for project in projects:
            status = project.status
            status_counts[status] = status_counts.get(status, 0) + 1
        return {
            "total_projects": total_projects,
            "status_breakdown": status_counts,
            "active_projects": status_counts.get("running", 0),
            "completed_projects": status_counts.get("completed", 0),
            "pending_projects": status_counts.get("initiated", 0)
        }
    except Exception as e:
        logger.error(f"Error getting project stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting project stats: {str(e)}")

@router.get("/{project_id}", summary="Get a project by ID")
async def get_project(project_id: str):
    try:
        project_service = get_project_service()
        project = project_service.get_project(project_id)
        if hasattr(project, 'model_dump'):
            project_dict = project.model_dump()
        elif hasattr(project, 'dict'):
            project_dict = project.dict()
        elif hasattr(project, '__dict__'):
            project_dict = project.__dict__
        else:
            project_dict = dict(project)
        if project_dict.get('llm_api_key_id'):
            try:
                llm_configs = get_llm_configurations_from_db()
                llm_config = llm_configs.get(project_dict['llm_api_key_id'])
                if llm_config:
                    project_dict['llm_provider'] = llm_config.get('provider', 'unknown')
                    project_dict['llm_model'] = llm_config.get('model', 'unknown')
                    project_dict['llm_temperature'] = str(llm_config.get('temperature', 0.7))
                    project_dict['llm_max_tokens'] = str(llm_config.get('max_tokens', 4000))
                    logger.info(f"Expanded LLM config for project {project_id}: {llm_config.get('provider')}/{llm_config.get('model')}")
                else:
                    logger.warning(f"LLM config {project_dict['llm_api_key_id']} not found for project {project_id}")
                    project_dict['llm_provider'] = 'deleted'
                    project_dict['llm_model'] = 'deleted'
            except Exception as llm_error:
                logger.error(f"Error expanding LLM config for project {project_id}: {llm_error}")
                project_dict['llm_provider'] = 'error'
                project_dict['llm_model'] = 'error'
        logger.info(f"Retrieved project: {project_id} with LLM config: provider={project_dict.get('llm_provider')}, model={project_dict.get('llm_model')}")
        return project_dict
    except Exception as e:
        logger.error(f"Error getting project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting project: {str(e)}")

@router.put("/{project_id}", summary="Update a project")
async def update_project(project_id: str, project_data: dict = Body(...)):
    try:
        project_service = get_project_service()
        response = requests.put(
            f"{project_service.base_url}/projects/{project_id}",
            json=project_data,
            headers=project_service._get_auth_headers()
        )
        response.raise_for_status()
        result = response.json()
        return result
    except Exception as e:
        logger.error(f"Error updating project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating project: {str(e)}")

@router.get("/{project_id}/crew-interactions", summary="List historic crew interactions with filters")
async def get_crew_interactions(
    project_id: str,
    task_id: Optional[str] = Query(None),
    conversation_id: Optional[str] = Query(None),
    agent_name: Optional[str] = Query(None),
    tool_name: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    interaction_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None)
):
    """Return historic interactions stored in DB."""
    db: Session = None
    try:
        db = get_db()
        query = db.query(CrewInteractionModel).filter(CrewInteractionModel.project_id == project_id)
        if task_id:
            query = query.filter(CrewInteractionModel.task_id == task_id)
        if conversation_id:
            query = query.filter(CrewInteractionModel.conversation_id == conversation_id)
        if agent_name:
            query = query.filter(CrewInteractionModel.agent_name == agent_name)
        if tool_name:
            query = query.filter(CrewInteractionModel.tool_name == tool_name)
        if status:
            query = query.filter(CrewInteractionModel.status == status)
        if interaction_type:
            query = query.filter(CrewInteractionModel.type == interaction_type)
        if search:
            like = f"%{search}%"
            from sqlalchemy import or_
            query = query.filter(or_(CrewInteractionModel.agent_name.ilike(like), CrewInteractionModel.tool_name.ilike(like), CrewInteractionModel.function_name.ilike(like)))
        total = query.count()
        rows = query.order_by(CrewInteractionModel.timestamp.desc()).offset(offset).limit(limit).all()
        interactions = []
        for r in rows:
            interactions.append({
                "id": str(r.id),
                "project_id": r.project_id,
                "task_id": r.task_id,
                "conversation_id": r.conversation_id,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                "type": r.type,
                "parent_id": str(r.parent_id) if r.parent_id else None,
                "depth": r.depth,
                "sequence": r.sequence,
                "crew_name": r.crew_name,
                "crew_description": r.crew_description,
                "crew_members": r.crew_members,
                "crew_goal": r.crew_goal,
                "agent_name": r.agent_name,
                "agent_role": r.agent_role,
                "agent_goal": r.agent_goal,
                "agent_backstory": r.agent_backstory,
                "agent_id": r.agent_id,
                "tool_name": r.tool_name,
                "tool_description": r.tool_description,
                "function_name": r.function_name,
                "request_data": r.request_data,
                "response_data": r.response_data,
                "reasoning_step": r.reasoning_step,
                "request_text": r.request_text,
                "response_text": r.response_text,
                "message_type": r.message_type,
                "token_usage": r.token_usage,
                "performance_metrics": r.performance_metrics,
                "status": r.status,
                "start_time": r.start_time.isoformat() if r.start_time else None,
                "end_time": r.end_time.isoformat() if r.end_time else None,
                "duration_ms": r.duration_ms,
                "error_message": r.error_message,
                "retry_count": r.retry_count,
                "interaction_metadata": r.interaction_metadata,
            })
        return {"total": total, "count": len(interactions), "interactions": interactions}
    except Exception as e:
        logger.error(f"Error fetching crew interactions for {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch interactions")
    finally:
        if db:
            db.close()

@router.get("/{project_id}/crew-interactions/stats", summary="Crew interactions statistics")
async def crew_interactions_stats(project_id: str, task_id: Optional[str] = None):
    db: Session = None
    try:
        db = get_db()
        base = db.query(CrewInteractionModel).filter(CrewInteractionModel.project_id == project_id)
        if task_id:
            base = base.filter(CrewInteractionModel.task_id == task_id)
        total = base.count()
        # Type counts
        type_rows = db.query(CrewInteractionModel.type, func.count(CrewInteractionModel.id)).filter(CrewInteractionModel.project_id == project_id)
        if task_id:
            type_rows = type_rows.filter(CrewInteractionModel.task_id == task_id)
        type_rows = type_rows.group_by(CrewInteractionModel.type).all()
        type_counts = {t: c for t, c in type_rows}
        # Status counts
        status_rows = db.query(CrewInteractionModel.status, func.count(CrewInteractionModel.id)).filter(CrewInteractionModel.project_id == project_id)
        if task_id:
            status_rows = status_rows.filter(CrewInteractionModel.task_id == task_id)
        status_rows = status_rows.group_by(CrewInteractionModel.status).all()
        status_counts = {s: c for s, c in status_rows}
        # Unique agents/tools
        unique_agents = db.query(func.count(func.distinct(CrewInteractionModel.agent_name))).filter(CrewInteractionModel.project_id == project_id, CrewInteractionModel.agent_name.isnot(None)).scalar() or 0
        unique_tools = db.query(func.count(func.distinct(CrewInteractionModel.tool_name))).filter(CrewInteractionModel.project_id == project_id, CrewInteractionModel.tool_name.isnot(None)).scalar() or 0
        # Token totals
        import json as _json
        total_tokens = 0
        total_cost = 0.0
        token_rows = base.filter(CrewInteractionModel.token_usage.isnot(None)).all()
        for r in token_rows:
            try:
                usage = r.token_usage
                if usage:
                    total_tokens += int(usage.get('total_tokens', 0))
                    total_cost += float(usage.get('estimated_cost', 0.0))
            except Exception:
                pass
        return {
            "project_id": project_id,
            "total_interactions": total,
            "type_counts": type_counts,
            "status_counts": status_counts,
            "unique_agents": unique_agents,
            "unique_tools": unique_tools,
            "total_tokens": total_tokens,
            "total_cost": total_cost,
        }
    except Exception as e:
        logger.error(f"Error computing crew interaction stats for {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to compute stats")
    finally:
        if db:
            db.close()

# Note: template-usage and generation-history endpoints will be restored when implementation source confirmed.
