from fastapi import APIRouter, HTTPException, Request, Body, Query
from typing import List, Optional
import asyncio
from app.core.project_service import get_project_service, ProjectCreate
import logging
import requests
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.crew_logger import get_db
from app.models.crew_interaction import CrewInteractionModel
import os, requests
from asyncio import Semaphore, wait_for, TimeoutError as AsyncTimeoutError

logger = logging.getLogger("platform.projects_router")

router = APIRouter(prefix="/api/projects", tags=["projects"])

@router.get("", include_in_schema=False)
async def list_projects_no_slash():
    return await list_projects()

@router.get("/", summary="List all projects")
async def list_projects(include_stats: bool = Query(False)):
    try:
        project_service = get_project_service()
        projects = project_service.list_projects()
        if include_stats:
            from app.core.stats_service import get_stats_service
            stats_service = get_stats_service()
            enriched = []

            # Limit concurrency to avoid DB overload
            limit = int(os.getenv("PROJECT_LIST_STATS_CONCURRENCY", "6"))
            sem = Semaphore(limit)

            async def enrich(p):
                pid = getattr(p, 'id', None) or (p.get('id') if isinstance(p, dict) else None)
                base = p.model_dump() if hasattr(p, 'model_dump') else (p if isinstance(p, dict) else p.__dict__)
                if not pid:
                    return base
                try:
                    async with sem:
                        # Short timeout per project
                        timeout_s = float(os.getenv("PROJECT_LIST_PER_STAT_TIMEOUT", "2.0"))
                        stat = await wait_for(stats_service.get_project_stats_cached(pid), timeout=timeout_s)
                    if stat:
                        base['files_count'] = stat.get('files_count')
                        base['embeddings_count'] = stat.get('embeddings_count')
                        base['stats_stale'] = stat.get('stale')
                except AsyncTimeoutError:
                    base['stats_stale'] = True
                except Exception:
                    base['stats_stale'] = True
                return base

            enriched = await asyncio.gather(*(enrich(p) for p in projects))
            return enriched
        return projects
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list projects: {str(e)}")

@router.post("/", summary="Create a new project")
async def create_project(request: dict):
    try:
        project_service = get_project_service()
        # Map friendly UI aliases to canonical context fields
        if "rfp" in request and "rfp_summary" not in request:
            request["rfp_summary"] = request.pop("rfp")
        if "timeline" in request and "timeline_notes" not in request:
            request["timeline_notes"] = request.pop("timeline")
        project = project_service.create_project(ProjectCreate(**request))
        try:
            from app.core.event_bus import get_event_bus
            await get_event_bus().publish("project_created", {"project_id": getattr(project, 'id', None) or project.get('id')})
        except Exception:
            pass
        return project
    except Exception as e:
        logger.error(f"Project creation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create project: {str(e)}")

@router.post("", include_in_schema=False)
async def create_project_alias(request: dict):
    """Alias to allow POST /api/projects without trailing slash"""
    return await create_project(request)

@router.delete("/{project_id}", summary="Delete a project")
async def delete_project(project_id: str):
    try:
        project_service = get_project_service()
        result = project_service.delete_project(project_id)
        try:
            from app.core.event_bus import get_event_bus
            await get_event_bus().publish("project_deleted", {"project_id": project_id})
        except Exception:
            pass
        return result
    except Exception as e:
        logger.error(f"Error deleting project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete project: {str(e)}")


from app.core.llm_config import get_llm_configurations_from_db
from app.core.service_client import get_service_client

@router.get("/stats", summary="Get project statistics")
async def get_projects_stats():
    try:
        project_service = get_project_service()
        projects = project_service.list_projects()
        total_projects = len(projects)
        status_counts = {}
        for project in projects:
            status = project.status
            status_counts[status] = status_counts.get(status, 0) + 1
        return {
            "total_projects": total_projects,
            "status_breakdown": status_counts,
            "active_projects": status_counts.get("running", 0),
            "completed_projects": status_counts.get("completed", 0),
            "pending_projects": status_counts.get("initiated", 0)
        }
    except Exception as e:
        logger.error(f"Error getting project stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting project stats: {str(e)}")

