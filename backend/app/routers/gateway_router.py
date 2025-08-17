#!/usr/bin/env python3
"""
API Gateway Router - Routes requests to microservices
Replaces business logic routers with HTTP client calls to extracted services
"""

import os
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Query, Request, BackgroundTasks, Body
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from app.core.service_client import get_service_client

logger = logging.getLogger("api-gateway.router")

# Create router
router = APIRouter(tags=["api-gateway"])

# =====================================================================================
# HEALTH CHECK ENDPOINTS
# =====================================================================================

@router.get("/api/health", summary="API Gateway Health Check")
async def api_health_check():
    """Gateway health check endpoint for frontend"""
    try:
        client = await get_service_client()
        health_results = await client.check_all_services_health()
        
        # Determine overall health
        all_healthy = all(
            service.get("status") in ["healthy", "up", "present"] 
            for service in health_results.values()
        )
        
        return {
            "status": "healthy" if all_healthy else "degraded",
            "services": health_results,
            "gateway": "operational",
            "timestamp": "2025-08-16T11:52:20.164664"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "gateway": "operational",
            "timestamp": "2025-08-16T11:52:20.164664"
        }

# Pydantic models for requests
class ProjectCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    client_name: str
    client_contact: Optional[str] = None
    # Optional LLM configuration during creation
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_api_key_id: Optional[str] = None
    llm_temperature: Optional[str] = "0.1"
    llm_max_tokens: Optional[str] = "4000"

class QueryRequest(BaseModel):
    query: str
    limit: Optional[int] = 10

class DocumentProcessRequest(BaseModel):
    files: Optional[List[str]] = None
    reprocess: bool = False

class AgentTaskRequest(BaseModel):
    input_data: Dict[str, Any]
    parameters: Optional[Dict[str, Any]] = None

class CrewWorkflowRequest(BaseModel):
    input_data: Dict[str, Any]
    parameters: Optional[Dict[str, Any]] = None

# =====================================================================================
# PROJECT MANAGEMENT ENDPOINTS - Route to Project Service (8002)
# =====================================================================================

@router.get("/api/projects/", summary="List all projects")
@router.get("/api/projects", summary="List all projects (no slash)", include_in_schema=False)
async def list_projects(include_stats: bool = Query(False)):
    """List all projects via Project Service"""
    try:
        client = await get_service_client()
        return await client.list_projects(include_stats=include_stats)
    except Exception as e:
        logger.error(f"List projects failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list projects: {str(e)}")

@router.get("/api/projects/{project_id}", summary="Get project by ID")
async def get_project(project_id: str):
    """Get project by ID via Project Service"""
    try:
        client = await get_service_client()
        return await client.get_project(project_id)
    except Exception as e:
        logger.error(f"Get project {project_id} failed: {e}")
        raise HTTPException(status_code=404, detail=f"Project not found: {str(e)}")

@router.put("/api/projects/{project_id}", summary="Update a project")
async def update_project(project_id: str, project_data: dict = Body(...)):
    """Update project via Project Service"""
    try:
        client = await get_service_client()
        return await client.update_project(project_id, project_data)
    except Exception as e:
        logger.error(f"Update project failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update project: {str(e)}")

@router.post("/api/projects/", summary="Create new project")
@router.post("/api/projects", summary="Create new project (no slash)", include_in_schema=False)
async def create_project(request: ProjectCreateRequest):
    """Create new project via Project Service with gateway-side validation and downstream error propagation"""
    # Validate required fields before proxying
    errors = []
    if not request.name or not str(request.name).strip():
        errors.append({"loc": ["body", "name"], "msg": "Field required", "type": "missing"})
    if not request.client_name or not str(request.client_name).strip():
        errors.append({"loc": ["body", "client_name"], "msg": "Field required", "type": "missing"})
    if errors:
        raise HTTPException(status_code=422, detail=errors)

    try:
        client = await get_service_client()
        return await client.create_project(request.dict())
    except Exception as e:
        # Propagate 4xx from downstream when possible
        try:
            import httpx
            if isinstance(e, httpx.HTTPStatusError):
                status_code = e.response.status_code
                try:
                    detail = e.response.json()
                except Exception:
                    detail = e.response.text
                logger.error(f"Create project failed downstream {status_code}: {detail}")
                raise HTTPException(status_code=status_code, detail=detail)
        except Exception:
            pass
        logger.error(f"Create project failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create project: {str(e)}")

