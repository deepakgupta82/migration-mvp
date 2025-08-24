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

from app.core.service_client import get_service_client

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

@router.get("/api/health/containers", summary="Container / service stats (proxy)")
async def api_health_containers():
    """Proxy to backend /health/containers for frontend convenience."""
    try:
        backend_base = os.getenv("BACKEND_PUBLIC_URL", "http://localhost:8000")
        async with httpx.AsyncClient(timeout=httpx.Timeout(8.0, connect=2.0)) as ac:
            r = await ac.get(f"{backend_base}/health/containers")
            return JSONResponse(status_code=r.status_code, content=r.json())
    except Exception as e:
        logger.error(f"Proxy health containers failed: {e}")
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
        return await client.list_projects(include_stats=include_stats)
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
        return await client.get_project(project_id)
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

@router.get("/api/llm/configurations", summary="Get LLM configurations")
async def get_llm_configurations():
    """Get LLM configurations via Project Service"""
    try:
        client = await get_service_client()
        # Fixed endpoint path - project service uses /llm-configurations not /api/projects/llm-configurations
        return await client._make_request("GET", "project", "/llm-configurations")
    except Exception as e:
        logger.error(f"Get LLM configurations failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get LLM configurations: {str(e)}")

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
