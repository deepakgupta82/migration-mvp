#!/usr/bin/env python3
"""
API Gateway Router - Routes requests to microservices
Replaces business logic routers with HTTP client calls to extracted services
"""

import os
import logging
import asyncio
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Query, Request, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
import httpx
from app.core.event_bus import get_event_bus

from app.core.service_client import get_service_client
from app.core.event_bus import get_event_bus

logger = logging.getLogger("api-gateway.router")

# Create router
router = APIRouter(tags=["api-gateway"])

# =====================================================================================
# HEALTH CHECK ENDPOINTS
# =====================================================================================

@router.get("/api/health", summary="API Gateway Health Check")
async def api_health_check():
    """Gateway health check endpoint for frontend that includes infra statuses."""
    try:
        client = await get_service_client()
        try:
            micro_health = await asyncio.wait_for(client.check_all_services_health(), timeout=8.0)
        except Exception as te:
            logger.warning(f"Microservices health timed out/failed, continuing with infra only: {te}")
            micro_health = {}

        # Fetch backend comprehensive health (includes infra like neo4j, minio, loki, promtail, redis, postgresql)
        backend_base = os.getenv("BACKEND_PUBLIC_URL", "http://localhost:8000")
        infra_services: Dict[str, Any] = {}
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=2.0)) as ac:
                r = await ac.get(f"{backend_base}/health")
                if r.status_code == 200:
                    data = r.json()
                    infra_map = data.get("services") or {}
                    # Only take canonical infra keys
                    for k in ["neo4j", "minio", "loki", "promtail", "redis", "postgresql", "weaviate", "llm_configurations", "backend", "project_service", "reporting_service"]:
                        if k in infra_map:
                            infra_services[k] = infra_map[k]
        except Exception as ie:
            logger.debug(f"Infra health fetch failed: {ie}")

        # Merge maps (microservices keys are like project/reporting/document/...)
        services: Dict[str, Any] = {**micro_health, **infra_services}

        # Normalize to compute overall status
        def is_connected(val: Any) -> Optional[bool]:
            try:
                if isinstance(val, dict):
                    s = str(val.get("status", "")).lower()
                else:
                    s = str(val).lower()
                if s in ("healthy", "up", "present", "ok", "connected", "available"):
                    return True
                if any(x in s for x in ("error", "down", "failed", "unhealthy")):
                    return False
            except Exception:
                pass
            return None

        flags = [is_connected(v) for v in services.values()]
        trues = sum(1 for f in flags if f is True)
        falses = sum(1 for f in flags if f is False)
        total = trues + falses
        if total == 0:
            overall = "degraded"
        elif falses == 0:
            overall = "healthy"
        elif trues >= falses:
            overall = "degraded"
        else:
            overall = "unhealthy"

        return {
            "status": overall,
            "services": services,
            "gateway": "operational",
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "gateway": "operational",
        }

@router.get("/health", summary="Gateway health alias", include_in_schema=False)
async def api_health_alias():
    """Alias for /api/health to align with other services' probes."""
    return await api_health_check()

@router.get("/api/health/containers", summary="Container / service stats (proxy)")
async def api_health_containers():
    """Proxy to backend /health/containers for frontend convenience."""
    logger.info("🔍 Container stats proxy endpoint called")
    try:
        backend_base = os.getenv("BACKEND_PUBLIC_URL", "http://localhost:8000")
        logger.debug(f"📡 Proxying to: {backend_base}/health/containers")
        async with httpx.AsyncClient(timeout=httpx.Timeout(8.0, connect=2.0)) as ac:
            r = await ac.get(f"{backend_base}/health/containers")
            logger.debug(f"📋 Backend response: status={r.status_code}, content_length={len(r.content)}")
            if r.status_code == 200:
                data = r.json()
                container_count = len(data.get('containers', []))
                logger.info(f"✅ Container stats proxy successful: {container_count} containers")
                return JSONResponse(status_code=r.status_code, content=data)
            else:
                logger.warning(f"⚠️ Backend returned non-200: {r.status_code}")
                return JSONResponse(status_code=r.status_code, content=r.json())
    except Exception as e:
        logger.error(f"❌ Proxy health containers failed: {e}")
        raise HTTPException(status_code=502, detail="Failed to fetch container stats")

# Pydantic models for requests
class ProjectCreateRequest(BaseModel):
    # Deprecated: kept for reference but not used in handler to allow pass-through of extra fields
    name: str
    description: Optional[str] = None
    # Note: client_name and other fields are required by project-service; the route below
    # uses a raw dict to forward all provided fields without validation truncation.

class QueryRequest(BaseModel):
    query: str
    limit: Optional[int] = 10
    use_llm: Optional[bool] = False

class ChatRequest(BaseModel):
    question: str
    context_limit: Optional[int] = 5
    use_llm: Optional[bool] = False

class DocumentProcessRequest(BaseModel):
    # Kept for reference; not used by the handlers below. We accept flexible dicts instead.
    files: Optional[List[str]] = None
    reprocess: bool = False

class AgentTaskRequest(BaseModel):
    input_data: Dict[str, Any]
    parameters: Optional[Dict[str, Any]] = None

class CrewWorkflowRequest(BaseModel):
    input_data: Dict[str, Any]
    parameters: Optional[Dict[str, Any]] = None

# Request model for document generation proxy
class GenerateDocumentRequest(BaseModel):
    template_id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    format: Optional[str] = "markdown"  # markdown | pdf | docx
    output_type: Optional[str] = "markdown"
    request_id: Optional[str] = None

# =====================================================================================
# PROJECT MANAGEMENT ENDPOINTS - Route to Project Service (8002)
# =====================================================================================

