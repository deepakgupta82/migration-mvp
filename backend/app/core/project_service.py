import requests
import os
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

# Get the project service URL from environment variable
PROJECT_SERVICE_URL = os.getenv("PROJECT_SERVICE_URL", "http://project-service:8000")

class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    client_name: str
    client_contact: Optional[str] = None

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    client_name: Optional[str] = None
    client_contact: Optional[str] = None
    status: Optional[str] = None

class Project(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    client_name: str
    client_contact: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime

class ProjectServiceClient:
    def __init__(self, base_url: str = PROJECT_SERVICE_URL):
        self.base_url = base_url

    def create_project(self, project_data: ProjectCreate) -> Project:
        """Create a new project"""
        response = requests.post(f"{self.base_url}/projects", json=project_data.dict())
        response.raise_for_status()
        return Project(**response.json())

    def get_project(self, project_id: str) -> Project:
        """Get a project by ID"""
        response = requests.get(f"{self.base_url}/projects/{project_id}")
        response.raise_for_status()
        return Project(**response.json())

    def list_projects(self) -> List[Project]:
        """List all projects"""
        response = requests.get(f"{self.base_url}/projects")
        response.raise_for_status()
        return [Project(**project) for project in response.json()]

    def update_project(self, project_id: str, project_data: ProjectUpdate) -> Project:
        """Update a project"""
        response = requests.put(f"{self.base_url}/projects/{project_id}", json=project_data.dict(exclude_unset=True))
        response.raise_for_status()
        return Project(**response.json())

    def delete_project(self, project_id: str) -> dict:
        """Delete a project"""
        response = requests.delete(f"{self.base_url}/projects/{project_id}")
        response.raise_for_status()
        return response.json()