@router.get("/{project_id}", summary="Get a project by ID")
async def get_project(project_id: str):
    try:
        project_service = get_project_service()
        project = project_service.get_project(project_id)
        if hasattr(project, 'model_dump'):
            project_dict = project.model_dump()
        elif hasattr(project, 'dict'):
            project_dict = project.dict()
        elif hasattr(project, '__dict__'):
            project_dict = project.__dict__
        else:
            project_dict = dict(project)
        if project_dict.get('llm_api_key_id'):
            try:
                llm_configs = get_llm_configurations_from_db()
                llm_config = llm_configs.get(project_dict['llm_api_key_id'])
                if llm_config:
                    project_dict['llm_provider'] = llm_config.get('provider', 'unknown')
                    project_dict['llm_model'] = llm_config.get('model', 'unknown')
                    project_dict['llm_temperature'] = str(llm_config.get('temperature', 0.7))
                    project_dict['llm_max_tokens'] = str(llm_config.get('max_tokens', 4000))
                    logger.info(f"Expanded LLM config for project {project_id}: {llm_config.get('provider')}/{llm_config.get('model')}")
                else:
                    logger.warning(f"LLM config {project_dict['llm_api_key_id']} not found for project {project_id}")
                    project_dict['llm_provider'] = 'deleted'
                    project_dict['llm_model'] = 'deleted'
            except Exception as llm_error:
                logger.error(f"Error expanding LLM config for project {project_id}: {llm_error}")
                project_dict['llm_provider'] = 'error'
                project_dict['llm_model'] = 'error'
        logger.info(f"Retrieved project: {project_id} with LLM config: provider={project_dict.get('llm_provider')}, model={project_dict.get('llm_model')}")
        return project_dict
    except Exception as e:
        logger.error(f"Error getting project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting project: {str(e)}")

@router.post("/{project_id}/reindex-context", summary="Reindex project's freeform context into vectors and graph")
async def reindex_project_context(project_id: str):
    try:
        project_service = get_project_service()
        project = project_service.get_project(project_id)
        if hasattr(project, 'model_dump'):
            p = project.model_dump()
        elif hasattr(project, '__dict__'):
            p = project.__dict__
        else:
            p = dict(project)
        sections = []
        def add(label, key):
            val = p.get(key)
            if val:
                sections.append(f"## {label}\n\n{val}\n")
        add("Project Overview","project_overview")
        add("Project Intent","project_intent")
        add("Client Summary","client_summary")
        add("RFP Summary","rfp_summary")
        add("RFP Responses","rfp_responses")
        add("Expectations","expectations")
        add("Deliverables Summary","deliverables_summary")
        add("Timeline Notes","timeline_notes")
        content = "\n\n".join(sections).strip()
        if content:
            # Index into vector-service
            try:
                import anyio
                async def _index():
                    client = await get_service_client()
                    await client.create_vector_collection(project_id)
                    await client.add_documents_to_vectors(project_id, [{
                        "id": "__project_context.md",
                        "content": content,
                        "filename": "__project_context.md",
                        "source": "project_context"
                    }])
                anyio.run(_index)
            except Exception:
                logger.exception("Vector-service indexing failed for project context")
        # Upsert project node via graph-service extract endpoint using a small document
        try:
            import anyio, uuid as _uuid
            async def _upsert_graph():
                client = await get_service_client()
                doc_id = f"ctx-{_uuid.uuid4().hex[:8]}"
                payload = {
                    "document_content": content or (p.get("project_overview") or ""),
                    "filename": "__project_context.md",
                    "document_id": doc_id,
                }
                await client.extract_entities(project_id, payload)
            anyio.run(_upsert_graph)
        except Exception:
            logger.exception("Graph-service upsert of project context failed")
        return {"status": "ok", "indexed": bool(content)}
    except Exception as e:
        logger.error(f"Error reindexing project context: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reindex context: {e}")

