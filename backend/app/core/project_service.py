import requests
import os
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
try:
    from app.main import correlation_id_ctx
except ImportError:
    correlation_id_ctx = None

import os, requests, logging, time, json
from typing import Dict

logger = logging.getLogger(__name__)

# Get the project service URL from environment variable
# Use localhost for local development, Docker service name for containerized deployment
PROJECT_SERVICE_URL = os.getenv("PROJECT_SERVICE_URL", "http://localhost:8002")

class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    client_name: str
    client_contact: Optional[str] = None
    # LLM Configuration fields (included at creation time)
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_api_key_id: Optional[str] = None
    llm_temperature: Optional[str] = "0.1"
    llm_max_tokens: Optional[str] = "4000"

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
    # Report fields
    report_content: Optional[str] = None
    report_url: Optional[str] = None
    report_artifact_url: Optional[str] = None

class ProjectServiceClient:
    def __init__(self):
        self.base_url = os.getenv("PROJECT_SERVICE_URL", "http://localhost:8002")
        self.api_key = os.getenv("PLATFORM_INTERNAL_API_KEY")

    def _get_auth_headers(self):
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-Internal-API-Key"] = self.api_key
        return headers

    def create_project(self, project_data: ProjectCreate) -> Project:
        """Create a new project"""
        response = requests.post(
            f"{self.base_url}/projects",
            json=project_data.model_dump(),
            headers=self._get_auth_headers(),
            timeout=5
        )
        response.raise_for_status()
        return Project(**response.json())

    def get_project(self, project_id: str) -> Project:
        """Get a project by ID"""
        response = requests.get(
            f"{self.base_url}/projects/{project_id}",
            headers=self._get_auth_headers(),
            timeout=5
        )
        response.raise_for_status()
        return Project(**response.json())

    def list_projects(self) -> List[Project]:
        """List all projects"""
        response = requests.get(
            f"{self.base_url}/projects",
            headers=self._get_auth_headers(),
            timeout=5
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
            headers=self._get_auth_headers(),
            timeout=5
        )
        response.raise_for_status()
        return Project(**response.json())

    def delete_project(self, project_id: str) -> dict:
        """Delete a project"""
        response = requests.delete(
            f"{self.base_url}/projects/{project_id}",
            headers=self._get_auth_headers(),
            timeout=5
        )
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

# LLM configurations cache
_llm_config_cache: Dict[str, Dict] = {}
_last_llm_cache_refresh = 0.0
_LLM_CACHE_TTL = 60  # seconds
_LOCAL_LLM_CONFIG_FILE = os.getenv("LOCAL_LLM_CONFIG_FILE", "llm_configurations.json")

def _load_local_llm_configs() -> Dict[str, Dict]:
    if os.path.exists(_LOCAL_LLM_CONFIG_FILE):
        try:
            with open(_LOCAL_LLM_CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f) or []
            if isinstance(data, dict):
                return data
            return {cfg.get("id") or cfg.get("name"): cfg for cfg in data}
        except Exception as e:
            logger.warning(f"[LLM_CACHE] Failed reading local config file: {e}")
    return {}

def get_llm_configurations_from_db(force: bool = False) -> Dict[str, Dict]:
    global _last_llm_cache_refresh, _llm_config_cache
    now = time.time()
    if force or (now - _last_llm_cache_refresh) > _LLM_CACHE_TTL or not _llm_config_cache:
        try:
            client = ProjectServiceClient()
            r = requests.get(f"{client.base_url}/llm-configurations", headers=client._get_auth_headers(), timeout=10)
            if r.status_code == 200:
                data = r.json() or []
                _llm_config_cache = {cfg.get("id") or cfg.get("_id") or cfg.get("name"): cfg for cfg in data}
                _last_llm_cache_refresh = now
                logger.info(f"[LLM_CACHE] Loaded {len(_llm_config_cache)} configs from project service")
            elif r.status_code in (401, 403):
                logger.info(f"[LLM_CACHE] Auth refused ({r.status_code}); using local fallback if present")
                _llm_config_cache = _load_local_llm_configs()
                _last_llm_cache_refresh = now
                if _llm_config_cache:
                    logger.info(f"[LLM_CACHE] Loaded {len(_llm_config_cache)} local configs (auth fallback)")
                else:
                    logger.warning(f"[LLM_CACHE] No local configs available during auth fallback")
            else:
                logger.warning(f"[LLM_CACHE] Failed to refresh configs: {r.status_code}")
        except Exception as e:
            logger.warning(f"[LLM_CACHE] Service unreachable: {e}; attempting local fallback")
            _llm_config_cache = _load_local_llm_configs()
            if _llm_config_cache:
                logger.info(f"[LLM_CACHE] Loaded {len(_llm_config_cache)} local configs (offline mode)")
    return _llm_config_cache

def invalidate_llm_cache():
    global _llm_config_cache, _last_llm_cache_refresh
    _llm_config_cache = {}
    _last_llm_cache_refresh = 0.0
