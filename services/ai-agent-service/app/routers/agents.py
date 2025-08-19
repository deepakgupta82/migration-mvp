#!/usr/bin/env python3
"""
AI Agent Router - API endpoints for AI agent orchestration
Handles single agents and multi-agent crew workflows
"""

from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
import logging

from ..core.agent_processor import AIAgentProcessor
import os
import uuid
import httpx
from datetime import datetime

logger = logging.getLogger("ai-agent-service")
router = APIRouter()

# Initialize processor
agent_processor = AIAgentProcessor()

# Pydantic models
class AgentTaskRequest(BaseModel):
    input_data: Dict[str, Any] = Field(..., description="Input data for the agent")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Additional parameters")
    priority: Optional[str] = Field("normal", description="Task priority (low, normal, high)")

class CrewWorkflowRequest(BaseModel):
    input_data: Dict[str, Any] = Field(..., description="Input data for the crew workflow")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Workflow parameters")
    priority: Optional[str] = Field("normal", description="Workflow priority")

class HealthResponse(BaseModel):
    service: str
    status: str
    dependencies: Dict[str, bool]
    active_jobs: int
    port: int
    version: str

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    try:
        dependencies = await agent_processor.verify_dependencies()
        active_jobs = await agent_processor.get_active_jobs()
        
        return HealthResponse(
            service="ai-agent-orchestration",
            status="healthy" if all(dependencies.values()) else "degraded",
            dependencies=dependencies,
            active_jobs=active_jobs.get("total_active", 0),
            port=8008,
            version="1.0.0"
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            service="ai-agent-orchestration",
            status="unhealthy",
            dependencies={},
            active_jobs=0,
            port=8008,
            version="1.0.0"
        )

# ---------------- Document Generation via microservices ----------------
class GenerateDocumentRequest(BaseModel):
    template_id: Optional[str] = None
    name: Optional[str] = "Project Summary"
    description: Optional[str] = None
    format: Optional[str] = "markdown"  # markdown | pdf | docx
    output_type: Optional[str] = "markdown"
    request_id: Optional[str] = None

class GenerateDocumentResponse(BaseModel):
    success: bool
    project_id: str
    name: str
    markdown_filename: str
    download_urls: Dict[str, str]
    content_preview: str

def _svc_headers(corr_id: Optional[str] = None) -> Dict[str, str]:
    headers = {"Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}", "Content-Type": "application/json"}
    if corr_id:
        headers["X-Correlation-ID"] = corr_id
    return headers

def _slugify(name: str) -> str:
    safe = "".join(c for c in (name or "document") if c.isalnum() or c in (" ", "-", "_")).strip()
    return safe.replace(" ", "_").lower() or f"document_{uuid.uuid4().hex[:8]}"