@router.put("/{project_id}", summary="Update a project")
async def update_project(project_id: str, project_data: dict = Body(...)):
    try:
        project_service = get_project_service()
        # Map friendly UI aliases to canonical context fields
        if isinstance(project_data, dict):
            if "rfp" in project_data and "rfp_summary" not in project_data:
                project_data["rfp_summary"] = project_data.pop("rfp")
            if "timeline" in project_data and "timeline_notes" not in project_data:
                project_data["timeline_notes"] = project_data.pop("timeline")
        # Ensure correlation id is propagated
        headers = project_service._get_auth_headers()
        try:
            from app.core.logging_config import correlation_id_ctx
            cid = correlation_id_ctx.get("-")
            if cid and cid != "-":
                headers["X-Correlation-ID"] = cid
        except Exception:
            pass
        response = requests.put(
            f"{project_service.base_url}/projects/{project_id}",
            json=project_data,
            headers=headers
        )
        response.raise_for_status()
        result = response.json()
        # Fire-and-forget reindex of project context if any context fields changed
        try:
            ctx_keys = {"project_overview","project_intent","client_summary","rfp_summary","rfp_responses","expectations","deliverables_summary","timeline_notes"}
            if any(k in project_data for k in ctx_keys):
                import asyncio
                async def _reindex():
                    try:
                        # Build a single markdown blob from project context
                        p = result if isinstance(result, dict) else {}
                        sections = []
                        def add(label, key):
                            val = (project_data.get(key) if key in project_data else p.get(key))
                            if val:
                                sections.append(f"## {label}\n\n{val}\n")
                        add("Project Overview","project_overview")
                        add("Project Intent","project_intent")
                        add("Client Summary","client_summary")
                        add("RFP Summary","rfp_summary")
                        add("RFP Responses","rfp_responses")
                        add("Expectations","expectations")
                        add("Deliverables Summary","deliverables_summary")
                        add("Timeline Notes","timeline_notes")
                        content = "\n\n".join(sections).strip()
                        if not content:
                            return
                        # Index into vector DB via vector-service
                        import anyio
                        from app.core.service_client import get_service_client
                        async def _index():
                            client = await get_service_client()
                            await client.create_vector_collection(project_id)
                            await client.add_documents_to_vectors(project_id, [{
                                "id": "__project_context.md",
                                "content": content,
                                "filename": "__project_context.md",
                                "source": "project_context"
                            }])
                        try:
                            anyio.run(_index)
                        except Exception:
                            logger.exception("Vector-service indexing failed for project context (update)")
                        # Upsert in graph via graph-service extract
                        async def _upsert_graph():
                            client = await get_service_client()
                            await client.extract_entities(project_id, {
                                "document_content": content,
                                "filename": "__project_context.md",
                                "document_id": "ctx-update"
                            })
                        try:
                            anyio.run(_upsert_graph)
                        except Exception:
                            logger.exception("Graph-service upsert failed for project context (update)")
                    except Exception:
                        logger.exception("Project context reindex failed")
                try:
                    asyncio.create_task(_reindex())
                except RuntimeError:
                    # No running loop (sync context) – run inline best-effort
                    import anyio
                    try:
                        anyio.run(_reindex)
                    except Exception:
                        pass
        except Exception:
            logger.exception("Failed to schedule project context reindex")
        return result
    except Exception as e:
        logger.error(f"Error updating project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating project: {str(e)}")