@router.delete("/api/projects/{project_id}", summary="Delete project")
async def delete_project(project_id: str):
    """Delete project via Project Service"""
    try:
        client = await get_service_client()
        return await client.delete_project(project_id)
    except Exception as e:
        logger.error(f"Delete project {project_id} failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete project: {str(e)}")

@router.get("/api/projects/stats", summary="Get project statistics")
async def get_projects_stats():
    """Get project statistics via Project Service"""
    try:
        client = await get_service_client()
        projects = await client.list_projects(include_stats=True)
        
        # Calculate stats from project list
        total_projects = len(projects)
        status_counts = {}
        for project in projects:
            status = project.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return {
            "total_projects": total_projects,
            "status_breakdown": status_counts,
            "active_projects": status_counts.get("running", 0),
            "completed_projects": status_counts.get("completed", 0),
            "pending_projects": status_counts.get("initiated", 0)
        }
    except Exception as e:
        logger.error(f"Get project stats failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get project stats: {str(e)}")

# =====================================================================================
# USER MANAGEMENT ENDPOINTS - Route to Project Service (8002)
# =====================================================================================

@router.get("/api/users/enhanced", summary="Get enhanced user information")
async def get_users_enhanced(skip: int = 0, limit: int = 100):
    """Get enhanced user information via Project Service"""
    try:
        client = await get_service_client()
        headers = {"Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"}
        return await client._make_request("GET", "project", f"/users/enhanced?skip={skip}&limit={limit}", headers=headers)
    except Exception as e:
        logger.error(f"Get users enhanced failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get enhanced user information: {str(e)}")

# =====================================================================================
# DOCUMENT PROCESSING ENDPOINTS - Route to Document Service (8004)
# =====================================================================================

