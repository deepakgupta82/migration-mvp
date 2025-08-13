import os, json, logging, asyncio, traceback
import tempfile
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Body, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from app.core.project_service import get_project_service, get_llm_configurations_from_db
from app.core.graph_service import GraphService
from app.core.rag_service import RAGService
from app.core.llm_factory import get_project_llm
from app.utils.sanitization import sanitize_agent_output, sanitize_for_latex
from app.core.event_bus import get_event_bus
from app.core.process_ws import get_process_ws_manager
from app.core.storage_service import get_storage

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
    name: Optional[str] = "Project Summary"
    description: Optional[str] = None
    include_sections: Optional[List[str]] = None  # future extension

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
        graph_service = GraphService()
        nodes_query = "MATCH (n {project_id: $project_id}) RETURN n"
        relationships_query = "MATCH (a {project_id: $project_id})-[r]->(b {project_id: $project_id}) RETURN a, r, b"
        nodes_result = graph_service.execute_query(nodes_query, {"project_id": project_id})
        relationships_result = graph_service.execute_query(relationships_query, {"project_id": project_id})
        nodes = []
        for record in nodes_result or []:
            node = record["n"]
            nodes.append({
                "id": node.get("name", str(node.id)),
                "label": node.get("name", "Unknown"),
                "type": list(node.labels)[0] if node.labels else "Unknown",
                "properties": dict(node)
            })
        edges = []
        for record in relationships_result or []:
            a = record["a"]; b = record["b"]; r = record["r"]
            edges.append({
                "source": a.get("name", str(a.id)),
                "target": b.get("name", str(b.id)),
                "label": r.type,
                "properties": dict(r)
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
        project_service = get_project_service()
        project = project_service.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        graph_service = GraphService()
        cleared = {"chromadb_embeddings":0,"neo4j_nodes":0,"neo4j_relationships":0}
        # Chroma
        try:
            import chromadb
            chroma_path = os.getenv("CHROMA_DB_PATH", "./data/chroma_db")
            client = chromadb.PersistentClient(path=chroma_path)
            collection_name = f"project_{project_id}"
            try:
                collection = client.get_collection(name=collection_name)
                cleared["chromadb_embeddings"] = collection.count()
                client.delete_collection(name=collection_name)
                client.create_collection(name=collection_name, metadata={"description":f"Document embeddings for project {project_id}"})
            except Exception as ce:
                if "does not exist" not in str(ce):
                    logger.warning(f"Chroma collection access issue: {ce}")
        except Exception as e:
            logger.warning(f"Chroma clear error: {e}")
        # Neo4j
        try:
            if graph_service.driver:
                node_count = graph_service.execute_query("MATCH (n {project_id: $project_id}) RETURN count(n) as c", {"project_id": project_id})
                if node_count:
                    cleared["neo4j_nodes"] = node_count[0]["c"]
                rel_count = graph_service.execute_query("MATCH (a {project_id: $project_id})-[r]-(b {project_id: $project_id}) RETURN count(r) as c", {"project_id": project_id})
                if rel_count:
                    cleared["neo4j_relationships"] = rel_count[0]["c"]
                graph_service.execute_query("MATCH (n {project_id: $project_id}) DETACH DELETE n", {"project_id": project_id})
        except Exception as e:
            logger.warning(f"Neo4j clear error: {e}")
        # Stats file cleanup
        try:
            project_dir = os.path.join(UPLOAD_ROOT, f"project_{project_id}")
            stats_file = os.path.join(project_dir, "processing_stats.json")
            if os.path.exists(stats_file):
                os.remove(stats_file)
        except Exception as e:
            logger.warning(f"Stats file cleanup error: {e}")
        # Publish event to trigger stats update
        try:
            await get_event_bus().publish("data_cleared", {"project_id": project_id})
        except Exception as e:
            logger.warning(f"Failed to publish data_cleared event: {e}")
        return {"message":"Project data cleared successfully","project_id":project_id, "chromadb_embeddings":cleared["chromadb_embeddings"], "neo4j_nodes":cleared["neo4j_nodes"], "neo4j_relationships":cleared["neo4j_relationships"], "cleared_items":cleared}
    except Exception as e:
        logger.error(f"Clear data failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error clearing data: {e}")

@router.post("/{project_id}/query", response_model=QueryResponse, summary="Query project knowledge base")
async def query_project_knowledge(project_id: str, query_request: QueryRequest):
    try:
        project_service = get_project_service()
        project = project_service.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        try:
            llm = get_project_llm(project)
        except Exception as llm_error:
            raise HTTPException(status_code=500, detail=f"LLM error: {llm_error}")
        rag_service = RAGService(project_id, llm)
        answer = rag_service.query(query_request.question)
        return QueryResponse(answer=answer, project_id=project_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query failed {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error querying knowledge base: {e}")

@router.get("/{project_id}/service-status", summary="Service status for project")
async def get_project_service_status(project_id: str):
    try:
        project_service = get_project_service()
        project = project_service.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        try:
            llm = get_project_llm(project)
            rag_service = RAGService(project_id, llm)
            status = rag_service.get_service_status()
            rag_service.cleanup()
            return status
        except Exception as llm_error:
            rag_service = RAGService(project_id, llm=None)
            status = rag_service.get_service_status()
            status.setdefault("llm", {})["error"] = str(llm_error)
            rag_service.cleanup()
            return status
    except Exception as e:
        logger.error(f"Service status failed {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Service status check failed: {e}")

@router.get("/{project_id}/report", response_model=ReportResponse, summary="Get project report")
async def get_project_report(project_id: str):
    try:
        project_service = get_project_service()
        project = project_service.get_project(project_id)
        report_content = getattr(project, 'report_content', None)
        if not report_content:
            raise HTTPException(status_code=404, detail="Report content not found for this project")
        return ReportResponse(project_id=project_id, report_content=report_content)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fetch report failed {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching report: {e}")

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

@router.post("/{project_id}/generate-report", summary="Generate infrastructure report")
async def generate_infrastructure_report(project_id: str, request: dict = None):
    logger.info(f"Generating infrastructure report for project {project_id}")
    request_data = request or {}
    try:
        project_service = get_project_service()
        project = project_service.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        # Count uploaded files from storage
        storage = get_storage()
        files = []
        try:
            files = storage.list_files(project_id, "uploads_raw")
        except Exception:
            pass
        if not files:
            raise HTTPException(status_code=400, detail="No documents available for report generation")
        report_content = f"""# Infrastructure Assessment Report\n\n## Project Overview\nProject ID: {project_id}\nProject Name: {project.name}\nGenerated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n## Document Analysis\nProcessed {len(files)} documents:\n\n"""
        for f in files:
            report_content += f"- {f}\n"
        report_content += """\n## Infrastructure Components\n- Compute Resources\n- Storage Systems\n- Network Components\n- Applications\n\n## Migration Recommendations\n1. Assessment Phase\n2. Planning Phase\n3. Execution Phase\n4. Validation Phase\n\n## Risk Assessment\n- Low / Medium / High risk items summarized\n\n---\nGenerated by Nagarro's Ascent Platform\n"""
        report_filename = f"infrastructure_assessment_{project_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.md"
        # Upload to object storage
        storage.upload_text(project_id, "generated_reports", report_filename, report_content, content_type="text/markdown; charset=utf-8")
        try:
            project_service.update_project(project_id, {"report_content": report_content, "status": "completed"})
        except Exception as e:
            logger.warning(f"Update project with report failed: {e}")
        return {"success":True,"message":f"Report generated for project {project_id}","project_id":project_id,"name":request_data.get('name','Infrastructure Assessment Report'),"download_urls":{"markdown":f"/api/projects/{project_id}/download/{report_filename}"},"markdown_filename":report_filename,"content_preview":report_content[:500]+("..." if len(report_content)>500 else "")}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Report generation failed {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {e}")

# ---------------------------------------------------------------------------
# IMPLEMENTED: Process project documents (previously 501)
# ---------------------------------------------------------------------------
@router.post("/{project_id}/process-documents", summary="Process project documents (async job)")
async def process_project_documents(project_id: str, request: Request):
    import uuid
    job_id = str(uuid.uuid4())
    try:
        process_ws = get_process_ws_manager()
        await process_ws.broadcast(project_id, f"START: processing documents for project {project_id} (job_id={job_id})")
        logger.info(f"process-documents: start for {project_id} (job_id={job_id})")
        project_service = get_project_service()
        project = project_service.get_project(project_id)
        if not project:
            await process_ws.broadcast(project_id, "ERROR: Project not found")
            raise HTTPException(status_code=404, detail="Project not found")
        # Spawn background task for processing
        async def background_process():
            try:
                # Load chunking/embedding config
                config_path = os.path.join(os.getcwd(), "config", "config.local.json")
                chunking_strategy = "semantic"
                chunk_size = 3500
                embedding_model = "all-MiniLM-L6-v2"
                try:
                    with open(config_path, "r", encoding="utf-8") as cf:
                        cfg = json.load(cf)
                        proc_cfg = cfg.get("processing", {})
                        chunking_strategy = proc_cfg.get("chunking_strategy", chunking_strategy)
                        chunk_size = proc_cfg.get("chunk_size", chunk_size)
                        embedding_model = proc_cfg.get("embedding_model", embedding_model)
                except Exception as ce:
                    logger.warning(f"Could not load processing config: {ce}")
                logger.info(f"Using chunking_strategy={chunking_strategy}, chunk_size={chunk_size}, embedding_model={embedding_model}")
                await process_ws.broadcast(project_id, f"CONFIG: chunking_strategy={chunking_strategy}, chunk_size={chunk_size}, embedding_model={embedding_model}")
                # Begin streaming updates
                await process_ws.broadcast(project_id, f"PROCESSING: initializing services for job_id={job_id}")
                # Verify project exists
                project_service = get_project_service()
                project = project_service.get_project(project_id)
                storage = get_storage()
                saved_files: List[str] = []
                errors: Dict[str, str] = {}
                json_files: List[str] = []
                content_type = (request.headers.get("content-type") or "").lower()
                uploaded_blobs: List[tuple[str, bytes]] = []
                if content_type.startswith("multipart/"):
                    try:
                        form = await request.form()
                        keys = list(form.keys())
                        await process_ws.broadcast(project_id, f"PROCESSING: form keys={keys}")
                        count_files = 0
                        seen_items = []
                        for key, value in form.multi_items():
                            seen_items.append((key, value))
                        for key_name in ("files", "file", "upload", "uploads", "document", "documents", "files[]"):
                            vals = form.getlist(key_name) if hasattr(form, 'getlist') else []
                            for v in vals:
                                seen_items.append((key_name, v))
                        for key, value in seen_items:
                            items = value if isinstance(value, list) else [value]
                            for item in items:
                                if hasattr(item, 'filename') and hasattr(item, 'read'):
                                    try:
                                        data = await item.read() if callable(getattr(item, 'read', None)) else b''
                                    except TypeError:
                                        data = item.read()
                                    count_files += 1
                                    fname = getattr(item, 'filename', 'upload')
                                    if data:
                                        uploaded_blobs.append((fname, data))
                                        try:
                                            storage.upload_bytes(project_id, "uploads_raw", fname, data, content_type=getattr(item, 'content_type', None))
                                        except Exception as store_err:
                                            logger.warning(f"Upload to storage failed for {fname}: {store_err}")
                                        saved_files.append(fname)
                                        await process_ws.broadcast(project_id, f"UPLOADED: {fname}")
                        await process_ws.broadcast(project_id, f"PROCESSING: total file-like items found={count_files}")
                    except Exception as fe:
                        logger.debug(f"Form parse failed: {fe}")
                else:
                    try:
                        body = await request.json()
                        if isinstance(body, dict):
                            json_files = [f.get('filename') for f in (body.get('files') or []) if isinstance(f, dict) and f.get('filename')]
                        await process_ws.broadcast(project_id, f"PROCESSING: json filenames={json_files}")
                    except Exception as je:
                        logger.debug(f"JSON parse failed: {je}")
                candidate_files: List[str] = []
                try:
                    if not json_files and not uploaded_blobs:
                        candidate_files = storage.list_files(project_id, "uploads_raw")
                except Exception as le:
                    logger.debug(f"List storage files failed: {le}")
                    candidate_files = []
                await process_ws.broadcast(project_id, f"PROCESSING: uploaded_blobs={len(uploaded_blobs)} candidate_files={len(candidate_files)} json_files={len(json_files)}")
                if not candidate_files and not json_files and not uploaded_blobs:
                    await process_ws.broadcast(project_id, "ERROR: No documents provided or found")
                    return
                try:
                    llm = None
                    try:
                        llm = get_project_llm(project)
                    except Exception as llm_err:
                        logger.warning(f"LLM initialization failed for project {project_id}: {llm_err}")
                    rag_service = RAGService(project_id, llm)
                except Exception as init_err:
                    await process_ws.broadcast(project_id, f"ERROR: init failed: {init_err}")
                    return
                processed: List[str] = []
                reprocess_flag = str((request.query_params.get("reprocess") or "false")).lower() in ("1","true","yes")
                for (nm, blob) in uploaded_blobs:
                    import tempfile as _tf
                    ext = os.path.splitext(nm)[1] or ""
                    tmp = _tf.NamedTemporaryFile(delete=False, suffix=ext)
                    try:
                        tmp.write(blob)
                    finally:
                        tmp.close()
                    try:
                        result_msg = rag_service.add_file(tmp.name, reprocess=reprocess_flag, source_name=nm)
                        await process_ws.broadcast(project_id, f"PROCESSED: {nm}")
                        processed.append(nm)
                    except Exception as pe:
                        errors[nm] = str(pe)
                        await process_ws.broadcast(project_id, f"ERROR: process {nm}: {pe}")
                    finally:
                        try:
                            os.unlink(tmp.name)
                        except Exception:
                            pass
                for jname in json_files:
                    try:
                        obj, _, _ = storage.download(project_id, "uploads_raw", jname)
                        import tempfile as _tf
                        ext = os.path.splitext(jname)[1] or ""
                        tmp = _tf.NamedTemporaryFile(delete=False, suffix=ext)
                        try:
                            while True:
                                chunk = obj.read(8192)
                                if not chunk:
                                    break
                                tmp.write(chunk)
                        finally:
                            try:
                                obj.close()
                            except Exception:
                                pass
                            tmp.close()
                        result_msg = rag_service.add_file(tmp.name, reprocess=reprocess_flag, source_name=jname)
                        await process_ws.broadcast(project_id, f"PROCESSED: {jname}")
                        processed.append(jname)
                    except Exception as pe:
                        errors[jname] = str(pe)
                        await process_ws.broadcast(project_id, f"ERROR: process {jname}: {pe}")
                    finally:
                        try:
                            os.unlink(tmp.name)
                        except Exception:
                            pass
                if not json_files and not uploaded_blobs:
                    for fname in candidate_files:
                        try:
                            obj, _, _ = storage.download(project_id, "uploads_raw", fname)
                            import tempfile as _tf
                            ext = os.path.splitext(fname)[1] or ""
                            tmp = _tf.NamedTemporaryFile(delete=False, suffix=ext)
                            try:
                                while True:
                                    chunk = obj.read(8192)
                                    if not chunk:
                                        break
                                    tmp.write(chunk)
                            finally:
                                try:
                                    obj.close()
                                except Exception:
                                    pass
                                tmp.close()
                            result_msg = rag_service.add_file(tmp.name, reprocess=reprocess_flag, source_name=fname)
                            await process_ws.broadcast(project_id, f"PROCESSED: {fname}")
                            processed.append(fname)
                        except Exception as pe:
                            errors[fname] = str(pe)
                            await process_ws.broadcast(project_id, f"ERROR: process {fname}: {pe}")
                        finally:
                            try:
                                os.unlink(tmp.name)
                            except Exception:
                                pass
                embeddings_count = 0
                try:
                    embeddings_count = rag_service.collection.count() if getattr(rag_service, 'collection', None) else 0
                except Exception:
                    pass
                graph_nodes = 0; graph_relationships = 0
                try:
                    graph_service = GraphService()
                    node_count = graph_service.execute_query("MATCH (n {project_id: $project_id}) RETURN count(n) as c", {"project_id": project_id})
                    if node_count:
                        graph_nodes = node_count[0]['c']
                    rel_count = graph_service.execute_query("MATCH (a {project_id: $project_id})-[r]-(b {project_id: $project_id}) RETURN count(r) as c", {"project_id": project_id})
                    if rel_count:
                        graph_relationships = rel_count[0]['c']
                except Exception as ge:
                    logger.warning(f"Graph stats error for {project_id}: {ge}")
                stats_path = os.path.join(UPLOAD_ROOT, f"project_{project_id}", "processing_stats.json")
                stats_payload = {
                    "embeddings": embeddings_count,
                    "graph_nodes": graph_nodes,
                    "graph_relationships": graph_relationships,
                    "processing_status": "completed" if not errors else "partial_success",
                    "last_updated": datetime.now(timezone.utc).isoformat()
                }
                try:
                    with open(stats_path, 'w', encoding='utf-8') as sf:
                        json.dump(stats_payload, sf, indent=2)
                except Exception as se:
                    logger.warning(f"Failed to write stats for {project_id}: {se}")
                try:
                    await get_event_bus().publish("documents_processed", {"project_id": project_id, "processed": len(processed)})
                    await process_ws.broadcast(project_id, f"COMPLETE: processed {len(processed)} files")
                    await process_ws.broadcast(project_id, "PROCESSING_COMPLETED")
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"Background document processing failed {project_id}: {e}")
                await process_ws.broadcast(project_id, f"ERROR: {e}")
        asyncio.create_task(background_process())
        # Immediately return job_id so UI can poll status or subscribe to updates
        return {"job_id": job_id, "project_id": project_id, "status": "started"}
    except Exception as e:
        logger.error(f"Failed to start document processing job {project_id}: {e}")
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
