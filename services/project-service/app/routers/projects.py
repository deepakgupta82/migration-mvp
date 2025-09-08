"""
Projects Router
Handles project CRUD operations
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime

from app.repositories.dependency_container import get_project_repository, get_user_repository
from database import ProjectModel, UserModel

logger = logging.getLogger("project-service.projects")

router = APIRouter()

# Pydantic models for request/response
from pydantic import BaseModel, Field
from uuid import uuid4

class ProjectCreate(BaseModel):
    name: str = Field(..., description="Project name")
    description: Optional[str] = Field(None, description="Project description")
    client_name: Optional[str] = Field(None, description="Client name")
    project_overview: Optional[str] = Field(None, description="Project overview")
    project_intent: Optional[str] = Field(None, description="Project intent")
    client_summary: Optional[str] = Field(None, description="Client summary")
    rfp_summary: Optional[str] = Field(None, description="RFP summary")
    rfp_responses: Optional[str] = Field(None, description="RFP responses")
    expectations: Optional[str] = Field(None, description="Expectations")
    deliverables_summary: Optional[str] = Field(None, description="Deliverables summary")
    timeline_notes: Optional[str] = Field(None, description="Timeline notes")
    status: str = Field("initiated", description="Project status")
    llm_api_key_id: Optional[str] = Field(None, description="LLM API key ID")
    llm_provider: Optional[str] = Field(None, description="LLM provider")
    llm_model: Optional[str] = Field(None, description="LLM model")
    llm_temperature: Optional[str] = Field(None, description="LLM temperature")
    llm_max_tokens: Optional[str] = Field(None, description="LLM max tokens")

class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Project name")
    description: Optional[str] = Field(None, description="Project description")
    client_name: Optional[str] = Field(None, description="Client name")
    project_overview: Optional[str] = Field(None, description="Project overview")
    project_intent: Optional[str] = Field(None, description="Project intent")
    client_summary: Optional[str] = Field(None, description="Client summary")
    rfp_summary: Optional[str] = Field(None, description="RFP summary")
    rfp_responses: Optional[str] = Field(None, description="RFP responses")
    expectations: Optional[str] = Field(None, description="Expectations")
    deliverables_summary: Optional[str] = Field(None, description="Deliverables summary")
    timeline_notes: Optional[str] = Field(None, description="Timeline notes")
    status: Optional[str] = Field(None, description="Project status")
    llm_api_key_id: Optional[str] = Field(None, description="LLM API key ID")
    llm_provider: Optional[str] = Field(None, description="LLM provider")
    llm_model: Optional[str] = Field(None, description="LLM model")
    llm_temperature: Optional[str] = Field(None, description="LLM temperature")
    llm_max_tokens: Optional[str] = Field(None, description="LLM max tokens")

@router.get("", summary="List all projects")
async def list_projects(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search query")
):
    """List all projects with optional filtering"""
    try:
        repo = get_project_repository()

        if user_id:
            projects = repo.get_user_projects(user_id)
        elif status:
            projects = repo.get_projects_by_status(status)
        elif search:
            projects = repo.search_projects(search)
        else:
            # Get all projects - this might need to be implemented in repository
            projects = repo.get_all()

        # Convert to dict format
        result = []
        for project in projects:
            if hasattr(project, 'model_dump'):
                project_dict = project.model_dump()
            elif hasattr(project, '__dict__'):
                project_dict = project.__dict__
                # Remove SQLAlchemy internal attributes
                project_dict.pop('_sa_instance_state', None)
            else:
                project_dict = dict(project)

            result.append(project_dict)

        return result

    except Exception as e:
        logger.error(f"Error listing projects: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list projects: {str(e)}")

@router.post("", summary="Create a new project")
async def create_project(project_data: ProjectCreate):
    """Create a new project"""
    try:
        repo = get_project_repository()

        # Convert to dict and add timestamps
        project_dict = project_data.model_dump()
        project_dict['id'] = str(uuid4())
        project_dict['created_at'] = datetime.utcnow()
        project_dict['updated_at'] = datetime.utcnow()

        # Create project
        project = repo.create(project_dict)

        # Convert to dict for response
        if hasattr(project, 'model_dump'):
            result = project.model_dump()
        elif hasattr(project, '__dict__'):
            result = project.__dict__
            result.pop('_sa_instance_state', None)
        else:
            result = dict(project)

        logger.info(f"Created project: {result['id']}")
        return result

    except Exception as e:
        logger.error(f"Error creating project: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create project: {str(e)}")

@router.get("/{project_id}", summary="Get a project by ID")
async def get_project(project_id: str):
    """Get a project by its ID"""
    try:
        repo = get_project_repository()
        project = repo.get_by_id_with_users(project_id)

        if not project:
            raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

        # Convert to dict
        if hasattr(project, 'model_dump'):
            result = project.model_dump()
        elif hasattr(project, '__dict__'):
            result = project.__dict__
            result.pop('_sa_instance_state', None)
        else:
            result = dict(project)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get project: {str(e)}")

@router.put("/{project_id}", summary="Update a project")
async def update_project(project_id: str, project_data: ProjectUpdate):
    """Update an existing project"""
    try:
        repo = get_project_repository()

        # Check if project exists
        existing = repo.get_by_id(project_id)
        if not existing:
            raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

        # Convert to dict and add update timestamp
        update_dict = project_data.model_dump(exclude_unset=True)
        update_dict['updated_at'] = datetime.utcnow()

        # Update project
        updated_project = repo.update(project_id, update_dict)

        # Convert to dict for response
        if hasattr(updated_project, 'model_dump'):
            result = updated_project.model_dump()
        elif hasattr(updated_project, '__dict__'):
            result = updated_project.__dict__
            result.pop('_sa_instance_state', None)
        else:
            result = dict(updated_project)

        logger.info(f"Updated project: {project_id}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update project: {str(e)}")

@router.delete("/{project_id}", summary="Delete a project")
async def delete_project(project_id: str):
    """Delete a project and all its related data"""
    try:
        repo = get_project_repository()

        # Check if project exists
        existing = repo.get_by_id(project_id)
        if not existing:
            raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

        # Delete project with cascade
        success = repo.delete_project_cascade(project_id)

        if not success:
            raise HTTPException(status_code=500, detail=f"Failed to delete project {project_id}")

        logger.info(f"Deleted project: {project_id}")
        return {"message": f"Project {project_id} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete project: {str(e)}")

@router.get("/{project_id}/stats", summary="Get project statistics")
async def get_project_stats(project_id: str):
    """Get statistics for a specific project"""
    try:
        repo = get_project_repository()

        # Check if project exists
        project = repo.get_by_id(project_id)
        if not project:
            raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

        # Get file count
        file_count = repo.get_project_files_count(project_id)

        # Get basic stats
        stats = {
            "project_id": project_id,
            "file_count": file_count,
            "status": project.status if hasattr(project, 'status') else 'unknown',
            "created_at": project.created_at.isoformat() if hasattr(project, 'created_at') and project.created_at else None,
            "updated_at": project.updated_at.isoformat() if hasattr(project, 'updated_at') and project.updated_at else None
        }

        return stats

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting project stats {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get project stats: {str(e)}")
