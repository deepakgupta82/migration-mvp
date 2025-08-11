from fastapi import APIRouter, HTTPException, Request, Body
from typing import List
from app.core.project_service import get_project_service, ProjectCreate
import logging
import requests

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

@router.get("/{project_id}/crew-interactions/stats", summary="Get crew interaction statistics for a project")
async def get_crew_interaction_stats(project_id: str):
    """Return crew interaction stats (placeholder implementation).
    Later this should pull from a persistence layer or analytics store.
    """
    try:
        # Placeholder synthetic data
        stats = {
            "project_id": project_id,
            "total_interactions": 0,
            "unique_crews": 0,
            "last_interaction": None,
            "by_crew": []
        }
        return stats
    except Exception as e:
        logger.error(f"Error getting crew interaction stats for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get crew interaction stats: {e}")

@router.get("/{project_id}/template-usage", summary="Get template usage metrics for a project")
async def get_template_usage(project_id: str):
    try:
        usage = {
            "project_id": project_id,
            "total_templates_used": 0,
            "templates": []
        }
        return usage
    except Exception as e:
        logger.error(f"Error getting template usage for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get template usage: {e}")

@router.get("/{project_id}/generation-history", summary="Get generation history for a project")
async def get_generation_history(project_id: str):
    try:
        history = {
            "project_id": project_id,
            "events": []  # Each event could later include id, type, timestamp, inputs, outputs summary
        }
        return history
    except Exception as e:
        logger.error(f"Error getting generation history for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get generation history: {e}")