@router.post("/upload/{project_id}", summary="Upload files (legacy endpoint)")
async def upload_files_legacy(project_id: str, files: List[UploadFile] = File(...)):
    """Legacy upload endpoint - routes to Document Service with better error propagation"""
    try:
        client = await get_service_client()
        return await client.upload_documents(project_id, files)
    except Exception as e:
        # Propagate downstream status codes when possible
        try:
            import httpx
            if isinstance(e, httpx.HTTPStatusError):
                status_code = e.response.status_code
                try:
                    detail = e.response.json()
                except Exception:
                    detail = e.response.text
                logger.error(f"Legacy upload failed downstream {status_code}: {detail}")
                raise HTTPException(status_code=status_code, detail=detail)
        except Exception:
            pass
        logger.error(f"Legacy upload failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.post("/api/projects/{project_id}/upload", summary="Upload documents")
async def upload_documents(
    project_id: str,
    files: List[UploadFile] = File(None),
    files_alt: List[UploadFile] = File(None, alias="files[]")
):
    """Upload documents via Document Service with better error propagation"""
    try:
        # Accept both 'files' and 'files[]' field names
        incoming_files: List[UploadFile] = []
        if files:
            incoming_files.extend(files)
        if files_alt:
            incoming_files.extend(files_alt)
        if not incoming_files:
            raise HTTPException(status_code=422, detail="No files provided. Use 'files' or 'files[]' multipart fields.")

        client = await get_service_client()
        return await client.upload_documents(project_id, incoming_files)
    except Exception as e:
        # Propagate downstream status codes when possible
        try:
            import httpx
            if isinstance(e, httpx.HTTPStatusError):
                status_code = e.response.status_code
                try:
                    detail = e.response.json()
                except Exception:
                    detail = e.response.text
                logger.error(f"Upload failed downstream for {project_id} {status_code}: {detail}")
                raise HTTPException(status_code=status_code, detail=detail)
        except Exception:
            pass
        logger.error(f"Upload failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.post("/api/projects/{project_id}/process-all", summary="Process all uploaded documents")
async def process_all_documents(project_id: str):
    """Process all uploaded documents via Document Service"""
    try:
        client = await get_service_client()
        return await client.process_documents(project_id)
    except Exception as e:
        logger.error(f"Process all failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Process all failed: {str(e)}")

@router.post("/api/projects/{project_id}/process-selected", summary="Process selected documents")
async def process_selected_documents(project_id: str, request: DocumentProcessRequest):
    """Process selected documents via Document Service"""
    try:
        client = await get_service_client()
        return await client.process_documents(project_id, request.files)
    except Exception as e:
        logger.error(f"Process selected failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Process selected failed: {str(e)}")

# =====================================================================================
# PROJECT FILE MANAGEMENT ENDPOINTS - Route to Document/Storage Services
# =====================================================================================

@router.get("/api/projects/{project_id}/uploads", summary="List uploaded files (legacy endpoint)")
async def list_project_uploads_legacy(project_id: str):
    """Legacy endpoint for frontend compatibility - routes to uploaded-files"""
    try:
        client = await get_service_client()
        return await client.get_uploaded_files(project_id)
    except Exception as e:
        logger.error(f"List uploaded files failed for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list uploaded files: {str(e)}")

@router.get("/api/projects/{project_id}/uploaded-files", summary="List uploaded files")
async def list_uploaded_files(project_id: str):
    """List uploaded files via Storage Service"""
    try:
        client = await get_service_client()
        return await client.list_project_files(project_id, "uploads_raw")
    except Exception as e:
        logger.error(f"List files failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")

# =====================================================================================
# KNOWLEDGE BASE QUERY ENDPOINTS - Route to Vector/Graph Services
# =====================================================================================

@router.post("/api/projects/{project_id}/query", summary="Query project knowledge base")
async def query_project_knowledge(project_id: str, query_request: QueryRequest):
    """Query project knowledge base via Vector Service"""
    try:
        client = await get_service_client()
        return await client.vector_search(project_id, query_request.query, query_request.limit)
    except Exception as e:
        logger.error(f"Knowledge query failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

@router.get("/api/projects/{project_id}/graph", summary="Get project graph")
async def get_project_graph(project_id: str, type: Optional[str] = None):
    """Get project graph via Graph Service"""
    try:
        client = await get_service_client()
        return await client.get_project_graph(project_id)
    except Exception as e:
        logger.error(f"Get graph failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get graph: {str(e)}")

@router.post("/api/projects/{project_id}/clear-data", summary="Clear project data")
async def clear_project_data(project_id: str):
    """Clear project embeddings and graph data via Vector/Graph Services"""
    try:
        client = await get_service_client()
        
        # Clear vector data
        try:
            vector_result = await client._make_request("DELETE", "vector", f"/api/vectors/projects/{project_id}/collection")
        except:
            vector_result = {"status": "error"}
        
        # Clear graph data  
        try:
            graph_result = await client._make_request("DELETE", "graph", f"/api/graphs/projects/{project_id}/graph")
        except:
            graph_result = {"status": "error"}
        
        return {
            "message": "Project data cleared successfully",
            "project_id": project_id,
            "vector_cleared": vector_result.get("status") == "success",
            "graph_cleared": graph_result.get("status") == "success"
        }
    except Exception as e:
        logger.error(f"Clear data failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear data: {str(e)}")

# =====================================================================================
# DOCUMENT/TEMPLATE MANAGEMENT ENDPOINTS - Route to Project Service
# =====================================================================================

@router.get("/api/projects/{project_id}/deliverables", summary="Get project deliverables")
async def get_project_deliverables(project_id: str):
    """Get project-specific document templates"""
    try:
        client = await get_service_client()
        return await client.get_project_deliverables(project_id)
    except Exception as e:
        logger.error(f"Get project deliverables failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get project deliverables: {str(e)}")

@router.post("/api/projects/{project_id}/deliverables", summary="Create project deliverable")
async def create_project_deliverable(project_id: str, deliverable: dict):
    """Create new project deliverable template"""
    try:
        client = await get_service_client()
        return await client.create_project_deliverable(project_id, deliverable)
    except Exception as e:
        logger.error(f"Create project deliverable failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create project deliverable: {str(e)}")

@router.get("/api/templates/global", summary="Get global templates")
async def get_global_templates():
    """Get global document templates"""
    try:
        client = await get_service_client()
        return await client.get_global_templates()
    except Exception as e:
        logger.error(f"Get global templates failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get global templates: {str(e)}")

@router.post("/api/templates/global", summary="Create global template")
async def create_global_template(template: dict):
    """Create new global template"""
    try:
        client = await get_service_client()
        return await client.create_global_template(template)
    except Exception as e:
        logger.error(f"Create global template failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create global template: {str(e)}")

@router.get("/api/projects/{project_id}/generation-requests", summary="Get project generation requests")
async def get_generation_requests(project_id: str):
    """Get document generation requests for project"""
    try:
        client = await get_service_client()
        return await client.get_generation_requests(project_id)
    except Exception as e:
        logger.error(f"Get generation requests failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get generation requests: {str(e)}")

@router.post("/api/projects/{project_id}/generation-requests", summary="Create generation request")
async def create_generation_request(project_id: str, request: dict):
    """Create new document generation request"""
    try:
        client = await get_service_client()
        return await client.create_generation_request(project_id, request)
    except Exception as e:
        logger.error(f"Create generation request failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create generation request: {str(e)}")

@router.get("/api/projects/{project_id}/template-usage", summary="Get template usage stats")
async def get_template_usage(project_id: str):
    """Get template usage statistics for project"""
    try:
        client = await get_service_client()
        return await client.get_template_usage(project_id)
    except Exception as e:
        logger.error(f"Get template usage failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get template usage: {str(e)}")

@router.get("/api/projects/{project_id}/generation-history", summary="Get generation history")
async def get_generation_history(project_id: str):
    """Get document generation history for project"""
    try:
        client = await get_service_client()
        return await client.get_generation_history(project_id)
    except Exception as e:
        logger.error(f"Get generation history failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get generation history: {str(e)}")

# =====================================================================================
# LLM CONFIGURATION ENDPOINTS - Process configs route to Project Service
# =====================================================================================

@router.get("/api/projects/{project_id}/llm-process-configs", summary="Get LLM process configurations")
async def get_llm_process_configs(project_id: str):
    """Get LLM processing configurations for project"""
    try:
        client = await get_service_client()
        return await client.get_llm_process_configs(project_id)
    except Exception as e:
        logger.error(f"Get LLM process configs failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get LLM process configs: {str(e)}")

@router.post("/api/projects/{project_id}/llm-process-configs", summary="Update LLM process configurations")
async def update_llm_process_configs(project_id: str, configs: dict):
    """Update LLM processing configurations for project"""
    try:
        client = await get_service_client()
        return await client.update_llm_process_configs(project_id, configs)
    except Exception as e:
        logger.error(f"Update LLM process configs failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update LLM process configs: {str(e)}")

@router.post("/api/projects/{project_id}/process-llm-config/{config_key}/test", summary="Test LLM process config")
async def test_llm_process_config(project_id: str, config_key: str, test_data: dict):
    """Test LLM process configuration"""
    try:
        client = await get_service_client()
        return await client.test_llm_process_config(project_id, config_key, test_data)
    except Exception as e:
        logger.error(f"Test LLM process config failed for {project_id}/{config_key}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to test LLM process config: {str(e)}")

@router.get("/api/ollama/models", summary="Get Ollama models")
async def get_ollama_models():
    """Get available Ollama models"""
    try:
        client = await get_service_client()
        return await client.get_ollama_models()
    except Exception as e:
        logger.error(f"Get Ollama models failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get Ollama models: {str(e)}")

# =====================================================================================
# AI AGENT ENDPOINTS - Route to AI Agent Service (8008)
# =====================================================================================

@router.get("/api/agents", summary="List available AI agents")
async def list_agents():
    """List available AI agents via AI Agent Service"""
    try:
        client = await get_service_client()
        return await client.list_agents()
    except Exception as e:
        logger.error(f"List agents failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list agents: {str(e)}")

@router.get("/api/crews", summary="List available AI crews")
async def list_crews():
    """List available AI crews via AI Agent Service"""
    try:
        client = await get_service_client()
        # Correct endpoint: /api/agents/crews not /api/crews/list
        return await client._make_request("GET", "ai_agent", "/api/agents/crews")
    except Exception as e:
        logger.error(f"List crews failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list crews: {str(e)}")

@router.post("/api/agents/{agent_id}/tasks", summary="Start agent task")
async def start_agent_task(agent_id: str, request: AgentTaskRequest):
    """Start agent task via AI Agent Service"""
    try:
        client = await get_service_client()
        return await client.start_agent_task(agent_id, request.dict())
    except Exception as e:
        logger.error(f"Start agent task failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start agent task: {str(e)}")

@router.post("/api/crews/{crew_id}/workflows", summary="Start crew workflow")
async def start_crew_workflow(crew_id: str, request: CrewWorkflowRequest):
    """Start crew workflow via AI Agent Service"""
    try:
        client = await get_service_client()
        return await client.start_crew_workflow(crew_id, request.dict())
    except Exception as e:
        logger.error(f"Start crew workflow failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start crew workflow: {str(e)}")

# =====================================================================================
# LLM CONFIGURATION ENDPOINTS - Route to LLM Service (8007)
# =====================================================================================

@router.get("/api/llm/providers", summary="Get LLM providers")
async def get_llm_providers():
    """Get available LLM providers via LLM Service"""
    try:
        client = await get_service_client()
        return await client.get_llm_providers()
    except Exception as e:
        logger.error(f"Get LLM providers failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get LLM providers: {str(e)}")

# LLM test and models passthrough
@router.get("/api/llm/test-llm-config", summary="Test LLM configuration connectivity")
async def test_llm_config(config_id: Optional[str] = Query(None), test_query: Optional[str] = Query(None)):
    try:
        # Route to backend llm_router mounted under /api/llm
        import requests
        params = {}
        if config_id:
            params['config_id'] = config_id
        if test_query:
            params['test_query'] = test_query
        resp = requests.get(f"http://localhost:8000/api/llm/test-llm-config", params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"LLM test config failed via gateway passthrough: {e}")
        raise HTTPException(status_code=500, detail=f"LLM test failed: {str(e)}")

@router.get("/api/llm/configurations", summary="Get LLM configurations")
async def get_llm_configurations():
    """Get LLM configurations via Project Service"""
    try:
        client = await get_service_client()
        return await client._make_request("GET", "project", "/llm-configurations")
    except Exception as e:
        logger.error(f"Get LLM configurations failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get LLM configurations: {str(e)}")

@router.post("/api/llm/configurations", summary="Create LLM configuration")
async def create_llm_configuration(request: dict = Body(...)):
    """Create LLM configuration via Project Service"""
    try:
        client = await get_service_client()
        return await client.create_llm_configuration(request)
    except Exception as e:
        logger.error(f"Create LLM configuration failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create LLM configuration: {str(e)}")

# =====================================================================================
# STORAGE ENDPOINTS - Route to Storage Service (8010)
# =====================================================================================

@router.get("/api/storage/projects/{project_id}/files/{category}", summary="List project files")
async def list_project_files_api(project_id: str, category: str, suffix_filter: Optional[str] = Query(None)):
    """List project files via Storage Service"""
    try:
        client = await get_service_client()
        return await client.list_project_files(project_id, category, suffix_filter)
    except Exception as e:
        logger.error(f"List project files failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")

@router.get("/api/storage/projects/{project_id}/stats", summary="Get project storage stats")
async def get_project_storage_stats(project_id: str):
    """Get project storage statistics via Storage Service"""
    try:
        client = await get_service_client()
        return await client.get_storage_stats(project_id)
    except Exception as e:
        logger.error(f"Get storage stats failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get storage stats: {str(e)}")

# =====================================================================================
# SERVICE HEALTH ENDPOINTS - Check all microservices
# =====================================================================================

@router.get("/api/services/health", summary="Check all microservices health")
async def check_all_services_health():
    """Check health of all microservices"""
    try:
        client = await get_service_client()
        return await client.check_all_services_health()
    except Exception as e:
        logger.error(f"Service health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@router.get("/api/services/{service}/health", summary="Check specific service health")
async def check_service_health(service: str):
    """Check health of specific microservice"""
    try:
        client = await get_service_client()
        return await client.check_service_health(service)
    except Exception as e:
        logger.error(f"Service {service} health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed for {service}: {str(e)}")

# =====================================================================================
# GATEWAY STATUS ENDPOINT
# =====================================================================================

@router.get("/api/gateway/debug", summary="Debug service client token")
async def debug_service_client():
    """Debug endpoint to check service client token"""
    try:
        client = await get_service_client()
        token = await client._get_admin_token()
        return {
            "token_value": token,
            "env_var": os.getenv("SERVICE_AUTH_TOKEN", "NOT_SET"),
            "token_matches": token == os.getenv("SERVICE_AUTH_TOKEN", "service-backend-token")
        }
    except Exception as e:
        logger.error(f"Debug failed: {e}")
        raise HTTPException(status_code=500, detail=f"Debug failed: {str(e)}")

@router.get("/api/gateway/status", summary="API Gateway status")
async def gateway_status():
    """Get API Gateway status and service connectivity"""
    try:
        client = await get_service_client()
        service_health = await client.check_all_services_health()
        
        healthy_services = sum(1 for h in service_health.values() if h.get("status") == "healthy")
        total_services = len(service_health)
        
        return {
            "gateway_status": "healthy",
            "version": "2.0.0",
            "role": "API Gateway - Routes to 7 microservices",
            "services_connected": f"{healthy_services}/{total_services}",
            "service_endpoints": client.services,
            "service_health": service_health,
            "timestamp": logger.__dict__.get('timestamp', 'N/A')
        }
    except Exception as e:
        logger.error(f"Gateway status failed: {e}")
        return {
            "gateway_status": "degraded",
            "version": "2.0.0", 
            "role": "API Gateway - Routes to 7 microservices",
            "error": str(e),
            "timestamp": logger.__dict__.get('timestamp', 'N/A')
        }
