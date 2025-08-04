import requests
import os
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

# Get the project service URL from environment variable
# Use localhost for local development, Docker service name for containerized deployment
PROJECT_SERVICE_URL = os.getenv("PROJECT_SERVICE_URL", "http://localhost:8002")

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
    # LLM Configuration fields
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_api_key_id: Optional[str] = None
    llm_temperature: Optional[str] = None
    llm_max_tokens: Optional[str] = None

class Project(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    client_name: str
    client_contact: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
    # LLM Configuration fields
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_api_key_id: Optional[str] = None
    llm_temperature: Optional[str] = "0.1"
    llm_max_tokens: Optional[str] = "4000"

class ProjectServiceClient:
    def __init__(self, base_url: str = PROJECT_SERVICE_URL):
        self.base_url = base_url
        self._auth_token = None

    def _get_auth_headers(self):
        """Get authentication headers for service-to-service communication using JWT"""
        import jwt
        from datetime import datetime, timedelta

        # Generate JWT service token with proper claims
        service_secret = os.getenv("SERVICE_JWT_SECRET", "your-service-secret-key-change-in-production")

        payload = {
            "iss": "backend-service",  # Issuer
            "aud": "project-service",  # Audience
            "sub": "service-account",  # Subject
            "iat": datetime.utcnow(),  # Issued at
            "exp": datetime.utcnow() + timedelta(minutes=15),  # Expires in 15 minutes
            "scope": "read:projects read:llm-configs write:projects"  # Service permissions
        }

        service_token = jwt.encode(payload, service_secret, algorithm="HS256")

        return {
            "Authorization": f"Bearer {service_token}",
            "Content-Type": "application/json",
            "X-Service-Name": "backend-service"
        }

    def create_project(self, project_data: ProjectCreate) -> Project:
        """Create a new project"""
        response = requests.post(
            f"{self.base_url}/projects",
            json=project_data.dict(),
            headers=self._get_auth_headers()
        )
        response.raise_for_status()
        return Project(**response.json())

    def get_project(self, project_id: str) -> Project:
        """Get a project by ID"""
        response = requests.get(
            f"{self.base_url}/projects/{project_id}",
            headers=self._get_auth_headers()
        )
        response.raise_for_status()
        return Project(**response.json())

    def list_projects(self) -> List[Project]:
        """List all projects"""
        response = requests.get(
            f"{self.base_url}/projects",
            headers=self._get_auth_headers()
        )
        response.raise_for_status()
        return [Project(**project) for project in response.json()]

    def update_project(self, project_id: str, project_data) -> Project:
        """Update a project"""
        # Handle both dict and ProjectUpdate objects
        if hasattr(project_data, 'dict'):
            data = project_data.dict(exclude_unset=True)
        else:
            data = project_data

        response = requests.put(
            f"{self.base_url}/projects/{project_id}",
            json=data,
            headers=self._get_auth_headers()
        )
        response.raise_for_status()
        return Project(**response.json())

    def delete_project(self, project_id: str) -> dict:
        """Delete a project"""
        response = requests.delete(f"{self.base_url}/projects/{project_id}")
        response.raise_for_status()
        return response.json()

    def get_platform_settings(self) -> List[dict]:
        """Get platform settings (API keys, etc.)"""
        try:
            # Try to get settings from project service with admin auth
            response = requests.get(
                f"{self.base_url}/platform-settings",
                headers=self._get_auth_headers()
            )
            if response.status_code == 200:
                return response.json()
            else:
                # If no admin auth or endpoint not available, return empty list
                return []
        except Exception:
            # Return empty list if project service is not available
            return []
