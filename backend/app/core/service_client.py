#!/usr/bin/env python3
"""
API Gateway Service Client
HTTP client for routing requests to extracted microservices
"""

import os
import logging
import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger("api-gateway")

class ServiceClient:
    """HTTP client for communicating with microservices"""
    
    def __init__(self):
        # Service endpoints configuration
        self.services = {
            "project": os.getenv("PROJECT_SERVICE_URL", "http://localhost:8002"),
            "reporting": os.getenv("REPORTING_SERVICE_URL", "http://localhost:8001"),
            "document": os.getenv("DOCUMENT_SERVICE_URL", "http://localhost:8003"),
            "vector": os.getenv("VECTOR_SERVICE_URL", "http://localhost:8005"),
            "graph": os.getenv("GRAPH_SERVICE_URL", "http://localhost:8006"),
            "llm": os.getenv("LLM_SERVICE_URL", "http://localhost:8007"),
            "ai_agent": os.getenv("AI_AGENT_SERVICE_URL", "http://localhost:8008"),
            "websocket": os.getenv("WEBSOCKET_SERVICE_URL", "http://localhost:8009"),
            "storage": os.getenv("STORAGE_SERVICE_URL", "http://localhost:8010"),
            "analytics": os.getenv("ANALYTICS_SERVICE_URL", "http://localhost:8014"),
            "security": os.getenv("SECURITY_SERVICE_URL", "http://localhost:8015"),
            "collaboration": os.getenv("COLLABORATION_SERVICE_URL", "http://localhost:8016"),
            "knowledge": os.getenv("KNOWLEDGE_SERVICE_URL", "http://localhost:8017"),
        }
        
        # HTTP client configuration
        self.timeout = httpx.Timeout(30.0, connect=5.0)
        self.client = httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100)
        )
        
        logger.info(f"Service client initialized with endpoints: {list(self.services.keys())}")

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()

    async def _make_request(self, method: str, service: str, path: str, 
                           json: Optional[Dict] = None, params: Optional[Dict] = None,
                           files: Optional[Dict] = None, headers: Optional[Dict] = None) -> Dict[str, Any]:
        """Make HTTP request to service"""
        try:
            if service not in self.services:
                raise ValueError(f"Unknown service: {service}")
            
            url = f"{self.services[service]}{path}"
            
            # Always add service authentication header
            request_headers = {
                "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
            }
            
            # Add Content-Type only if we're sending JSON data
            if json is not None:
                request_headers["Content-Type"] = "application/json"
                
            # Correlation ID propagation
            try:
                from app.core.logging_config import correlation_id_ctx
                corr_id = correlation_id_ctx.get("-")
                if corr_id and corr_id != "-":
                    request_headers["X-Correlation-ID"] = corr_id
            except Exception:
                pass

            # Add any additional headers
            if headers:
                request_headers.update(headers)
            
            logger.info(f"ServiceClient: {method} {url} - Headers: {list(request_headers.keys())}")
            
            response = await self.client.request(
                method=method,
                url=url,
                json=json,
                params=params,
                files=files,
                headers=request_headers
            )
            
            logger.info(f"ServiceClient: Response {response.status_code} from {url}")
            
            # Handle different response types
            if response.headers.get("content-type", "").startswith("application/json"):
                result = response.json()
            else:
                # Return raw content plus a few headers so callers can propagate content-type
                result = {
                    "content": response.content,
                    "status_code": response.status_code,
                    "content-type": response.headers.get("content-type"),
                    "Content-Type": response.headers.get("Content-Type"),
                }
            
            if response.status_code >= 400:
                logger.error(f"Service error {response.status_code}: {result}")
                raise httpx.HTTPStatusError(f"Service error: {response.status_code}", request=response.request, response=response)
            
            logger.debug(f"Request successful: {method} {url}")
            return result
            
        except httpx.TimeoutException as e:
            logger.error(f"Timeout calling {service} service: {e}")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error calling {service} service: {e}")
            raise
        except Exception as e:
            logger.error(f"Error calling {service} service: {e}")
            raise

    async def request_raw(
        self,
        method: str,
        service: str,
        path: str,
        *,
        json: Optional[Dict] = None,
        params: Optional[Dict] = None,
        files: Optional[Dict] = None,
        headers: Optional[Dict] = None,
    ) -> httpx.Response:
        """Low-level helper to perform a request and return the raw response.
        Useful for diagnostics like correlation ID propagation where headers matter.
        """
        if service not in self.services:
            raise ValueError(f"Unknown service: {service}")

        url = f"{self.services[service]}{path}"

        # Base headers with service auth
        request_headers = {
            "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
        }

        # Add JSON content-type when applicable
        if json is not None:
            request_headers["Content-Type"] = "application/json"

        # Correlation ID from context unless explicitly provided by caller
        try:
            from app.core.logging_config import correlation_id_ctx
            corr_id = correlation_id_ctx.get("-")
            if corr_id and corr_id != "-" and not (headers and headers.get("X-Correlation-ID")):
                request_headers["X-Correlation-ID"] = corr_id
        except Exception:
            pass

        if headers:
            request_headers.update(headers)

        logger.info(f"ServiceClient.raw: {method} {url} - Headers: {list(request_headers.keys())}")
        resp = await self.client.request(
            method=method,
            url=url,
            json=json,
            params=params,
            files=files,
            headers=request_headers,
        )
        return resp

    # Project Service Methods
    async def list_projects(self, include_stats: bool = False) -> List[Dict]:
        """List all projects"""
        # Project service requires authentication, use admin token for system operations
        headers = {"Authorization": f"Bearer {await self._get_admin_token()}"}
        return await self._make_request("GET", "project", "/projects", params={"include_stats": include_stats}, headers=headers)

    async def get_project(self, project_id: str) -> Dict:
        """Get project by ID"""
        headers = {"Authorization": f"Bearer {await self._get_admin_token()}"}
        return await self._make_request("GET", "project", f"/projects/{project_id}", headers=headers)

    async def create_project(self, project_data: Dict) -> Dict:
        """Create new project"""
        headers = {"Authorization": f"Bearer {await self._get_admin_token()}"}
        return await self._make_request("POST", "project", "/projects", json=project_data, headers=headers)

    async def delete_project(self, project_id: str) -> Dict:
        """Delete project"""
        headers = {"Authorization": f"Bearer {await self._get_admin_token()}"}
        return await self._make_request("DELETE", "project", f"/projects/{project_id}", headers=headers)

    async def update_project(self, project_id: str, project_data: Dict) -> Dict:
        """Update a project by ID"""
        headers = {"Authorization": f"Bearer {await self._get_admin_token()}"}
        return await self._make_request("PUT", "project", f"/projects/{project_id}", json=project_data, headers=headers)

    async def _get_admin_token(self) -> str:
        """Get service authentication token for inter-service requests"""
        # Use the SERVICE_AUTH_TOKEN environment variable for service-to-service authentication
        return os.getenv("SERVICE_AUTH_TOKEN", "service-backend-token")

    # Document Service Methods  
    async def upload_documents(self, project_id: str, files: List) -> Dict:
        """Upload documents to storage"""
        try:
            # Build a list of ('files', (filename, content, content_type)) tuples
            multipart_files = []
            for i, file in enumerate(files):
                if hasattr(file, 'read'):
                    content = await file.read()
                    filename = getattr(file, 'filename', f'file_{i}')
                    content_type = getattr(file, 'content_type', 'application/octet-stream')
                    multipart_files.append(('files', (filename, content, content_type)))
                    # Reset file pointer for any subsequent reads
                    if hasattr(file, 'seek'):
                        await file.seek(0)
                else:
                    # Assume already in httpx file tuple form
                    multipart_files.append(('files', file))

            return await self._make_request("POST", "document", f"/api/documents/{project_id}/upload", files=multipart_files)
        except Exception as e:
            logger.error(f"Upload documents failed: {e}")
            raise

    async def process_documents(self, project_id: str, file_list: Optional[List[str]] = None, reprocess: bool = False) -> Dict:
        """Process uploaded documents via document-service.
        If file_list provided, calls process-selected with optional reprocess flag;
        otherwise triggers process-all with reprocess flag if supported.
        """
        if file_list:
            endpoint = f"/api/documents/{project_id}/process-selected"
            payload = {"file_names": file_list, "reprocess": bool(reprocess)}
            return await self._make_request("POST", "document", endpoint, json=payload)
        else:
            endpoint = f"/api/documents/{project_id}/process-all"
            # Some implementations of process-all may accept a reprocess flag
            payload = {"reprocess": bool(reprocess)}
            return await self._make_request("POST", "document", endpoint, json=payload)

    async def get_document_status(self, project_id: str, job_id: str) -> Dict:
        """Get document processing status"""
        return await self._make_request("GET", "document", f"/api/documents/{project_id}/status/{job_id}")

    # Vector Service Methods
    async def create_vector_collection(self, project_id: str) -> Dict:
        """Create vector collection for project"""
        return await self._make_request("POST", "vector", f"/api/vectors/projects/{project_id}/collection")

    async def add_documents_to_vectors(self, project_id: str, documents: List[Dict]) -> Dict:
        """Add documents to vector store"""
        return await self._make_request("POST", "vector", f"/api/vectors/projects/{project_id}/documents", 
                                      json={"documents": documents})

    async def vector_search(self, project_id: str, query: str, limit: int = 10) -> Dict:
        """Perform vector similarity search"""
        return await self._make_request("POST", "vector", f"/api/vectors/projects/{project_id}/search",
                                      json={"query": query, "limit": limit})

    async def hybrid_search(self, project_id: str, query: str, limit: int = 10) -> Dict:
        """Perform hybrid search"""
        return await self._make_request("POST", "vector", f"/api/vectors/projects/{project_id}/search/hybrid",
                                      json={"query": query, "limit": limit})

    async def delete_collection(self, project_id: str) -> Dict:
        """Delete a project's vector collection"""
        return await self._make_request("DELETE", "vector", f"/api/vectors/projects/{project_id}/collection")

    # Graph Service Methods
    async def extract_entities(self, project_id: str, document: Dict) -> Dict:
        """Extract entities and create graph for a single document content"""
        # document should contain: { document_content, filename, document_id }
        return await self._make_request(
            "POST", "graph", f"/api/graphs/projects/{project_id}/extract", json=document
        )

    async def get_project_graph(self, project_id: str) -> Dict:
        """Get project graph data"""
        return await self._make_request("GET", "graph", f"/api/graphs/projects/{project_id}/graph")

    async def delete_project_graph(self, project_id: str) -> Dict:
        """Delete project graph data"""
        return await self._make_request("DELETE", "graph", f"/api/graphs/projects/{project_id}/graph")

    async def get_graph_stats(self, project_id: str) -> Dict:
        """Get graph statistics"""
        return await self._make_request("GET", "graph", f"/api/graphs/projects/{project_id}/stats")

    async def get_infrastructure_topology(self, project_id: str, include_technologies: bool = True) -> Dict:
        """Get simplified infrastructure topology graph"""
        suffix = "?include_technologies=true" if include_technologies else "?include_technologies=false"
        return await self._make_request("GET", "graph", f"/api/graphs/projects/{project_id}/topology{suffix}")

    async def delete_project_graph(self, project_id: str) -> Dict:
        """Delete all graph data for a project"""
        return await self._make_request("DELETE", "graph", f"/api/graphs/projects/{project_id}/graph")

    async def search_graph_nodes(self, project_id: str, query: str, node_type: Optional[str] = None, limit: int = 20) -> Dict:
        """Search graph nodes by name substring via graph-service."""
        params = {"q": query, "limit": limit}
        if node_type:
            params["node_type"] = node_type
        return await self._make_request("GET", "graph", f"/api/graphs/projects/{project_id}/nodes/search", params=params)

    async def search_graph_relationships(self, project_id: str, rel_type: Optional[str] = None, limit: int = 50) -> Dict:
        """Search relationships within a project by type via graph-service."""
        params = {"limit": limit}
        if rel_type:
            params["rel_type"] = rel_type
        return await self._make_request("GET", "graph", f"/api/graphs/projects/{project_id}/relationships/search", params=params)

    async def get_graph_neighborhood(
        self,
        project_id: str,
        node_id: str,
        *,
        depth: int = 1,
        direction: str = "both",
        rel_types: Optional[list[str]] = None,
        limit: int = 200,
    ) -> Dict:
        """Retrieve a neighborhood subgraph around a node via graph-service."""
        params = {"node_id": node_id, "depth": depth, "direction": direction, "limit": limit}
        if rel_types:
            params["rel_types"] = ",".join(rel_types)
        return await self._make_request("GET", "graph", f"/api/graphs/projects/{project_id}/neighborhood", params=params)

    # LLM Service Methods
    async def get_llm_providers(self) -> Dict:
        """Get available LLM providers"""
        return await self._make_request("GET", "llm", "/api/llm/providers")

    async def process_llm_request(self, process_type: str, project_id: str, input_data: Dict) -> Dict:
        """Process LLM request"""
        return await self._make_request("POST", "llm", "/api/llm/process",
                                      json={"process_type": process_type, "project_id": project_id, "input_data": input_data})

    async def get_llm_configuration(self, project_id: str, process_type: str) -> Dict:
        """Get LLM configuration for process"""
        return await self._make_request("GET", "llm", f"/api/llm/{process_type}/{project_id}")
    
    # LLM Configuration Management Methods
    async def get_llm_configurations(self, project_id: str) -> Dict:
        """Get all LLM configurations for a project"""
        return await self._make_request("GET", "llm", f"/api/llm/configurations?project_id={project_id}")
    
    async def create_llm_configuration(self, config_data: Dict) -> Dict:
        """Create a new LLM configuration"""
        return await self._make_request("POST", "llm", "/api/llm/configurations", json=config_data)
    
    async def update_llm_configuration(self, config_id: int, config_data: Dict) -> Dict:
        """Update an existing LLM configuration"""
        return await self._make_request("PUT", "llm", f"/api/llm/configurations/{config_id}", json=config_data)
    
    async def delete_llm_configuration(self, config_id: int) -> Dict:
        """Delete an LLM configuration"""
        return await self._make_request("DELETE", "llm", f"/api/llm/configurations/{config_id}")
    
    async def get_llm_models(self, provider: str) -> Dict:
        """Get available models for a provider"""
        return await self._make_request("GET", "llm", f"/api/llm/models/{provider}")
    
    async def test_llm_configuration(self, test_data: Dict) -> Dict:
        """Test an LLM configuration"""
        return await self._make_request("POST", "llm", "/api/llm/test-llm-config", json=test_data)

    # AI Agent Service Methods
    async def list_agents(self) -> Dict:
        """List available AI agents"""
        return await self._make_request("GET", "ai_agent", "/api/agents/list")

    async def list_crews(self) -> Dict:
        """List available AI crews"""
        return await self._make_request("GET", "ai_agent", "/api/agents/crews")

    async def start_agent_task(self, agent_id: str, task_data: Dict) -> Dict:
        """Start agent task"""
        return await self._make_request("POST", "ai_agent", f"/api/agents/{agent_id}/tasks", json=task_data)

    async def start_crew_workflow(self, crew_id: str, workflow_data: Dict) -> Dict:
        """Start crew workflow"""
        return await self._make_request("POST", "ai_agent", f"/api/agents/crews/{crew_id}/workflows", json=workflow_data)

    async def get_task_status(self, job_id: str) -> Dict:
        """Get agent task status"""
        return await self._make_request("GET", "ai_agent", f"/api/agents/tasks/{job_id}/status")

    # Storage Service Methods
    async def upload_files(self, project_id: str, category: str, files: List) -> Dict:
        """Upload files to storage"""
        file_data = {}
        for i, file in enumerate(files):
            file_data[f'file_{i}'] = file
        return await self._make_request("POST", "storage", f"/api/storage/projects/{project_id}/upload/{category}", files=file_data)

    async def upload_bytes(self, project_id: str, category: str, filename: str, data_bytes: bytes, content_type: str = "application/octet-stream") -> Dict:
        """Upload raw bytes to storage as a file."""
        files = {"files": (filename, data_bytes, content_type)}
        # Note: storage upload endpoint expects multipart under /upload/{category}
        return await self._make_request("POST", "storage", f"/api/storage/projects/{project_id}/upload/{category}", files=files)

    async def download_file(self, project_id: str, category: str, filename: str) -> Dict:
        """Download file from storage"""
        return await self._make_request("GET", "storage", f"/api/storage/projects/{project_id}/download/{category}/{filename}")

    async def list_project_files(self, project_id: str, category: str, suffix_filter: Optional[str] = None) -> Dict:
        """List files in project storage"""
        params = {}
        if suffix_filter:
            params["suffix_filter"] = suffix_filter
        return await self._make_request("GET", "storage", f"/api/storage/projects/{project_id}/files/{category}", params=params)

    async def get_storage_stats(self, project_id: Optional[str] = None) -> Dict:
        """Get storage statistics"""
        if project_id:
            return await self._make_request("GET", "storage", f"/api/storage/projects/{project_id}/stats")
        return await self._make_request("GET", "storage", "/api/storage/stats/global")

    # Reporting Service Helpers
    async def reporting_convert_markdown(self, project_id: str, markdown_content: str, base: str, target: str) -> Dict[str, Any]:
        """Convert markdown to target format (pdf|docx) via Reporting Service.
        Returns raw bytes if the reporting service streams content, or a dict with content.
        """
        try:
            # Prefer a generic conversion endpoint if present
            payload = {"markdown_content": markdown_content, "project_id": project_id, "filename": base}
            path = f"/api/reporting/convert/{target}"
            resp = await self.client.post(f"{self.services['reporting']}{path}", json=payload, headers={"Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"})
            # If response is not JSON, return bytes
            ctype = resp.headers.get("content-type", "")
            if not ctype.startswith("application/json"):
                return {"content": resp.content, "content_type": ctype or ("application/pdf" if target=="pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
            return resp.json()
        except Exception as e:
            logger.error(f"Reporting convert markdown failed: {e}")
            raise

    # WebSocket Service Methods
    async def get_websocket_stats(self) -> Dict:
        """Get WebSocket connection statistics"""
        return await self._make_request("GET", "websocket", "/stats")

    async def broadcast_message(self, channel: str, message: Dict) -> Dict:
        """Broadcast message via WebSocket"""
        return await self._make_request("POST", "websocket", "/broadcast",
                                      json={"channel": channel, "message": message})

    async def get_uploaded_files(self, project_id: str) -> Dict:
        """Get uploaded files for project"""
        headers = {"Authorization": f"Bearer {await self._get_admin_token()}"}
        logger.info(f"ServiceClient: GET files for project {project_id}")
        logger.info(f"ServiceClient: Using URL http://localhost:8002/projects/{project_id}/files")
        logger.info(f"ServiceClient: Headers: {headers}")
        
        try:
            result = await self._make_request("GET", "project", f"/projects/{project_id}/files", headers=headers)
            logger.info(f"ServiceClient: Success getting files for project {project_id}")
            return result
        except Exception as e:
            logger.error(f"ServiceClient: Failed getting files for project {project_id}: {e}")
            raise

    # Document-specific deletion methods
    async def delete_document_storage(self, project_id: str, filename: str) -> Dict:
        """Delete document and related files from storage"""
        return await self._make_request("DELETE", "storage", f"/api/storage/projects/{project_id}/documents/{filename}")

    async def delete_document_vectors(self, project_id: str, filename: str) -> Dict:
        """Delete document vectors from vector service"""
        return await self._make_request("DELETE", "vector", f"/api/vectors/projects/{project_id}/documents/{filename}")

    async def delete_document_graph(self, project_id: str, filename: str) -> Dict:
        """Delete document graph data from graph service"""
        return await self._make_request("DELETE", "graph", f"/api/graphs/projects/{project_id}/documents/{filename}")

    # Document Generation via AI Agent Service
    async def generate_document(self, project_id: str, payload: Dict[str, Any]) -> Dict:
        """Generate a document using AI Agent orchestration"""
        try:
            return await self._make_request(
                "POST",
                "ai_agent",
                f"/api/agents/projects/{project_id}/documents/generate",
                json=payload,
            )
        except Exception as e:
            logger.error(f"ServiceClient: Document generation failed for project {project_id}: {e}")
            raise

    # Document/Template Management Methods - Project Service
    async def get_project_deliverables(self, project_id: str) -> List[Dict]:
        """Get project-specific document templates"""
        headers = {"Authorization": f"Bearer {await self._get_admin_token()}"}
        return await self._make_request("GET", "project", f"/projects/{project_id}/deliverables", headers=headers)

    async def create_project_deliverable(self, project_id: str, deliverable: Dict) -> Dict:
        """Create new project deliverable template"""
        headers = {"Authorization": f"Bearer {await self._get_admin_token()}"}
        return await self._make_request("POST", "project", f"/projects/{project_id}/deliverables", 
                                       json=deliverable, headers=headers)

    async def get_global_templates(self) -> List[Dict]:
        """Get global document templates"""
        headers = {"Authorization": f"Bearer {await self._get_admin_token()}"}
        return await self._make_request("GET", "project", "/templates/global", headers=headers)

    async def create_global_template(self, template: Dict) -> Dict:
        """Create new global template"""
        headers = {"Authorization": f"Bearer {await self._get_admin_token()}"}
        return await self._make_request("POST", "project", "/templates/global", json=template, headers=headers)

    async def get_generation_requests(self, project_id: str) -> List[Dict]:
        """Get document generation requests for project"""
        headers = {"Authorization": f"Bearer {await self._get_admin_token()}"}
        return await self._make_request("GET", "project", f"/projects/{project_id}/generation-requests", headers=headers)

    async def create_generation_request(self, project_id: str, request: Dict) -> Dict:
        """Create new document generation request"""
        headers = {"Authorization": f"Bearer {await self._get_admin_token()}"}
        return await self._make_request("POST", "project", f"/projects/{project_id}/generation-requests", 
                                       json=request, headers=headers)

    async def get_template_usage(self, project_id: str) -> Dict:
        """Get template usage statistics for project"""
        headers = {"Authorization": f"Bearer {await self._get_admin_token()}"}
        return await self._make_request("GET", "project", f"/projects/{project_id}/template-usage", headers=headers)

    async def get_generation_history(self, project_id: str) -> List[Dict]:
        """Get document generation history for project"""
        headers = {"Authorization": f"Bearer {await self._get_admin_token()}"}
        return await self._make_request("GET", "project", f"/projects/{project_id}/generation-history", headers=headers)

    # LLM Process Config Methods - Project Service owns storage of these
    async def get_llm_process_configs(self, project_id: str) -> Dict:
        """Get LLM processing configurations for project"""
        headers = {"Authorization": f"Bearer {await self._get_admin_token()}"}
        return await self._make_request("GET", "project", f"/projects/{project_id}/llm-process-configs", headers=headers)

    async def update_llm_process_configs(self, project_id: str, configs: Dict) -> Dict:
        """Update LLM processing configurations for project"""
        headers = {"Authorization": f"Bearer {await self._get_admin_token()}"}
        return await self._make_request("POST", "project", f"/projects/{project_id}/llm-process-configs", json=configs, headers=headers)

    async def test_llm_process_config(self, project_id: str, config_key: str, test_data: Dict) -> Dict:
        """Test LLM process configuration"""
        headers = {"Authorization": f"Bearer {await self._get_admin_token()}"}
        return await self._make_request("POST", "project", f"/projects/{project_id}/process-llm-config/{config_key}/test", json=test_data, headers=headers)

    async def get_ollama_models(self) -> Dict:
        """Get available Ollama models"""
        return await self._make_request("GET", "llm", "/api/llm/ollama/models")

    # Service Health Methods
    async def check_service_health(self, service: str) -> Dict:
        """Check health of specific service"""
        return await self._make_request("GET", service, "/health")

    async def check_all_services_health(self) -> Dict[str, Dict]:
        """Check health of all services"""
        health_results = {}
        for service_name in self.services.keys():
            try:
                health_results[service_name] = await self.check_service_health(service_name)
            except Exception as e:
                health_results[service_name] = {"status": "error", "error": str(e)}
        return health_results

# Global service client instance
_service_client: Optional[ServiceClient] = None

async def get_service_client() -> ServiceClient:
    """Get global service client instance"""
    global _service_client
    if _service_client is None:
        _service_client = ServiceClient()
    return _service_client

async def close_service_client():
    """Close global service client"""
    global _service_client
    if _service_client:
        await _service_client.close()
        _service_client = None