@router.get("/{project_id}/crew-interactions", summary="List historic crew interactions with filters")
async def get_crew_interactions(
    project_id: str,
    task_id: Optional[str] = Query(None),
    conversation_id: Optional[str] = Query(None),
    agent_name: Optional[str] = Query(None),
    tool_name: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    interaction_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None)
):
    """Return historic interactions stored in DB."""
    db: Session = None
    try:
        db = get_db()
        query = db.query(CrewInteractionModel).filter(CrewInteractionModel.project_id == project_id)
        if task_id:
            query = query.filter(CrewInteractionModel.task_id == task_id)
        if conversation_id:
            query = query.filter(CrewInteractionModel.conversation_id == conversation_id)
        if agent_name:
            query = query.filter(CrewInteractionModel.agent_name == agent_name)
        if tool_name:
            query = query.filter(CrewInteractionModel.tool_name == tool_name)
        if status:
            query = query.filter(CrewInteractionModel.status == status)
        if interaction_type:
            query = query.filter(CrewInteractionModel.type == interaction_type)
        if search:
            like = f"%{search}%"
            from sqlalchemy import or_
            query = query.filter(or_(CrewInteractionModel.agent_name.ilike(like), CrewInteractionModel.tool_name.ilike(like), CrewInteractionModel.function_name.ilike(like)))
        total = query.count()
        rows = query.order_by(CrewInteractionModel.timestamp.desc()).offset(offset).limit(limit).all()
        interactions = []
        for r in rows:
            interactions.append({
                "id": str(r.id),
                "project_id": r.project_id,
                "task_id": r.task_id,
                "conversation_id": r.conversation_id,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                "type": r.type,
                "parent_id": str(r.parent_id) if r.parent_id else None,
                "depth": r.depth,
                "sequence": r.sequence,
                "crew_name": r.crew_name,
                "crew_description": r.crew_description,
                "crew_members": r.crew_members,
                "crew_goal": r.crew_goal,
                "agent_name": r.agent_name,
                "agent_role": r.agent_role,
                "agent_goal": r.agent_goal,
                "agent_backstory": r.agent_backstory,
                "agent_id": r.agent_id,
                "tool_name": r.tool_name,
                "tool_description": r.tool_description,
                "function_name": r.function_name,
                "request_data": r.request_data,
                "response_data": r.response_data,
                "reasoning_step": r.reasoning_step,
                "request_text": r.request_text,
                "response_text": r.response_text,
                "message_type": r.message_type,
                "token_usage": r.token_usage,
                "performance_metrics": r.performance_metrics,
                "status": r.status,
                "start_time": r.start_time.isoformat() if r.start_time else None,
                "end_time": r.end_time.isoformat() if r.end_time else None,
                "duration_ms": r.duration_ms,
                "error_message": r.error_message,
                "retry_count": r.retry_count,
                "interaction_metadata": r.interaction_metadata,
            })
        return {"total": total, "count": len(interactions), "interactions": interactions}
    except Exception as e:
        logger.error(f"Error fetching crew interactions for {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch interactions")
    finally:
        if db:
            db.close()

@router.get("/{project_id}/crew-interactions/stats", summary="Crew interactions statistics")
async def crew_interactions_stats(project_id: str, task_id: Optional[str] = None):
    db: Session = None
    try:
        db = get_db()
        base = db.query(CrewInteractionModel).filter(CrewInteractionModel.project_id == project_id)
        if task_id:
            base = base.filter(CrewInteractionModel.task_id == task_id)
        total = base.count()
        # Type counts
        type_rows = db.query(CrewInteractionModel.type, func.count(CrewInteractionModel.id)).filter(CrewInteractionModel.project_id == project_id)
        if task_id:
            type_rows = type_rows.filter(CrewInteractionModel.task_id == task_id)
        type_rows = type_rows.group_by(CrewInteractionModel.type).all()
        type_counts = {t: c for t, c in type_rows}
        # Status counts
        status_rows = db.query(CrewInteractionModel.status, func.count(CrewInteractionModel.id)).filter(CrewInteractionModel.project_id == project_id)
        if task_id:
            status_rows = status_rows.filter(CrewInteractionModel.task_id == task_id)
        status_rows = status_rows.group_by(CrewInteractionModel.status).all()
        status_counts = {s: c for s, c in status_rows}
        # Unique agents/tools
        unique_agents = db.query(func.count(func.distinct(CrewInteractionModel.agent_name))).filter(CrewInteractionModel.project_id == project_id, CrewInteractionModel.agent_name.isnot(None)).scalar() or 0
        unique_tools = db.query(func.count(func.distinct(CrewInteractionModel.tool_name))).filter(CrewInteractionModel.project_id == project_id, CrewInteractionModel.tool_name.isnot(None)).scalar() or 0
        # Token totals
        import json as _json
        total_tokens = 0
        total_cost = 0.0
        token_rows = base.filter(CrewInteractionModel.token_usage.isnot(None)).all()
        for r in token_rows:
            try:
                usage = r.token_usage
                if usage:
                    total_tokens += int(usage.get('total_tokens', 0))
                    total_cost += float(usage.get('estimated_cost', 0.0))
            except Exception:
                pass
        return {
            "project_id": project_id,
            "total_interactions": total,
            "type_counts": type_counts,
            "status_counts": status_counts,
            "unique_agents": unique_agents,
            "unique_tools": unique_tools,
            "total_tokens": total_tokens,
            "total_cost": total_cost,
        }
    except Exception as e:
        logger.error(f"Error computing crew interaction stats for {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to compute stats")
    finally:
        if db:
            db.close()

