import os, json, logging, asyncio, traceback
import tempfile
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Body, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
# Gateway pattern: Only import service client, no direct business logic
from app.core.service_client import get_service_client
from app.core.event_bus import get_event_bus

logger = logging.getLogger("platform.project_analysis_router")

router = APIRouter(prefix="/api/projects", tags=["project-analysis"])

UPLOAD_ROOT = os.getenv("UPLOAD_ROOT_TMP") or tempfile.gettempdir()
os.makedirs(UPLOAD_ROOT, exist_ok=True)

class QueryRequest(BaseModel):
    question: str

class QueryResponse(BaseModel):
    answer: str
    project_id: str

class GraphResponse(BaseModel):
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]

class ReportResponse(BaseModel):
    project_id: str
    report_content: str

# New models for document processing / generation
class ProcessDocumentsResponse(BaseModel):
    project_id: str
    processed_files: List[str]
    uploaded_files: List[str] = []
    errors: Dict[str, str]
    embeddings: Optional[int] = 0
    graph_nodes: Optional[int] = 0
    graph_relationships: Optional[int] = 0
    processing_status: str
    last_updated: str

class GenerateDocumentRequest(BaseModel):
    template_id: Optional[str] = None
    name: Optional[str] = "Project Summary"
    description: Optional[str] = None
    format: Optional[str] = "markdown"
    output_type: Optional[str] = "markdown"
    request_id: Optional[str] = None

class GenerateDocumentResponse(BaseModel):
    success: bool
    project_id: str
    name: str
    markdown_filename: str
    download_urls: Dict[str, str]
    content_preview: str

@router.get("/{project_id}/graph", response_model=GraphResponse, summary="Get project graph")
async def get_project_graph(project_id: str, type: Optional[str] = None):
    try:
        # Delegate to graph-service via ServiceClient
        from app.core.service_client import get_service_client
        client = await get_service_client()
        graph_data = await client.get_project_graph(project_id)

        # Build node id -> name map and normalized node list
        nodes = []
        id_to_name = {}
        for n in (graph_data.get("nodes") or []):
            node_id = n.get("id") or n.get("node_id") or n.get("name")
            name = n.get("name") or n.get("properties", {}).get("name") or str(node_id)
            node_type = None
            labels = n.get("labels") or n.get("label") or []
            if isinstance(labels, list) and labels:
                node_type = labels[0]
            elif isinstance(labels, str):
                node_type = labels
            nodes.append({
                "id": name,
                "label": name,
                "type": node_type or n.get("type") or "Unknown",
                "properties": n,
            })
            id_to_name[node_id] = name

        # Map relationships to edges using id->name
        edges = []
        for r in (graph_data.get("relationships") or []):
            src_id = r.get("source_id") or r.get("source")
            tgt_id = r.get("target_id") or r.get("target")
            label = r.get("type") or r.get("label") or r.get("relationship") or "RELATED_TO"
            edges.append({
                "source": id_to_name.get(src_id, str(src_id)),
                "target": id_to_name.get(tgt_id, str(tgt_id)),
                "label": label,
                "properties": r,
            })
        if type == "infrastructure":
            infra_types = {'hostname','server','database','application','service','network','storage','load_balancer','firewall','switch','router','cluster','system_identifier','component_identifier','host','instance','virtual_machine','container','pod','node','endpoint'}
            infra_nodes = []
            for n in nodes:
                node_type = n.get('properties', {}).get('type','').lower()
                node_label = n.get('type','').lower()
                if (node_type in infra_types or node_label in infra_types or any(t in node_type for t in infra_types) or any(t in node_label for t in infra_types)):
                    infra_nodes.append(n)
            infra_ids = {n['id'] for n in infra_nodes}
            infra_edges = [e for e in edges if e['source'] in infra_ids and e['target'] in infra_ids]
            nodes, edges = infra_nodes, infra_edges
        return GraphResponse(nodes=nodes, edges=edges)
    except Exception as e:
        logger.error(f"Graph fetch failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching graph: {e}")

