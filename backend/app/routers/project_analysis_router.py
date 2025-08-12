import os, json, logging, asyncio, traceback
import tempfile
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Body
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
@router.post("/{project_id}/process-documents", response_model=ProcessDocumentsResponse, summary="Process project documents")
async def process_project_documents(project_id: str, files: Optional[List[UploadFile]] = File(None), body: Optional[Dict[str, Any]] = Body(default=None)):
    try:
        process_ws = get_process_ws_manager()
        await process_ws.broadcast(project_id, f"START: processing documents for project {project_id}")
        # Verify project exists
        project_service = get_project_service()
        project = project_service.get_project(project_id)
        if not project:
            await process_ws.broadcast(project_id, "ERROR: Project not found")
            raise HTTPException(status_code=404, detail="Project not found")
        # Ensure project directory for local stats/metadata
        project_dir = os.path.join(UPLOAD_ROOT, f"project_{project_id}")
        os.makedirs(project_dir, exist_ok=True)
        storage = get_storage()
        saved_files: List[str] = []
        errors: Dict[str, str] = {}
        json_files: List[str] = []
        if body and isinstance(body, dict):
            json_files = [f.get('filename') for f in (body.get('files') or []) if isinstance(f, dict) and f.get('filename')]
        # Save uploaded files to object storage (and temp for processing)
        if files:
            for uf in files:
                try:
                    data = await uf.read()
                    storage.upload_bytes(project_id, "uploads_raw", uf.filename, data, content_type=getattr(uf, 'content_type', None))
                    saved_files.append(uf.filename)
                    await process_ws.broadcast(project_id, f"UPLOADED: {uf.filename}")
                    try:
                        await get_event_bus().publish("document_uploaded", {"project_id": project_id})
                    except Exception:
                        pass
                except Exception as fe:
                    errors[uf.filename] = f"Save failed: {fe}"
                    await process_ws.broadcast(project_id, f"ERROR: failed saving {uf.filename}: {fe}")
        # Determine files to process
        candidate_files: List[str] = []
        try:
            if not json_files:
                candidate_files = storage.list_files(project_id, "uploads_raw")
        except Exception:
            candidate_files = []
        if not candidate_files and not json_files and not saved_files:
            await process_ws.broadcast(project_id, "ERROR: No documents provided or found")
            raise HTTPException(status_code=422, detail="No documents provided. Upload multipart 'files' or send JSON { files: [{filename}] } ")
        # Initialize RAG service + LLM
        try:
            llm = None
            try:
                llm = get_project_llm(project)
            except Exception as llm_err:
                logger.warning(f"LLM initialization failed for project {project_id}: {llm_err}")
            rag_service = RAGService(project_id, llm)
        except Exception as init_err:
            await process_ws.broadcast(project_id, f"ERROR: init failed: {init_err}")
            raise HTTPException(status_code=500, detail=f"Failed to initialize processing services: {init_err}")
        processed: List[str] = []
        # Helper to download a file from storage to a temp path and process
        async def _process_storage_file(name: str):
            try:
                obj, _, _ = storage.download(project_id, "uploads_raw", name)
                import tempfile as _tf
                tmp = _tf.NamedTemporaryFile(delete=False)
                try:
                    # obj may be a stream (MinIO); read in chunks
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
                result_msg = rag_service.add_file(tmp.name)
                logger.info(f"Processed {name}: {result_msg}")
                await process_ws.broadcast(project_id, f"PROCESSED: {name}")
                processed.append(name)
            except Exception as pe:
                logger.error(f"Processing failed for {name}: {pe}")
                errors[name] = str(pe)
                await process_ws.broadcast(project_id, f"ERROR: process {name}: {pe}")
            finally:
                try:
                    os.unlink(tmp.name)
                except Exception:
                    pass
        # Process explicit JSON file names (from storage)
        for jname in json_files:
            await _process_storage_file(jname)
        # Also process discovered files when none explicitly selected
        if not json_files:
            for fname in candidate_files:
                await _process_storage_file(fname)
        # Collect stats
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
        stats_path = os.path.join(project_dir, "processing_stats.json")
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
        return ProcessDocumentsResponse(
            project_id=project_id,
            processed_files=processed,
            errors=errors,
            embeddings=embeddings_count,
            graph_nodes=graph_nodes,
            graph_relationships=graph_relationships,
            processing_status=stats_payload['processing_status'],
            last_updated=stats_payload['last_updated']
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document processing failed {project_id}: {e}")
        try:
            await get_process_ws_manager().broadcast(project_id, f"ERROR: {e}")
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Failed to process documents: {e}")

# ---------------------------------------------------------------------------
# IMPLEMENTED: Generate custom project document (previously 501)
# ---------------------------------------------------------------------------
@router.post("/{project_id}/generate-document", response_model=GenerateDocumentResponse, summary="Generate a project document")
async def generate_document(project_id: str, request: GenerateDocumentRequest):
    try:
        project_service = get_project_service()
        project = project_service.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        # Load stats if available (local)
        project_dir = os.path.join(UPLOAD_ROOT, f"project_{project_id}")
        os.makedirs(project_dir, exist_ok=True)
        stats_file = os.path.join(project_dir, "processing_stats.json")
        stats_data = {}
        if os.path.exists(stats_file):
            try:
                with open(stats_file, 'r', encoding='utf-8') as sf:
                    stats_data = json.load(sf)
            except Exception:
                pass
        # Attempt LLM summary
        llm_summary = ""
        try:
            llm = get_project_llm(project)
            prompt = (
                f"Provide a concise executive summary for project '{getattr(project, 'name', project_id)}' focusing on infrastructure, migration considerations, and risk factors. "
                f"Base this on processed documents if available. Include 3-5 key recommendations."
            )
            raw = llm.invoke(prompt) if hasattr(llm, 'invoke') else ""
            # unwrap AIMessage or similar
            content = getattr(raw, 'content', raw)
            llm_summary = sanitize_agent_output(content if isinstance(content, str) else str(content))
        except Exception as le:
            logger.warning(f"LLM summary failed for {project_id}: {le}")
        document_name = request.name or "Project Summary"
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        safe_base = ''.join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in document_name).strip().replace(' ', '_') or 'document'
        filename = f"{safe_base}_{timestamp}.md"
        content = f"""# {document_name}\n\nProject ID: {project_id}\nGenerated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n## Overview\n{request.description or 'Custom project document generated by platform.'}\n\n## Processing Summary\n- Embeddings: {stats_data.get('embeddings', 'n/a')}\n- Graph Nodes: {stats_data.get('graph_nodes', 'n/a')}\n- Graph Relationships: {stats_data.get('graph_relationships', 'n/a')}\n- Last Updated: {stats_data.get('last_updated', 'n/a')}\n\n## Executive Summary\n{llm_summary or 'LLM summary unavailable - ensure LLM configuration is valid and documents are processed.'}\n\n## Recommendations\n1. Validate infrastructure inventory.\n2. Prioritize migration sequencing.\n3. Mitigate high-risk dependencies early.\n4. Automate testing & validation.\n5. Establish rollback strategy.\n\n---\nGenerated by Nagarro's Ascent Platform\n"""
        # Upload to object storage
        storage = get_storage()
        storage.upload_text(project_id, "generated_reports", filename, content, content_type="text/markdown; charset=utf-8")
        return GenerateDocumentResponse(
            success=True,
            project_id=project_id,
            name=document_name,
            markdown_filename=filename,
            download_urls={"markdown": f"/api/projects/{project_id}/download/{filename}"},
            content_preview=content[:500] + ("..." if len(content) > 500 else "")
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document generation failed {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate document: {e}")

@router.get("/{project_id}/download/{filename}", summary="Download generated document")
async def download_project_file(project_id: str, filename: str):
    try:
        project_service = get_project_service()
        project = project_service.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        storage = get_storage()
        try:
            obj, content_type, size = storage.download(project_id, "generated_reports", filename)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="File not found")
        # Infer content type by extension if missing
        if not content_type or content_type == "application/octet-stream":
            if filename.endswith('.md'):
                content_type = "text/markdown"
            elif filename.endswith('.pdf'):
                content_type = "application/pdf"
            elif filename.endswith('.docx'):
                content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        def iterfile():
            try:
                while True:
                    chunk = obj.read(8192)
                    if not chunk:
                        break
                    yield chunk
            finally:
                try:
                    obj.close()
                except Exception:
                    pass
        headers = {"Content-Disposition": f"attachment; filename={filename}"}
        return StreamingResponse(iterfile(), media_type=content_type, headers=headers)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download failed {project_id}/{filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to download file: {e}")