@router.get("/{project_id}/template-usage", summary="Get template usage for a project")
async def template_usage(project_id: str):
    """Aggregate template usage counts and last generated times.
    Sources:
      1. Project-service deliverables (usage fields if present)
      2. Generation history (deliverables generation requests) via project-service
      3. Local crew interactions token_usage (fallback not strictly needed here)
    """
    try:
        service = get_project_service()
        headers = service._get_auth_headers()
        base_url = service.base_url
        usage_map = {}
        last_generated_map = {}

        # Fetch project deliverables (templates)
        try:
            # Correlation propagation
            try:
                from app.core.logging_config import correlation_id_ctx
                cid = correlation_id_ctx.get("-")
                if cid and cid != "-":
                    headers["X-Correlation-ID"] = cid
            except Exception:
                pass
            r = requests.get(f"{base_url}/projects/{project_id}/deliverables", headers=headers, timeout=10)
            if r.ok:
                for t in r.json():
                    name = t.get('name') or t.get('id')
                    usage_map[name] = t.get('usage_count', 0)
                    if t.get('last_used'):
                        last_generated_map[name] = t.get('last_used')
        except Exception:
            pass

        # Fetch generation requests and count by template
        try:
            r2 = requests.get(f"{base_url}/projects/{project_id}/generation-requests", headers=headers, timeout=10)
            if r2.ok:
                for gr in r2.json():
                    tmpl_name = gr.get('template_name') or gr.get('template_id')
                    if tmpl_name:
                        usage_map[tmpl_name] = usage_map.get(tmpl_name, 0) + 1
                        # Track last generated timestamp (most recent)
                        ts = gr.get('requested_at') or gr.get('created_at')
                        if ts:
                            prev = last_generated_map.get(tmpl_name)
                            if not prev or ts > prev:
                                last_generated_map[tmpl_name] = ts
        except Exception:
            pass

        template_usage = [
            {
                "template_name": name,
                "usage_count": count,
                "last_generated": last_generated_map.get(name)
            }
            for name, count in sorted(usage_map.items())
        ]
        return {"project_id": project_id, "template_usage": template_usage}
    except Exception as e:
        logger.error(f"Error computing template usage for {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to compute template usage")

@router.get("/{project_id}/generation-history", summary="Get generation history for a project")
async def generation_history(project_id: str, limit: int = Query(100, ge=1, le=1000)):
    """Return generation request history from project-service."""
    try:
        service = get_project_service()
        headers = service._get_auth_headers()
        base_url = service.base_url
        history = []
        try:
            r = requests.get(f"{base_url}/projects/{project_id}/generation-requests", headers=headers, timeout=10)
            if r.ok:
                for gr in r.json()[:limit]:
                    history.append({
                        "id": gr.get('id'),
                        "template_id": gr.get('template_id'),
                        "template_name": gr.get('template_name'),
                        "requested_by": gr.get('requested_by'),
                        "requested_at": gr.get('requested_at') or gr.get('created_at'),
                        "status": gr.get('status'),
                        "progress": gr.get('progress'),
                        "download_url": gr.get('download_url'),
                        "error_message": gr.get('error_message')
                    })
        except Exception:
            pass
        return history
    except Exception as e:
        logger.error(f"Error retrieving generation history for {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get generation history")

@router.get("/../template-usage/global", include_in_schema=False)
async def deprecated_global_template_usage():
    raise HTTPException(status_code=404, detail="Moved to /api/template-usage/global")