@router.post("/{project_id}/clear-data", summary="Clear embeddings and graph data")
async def clear_project_data(project_id: str):
    try:
        # Use service client to check if project exists
        client = await get_service_client()
        project = await client.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Delegate clears to microservices via service client
        cleared = {"weaviate_embeddings": 0, "neo4j_nodes": 0, "neo4j_relationships": 0}
        
        # Vector collection deletion via service client
        try:
            vres = await client.delete_collection(project_id)
            cleared["weaviate_embeddings"] = int(vres.get("document_count", 0)) if isinstance(vres, dict) else 0
        except Exception as e:
            logger.warning(f"Vector-service clear error: {e}")
        
        # Graph deletion via service client
        try:
            gres = await client.delete_project_graph(project_id)
            if isinstance(gres, dict):
                cleared["neo4j_nodes"] = int(gres.get("nodes_deleted", 0))
        except Exception as e:
            logger.warning(f"Graph-service clear error: {e}")
        
        # Publish event to trigger stats update
        try:
            await get_event_bus().publish("data_cleared", {"project_id": project_id})
        except Exception as e:
            logger.warning(f"Failed to publish data_cleared event: {e}")
        
        return {
            "message": "Project data cleared successfully",
            "project_id": project_id, 
            "weaviate_embeddings": cleared["weaviate_embeddings"], 
            "neo4j_nodes": cleared["neo4j_nodes"], 
            "neo4j_relationships": cleared["neo4j_relationships"], 
            "cleared_items": cleared
        }
    except Exception as e:
        logger.error(f"Clear data failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error clearing data: {e}")