@router.get("/api/projects/", summary="List all projects")
@router.get("/api/projects", summary="List all projects (no slash)", include_in_schema=False)
async def list_projects(include_stats: bool = Query(False)):
    """List all projects via Project Service"""
    try:
        client = await get_service_client()
        projects = await client.list_projects(include_stats=include_stats)
        # Map backend field to frontend expected field for each project
        if isinstance(projects, list):
            for project in projects:
                if isinstance(project, dict) and "llm_api_key_id" in project and "default_llm_config_id" not in project:
                    project["default_llm_config_id"] = project["llm_api_key_id"]
        return projects
    except Exception as e:
        # Distinguish timeout to avoid breaking UI rendering
        msg = str(e)
        if "Timeout" in msg or "timed out" in msg:
            logger.error("List projects timed out calling project service")
            raise HTTPException(status_code=504, detail="Project service timed out")
    except Exception as e:
        logger.error(f"List projects failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list projects: {str(e)}")

@router.get("/api/projects/{project_id}", summary="Get project by ID")
async def get_project(project_id: str):
    """Get project by ID via Project Service"""
    try:
        client = await get_service_client()
        project = await client.get_project(project_id)
        # Map backend field to frontend expected field
        if isinstance(project, dict) and "llm_api_key_id" in project and "default_llm_config_id" not in project:
            project["default_llm_config_id"] = project["llm_api_key_id"]
        return project
    except Exception as e:
        logger.error(f"Get project {project_id} failed: {e}")
        raise HTTPException(status_code=404, detail=f"Project not found: {str(e)}")

@router.post("/api/projects/", summary="Create new project")
@router.post("/api/projects", summary="Create new project (no slash)", include_in_schema=False)
async def create_project(request: dict):
    """Create new project via Project Service (forwards all provided fields)"""
    try:
        client = await get_service_client()
        # Map friendly UI aliases
        req = dict(request or {})
        if "rfp" in req and "rfp_summary" not in req:
            req["rfp_summary"] = req.pop("rfp")
        if "timeline" in req and "timeline_notes" not in req:
            req["timeline_notes"] = req.pop("timeline")
        # Map LLM configuration field from frontend to backend
        if "default_llm_config_id" in req and "llm_api_key_id" not in req:
            req["llm_api_key_id"] = req.pop("default_llm_config_id")
        # Forward all fields as-is to avoid dropping required keys like client_name
        return await client.create_project(req)
    except Exception as e:
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

@router.put("/api/projects/{project_id}", summary="Update project")
async def update_project(project_id: str, update: dict):
    """Update project via Project Service"""
    try:
        client = await get_service_client()
        upd = dict(update or {})
        if "rfp" in upd and "rfp_summary" not in upd:
            upd["rfp_summary"] = upd.pop("rfp")
        if "timeline" in upd and "timeline_notes" not in upd:
            upd["timeline_notes"] = upd.pop("timeline")
        # Map LLM configuration field from frontend to backend for updates too
        if "default_llm_config_id" in upd and "llm_api_key_id" not in upd:
            upd["llm_api_key_id"] = upd.pop("default_llm_config_id")
        return await client.update_project(project_id, upd)
    except Exception as e:
        logger.error(f"Update project {project_id} failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update project: {str(e)}")

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

