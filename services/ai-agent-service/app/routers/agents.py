#!/usr/bin/env python3
"""
AI Agent Router - API endpoints for AI agent orchestration
Handles single agents and multi-agent crew workflows
"""

from typing import Dict, List, Any, Optional
import json
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel, Field
import logging

from ..core.agent_processor import AIAgentProcessor
from ..core.crew_factory import crew_factory
from fastapi import WebSocket, WebSocketDisconnect
import os
import uuid
import httpx
try:
    from app.core.config_client import cfg_get  # type: ignore
except Exception:
    cfg_get = None  # type: ignore
from datetime import datetime
from ..core import prompt_loader
from services.shared.usage_client import get_usage_client

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

# -------------------------
# Wiring placeholder (guarded)
# -------------------------
import os

def _flag_enabled(name: str, default: bool = False) -> bool:
    try:
        v = os.getenv(name, str(default)).strip().lower()
        return v in ("1", "true", "yes", "on")
    except Exception:
        return default

@router.get("/migration/plan/schema")
async def migration_plan_schema():
    if not _flag_enabled("AGENT_TOOLS_ENABLED", False):
        raise HTTPException(status_code=404, detail="agent tools disabled")
    return {
        "version": "v1",
        "sections": [
            {"name": "inventory", "fields": ["assets", "dependencies", "owners"]},
            {"name": "risks", "fields": ["complexity", "downtime", "data_integrity"]},
            {"name": "plan", "fields": ["phases", "cutover", "rollback", "validation"]}
        ]
    }

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
    try:
        from app.core.config_client import cfg_get
        token = cfg_get(["ai_agent_service", "service_auth_token"], os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token'))
    except Exception:
        token = os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    if corr_id:
        headers["X-Correlation-ID"] = corr_id
    return headers

def _slugify(name: str) -> str:
    safe = "".join(c for c in (name or "document") if c.isalnum() or c in (" ", "-", "_")).strip()
    return safe.replace(" ", "_").lower() or f"document_{uuid.uuid4().hex[:8]}"

# -------------- Crew-based orchestration endpoints (full CrewAI parity) --------------

class CrewDocumentRequest(BaseModel):
    document_type: str = Field(..., description="Type of document to generate (e.g., Cloud Readiness Scorecard)")
    document_description: str = Field(..., description="High-level guidance for the document")
    output_format: Optional[str] = Field("markdown", description="markdown|pdf|docx (Crew returns text; conversions are optional)")

class CrewAssessmentRequest(BaseModel):
    notes: Optional[str] = Field(None, description="Optional notes or focus areas for assessment")

class CrewRunResponse(BaseModel):
    success: bool
    project_id: str
    process_type: str
    output: str
    llm_hint: Optional[str] = None

class CrewJobStartResponse(BaseModel):
    success: bool
    job_id: str
    project_id: str
    process_type: str
    status_endpoint: str
    ws_endpoint: str

async def _select_llm_hint(process_type: str, project_id: Optional[str], corr_id: Optional[str]) -> Optional[str]:
    """Resolve a CrewAI-friendly LLM hint using llm-service configurations.

    Strategy: query llm-service /configurations and pick default or first, then build provider/model string
    suitable for CrewAI (e.g., gemini/<model>). We propagate correlation id for traceability.
    """
    try:
        llm_url = cfg_get(["ai_agent_service","llm_service_url"], os.getenv("LLM_SERVICE_URL", "http://localhost:8007")) if 'cfg_get' in globals() else os.getenv("LLM_SERVICE_URL", "http://localhost:8007")
        headers = _svc_headers(corr_id)
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{llm_url}/api/llm/configurations", headers=headers)
            if resp.status_code != 200:
                logger.warning(f"LLM service returned {resp.status_code}, using fallback")
                return _get_fallback_llm_hint()
            cfgs = resp.json() or []
            chosen = None
            # Prefer default
            for c in cfgs:
                if c.get("is_default"):
                    chosen = c
                    break
            if not chosen and cfgs:
                chosen = cfgs[0]
            if not chosen:
                logger.warning("No LLM configurations found, using fallback")
                return _get_fallback_llm_hint()
            provider = (chosen.get("provider") or "").lower()
            model = chosen.get("model_name") or chosen.get("model") or ""
            if not provider or not model:
                logger.warning(f"Invalid LLM config (provider: {provider}, model: {model}), using fallback")
                return _get_fallback_llm_hint()
            # CrewAI-friendly string
            if provider == "gemini":
                m = model.replace("models/", "").replace("gemini/", "")
                return f"gemini/{m}"
            # For other providers, CrewAI often accepts model string directly
            return model
    except Exception as e:
        logger.warning(f"LLM selection failed: {e}, using fallback")
        return _get_fallback_llm_hint()

def _get_fallback_llm_hint() -> str:
    """Provide a fallback LLM hint when llm-service is unavailable"""
    # Try to get from environment variables first
    fallback_model = os.getenv("FALLBACK_LLM_MODEL", "gpt-3.5-turbo")
    fallback_provider = os.getenv("FALLBACK_LLM_PROVIDER", "openai")

    if fallback_provider.lower() == "gemini":
        return f"gemini/{fallback_model}"
    else:
        return fallback_model

@router.post("/projects/{project_id}/crews/document/run", response_model=CrewJobStartResponse)
async def run_document_crew(project_id: str, request: CrewDocumentRequest, http_request: Request):
    """Start document-generation crew asynchronously; returns job id for status and ws streaming."""
    try:
        corr_id = http_request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        job_id = str(uuid.uuid4())
        llm_hint = await _select_llm_hint("crew_documentation", project_id, corr_id)

        # Create agent run usage record (running)
        usage = get_usage_client()
        run_rec = await usage.log_agent_run(
            project_id=project_id,
            correlation_id=corr_id,
            agent_type="crew",
            task_name="document_generation",
            status="running",
            metadata={"document_type": request.document_type, "output_format": request.output_format}
        )
        run_id = (run_rec or {}).get("id") if isinstance(run_rec, dict) else None

        # Store minimal workflow status in Redis via agent_processor for reuse
        status_key = f"crew_workflow:{job_id}"
        workflow_status = {
            "job_id": job_id,
            "crew_id": "document_generation",
            "crew_name": "Document Generation Crew",
            "status": "started",
            "progress": 0,
            "started_at": datetime.utcnow().isoformat(),
            "workflow_config": {
                "project_id": project_id,
                "document_type": request.document_type,
                "output_format": request.output_format
            },
            "current_step": "Initializing document crew...",
            "process_type": "crew_documentation",
            "llm_hint": llm_hint,
            "run_id": run_id
        }
        try:
            agent_processor.redis_client.setex(status_key, 7200, json.dumps(workflow_status))
        except Exception:
            pass

        async def _run():
            try:
                # Update progress
                try:
                    cur = json.loads(agent_processor.redis_client.get(status_key) or '{}')
                    cur.update({"status": "processing", "progress": 10, "current_step": "Selecting LLM and creating crew"})
                    agent_processor.redis_client.setex(status_key, 7200, json.dumps(cur))
                except Exception:
                    pass

                # Usage event: crew_start
                if run_id:
                    try:
                        await usage.log_agent_event(
                            run_id=run_id,
                            project_id=project_id,
                            correlation_id=corr_id,
                            event_type="crew_start",
                            role="system",
                            metadata={"step": "init"}
                        )
                    except Exception:
                        pass

                # Store a reference to active WebSocket connections for this job
                websocket_key = f"websocket:{job_id}"
                websocket_clients = getattr(agent_processor, 'websocket_clients', {})
                
                # Create crew with potential WebSocket streaming
                # Ensure RAG tool can discover project via env var during this run
                prev_proj = os.environ.get("CURRENT_PROJECT_ID")
                os.environ["CURRENT_PROJECT_ID"] = project_id
                crew = crew_factory.create_document_generation_crew(
                    project_id=project_id,
                    llm=llm_hint,
                    document_type=request.document_type,
                    document_description=request.document_description,
                    output_format=request.output_format or "markdown",
                    websocket=None,  # Will be connected via Redis status updates
                )
                
                # Update progress before kickoff
                try:
                    cur = json.loads(agent_processor.redis_client.get(status_key) or '{}')
                    cur.update({"status": "processing", "progress": 25, "current_step": "Starting crew execution..."})
                    agent_processor.redis_client.setex(status_key, 7200, json.dumps(cur))
                except Exception:
                    pass
                
                result = crew.kickoff()
                out = str(result) if result is not None else ""

                # Persist output to Storage as Markdown and provide download URLs for the frontend
                download_urls: Dict[str, str] = {}
                md_filename = None
                try:
                    import httpx as _httpx
                    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                    base = f"{_slugify(request.document_type)}_{project_id}_{ts}"
                    md_filename = f"{base}.md"
                    storage_url = (cfg_get(["ai_agent_service","storage_service_url"], os.getenv("STORAGE_SERVICE_URL", "http://localhost:8010"))
                                   if 'cfg_get' in globals() and cfg_get is not None else os.getenv("STORAGE_SERVICE_URL", "http://localhost:8010"))
                    # Upload markdown content
                    async with _httpx.AsyncClient(timeout=30.0) as _client:
                        up = await _client.post(
                            f"{storage_url}/api/storage/projects/{project_id}/upload-text/generated_reports",
                            headers=_svc_headers(corr_id),
                            params={"filename": md_filename},
                            json={"content": out or "", "content_type": "text/markdown; charset=utf-8"}
                        )
                        up.raise_for_status()
                    download_base = f"/api/projects/{project_id}/download/{base}"
                    download_urls = {"markdown": f"{download_base}.md"}
                except Exception as up_err:
                    logger.warning(f"Crew document upload skipped/failed: {up_err}")

                try:
                    cur = json.loads(agent_processor.redis_client.get(status_key) or '{}')
                    # Include structured result so frontend can build download buttons
                    cur.update({
                        "status": "completed",
                        "progress": 100,
                        "current_step": "Completed",
                        "result": {
                            "content": out,
                            "file_path": md_filename or "",
                            "download_urls": download_urls
                        }
                    })
                    agent_processor.redis_client.setex(status_key, 7200, json.dumps(cur))
                except Exception:
                    pass

                # Mark agent run completed
                if run_id:
                    try:
                        await usage.log_agent_run(
                            project_id=project_id,
                            correlation_id=corr_id,
                            agent_type="crew",
                            task_name="document_generation",
                            status="completed",
                            metadata={"result_file": md_filename}
                        )
                        await usage.log_agent_event(
                            run_id=run_id,
                            project_id=project_id,
                            correlation_id=corr_id,
                            event_type="crew_complete",
                            role="system",
                            metadata={"output_preview_chars": len(out or "")}
                        )
                    except Exception:
                        pass
            except Exception as e:
                logger.error(f"Async document crew error: {e}")
                try:
                    cur = json.loads(agent_processor.redis_client.get(status_key) or '{}')
                    cur.update({"status": "failed", "progress": 0, "current_step": f"Failed: {str(e)}"})
                    agent_processor.redis_client.setex(status_key, 7200, json.dumps(cur))
                except Exception:
                    pass
                # Mark agent run failed
                if run_id:
                    try:
                        await usage.log_agent_run(
                            project_id=project_id,
                            correlation_id=corr_id,
                            agent_type="crew",
                            task_name="document_generation",
                            status="failed",
                            metadata={"error": str(e)}
                        )
                        await usage.log_agent_event(
                            run_id=run_id,
                            project_id=project_id,
                            correlation_id=corr_id,
                            event_type="crew_error",
                            role="system",
                            metadata={"error": str(e)}
                        )
                    except Exception:
                        pass
            finally:
                # Restore env var for safety in concurrent runs
                try:
                    if prev_proj is not None:
                        os.environ["CURRENT_PROJECT_ID"] = prev_proj
                    else:
                        os.environ.pop("CURRENT_PROJECT_ID", None)
                except Exception:
                    pass

        import asyncio
        asyncio.create_task(_run())

        base = f"/api/agents/workflows/{job_id}/status"
        ws = f"/api/agents/workflows/{job_id}/ws"
        return CrewJobStartResponse(success=True, job_id=job_id, project_id=project_id, process_type="crew_documentation", status_endpoint=base, ws_endpoint=ws)
    except Exception as e:
        logger.error(f"Document crew run failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/projects/{project_id}/crews/assessment/run", response_model=CrewJobStartResponse)
async def run_assessment_crew(project_id: str, request: CrewAssessmentRequest, http_request: Request):
    """Start assessment crew asynchronously; returns job id for status and ws streaming."""
    try:
        corr_id = http_request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        job_id = str(uuid.uuid4())
        llm_hint = await _select_llm_hint("crew_assessment", project_id, corr_id)

        # Create agent run usage record (running)
        usage = get_usage_client()
        run_rec = await usage.log_agent_run(
            project_id=project_id,
            correlation_id=corr_id,
            agent_type="crew",
            task_name="assessment",
            status="running",
            metadata={"notes": request.notes}
        )
        run_id = (run_rec or {}).get("id") if isinstance(run_rec, dict) else None

        status_key = f"crew_workflow:{job_id}"
        workflow_status = {
            "job_id": job_id,
            "crew_id": "assessment",
            "crew_name": "Assessment Crew",
            "status": "started",
            "progress": 0,
            "started_at": datetime.utcnow().isoformat(),
            "workflow_config": {"project_id": project_id, "notes": request.notes},
            "current_step": "Initializing assessment crew...",
            "process_type": "crew_assessment",
            "llm_hint": llm_hint,
            "run_id": run_id
        }
        try:
            agent_processor.redis_client.setex(status_key, 7200, json.dumps(workflow_status))
        except Exception:
            pass

        import asyncio
        async def _run():
            try:
                # Update progress
                try:
                    cur = json.loads(agent_processor.redis_client.get(status_key) or '{}')
                    cur.update({"status": "processing", "progress": 10, "current_step": "Selecting LLM and creating crew"})
                    agent_processor.redis_client.setex(status_key, 7200, json.dumps(cur))
                except Exception:
                    pass

                crew = crew_factory.create_assessment_crew(project_id=project_id, llm=llm_hint, websocket=None)
                
                # Update progress before kickoff
                try:
                    cur = json.loads(agent_processor.redis_client.get(status_key) or '{}')
                    cur.update({"status": "processing", "progress": 25, "current_step": "Starting crew execution..."})
                    agent_processor.redis_client.setex(status_key, 7200, json.dumps(cur))
                except Exception:
                    pass
                
                # Usage event: assessment_start
                if run_id:
                    try:
                        await usage.log_agent_event(
                            run_id=run_id,
                            project_id=project_id,
                            correlation_id=corr_id,
                            event_type="assessment_start",
                            role="system"
                        )
                    except Exception:
                        pass

                result = crew.kickoff()
                out = str(result) if result is not None else ""
                
                try:
                    cur = json.loads(agent_processor.redis_client.get(status_key) or '{}')
                    cur.update({"status": "completed", "progress": 100, "current_step": "Completed", "result": out})
                    agent_processor.redis_client.setex(status_key, 7200, json.dumps(cur))
                except Exception:
                    pass
                # Mark run completed
                if run_id:
                    try:
                        await usage.log_agent_run(
                            project_id=project_id,
                            correlation_id=corr_id,
                            agent_type="crew",
                            task_name="assessment",
                            status="completed"
                        )
                        await usage.log_agent_event(
                            run_id=run_id,
                            project_id=project_id,
                            correlation_id=corr_id,
                            event_type="assessment_complete",
                            role="system",
                            metadata={"output_preview_chars": len(out or "")}
                        )
                    except Exception:
                        pass
            except Exception as e:
                logger.error(f"Async assessment crew error: {e}")
                try:
                    cur = json.loads(agent_processor.redis_client.get(status_key) or '{}')
                    cur.update({"status": "failed", "progress": 0, "current_step": f"Failed: {str(e)}"})
                    agent_processor.redis_client.setex(status_key, 7200, json.dumps(cur))
                except Exception:
                    pass
                if run_id:
                    try:
                        await usage.log_agent_run(
                            project_id=project_id,
                            correlation_id=corr_id,
                            agent_type="crew",
                            task_name="assessment",
                            status="failed",
                            metadata={"error": str(e)}
                        )
                        await usage.log_agent_event(
                            run_id=run_id,
                            project_id=project_id,
                            correlation_id=corr_id,
                            event_type="assessment_error",
                            role="system",
                            metadata={"error": str(e)}
                        )
                    except Exception:
                        pass
            except Exception as e:
                logger.error(f"Async assessment crew error: {e}")
                try:
                    cur = json.loads(agent_processor.redis_client.get(status_key) or '{}')
                    cur.update({"status": "failed", "progress": 0, "current_step": f"Failed: {str(e)}"})
                    agent_processor.redis_client.setex(status_key, 7200, json.dumps(cur))
                except Exception:
                    pass

        asyncio.create_task(_run())
        base = f"/api/agents/workflows/{job_id}/status"
        ws = f"/api/agents/workflows/{job_id}/ws"
        return CrewJobStartResponse(success=True, job_id=job_id, project_id=project_id, process_type="crew_assessment", status_endpoint=base, ws_endpoint=ws)
    except Exception as e:
        logger.error(f"Assessment crew run failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- WebSocket endpoint for workflow progress streaming ---
@router.websocket("/workflows/{job_id}/ws")
async def workflow_ws(websocket: WebSocket, job_id: str):
    await websocket.accept()
    logger.info(f"WebSocket connected for job {job_id}")
    
    try:
        import asyncio as _asyncio
        last_status = None
        
        while True:
            try:
                status_key = f"crew_workflow:{job_id}"
                data = agent_processor.redis_client.get(status_key)
                
                if data:
                    current_status = json.loads(data)
                    # Only send updates when status changes
                    if current_status != last_status:
                        await websocket.send_text(data)
                        logger.debug(f"Sent WebSocket update for job {job_id}: {current_status.get('current_step', 'Unknown step')}")
                        last_status = current_status
                else:
                    # Send initial status for unknown jobs
                    initial_msg = {"job_id": job_id, "status": "initializing", "progress": 0, "current_step": "Connecting to CrewAI terminal..."}
                    await websocket.send_text(json.dumps(initial_msg))
                    
            except Exception as e:
                logger.error(f"WebSocket error for job {job_id}: {e}")
                # Send error status
                error_msg = {"job_id": job_id, "status": "error", "progress": 0, "current_step": f"Connection error: {str(e)}"}
                await websocket.send_text(json.dumps(error_msg))
                
            await _asyncio.sleep(1.0)  # Reduced from 1.5 to make it more responsive
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for job {job_id}")
        return
    except Exception as e:
        logger.error(f"WebSocket fatal error for job {job_id}: {e}")
        return

@router.post("/projects/{project_id}/documents/generate", response_model=GenerateDocumentResponse)
async def generate_document(project_id: str, request: GenerateDocumentRequest):
    """Generate a document using Project templates, LLM service, and store via Storage service."""
    corr_id = str(uuid.uuid4())
    svc = {
    "project": (cfg_get(["ai_agent_service","project_service_url"], os.getenv("PROJECT_SERVICE_URL", "http://localhost:8002")) if 'cfg_get' in globals() else os.getenv("PROJECT_SERVICE_URL", "http://localhost:8002")),
    "vector": (cfg_get(["ai_agent_service","vector_service_url"], os.getenv("VECTOR_SERVICE_URL", "http://localhost:8005")) if 'cfg_get' in globals() else os.getenv("VECTOR_SERVICE_URL", "http://localhost:8005")),
    "llm": (cfg_get(["ai_agent_service","llm_service_url"], os.getenv("LLM_SERVICE_URL", "http://localhost:8007")) if 'cfg_get' in globals() else os.getenv("LLM_SERVICE_URL", "http://localhost:8007")),
    "storage": (cfg_get(["ai_agent_service","storage_service_url"], os.getenv("STORAGE_SERVICE_URL", "http://localhost:8010")) if 'cfg_get' in globals() else os.getenv("STORAGE_SERVICE_URL", "http://localhost:8010")),
    "reporting": (cfg_get(["ai_agent_service","reporting_service_url"], os.getenv("REPORTING_SERVICE_URL", "http://localhost:8003")) if 'cfg_get' in globals() else os.getenv("REPORTING_SERVICE_URL", "http://localhost:8003")),
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

            # 3) Compose prompt for LLM Service via prompt loader
            template_guidance = (tmpl or {}).get("description") or request.description or "Generate a professional project summary."
            joined_snippets = ("\n---\n".join(context_snippets)) if context_snippets else ""
            try:
                prompt = prompt_loader.render_text("document_generation", {
                    "project_id": project_id,
                    "template_guidance": template_guidance,
                    "context_snippets": joined_snippets
                })
            except Exception:
                # Safe fallback to previous inline composition
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
async def get_workflow_status(job_id: str):
    """Get status of a running workflow (crew or post-processing)"""
    try:
        # Try crew workflow first
        status = await agent_processor.get_workflow_status(job_id)

        if status:
            return status

        # Try post-processing job
        try:
            status_key = f"post_process:{job_id}"
            status_data = agent_processor.redis_client.get(status_key)

            if status_data:
                return json.loads(status_data)
        except Exception:
            pass

        raise HTTPException(status_code=404, detail="Workflow not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting workflow status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/workflows/{job_id}/cancel")
async def cancel_crew_workflow(job_id: str):
    """Gracefully request cancellation of a running crew workflow.
    This marks the Redis status as cancelled. If cooperative cancellation hooks are
    present in running crews, they should observe this flag and stop soon after.
    """
    try:
        status_key = f"crew_workflow:{job_id}"
        try:
            cur_raw = agent_processor.redis_client.get(status_key)
            cur = json.loads(cur_raw) if cur_raw else {}
        except Exception:
            cur = {}
        cur.update({"status": "cancelled", "current_step": "Cancellation requested"})
        try:
            agent_processor.redis_client.setex(status_key, 7200, json.dumps(cur))
        except Exception:
            pass
        return {"success": True, "job_id": job_id, "status": "cancelled"}
    except Exception as e:
        logger.error(f"Error cancelling workflow {job_id}: {e}")
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

@router.post("/post-process/{project_id}/{document_id}", response_model=CrewJobStartResponse)
async def trigger_post_processing(
    project_id: str,
    document_id: str,
    background_tasks: BackgroundTasks,
    http_request: Request
):
    """Trigger post-processing agent for lessons learned generation"""
    try:
        from ..agents.post_processing_agent import PostProcessingAgent

        corr_id = http_request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        job_id = str(uuid.uuid4())

        # Get service URLs from config
        service_urls = {
            "graph_service": cfg_get(["ai_agent_service", "graph_service_url"], os.getenv("GRAPH_SERVICE_URL", "http://localhost:8006")),
            "vector_service": cfg_get(["ai_agent_service", "vector_service_url"], os.getenv("VECTOR_SERVICE_URL", "http://localhost:8005")),
            "llm_service": cfg_get(["ai_agent_service", "llm_service_url"], os.getenv("LLM_SERVICE_URL", "http://localhost:8007")),
            "lessons_service": cfg_get(["ai_agent_service", "lessons_service_url"], os.getenv("LESSONS_SERVICE_URL", "http://localhost:8018"))
        }

        # Store job status in Redis
        status_key = f"post_process:{job_id}"
        job_status = {
            "job_id": job_id,
            "project_id": project_id,
            "document_id": document_id,
            "status": "started",
            "progress": 0,
            "started_at": datetime.utcnow().isoformat(),
            "current_step": "Initializing post-processing...",
            "process_type": "post_processing",
            "correlation_id": corr_id
        }

        try:
            agent_processor.redis_client.setex(status_key, 3600, json.dumps(job_status))
        except Exception as e:
            logger.warning(f"Failed to store initial job status: {e}")

        # Background processing function
        async def _run_post_processing():
            try:
                # Update progress: Gathering data
                await _update_post_process_status(job_id, "processing", 25, "Gathering knowledge core data...")

                # Process document insights
                result = await PostProcessingAgent.process_document_insights(
                    project_id, document_id, service_urls
                )

                # Update final status
                if result.get("success"):
                    await _update_post_process_status(
                        job_id, "completed", 100,
                        f"Generated {result.get('insights_generated', 0)} insights",
                        result
                    )
                else:
                    await _update_post_process_status(
                        job_id, "failed", 0,
                        f"Post-processing failed: {result.get('error', 'Unknown error')}",
                        result
                    )

            except Exception as e:
                logger.error(f"Post-processing job {job_id} failed: {e}")
                await _update_post_process_status(
                    job_id, "failed", 0, f"Exception: {str(e)}"
                )

        # Start background task
        background_tasks.add_task(_run_post_processing)

        return CrewJobStartResponse(
            success=True,
            job_id=job_id,
            project_id=project_id,
            process_type="post_processing",
            status_endpoint=f"/api/agents/workflows/{job_id}/status",
            ws_endpoint=f"/api/agents/workflows/{job_id}/ws"
        )

    except Exception as e:
        logger.error(f"Failed to start post-processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def _update_post_process_status(job_id: str, status: str, progress: int, current_step: str, result: Dict = None):
    """Update post-processing job status"""
    try:
        status_key = f"post_process:{job_id}"
        current_status = agent_processor.redis_client.get(status_key)

        if current_status:
            status_data = json.loads(current_status)
            status_data.update({
                "status": status,
                "progress": progress,
                "current_step": current_step,
                "last_updated": datetime.utcnow().isoformat()
            })

            if result:
                status_data["result"] = result

            if status == "completed":
                status_data["completed_at"] = datetime.utcnow().isoformat()

            agent_processor.redis_client.setex(status_key, 3600, json.dumps(status_data))

    except Exception as e:
        logger.error(f"Error updating post-process status: {e}")

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