# New global template usage proxy (outside project scope)
@router.get("/template-usage/global", summary="Global template usage (proxy)", tags=["templates"], include_in_schema=True)
async def global_template_usage():
    try:
        service = get_project_service()
        headers = service._get_auth_headers()
        try:
            from app.core.logging_config import correlation_id_ctx
            cid = correlation_id_ctx.get("-")
            if cid and cid != "-":
                headers["X-Correlation-ID"] = cid
        except Exception:
            pass
        r = requests.get(f"{service.base_url}/template-usage/global", headers=headers, timeout=10)
        if r.ok:
            return r.json()
        raise HTTPException(status_code=r.status_code, detail="Upstream error fetching global template usage")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Global template usage proxy failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch global template usage")

@router.get("/{project_id}/stats-snapshot", summary="Get fast cached project stats snapshot")
async def project_stats_snapshot(project_id: str):
    try:
        from app.core.stats_service import get_stats_service
        stats_service = get_stats_service()
        stats = await stats_service.get_project_stats_cached(project_id)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get project stats: {e}")

@router.get("/{project_id}/stats", include_in_schema=False)
async def project_stats_alias(project_id: str):
    """Alias to provide fast cached stats at legacy path"""
    return await project_stats_snapshot(project_id)


# --- New Upload and Processing Flow ---

from app.models.upload_models import ProcessRequest, ProcessResponse
from app.routers.project_analysis_router import process_project_documents
from datetime import datetime
import uuid
import json

@router.get("/{project_id}/uploaded-files", summary="List uploaded files waiting for processing")
async def list_uploaded_files(project_id: str):
    """Get list of files uploaded to storage but not yet processed"""
    try:
        from app.core.storage_service import get_storage
        storage = get_storage()
        
        # Get raw uploaded files
        raw_files = storage.list_files(project_id, "uploads_raw")
        
        # Get already processed files  
        processed_files = storage.list_files(project_id, "uploads_parsed")
        processed_base_names = {f.rsplit('.', 1)[0] for f in processed_files if '.' in f}
        
        # Filter to show only unprocessed files
        pending_files = []
        for f in raw_files:
            base_name = f.rsplit('.', 1)[0] if '.' in f else f
            if base_name not in processed_base_names:
                pending_files.append(f)

        # Build file info objects for frontend
        def get_file_info(filename):
            # Try to get metadata from storage if available, else fallback
            try:
                obj, content_type, size = storage.download(project_id, "uploads_raw", filename)
                uploaded_at = None
                try:
                    uploaded_at = obj.last_modified.isoformat()
                except Exception:
                    uploaded_at = None
                obj.close()
            except Exception:
                content_type = "Unknown"
                size = 0
                uploaded_at = None
            return {
                "filename": filename,
                "file_type": content_type or "Unknown",
                "file_size": size or 0,
                "uploaded_at": uploaded_at or "Unknown"
            }

        uploaded_files_info = [get_file_info(f) for f in raw_files]

        return {
            "project_id": project_id,
            "uploaded_files": uploaded_files_info,
            "processed_files": list(processed_base_names), 
            "pending_files": pending_files,
            "counts": {
                "total_uploaded": len(raw_files),
                "processed": len(processed_base_names),
                "pending": len(pending_files)
            }
        }
    except Exception as e:
        logger.error(f"Failed to list uploaded files for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")