@router.post("/{project_id}/query", response_model=QueryResponse, summary="Query project knowledge base")
async def query_project_knowledge(project_id: str, query_request: QueryRequest):
    try:
        # Use service client to verify project exists
        client = await get_service_client()
        project = await client.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Perform vector search via service client
        try:
            # Try primary vector search first
            result = await client.vector_search(project_id, query_request.question, limit=5)
        except Exception as e:
            logger.warning(f"Primary vector search failed, trying hybrid: {e}")
            try:
                result = await client.hybrid_search(project_id, query_request.question, limit=5)
            except Exception as e2:
                logger.error(f"Both vector search methods failed: {e2}")
                raise HTTPException(status_code=500, detail="Vector search service unavailable")
        
        # Process search results
        docs = []
        for item in result.get("results", []) or []:
            content = item.get("content") or ""
            meta = item.get("metadata") or {}
            filename = meta.get("filename", "unknown")
            if content:
                docs.append(f"[From {filename}]: {content}")
        
        if not docs:
            answer = "No relevant information found in the knowledge base."
        else:
            # For now, return concatenated results without LLM synthesis
            # TODO: Add LLM synthesis via llm-service when available
            answer = "\n\n".join(docs)
        
        return QueryResponse(answer=answer, project_id=project_id)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query failed {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error querying knowledge base: {e}")

@router.get("/{project_id}/service-status", summary="Service status for project")
async def get_project_service_status(project_id: str):
    try:
        # Use service client to verify project exists and get service statuses
        client = await get_service_client()
        project = await client.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Get health status from all services
        health_status = await client.check_all_services_health()
        
        # Get project-specific vector collection info
        vector_status = {"status": "unknown", "document_count": 0}
        try:
            vector_info = await client._make_request("GET", "vector", f"/api/vectors/projects/{project_id}/collection")
            vector_status = {
                "status": vector_info.get("status", "unknown"),
                "document_count": vector_info.get("document_count", 0)
            }
        except Exception as e:
            logger.warning(f"Could not get vector status for project {project_id}: {e}")
        
        # Get project-specific graph info
        graph_status = {"status": "unknown", "node_count": 0}
        try:
            graph_info = await client.get_project_graph(project_id)
            graph_status = {
                "status": "connected" if graph_info else "empty",
                "node_count": len(graph_info.get("nodes", []))
            }
        except Exception as e:
            logger.warning(f"Could not get graph status for project {project_id}: {e}")
        
        return {
            "project_id": project_id,
            "services": health_status,
            "vector_store": vector_status,
            "graph_store": graph_status,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Service status check failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting service status: {e}")

# REMOVED: Markdown report retrieval endpoint - replaced with JSONL analysis endpoints
# Use /api/documents/{project_id}/analysis for new JSONL-based analysis retrieval

@router.get("/{project_id}/stats", summary="Project processing statistics")
async def get_project_stats(project_id: str):
    try:
        project_service = get_project_service()
        project = project_service.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        storage = get_storage()
        # Prefer object storage counts
        try:
            files_count = len(storage.list_files(project_id, "uploads_raw"))
        except Exception:
            # Fallback to local temp directory scan
            project_dir = os.path.join(UPLOAD_ROOT, f"project_{project_id}")
            files_count = 0
            if os.path.exists(project_dir):
                files_count = len([f for f in os.listdir(project_dir) if os.path.isfile(os.path.join(project_dir, f)) and not f.endswith('.json')])
        # Deliverables via object storage
        try:
            deliverables_count = len(storage.list_files(project_id, "generated_reports", suffix_filters=(".docx", ".pdf", ".md")))
        except Exception:
            deliverables_dir = os.path.join(UPLOAD_ROOT, f"project_{project_id}", "deliverables")
            deliverables_count = 0
            if os.path.exists(deliverables_dir):
                deliverables_count = len([f for f in os.listdir(deliverables_dir) if f.endswith(('.docx', '.pdf', '.md'))])
        # Stats file (kept local for now)
        project_dir = os.path.join(UPLOAD_ROOT, f"project_{project_id}")
        stats_file = os.path.join(project_dir, "processing_stats.json")
        processing_results = {"embeddings":0,"graph_nodes":0,"graph_relationships":0,"processing_status":"ready"}
        if os.path.exists(stats_file):
            try:
                with open(stats_file,'r') as f:
                    processing_results = json.load(f)
            except Exception as e:
                logger.warning(f"Stats read error {project_id}: {e}")
        agent_interactions = 0
        assessment_logs_file = os.path.join(project_dir, "assessment_logs.json")
        if os.path.exists(assessment_logs_file):
            try:
                with open(assessment_logs_file,'r') as f:
                    logs = json.load(f)
                    agent_interactions = len([l for l in logs if l.get('type') in ['agent_action','tool_result','agent_finish']])
            except Exception as e:
                logger.warning(f"Assessment log read error {project_id}: {e}")
        return {
            "project_id": project_id,
            "embeddings": processing_results.get("embeddings",0),
            "graph_nodes": processing_results.get("graph_nodes",0),
            "graph_relationships": processing_results.get("graph_relationships",0),
            "agent_interactions": agent_interactions,
            "deliverables": deliverables_count,
            "files_processed": files_count,
            "processing_status": processing_results.get("processing_status","ready"),
            "last_updated": processing_results.get("last_updated", datetime.now(timezone.utc).isoformat())
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Stats failed {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get project stats: {e}")

# REMOVED: Markdown report generation endpoint - replaced with JSONL analysis endpoints
# Use /api/documents/{project_id}/analysis/batch for new JSONL-based analysis

# ---------------------------------------------------------------------------
# IMPLEMENTED: Process project documents (previously 501)
# ---------------------------------------------------------------------------
@router.post("/{project_id}/process-documents", summary="Process project documents (proxied to document-service)")
async def process_project_documents(project_id: str, request: Request):
    """Deprecated monolithic route now proxies to document-service.
    Behavior:
    - If multipart/form-data contains files, upload them to document-service and process-selected.
    - If JSON body has file_names and optional reprocess, process-selected.
    - Otherwise, trigger process-all.
    Returns a job descriptor from document-service.
    """
    from app.core.service_client import get_service_client
    import uuid
    job_id = str(uuid.uuid4())
    process_ws = get_process_ws_manager()
    try:
        # Validate project exists
        project_service = get_project_service()
        project = project_service.get_project(project_id)
        if not project:
            await process_ws.broadcast(project_id, "ERROR: Project not found")
            raise HTTPException(status_code=404, detail="Project not found")

        await process_ws.broadcast(project_id, f"START: proxy processing for project {project_id} (job_id={job_id})")

        client = await get_service_client()
        content_type = (request.headers.get("content-type") or "").lower()

        reprocess_flag = False
        selected_files: List[str] = []

        # Case 1: multipart uploads, forward files then process-selected
        if content_type.startswith("multipart/"):
            try:
                form = await request.form()
                upload_items = []
                # Collect UploadFile items from common keys
                for key in ("files", "file", "upload", "uploads", "document", "documents", "files[]"):
                    values = form.getlist(key) if hasattr(form, "getlist") else []
                    for v in values:
                        upload_items.append(v)
                # Fallback: iterate all form items
                if not upload_items:
                    for _, v in form.multi_items():
                        upload_items.append(v)

                files_to_send = [it for it in upload_items if hasattr(it, "read")]
                if files_to_send:
                    await process_ws.broadcast(project_id, f"UPLOADING: {len(files_to_send)} files")
                    upload_result = await client.upload_documents(project_id, files_to_send)
                    # Derive filenames from returned payload or input
                    try:
                        uploaded = upload_result.get("uploaded_files") or []
                        selected_files = [f.get("filename") for f in uploaded if isinstance(f, dict) and f.get("filename")]
                    except Exception:
                        selected_files = [getattr(f, "filename", "") for f in files_to_send if getattr(f, "filename", "")]
                else:
                    await process_ws.broadcast(project_id, "WARNING: No files found in multipart form")
            except Exception as e:
                logger.warning(f"Multipart parse/upload failed: {e}")

        # Case 2: JSON body specifying file_names and reprocess
        elif content_type.startswith("application/json"):
            try:
                body = await request.json()
                if isinstance(body, dict):
                    selected_files = body.get("file_names") or body.get("files") or []
                    # Allow array of strings or array of objects with filename
                    if selected_files and isinstance(selected_files[0], dict):
                        selected_files = [f.get("filename") for f in selected_files if f.get("filename")]
                    reprocess_flag = bool(body.get("reprocess", False))
            except Exception as e:
                logger.debug(f"JSON body parse failed: {e}")

        # Decide which document-service endpoint to call
        try:
            if selected_files:
                await process_ws.broadcast(project_id, f"PROCESSING-SELECTED: {len(selected_files)} files (reprocess={reprocess_flag})")
                result = await client.process_documents(project_id, file_list=selected_files, reprocess=reprocess_flag)
            else:
                await process_ws.broadcast(project_id, f"PROCESSING-ALL: starting (reprocess={reprocess_flag})")
                result = await client.process_documents(project_id, file_list=None, reprocess=reprocess_flag)
        except Exception as call_err:
            logger.error(f"Document-service process call failed: {call_err}")
            raise HTTPException(status_code=502, detail=f"Document service error: {call_err}")

        # Optionally notify via WebSocket and return
        try:
            await process_ws.broadcast(project_id, "PROCESSING_STARTED")
        except Exception:
            pass

        # Attach deprecation header via response object isn't trivial here; include hint in payload
        if isinstance(result, dict):
            result.setdefault("_deprecated_hint", "/api/projects/{project_id}/process-documents is proxied; prefer /api/documents/... routes")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to proxy document processing for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start processing job: {e}")


@router.get("/{project_id}/uploads", summary="List uploaded files for a project")
async def list_project_uploads(project_id: str):
    try:
        # Verify project exists
        project_service = get_project_service()
        if not project_service.get_project(project_id):
            raise HTTPException(status_code=404, detail="Project not found")
        storage = get_storage()
        files = storage.list_files(project_id, "uploads_raw")
        return {"project_id": project_id, "files": files, "count": len(files)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"List uploads failed {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list uploads: {e}")

# ---------------------------------------------------------------------------
# IMPLEMENTED: Generate project document using RAGService (like entity extraction)
# ---------------------------------------------------------------------------
@router.post("/{project_id}/generate-document", response_model=GenerateDocumentResponse, summary="Generate project document via AI Agent service")
async def generate_project_document(project_id: str, request: GenerateDocumentRequest):
    logger.info(f"Proxying document generation for project {project_id}: template_id={request.template_id} name={request.name}")
    from app.core.service_client import get_service_client
    process_ws = get_process_ws_manager()
    try:
        # Validate project
        project_service = get_project_service()
        project = project_service.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Broadcast start
        try:
            await process_ws.broadcast(project_id, {
                "type": "DOCUMENT_GENERATION_STARTED",
                "project_id": project_id,
                "template_id": request.template_id,
                "name": request.name,
            })
        except Exception:
            pass

        payload = request.dict()
        client = await get_service_client()
        agent_result = await client.generate_document(project_id, payload)

        if not agent_result.get("success"):
            raise HTTPException(status_code=500, detail=agent_result.get("error") or "Document generation failed")

        try:
            await process_ws.broadcast(project_id, {
                "type": "DOCUMENT_GENERATION_COMPLETED",
                "project_id": project_id,
                "template_id": request.template_id,
                "name": request.name,
                "filename": agent_result.get("markdown_filename")
            })
        except Exception:
            pass

        return GenerateDocumentResponse(
            success=True,
            project_id=project_id,
            name=agent_result.get("name", request.name or "Document"),
            markdown_filename=agent_result.get("markdown_filename"),
            download_urls=agent_result.get("download_urls", {}),
            content_preview=(agent_result.get("content_preview") or "")[:1000]
        )
    except HTTPException:
        try:
            await process_ws.broadcast(project_id, {
                "type": "DOCUMENT_GENERATION_FAILED",
                "project_id": project_id,
                "template_id": request.template_id,
                "name": request.name,
            })
        except Exception:
            pass
        raise
    except Exception as e:
        logger.error(f"Proxy document generation failed {project_id}: {e}")
        try:
            await process_ws.broadcast(project_id, {
                "type": "DOCUMENT_GENERATION_FAILED",
                "project_id": project_id,
                "template_id": request.template_id,
                "name": request.name,
                "error": str(e)
            })
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Failed to generate document: {e}")

# ---------------------------------------------------------------------------
# IMPLEMENTED: Download generated documents and reports
# ---------------------------------------------------------------------------
# REMOVED: Markdown report download endpoint - replaced with JSONL analysis endpoints
# Use /api/documents/{project_id}/analysis/{analysis_id} for new JSONL-based analysis retrieval