@router.get("/api/projects/{project_id}/stats", summary="Get individual project statistics")
async def get_project_stats(project_id: str):
    """Get statistics for a specific project"""
    try:
        client = await get_service_client()
        
        # Get project details
        project = await client.get_project(project_id)
        
        # Get storage stats
        storage_stats = {}
        try:
            storage_stats = await client.get_storage_stats(project_id)
        except Exception as e:
            logger.warning(f"Failed to get storage stats for {project_id}: {e}")
            storage_stats = {"error": "Failed to get storage stats"}
        
        # Get graph stats if available
        graph_stats = {}
        try:
            graph_stats = await client._make_request("GET", "graph", f"/api/graphs/projects/{project_id}/stats")
        except Exception as e:
            logger.warning(f"Failed to get graph stats for {project_id}: {e}")
            graph_stats = {"error": "Failed to get graph stats"}
        
        # Get vector stats if available
        vector_stats = {}
        try:
            vector_stats = await client._make_request("GET", "vector", f"/api/vectors/projects/{project_id}/stats")
        except Exception as e:
            logger.warning(f"Failed to get vector stats for {project_id}: {e}")
            vector_stats = {"error": "Failed to get vector stats"}
        
        return {
            "project_id": project_id,
            "project_name": project.get("name", "Unknown"),
            "status": project.get("status", "unknown"),
            "storage_stats": storage_stats,
            "graph_stats": graph_stats,
            "vector_stats": vector_stats,
            "created_at": project.get("created_at"),
            "updated_at": project.get("updated_at")
        }
    except Exception as e:
        logger.error(f"Get project {project_id} stats failed: {e}")
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
    """Legacy upload endpoint - routes to Document Service"""
    try:
        client = await get_service_client()
        return await client.upload_documents(project_id, files)
    except Exception as e:
        logger.error(f"Legacy upload failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.post("/api/projects/{project_id}/upload", summary="Upload documents")
async def upload_documents(project_id: str, files: List[UploadFile] = File(...)):
    """Upload documents via Document Service"""
    try:
        client = await get_service_client()
        return await client.upload_documents(project_id, files)
    except Exception as e:
        logger.error(f"Upload failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

def _extract_filenames(payload: Dict[str, Any]) -> List[str]:
    files: List[str] = []
    if not isinstance(payload, dict):
        return files
    if "file_names" in payload and isinstance(payload["file_names"], list):
        files = [str(x) for x in payload.get("file_names", []) if isinstance(x, (str, bytes))]
    elif "files" in payload and isinstance(payload["files"], list):
        raw = payload["files"]
        if all(isinstance(x, str) for x in raw):
            files = [str(x) for x in raw]
        else:
            # Extract filename from objects: { filename, name, key }
            candidates = []
            for item in raw:
                if isinstance(item, dict):
                    name = item.get("filename") or item.get("name") or item.get("key") or item.get("object_key")
                    if isinstance(name, str):
                        candidates.append(name)
            files = candidates
    return files


@router.post("/api/projects/{project_id}/process-all", summary="Process all uploaded documents")
async def process_all_documents(project_id: str, request: Dict[str, Any]):
    """Process all uploaded documents via Document Service"""
    try:
        client = await get_service_client()
        # Forward to document-service process-all; include reprocess when true
        reprocess_flag = False
        try:
            # Accept both Pydantic and raw dict bodies
            if isinstance(request, dict):
                reprocess_flag = bool(request.get("reprocess", False))
            else:
                reprocess_flag = bool(getattr(request, "reprocess", False))
        except Exception:
            reprocess_flag = False
        if reprocess_flag:
            # document service supports query param reprocess via legacy alias; call directly
            return await client._make_request(
                "POST", "document", f"/api/documents/{project_id}/process-all", params={"reprocess": True}
            )
        return await client._make_request("POST", "document", f"/api/documents/{project_id}/process-all")
    except Exception as e:
        logger.error(f"Process all failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Process all failed: {str(e)}")

@router.post("/api/projects/{project_id}/process-selected", summary="Process selected documents")
async def process_selected_documents(project_id: str, request: Dict[str, Any]):
    """Process selected documents via Document Service"""
    try:
        client = await get_service_client()
        files = _extract_filenames(request)
        reprocess_flag = bool(request.get("reprocess", False)) if isinstance(request, dict) else bool(getattr(request, "reprocess", False))
        if not files:
            raise HTTPException(status_code=400, detail="No file names provided for selected processing")
        payload = {"file_names": files, "reprocess": reprocess_flag}
        return await client._make_request("POST", "document", f"/api/documents/{project_id}/process-selected", json=payload)
    except Exception as e:
        logger.error(f"Process selected failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Process selected failed: {str(e)}")

@router.post("/api/projects/{project_id}/process-documents", summary="Process documents (legacy alias)")
async def process_documents_legacy(project_id: str, request: Dict[str, Any]):
    """Legacy route used by frontend: maps to Document Service process-all; supports optional selected files."""
    try:
        client = await get_service_client()
        files = _extract_filenames(request)
        reprocess_flag = bool(request.get("reprocess", False)) if isinstance(request, dict) else bool(getattr(request, "reprocess", False))
        if files:
            payload = {"file_names": files, "reprocess": reprocess_flag}
            return await client._make_request("POST", "document", f"/api/documents/{project_id}/process-selected", json=payload)
        # Else process all; honor reprocess flag if present
        if reprocess_flag:
            return await client._make_request("POST", "document", f"/api/documents/{project_id}/process-all", params={"reprocess": True})
        return await client._make_request("POST", "document", f"/api/documents/{project_id}/process-all")
    except Exception as e:
        logger.error(f"Legacy process-documents failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Process documents failed: {str(e)}")

# =====================================================================================
# DOCUMENT GENERATION ENDPOINTS - Route to AI Agent + Storage Services
# =====================================================================================

@router.post("/api/projects/{project_id}/documents/generate", summary="Generate document from template")
async def generate_document(project_id: str, payload: GenerateDocumentRequest):
    """Proxy to AI Agent Service to generate a document (uses global templates)."""
    try:
        client = await get_service_client()
        return await client.generate_document(project_id, payload.dict(exclude_none=True))
    except Exception as e:
        logger.error(f"Generate document failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate document: {str(e)}")

# Backward-compatible alias (legacy UIs may call this)
@router.post("/api/projects/{project_id}/generate-document", include_in_schema=False)
async def generate_document_legacy(project_id: str, payload: GenerateDocumentRequest):
    try:
        client = await get_service_client()
        return await client.generate_document(project_id, payload.dict(exclude_none=True))
    except Exception as e:
        logger.error(f"Legacy generate-document failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate document: {str(e)}")

@router.get("/api/projects/{project_id}/download/{filename}", summary="Download generated document/report")
async def download_generated_file(project_id: str, filename: str):
    """Download from Storage. If requesting PDF/DOCX and it doesn't exist yet, convert from MD, store, then return.

    Storage category: generated_reports
    """
    try:
        client = await get_service_client()
        category = "generated_reports"

        # Helper to stream a blob dict returned by ServiceClient
        def _stream_blob(name: str, blob: Dict[str, Any]):
            content = blob.get("content", b"")
            status_code = blob.get("status_code", 200)
            headers = {}
            for k in ("content-type", "Content-Type"):
                if k in blob and blob[k]:
                    headers["Content-Type"] = blob[k]
                    break
            headers.setdefault("Content-Disposition", f"attachment; filename=\"{name}\"")
            return StreamingResponse(iter([content]), status_code=status_code, headers=headers)

        # Try direct download first
        try:
            blob = await client.download_file(project_id, category, filename)
            return _stream_blob(filename, blob)
        except Exception as e:
            # If the request is not for a convertible type, or error is not 404, surface it
            ext = (filename.rsplit(".", 1)[-1] or "").lower() if "." in filename else ""
            is_convertible = ext in ("pdf", "docx")
            if not is_convertible:
                raise

            # Attempt on-demand conversion from corresponding MD
            base = filename[: -(len(ext) + 1)] if ext else filename
            md_name = f"{base}.md"
            try:
                md_blob = await client.download_file(project_id, category, md_name)
            except Exception as e2:
                # No source markdown to convert
                raise HTTPException(status_code=404, detail=f"Source markdown not found for conversion: {md_name}")

            md_bytes = md_blob.get("content", b"")
            if not md_bytes:
                raise HTTPException(status_code=500, detail="Empty markdown content for conversion")

            # Convert via Reporting Service
            try:
                converted = await client.reporting_convert_markdown(
                    project_id=project_id,
                    markdown_content=md_bytes.decode("utf-8", errors="ignore"),
                    base=base,
                    target=ext,
                )
                bin_data = converted.get("content") if isinstance(converted, dict) else None
                if not bin_data:
                    # Some reporting services may return raw bytes already
                    bin_data = converted if isinstance(converted, (bytes, bytearray)) else None
                if not bin_data:
                    raise RuntimeError("Conversion failed: no content returned")

                content_type = "application/pdf" if ext == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                # Upload converted artifact to Storage for caching
                await client.upload_bytes(
                    project_id=project_id,
                    category=category,
                    filename=filename,
                    data_bytes=bin_data,
                    content_type=content_type,
                )

                # Return the freshly converted file
                return StreamingResponse(iter([bin_data]), status_code=200, headers={
                    "Content-Type": content_type,
                    "Content-Disposition": f"attachment; filename=\"{filename}\"",
                })
            except HTTPException:
                raise
            except Exception as conv_err:
                logger.error(f"On-demand conversion failed for {project_id}/{filename}: {conv_err}")
                raise HTTPException(status_code=500, detail=f"Conversion failed: {conv_err}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download generated file failed for {project_id}/{filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to download file: {str(e)}")

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
        raw = await client.list_project_files(project_id, "uploads_raw")

        # Normalize to { project_id, files: [{filename, file_size, file_type, uploaded_at}], count }
        files = []
        def extract_file_info(f):
            # Defensive: handle dict or str
            if isinstance(f, dict):
                name = f.get("filename") or f.get("key") or f.get("name") or f.get("object_key")
                file_size = f.get("file_size") or f.get("size")
                file_type = f.get("file_type") or f.get("content_type")
                uploaded_at = f.get("uploaded_at") or f.get("timestamp")
                if name:
                    return {
                        "filename": name.split("/")[-1],
                        "file_size": file_size,
                        "file_type": file_type,
                        "uploaded_at": uploaded_at
                    }
            elif isinstance(f, str):
                return {"filename": f}
            return None

        if isinstance(raw, dict):
            items = raw.get("files") or raw.get("objects") or raw.get("uploaded_files") or raw.get("items") or raw
            if isinstance(items, list):
                for f in items:
                    info = extract_file_info(f)
                    if info:
                        files.append(info)
            elif isinstance(items, dict) and "files" in items:
                maybe = items.get("files")
                if isinstance(maybe, list):
                    for f in maybe:
                        info = extract_file_info(f)
                        if info:
                            files.append(info)
        elif isinstance(raw, list):
            for f in raw:
                info = extract_file_info(f)
                if info:
                    files.append(info)

        return {"project_id": project_id, "files": files, "count": len(files)}
    except Exception as e:
        logger.error(f"List files failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")

@router.delete("/api/projects/{project_id}/files/{file_id}", summary="Delete project file completely")
async def delete_project_file_completely(
    project_id: str,
    file_id: str
):
    """Delete a project file completely including storage, embeddings, and graph data"""
    try:
        client = await get_service_client()
        
        # First, get the file details to get the filename
        try:
            file_details = await client._make_request("GET", "project", f"/projects/{project_id}/files/{file_id}")
            filename = file_details.get("filename", file_id)
        except Exception as e:
            logger.warning(f"Could not get file details for {file_id}: {e}")
            filename = file_id
        
        # 1. Delete from project service database
        try:
            await client._make_request("DELETE", "project", f"/projects/{project_id}/files/{file_id}")
            logger.info(f"Deleted file record {file_id} from project service")
        except Exception as e:
            logger.error(f"Failed to delete file record from project service: {e}")
            # Continue with other deletions even if this fails
        
        # 2. Delete from storage service (raw uploads, parsed files, etc.)
        deleted_files = []
        try:
            storage_result = await client.delete_document_storage(project_id, filename)
            deleted_files = storage_result.get("deleted_files", [])
            logger.info(f"Deleted files from storage: {len(deleted_files)} files")
        except Exception as e:
            logger.warning(f"Failed to delete files from storage: {e}")
        
        # 3. Delete embeddings from vector service
        embeddings_deleted = 0
        try:
            vector_result = await client.delete_document_vectors(project_id, filename)
            embeddings_deleted = vector_result.get("deleted_count", 0)
            logger.info(f"Deleted {embeddings_deleted} embeddings for document {filename}")
        except Exception as e:
            logger.warning(f"Failed to delete embeddings for {filename}: {e}")
        
        # 4. Delete graph data from graph service
        graph_nodes_deleted = 0
        graph_relationships_deleted = 0
        try:
            graph_result = await client.delete_document_graph(project_id, filename)
            graph_nodes_deleted = graph_result.get("nodes_deleted", 0)
            graph_relationships_deleted = graph_result.get("relationships_deleted", 0)
            logger.info(f"Deleted {graph_nodes_deleted} nodes and {graph_relationships_deleted} relationships for document {filename}")
        except Exception as e:
            logger.warning(f"Failed to delete graph data for {filename}: {e}")
        
        # 5. Publish document_deleted event for stats service
        try:
            event_bus = get_event_bus()
            await event_bus.publish("document_deleted", {
                "project_id": project_id,
                "file_id": file_id,
                "filename": filename,
                "deleted_count": 1
            })
        except Exception as e:
            logger.warning(f"Failed to publish document_deleted event: {e}")
        
        return {
            "message": "File deleted successfully",
            "project_id": project_id,
            "file_id": file_id,
            "filename": filename,
            "deleted_files": deleted_files,
            "embeddings_deleted": embeddings_deleted,
            "graph_nodes_deleted": graph_nodes_deleted,
            "graph_relationships_deleted": graph_relationships_deleted
        }
        
    except Exception as e:
        logger.error(f"Complete file deletion failed for {project_id}/{file_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete file completely: {str(e)}")

@router.delete("/api/projects/{project_id}/files", summary="Bulk delete project files completely")
async def bulk_delete_project_files(
    project_id: str,
    file_ids: List[str]
):
    """Bulk delete project files completely including storage, embeddings, and graph data"""
    try:
        client = await get_service_client()
        
        results = {
            "successful_deletions": [],
            "failed_deletions": [],
            "total_deleted_files": 0,
            "total_deleted_embeddings": 0,
            "total_deleted_graph_nodes": 0
        }
        
        for file_id in file_ids:
            try:
                # Get file details
                try:
                    file_details = await client._make_request("GET", "project", f"/projects/{project_id}/files/{file_id}")
                    filename = file_details.get("filename", file_id)
                except Exception as e:
                    logger.warning(f"Could not get file details for {file_id}: {e}")
                    filename = file_id
                
                # Delete from project service database
                try:
                    await client._make_request("DELETE", "project", f"/projects/{project_id}/files/{file_id}")
                    logger.info(f"Deleted file record {file_id} from project service")
                except Exception as e:
                    logger.error(f"Failed to delete file record from project service: {e}")
                
                # Delete from storage service
                try:
                    storage_result = await client.delete_document_storage(project_id, filename)
                    deleted_files_count = len(storage_result.get("deleted_files", []))
                    results["total_deleted_files"] += deleted_files_count
                    logger.info(f"Deleted {deleted_files_count} files from storage for {filename}")
                except Exception as e:
                    logger.warning(f"Failed to delete files from storage for {filename}: {e}")
                
                # Delete embeddings from vector service
                try:
                    vector_result = await client.delete_document_vectors(project_id, filename)
                    embeddings_deleted = vector_result.get("deleted_count", 0)
                    results["total_deleted_embeddings"] += embeddings_deleted
                    logger.info(f"Deleted {embeddings_deleted} embeddings for document {filename}")
                except Exception as e:
                    logger.warning(f"Failed to delete embeddings for {filename}: {e}")
                
                # Delete graph data from graph service
                try:
                    graph_result = await client.delete_document_graph(project_id, filename)
                    graph_nodes_deleted = graph_result.get("nodes_deleted", 0)
                    results["total_deleted_graph_nodes"] += graph_nodes_deleted
                    logger.info(f"Deleted {graph_nodes_deleted} nodes for document {filename}")
                except Exception as e:
                    logger.warning(f"Failed to delete graph data for {filename}: {e}")
                
                # Publish document_deleted event
                try:
                    event_bus = get_event_bus()
                    await event_bus.publish("document_deleted", {
                        "project_id": project_id,
                        "file_id": file_id,
                        "filename": filename,
                        "deleted_count": 1
                    })
                except Exception as e:
                    logger.warning(f"Failed to publish document_deleted event: {e}")
                
                results["successful_deletions"].append({
                    "file_id": file_id,
                    "filename": filename
                })
                
            except Exception as e:
                logger.error(f"Failed to delete file {file_id}: {e}")
                results["failed_deletions"].append({
                    "file_id": file_id,
                    "error": str(e)
                })
        
        return {
            "message": f"Bulk deletion completed: {len(results['successful_deletions'])} successful, {len(results['failed_deletions'])} failed",
            "project_id": project_id,
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Bulk file deletion failed for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Bulk file deletion failed: {str(e)}")

# =====================================================================================
# KNOWLEDGE BASE QUERY ENDPOINTS - Route to Vector/Graph Services
# =====================================================================================

@router.post("/api/projects/{project_id}/query", summary="Query project knowledge base")
async def query_project_knowledge(project_id: str, query_request: QueryRequest):
    """Query project knowledge base and return an answer string.

    Prefers knowledge-service if available; falls back to vector-service search and
    concatenates snippets when knowledge-service isn't reachable.
    Returns envelope: { answer, project_id }.
    """
    try:
        client = await get_service_client()

        # 1) Try knowledge-service project QA first (if running)
        try:
            ks_resp = await client._make_request(
                "POST",
                "knowledge",
                f"/qa/projects/{project_id}",
                json={"question": query_request.query, "context_limit": query_request.limit or 5, "use_llm": bool(getattr(query_request, 'use_llm', False))},
            )
            # Accept either { qa: { answer }} or { answer }
            answer = None
            if isinstance(ks_resp, dict):
                if ks_resp.get("qa") and isinstance(ks_resp["qa"], dict):
                    answer = ks_resp["qa"].get("answer")
                if not answer:
                    answer = ks_resp.get("answer")
            if answer:
                return {"answer": answer, "project_id": project_id}
        except Exception as ks_err:
            logger.warning(f"Knowledge-service not available, falling back to vector search: {ks_err}")

        # 2) Fallback: vector-service search → simple concatenation
        try:
            try:
                result = await client.vector_search(project_id, query_request.query, query_request.limit or 5)
            except Exception as e1:
                logger.warning(f"Primary vector search failed, trying hybrid: {e1}")
                result = await client.hybrid_search(project_id, query_request.query, query_request.limit or 5)

            docs = []
            for item in (result or {}).get("results", []) or []:
                content = item.get("content") or ""
                meta = item.get("metadata") or {}
                filename = meta.get("filename", "unknown")
                if content:
                    docs.append(f"[From {filename}]: {content}")

            if not docs:
                answer = "No relevant information found in the knowledge base."
            else:
                answer = "\n\n".join(docs)
            return {"answer": answer, "project_id": project_id}
        except Exception as e:
            logger.error(f"Vector search failed for {project_id}: {e}")
            raise HTTPException(status_code=502, detail="Vector search service unavailable")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Knowledge query failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

@router.post("/api/projects/{project_id}/chat", summary="Chat with project knowledge base")
async def chat_project_knowledge(project_id: str, request: ChatRequest):
    """Gateway chat endpoint that proxies to knowledge-service project QA.
    Returns a consistent envelope: { answer, project_id }.
    """
    try:
        client = await get_service_client()
        try:
            ks_resp = await client._make_request(
                "POST",
                "knowledge",
                f"/qa/projects/{project_id}",
                json={"question": request.question, "context_limit": request.context_limit or 5, "use_llm": bool(getattr(request, 'use_llm', False))},
            )
            # Normalize response
            answer = None
            if isinstance(ks_resp, dict):
                if ks_resp.get("qa") and isinstance(ks_resp["qa"], dict):
                    answer = ks_resp["qa"].get("answer")
                if not answer:
                    answer = ks_resp.get("answer")
            if not answer:
                answer = "No relevant information found in the knowledge base."
            return {"answer": answer, "project_id": project_id}
        except Exception as ks_err:
            logger.warning(f"Knowledge-service chat failed, falling back to vector search: {ks_err}")
            # Fallback to the same logic as /query
            try:
                result = await client.vector_search(project_id, request.question, 5)
            except Exception as e1:
                logger.warning(f"Primary vector search failed, trying hybrid: {e1}")
                result = await client.hybrid_search(project_id, request.question, 5)

            docs = []
            for item in (result or {}).get("results", []) or []:
                content = item.get("content") or ""
                meta = item.get("metadata") or {}
                filename = meta.get("filename", "unknown")
                if content:
                    docs.append(f"[From {filename}]: {content}")
            answer = "No relevant information found in the knowledge base." if not docs else "\n\n".join(docs)
            return {"answer": answer, "project_id": project_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")

@router.get("/api/projects/{project_id}/graph", summary="Get project graph")
async def get_project_graph(project_id: str, type: Optional[str] = None):
    """Get project graph via Graph Service"""
    try:
        client = await get_service_client()
        # If infrastructure view is requested, use graph-service topology endpoint
        if type and type.lower() == "infrastructure":
            return await client._make_request(
                "GET", "graph", f"/api/graphs/projects/{project_id}/topology"
            )
        # Otherwise return full graph
        return await client.get_project_graph(project_id)
    except Exception as e:
        logger.error(f"Get graph failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get graph: {str(e)}")

@router.get("/api/projects/{project_id}/pyvis", summary="Get project graph (pyvis format)")
async def get_project_graph_pyvis(project_id: str):
    """Get project graph in pyvis/vis-network friendly structure via Graph Service"""
    try:
        client = await get_service_client()
        return await client._make_request(
            "GET", "graph", f"/api/graphs/projects/{project_id}/pyvis"
        )
    except Exception as e:
        logger.error(f"Get pyvis graph failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get pyvis graph: {str(e)}")

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

# -------------------------------------------------------------------------------------
# Crew run endpoints (document/assessment) and workflow status/cancel - proxy to AI Agent
# -------------------------------------------------------------------------------------

@router.post("/api/projects/{project_id}/crews/document/run", summary="Run document crew")
async def gateway_run_document_crew(project_id: str, payload: Dict[str, Any], request: Request):
    """Proxy to AI Agent Service to start a document-generation crew run.
    Rewrites ws_endpoint to a direct ai-agent-service URL for WebSocket connections.
    """
    try:
        client = await get_service_client()
        resp = await client._make_request(
            "POST",
            "ai_agent",
            f"/api/agents/projects/{project_id}/crews/document/run",
            json=payload,
        )
        # Ensure ws endpoint is absolute to ai-agent-service to avoid WS proxying issues
        try:
            job_id = resp.get("job_id")
            if job_id:
                resp["ws_endpoint"] = f"{client.services['ai_agent']}/api/agents/workflows/{job_id}/ws"
                # Keep status endpoint via gateway for convenience
                resp["status_endpoint"] = f"/api/agents/workflows/{job_id}/status"
        except Exception:
            pass
        return resp
    except Exception as e:
        logger.error(f"Gateway document crew run failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start document crew: {str(e)}")

@router.post("/api/projects/{project_id}/crews/assessment/run", summary="Run assessment crew")
async def gateway_run_assessment_crew(project_id: str, payload: Dict[str, Any], request: Request):
    """Proxy to AI Agent Service to start an assessment crew run.
    Rewrites ws_endpoint to a direct ai-agent-service URL for WebSocket connections.
    """
    try:
        client = await get_service_client()
        resp = await client._make_request(
            "POST",
            "ai_agent",
            f"/api/agents/projects/{project_id}/crews/assessment/run",
            json=payload,
        )
        try:
            job_id = resp.get("job_id")
            if job_id:
                resp["ws_endpoint"] = f"{client.services['ai_agent']}/api/agents/workflows/{job_id}/ws"
                resp["status_endpoint"] = f"/api/agents/workflows/{job_id}/status"
        except Exception:
            pass
        return resp
    except Exception as e:
        logger.error(f"Gateway assessment crew run failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start assessment crew: {str(e)}")

@router.get("/api/agents/workflows/{job_id}/status", summary="Get crew workflow status")
async def gateway_get_workflow_status(job_id: str):
    """Proxy workflow status fetch to AI Agent Service"""
    try:
        client = await get_service_client()
        return await client._make_request("GET", "ai_agent", f"/api/agents/workflows/{job_id}/status")
    except Exception as e:
        logger.error(f"Gateway get workflow status failed for {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get workflow status: {str(e)}")

@router.post("/api/agents/workflows/{job_id}/cancel", summary="Cancel crew workflow")
async def gateway_cancel_workflow(job_id: str):
    """Request cancellation of a crew workflow via AI Agent Service"""
    try:
        client = await get_service_client()
        return await client._make_request("POST", "ai_agent", f"/api/agents/workflows/{job_id}/cancel")
    except Exception as e:
        logger.error(f"Gateway cancel workflow failed for {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel workflow: {str(e)}")

# =====================================================================================
# CREW CONFIG ENDPOINTS - Proxy to AI Agent Service (8008)
# =====================================================================================

@router.get("/api/crew-config", summary="Get crew configuration")
async def gateway_get_crew_config():
    try:
        client = await get_service_client()
        return await client._make_request("GET", "ai_agent", "/api/crew-config")
    except Exception as e:
        logger.error(f"Crew config fetch failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load crew configuration: {str(e)}")

@router.post("/api/crew-config/reload", summary="Reload crew configuration")
async def gateway_reload_crew_config():
    try:
        client = await get_service_client()
        return await client._make_request("POST", "ai_agent", "/api/crew-config/reload")
    except Exception as e:
        logger.error(f"Crew config reload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reload crew configuration: {str(e)}")

@router.put("/api/crew-config", summary="Update crew configuration")
async def gateway_update_crew_config(payload: Dict[str, Any]):
    try:
        client = await get_service_client()
        return await client._make_request("PUT", "ai_agent", "/api/crew-config", json=payload)
    except Exception as e:
        logger.error(f"Crew config update failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update crew configuration: {str(e)}")

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

@router.get("/api/llm/configurations", summary="Get all LLM configurations")
async def get_llm_configurations():
    """Get all LLM configurations via Backend LLM Router"""
    try:
        # Import and use the backend LLM router directly for consistency
        from app.routers.llm_router import get_llm_configurations as backend_get_llm
        return await backend_get_llm()
    except Exception as e:
        logger.error(f"Get LLM configurations failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get LLM configurations: {str(e)}")

@router.post("/api/llm/configurations", summary="Create LLM configuration")
async def create_llm_configuration(payload: dict):
    """Create new LLM configuration via Backend LLM Router (handles data type conversion)"""
    try:
        # Import and use the backend LLM router directly to ensure proper data type conversion
        from app.routers.llm_router import create_llm_configuration as backend_create_llm
        return await backend_create_llm(payload)
    except Exception as e:
        logger.error(f"Create LLM configuration failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create LLM configuration: {str(e)}")

@router.put("/api/llm/configurations/{config_id}", summary="Update LLM configuration")
async def update_llm_configuration(config_id: str, payload: dict):
    """Update LLM configuration via Backend LLM Router (handles data type conversion)"""
    try:
        # Import and use the backend LLM router directly to ensure proper data type conversion
        from app.routers.llm_router import update_llm_configuration as backend_update_llm
        return await backend_update_llm(config_id, payload)
    except Exception as e:
        logger.error(f"Update LLM configuration failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update LLM configuration: {str(e)}")

@router.delete("/api/llm/configurations/{config_id}", summary="Delete LLM configuration")
async def delete_llm_configuration(config_id: str):
    """Delete LLM configuration via Backend LLM Router"""
    try:
        # Import and use the backend LLM router directly for consistency
        from app.routers.llm_router import delete_llm_configuration as backend_delete_llm
        return await backend_delete_llm(config_id)
    except Exception as e:
        logger.error(f"Delete LLM configuration failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete LLM configuration: {str(e)}")

@router.get("/api/llm/models/{provider}", summary="Get models for provider")
async def get_provider_models(provider: str, api_key: Optional[str] = Query(None)):
    """Get available models for a provider via LLM Service"""
    try:
        client = await get_service_client()
        params = {}
        if api_key:
            params["api_key"] = api_key
        return await client._make_request("GET", "llm", f"/api/llm/models/{provider}", params=params)
    except Exception as e:
        logger.error(f"Get provider models failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get provider models: {str(e)}")

@router.post("/api/llm/test-llm-config", summary="Test LLM configuration")
async def test_llm_configuration(payload: dict):
    """Test LLM configuration via LLM Service"""
    try:
        client = await get_service_client()
        return await client._make_request("POST", "llm", "/api/llm/test-llm-config", json=payload)
    except Exception as e:
        logger.error(f"Test LLM configuration failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to test LLM configuration: {str(e)}")

@router.get("/api/llm/resolve", summary="Resolve LLM provider/model for a process and project")
async def resolve_llm_provider_model(process_type: str, project_id: Optional[str] = Query(None)):
    """Proxy to llm-service to resolve provider/model without instantiating an LLM."""
    try:
        client = await get_service_client()
        params = {"process_type": process_type}
        if project_id:
            params["project_id"] = project_id
        return await client._make_request("GET", "llm", "/api/llm/resolve", params=params)
    except Exception as e:
        logger.error(f"Resolve LLM failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to resolve LLM: {str(e)}")

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

@router.get("/api/projects/{project_id}/files/browse", summary="Browse MinIO directory structure")
async def browse_project_files(project_id: str, path: Optional[str] = Query("")):
    """Browse MinIO directory structure for a project with file/folder navigation"""
    try:
        from app.core.storage_service import get_storage
        storage = get_storage()
        
        # Ensure path is safe (no .. traversal)
        if path and (".." in path or path.startswith("/")):
            raise HTTPException(status_code=400, detail="Invalid path")
        
        # Get all files in the project
        prefix = f"projects/{project_id}/"
        if path:
            prefix += f"{path.strip('/')}/"
        
        files = []
        directories = set()
        
        try:
            # List objects from MinIO
            if storage.client:
                objects = storage.client.list_objects(storage.bucket, prefix=prefix, recursive=False)
                
                for obj in objects:
                    # Remove project prefix from object name
                    relative_path = obj.object_name[len(f"projects/{project_id}/"):]
                    
                    if not relative_path:
                        continue
                    
                    # Determine if it's a file or directory marker
                    if relative_path.endswith('/'):
                        # Directory marker
                        dir_name = relative_path.rstrip('/')
                        if '/' in dir_name:
                            dir_name = dir_name.split('/')[-1]
                        if dir_name and dir_name not in directories:
                            directories.add(dir_name)
                            files.append({
                                "name": dir_name,
                                "type": "directory",
                                "path": f"{path.rstrip('/') + '/' if path else ''}{dir_name}",
                                "size": None,
                                "last_modified": None
                            })
                    else:
                        # Regular file
                        if '/' in relative_path:
                            # File is in a subdirectory, add the directory if not already added
                            dir_parts = relative_path.split('/')
                            if len(dir_parts) > 1:
                                first_dir = dir_parts[0]
                                if first_dir not in directories:
                                    directories.add(first_dir)
                                    files.append({
                                        "name": first_dir,
                                        "type": "directory", 
                                        "path": f"{path.rstrip('/') + '/' if path else ''}{first_dir}",
                                        "size": None,
                                        "last_modified": None
                                    })
                            
                            # Only show files in current directory level
                            if len(dir_parts) == 1 or (path and relative_path.startswith(path.rstrip('/') + '/')):
                                file_name = dir_parts[-1]
                                files.append({
                                    "name": file_name,
                                    "type": "file",
                                    "path": relative_path,
                                    "size": obj.size,
                                    "last_modified": obj.last_modified.isoformat() if obj.last_modified else None
                                })
                        else:
                            # File in current directory
                            files.append({
                                "name": relative_path,
                                "type": "file",
                                "path": relative_path,
                                "size": obj.size,
                                "last_modified": obj.last_modified.isoformat() if obj.last_modified else None
                            })
            
            # Sort: directories first, then files, alphabetically
            files.sort(key=lambda x: (x["type"] == "file", x["name"].lower()))
            
            return {
                "files": files,
                "current_path": path
            }
            
        except Exception as storage_error:
            logger.error(f"MinIO access error: {storage_error}")
            return {
                "files": [],
                "current_path": path,
                "error": "Unable to access storage"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Browse project files failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to browse files: {str(e)}")

@router.get("/api/storage/projects/{project_id}/download/{file_path:path}", summary="Download file from MinIO")
async def download_project_file(project_id: str, file_path: str):
    """Download a file from MinIO storage"""
    try:
        from app.core.storage_service import get_storage
        from fastapi.responses import StreamingResponse
        import io
        
        storage = get_storage()
        
        # Ensure file path is safe
        if ".." in file_path or file_path.startswith("/"):
            raise HTTPException(status_code=400, detail="Invalid file path")
        
        # Construct full object key
        object_key = f"projects/{project_id}/{file_path}"
        
        try:
            if storage.client:
                # Get object from MinIO
                response = storage.client.get_object(storage.bucket, object_key)
                
                # Read data
                data = response.read()
                response.close()
                response.release_conn()
                
                # Determine content type
                content_type = "application/octet-stream"
                if file_path.lower().endswith(('.pdf',)):
                    content_type = "application/pdf"
                elif file_path.lower().endswith(('.txt', '.md')):
                    content_type = "text/plain"
                elif file_path.lower().endswith(('.json',)):
                    content_type = "application/json"
                elif file_path.lower().endswith(('.png',)):
                    content_type = "image/png"
                elif file_path.lower().endswith(('.jpg', '.jpeg')):
                    content_type = "image/jpeg"
                
                # Get filename for download
                filename = file_path.split('/')[-1]
                
                return StreamingResponse(
                    io.BytesIO(data),
                    media_type=content_type,
                    headers={"Content-Disposition": f"attachment; filename={filename}"}
                )
            else:
                raise HTTPException(status_code=503, detail="Storage service not available")
                
        except Exception as storage_error:
            logger.error(f"Download error: {storage_error}")
            raise HTTPException(status_code=404, detail="File not found or inaccessible")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download file failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to download file: {str(e)}")

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

# =====================================================================================
# CORRELATION TRACE ENDPOINT - Verify propagation across services
# =====================================================================================

@router.get("/api/correlation/trace", summary="Trace correlation headers across services")
async def correlation_trace(project_id: Optional[str] = Query(None)):
    """Calls representative endpoints on multiple services and returns the
    X-Correlation-ID observed in each response. This helps validate universal propagation.
    """
    client = await get_service_client()
    results: Dict[str, Any] = {}

    async def capture(service: str, method: str, path: str):
        try:
            resp = await client.request_raw(method, service, path)
            cid = resp.headers.get("x-correlation-id") or resp.headers.get("X-Correlation-ID")
            try:
                logger.info(f"Correlation trace: service={service} method={method} path={path} status={resp.status_code} cid={cid}")
            except Exception:
                pass
            results[service] = {
                "status": resp.status_code,
                "x_correlation_id": cid,
                "content_type": resp.headers.get("content-type"),
            }
        except Exception as e:
            results[service] = {"status": "error", "error": str(e)}

    # Choose lightweight endpoints per service
    await capture("project", "GET", "/health")
    await capture("document", "GET", "/health")
    await capture("reporting", "GET", "/health")
    await capture("vector", "GET", "/health")
    await capture("graph", "GET", "/health")
    await capture("llm", "GET", "/health")
    await capture("ai_agent", "GET", "/health")
    await capture("storage", "GET", "/health")
    await capture("websocket", "GET", "/health")

    # Optional: project-specific call to exercise typical flow
    if project_id:
        await capture("graph", "GET", f"/api/graphs/projects/{project_id}/stats")
    # Use the vector stats endpoint (GET) to avoid 422 from body-less POST search
    await capture("vector", "GET", f"/api/vectors/projects/{project_id}/stats")

    return {"trace": results}

# Stats Events Endpoint for Real-Time Updates
class StatsEvent(BaseModel):
    project_id: str
    event_type: str
    additional_data: Optional[Dict[str, Any]] = None
    timestamp: str

@router.post("/api/stats/events", summary="Receive stats events from microservices (internal)")
async def receive_stats_event(event: StatsEvent):
    """Internal endpoint for microservices to trigger real-time stats updates."""
    try:
        from app.core.stats_service import get_stats_service
        stats_service = get_stats_service()
        
        # Trigger event-driven stats update
        await stats_service.update_project_stats(
            project_id=event.project_id,
            event_type=event.event_type,
            additional_data=event.additional_data
        )
        
        logger.debug(f"Processed stats event: {event.project_id} - {event.event_type}")
        return {"status": "success", "message": "Stats event processed"}
        
    except Exception as e:
        logger.error(f"Failed to process stats event: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process stats event: {e}")
