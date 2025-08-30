import requests
import os
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
try:
    from app.main import correlation_id_ctx
except ImportError:
    correlation_id_ctx = None

import os, requests, logging, time, json, base64
from typing import Dict
from functools import lru_cache

logger = logging.getLogger(__name__)

# Get the project service URL from environment variable
# Use localhost for local development, Docker service name for production
PROJECT_SERVICE_URL = os.getenv("PROJECT_SERVICE_URL", "http://localhost:8002")

class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    client_name: str
    client_contact: Optional[str] = None
    # Extended project context fields (optional)
    project_overview: Optional[str] = None
    project_intent: Optional[str] = None
    client_summary: Optional[str] = None
    rfp_summary: Optional[str] = None
    rfp_responses: Optional[str] = None
    expectations: Optional[str] = None
    deliverables_summary: Optional[str] = None
    timeline_notes: Optional[str] = None
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
    # Extended project context fields
    project_overview: Optional[str] = None
    project_intent: Optional[str] = None
    client_summary: Optional[str] = None
    rfp_summary: Optional[str] = None
    rfp_responses: Optional[str] = None
    expectations: Optional[str] = None
    deliverables_summary: Optional[str] = None
    timeline_notes: Optional[str] = None
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
    # Extended project context
    project_overview: Optional[str] = None
    project_intent: Optional[str] = None
    client_summary: Optional[str] = None
    rfp_summary: Optional[str] = None
    rfp_responses: Optional[str] = None
    expectations: Optional[str] = None
    deliverables_summary: Optional[str] = None
    timeline_notes: Optional[str] = None
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
        # Service account credentials for option 2 (JWT auth)
        self.username = os.getenv("PROJECT_SERVICE_USERNAME")
        self.password = os.getenv("PROJECT_SERVICE_PASSWORD")
        self._token: Optional[str] = None
        self._token_expiry: Optional[int] = None  # epoch seconds
        self._default_token_ttl = int(os.getenv("PROJECT_SERVICE_TOKEN_TTL", "3300"))  # ~55m

    # ---------------- Authentication helpers -----------------
    def _token_valid(self) -> bool:
        if not self._token or not self._token_expiry:
            return False
        # refresh if less than 60s remaining
        return (self._token_expiry - time.time()) > 60

    def _decode_jwt_exp(self, token: str) -> Optional[int]:
        try:
            parts = token.split('.')
            if len(parts) < 2:
                return None
            padded = parts[1] + '=' * (-len(parts[1]) % 4)
            payload_bytes = base64.urlsafe_b64decode(padded)
            payload = json.loads(payload_bytes.decode('utf-8'))
            return int(payload.get('exp')) if 'exp' in payload else None
        except Exception:
            return None

    def _fetch_token(self):
        if not (self.username and self.password):
            logger.debug("PROJECT_SERVICE_USERNAME/PASSWORD not set; skipping auth")
            return
        try:
            resp = requests.post(
                f"{self.base_url}/token",
                data={"username": self.username, "password": self.password},
                timeout=5,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            if resp.status_code == 200:
                data = resp.json()
                token = data.get("access_token")
                if token:
                    self._token = token
                    exp = self._decode_jwt_exp(token)
                    if exp:
                        self._token_expiry = exp
                    else:
                        # fallback approximate expiry
                        self._token_expiry = int(time.time()) + self._default_token_ttl
                    logger.info("[PROJECT_SERVICE_CLIENT] Acquired JWT token for project-service calls")
                else:
                    logger.warning("[PROJECT_SERVICE_CLIENT] Token endpoint returned no access_token")
            else:
                logger.warning(f"[PROJECT_SERVICE_CLIENT] Token request failed {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            logger.error(f"[PROJECT_SERVICE_CLIENT] Token fetch error: {e}")

    def _ensure_token(self):
        if not self._token_valid():
            self._fetch_token()

    def _get_auth_headers(self):
        headers = {"Content-Type": "application/json"}
        # Prefer JWT auth if credentials configured
        if self.username and self.password:
            self._ensure_token()
            if self._token:
                headers["Authorization"] = f"Bearer {self._token}"
        # Fallback internal key if present (and maybe used for other endpoints)
        elif self.api_key:
            headers["X-Internal-API-Key"] = self.api_key
        # Fallback to SERVICE_AUTH_TOKEN as Bearer token
        else:
            service_token = os.getenv("SERVICE_AUTH_TOKEN")
            if service_token:
                headers["Authorization"] = f"Bearer {service_token}"
        # Correlation ID propagation
        try:
            from app.core.logging_config import correlation_id_ctx  # local import to avoid cycles
            corr_id = correlation_id_ctx.get("-")
            if corr_id and corr_id != "-":
                headers["X-Correlation-ID"] = corr_id
        except Exception:
            pass
        return headers

    # ---------------- Project operations -----------------
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

    def get_project(self, project_id: str) -> Optional[Project]:
        """Get a project by ID with retry logic and UUID validation"""
        # Basic UUID format validation
        if not project_id or len(project_id) != 36:
            logger.warning(f"Invalid project ID format: {project_id}")
            return None

        max_retries = 3
        base_delay = 0.5

        for attempt in range(max_retries):
            try:
                response = requests.get(
                    f"{self.base_url}/projects/{project_id}",
                    headers=self._get_auth_headers(),
                    timeout=10  # Increased timeout
                )

                if response.status_code == 404:
                    return None
                elif response.status_code == 400:
                    # Invalid UUID format - don't retry
                    logger.warning(f"Invalid UUID format rejected by server: {project_id}")
                    return None
                elif response.status_code == 503:
                    # Service unavailable - retry
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"Project service unavailable (attempt {attempt + 1}), retrying in {delay}s...")
                        time.sleep(delay)
                        continue

                response.raise_for_status()
                return Project(**response.json())

            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Request timeout (attempt {attempt + 1}), retrying in {delay}s...")
                    time.sleep(delay)
                    continue
                else:
                    logger.error(f"Request timeout after {max_retries} attempts for project {project_id}")
                    raise
            except requests.exceptions.ConnectionError as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Connection error (attempt {attempt + 1}): {e}, retrying in {delay}s...")
                    time.sleep(delay)
                    continue
                else:
                    logger.error(f"Connection failed after {max_retries} attempts for project {project_id}: {e}")
                    raise
            except requests.exceptions.RequestException as e:
                logger.error(f"Error fetching project {project_id}: {e}")
                raise

        return None

    def list_projects(self) -> List[Project]:
        """List all projects with retry logic"""
        max_retries = 3
        base_delay = 0.5

        for attempt in range(max_retries):
            try:
                response = requests.get(
                    f"{self.base_url}/projects",
                    headers=self._get_auth_headers(),
                    timeout=10  # Increased timeout
                )
                response.raise_for_status()
                return [Project(**project) for project in response.json()]

            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"List projects timeout (attempt {attempt + 1}), retrying in {delay}s...")
                    time.sleep(delay)
                    continue
                else:
                    logger.error(f"List projects timeout after {max_retries} attempts")
                    raise
            except requests.exceptions.ConnectionError as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"List projects connection error (attempt {attempt + 1}): {e}, retrying in {delay}s...")
                    time.sleep(delay)
                    continue
                else:
                    logger.error(f"List projects connection failed after {max_retries} attempts: {e}")
                    raise
            except requests.exceptions.RequestException as e:
                logger.error(f"Error listing projects: {e}")
                raise

        return []

    def update_project(self, project_id: str, project_data) -> Project:
        """Update a project with retry logic and UUID validation"""
        # Basic UUID format validation
        if not project_id or len(project_id) != 36:
            logger.warning(f"Invalid project ID format for update: {project_id}")
            raise ValueError("Invalid project ID format")

        # Handle both dict and ProjectUpdate objects
        if hasattr(project_data, 'dict'):
            data = project_data.dict(exclude_unset=True)
        else:
            data = project_data

        max_retries = 3
        base_delay = 0.5

        for attempt in range(max_retries):
            try:
                response = requests.put(
                    f"{self.base_url}/projects/{project_id}",
                    json=data,
                    headers=self._get_auth_headers(),
                    timeout=10  # Increased timeout
                )
                response.raise_for_status()
                return Project(**response.json())

            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Update project timeout (attempt {attempt + 1}), retrying in {delay}s...")
                    time.sleep(delay)
                    continue
                else:
                    logger.error(f"Update project timeout after {max_retries} attempts for project {project_id}")
                    raise
            except requests.exceptions.ConnectionError as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Update project connection error (attempt {attempt + 1}): {e}, retrying in {delay}s...")
                    time.sleep(delay)
                    continue
                else:
                    logger.error(f"Update project connection failed after {max_retries} attempts for project {project_id}: {e}")
                    raise
            except requests.exceptions.RequestException as e:
                logger.error(f"Error updating project {project_id}: {e}")
                raise

    def delete_project(self, project_id: str) -> dict:
        """Delete a project with retry logic and UUID validation"""
        # Basic UUID format validation
        if not project_id or len(project_id) != 36:
            logger.warning(f"Invalid project ID format for deletion: {project_id}")
            raise ValueError("Invalid project ID format")

        max_retries = 3
        base_delay = 0.5

        for attempt in range(max_retries):
            try:
                response = requests.delete(
                    f"{self.base_url}/projects/{project_id}",
                    headers=self._get_auth_headers(),
                    timeout=15  # Increased timeout for deletion
                )
                response.raise_for_status()
                return response.json()

            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Delete project timeout (attempt {attempt + 1}), retrying in {delay}s...")
                    time.sleep(delay)
                    continue
                else:
                    logger.error(f"Delete project timeout after {max_retries} attempts for project {project_id}")
                    raise
            except requests.exceptions.ConnectionError as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Delete project connection error (attempt {attempt + 1}): {e}, retrying in {delay}s...")
                    time.sleep(delay)
                    continue
                else:
                    logger.error(f"Delete project connection failed after {max_retries} attempts for project {project_id}: {e}")
                    raise
            except requests.exceptions.RequestException as e:
                logger.error(f"Error deleting project {project_id}: {e}")
                raise

    def get_platform_settings(self) -> List[dict]:
        """Get platform settings (API keys, etc.)"""
        try:
            response = requests.get(
                f"{self.base_url}/platform-settings",
                headers=self._get_auth_headers()
            )
            if response.status_code == 200:
                return response.json()
            else:
                return []
        except Exception:
            return []

    def get_project_file_count(self, project_id: str, timeout: float = 0.7) -> int:
        """Return file count for a project using a lightweight endpoint with retry logic"""
        # Basic UUID format validation
        if not project_id or len(project_id) != 36:
            logger.warning(f"Invalid project ID format for file count: {project_id}")
            return 0

        headers = self._get_auth_headers()
        max_retries = 2  # Fewer retries for lightweight endpoint
        base_delay = 0.2

        for attempt in range(max_retries):
            try:
                r = requests.get(f"{self.base_url}/projects/{project_id}/files/count", headers=headers, timeout=timeout)
                if r.status_code == 200:
                    try:
                        data = r.json()
                        if isinstance(data, dict) and 'count' in data:
                            return int(data['count'])
                        if isinstance(data, int):
                            return int(data)
                    except Exception:
                        pass
                elif r.status_code == 404:
                    return 0  # Project not found
                elif r.status_code == 400:
                    logger.warning(f"Invalid UUID format rejected by server for file count: {project_id}")
                    return 0

            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.debug(f"File count timeout (attempt {attempt + 1}), retrying in {delay}s...")
                    time.sleep(delay)
                    continue
            except Exception:
                pass

        # Fallback to listing (short timeout)
        try:
            r = requests.get(f"{self.base_url}/projects/{project_id}/files", headers=headers, timeout=timeout)
            if r.status_code == 200:
                try:
                    files = r.json() or []
                    return len(files)
                except Exception:
                    return 0
        except Exception:
            return 0
        return 0

    def get_project_files(self, project_id: str, timeout: float = 1.0) -> list:
        """Get files for a project with retry logic and UUID validation"""
        # Basic UUID format validation
        if not project_id or len(project_id) != 36:
            logger.warning(f"Invalid project ID format for files: {project_id}")
            return []

        headers = self._get_auth_headers()
        max_retries = 3
        base_delay = 0.3

        for attempt in range(max_retries):
            try:
                r = requests.get(f"{self.base_url}/projects/{project_id}/files", headers=headers, timeout=timeout)
                if r.status_code == 200:
                    try:
                        files = r.json() or []
                        return files
                    except Exception:
                        pass
                elif r.status_code == 404:
                    return []  # Project not found
                elif r.status_code == 400:
                    logger.warning(f"Invalid UUID format rejected by server for files: {project_id}")
                    return []

            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.debug(f"Files timeout (attempt {attempt + 1}), retrying in {delay}s...")
                    time.sleep(delay)
                    continue
            except Exception:
                pass

        return []

    def get_vector_count(self, project_id: str, timeout: float = 3.0) -> int:
        """Get vector embeddings count for a project from vector-service via HTTP with retry logic"""
        # Basic UUID format validation
        if not project_id or len(project_id) != 36:
            logger.warning(f"Invalid project ID format for vector count: {project_id}")
            return 0

        try:
            base_url = os.getenv("VECTOR_SERVICE_URL", "http://localhost:8005")
            url = f"{base_url}/api/vectors/projects/{project_id}/stats"
            headers = self._get_auth_headers()

            # Simple retry for vector service
            max_retries = 2
            for attempt in range(max_retries):
                try:
                    r = requests.get(url, headers=headers, timeout=timeout)
                    if r.status_code == 200:
                        data = r.json() or {}
                        return int((data.get("embeddings_count") or data.get("total") or 0))
                    elif r.status_code == 404:
                        return 0  # Project not found
                except requests.exceptions.Timeout:
                    if attempt < max_retries - 1:
                        time.sleep(0.5)
                        continue
        except Exception as e:
            logger.debug(f"[PROJECT_SERVICE_CLIENT] get_vector_count failed: {e}")
        return 0

    def get_graph_counts(self, project_id: str, timeout: float = 3.0) -> dict:
        """Get graph node and relationship counts for a project from graph-service via HTTP with retry logic"""
        # Basic UUID format validation
        if not project_id or len(project_id) != 36:
            logger.warning(f"Invalid project ID format for graph counts: {project_id}")
            return {"nodes": 0, "relationships": 0}

        try:
            base_url = os.getenv("GRAPH_SERVICE_URL", "http://localhost:8006")
            url = f"{base_url}/api/graphs/projects/{project_id}/stats"
            headers = self._get_auth_headers()

            # Simple retry for graph service
            max_retries = 2
            for attempt in range(max_retries):
                try:
                    r = requests.get(url, headers=headers, timeout=timeout)
                    if r.status_code == 200:
                        data = r.json() or {}
                        # Graph service may return keys as total_nodes/total_relationships or nodes/relationships
                        nodes_val = (
                            data.get("nodes")
                            or data.get("graph_nodes")
                            or data.get("total_nodes")
                            or 0
                        )
                        rels_val = (
                            data.get("relationships")
                            or data.get("graph_relationships")
                            or data.get("total_relationships")
                            or 0
                        )
                        return {
                            "nodes": int(nodes_val or 0),
                            "relationships": int(rels_val or 0),
                        }
                    elif r.status_code == 404:
                        return {"nodes": 0, "relationships": 0}  # Project not found
                except requests.exceptions.Timeout:
                    if attempt < max_retries - 1:
                        time.sleep(0.5)
                        continue
        except Exception as e:
            logger.debug(f"[PROJECT_SERVICE_CLIENT] get_graph_counts failed: {e}")
        return {"nodes": 0, "relationships": 0}

# Cached singleton accessor to avoid repeated instantiation and enable reuse across routers
@lru_cache(maxsize=1)
def get_project_service() -> ProjectServiceClient:
    return ProjectServiceClient()

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
            headers = client._get_auth_headers()
            logger.info(f"[LLM_CACHE][DEBUG] Request headers for /llm-configurations: {headers}")
            r = requests.get(f"{client.base_url}/llm-configurations", headers=headers, timeout=10)
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