@router.post("/{project_id}/process-all", response_model=ProcessResponse, summary="Process all uploaded files")
async def process_all_files(project_id: str, request_data: ProcessRequest = ProcessRequest()):
    """
    Process all files uploaded to storage.
    Equivalent to the old immediate upload+process behavior, but as a separate step.
    """
    try:
        from app.core.storage_service import get_storage
        storage = get_storage()
        
        # Get all uploaded files
        uploaded_files = storage.list_files(project_id, "uploads_raw")
        
        if not uploaded_files:
            raise HTTPException(status_code=404, detail="No uploaded files found for processing")
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        logger.info(f"Starting bulk processing for project {project_id}: {len(uploaded_files)} files (job_id={job_id})")
        
        # Create a processing request
        from fastapi import Request
        
        # Create form data for the files to process
        processing_request = {
            "files": uploaded_files,
            "reprocess": request_data.reprocess,
            "job_id": job_id
        }
        
        # Start background processing (don't await - let it run async)
        asyncio.create_task(_process_files_background(project_id, uploaded_files, request_data.reprocess, job_id))
        
        return ProcessResponse(
            project_id=project_id,
            job_id=job_id,
            status="started",
            files_to_process=uploaded_files,
            message=f"Started processing {len(uploaded_files)} files in background",
            started_at=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Failed to start processing for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start processing: {str(e)}")

@router.post("/{project_id}/process-selected", response_model=ProcessResponse, summary="Process selected files")
async def process_selected_files(project_id: str, request_data: ProcessRequest):
    """
    Process only the specified files.
    Frontend sends list of selected filenames.
    """
    if not request_data.file_names:
        raise HTTPException(status_code=400, detail="No files specified for processing")
    
    try:
        from app.core.storage_service import get_storage
        storage = get_storage()
        
        # Verify all selected files exist in storage
        uploaded_files = storage.list_files(project_id, "uploads_raw")
        missing_files = [f for f in request_data.file_names if f not in uploaded_files]
        
        if missing_files:
            raise HTTPException(
                status_code=404, 
                detail=f"Files not found in storage: {', '.join(missing_files)}"
            )
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        logger.info(f"Starting selective processing for project {project_id}: {request_data.file_names} (job_id={job_id})")
        
        # Start background processing
        asyncio.create_task(_process_files_background(project_id, request_data.file_names, request_data.reprocess, job_id))
        
        return ProcessResponse(
            project_id=project_id,
            job_id=job_id,
            status="started", 
            files_to_process=request_data.file_names,
            message=f"Started processing {len(request_data.file_names)} selected files in background",
            started_at=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Failed to start selective processing for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start processing: {str(e)}")

async def _process_files_background(project_id: str, file_names: List[str], reprocess: bool, job_id: str):
    """Background task to process files using the existing RAG pipeline"""
    import tempfile
    import os
    
    logger.info(f"Background processing started for job {job_id}: {len(file_names)} files")
    
    try:
        from app.core.storage_service import get_storage
        from app.core.rag_service import RAGService
        from app.core.llm_config import LLMFactory
        
        storage = get_storage()
        
        # Get LLM configuration
        try:
            llm_factory = LLMFactory()
            llm = await llm_factory.create_llm(project_id)
        except Exception as llm_err:
            logger.warning(f"Could not initialize LLM for {project_id}: {llm_err}. Entity extraction will be skipped.")
            llm = None
        
        # Initialize RAG service
        config = {
            "chunking_strategy": "semantic",
            "batch_size": 100,
            "entity_parallel_workers": 4,
            "entity_timeout_seconds": 30
        }
        rag_service = RAGService(project_id, llm=llm, config=config)
        
        # Process each file
        results = []
        for filename in file_names:
            try:
                logger.info(f"Processing file {filename} for project {project_id}")
                
                # Download file from MinIO
                obj, content_type, size = storage.download(project_id, "uploads_raw", filename)
                
                # Save to temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp_file:
                    tmp_file.write(obj.read())
                    tmp_path = tmp_file.name
                
                obj.close()
                
                # Process with RAG service
                result = rag_service.add_file(tmp_path, reprocess=reprocess, source_name=filename)
                results.append({"filename": filename, "status": "success", "result": result})
                
                # Cleanup temp file
                try:
                    os.unlink(tmp_path)
                except:
                    pass
                
                logger.info(f"Successfully processed {filename}")
                
            except Exception as file_err:
                logger.error(f"Failed to process {filename}: {file_err}")
                results.append({"filename": filename, "status": "error", "error": str(file_err)})
        
        # Log completion
        success_count = len([r for r in results if r["status"] == "success"])
        logger.info(f"Background processing completed for job {job_id}: {success_count}/{len(file_names)} files successful")
        
    except Exception as e:
        logger.error(f"Background processing failed for job {job_id}: {e}")