@router.post("/projects/{project_id}/documents/generate", response_model=GenerateDocumentResponse)
async def generate_document(project_id: str, request: GenerateDocumentRequest):
    """Generate a document using Project templates, LLM service, and store via Storage service."""
    corr_id = str(uuid.uuid4())
    svc = {
        "project": os.getenv("PROJECT_SERVICE_URL", "http://localhost:8002"),
        "vector": os.getenv("VECTOR_SERVICE_URL", "http://localhost:8005"),
        "llm": os.getenv("LLM_SERVICE_URL", "http://localhost:8007"),
        "storage": os.getenv("STORAGE_SERVICE_URL", "http://localhost:8010"),
        "reporting": os.getenv("REPORTING_SERVICE_URL", "http://localhost:8003"),
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # 1) Resolve template from Project Service
            tmpl = None
            try:
                resp = await client.get(f"{svc['project']}/templates/global", headers=_svc_headers(corr_id))
                resp.raise_for_status()
                templates = resp.json() if isinstance(resp.json(), list) else resp.json().get("templates", [])
                if request.template_id:
                    tmpl = next((t for t in templates if str(t.get("id")) == str(request.template_id)), None)
                if not tmpl and request.name:
                    tmpl = next((t for t in templates if str(t.get("name","")) == str(request.name)), None)
            except Exception as e:
                logger.warning(f"Template fetch failed: {e}")

            # 2) Gather light RAG context (optional)
            context_snippets: List[str] = []
            try:
                q = (request.description or "Project context for documentation")[:200]
                sresp = await client.post(
                    f"{svc['vector']}/api/vectors/projects/{project_id}/search",
                    headers=_svc_headers(corr_id),
                    json={"query": q, "limit": 5, "include_metadata": True}
                )
                if sresp.status_code == 200:
                    data = sresp.json()
                    for r in data.get("results", [])[:5]:
                        txt = r.get("text") or r.get("content") or r.get("document", {})
                        if isinstance(txt, dict):
                            txt = txt.get("content") or ""
                        if isinstance(txt, str) and txt.strip():
                            context_snippets.append(txt.strip())
            except Exception as e:
                logger.info(f"Vector search skipped: {e}")

            # 3) Compose prompt for LLM Service
            template_guidance = (tmpl or {}).get("description") or request.description or "Generate a professional project summary."
            prompt_sections = [
                f"You are generating a document for project {project_id}.",
                f"Template Guidance: {template_guidance}",
                "Output must be valid GitHub-flavored Markdown.",
            ]
            if context_snippets:
                prompt_sections.append("Context snippets:\n" + "\n---\n".join(context_snippets))
            prompt = "\n\n".join(prompt_sections)

            # 4) Call LLM Service
            llm_req = {"process_type": "crew_documentation", "prompt": prompt, "project_id": project_id}
            llm_resp = await client.post(f"{svc['llm']}/api/llm/process", headers=_svc_headers(corr_id), json=llm_req)
            if llm_resp.status_code != 200 or not llm_resp.json().get("success"):
                raise HTTPException(status_code=500, detail=f"LLM generation failed: {llm_resp.text}")
            document_md = llm_resp.json().get("response", "")
            if not document_md.strip():
                document_md = f"# {request.name or 'Project Document'}\n\n(Empty content)"

            # 5) Store markdown via Storage Service
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            base = f"{_slugify(request.name or (tmpl or {}).get('name') or 'document')}_{project_id}_{ts}"
            md_filename = f"{base}.md"
            up_resp = await client.post(
                f"{svc['storage']}/api/storage/projects/{project_id}/upload-text/generated_reports",
                headers=_svc_headers(corr_id),
                params={"filename": md_filename},
                json={"content": document_md, "content_type": "text/markdown; charset=utf-8"}
            )
            up_resp.raise_for_status()

            download_base = f"/api/projects/{project_id}/download/{base}"
            download_urls = {"markdown": f"{download_base}.md"}

            # 6) Optional conversion: use /convert to get bytes, then upload to Storage so gateway can serve it
            target = (request.format or "markdown").lower()
            if target in ("pdf", "docx"):
                try:
                    conv_path = f"/convert/{target}"
                    conv_resp = await client.post(
                        f"{svc['reporting']}{conv_path}",
                        headers=_svc_headers(corr_id),
                        json={
                            "markdown_content": document_md,
                            "project_id": project_id,
                            "filename": base
                        }
                    )
                    conv_resp.raise_for_status()
                    content_type = "application/pdf" if target == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    bin_data = conv_resp.content

                    files = {"files": (f"{base}.{target}", bin_data, content_type)}
                    up_bin = await client.post(
                        f"{svc['storage']}/api/storage/projects/{project_id}/upload/generated_reports",
                        headers={k: v for k, v in _svc_headers(corr_id).items() if k.lower() != "content-type"},
                        files=files
                    )
                    up_bin.raise_for_status()
                    download_urls[target] = f"{download_base}.{target}"
                except Exception as e:
                    logger.warning(f"Conversion/upload skipped: {e}")

            return GenerateDocumentResponse(
                success=True,
                project_id=project_id,
                name=request.name or (tmpl or {}).get("name", "Document"),
                markdown_filename=md_filename,
                download_urls=download_urls,
                content_preview=document_md[:500] + ("..." if len(document_md) > 500 else "")
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list")
async def get_available_agents():
    """Get list of available AI agents"""
    try:
        agents = await agent_processor.get_available_agents()
        return {
            "agents": agents,
            "total_count": len(agents)
        }
    except Exception as e:
        logger.error(f"Error getting agents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/crews")
async def get_available_crews():
    """Get list of available AI crews"""
    try:
        crews = await agent_processor.get_available_crews()
        return {
            "crews": crews,
            "total_count": len(crews)
        }
    except Exception as e:
        logger.error(f"Error getting crews: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{agent_id}/tasks")
async def start_agent_task(agent_id: str, request: AgentTaskRequest):
    """Start a single agent task"""
    try:
        task_config = {
            "input_data": request.input_data,
            "parameters": request.parameters or {},
            "priority": request.priority
        }
        
        result = await agent_processor.start_agent_task(agent_id, task_config)
        
        if result.get("success"):
            return {
                "success": True,
                "job_id": result.get("job_id"),
                "agent_id": agent_id,
                "status": result.get("status"),
                "message": result.get("message"),
                "status_endpoint": f"/api/agents/tasks/{result.get('job_id')}/status"
            }
        else:
            raise HTTPException(status_code=400, detail=result.get("error"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting agent task: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/crews/{crew_id}/workflows")
async def start_crew_workflow(crew_id: str, request: CrewWorkflowRequest):
    """Start a multi-agent crew workflow"""
    try:
        workflow_config = {
            "input_data": request.input_data,
            "parameters": request.parameters or {},
            "priority": request.priority
        }
        
        result = await agent_processor.start_crew_workflow(crew_id, workflow_config)
        
        if result.get("success"):
            return {
                "success": True,
                "job_id": result.get("job_id"),
                "crew_id": crew_id,
                "status": result.get("status"),
                "estimated_time_minutes": result.get("estimated_time_minutes"),
                "message": result.get("message"),
                "status_endpoint": f"/api/agents/workflows/{result.get('job_id')}/status"
            }
        else:
            raise HTTPException(status_code=400, detail=result.get("error"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting crew workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tasks/{job_id}/status")
async def get_agent_task_status(job_id: str):
    """Get status of a running agent task"""
    try:
        status = await agent_processor.get_task_status(job_id)
        
        if status:
            return status
        else:
            raise HTTPException(status_code=404, detail="Task not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting task status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/workflows/{job_id}/status")
async def get_crew_workflow_status(job_id: str):
    """Get status of a running crew workflow"""
    try:
        status = await agent_processor.get_workflow_status(job_id)
        
        if status:
            return status
        else:
            raise HTTPException(status_code=404, detail="Workflow not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting workflow status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/jobs/active")
async def get_active_jobs():
    """Get all active AI jobs (tasks and workflows)"""
    try:
        active_jobs = await agent_processor.get_active_jobs()
        return active_jobs
    except Exception as e:
        logger.error(f"Error getting active jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Debug endpoints
@router.get("/debug/cache-status")
async def get_cache_status():
    """Debug: Get Redis cache status"""
    try:
        cache_info = {
            "redis_connected": agent_processor.redis_client.ping() if agent_processor.redis_client else False,
            "cache_keys": [],
            "memory_usage": "unknown"
        }
        
        if agent_processor.redis_client:
            # Get agent-related cache keys
            task_keys = agent_processor.redis_client.keys("agent_task:*")
            workflow_keys = agent_processor.redis_client.keys("crew_workflow:*")
            cache_info["cache_keys"] = {
                "agent_tasks": len(task_keys),
                "crew_workflows": len(workflow_keys),
                "total": len(task_keys) + len(workflow_keys)
            }
            cache_info["memory_usage"] = agent_processor.redis_client.info("memory").get("used_memory_human", "unknown")
            
        return cache_info
    except Exception as e:
        logger.error(f"Error getting cache status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/debug/system-status")
async def get_system_status():
    """Debug: Get AI agent system status"""
    try:
        dependencies = await agent_processor.verify_dependencies()
        active_jobs = await agent_processor.get_active_jobs()
        
        return {
            "dependencies": dependencies,
            "active_jobs_count": active_jobs.get("total_active", 0),
            "active_crews": len(agent_processor.active_crews),
            "system_healthy": all(dependencies.values()),
            "timestamp": "2025-08-16T00:00:00Z"
        }
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
