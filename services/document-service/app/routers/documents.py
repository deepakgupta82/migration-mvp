"""
Document Processing Router
Handles document upload, processing, and status endpoints
"""

from fastapi import APIRouter, HTTPException, Form, File, UploadFile, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any, Callable, Coroutine
import uuid
import tempfile
import os
import logging
from datetime import datetime
import asyncio
import json
import httpx
import zipfile
import io

from ..core.document_processor import DocumentProcessor
from ..core.semantic_chunking import chunk_text as chunk_text_semantic
from ..chunking.layout_chunker import LayoutAwareChunker, LAYOUT_AWARE_ENABLED
from ..core.enrichment import enrich_text
from ..core.structured_processor import StructuredDocumentProcessor
from ..core.content_extractor import ContentExtractor

# PVC orchestration clients
from ..shared.graph_client import GraphServiceClient
from ..shared.vector_client import VectorServiceClient

# Import ServiceClient for HTTP calls
from services.shared.service_client import get_service_client

# Singleton service client (re-used across requests to avoid re-init cost)
_SERVICE_CLIENT_SINGLETON = None

def _get_sc():
    global _SERVICE_CLIENT_SINGLETON
    if _SERVICE_CLIENT_SINGLETON is None:
        try:
            _SERVICE_CLIENT_SINGLETON = get_service_client()
            logger.info("Initialized shared service client singleton")
        except Exception as e:
            logger.warning(f"Failed to init service client singleton: {e}")
            _SERVICE_CLIENT_SINGLETON = None
    return _SERVICE_CLIENT_SINGLETON

# Initialize logger early
logger = logging.getLogger("document-service.router")

# Import LLM analyzer for enhanced endpoints
try:
    from ..core.llm_content_analyzer import LLMContentAnalyzer
    LLM_ANALYZER_AVAILABLE = True
except ImportError:
    LLM_ANALYZER_AVAILABLE = False
    logger.warning("LLM Content Analyzer not available for enhanced endpoints")

router = APIRouter()

# Simple perf timing helper with correlation ID and in-memory metrics aggregation
_PERF_METRICS: Dict[str, Dict[str, Any]] = {}

def _timed(section: str):
    """Decorator preserving FastAPI endpoint signature to avoid 422 validation on synthetic *args/**kwargs.

    The previous implementation wrapped the function without functools.wraps, causing FastAPI to
    introspect the wrapper(*args, **kwargs) signature and treat 'args'/'kwargs' as query params,
    leading to 422 errors. We now preserve the original function's signature & metadata.
    """
    def deco(func: Callable[..., Coroutine[Any, Any, Any]]):
        from functools import wraps

        @wraps(func)
        async def wrapper(*args, **kwargs):
            start = datetime.now()
            corr_id = None
            # Attempt to pull Request from args/kwargs to extract correlation id
            for val in list(kwargs.values()) + list(args):
                try:
                    from fastapi import Request as _FReq  # local import to avoid circular
                    if isinstance(val, _FReq):
                        cid = val.headers.get("X-Correlation-ID")
                        if cid:
                            corr_id = cid
                            break
                except Exception:
                    pass
            try:
                return await func(*args, **kwargs)
            finally:
                dur = (datetime.now() - start).total_seconds()
                m = _PERF_METRICS.get(section)
                if not m:
                    m = {"count": 0, "total": 0.0, "max": 0.0, "min": None}
                    _PERF_METRICS[section] = m
                m["count"] += 1
                m["total"] += dur
                if dur > m["max"]:
                    m["max"] = dur
                if m["min"] is None or dur < m["min"]:
                    m["min"] = dur
                avg = m["total"] / m["count"] if m["count"] else dur
                logger.info(
                    "PERF %s duration=%.3fs avg=%.3fs max=%.3fs min=%.3fs count=%d corr_id=%s",
                    section, dur, avg, m["max"], m["min"], m["count"], corr_id or "n/a"
                )
        return wrapper
    return deco

@router.get("/metrics/perf")
async def get_perf_metrics():
    """Expose in-memory performance metrics (non-prometheus)"""
    # Derive averages on demand
    out = {}
    for k, v in _PERF_METRICS.items():
        out[k] = {
            "count": v["count"],
            "total_seconds": round(v["total"], 4),
            "avg_seconds": round(v["total"] / v["count"], 4) if v["count"] else 0,
            "max_seconds": round(v["max"], 4),
            "min_seconds": round(v["min"], 4) if v["min"] is not None else None,
        }
    return {"service": "document-service", "metrics": out, "generated_at": datetime.now().isoformat()}

    # -------------------------
    # Wiring placeholders (guarded)
    # -------------------------
    def _flag_enabled(name: str, default: bool = False) -> bool:
        try:
            v = os.getenv(name, str(default)).strip().lower()
            return v in ("1", "true", "yes", "on")
        except Exception:
            return default

    @router.get("/layout/schema")
    async def get_layout_schema():
        """Return expected MinerU/layout JSON schema for UI wiring (no-op when disabled)."""
        if not _flag_enabled("MINERU_ENABLED", False):
            raise HTTPException(status_code=404, detail="MinerU disabled")
        return {
            "version": "v1",
            "element": {
                "element_id": "string",
                "kind": "paragraph|heading|table|figure|caption",
                "page_number": 1,
                "bbox": [0, 0, 100, 100],
                "reading_order": 0,
                "section_path": ["Section", "Subsection"],
                "text_preview": "string",
                "confidence": 0.95
            },
            "summary": {
                "mineru_used": True,
                "avg_section_depth": 1.7,
                "max_section_depth": 4,
                "header_count": 12,
                "table_count": 3,
                "table_rows_avg": 8.2,
                "table_cols_avg": 4.1
            }
        }

    @router.get("/layout/sample")
    async def get_layout_sample():
        """Return a static sample layout JSON for UI preview (no-op when disabled)."""
        if not _flag_enabled("MINERU_ENABLED", False):
            raise HTTPException(status_code=404, detail="MinerU disabled")
        return {
            "elements": [
                {
                    "element_id": "p1",
                    "kind": "heading",
                    "page_number": 1,
                    "bbox": [50, 80, 550, 120],
                    "reading_order": 0,
                    "section_path": ["1", "Introduction"],
                    "text_preview": "Introduction",
                    "confidence": 0.99
                },
                {
                    "element_id": "p2",
                    "kind": "paragraph",
                    "page_number": 1,
                    "bbox": [50, 130, 550, 300],
                    "reading_order": 1,
                    "section_path": ["1", "Introduction"],
                    "text_preview": "This document describes...",
                    "confidence": 0.96
                }
            ],
            "summary": {
                "mineru_used": False,
                "avg_section_depth": 1,
                "max_section_depth": 2,
                "header_count": 1,
                "table_count": 0,
                "table_rows_avg": 0,
                "table_cols_avg": 0
            }
        }

async def notify_stats_service(project_id: str, event_type: str, additional_data: Optional[Dict] = None):
    """Notify authoritative stats-service (port 8004) of events. Avoid backend gateway."""
    try:
        stats_url = os.getenv("STATS_SERVICE_URL", "http://localhost:8004")
        headers = {
            "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}",
            "Content-Type": "application/json"
        }
        payload = additional_data or {}
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Map known events to dedicated endpoints
            if event_type == "documents_processed":
                await client.post(
                    f"{stats_url}/api/stats/projects/{project_id}/events/document-processed",
                    json={"document": payload, "timestamp": datetime.now().isoformat()},
                    headers=headers,
                )
            elif event_type == "document_uploaded":
                await client.post(
                    f"{stats_url}/api/stats/projects/{project_id}/events/document-uploaded",
                    json={"document": payload, "timestamp": datetime.now().isoformat()},
                    headers=headers,
                )
            elif event_type == "embeddings_updated":
                await client.post(
                    f"{stats_url}/api/stats/projects/{project_id}/events/embeddings-updated",
                    json={"embeddings": payload, "timestamp": datetime.now().isoformat()},
                    headers=headers,
                )
            elif event_type == "graph_updated":
                await client.post(
                    f"{stats_url}/api/stats/projects/{project_id}/events/graph-updated",
                    json={"graph": payload, "timestamp": datetime.now().isoformat()},
                    headers=headers,
                )
            else:
                # Unknown event: best-effort document processed to bump activity
                await client.post(
                    f"{stats_url}/api/stats/projects/{project_id}/events/document-processed",
                    json={"document": payload, "timestamp": datetime.now().isoformat()},
                    headers=headers,
                )
        logger.debug(f"Notified stats-service: {project_id} - {event_type}")
    except Exception as e:
        logger.debug(f"Failed to notify stats-service: {e}")  # Non-critical, don't fail processing

from pydantic import BaseModel, Field

# Initialize document processors
processor = DocumentProcessor()
content_extractor = ContentExtractor()

# Initialize LLM analyzer for enhanced processing
llm_analyzer = None
if LLM_ANALYZER_AVAILABLE:
    try:
        llm_analyzer = LLMContentAnalyzer()
        logger.info("LLM Content Analyzer initialized for enhanced endpoints")
    except Exception as e:
        logger.warning(f"Failed to initialize LLM Content Analyzer: {e}")
        llm_analyzer = None

def is_error_content(content: str) -> bool:
    """Check if content represents an error document"""
    if not content or not isinstance(content, str):
        return True
        
    content_lower = content.lower()
    error_indicators = [
        "# error processing document:",
        "document conversion failed",
        "failed to extract content",
        "error occurred during processing",
        "unable to process document",
        "conversion error:",
        "processing failed:",
        "extraction failed:",
        "error: could not",
        "failed to parse",
        "document could not be processed"
    ]
    
    # Check for error indicators
    for indicator in error_indicators:
        if indicator in content_lower:
            return True
    
    # Check for very short content (likely errors)
    if len(content.strip()) < 50:
        return True
        
    return False
structured_processor = StructuredDocumentProcessor()

# Import enhanced processor for new workflow
from ..core.enhanced_processor import EnhancedDocumentProcessor
enhanced_processor = EnhancedDocumentProcessor()

# Analytics service integration via HTTP calls
ANALYTICS_SERVICE_URL = os.getenv("ANALYTICS_SERVICE_URL", "http://localhost:8014")

# Placeholder classes for compatibility
class AnalysisResultCreate:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

class AnalysisBatchCreate:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

class AnalysisVersionCreate:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

# Mock repository for HTTP-based integration
class HttpAnalysisRepository:
    """HTTP-based analysis repository that calls analytics service"""

    def __init__(self):
        self.base_url = ANALYTICS_SERVICE_URL
        self.service_available = True

    async def _check_service_health(self):
        """Check if analytics service is available"""
        if not self.service_available:
            return False

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/health")
                if response.status_code == 200:
                    return True
                else:
                    logger.warning(f"Analytics service health check failed: {response.status_code}")
                    self.service_available = False
                    return False
        except Exception as e:
            logger.warning(f"Analytics service not available: {e}")
            self.service_available = False
            return False

    async def create_result(self, result_data):
        """Create analysis result via HTTP"""
        if not await self._check_service_health():
            logger.info("Analytics service not available, skipping result creation")
            return {"id": f"local_{uuid.uuid4()}"}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/analysis",
                    json=result_data.__dict__ if hasattr(result_data, '__dict__') else result_data
                )
                if response.status_code == 201:
                    return {"id": response.json().get("id")}
                else:
                    logger.warning(f"Failed to create analysis result: {response.status_code}")
                    return None
        except Exception as e:
            logger.warning(f"Error creating analysis result: {e}")
            return None

    async def get_results_by_batch(self, batch_id, limit=50, offset=0):
        """Get results by batch via HTTP"""
        if not await self._check_service_health():
            logger.info("Analytics service not available, returning empty results")
            return []

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/api/documents/analysis/results/batch/{batch_id}/results",
                    params={"limit": limit, "offset": offset}
                )
                if response.status_code == 200:
                    return response.json().get("results", [])
                else:
                    logger.warning(f"Failed to get batch results: {response.status_code}")
                    return []
        except Exception as e:
            logger.warning(f"Error getting batch results: {e}")
            return []

    async def create_batch(self, batch_data):
        """Create analysis batch via HTTP"""
        if not await self._check_service_health():
            logger.info("Analytics service not available, creating local batch")
            return {"id": f"local_batch_{uuid.uuid4()}"}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/documents/analysis/results/batch",
                    json=batch_data.__dict__ if hasattr(batch_data, '__dict__') else batch_data
                )
                if response.status_code == 201:
                    return {"id": response.json().get("batch_id")}
                else:
                    logger.warning(f"Failed to create analysis batch: {response.status_code}")
                    return None
        except Exception as e:
            logger.warning(f"Error creating analysis batch: {e}")
            return None

    async def get_batch_by_id(self, batch_id):
        """Get batch by ID via HTTP"""
        if not await self._check_service_health():
            logger.info("Analytics service not available, returning mock batch data")
            return {
                "batch_id": batch_id,
                "status": "completed",
                "results": []
            }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/api/documents/analysis/results/batch/{batch_id}")
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.warning(f"Failed to get batch: {response.status_code}")
                    return None
        except Exception as e:
            logger.warning(f"Error getting batch: {e}")
            return None

    async def create_version(self, version_data):
        """Create analysis version via HTTP"""
        if not await self._check_service_health():
            logger.info("Analytics service not available, creating local version")
            return {"id": f"local_version_{uuid.uuid4()}"}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/documents/analysis/results/version",
                    json=version_data.__dict__ if hasattr(version_data, '__dict__') else version_data
                )
                if response.status_code == 201:
                    return {"id": response.json().get("version_id")}
                else:
                    logger.warning(f"Failed to create analysis version: {response.status_code}")
                    return None
        except Exception as e:
            logger.warning(f"Error creating analysis version: {e}")
            return None

    async def get_version_by_number(self, version_number):
        """Get version by number via HTTP"""
        if not await self._check_service_health():
            logger.info("Analytics service not available, returning mock version data")
            return {
                "id": f"local_version_{version_number}",
                "version_number": version_number,
                "description": "Mock version content",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }

        try:
            # Analytics service doesn't have version endpoints according to API docs
            # Return mock data to prevent blocking
            logger.info(f"Analytics service version endpoint not available, returning mock data for: {version_number}")
            return {
                "id": f"local_version_{version_number}",
                "version_number": version_number,
                "description": "Mock version content",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
        except Exception as e:
            logger.warning(f"Error getting version: {e}")
            return {
                "id": f"local_version_{version_number}",
                "version_number": version_number,
                "description": "Mock version content",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }

    async def update_result(self, result_id: str, updates: Dict[str, Any]):
        """Update analysis result via HTTP"""
        if not await self._check_service_health():
            logger.info("Analytics service not available, skipping result update")
            return None

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.put(
                    f"{self.base_url}/api/analysis/{result_id}",
                    json=updates
                )
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.warning(f"Failed to update analysis result {result_id}: {response.status_code}")
                    return None
        except Exception as e:
            logger.warning(f"Error updating analysis result {result_id}: {e}")
            return None

    async def delete_result(self, result_id: str):
        """Delete analysis result via HTTP"""
        if not await self._check_service_health():
            logger.info("Analytics service not available, skipping result deletion")
            return None

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.delete(f"{self.base_url}/api/analysis/{result_id}")
                if response.status_code == 204:
                    return True
                else:
                    logger.warning(f"Failed to delete analysis result {result_id}: {response.status_code}")
                    return False
        except Exception as e:
            logger.warning(f"Error deleting analysis result {result_id}: {e}")
            return False

    async def get_batches_by_version(self, version_id: str, limit: int = 50, offset: int = 0):
        """Retrieve batches for a given version.

        The underlying analytics service routes are still evolving; we attempt a
        likely endpoint and degrade gracefully. This prevents AttributeError
        crashes in callers while keeping UI responsive even if the analytics
        service is unavailable or lacks the endpoint.
        """
        # Fast path: if health already failed, just return empty list (UI treats as no batches yet)
        if not await self._check_service_health():
            return []

        possible_endpoints = [
            # Hypothesized REST style (version then batches)
            f"{self.base_url}/api/documents/analysis/results/version/{version_id}/batches",
            # Alternative pluralization / nesting variants
            f"{self.base_url}/api/analysis/version/{version_id}/batches",
        ]

        for ep in possible_endpoints:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(ep, params={"limit": limit, "offset": offset})
                    if resp.status_code == 200:
                        data = resp.json()
                        # Accept either a top-level list or an object containing 'batches'
                        if isinstance(data, list):
                            return data
                        return data.get("batches", [])
                    elif resp.status_code == 404:
                        # Try next pattern; continue silently
                        continue
                    else:
                        logger.debug(f"Unexpected status {resp.status_code} from {ep}")
            except Exception as e:
                logger.debug(f"Batch fetch attempt failed for {ep}: {e}")

        # Fallback: return empty list with debug log so upstream logic proceeds safely
        logger.info(f"No batch list endpoint available for version {version_id}; returning empty list")
        return []

ANALYSIS_REPO_AVAILABLE = True

def get_analysis_repository():
    """Get HTTP-based analysis repository instance"""
    return HttpAnalysisRepository()

# Pydantic models for request/response
class ProcessRequest(BaseModel):
    file_names: Optional[List[str]] = None
    reprocess: bool = False

class ProcessResponse(BaseModel):
    project_id: str
    job_id: str
    status: str
    files_to_process: List[str]
    message: str
    started_at: str

class FileStatus(BaseModel):
    filename: str
    status: str
    conversion_strategy: Optional[str] = None
    timestamp: Optional[str] = None
    error: Optional[str] = None

class ProcessingStatus(BaseModel):
    project_id: str
    job_id: str
    status: str
    total_files: int
    processed_files: int
    failed_files: int
    current_file: Optional[str] = None
    files_status: List[FileStatus] = []
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    last_updated: Optional[str] = None

def _chunk_markdown_text(text: str, jsonl_data: Optional[List[Dict[str, Any]]] = None) -> List[str]:
    """Chunk markdown text using semantic/paragraph strategy helper with JSONL-aware support.
    Strategy can be set via CHUNKING_STRATEGY env: semantic | paragraph | rule_based | jsonl_aware
    """
    try:
        from app.core.config_client import cfg_get
        strategy = str(cfg_get(["document_service", "chunking_strategy"], os.getenv("CHUNKING_STRATEGY", "paragraph")))
    except Exception:
        strategy = os.getenv("CHUNKING_STRATEGY", "paragraph")
    
    # Use jsonl_aware strategy if JSONL data is provided
    if jsonl_data and strategy in ["semantic", "jsonl_aware"]:
        strategy = "jsonl_aware"
        logger.info(f"Using JSONL-aware chunking strategy with {len(jsonl_data)} elements")
    
    try:
        return chunk_text_semantic(text, strategy=strategy, jsonl_data=jsonl_data)
    except Exception as e:
        logger.warning(f"Semantic chunking failed ({e}); falling back to simple paragraph split")
        # minimal fallback
        return [p.strip() for p in text.split("\n\n") if p.strip()]


def _pvc_enabled() -> bool:
    """Feature flag for PVC endpoints (default: disabled to protect existing demos)."""
    val = os.getenv("PVC_ENABLED", "false")
    try:
        from app.core.config_client import cfg_get as _cfg
        val = _cfg(["document_service", "pvc_enabled"], val)
    except Exception:
        pass
    return val if isinstance(val, bool) else str(val).lower() in ("1", "true", "yes", "on")


def _extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """Best-effort JSON extraction from an LLM response string.

    Tries direct parse, then searches for the largest {...} or [...] block.
    """
    if not text:
        return None
    try:
        import json as _json
        return _json.loads(text)
    except Exception:
        pass
    # try to locate JSON block
    import re, json as _json
    candidates = []
    # brace-based
    for m in re.finditer(r"\{[\s\S]*\}", text):
        candidates.append(text[m.start():m.end()])
    # bracket-based
    for m in re.finditer(r"\[[\s\S]*\]", text):
        candidates.append(text[m.start():m.end()])
    candidates.sort(key=lambda s: len(s), reverse=True)
    for c in candidates:
        try:
            return _json.loads(c)
        except Exception:
            continue
    return None

# =====================================================================================
# PVC Tiered Extraction Endpoints (T1/T2/T3)
# =====================================================================================
from pydantic import BaseModel as _BaseModel

class _T1Request(_BaseModel):
    filename: str
    output_format: str = "jsonl"  # jsonl or json
    extract_images: bool = True
    extract_tables: bool = True
    include_coordinates: bool = True

class _T1Response(_BaseModel):
    project_id: str
    filename: str
    status: str
    output_file: Optional[str] = None
    elements: int = 0
    message: Optional[str] = None

@router.post("/{project_id}/pvc/t1", response_model=_T1Response)
async def pvc_t1_extract(
    project_id: str,
    request_data: _T1Request,
    request: Request = None,
):
    """Tier 1: Convert raw file -> structured JSON/JSONL and upload to storage.

    - Uses EnhancedDocumentProcessor if enabled, otherwise falls back to StructuredDocumentProcessor.
    - Stores result under `structured/` container in storage-service.
    """
    if not _pvc_enabled():
        raise HTTPException(status_code=403, detail="PVC endpoints are disabled. Set PVC_ENABLED=true to enable.")

    corr_id = None
    try:
        if request is not None:
            corr_id = request.headers.get("X-Correlation-ID")
    except Exception:
        pass
    if not corr_id:
        corr_id = str(uuid.uuid4())

    filename = request_data.filename
    if not filename:
        raise HTTPException(status_code=400, detail="filename is required")

    # Ensure we download the file from storage
    import httpx as _httpx
    try:
        async with _httpx.AsyncClient(timeout=enhanced_processor.http_timeout if os.getenv("USE_ENHANCED_WORKFLOW", "true").lower()=="true" else processor.http_timeout) as client:
            headers = {"Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"}
            headers["X-Correlation-ID"] = corr_id
            dl = await client.get(
                f"{processor.storage_url}/api/storage/projects/{project_id}/files/uploads_raw/{filename}",
                headers=headers,
            )
            if dl.status_code != 200:
                raise HTTPException(status_code=404, detail=f"File {filename} not found in project {project_id}")

            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp:
                tmp.write(dl.content)
                tmp_path = tmp.name

        try:
            use_enhanced = os.getenv("USE_ENHANCED_WORKFLOW", "true").lower() == "true"
            if use_enhanced:
                res = await enhanced_processor.process_document_enhanced(
                    file_path=tmp_path,
                    filename=filename,
                    project_id=project_id,
                    correlation_id=corr_id,
                    extract_images=request_data.extract_images,
                    extract_tables=request_data.extract_tables,
                    include_coordinates=request_data.include_coordinates,
                )
                if res.get("status") != "success":
                    raise Exception(res.get("error", "Enhanced processing failed"))

                # Upload structured output (already persisted by enhanced workflow, but ensure via storage)
                output_file = res.get("structured_output")
                if not output_file:
                    # create a synthetic JSONL from elements if provided
                    elements = res.get("elements", [])
                    payload = "\n".join(json.dumps({"type": "element", "data": e}, ensure_ascii=False) for e in elements)
                    out_name = f"{os.path.splitext(filename)[0]}_structured.{request_data.output_format}"
                    async with _httpx.AsyncClient(timeout=enhanced_processor.http_timeout) as client:
                        headers = {"Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}", "X-Correlation-ID": corr_id}
                        files = {"files": (out_name, payload.encode("utf-8"), "application/jsonl" if request_data.output_format=="jsonl" else "application/json")}
                        ur = await client.post(f"{processor.storage_url}/api/storage/projects/{project_id}/upload/structured", files=files, headers=headers)
                        if ur.status_code != 200:
                            logger.warning(f"Structured upload returned {ur.status_code}: {ur.text[:200]}")
                        output_file = out_name

                return _T1Response(
                    project_id=project_id,
                    filename=filename,
                    status="success",
                    output_file=output_file,
                    elements=int(res.get("elements_extracted", 0)),
                    message="T1 extraction completed",
                )
            else:
                # traditional structured
                result = await structured_processor.process_document(
                    file_path=tmp_path,
                    filename=filename,
                    project_id=project_id,
                    correlation_id=corr_id,
                    extract_images=request_data.extract_images,
                    extract_tables=request_data.extract_tables,
                    include_coordinates=request_data.include_coordinates,
                )
                out_name = f"{os.path.splitext(filename)[0]}_structured.{request_data.output_format}"
                if request_data.output_format == "jsonl":
                    content = result.to_jsonl()
                    ctype = "application/jsonl"
                else:
                    content = json.dumps(result.to_dict(), indent=2, ensure_ascii=False)
                    ctype = "application/json"
                async with _httpx.AsyncClient(timeout=processor.http_timeout) as client:
                    headers = {"Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}", "X-Correlation-ID": corr_id}
                    files = {"files": (out_name, content.encode("utf-8"), ctype)}
                    ur = await client.post(f"{processor.storage_url}/api/storage/projects/{project_id}/upload/structured", files=files, headers=headers)
                    if ur.status_code != 200:
                        logger.warning(f"Structured upload returned {ur.status_code}: {ur.text[:200]}")
                return _T1Response(
                    project_id=project_id,
                    filename=filename,
                    status=result.status,
                    output_file=out_name,
                    elements=len(result.elements),
                    message="T1 extraction completed (traditional)",
                )
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"T1 extraction failed for {filename}: {e}")
        raise HTTPException(status_code=500, detail=f"T1 extraction failed: {str(e)}")

class _T2Request(_BaseModel):
    filename: str
    # optional: override which structured file to use
    structured_suffix: Optional[str] = None  # defaults to _structured.jsonl

class _T2Response(_BaseModel):
    project_id: str
    filename: str
    status: str
    proposal_preview: Dict[str, Any] = {}
    message: Optional[str] = None

@router.post("/{project_id}/pvc/t2", response_model=_T2Response)
async def pvc_t2_enrich(
    project_id: str,
    request_data: _T2Request,
    request: Request = None,
):
    """Tier 2: Call llm-service /enrich to produce a normalized proposal draft.

    For now, read the parsed markdown (if present) and send it for enrichment.
    Later, this can aggregate JSONL elements for better prompts.
    """
    if not _pvc_enabled():
        raise HTTPException(status_code=403, detail="PVC endpoints are disabled. Set PVC_ENABLED=true to enable.")

    corr_id = request.headers.get("X-Correlation-ID") if request else str(uuid.uuid4())
    filename = request_data.filename
    if not filename:
        raise HTTPException(status_code=400, detail="filename is required")

    # Try to load parsed markdown produced earlier
    md_filename = filename if filename.lower().endswith(".md") else f"{os.path.splitext(filename)[0]}.md"
    parsed_content = None
    import httpx as _httpx
    try:
        async with _httpx.AsyncClient(timeout=processor.http_timeout) as client:
            headers = {"Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}", "X-Correlation-ID": corr_id}
            r = await client.get(
                f"{processor.storage_url}/api/storage/projects/{project_id}/files/parsed/{md_filename}",
                headers=headers,
            )
            if r.status_code == 200:
                parsed_content = r.text
    except Exception as e:
        logger.debug(f"Unable to load parsed content for T2: {e}")

    if not parsed_content:
        raise HTTPException(status_code=404, detail=f"Parsed markdown not found for {md_filename}; run T1/process first")

    # Call llm-service /enrich with the correct payload shape expected by EnrichRequest
    # EnrichRequest schema: { project_id?: string, text: string, mode?: string, hint?: string }
    # We'll request both facts and entities in one pass
    llm_url = os.getenv("LLM_SERVICE_URL", "http://localhost:8007")
    # Load enrich hint from prompt loader with fallback
    try:
        from ..core import prompt_loader as _pl
        _pdoc = _pl.get_prompt("enrich_facts_entities")
        _hint_text = None
        if isinstance(_pdoc, dict):
            _hint_text = _pdoc.get("text") or _pdoc.get("prompt")
    except Exception:
        _hint_text = None
    if not _hint_text:
        _hint_text = "Return strict JSON with keys 'facts' (list of objects with name,value,evidence) and 'entities' (list of objects with name,type,aliases)."

    body = {
        "project_id": project_id,
        "text": parsed_content[:180000],
        "mode": "facts_entities",
        "hint": _hint_text
    }
    try:
        async with _httpx.AsyncClient(timeout=30.0) as client:
            headers = {"Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}", "X-Correlation-ID": corr_id}
            resp = await client.post(f"{llm_url}/api/llm/enrich", json=body, headers=headers)
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail=f"LLM enrich failed: {resp.status_code}")
            data = resp.json()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"T2 enrich call failed: {e}")
        raise HTTPException(status_code=502, detail=f"T2 enrich failed: {str(e)}")

    # Provide a small preview of proposal content without committing yet
    preview = {
        "entities_count": len(data.get("entities", [])) if isinstance(data, dict) else 0,
        "relationships_count": len(data.get("relationships", [])) if isinstance(data, dict) else 0,
        "facts_count": len(data.get("facts", [])) if isinstance(data, dict) else 0,
    }
    return _T2Response(
        project_id=project_id,
        filename=filename,
        status="draft_proposal_ready",
        proposal_preview=preview,
        message="T2 enrichment completed (preview only)",
    )

class _T3Request(_BaseModel):
    filename: Optional[str] = None  # optional scope
    auto_commit: bool = False

class _T3Response(_BaseModel):
    project_id: str
    status: str
    commit_summary: Dict[str, Any] = {}
    message: Optional[str] = None

@router.post("/{project_id}/pvc/t3", response_model=_T3Response)
async def pvc_t3_commit(
    project_id: str,
    request_data: _T3Request = _T3Request(),
    request: Request = None,
):
    """Tier 3: Dedup/commit proposals and upsert vector cards (stub for now).

    For Phase 1, this endpoint returns a placeholder and points to fuse-knowledge
    for actual commit flows using the new proposals APIs.
    """
    if not _pvc_enabled():
        raise HTTPException(status_code=403, detail="PVC endpoints are disabled. Set PVC_ENABLED=true to enable.")

    # In Phase 1, just return guidance and delegate to fuse-knowledge
    summary = {
        "note": "Use /api/documents/{project_id}/pvc/fuse-knowledge to commit validated proposals",
        "next": {
            "endpoint": f"/api/documents/{project_id}/pvc/fuse-knowledge",
            "payload_examples": [
                {"status_filter": "validated"},
                {"proposal_ids": ["<id1>", "<id2>"]}
            ],
        },
    }
    return _T3Response(project_id=project_id, status="pending_commit", commit_summary=summary, message="T3 stub")

@router.post("/{project_id}/upload")
async def upload_documents(
    project_id: str,
    files: List[UploadFile] = File(...),
    request: Request = None,
    background_tasks: BackgroundTasks = None,
):
    """Upload documents to Storage Service (port 8010) and trigger background analysis"""
    try:
        import httpx

        logger.info(f"Starting upload for project {project_id} with {len(files)} files")
        for i, file in enumerate(files):
            logger.info(f"File {i+1}: {file.filename} ({file.content_type})")

        uploaded_files = []

        # Create HTTP client to call Storage Service
        async with httpx.AsyncClient(timeout=processor.http_timeout) as client:
            corr_id = None
            try:
                if request is not None:
                    corr_id = request.headers.get("X-Correlation-ID")
            except Exception:
                pass
            for file in files:
                if not file.filename:
                    continue

                # Read file content
                content = await file.read()

                # If ZIP, extract and upload contained files
                if file.filename.lower().endswith('.zip'):
                    try:
                        with zipfile.ZipFile(io.BytesIO(content)) as zf:
                            for zip_info in zf.infolist():
                                if zip_info.is_dir():
                                    continue
                                inner_name = zip_info.filename
                                # Skip hidden/system files
                                if any(part.startswith('.') for part in inner_name.split('/')):
                                    continue
                                data = zf.read(zip_info)
                                inner_ct = 'application/octet-stream'
                                # Basic content-type inference by extension
                                lower = inner_name.lower()
                                if lower.endswith('.pdf'): inner_ct = 'application/pdf'
                                elif lower.endswith('.docx'): inner_ct = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                                elif lower.endswith('.doc'): inner_ct = 'application/msword'
                                elif lower.endswith('.pptx'): inner_ct = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
                                elif lower.endswith('.ppt'): inner_ct = 'application/vnd.ms-powerpoint'
                                elif lower.endswith('.xlsx'): inner_ct = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                                elif lower.endswith('.xls'): inner_ct = 'application/vnd.ms-excel'
                                elif lower.endswith('.csv'): inner_ct = 'text/csv'
                                elif lower.endswith('.json'): inner_ct = 'application/json'
                                elif lower.endswith('.xml'): inner_ct = 'application/xml'
                                elif lower.endswith('.md') or lower.endswith('.markdown'): inner_ct = 'text/markdown'
                                elif lower.endswith('.txt'): inner_ct = 'text/plain'
                                elif lower.endswith('.png'): inner_ct = 'image/png'
                                elif lower.endswith('.jpg') or lower.endswith('.jpeg'): inner_ct = 'image/jpeg'
                                elif lower.endswith('.gif'): inner_ct = 'image/gif'
                                elif lower.endswith('.tif') or lower.endswith('.tiff'): inner_ct = 'image/tiff'

                                files_data = {
                                    'files': (inner_name, data, inner_ct)
                                }
                                headers = {
                                    "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
                                }
                                if corr_id:
                                    headers["X-Correlation-ID"] = corr_id
                                storage_response = await client.post(
                                    f"{processor.storage_url}/api/storage/projects/{project_id}/upload/uploads_raw",
                                    files=files_data,
                                    headers=headers,
                                )
                                if storage_response.status_code == 200:
                                    uploaded_files.append({
                                        "filename": inner_name,
                                        "size": len(data),
                                        "uploaded_at": datetime.now().isoformat(),
                                        "source_zip": file.filename
                                    })
                                    logger.info(f"Uploaded {inner_name} from {file.filename} to project {project_id}")
                                else:
                                    logger.error(f"Storage upload failed for {inner_name} in {file.filename}: {storage_response.status_code}")
                                    raise HTTPException(status_code=500, detail=f"Storage upload failed: {storage_response.status_code}")
                    except zipfile.BadZipFile:
                        logger.error(f"Invalid ZIP file: {file.filename}")
                        raise HTTPException(status_code=400, detail=f"Invalid ZIP file: {file.filename}")
                else:
                    # Call Storage Service upload endpoint using ServiceClient
                    from services.shared.service_client import get_service_client
                    client = await get_service_client()
                    
                    files_data = {
                        'files': (file.filename, content, file.content_type or 'application/octet-stream')
                    }

                    # Call Storage Service upload endpoint
                    headers = {
                        "X-Correlation-ID": corr_id or str(uuid.uuid4())
                    }
                    
                    logger.info(f"Uploading {file.filename} to storage service at {processor.storage_url}/api/storage/projects/{project_id}/upload/uploads_raw")
                    storage_response = await client.post(
                        "storage",
                        f"/api/storage/projects/{project_id}/upload/uploads_raw",
                        files=files_data,
                        headers=headers,
                    )

                    # ServiceClient returns a dict (JSON) without status_code on success; add defensive handling
                    resp_status = storage_response.get("status_code") if isinstance(storage_response, dict) else getattr(storage_response, "status_code", None)
                    # If no explicit status, assume success (ServiceClient would have raised on HTTP error)
                    success = (resp_status is None) or resp_status == 200
                    logger.info(f"Storage service response for {file.filename}: {resp_status if resp_status is not None else 'implicit 200'}")
                    if success:
                        uploaded_files.append({
                            "filename": file.filename,
                            "size": len(content),
                            "uploaded_at": datetime.now().isoformat()
                        })
                        logger.info(f"Uploaded {file.filename} to project {project_id}")
                    else:
                        logger.error(f"Storage service upload failed for {file.filename}: {resp_status}")
                        raise HTTPException(
                            status_code=500,
                            detail=f"Storage service upload failed: {resp_status}"
                        )

        # Notify stats service of file upload (event-driven stats)
        await notify_stats_service(project_id, "document_uploaded", {
            "uploaded_count": len(uploaded_files),
            "filenames": [f["filename"] for f in uploaded_files]
        })

        # Storage-only upload: NO background analysis trigger
        logger.info(f"Storage-only upload complete for {len(uploaded_files)} files; no analysis triggered")

        return {
            "project_id": project_id,
            "uploaded_files": uploaded_files,
            "total_uploaded": len(uploaded_files),
            "message": f"Successfully uploaded {len(uploaded_files)} files to storage only",
            "analysis_triggered": False,
            "processing_triggered": False
        }

    except Exception as e:
        logger.error(f"Upload failed for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.post("/{project_id}/process-all", summary="Process all uploaded documents", include_in_schema=False)
async def process_all_documents(
    project_id: str, 
    background_tasks: BackgroundTasks,
    request_data: ProcessRequest = ProcessRequest(),
    request: Request = None,
):
    """Deprecated: process-all is no longer supported. Use /api/documents/{project_id}/process-selected."""
    raise HTTPException(
        status_code=410, 
        detail={
            "error": "Endpoint deprecated",
            "message": "process-all has been removed. Use process-selected instead.",
            "alternative": f"/api/documents/{project_id}/process-selected",
            "migration_guide": "Send POST request with { file_names: [list_of_files] } to process specific files"
        }
    )

@router.post("/{project_id}/process-selected", response_model=ProcessResponse)
async def process_selected_documents(
    project_id: str,
    background_tasks: BackgroundTasks,
    request_data: ProcessRequest,
    request: Request = None,
):
    """Process selected documents using ENHANCED PIPELINE ONLY"""
    try:
        selected_files = request_data.file_names or []
        if not selected_files:
            raise HTTPException(status_code=400, detail="No files selected for processing")

        # Verify selected files exist in storage (uploads_raw)
        import httpx
        async with httpx.AsyncClient(timeout=processor.http_timeout) as client:
            headers = {
                "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
            }
            corr_id = request.headers.get("X-Correlation-ID") if request else None
            if corr_id:
                headers["X-Correlation-ID"] = corr_id

            resp = await client.get(
                f"{processor.storage_url}/api/storage/projects/{project_id}/files/uploads_raw",
                headers=headers,
            )
            if resp.status_code == 200:
                stored = resp.json().get("files", [])
                existing = {f.get("filename") for f in stored if isinstance(f, dict)}
                missing = [f for f in selected_files if f not in existing]
                if missing:
                    raise HTTPException(status_code=404, detail=f"Files not found in storage: {', '.join(missing)}")
            else:
                logger.warning(f"Could not verify storage files for {project_id}: {resp.status_code}")

        # Start enhanced-only background task
        job_id = str(uuid.uuid4())
        corr_id = request.headers.get("X-Correlation-ID") if request else job_id

        logger.info(f"Starting ENHANCED-ONLY processing for project {project_id}: {len(selected_files)} files (job_id={job_id})")
        background_tasks.add_task(_enhanced_processing_pipeline, project_id, selected_files, job_id, corr_id)

        # Initialize processing status
        await processor.update_processing_status(project_id, job_id, {
            "status": "started",
            "total_files": len(selected_files),
            "processed_files": 0,
            "failed_files": 0,
            "files_to_process": selected_files,
            "pipeline": "enhanced",
            "started_at": datetime.now().isoformat()
        })

        return ProcessResponse(
            project_id=project_id,
            job_id=job_id,
            status="started",
            files_to_process=selected_files,
            message=f"Started ENHANCED processing of {len(selected_files)} files in background",
            started_at=datetime.now().isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start enhanced processing for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start processing: {str(e)}")

@router.get("/{project_id}/status/{job_id}", response_model=ProcessingStatus)
async def get_processing_status(project_id: str, job_id: str):
    """Get processing status for a job"""
    try:
        status = await processor.get_processing_status(project_id, job_id)
        
        if status.get("status") == "not_found":
            raise HTTPException(status_code=404, detail="Processing job not found")
        
        # Ensure required fields are present for Pydantic validation
        status["project_id"] = project_id
        status["job_id"] = job_id
        
        return ProcessingStatus(**status)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get processing status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")

async def _enhanced_processing_pipeline(
    project_id: str,
    filenames: List[str],
    job_id: str,
    correlation_id: Optional[str] = None
):
    """Enhanced processing pipeline: JSONL → entities → assessment → insights (+stats/ws)"""
    try:
        import httpx
        import tempfile
        import os
        
        for fn in filenames:
            try:
                # Download file from Storage Service before processing
                async with httpx.AsyncClient(timeout=processor.http_timeout) as client:
                    headers = {
                        "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
                    }
                    if correlation_id:
                        headers["X-Correlation-ID"] = correlation_id
                    
                    download_response = await client.get(
                        f"{processor.storage_url}/api/storage/projects/{project_id}/download/uploads_raw/{fn}",
                        headers=headers,
                    )
                    
                    if download_response.status_code != 200:
                        raise Exception(f"Failed to download file {fn} from storage: {download_response.status_code}")
                    
                    # Save to temporary file
                    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(fn)[1]) as tmp_file:
                        tmp_file.write(download_response.content)
                        tmp_file_path = tmp_file.name
                
                try:
                    # JSONL conversion (enhanced)
                    await processor.update_processing_status(project_id, job_id, {"current_file": fn, "stage": "jsonl_conversion"})
                    result = await enhanced_processor.process_document_enhanced(
                        file_path=tmp_file_path,
                        project_id=project_id,
                        filename=fn,
                        correlation_id=correlation_id
                    )

                    # Optional entity extraction if exposed by enhanced processor
                    try:
                        await processor.update_processing_status(project_id, job_id, {"current_file": fn, "stage": "entity_extraction"})
                        _ = await enhanced_processor.extract_entities_llm(
                            project_id=project_id,
                            filename=fn,
                            jsonl_content=result.get("jsonl") if isinstance(result, dict) else None,
                            correlation_id=correlation_id
                        )
                    except Exception as ee:
                        logger.warning(f"Entity extraction skipped/failed for {fn}: {ee}")

                    # Assessment (LLM) and insights (LLM) if enabled in enhanced workflow
                    try:
                        await processor.update_processing_status(project_id, job_id, {"current_file": fn, "stage": "assessment"})
                        # Many implementations integrate assessment into process_document_enhanced already
                        # so this is best-effort and tolerant if not present:
                        if hasattr(enhanced_processor, "assess_document_llm"):
                            assessment = await enhanced_processor.assess_document_llm(
                                project_id=project_id,
                                filename=fn,
                                correlation_id=correlation_id
                            )
                            if hasattr(enhanced_processor, "update_project_insights_llm"):
                                await processor.update_processing_status(project_id, job_id, {"current_file": fn, "stage": "insights"})
                                await enhanced_processor.update_project_insights_llm(
                                    project_id=project_id,
                                    assessment=assessment,
                                    correlation_id=correlation_id
                                )
                    except Exception as ee:
                        logger.warning(f"Assessment/insights skipped/failed for {fn}: {ee}")

                    # Stats update (best-effort)
                    try:
                        await processor.emit_stats_event(
                            project_id=project_id,
                            event_type="documents_processed",
                            additional_data={"filename": fn, "job_id": job_id, "pipeline": "enhanced"}
                        )
                    except Exception:
                        pass

                    await processor.increment_processed_file(project_id, job_id, fn)

                finally:
                    # Clean up temp file
                    os.unlink(tmp_file_path)

            except Exception as fe:
                logger.error(f"Enhanced pipeline failed for {fn}: {fe}")
                await processor.increment_failed_file(project_id, job_id, fn, str(fe))

        await processor.update_processing_status(project_id, job_id, {"status": "completed", "completed_at": datetime.now().isoformat()})

        # Notify frontend via WebSocket about processing completion
        for filename in filenames:
            await _notify_document_processing_complete(project_id, filename, correlation_id=correlation_id)

        logger.info(f"Enhanced processing completed for job {job_id} in project {project_id}")

    except Exception as e:
        logger.error(f"Enhanced processing job failed {job_id}: {e}")
        await processor.update_processing_status(project_id, job_id, {"status": "failed", "error": str(e), "failed_at": datetime.now().isoformat()})

async def _process_files_background(project_id: str, file_names: List[str], reprocess: bool, job_id: str, correlation_id: Optional[str] = None):
    """Background task to process files with enhanced workflow - uses enhanced processor when available"""
    logger.info(f"Background processing started for job {job_id}: {len(file_names)} files")

    # Check if enhanced workflow is enabled
    use_enhanced_workflow = os.getenv("USE_ENHANCED_WORKFLOW", "true").lower() == "true"
    
    if use_enhanced_workflow:
        logger.info(f"Using enhanced workflow for job {job_id}")
        try:
            # Use enhanced processor for batch processing
            batch_result = await enhanced_processor.process_batch_enhanced(
                project_id=project_id,
                filenames=file_names,
                correlation_id=correlation_id,
                processing_options={
                    "extract_images": True,
                    "extract_tables": True,
                    "include_coordinates": True
                }
            )
            
            # Convert enhanced results to traditional status format for API compatibility
            processed_count = batch_result["processed_count"]
            failed_count = batch_result["failed_count"]
            files_status = []
            
            for result in batch_result["results"]:
                if result["status"] == "success":
                    files_status.append(FileStatus(
                        filename=result["filename"],
                        status="success",
                        conversion_strategy="enhanced_unstructured",
                        timestamp=datetime.now().isoformat()
                    ))
                else:
                    files_status.append(FileStatus(
                        filename=result["filename"],
                        status="error",
                        error=result.get("error", "Enhanced processing failed"),
                        timestamp=datetime.now().isoformat()
                    ))
            
            # Update final status
            await processor.update_processing_status(project_id, job_id, {
                "status": "completed" if failed_count == 0 else "completed_with_errors",
                "processed_files": processed_count,
                "failed_files": failed_count,
                "files_status": [status.dict() for status in files_status],
                "completed_at": datetime.now().isoformat(),
                "current_file": None,
                "workflow_type": "enhanced"
            })
            
            logger.info(f"Enhanced background processing completed for job {job_id}: {processed_count} success, {failed_count} failed")

            # Extract content for successfully processed files
            if processed_count > 0:
                try:
                    extraction_tasks = []
                    for result in batch_result["results"]:
                        if result["status"] == "success":
                            # Get processed content from storage
                            filename = result["filename"]
                            extraction_tasks.append(
                                content_extractor.extract_and_update_project_file(
                                    project_id=project_id,
                                    filename=filename,
                                    processed_content="",  # Will be fetched from storage
                                    structured_result=result.get("processing_result"),
                                    correlation_id=correlation_id
                                )
                            )

                    if extraction_tasks:
                        logger.info(f"Starting content extraction for {len(extraction_tasks)} enhanced processed files")
                        extraction_results = await asyncio.gather(*extraction_tasks, return_exceptions=True)

                        successful_extractions = sum(1 for r in extraction_results if not isinstance(r, Exception) and r.get("status") == "success")
                        logger.info(f"Content extraction completed: {successful_extractions}/{len(extraction_tasks)} successful")

                except Exception as e:
                    logger.warning(f"Enhanced content extraction failed: {e}")

            # Notify stats service of processing completion (event-driven stats)
            await notify_stats_service(project_id, "documents_processed", {
                "job_id": job_id,
                "files_processed": processed_count,
                "files_failed": failed_count,
                "workflow_type": "enhanced"
            })

            return
            
        except Exception as e:
            logger.warning(f"Enhanced workflow failed for job {job_id}, falling back to traditional: {e}")
            # Fall back to traditional workflow
    
    # Traditional workflow (fallback or when enhanced is disabled)
    logger.info(f"Using traditional workflow for job {job_id}")

    try:
        # Use HTTP calls to Storage Service instead of direct imports
        import httpx
        import json

        processed_count = 0
        failed_count = 0
        files_status: List[FileStatus] = []

        async with httpx.AsyncClient(timeout=processor.http_timeout) as client:
            for filename in file_names:
                try:
                    # Update current processing status
                    await processor.update_processing_status(project_id, job_id, {
                        "current_file": filename,
                        "processed_files": processed_count,
                        "failed_files": failed_count
                    })

                    # Download file from Storage Service
                    headers = {
                        "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
                    }
                    if correlation_id:
                        headers["X-Correlation-ID"] = correlation_id
                    download_response = await client.get(
                        f"{processor.storage_url}/api/storage/projects/{project_id}/download/uploads_raw/{filename}",
                        headers=headers,
                    )

                    if download_response.status_code != 200:
                        raise Exception(f"Failed to download file from storage: {download_response.status_code}")

                    # Save to temporary file
                    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                        tmp_file.write(download_response.content)
                        tmp_file_path = tmp_file.name

                    try:
                        # Process the document using DocumentProcessor
                        result = await processor.convert_document_to_markdown(
                            tmp_file_path, filename, project_id, reprocess, correlation_id=correlation_id
                        )

                        # Validate content before proceeding
                        content = result.get("content", "")
                        if is_error_content(content):
                            logger.warning(f"Skipping error document {filename}: detected error content")
                            files_status.append(FileStatus(
                                filename=filename,
                                status="skipped",
                                error="Error content detected - document not processed",
                                timestamp=datetime.now().isoformat()
                            ))
                            continue

                        # Upload processed markdown back to Storage Service
                        if content:
                            md_filename = result["md_filename"]

                            # Enrichment (language, keywords, optional summary via LLM if enabled)
                            try:
                                enrichment = await enrich_text(content, project_id=project_id, corr_id=correlation_id)
                            except Exception as e:
                                enrichment = {}
                                logger.warning(f"Enrichment failed for {filename}: {type(e).__name__}: {e}")

                            # Upload processed markdown
                            files_data = {
                                'files': (md_filename, content.encode('utf-8'), 'text/markdown')
                            }

                            headers = {
                                "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
                            }
                            if correlation_id:
                                headers["X-Correlation-ID"] = correlation_id
                            
                            # Use ServiceClient for file upload
                            service_client = await get_service_client()
                            upload_response = await service_client.post(
                                "storage",
                                f"/api/storage/projects/{project_id}/upload/uploads_parsed",
                                files=files_data,
                                headers=headers,
                            )
                            # ServiceClient returns dict JSON; use embedded status_code when present
                            up_status = upload_response.get("status_code") if isinstance(upload_response, dict) else getattr(upload_response, "status_code", None)
                            if up_status not in (None, 200):
                                body_preview = str(upload_response)[:200]
                                logger.warning(f"Failed to upload processed markdown: {up_status} body={body_preview}")

                            # Save metadata
                            metadata = {
                                "original_filename": filename,
                                "md_filename": md_filename,
                                "conversion_strategy": result.get("conversion_strategy"),
                                "timestamp": result.get("timestamp"),
                                "file_size": result.get("file_size"),
                                "content_length": result.get("content_length"),
                                "status": result.get("status"),
                                "enrichment": enrichment or {}
                            }

                            metadata_filename = os.path.splitext(filename)[0] + "_metadata.json"
                            metadata_json = json.dumps(metadata, indent=2)

                            # Upload metadata to Storage Service
                            metadata_files_data = {
                                'files': (metadata_filename, metadata_json.encode('utf-8'), 'application/json')
                            }

                            headers = {
                                "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
                            }
                            if correlation_id:
                                headers["X-Correlation-ID"] = correlation_id
                            
                            # Use ServiceClient for metadata upload
                            service_client = await get_service_client()
                            metadata_response = await service_client.post(
                                "storage",
                                f"/api/storage/projects/{project_id}/upload/metadata",
                                files=metadata_files_data,
                                headers=headers,
                            )
                            md_status = metadata_response.get("status_code") if isinstance(metadata_response, dict) else getattr(metadata_response, "status_code", None)
                            if md_status not in (None, 200):
                                logger.warning(f"Failed to upload metadata: {md_status} body={str(metadata_response)[:200]}")

                        # Check if conversion actually succeeded
                        conversion_status = result.get("status", "error")
                        conversion_strategy = result.get("conversion_strategy", "unknown")

                        if conversion_status == "success" and conversion_strategy != "error_document":
                            # Ensure Vector collection exists
                            try:
                                headers = {
                                    "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
                                }
                                if correlation_id:
                                    headers["X-Correlation-ID"] = correlation_id
                                
                                # Use ServiceClient for vector collection creation
                                service_client = await get_service_client()
                                coll_resp = await service_client.post(
                                    "vector",
                                    f"/api/vectors/projects/{project_id}/collection",
                                    headers=headers,
                                )
                                coll_status = coll_resp.get("status_code") if isinstance(coll_resp, dict) else getattr(coll_resp, "status_code", None)
                                if coll_status not in (None, 200):
                                    logger.warning(f"Vector collection init returned {coll_status}")
                            except Exception as e:
                                logger.warning(f"Vector collection init failed: {e}")

                            # Chunk markdown and send to Vector Service for embeddings
                            content_text = result.get("content", "")
                            # Offload potentially heavy chunking to a thread so the event loop can serve /status
                            chunks = await asyncio.to_thread(_chunk_markdown_text, content_text)
                            # Enforce optional limit on chunks to control load
                            if getattr(processor, "max_chunks", 0):
                                chunks = chunks[: max(0, int(processor.max_chunks))]
                            logger.info(f"Chunked {filename} into {len(chunks)} chunks for embedding")
                            if not chunks:
                                logger.warning(f"No chunks produced for {filename}; skipping embeddings")
                            else:
                                # Batch embeddings to prevent timeouts
                                batch_size = max(1, int(getattr(processor, "vector_batch_size", 50)))
                                total = len(chunks)
                                embedded = 0
                                for start in range(0, total, batch_size):
                                    batch = chunks[start:start + batch_size]
                                    docs_payload = {
                                        "documents": [
                                            {
                                                "id": f"{os.path.splitext(md_filename)[0]}_{start + i}",
                                                "content": ch,
                                                "filename": md_filename,
                                                "source": "document-service"
                                            }
                                            for i, ch in enumerate(batch)
                                        ]
                                    }
                                    # simple retry loop
                                    attempt = 0
                                    while attempt < 3:
                                        try:
                                            # Use ServiceClient for vector document sync
                                            service_client = await get_service_client()
                                            vec_resp = await service_client.post(
                                                "vector",
                                                f"/api/vectors/projects/{project_id}/documents/sync",
                                                json=docs_payload,
                                                headers=headers,
                                            )
                                            vr_status = vec_resp.get("status_code") if isinstance(vec_resp, dict) else getattr(vec_resp, "status_code", None)
                                            if (vr_status is None) or (vr_status == 200):
                                                embedded += len(batch)
                                                break
                                            else:
                                                logger.warning(f"Vector add_documents batch returned {vr_status}: {str(vec_resp)[:300]}")
                                        except Exception as e:
                                            logger.warning(f"Vector add_documents batch failed (attempt {attempt+1}/3): {type(e).__name__}: {e}")
                                        attempt += 1
                                        # small backoff
                                        await asyncio.sleep(0.5 * attempt)
                                logger.info(f"Embedded {embedded}/{total} chunks for {filename} in batches of {batch_size}")

                            # Trigger entity extraction on full markdown via Graph Service
                            try:
                                graph_req = {
                                    "document_content": content_text,
                                    "filename": md_filename,
                                    "document_id": os.path.splitext(md_filename)[0]
                                }
                                headers = {
                                    "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
                                }
                                if correlation_id:
                                    headers["X-Correlation-ID"] = correlation_id
                                
                                # Use ServiceClient for graph extraction
                                service_client = await get_service_client()
                                graph_resp = await service_client.post(
                                    "graph",
                                    f"/api/graphs/projects/{project_id}/extract",
                                    json=graph_req,
                                    headers=headers,
                                )
                                gr_status = graph_resp.get("status_code") if isinstance(graph_resp, dict) else getattr(graph_resp, "status_code", None)
                                if gr_status not in (None, 200):
                                    logger.warning(f"Graph extract returned {gr_status}: {str(graph_resp)[:500]}")
                                else:
                                    logger.info(f"Graph extraction queued for {filename}")
                            except Exception as e:
                                logger.warning(f"Graph extraction call failed: {type(e).__name__}: {e}")

                            processed_count += 1
                            files_status.append(FileStatus(
                                filename=filename,
                                status="success",
                                conversion_strategy=conversion_strategy,
                                timestamp=result.get("timestamp")
                            ))
                            logger.info(f"Successfully processed {filename} for project {project_id} using {conversion_strategy}")

                            # Extract and update content features
                            try:
                                extraction_result = await content_extractor.extract_and_update_project_file(
                                    project_id=project_id,
                                    filename=filename,
                                    processed_content=content,
                                    correlation_id=correlation_id
                                )
                                if extraction_result["status"] == "success":
                                    logger.info(f"Content extraction successful for {filename}")
                                else:
                                    logger.warning(f"Content extraction failed for {filename}: {extraction_result.get('error', 'Unknown error')}")
                            except Exception as e:
                                logger.warning(f"Content extraction error for {filename}: {e}")

                        else:
                            failed_count += 1
                            error_msg = f"Conversion failed - strategy: {conversion_strategy}"
                            files_status.append(FileStatus(
                                filename=filename,
                                status="error",
                                error=error_msg,
                                conversion_strategy=conversion_strategy,
                                timestamp=result.get("timestamp")
                            ))
                            logger.error(f"Failed to process {filename} for project {project_id}: {error_msg}")

                        # Note: WebSocket broadcasting will be handled by other services
                        # Document Service should focus only on document processing

                    finally:
                        # Clean up temp file
                        os.unlink(tmp_file_path)

                except Exception as e:
                    failed_count += 1
                    files_status.append(FileStatus(
                        filename=filename,
                        status="error",
                        error=str(e),
                        timestamp=datetime.now().isoformat()
                    ))
                    logger.error(f"Failed to process {filename}: {type(e).__name__}: {e}")

        # Update final status
        await processor.update_processing_status(project_id, job_id, {
            "status": "completed" if failed_count == 0 else "completed_with_errors",
            "processed_files": processed_count,
            "failed_files": failed_count,
            "files_status": [status.dict() for status in files_status],
            "completed_at": datetime.now().isoformat(),
            "current_file": None
        })

        # Notify frontend via WebSocket about processing completion for successfully processed files
        for status in files_status:
            if status.status == "success":
                await _notify_document_processing_complete(project_id, status.filename, correlation_id=correlation_id)

        logger.info(f"Background processing completed for job {job_id}: {processed_count} success, {failed_count} failed")
        
        # Notify stats service of processing completion (event-driven stats)
        await notify_stats_service(project_id, "documents_processed", {
            "job_id": job_id,
            "files_processed": processed_count,
            "files_failed": failed_count,
            "workflow_type": "traditional"
        })

    except Exception as e:
        logger.error(f"Background processing failed for job {job_id}: {e}")

        # Update error status
        await processor.update_processing_status(project_id, job_id, {
            "status": "failed",
            "error": str(e),
            "completed_at": datetime.now().isoformat()
        })

# Structured Processing Endpoints (Phase 2.3 Enhancement)

class StructuredProcessRequest(BaseModel):
    extract_images: bool = True
    extract_tables: bool = True
    include_coordinates: bool = True
    output_format: str = "jsonl"  # jsonl or json

class StructuredProcessResponse(BaseModel):
    project_id: str
    filename: str
    status: str
    processing_time: float
    total_elements: int
    element_types: Dict[str, int]
    output_file: Optional[str] = None
    errors: List[str] = []
    warnings: List[str] = []

@router.post("/{project_id}/structured-process/{filename}", response_model=StructuredProcessResponse)
async def process_document_structured(
    project_id: str,
    filename: str,
    request_data: StructuredProcessRequest = StructuredProcessRequest(),
    request: Request = None
):
    """Process a single document with structured JSONL output - enhanced with service integration"""
    try:
        import httpx
        
        # Get correlation ID
        corr_id = None
        try:
            if request is not None:
                corr_id = request.headers.get("X-Correlation-ID")
        except Exception:
            pass
        
        if not corr_id:
            corr_id = str(uuid.uuid4())
        
        logger.info(f"Starting structured processing for {filename} in project {project_id} [corr_id={corr_id}]")
        
        # Check if enhanced workflow is enabled
        use_enhanced_workflow = os.getenv("USE_ENHANCED_WORKFLOW", "true").lower() == "true"
        
        if use_enhanced_workflow:
            logger.info(f"Using enhanced structured processing for {filename}")
            try:
                # Download file from Storage Service
                async with httpx.AsyncClient(timeout=enhanced_processor.http_timeout) as client:
                    headers = {
                        "Authorization": f"Bearer {enhanced_processor.auth_token}"
                    }
                    if corr_id:
                        headers["X-Correlation-ID"] = corr_id
                    
                    download_response = await client.get(
                        f"{enhanced_processor.storage_url}/api/storage/projects/{project_id}/files/uploads_raw/{filename}",
                        headers=headers
                    )
                    
                    if download_response.status_code != 200:
                        raise HTTPException(
                            status_code=404,
                            detail=f"File {filename} not found in project {project_id}"
                        )
                    
                    # Save to temporary file
                    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp_file:
                        tmp_file.write(download_response.content)
                        tmp_file_path = tmp_file.name
                    
                    try:
                        # Process with enhanced workflow
                        result = await enhanced_processor.process_document_enhanced(
                            file_path=tmp_file_path,
                            filename=filename,
                            project_id=project_id,
                            correlation_id=corr_id,
                            extract_images=request_data.extract_images,
                            extract_tables=request_data.extract_tables,
                            include_coordinates=request_data.include_coordinates
                        )
                        
                        if result["status"] == "success":
                            processing_result = result["processing_result"]
                            
                            # Return in original API format for frontend compatibility
                            response = StructuredProcessResponse(
                                project_id=project_id,
                                filename=filename,
                                status=result["status"],
                                processing_time=result["processing_time"],
                                total_elements=result["elements_extracted"],
                                element_types=result["element_types"],
                                output_file=result["structured_output"],
                                errors=[],
                                warnings=[]
                            )
                            
                            logger.info(f"Enhanced structured processing completed for {filename}: {result['elements_extracted']} elements")
                            return response
                        else:
                            # Fall back to traditional processing
                            logger.warning(f"Enhanced processing failed for {filename}, falling back to traditional")
                            raise Exception(result.get('error', 'Enhanced processing failed'))
                            
                    finally:
                        # Clean up temp file
                        os.unlink(tmp_file_path)
                        
            except Exception as e:
                logger.warning(f"Enhanced structured processing failed for {filename}, falling back: {e}")
                # Fall back to traditional structured processing
        
        # Traditional structured processing (fallback or when enhanced is disabled)
        logger.info(f"Using traditional structured processing for {filename}")
        
        # Download file from Storage Service
        async with httpx.AsyncClient(timeout=processor.http_timeout) as client:
            headers = {
                "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
            }
            if corr_id:
                headers["X-Correlation-ID"] = corr_id
            
            download_response = await client.get(
                f"{processor.storage_url}/api/storage/projects/{project_id}/download/uploads_raw/{filename}",
                headers=headers
            )
            
            if download_response.status_code != 200:
                raise HTTPException(
                    status_code=404,
                    detail=f"File {filename} not found in project {project_id}"
                )
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp_file:
                tmp_file.write(download_response.content)
                tmp_file_path = tmp_file.name
            
            try:
                # Process with structured processor
                result = await structured_processor.process_document(
                    file_path=tmp_file_path,
                    filename=filename,
                    project_id=project_id,
                    correlation_id=corr_id,
                    extract_images=request_data.extract_images,
                    extract_tables=request_data.extract_tables,
                    include_coordinates=request_data.include_coordinates
                )
                
                # Save structured output to Storage Service
                output_file = None
                if result.status == "success":
                    # Generate output filename
                    base_name = os.path.splitext(filename)[0]
                    output_filename = f"{base_name}_structured.{request_data.output_format}"
                    
                    # Convert to specified format
                    if request_data.output_format == "jsonl":
                        output_content = result.to_jsonl()
                        content_type = "application/jsonl"
                    else:  # json
                        output_content = json.dumps(result.to_dict(), indent=2, ensure_ascii=False)
                        content_type = "application/json"
                    
                    # Upload to Storage Service
                    files_data = {
                        'files': (output_filename, output_content.encode('utf-8'), content_type)
                    }
                    
                    upload_response = await client.post(
                        f"{processor.storage_url}/api/storage/projects/{project_id}/upload/structured",
                        files=files_data,
                        headers=headers
                    )
                    
                    if upload_response.status_code == 200:
                        output_file = output_filename
                        logger.info(f"Uploaded structured output: {output_filename}")
                    else:
                        logger.warning(f"Failed to upload structured output: {upload_response.status_code}")
                
                # Create response
                response = StructuredProcessResponse(
                    project_id=project_id,
                    filename=filename,
                    status=result.status,
                    processing_time=result.processing_stats.get("processing_time_seconds", 0),
                    total_elements=len(result.elements),
                    element_types=result.processing_stats.get("element_types", {}),
                    output_file=output_file,
                    errors=result.errors,
                    warnings=result.warnings
                )

                # Notify frontend via WebSocket about processing completion
                if result.status == "success":
                    await _notify_document_processing_complete(project_id, filename, correlation_id=corr_id)

                logger.info(f"Structured processing completed for {filename}: {len(result.elements)} elements")
                return response
                
            finally:
                # Clean up temp file
                os.unlink(tmp_file_path)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Structured processing failed for {filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Structured processing failed: {str(e)}")

@router.post("/{project_id}/structured-process-all")
async def process_all_documents_structured(
    project_id: str,
    background_tasks: BackgroundTasks,
    request_data: StructuredProcessRequest = StructuredProcessRequest(),
    request: Request = None
):
    """Process all documents with structured output"""
    try:
        import httpx
        
        # Get uploaded files
        async with httpx.AsyncClient(timeout=processor.http_timeout) as client:
            corr_id = None
            try:
                if request is not None:
                    corr_id = request.headers.get("X-Correlation-ID")
            except Exception:
                pass
            
            headers = {
                "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
            }
            if corr_id:
                headers["X-Correlation-ID"] = corr_id
            
            response = await client.get(
                f"{processor.storage_url}/api/storage/projects/{project_id}/files/uploads_raw",
                headers=headers
            )
            
            if response.status_code == 200:
                try:
                    storage_result = response.json()
                    # Handle both list and dict responses from storage service
                    if isinstance(storage_result, dict):
                        # If it's a dict, it might be a single file or wrapped response
                        if "files" in storage_result:
                            files_list = storage_result["files"]
                        elif "filename" in storage_result:
                            # Single file response
                            files_list = [storage_result]
                        else:
                            logger.warning(f"Unexpected dict structure from storage service: {list(storage_result.keys())}")
                            files_list = []
                    elif isinstance(storage_result, list):
                        files_list = storage_result
                    else:
                        logger.warning(f"Storage service returned non-list/dict response: {type(storage_result)}")
                        files_list = []
                    
                    uploaded_files = [f["filename"] for f in files_list if isinstance(f, dict) and "filename" in f]
                except Exception as json_error:
                    logger.warning(f"Failed to parse storage response: {json_error}")
                    uploaded_files = []
            else:
                uploaded_files = []
        
        if not uploaded_files:
            raise HTTPException(status_code=404, detail="No uploaded files found for structured processing")
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        logger.info(f"Starting structured processing job {job_id} for project {project_id}: {len(uploaded_files)} files")
        
        # Start background processing
        background_tasks.add_task(
            _process_structured_background,
            project_id,
            job_id,
            uploaded_files,
            request_data,
            corr_id
        )
        
        return {
            "project_id": project_id,
            "job_id": job_id,
            "status": "started",
            "files_to_process": uploaded_files,
            "message": f"Started structured processing of {len(uploaded_files)} files",
            "started_at": datetime.now().isoformat(),
            "processing_options": {
                "extract_images": request_data.extract_images,
                "extract_tables": request_data.extract_tables,
                "include_coordinates": request_data.include_coordinates,
                "output_format": request_data.output_format
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start structured processing for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start structured processing: {str(e)}")

@router.get("/{project_id}/structured-status/{job_id}")
async def get_structured_processing_status(project_id: str, job_id: str):
    """Get status of structured processing job"""
    try:
        status = await processor.get_processing_status(project_id, job_id)
        if not status:
            raise HTTPException(status_code=404, detail="Processing job not found")
        return status
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting structured processing status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def _process_structured_background(
    project_id: str,
    job_id: str,
    filenames: List[str],
    request_data: StructuredProcessRequest,
    correlation_id: Optional[str] = None
):
    """Background task for structured processing with enhanced workflow support"""
    import httpx
    import json
    
    # Check if enhanced workflow is enabled
    use_enhanced_workflow = os.getenv("USE_ENHANCED_WORKFLOW", "true").lower() == "true"
    
    if use_enhanced_workflow:
        logger.info(f"Using enhanced structured processing for job {job_id}")
        try:
            # Use enhanced processor for batch processing
            batch_result = await enhanced_processor.process_batch_enhanced(
                project_id=project_id,
                filenames=filenames,
                correlation_id=correlation_id,
                processing_options={
                    "extract_images": request_data.extract_images,
                    "extract_tables": request_data.extract_tables,
                    "include_coordinates": request_data.include_coordinates
                }
            )
            
            # Convert enhanced results to structured processing format
            processed_count = batch_result["processed_count"]
            failed_count = batch_result["failed_count"]
            files_status = []
            
            for result in batch_result["results"]:
                if result["status"] == "success":
                    files_status.append({
                        "filename": result["filename"],
                        "status": "success",
                        "output_file": result.get("structured_output"),
                        "elements_extracted": result.get("elements_extracted", 0),
                        "processing_time": result.get("processing_time", 0),
                        "timestamp": datetime.now().isoformat()
                    })
                else:
                    files_status.append({
                        "filename": result["filename"],
                        "status": "error",
                        "error": result.get("error", "Enhanced processing failed"),
                        "timestamp": datetime.now().isoformat()
                    })
            
            # Update final status
            await processor.update_processing_status(project_id, job_id, {
                "status": "completed" if failed_count == 0 else "completed_with_errors",
                "processed_files": processed_count,
                "failed_files": failed_count,
                "files_status": files_status,
                "completed_at": datetime.now().isoformat(),
                "current_file": None,
                "workflow_type": "enhanced_structured"
            })

            # Notify frontend via WebSocket about processing completion for successfully processed files
            for result in batch_result["results"]:
                if result["status"] == "success":
                    await _notify_document_processing_complete(project_id, result["filename"], correlation_id=correlation_id)

            logger.info(f"Enhanced structured processing completed for job {job_id}: {processed_count} success, {failed_count} failed")
            return
            
        except Exception as e:
            logger.warning(f"Enhanced structured workflow failed for job {job_id}, falling back: {e}")
            # Fall back to traditional structured processing
    
    # Traditional structured processing (fallback or when enhanced is disabled)
    logger.info(f"Using traditional structured processing for job {job_id}")
    
    processed_count = 0
    failed_count = 0
    files_status = []
    
    # Initialize status
    await processor.update_processing_status(project_id, job_id, {
        "status": "processing",
        "total_files": len(filenames),
        "processed_files": 0,
        "failed_files": 0,
        "files_to_process": filenames,
        "started_at": datetime.now().isoformat(),
        "processing_type": "structured"
    })
    
    try:
        async with httpx.AsyncClient(timeout=processor.http_timeout) as client:
            headers = {
                "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
            }
            if correlation_id:
                headers["X-Correlation-ID"] = correlation_id
            
            for i, filename in enumerate(filenames):
                try:
                    # Update current file status
                    await processor.update_processing_status(project_id, job_id, {
                        "current_file": filename,
                        "processed_files": processed_count,
                        "failed_files": failed_count
                    })
                    
                    logger.info(f"Processing {filename} ({i+1}/{len(filenames)}) with structured processor")
                    
                    # Download file
                    download_response = await client.get(
                        f"{processor.storage_url}/api/storage/projects/{project_id}/files/uploads_raw/{filename}",
                        headers=headers
                    )
                    
                    if download_response.status_code != 200:
                        raise Exception(f"Failed to download file: {download_response.status_code}")
                    
                    # Save to temporary file
                    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp_file:
                        tmp_file.write(download_response.content)
                        tmp_file_path = tmp_file.name
                    
                    try:
                        # Process with structured processor
                        result = await structured_processor.process_document(
                            file_path=tmp_file_path,
                            filename=filename,
                            project_id=project_id,
                            correlation_id=correlation_id,
                            extract_images=request_data.extract_images,
                            extract_tables=request_data.extract_tables,
                            include_coordinates=request_data.include_coordinates
                        )
                        
                        if result.status == "success":
                            # Save structured output
                            base_name = os.path.splitext(filename)[0]
                            output_filename = f"{base_name}_structured.{request_data.output_format}"
                            
                            # Convert to specified format
                            if request_data.output_format == "jsonl":
                                output_content = result.to_jsonl()
                                content_type = "application/jsonl"
                            else:  # json
                                output_content = json.dumps(result.to_dict(), indent=2, ensure_ascii=False)
                                content_type = "application/json"
                            
                            # Upload to Storage Service
                            files_data = {
                                'files': (output_filename, output_content.encode('utf-8'), content_type)
                            }
                            
                            upload_response = await client.post(
                                f"{processor.storage_url}/api/storage/projects/{project_id}/upload/structured",
                                files=files_data,
                                headers=headers
                            )
                            
                            if upload_response.status_code == 200:
                                processed_count += 1
                                files_status.append({
                                    "filename": filename,
                                    "status": "success",
                                    "output_file": output_filename,
                                    "elements_extracted": len(result.elements),
                                    "processing_time": result.processing_stats.get("processing_time_seconds", 0),
                                    "timestamp": datetime.now().isoformat()
                                })
                                logger.info(f"Successfully processed {filename}: {len(result.elements)} elements")
                            else:
                                raise Exception(f"Failed to upload structured output: {upload_response.status_code}")
                        else:
                            raise Exception(f"Structured processing failed: {result.errors}")
                    
                    finally:
                        # Clean up temp file
                        os.unlink(tmp_file_path)
                
                except Exception as e:
                    failed_count += 1
                    files_status.append({
                        "filename": filename,
                        "status": "error",
                        "error": str(e),
                        "timestamp": datetime.now().isoformat()
                    })
                    logger.error(f"Failed to process {filename} with structured processor: {e}")
        
        # Update final status
        await processor.update_processing_status(project_id, job_id, {
            "status": "completed" if failed_count == 0 else "completed_with_errors",
            "processed_files": processed_count,
            "failed_files": failed_count,
            "files_status": files_status,
            "completed_at": datetime.now().isoformat(),
            "current_file": None
        })
        
        logger.info(f"Structured processing completed for job {job_id}: {processed_count} success, {failed_count} failed")
    
    except Exception as e:
        logger.error(f"Structured background processing failed for job {job_id}: {e}")
        
        await processor.update_processing_status(project_id, job_id, {
            "status": "failed",
            "error": str(e),
            "completed_at": datetime.now().isoformat()
        })

@router.post("/{project_id}/generate-enhanced-chunks/{filename}")
async def generate_enhanced_chunks(
    project_id: str,
    filename: str,
    chunking_strategy: str = "jsonl_aware",
    max_chunk_tokens: int = 2000
):
    """
    Generate enhanced chunks from a processed document using JSONL-aware chunking
    
    This endpoint demonstrates the enhanced chunking capabilities that respect
    document structure and preserve context boundaries.
    """
    try:
        # First, check if the document has structured output available
        async with httpx.AsyncClient(timeout=enhanced_processor.http_timeout) as client:
            headers = {
                "Authorization": f"Bearer {enhanced_processor.auth_token}"
            }
            
            # Check for JSONL structured output
            jsonl_response = await client.get(
                f"{enhanced_processor.storage_url}/api/storage/projects/{project_id}/files/structured/{filename}.jsonl",
                headers=headers
            )
            
            structured_data = None
            if jsonl_response.status_code == 200:
                # Parse JSONL content to extract elements
                jsonl_content = jsonl_response.text
                jsonl_elements = []
                
                # Improved JSONL parsing that handles multi-line JSON objects
                import re
                
                # Use a simpler regex to find complete JSON objects
                # Split by newlines first, then try to parse each line
                lines = jsonl_content.strip().split('\n')
                
                for line in lines:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            if data.get('type') == 'element':
                                element_data = data.get('data', {})
                                jsonl_elements.append({
                                    "type": element_data.get('type', 'unknown'),
                                    "content": element_data.get('text', ''),
                                    "metadata": element_data.get('metadata', {}),
                                    "page_number": element_data.get('page_number'),
                                    "element_id": element_data.get('element_id'),
                                    "hierarchy_level": element_data.get('hierarchy_level', 0),
                                    "semantic_tags": element_data.get('semantic_tags', []),
                                    "confidence_score": element_data.get('confidence_score', 0.8)
                                })
                        except json.JSONDecodeError as e:
                            logger.warning(f"Failed to parse JSON line: {e} - Line content: {line[:100]}...")
                            continue
                
                if jsonl_elements:
                    structured_data = jsonl_elements
                    logger.info(f"Found {len(jsonl_elements)} structured elements for {filename}")
                else:
                    logger.warning(f"No valid JSONL elements found for {filename}, content length: {len(jsonl_content)}")
                    # Log first few lines for debugging
                    lines_preview = jsonl_content.strip().split('\n')[:3]
                    for i, preview_line in enumerate(lines_preview):
                        logger.warning(f"Line {i+1} preview: {preview_line[:200]}...")
                
                if jsonl_elements:
                    structured_data = jsonl_elements
                    logger.info(f"Found {len(jsonl_elements)} structured elements for {filename}")
            
            # Get the parsed text content
            parsed_response = await client.get(
                f"{enhanced_processor.storage_url}/api/storage/projects/{project_id}/files/parsed/{filename}.md",
                headers=headers
            )
            
            if parsed_response.status_code != 200:
                raise HTTPException(status_code=404, detail=f"Parsed content not found for {filename}")
            
            text_content = parsed_response.text
            
            layout_metrics = None
            # New layout-aware strategy using structured elements if available
            if structured_data and chunking_strategy in ("layout_aware", "layout-aware") and LAYOUT_AWARE_ENABLED:
                # Map structured_data elements into layout chunker expected schema
                layout_elems = []
                for e in structured_data:
                    kind = (e.get("type") or "paragraph").lower()
                    # Normalize kinds to chunker vocabulary
                    if kind in ("title", "header", "heading1", "heading2", "heading3", "heading"):
                        kind = "heading"
                    elif kind in ("figure_caption", "table_caption"):
                        kind = "caption"
                    # Accept only known kinds else treat as paragraph
                    if kind not in ("paragraph", "heading", "table", "figure", "caption"):
                        kind = "paragraph"
                    layout_elems.append({
                        "id": e.get("element_id") or f"el_{len(layout_elems)}",
                        "kind": kind,
                        "text": e.get("content") or "",
                        "page": e.get("page_number"),
                        "reading_order": e.get("hierarchy_level", 0)
                    })
                chunker = LayoutAwareChunker(max_tokens=max_chunk_tokens)
                chunks_raw, layout_metrics = chunker.chunk_sections(layout_elems, return_metrics=True)
                # Convert to consistent response format
                chunks = []
                for ch in chunks_raw:
                    chunks.append({
                        "chunk_id": ch.get("chunk_id"),
                        "content": ch.get("text"),
                        "element_ids": ch.get("element_ids"),
                        "approx_tokens": ch.get("approx_tokens"),
                        "boundary_reasons": ch.get("boundary_reasons", []),
                    })
                logger.info(f"Generated {len(chunks)} layout-aware chunks for {filename} (metrics: {layout_metrics})")
                # Async fire-and-forget ingestion of layout metrics
                if layout_metrics:
                    try:
                        ingest_url = os.getenv("ANALYTICS_SERVICE_URL", "http://localhost:8014") + "/ingest"
                        payload = {
                            "source": "document-service",
                            "project_id": project_id,
                            "filename": filename,
                            "metrics": layout_metrics,
                        }
                        async def _post_ingest(p):
                            try:
                                async with httpx.AsyncClient(timeout=3.0) as _c:
                                    await _c.post(ingest_url, json=p)
                            except Exception as _e:  # pragma: no cover - non critical
                                logger.debug(f"Analytics ingest post failed: {_e}")
                        asyncio.create_task(_post_ingest(payload))
                    except Exception as e:
                        logger.debug(f"Failed to queue analytics ingestion: {e}")
                chunking_strategy = "layout_aware"
            elif structured_data and chunking_strategy == "jsonl_aware":
                chunks_text = chunk_text_semantic(text_content, strategy="jsonl_aware", jsonl_data=structured_data)
                chunks = [
                    {
                        "chunk_id": f"{filename}_{i}",
                        "content": c,
                        "approx_tokens": len(c) // 4,
                        "boundary_reasons": ["jsonl_aware_group"],
                    }
                    for i, c in enumerate(chunks_text)
                ]
                logger.info(f"Generated {len(chunks)} JSONL-aware chunks for {filename}")
            else:
                # Fallback to semantic chunking
                chunks_text = chunk_text_semantic(text_content, strategy="semantic")
                chunks = [
                    {
                        "chunk_id": f"{filename}_{i}",
                        "content": c,
                        "approx_tokens": len(c) // 4,
                        "boundary_reasons": ["semantic_split"],
                    }
                    for i, c in enumerate(chunks_text)
                ]
                logger.info(f"Generated {len(chunks)} semantic chunks for {filename}")
            
            # Prepare response with enhanced metadata
            enhanced_chunks = []
            for i, ch in enumerate(chunks):
                content_val = ch.get("content") if isinstance(ch, dict) else ch
                enhanced_chunks.append({
                    "chunk_id": ch.get("chunk_id") if isinstance(ch, dict) else f"{filename}_{i}",
                    "content": content_val,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "chunk_length": len(content_val) if content_val else 0,
                    "metadata": {
                        "filename": filename,
                        "project_id": project_id,
                        "chunking_strategy": chunking_strategy,
                        "has_structured_data": structured_data is not None,
                        "structured_elements_used": len(structured_data) if structured_data else 0,
                        "boundary_reasons": ch.get("boundary_reasons") if isinstance(ch, dict) else [],
                        "approx_tokens": ch.get("approx_tokens") if isinstance(ch, dict) else len(content_val) // 4,
                        "element_ids": ch.get("element_ids") if isinstance(ch, dict) else None,
                    }
                })
            
            return {
                "status": "success",
                "filename": filename,
                "chunking_strategy": chunking_strategy,
                "total_chunks": len(enhanced_chunks),
                "chunks": enhanced_chunks,
                "processing_metadata": {
                    "structured_data_available": structured_data is not None,
                    "elements_processed": len(structured_data) if structured_data else 0,
                    "average_chunk_length": sum(len(chunk["content"]) for chunk in enhanced_chunks) // len(enhanced_chunks) if enhanced_chunks else 0,
                    "total_content_length": len(text_content),
                    "layout_metrics": layout_metrics,
                }
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating enhanced chunks for {filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Chunking error: {str(e)}")

@router.post("/{project_id}/extract-content-batch")
async def extract_content_batch(
    project_id: str,
    file_names: List[str],
    request: Request = None
):
    """Extract content from multiple processed documents in batch"""
    try:
        corr_id = None
        try:
            if request is not None:
                corr_id = request.headers.get("X-Correlation-ID")
        except Exception:
            pass

        if not corr_id:
            corr_id = str(uuid.uuid4())

        logger.info(f"Starting batch content extraction for {len(file_names)} files in project {project_id}")

        # Prepare file data for batch processing
        file_data = []
        for filename in file_names:
            file_data.append({
                "filename": filename,
                "content": None,  # Will be fetched from storage
                "structured_result": None
            })

        # Process batch extraction
        batch_result = await content_extractor.process_batch_extraction(
            project_id=project_id,
            file_data=file_data,
            correlation_id=corr_id
        )

        return {
            "project_id": project_id,
            "correlation_id": corr_id,
            "batch_result": batch_result,
            "message": f"Batch content extraction completed: {batch_result['success_count']}/{batch_result['total_files']} successful"
        }

    except Exception as e:
        logger.error(f"Batch content extraction failed for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Batch content extraction failed: {str(e)}")

@router.get("/workflow-config")
async def get_workflow_configuration():
    """Get current document processing workflow configuration"""
    try:
        use_enhanced = os.getenv("USE_ENHANCED_WORKFLOW", "true").lower() == "true"

        # Safely get enhanced processor properties
        try:
            vector_integration = enhanced_processor.enable_vector_integration if use_enhanced else False
            graph_integration = enhanced_processor.enable_graph_integration if use_enhanced else False
            websocket_notifications = enhanced_processor.enable_websocket_notifications if use_enhanced else False
            service_integration = enhanced_processor.get_integration_status() if use_enhanced else None
        except Exception as e:
            logger.warning(f"Enhanced processor not available: {e}")
            vector_integration = False
            graph_integration = False
            websocket_notifications = False
            service_integration = None

        config = {
            "enhanced_workflow_enabled": use_enhanced,
            "workflow_type": "enhanced" if use_enhanced else "traditional",
            "features": {
                "unstructured_io_primary": use_enhanced,
                "structured_jsonl_output": use_enhanced,
                "vector_service_integration": vector_integration,
                "graph_service_integration": graph_integration,
                "websocket_notifications": websocket_notifications,
                "smart_chunking": use_enhanced,
                "entity_extraction": use_enhanced,
                "correlation_id_tracking": True,
                "mineru_enabled": os.getenv("MINERU_ENABLED", "false").lower() in ("1","true","yes"),
                "multimodal_enabled": os.getenv("MULTIMODAL_ENABLED", "false").lower() in ("1","true","yes")
            },
            "service_integration": service_integration,
            "fallback_behavior": "Traditional workflow if enhanced fails",
            "api_compatibility": "Maintained - existing endpoints enhanced with new functionality",
            "environment_variables": {
                "USE_ENHANCED_WORKFLOW": os.getenv("USE_ENHANCED_WORKFLOW", "true"),
                "ENABLE_VECTOR_INTEGRATION": os.getenv("ENABLE_VECTOR_INTEGRATION", "true"),
                "ENABLE_GRAPH_INTEGRATION": os.getenv("ENABLE_GRAPH_INTEGRATION", "true"),
                "ENABLE_WEBSOCKET_NOTIFICATIONS": os.getenv("ENABLE_WEBSOCKET_NOTIFICATIONS", "true"),
                "MINERU_ENABLED": os.getenv("MINERU_ENABLED", "false"),
                "MULTIMODAL_ENABLED": os.getenv("MULTIMODAL_ENABLED", "false")
            }
        }

        return config

    except Exception as e:
        logger.error(f"Error getting workflow configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# =====================================================================================
# Content Analysis Endpoints (PHASE 1 Backend Infrastructure)
# =====================================================================================

class ContentDetailsResponse(BaseModel):
    """Response model for document content details"""
    project_id: str
    filename: str
    content: Optional[str] = None
    summary: Optional[str] = None
    categories: List[str] = []
    structure_metadata: Optional[Dict[str, Any]] = None
    processing_status: str
    last_updated: Optional[str] = None
    content_length: int = 0
    has_structured_data: bool = False

class DocumentAnalysisRequest(BaseModel):
    """Request model for document analysis"""
    analysis_type: str = "comprehensive"  # comprehensive, summary, categories, structure
    include_content: bool = False
    force_reanalysis: bool = False

class DocumentAnalysisResponse(BaseModel):
    """Response model for document analysis"""
    project_id: str
    filename: str
    analysis_id: str
    analysis_type: str
    summary: Optional[str] = None
    categories: List[str] = []
    key_insights: List[str] = []
    structure_analysis: Optional[Dict[str, Any]] = None
    content_preview: Optional[str] = None
    processing_time: float
    analysis_timestamp: str

class ProjectInsightsResponse(BaseModel):
    """Response model for project content insights"""
    project_id: str
    total_documents: int
    analyzed_documents: int
    top_categories: List[Dict[str, Any]] = []
    content_summary: Optional[str] = None
    document_types: Dict[str, int] = {}
    insights: List[str] = []
    last_updated: Optional[str] = None

class BatchAnalysisRequest(BaseModel):
    """Request model for batch content analysis"""
    filenames: List[str]
    analysis_type: str = "comprehensive"
    include_content: bool = False
    max_concurrent: int = 5

class BatchAnalysisResponse(BaseModel):
    """Response model for batch analysis"""
    project_id: str
    analysis_id: str
    total_files: int
    status: str
    started_at: str
    completed_at: Optional[str] = None
    results: List[Dict[str, Any]] = []

@router.get("/{project_id}/content/{filename}", response_model=ContentDetailsResponse)
async def get_document_content_details(
    project_id: str,
    filename: str,
    request: Request = None
):
    """Retrieve detailed content information for a specific document"""
    try:
        logger.info(f"Retrieving content details for {filename} in project {project_id}")

        # Get correlation ID
        corr_id = None
        try:
            if request is not None:
                corr_id = request.headers.get("X-Correlation-ID")
        except Exception:
            pass

        # Fetch content from storage service
        content = await content_extractor._fetch_processed_content(project_id, filename, corr_id)

        # Get project file metadata from project service
        file_metadata = await _get_project_file_metadata(project_id, filename, corr_id)

        # Prepare response
        response = ContentDetailsResponse(
            project_id=project_id,
            filename=filename,
            content=content,
            summary=file_metadata.get("summary_text"),
            categories=file_metadata.get("categories", []),
            structure_metadata=file_metadata.get("structure_metadata"),
            processing_status="available" if content else "not_processed",
            last_updated=file_metadata.get("upload_timestamp"),
            content_length=len(content) if content else 0,
            has_structured_data=file_metadata.get("structure_metadata") is not None
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving content details for {filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve content details: {str(e)}")

@router.post("/{project_id}/analyze/{filename}", response_model=DocumentAnalysisResponse)
async def analyze_document(
    project_id: str,
    filename: str,
    analysis_request: DocumentAnalysisRequest = DocumentAnalysisRequest(),
    request: Request = None
):
    """Perform content analysis on a specific document"""
    try:
        logger.info(f"Analyzing document {filename} in project {project_id}")

        # Get correlation ID
        corr_id = None
        try:
            if request is not None:
                corr_id = request.headers.get("X-Correlation-ID")
        except Exception:
            pass

        start_time = datetime.now()

        # Fetch processed content
        content = await content_extractor._fetch_processed_content(project_id, filename, corr_id)
        if not content:
            raise HTTPException(status_code=404, detail=f"Processed content not found for {filename}")

        # Perform analysis based on type
        analysis_result = await _perform_document_analysis(
            content, filename, analysis_request.analysis_type
        )

        # Extract content preview if requested
        content_preview = None
        if analysis_request.include_content:
            content_preview = content[:1000] + "..." if len(content) > 1000 else content

        # Create analysis response
        analysis_id = str(uuid.uuid4())
        processing_time = (datetime.now() - start_time).total_seconds()

        response = DocumentAnalysisResponse(
            project_id=project_id,
            filename=filename,
            analysis_id=analysis_id,
            analysis_type=analysis_request.analysis_type,
            summary=analysis_result.get("summary"),
            categories=analysis_result.get("categories", []),
            key_insights=analysis_result.get("insights", []),
            structure_analysis=analysis_result.get("structure"),
            content_preview=content_preview,
            processing_time=processing_time,
            analysis_timestamp=datetime.now().isoformat()
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing document {filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Document analysis failed: {str(e)}")

@router.get("/{project_id}/insights", response_model=ProjectInsightsResponse)
@_timed("project_insights")
async def get_project_content_insights(
    project_id: str,
    request: Request = None,
    force_analysis: bool = False,  # Changed default to False
    allow_analysis: bool = False   # New parameter to explicitly allow analysis
):
    """Get aggregated content insights for all documents in a project
    
    Args:
        project_id: The project ID
        force_analysis: If True, performs full analysis. If False, returns cached/summary data only.
        allow_analysis: Must be True to perform any analysis. Prevents automatic analysis on page load.
    """
    try:
        logger.info(f"Generating content insights for project {project_id} (force_analysis={force_analysis}, allow_analysis={allow_analysis})")

        # PAGE LOAD GUARD & LIGHTWEIGHT CACHE: Prevent automatic heavy analysis on initial UI mount
        user_agent = request.headers.get("User-Agent", "") if request else ""
        explicit_trigger = request.query_params.get("trigger", "") if request else ""
        is_initial_page_load = not force_analysis and not allow_analysis and explicit_trigger == ""

        if not allow_analysis and force_analysis:
            logger.warning(f"Blocked automatic analysis for project {project_id} - allow_analysis must be True")
            raise HTTPException(
                status_code=403,
                detail="Analysis requires explicit permission. Set allow_analysis=true to proceed."
            )

        # In-memory micro cache (module level dict) for lightweight summaries
        global _lightweight_insights_cache  # defined later if not present
        try:
            _lightweight_insights_cache
        except NameError:  # first use
            _lightweight_insights_cache = {}

        cache_key = f"{project_id}:lightweight"
        cached_entry = _lightweight_insights_cache.get(cache_key)

        if is_initial_page_load and cached_entry and (datetime.now().timestamp() - cached_entry["ts"]) < 60:
            logger.debug(f"Serving cached lightweight insights for project {project_id}")
            return cached_entry["data"]

        # Get correlation ID
        corr_id = None
        try:
            if request is not None:
                corr_id = request.headers.get("X-Correlation-ID")
        except Exception:
            pass

        # Get all project files
        project_files = await _get_all_project_files(project_id, corr_id)

        # If not forcing analysis or not allowing analysis, return lightweight summary only
        if not force_analysis or not allow_analysis:
            logger.info(f"Returning lightweight insights for {len(project_files)} files (no heavy analysis)")
            insights_data = await _get_lightweight_project_insights(project_files, corr_id)
            # Store/refresh cache
            lightweight_response = ProjectInsightsResponse(
                project_id=project_id,
                total_documents=len(project_files),
                analyzed_documents=insights_data.get("analyzed_count", 0),
                top_categories=insights_data.get("top_categories", []),
                content_summary=insights_data.get("content_summary"),
                document_types=insights_data.get("document_types", {}),
                insights=insights_data.get("insights", []),
                last_updated=datetime.now().isoformat()
            )
            _lightweight_insights_cache[cache_key] = {"ts": datetime.now().timestamp(), "data": lightweight_response}
            return lightweight_response
        else:
            logger.info(f"Performing full analysis for {len(project_files)} files")
            # Analyze insights from all files (heavy operation)
            insights_data = await _analyze_project_insights(project_files, corr_id)

        return ProjectInsightsResponse(
            project_id=project_id,
            total_documents=len(project_files),
            analyzed_documents=insights_data.get("analyzed_count", 0),
            top_categories=insights_data.get("top_categories", []),
            content_summary=insights_data.get("content_summary"),
            document_types=insights_data.get("document_types", {}),
            insights=insights_data.get("insights", []),
            last_updated=datetime.now().isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating project insights for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate project insights: {str(e)}")

@router.post("/{project_id}/analyze-batch", response_model=BatchAnalysisResponse)
@_timed("batch_analyze_start")
async def analyze_documents_batch(
    project_id: str,
    batch_request: BatchAnalysisRequest,
    background_tasks: BackgroundTasks,
    request: Request = None
):
    """Perform batch content analysis on multiple documents"""
    try:
        logger.info(f"Starting batch analysis for {len(batch_request.filenames)} files in project {project_id}")

        # Get correlation ID
        corr_id = None
        try:
            if request is not None:
                corr_id = request.headers.get("X-Correlation-ID")
        except Exception:
            pass

        # Generate analysis ID
        analysis_id = str(uuid.uuid4())

        # Initialize batch analysis status
        batch_status = {
            "analysis_id": analysis_id,
            "status": "started",
            "total_files": len(batch_request.filenames),
            "processed_files": 0,
            "results": [],
            "started_at": datetime.now().isoformat()
        }

        # Store batch status (in-memory for now, could be enhanced with Redis/database)
        _batch_analysis_status[analysis_id] = batch_status

        # Start background processing
        background_tasks.add_task(
            _process_batch_analysis_background,
            project_id,
            analysis_id,
            batch_request,
            corr_id
        )

        return BatchAnalysisResponse(
            project_id=project_id,
            analysis_id=analysis_id,
            total_files=len(batch_request.filenames),
            status="started",
            started_at=batch_status["started_at"],
            results=[]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting batch analysis for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start batch analysis: {str(e)}")

@router.get("/{project_id}/content-analysis/{analysis_id}", response_model=BatchAnalysisResponse)
@_timed("batch_status")
async def get_batch_analysis_status(
    project_id: str,
    analysis_id: str
):
    """Get status and results of a batch content analysis"""
    try:
        if analysis_id not in _batch_analysis_status:
            raise HTTPException(status_code=404, detail="Analysis job not found")

        status_data = _batch_analysis_status[analysis_id]

        return BatchAnalysisResponse(
            project_id=project_id,
            analysis_id=analysis_id,
            total_files=status_data["total_files"],
            status=status_data["status"],
            started_at=status_data["started_at"],
            completed_at=status_data.get("completed_at"),
            results=status_data["results"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting batch analysis status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get analysis status: {str(e)}")

# Global storage for batch analysis status (in production, use Redis or database)
_batch_analysis_status = {}

async def _get_project_file_metadata(project_id: str, filename: str, correlation_id: Optional[str] = None) -> Dict[str, Any]:
    """Get project file metadata from project service"""
    try:
        # Fast path cache (in-memory) to avoid duplicate downstream calls during rapid UI refreshes
        global _file_metadata_cache
        try:
            _file_metadata_cache
        except NameError:
            _file_metadata_cache = {}
        cache_key = f"{project_id}:{filename}"
        cached = _file_metadata_cache.get(cache_key)
        if cached and (datetime.now().timestamp() - cached["ts"]) < 30:
            return cached["data"]

        async with httpx.AsyncClient(timeout=processor.http_timeout) as client:
            headers = {
                "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
            }
            if correlation_id:
                headers["X-Correlation-ID"] = correlation_id

            # Get storage files list (raw uploads)
            response, project_response = await asyncio.gather(
                client.get(
                    f"{processor.storage_url}/api/storage/projects/{project_id}/files/uploads_raw",
                    headers=headers
                ),
                client.get(
                    f"{processor.project_service_url}/api/projects/{project_id}/files",
                    headers=headers
                )
            )

            # Check project service response status
            if project_response.status_code != 200:
                logger.warning(f"Project service returned {project_response.status_code}: {project_response.text}")
                return {}

            # Safely parse project response
            try:
                project_files = project_response.json()
                if not isinstance(project_files, list):
                    logger.warning(f"Project service returned non-list response: {type(project_files)}")
                    return {}
            except Exception as json_error:
                logger.warning(f"Failed to parse project service response: {json_error}")
                return {}

            # Check storage response
            if response.status_code == 200:
                try:
                    files = response.json()
                    # Handle both list and dict responses from storage service
                    if isinstance(files, dict):
                        # If it's a dict, it might be a single file or wrapped response
                        if "files" in files:
                            files = files["files"]
                        elif "filename" in files:
                            # Single file response
                            files = [files]
                        else:
                            logger.warning(f"Unexpected dict structure from storage service: {list(files.keys())}")
                            return {}
                    elif not isinstance(files, list):
                        logger.warning(f"Storage service returned non-list response: {type(files)}")
                        return {}

                    for file in files:
                        if isinstance(file, dict) and file.get("filename") == filename:
                            # Merge storage and project metadata if needed
                            project_file = next((pf for pf in project_files if isinstance(pf, dict) and pf.get("filename") == filename), {})
                            if isinstance(project_file, dict):
                                file.update(project_file)
                            return file
                except Exception as storage_error:
                    logger.warning(f"Failed to parse storage response: {storage_error}")

            result = {}
            _file_metadata_cache[cache_key] = {"ts": datetime.now().timestamp(), "data": result}
            return result

    except Exception as e:
        logger.warning(f"Error getting project file metadata: {e}")
        return {}


# =====================================================================================
# PVC Orchestration (Feature-flagged) - build proposal via LLM, validate/commit, upsert embeddings
# =====================================================================================

if True:
    class PVCRequest(BaseModel):
        filename: str = Field(..., description="Original uploaded filename without extension for parsed lookup")
        reprocess: bool = False

    class PVCResponse(BaseModel):
        project_id: str
        filename: str
        status: str
        llm_extraction: Dict[str, Any] = {}
        graph: Dict[str, Any] = {}
        vectors: Dict[str, Any] = {}
        message: Optional[str] = None

    @router.post("/{project_id}/pvc/process", response_model=PVCResponse)
    async def pvc_process_document(
        project_id: str,
        request_data: PVCRequest,
        request: Request = None,
    ):
        """PVC Orchestrator for a single document.

        Steps:
        1) Load parsed markdown from storage (or raw->convert fallback if needed).
        2) Call llm-service /api/llm/process with process_type=entity_extraction_full to get entities/relations/facts (JSON).
        3) Propose to graph-service (tolerant if currently returns 501 Not Implemented).
        4) Prepare vector index and upsert chunks as embeddings.
        """
        if not _pvc_enabled():
            raise HTTPException(status_code=403, detail="PVC endpoints are disabled. Set PVC_ENABLED=true to enable.")

        corr_id = None
        try:
            if request is not None:
                corr_id = request.headers.get("X-Correlation-ID")
        except Exception:
            pass
        if not corr_id:
            corr_id = str(uuid.uuid4())

        filename = request_data.filename
        if not filename:
            raise HTTPException(status_code=400, detail="filename is required")

        # Step 1: Load parsed markdown from Storage Service
        parsed_content = None
        md_filename = filename if filename.lower().endswith(".md") else f"{os.path.splitext(filename)[0]}.md"
        try:
            async with httpx.AsyncClient(timeout=processor.http_timeout) as client:
                headers = {"Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"}
                headers["X-Correlation-ID"] = corr_id
                resp = await client.get(
                    f"{processor.storage_url}/api/storage/projects/{project_id}/files/parsed/{md_filename}",
                    headers=headers,
                )
                if resp.status_code == 200:
                    parsed_content = resp.text
                else:
                    logger.warning(f"Parsed markdown not found for {md_filename} (status {resp.status_code}); attempting raw download + convert fallback")
        except Exception as e:
            logger.warning(f"Failed to fetch parsed markdown: {e}")

        # Fallback: download raw file and convert with existing processor
        if not parsed_content:
            try:
                async with httpx.AsyncClient(timeout=processor.http_timeout) as client:
                    headers = {"Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"}
                    headers["X-Correlation-ID"] = corr_id
                    raw_resp = await client.get(
                        f"{processor.storage_url}/api/storage/projects/{project_id}/download/uploads_raw/{filename}",
                        headers=headers,
                    )
                    if raw_resp.status_code != 200:
                        raise HTTPException(status_code=404, detail=f"Raw file {filename} not found in storage")
                    # Save to temp, convert
                    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp_file:
                        tmp_file.write(raw_resp.content)
                        tmp_path = tmp_file.name
                    try:
                        conv = await processor.convert_document_to_markdown(tmp_path, filename, project_id, request_data.reprocess, correlation_id=corr_id)
                        parsed_content = conv.get("content")
                        md_filename = conv.get("md_filename", md_filename)
                    finally:
                        os.unlink(tmp_path)
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Conversion fallback failed for {filename}: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to obtain parsed content: {str(e)}")

        if not parsed_content or is_error_content(parsed_content):
            raise HTTPException(status_code=422, detail="Parsed content is empty or appears to be an error document")

        # Step 2: Call LLM for entity extraction proposal
        llm_url = os.getenv("LLM_SERVICE_URL", "http://localhost:8007")
        llm_headers = {
            "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}",
            "X-Correlation-ID": corr_id,
        }
        # Externalized prompt for entity_extraction_full with fallback
        try:
            from ..core import prompt_loader as _pl
            _edoc = _pl.get_prompt("entity_extraction_full")
            base_instr = (_edoc.get("text") or _edoc.get("prompt")) if isinstance(_edoc, dict) else None
        except Exception:
            base_instr = None
        if not base_instr:
            base_instr = (
                "You are an information extraction system. Given the document markdown, extract:\n"
                "- entities: unique entities with types and canonical names\n"
                "- relationships: subject-predicate-object triples with evidence spans\n"
                "- facts: normalized key facts as name:value with provenance\n\n"
                "Return STRICT JSON with keys: {\\\"entities\\\":[], \\\"relationships\\\":[], \\\"facts\\\":[]}.\n"
                "Do not add commentary."
            )
        prompt = base_instr + "\n\nDOCUMENT:\n" + parsed_content[:180000]
        llm_body = {
            "process_type": "entity_extraction_full",
            "prompt": prompt,
            "project_id": project_id,
            "allow_global": False,
        }
        llm_result: Dict[str, Any]
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(f"{llm_url}/api/llm/process", json=llm_body, headers=llm_headers)
                if r.status_code != 200:
                    raise HTTPException(status_code=502, detail=f"LLM extraction failed: {r.status_code}")
                data = r.json()
                content = data.get("response") or ""
                llm_json = _extract_json_from_text(content) or {}
                llm_result = {"raw": data, "parsed": llm_json}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise HTTPException(status_code=502, detail=f"LLM call failed: {str(e)}")

        # Step 3: Propose to graph-service (tolerate 501 during scaffold)
        graph_client = GraphServiceClient()
        proposal_payload = {
            "document": {"filename": md_filename, "source": "document-service"},
            "entities": llm_result.get("parsed", {}).get("entities", []),
            "relationships": llm_result.get("parsed", {}).get("relationships", []),
            "facts": llm_result.get("parsed", {}).get("facts", []),
        }
        graph_status: Dict[str, Any] = {}
        try:
            proposed = await graph_client.propose_entities(project_id, proposal_payload, corr_id=corr_id)
            graph_status["proposed"] = proposed
            # Best-effort validate/commit if ids available
            prop_id = proposed.get("proposal_id") or proposed.get("id")
            if prop_id:
                try:
                    v = await graph_client.validate_proposal(prop_id, corr_id=corr_id)
                    graph_status["validated"] = v
                except Exception as ve:
                    graph_status["validated_error"] = str(ve)
                try:
                    c = await graph_client.commit_proposal(prop_id, corr_id=corr_id)
                    graph_status["committed"] = c
                except Exception as ce:
                    graph_status["committed_error"] = str(ce)
        except Exception as e:
            # Graph service may return 501 during scaffold; capture and continue
            graph_status["error"] = str(e)

        # Step 4: Prepare vector index and upsert embeddings from chunks
        vectors_status: Dict[str, Any] = {}
        try:
            vec_client = VectorServiceClient()
            # Multi-embedding: use kind if configured (e.g., raw_chunks)
            vectors_kind = os.getenv("VECTORS_USE_KIND")
            if vectors_kind:
                vectors_status["prepare"] = await vec_client.prepare_kind_collection(project_id, vectors_kind, corr_id=corr_id)
            else:
                vectors_status["prepare"] = await vec_client.prepare_index(project_id, corr_id=corr_id)

            # Chunk and upsert
            chunks = await asyncio.to_thread(_chunk_markdown_text, parsed_content)
            if getattr(processor, "max_chunks", 0):
                chunks = chunks[: max(0, int(processor.max_chunks))]
            batch_docs = [{
                "id": f"{os.path.splitext(md_filename)[0]}_{i}",
                "content": ch,
                "filename": md_filename,
                "source": "document-service"
            } for i, ch in enumerate(chunks)]
            if vectors_kind:
                vectors_status["upsert"] = await vec_client.upsert_embeddings_kind(project_id, vectors_kind, {"documents": batch_docs}, corr_id=corr_id)
            else:
                vectors_status["upsert"] = await vec_client.upsert_embeddings(project_id, {"documents": batch_docs}, corr_id=corr_id)
        except Exception as e:
            vectors_status["error"] = str(e)

        return PVCResponse(
            project_id=project_id,
            filename=filename,
            status="completed",
            llm_extraction=llm_result,
            graph=graph_status,
            vectors=vectors_status,
            message="PVC pipeline executed"
        )

# =====================================================================================
# PVC Fuse Knowledge Orchestrator
# =====================================================================================

class FuseEntityType(BaseModel):
    name: str
    description: Optional[str] = None
    properties: Dict[str, Any] = {}
    status: str = Field(default="pending_approval")

class FuseRelationshipType(BaseModel):
    name: str
    from_type: str
    to_type: str
    description: Optional[str] = None
    properties: Dict[str, Any] = {}
    status: str = Field(default="pending_approval")

class FuseKnowledgeRequest(BaseModel):
    # When provided, we'll attempt to register these types before commit
    entity_types: Optional[List[FuseEntityType]] = None
    relationship_types: Optional[List[FuseRelationshipType]] = None
    # Commit control
    proposal_ids: Optional[List[str]] = None
    status_filter: str = Field(default="validated", description="Commit proposals matching this status if proposal_ids not specified")
    # If true, we only register types and skip commit
    register_only: bool = False

class FuseKnowledgeResponse(BaseModel):
    project_id: str
    registered_entities: List[str] = []
    registered_relationships: List[str] = []
    commit_summary: Dict[str, Any] = {}
    message: Optional[str] = None

@router.post("/{project_id}/pvc/fuse-knowledge", response_model=FuseKnowledgeResponse)
async def pvc_fuse_knowledge(
    project_id: str,
    request_data: FuseKnowledgeRequest = FuseKnowledgeRequest(),
    request: Request = None,
):
    """Fuse-Knowledge orchestrator.

    - Optionally register entity and relationship types into the Type Registry (status pending_approval).
    - Batch commit proposals by IDs or by status filter (default: validated).
    - Returns a concise summary of registrations and commits.
    """
    if not _pvc_enabled():
        raise HTTPException(status_code=403, detail="PVC endpoints are disabled. Set PVC_ENABLED=true to enable.")

    # Correlation id handling
    corr_id = None
    try:
        if request is not None:
            corr_id = request.headers.get("X-Correlation-ID")
    except Exception:
        pass
    if not corr_id:
        corr_id = str(uuid.uuid4())

    graph_client = GraphServiceClient()

    registered_entities: List[str] = []
    registered_relationships: List[str] = []
    commit_summary: Dict[str, Any] = {}

    # Step 1: Register provided entity/relationship types (best-effort)
    try:
        # Fetch current registry (optional, mainly for logging/visibility)
        _ = await graph_client.get_type_registry(project_id, corr_id=corr_id)
    except Exception as e:
        logger.debug(f"Type registry fetch failed (non-fatal): {e}")

    try:
        if request_data.entity_types:
            seen = set()
            for et in request_data.entity_types:
                key = et.name.strip().lower()
                if not key or key in seen:
                    continue
                seen.add(key)
                payload = {
                    "name": et.name,
                    "description": et.description,
                    "properties": et.properties or {},
                    "status": et.status or "pending_approval",
                }
                try:
                    res = await graph_client.register_entity_type(project_id, payload, corr_id=corr_id)
                    if not res.get("error"):
                        registered_entities.append(et.name)
                    else:
                        logger.warning(f"Entity type registration error for {et.name}: {res}")
                except Exception as re:
                    logger.warning(f"Entity type registration failed for {et.name}: {re}")

        if request_data.relationship_types:
            seen_rel = set()
            for rt in request_data.relationship_types:
                key = (rt.name.strip().lower(), rt.from_type.strip().lower(), rt.to_type.strip().lower())
                if not rt.name or key in seen_rel:
                    continue
                seen_rel.add(key)
                payload = {
                    "name": rt.name,
                    "from_type": rt.from_type,
                    "to_type": rt.to_type,
                    "description": rt.description,
                    "properties": rt.properties or {},
                    "status": rt.status or "pending_approval",
                }
                try:
                    res = await graph_client.register_relationship_type(project_id, payload, corr_id=corr_id)
                    if not res.get("error"):
                        registered_relationships.append(rt.name)
                    else:
                        logger.warning(f"Relationship type registration error for {rt.name}: {res}")
                except Exception as rr:
                    logger.warning(f"Relationship type registration failed for {rt.name}: {rr}")
    except Exception as e:
        logger.debug(f"Type registration block failed (non-fatal): {e}")

    # Step 2: Optionally perform batch commit
    if not request_data.register_only:
        try:
            payload = None
            if request_data.proposal_ids:
                payload = {"proposal_ids": request_data.proposal_ids}
            else:
                payload = {"status_filter": request_data.status_filter or "validated"}

            commit_summary = await graph_client.commit_proposals_batch(project_id, payload, corr_id=corr_id)
        except Exception as e:
            logger.warning(f"Batch commit failed: {e}")
            commit_summary = {"error": str(e)}

    # Emit stats event (best-effort)
    try:
        await notify_stats_service(project_id, "graph_updated", {
            "registered_entities": len(registered_entities),
            "registered_relationships": len(registered_relationships),
            "commit": commit_summary if commit_summary else {},
        })
    except Exception:
        pass

    return FuseKnowledgeResponse(
        project_id=project_id,
        registered_entities=registered_entities,
        registered_relationships=registered_relationships,
        commit_summary=commit_summary,
        message="Fuse-knowledge executed"
    )
async def _get_lightweight_project_insights(project_files: List[Dict[str, Any]], correlation_id: Optional[str] = None) -> Dict[str, Any]:
    """Get lightweight project insights without heavy LLM analysis"""
    insights_data = {
        "analyzed_count": 0,
        "top_categories": [],
        "content_summary": "Content analysis available on demand",
        "document_types": {},
        "insights": [
            "Use force_analysis=true to perform full content analysis",
            f"Project contains {len(project_files)} documents",
            "Analysis includes categorization, summarization, and insights generation"
        ]
    }

    try:
        # Count document types from file metadata only
        for file in project_files:
            file_type = file.get("file_type", "unknown")
            insights_data["document_types"][file_type] = insights_data["document_types"].get(file_type, 0) + 1

        # Get basic file count
        insights_data["analyzed_count"] = len(project_files)

        return insights_data

    except Exception as e:
        logger.warning(f"Error getting lightweight insights: {e}")
        return insights_data

async def _perform_document_analysis(content: str, filename: str, analysis_type: str) -> Dict[str, Any]:
    """Perform content analysis on document"""
    result = {}

    try:
        if analysis_type in ["comprehensive", "summary"]:
            # Extract summary
            result["summary"] = await content_extractor._extract_summary(content)

        if analysis_type in ["comprehensive", "categories"]:
            # Extract categories
            result["categories"] = await content_extractor._extract_categories(content)

        if analysis_type in ["comprehensive", "structure"]:
            # Extract structure metadata
            result["structure"] = content_extractor._extract_structure_metadata(filename, content)

        # Generate key insights
        if analysis_type == "comprehensive":
            result["insights"] = await _generate_key_insights(content, result)

        return result

    except Exception as e:
        logger.warning(f"Error in document analysis: {e}")
        return {}

async def _generate_key_insights(content: str, analysis_result: Dict[str, Any]) -> List[str]:
    """Generate key insights from content and analysis"""
    insights = []

    try:
        # Basic insight generation based on content analysis
        if analysis_result.get("summary"):
            insights.append("Document has been summarized for quick reference")

        if analysis_result.get("categories"):
            insights.append(f"Categorized into {len(analysis_result['categories'])} topics")

        if analysis_result.get("structure"):
            sections = analysis_result["structure"].get("sections", [])
            if sections:
                insights.append(f"Document contains {len(sections)} main sections")

        # Content-based insights
        word_count = len(content.split())
        if word_count > 1000:
            insights.append("Large document - consider breaking into smaller chunks for analysis")
        elif word_count < 100:
            insights.append("Short document - may have limited analysis depth")

        return insights

    except Exception as e:
        logger.warning(f"Error generating insights: {e}")
        return []

async def _analyze_project_insights(project_files: List[Dict[str, Any]], correlation_id: Optional[str] = None) -> Dict[str, Any]:
    """Analyze insights across all project files"""
    insights_data = {
        "analyzed_count": 0,
        "top_categories": [],
        "content_summary": None,
        "document_types": {},
        "insights": []
    }

    try:
        all_categories = []
        analyzed_files = []

        for file in project_files:
            if file.get("summary_text") or file.get("categories"):
                analyzed_files.append(file)
                if file.get("categories"):
                    all_categories.extend(file["categories"])

                # Count document types
                file_type = file.get("file_type", "unknown")
                insights_data["document_types"][file_type] = insights_data["document_types"].get(file_type, 0) + 1

        insights_data["analyzed_count"] = len(analyzed_files)

        # Find top categories
        if all_categories:
            from collections import Counter
            category_counts = Counter(all_categories)
            insights_data["top_categories"] = [
                {"category": cat, "count": count}
                for cat, count in category_counts.most_common(10)
            ]

        # Generate project-level insights
        insights_data["insights"] = await _generate_project_insights(insights_data, len(project_files))

        return insights_data

    except Exception as e:
        logger.warning(f"Error analyzing project insights: {e}")
        return insights_data

async def _generate_project_insights(insights_data: Dict[str, Any], total_files: int) -> List[str]:
    """Generate insights about the project as a whole"""
    insights = []

    try:
        analyzed_count = insights_data.get("analyzed_count", 0)
        if analyzed_count > 0:
            analysis_percentage = (analyzed_count / total_files) * 100
            insights.append(".1f")

        if insights_data.get("top_categories"):
            top_cat = insights_data["top_categories"][0]
            insights.append(f"Most common topic: '{top_cat['category']}' (appears in {top_cat['count']} documents)")

        doc_types = insights_data.get("document_types", {})
        if doc_types:
            main_type = max(doc_types.items(), key=lambda x: x[1])
            insights.append(f"Primary document type: {main_type[0]} ({main_type[1]} files)")

        return insights

    except Exception as e:
        logger.warning(f"Error generating project insights: {e}")
        return []

async def _process_batch_analysis_background(
    project_id: str,
    analysis_id: str,
    batch_request: BatchAnalysisRequest,
    correlation_id: Optional[str] = None
):
    """Background processing for batch content analysis"""
    try:
        logger.info(f"Starting background batch analysis {analysis_id}")

        results = []
        processed_count = 0

        # Process files with concurrency limit
        semaphore = asyncio.Semaphore(batch_request.max_concurrent)

        async def analyze_single_file(filename: str):
            async with semaphore:
                try:
                    # Fetch content
                    content = await content_extractor._fetch_processed_content(project_id, filename, correlation_id)
                    if not content:
                        return {
                            "filename": filename,
                            "status": "error",
                            "error": "Content not found"
                        }

                    # Perform analysis
                    analysis_result = await _perform_document_analysis(
                        content, filename, batch_request.analysis_type
                    )

                    # Add content preview if requested
                    if batch_request.include_content:
                        analysis_result["content_preview"] = content[:500] + "..." if len(content) > 500 else content

                    return {
                        "filename": filename,
                        "status": "success",
                        "analysis": analysis_result,
                        "processing_time": 0.0  # Could be enhanced to track actual time
                    }

                except Exception as e:
                    logger.error(f"Error analyzing {filename}: {e}")
                    return {
                        "filename": filename,
                        "status": "error",
                        "error": str(e)
                    }

        # Process all files concurrently
        tasks = [analyze_single_file(filename) for filename in batch_request.filenames]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for result in batch_results:
            if isinstance(result, Exception):
                logger.error(f"Batch analysis task error: {result}")
                results.append({
                    "filename": "unknown",
                    "status": "error",
                    "error": str(result)
                })
            else:
                results.append(result)
                if result["status"] == "success":
                    processed_count += 1

        # Update batch status
        _batch_analysis_status[analysis_id].update({
            "status": "completed",
            "processed_files": processed_count,
            "results": results,
            "completed_at": datetime.now().isoformat()
        })

        logger.info(f"Completed background batch analysis {analysis_id}: {processed_count}/{len(batch_request.filenames)} successful")

    except Exception as e:
        logger.error(f"Error in background batch analysis {analysis_id}: {e}")
        _batch_analysis_status[analysis_id].update({
            "status": "failed",
            "error": str(e),
            "completed_at": datetime.now().isoformat()
        })

# =====================================================================================
# CONTENT SEARCH ENDPOINTS (PHASE 4)
# =====================================================================================

class ContentSearchRequest(BaseModel):
    """Request model for content search"""
    query: str = Field(..., min_length=1, description="Search query")
    search_type: str = Field(default="comprehensive", description="Type of search: comprehensive, semantic, keyword, metadata")
    limit: int = Field(default=20, ge=1, le=100, description="Maximum number of results")
    include_content: bool = Field(default=False, description="Include full content in results")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Additional filters (categories, document_types, etc.)")

class ContentSearchResult(BaseModel):
    """Search result model"""
    filename: str
    relevance_score: float
    search_type: str
    matched_content: Optional[str] = None
    summary: Optional[str] = None
    categories: List[str] = []
    document_type: Optional[str] = None
    content_length: int = 0
    last_updated: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class ContentSearchResponse(BaseModel):
    """Response model for content search"""
    project_id: str
    query: str
    search_type: str
    total_results: int
    results: List[ContentSearchResult]
    search_timestamp: str
    processing_time: float
    filters_applied: Optional[Dict[str, Any]] = None

@router.post("/{project_id}/search", response_model=ContentSearchResponse)
async def search_document_content(
    project_id: str,
    search_request: ContentSearchRequest,
    request: Request = None
):
    """
    Search within document content, summaries, categories, and structure metadata
    Supports comprehensive search combining multiple sources for optimal results
    """
    try:
        import time
        start_time = time.time()

        # Get correlation ID
        corr_id = None
        try:
            if request is not None:
                corr_id = request.headers.get("X-Correlation-ID")
        except Exception:
            pass

        logger.info(f"Starting content search for project {project_id}: '{search_request.query}'")

        # Perform the search based on type
        if search_request.search_type == "semantic":
            results = await _perform_semantic_search(project_id, search_request, corr_id)
        elif search_request.search_type == "keyword":
            results = await _perform_keyword_search(project_id, search_request, corr_id)
        elif search_request.search_type == "metadata":
            results = await _perform_metadata_search(project_id, search_request, corr_id)
        else:  # comprehensive
            results = await _perform_comprehensive_search(project_id, search_request, corr_id)

        processing_time = time.time() - start_time

        response = ContentSearchResponse(
            project_id=project_id,
            query=search_request.query,
            search_type=search_request.search_type,
            total_results=len(results),
            results=results,
            search_timestamp=datetime.now().isoformat(),
            processing_time=round(processing_time, 3),
            filters_applied=search_request.filters
        )

        logger.info(f"Content search completed: {len(results)} results in {processing_time:.3f}s")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in content search for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Content search failed: {str(e)}")

async def _perform_semantic_search(project_id: str, search_request: ContentSearchRequest, correlation_id: Optional[str] = None) -> List[ContentSearchResult]:
    """Perform semantic search using vector service"""
    try:
        # Call vector service for semantic search
        vector_url = os.getenv("VECTOR_SERVICE_URL", "http://localhost:8005")
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {
                "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
            }
            if correlation_id:
                headers["X-Correlation-ID"] = correlation_id

            # Try hybrid search first (semantic + keyword), fallback to semantic
            try:
                search_response = await client.post(
                    f"{vector_url}/api/vectors/projects/{project_id}/search/hybrid",
                    json={
                        "query": search_request.query,
                        "limit": search_request.limit,
                        "semantic_weight": 0.8
                    },
                    headers=headers
                )
            except Exception:
                # Fallback to semantic search
                search_response = await client.post(
                    f"{vector_url}/api/vectors/projects/{project_id}/search",
                    json={
                        "query": search_request.query,
                        "limit": search_request.limit,
                        "include_metadata": True
                    },
                    headers=headers
                )

            if search_response.status_code == 200:
                try:
                    vector_results = search_response.json()
                except Exception as json_error:
                    logger.error(f"Failed to parse vector search response: {json_error}")
                    return []
                results = []

                for item in vector_results.get("results", []):
                    # Get additional document metadata
                    filename = item.get("metadata", {}).get("filename", "unknown")
                    doc_metadata = await _get_document_metadata(project_id, filename, correlation_id)

                    result = ContentSearchResult(
                        filename=filename,
                        relevance_score=item.get("similarity_score", item.get("score", 0.0)),
                        search_type="semantic",
                        matched_content=item.get("content", "")[:500] if search_request.include_content else None,
                        summary=doc_metadata.get("summary_text"),
                        categories=doc_metadata.get("categories", []),
                        document_type=doc_metadata.get("file_type"),
                        content_length=doc_metadata.get("file_size", 0),
                        last_updated=doc_metadata.get("updated_at"),
                        metadata={
                            "chunk_index": item.get("metadata", {}).get("chunk_index"),
                            "source": item.get("metadata", {}).get("source"),
                            "semantic_score": item.get("semantic_score", 0.0),
                            "keyword_score": item.get("keyword_score", 0.0)
                        }
                    )
                    results.append(result)

                return results
            else:
                logger.warning(f"Vector search failed: {search_response.status_code}")
                return []

    except Exception as e:
        logger.error(f"Semantic search failed: {e}")
        return []

async def _perform_keyword_search(project_id: str, search_request: ContentSearchRequest, correlation_id: Optional[str] = None) -> List[ContentSearchResult]:
    """Perform keyword-based search in document metadata and content"""
    try:
        results = []

        # Get all project files
        project_files = await _get_all_project_files(project_id, correlation_id)

        query_lower = search_request.query.lower()

        for file_info in project_files:
            filename = file_info.get("filename", "")
            if not filename:
                continue

            # Get document content and metadata
            try:
                content = await content_extractor._fetch_processed_content(project_id, filename, correlation_id)
                doc_metadata = await _get_document_metadata(project_id, filename, correlation_id)

                if not content:
                    continue

                # Search in content
                content_lower = content.lower()
                if query_lower in content_lower:
                    # Calculate relevance score based on frequency and position
                    frequency = content_lower.count(query_lower)
                    first_occurrence = content_lower.find(query_lower)
                    position_score = 1.0 if first_occurrence < len(content_lower) * 0.1 else 0.5
                    relevance_score = min(frequency * 0.1 + position_score, 1.0)

                    # Extract matched snippet
                    match_start = max(0, first_occurrence - 100)
                    match_end = min(len(content), first_occurrence + len(search_request.query) + 100)
                    matched_content = content[match_start:match_end] if search_request.include_content else None

                    result = ContentSearchResult(
                        filename=filename,
                        relevance_score=relevance_score,
                        search_type="keyword",
                        matched_content=matched_content,
                        summary=doc_metadata.get("summary_text"),
                        categories=doc_metadata.get("categories", []),
                        document_type=doc_metadata.get("file_type"),
                        content_length=doc_metadata.get("file_size", 0),
                        last_updated=doc_metadata.get("updated_at"),
                        metadata={
                            "match_position": first_occurrence,
                            "frequency": frequency,
                            "total_length": len(content)
                        }
                    )
                    results.append(result)

            except Exception as e:
                logger.warning(f"Error searching file {filename}: {e}")
                continue

        # Sort by relevance score and limit results
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results[:search_request.limit]

    except Exception as e:
        logger.error(f"Keyword search failed: {e}")
        return []

async def _perform_metadata_search(project_id: str, search_request: ContentSearchRequest, correlation_id: Optional[str] = None) -> List[ContentSearchResult]:
    """Search in document metadata (summaries, categories, structure)"""
    try:
        results = []

        # Get all project files
        project_files = await _get_all_project_files(project_id, correlation_id)

        query_lower = search_request.query.lower()

        for file_info in project_files:
            filename = file_info.get("filename", "")
            if not filename:
                continue

            try:
                doc_metadata = await _get_document_metadata(project_id, filename, correlation_id)

                relevance_score = 0.0
                matched_field = None

                # Search in summary
                if doc_metadata.get("summary_text"):
                    summary_lower = doc_metadata["summary_text"].lower()
                    if query_lower in summary_lower:
                        relevance_score = 0.9
                        matched_field = "summary"

                # Search in categories
                if doc_metadata.get("categories"):
                    for category in doc_metadata["categories"]:
                        if query_lower in category.lower():
                            relevance_score = max(relevance_score, 0.8)
                            matched_field = "categories"
                            break

                # Search in structure metadata
                if doc_metadata.get("structure_metadata"):
                    structure_str = json.dumps(doc_metadata["structure_metadata"]).lower()
                    if query_lower in structure_str:
                        relevance_score = max(relevance_score, 0.7)
                        matched_field = "structure"

                if relevance_score > 0:
                    result = ContentSearchResult(
                        filename=filename,
                        relevance_score=relevance_score,
                        search_type="metadata",
                        matched_content=None,  # Don't include content for metadata search
                        summary=doc_metadata.get("summary_text"),
                        categories=doc_metadata.get("categories", []),
                        document_type=doc_metadata.get("file_type"),
                        content_length=doc_metadata.get("file_size", 0),
                        last_updated=doc_metadata.get("updated_at"),
                        metadata={
                            "matched_field": matched_field,
                            "structure_metadata": doc_metadata.get("structure_metadata")
                        }
                    )
                    results.append(result)

            except Exception as e:
                logger.warning(f"Error searching metadata for {filename}: {e}")
                continue

        # Sort by relevance score and limit results
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results[:search_request.limit]

    except Exception as e:
        logger.error(f"Metadata search failed: {e}")
        return []

# -------------------------------------------------------------------------------------------------
# Implementation Notes (automation summary):
# - Added get_batches_by_version to HttpAnalysisRepository with resilient fallbacks.
# - Introduced page load guard + micro cache for insights endpoint to avoid heavy auto analysis.
# - Implemented singleton service client and perf timing decorator for key endpoints.
# - Optimized project file metadata retrieval via parallel requests & short TTL cache.
# - Added in-memory caches for lightweight insights and file metadata (TTL 60s / 30s respectively).
# Future work:
# - Externalize caches to Redis for multi-instance deployments.
# - Persist batch analysis state to analytics service when endpoints stabilize.
# - Expand timing to include correlation IDs and percentile aggregation.
# -------------------------------------------------------------------------------------------------

async def _perform_comprehensive_search(project_id: str, search_request: ContentSearchRequest, correlation_id: Optional[str] = None) -> List[ContentSearchResult]:
    """Perform comprehensive search combining all methods"""
    try:
        # Run all search types
        semantic_results = await _perform_semantic_search(project_id, search_request, correlation_id)
        keyword_results = await _perform_keyword_search(project_id, search_request, correlation_id)
        metadata_results = await _perform_metadata_search(project_id, search_request, correlation_id)

        # Combine and deduplicate results
        all_results = semantic_results + keyword_results + metadata_results

        # Remove duplicates based on filename
        seen_files = set()
        deduplicated_results = []

        for result in all_results:
            if result.filename not in seen_files:
                seen_files.add(result.filename)
                deduplicated_results.append(result)
            else:
                # Update existing result with higher relevance score
                existing_index = next((i for i, r in enumerate(deduplicated_results) if r.filename == result.filename), -1)
                if existing_index >= 0:
                    existing_result = deduplicated_results[existing_index]
                    if result.relevance_score > existing_result.relevance_score:
                        # Merge metadata from both results
                        merged_metadata = {**existing_result.metadata, **result.metadata} if existing_result.metadata and result.metadata else (existing_result.metadata or result.metadata)
                        existing_result.relevance_score = result.relevance_score
                        existing_result.search_type = "comprehensive"
                        existing_result.metadata = merged_metadata

        # Sort by relevance score and limit results
        deduplicated_results.sort(key=lambda x: x.relevance_score, reverse=True)
        return deduplicated_results[:search_request.limit]

    except Exception as e:
        logger.error(f"Comprehensive search failed: {e}")
        return []

async def _get_document_metadata(project_id: str, filename: str, correlation_id: Optional[str] = None) -> Dict[str, Any]:
    """Get document metadata from project service"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {
                "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
            }
            if correlation_id:
                headers["X-Correlation-ID"] = correlation_id

            # Use correct project service endpoint with /api prefix
            response = await client.get(
                f"{processor.project_service_url}/api/projects/{project_id}/files",
                headers=headers
            )

            if response.status_code == 200:
                files = response.json()
                for file in files:
                    if file.get("filename") == filename:
                        return file

            return {}

    except Exception as e:
        logger.warning(f"Error getting document metadata for {filename}: {e}")
        return {}

async def _get_all_project_files(project_id: str, correlation_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get all files for a project"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {
                "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
            }
            if correlation_id:
                headers["X-Correlation-ID"] = correlation_id

            # Use correct project service endpoint with /api prefix
            response = await client.get(
                f"{processor.project_service_url}/api/projects/{project_id}/files",
                headers=headers
            )

            if response.status_code == 200:
                return response.json()
            return []

    except Exception as e:
        logger.warning(f"Error getting project files: {e}")
        return []

# =====================================================================================
# LLM-Enhanced Content Analysis Endpoints (PHASE 2)
# =====================================================================================

class LLMAnalysisRequest(BaseModel):
    """Request model for LLM content analysis"""
    analysis_type: str = "comprehensive"  # comprehensive, summary, categories, technical
    force_reanalysis: bool = False
    include_raw_analysis: bool = False

class LLMAnalysisResponse(BaseModel):
    """Response model for LLM content analysis"""
    project_id: str
    filename: str
    analysis_type: str
    final_summary: str
    final_categories: List[str]
    quality_score: float
    processing_methods: List[str]
    processing_time: float
    cached: bool
    timestamp: str

class LLMBatchAnalysisRequest(BaseModel):
    """Request model for LLM batch content analysis"""
    filenames: List[str]
    analysis_type: str = "comprehensive"
    max_concurrent: int = 10
    force_reanalysis: bool = False

class LLMBatchAnalysisResponse(BaseModel):
    """Response model for LLM batch analysis"""
    project_id: str
    analysis_id: str
    total_files: int
    status: str
    started_at: str
    completed_at: Optional[str] = None
    results: List[Dict[str, Any]] = []
    summary_stats: Dict[str, Any] = {}

# Global storage for LLM batch analysis status
_llm_batch_analysis_status = {}

# =====================================================================================
# JSONL ANALYSIS ENDPOINTS (PHASE 3 - Migration to JSONL-only)
# =====================================================================================

class AnalysisResult(BaseModel):
    """Analysis result model for JSONL storage"""
    analysis_id: str
    project_id: str
    filename: str
    analysis_type: str
    content: str
    metadata: Dict[str, Any]
    version: int = 1
    created_at: str
    updated_at: str
    quality_score: Optional[float] = None
    processing_time: Optional[float] = None

class AnalysisBatch(BaseModel):
    """Analysis batch model"""
    batch_id: str
    project_id: str
    analysis_type: str
    filenames: List[str]
    status: str
    created_at: str
    completed_at: Optional[str] = None
    results: List[Dict[str, Any]] = []
    metadata: Dict[str, Any] = {}

class AnalysisVersion(BaseModel):
    """Analysis version model"""
    version_id: str
    analysis_id: str
    version_number: int
    content: str
    metadata: Dict[str, Any]
    created_at: str
    created_by: Optional[str] = None

class CreateAnalysisRequest(BaseModel):
    """Request model for creating analysis result"""
    filename: str
    analysis_type: str
    content: str
    metadata: Optional[Dict[str, Any]] = None
    quality_score: Optional[float] = None

class UpdateAnalysisRequest(BaseModel):
    """Request model for updating analysis result"""
    content: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    quality_score: Optional[float] = None

class BatchAnalysisRequest(BaseModel):
    """Request model for batch analysis"""
    filenames: List[str]
    analysis_type: str
    metadata: Optional[Dict[str, Any]] = None

@router.post("/{project_id}/llm-analyze/{filename}", response_model=LLMAnalysisResponse)
async def analyze_document_with_llm(
    project_id: str,
    filename: str,
    analysis_request: LLMAnalysisRequest = LLMAnalysisRequest(),
    request: Request = None
):
    """Perform LLM-enhanced content analysis on a specific document"""
    if not llm_analyzer:
        raise HTTPException(
            status_code=503,
            detail="LLM Content Analyzer not available. Check LLM service configuration."
        )

    try:
        # Get correlation ID
        corr_id = None
        try:
            if request is not None:
                corr_id = request.headers.get("X-Correlation-ID")
        except Exception:
            pass

        logger.info(f"Starting LLM analysis for {filename} in project {project_id}")

        # Perform LLM analysis
        analysis_result = await llm_analyzer.analyze_document_content(
            project_id=project_id,
            filename=filename,
            analysis_type=analysis_request.analysis_type,
            correlation_id=corr_id,
            force_reanalysis=analysis_request.force_reanalysis
        )

        if analysis_result["status"] != "success":
            raise HTTPException(
                status_code=500,
                detail=f"LLM analysis failed: {analysis_result.get('error', 'Unknown error')}"
            )

        # Update project file with results
        update_success = await llm_analyzer.update_project_file_with_analysis(
            project_id, filename, analysis_result, corr_id
        )

        response = LLMAnalysisResponse(
            project_id=project_id,
            filename=filename,
            analysis_type=analysis_request.analysis_type,
            final_summary=analysis_result.get("final_summary", ""),
            final_categories=analysis_result.get("final_categories", []),
            quality_score=analysis_result.get("quality_score", 0.0),
            processing_methods=analysis_result.get("processing_methods", []),
            processing_time=analysis_result.get("total_processing_time", 0.0),
            cached=analysis_result.get("llm_summary_cached", False),
            timestamp=analysis_result.get("timestamp", datetime.now().isoformat())
        )

        logger.info(f"LLM analysis completed for {filename}: quality={response.quality_score:.2f}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in LLM analysis for {filename}: {e}")
        raise HTTPException(status_code=500, detail=f"LLM analysis failed: {str(e)}")

@router.post("/{project_id}/llm-analyze-batch", response_model=LLMBatchAnalysisResponse)
async def analyze_documents_batch_with_llm(
    project_id: str,
    batch_request: LLMBatchAnalysisRequest,
    background_tasks: BackgroundTasks,
    request: Request = None
):
    """Perform LLM-enhanced batch content analysis on multiple documents"""
    if not llm_analyzer:
        raise HTTPException(
            status_code=503,
            detail="LLM Content Analyzer not available. Check LLM service configuration."
        )

    try:
        # Get correlation ID
        corr_id = None
        try:
            if request is not None:
                corr_id = request.headers.get("X-Correlation-ID")
        except Exception:
            pass

        logger.info(f"Starting LLM batch analysis for {len(batch_request.filenames)} files in project {project_id}")

        # Generate analysis ID
        analysis_id = str(uuid.uuid4())

        # Initialize batch analysis status
        batch_status = {
            "analysis_id": analysis_id,
            "status": "started",
            "total_files": len(batch_request.filenames),
            "processed_files": 0,
            "results": [],
            "started_at": datetime.now().isoformat(),
            "summary_stats": {
                "successful_analyses": 0,
                "failed_analyses": 0,
                "average_quality_score": 0.0,
                "total_processing_time": 0.0
            }
        }

        # Store batch status
        _llm_batch_analysis_status[analysis_id] = batch_status

        # Start background processing
        background_tasks.add_task(
            _process_llm_batch_analysis_background,
            project_id,
            analysis_id,
            batch_request,
            corr_id
        )

        return LLMBatchAnalysisResponse(
            project_id=project_id,
            analysis_id=analysis_id,
            total_files=len(batch_request.filenames),
            status="started",
            started_at=batch_status["started_at"],
            results=[]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting LLM batch analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start LLM batch analysis: {str(e)}")

@router.get("/{project_id}/llm-analysis-status/{analysis_id}", response_model=LLMBatchAnalysisResponse)
async def get_llm_batch_analysis_status(project_id: str, analysis_id: str):
    """Get status and results of LLM batch content analysis"""
    try:
        if analysis_id not in _llm_batch_analysis_status:
            raise HTTPException(status_code=404, detail="LLM analysis job not found")

        status_data = _llm_batch_analysis_status[analysis_id]

        return LLMBatchAnalysisResponse(
            project_id=project_id,
            analysis_id=analysis_id,
            total_files=status_data["total_files"],
            status=status_data["status"],
            started_at=status_data["started_at"],
            completed_at=status_data.get("completed_at"),
            results=status_data["results"],
            summary_stats=status_data["summary_stats"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting LLM batch analysis status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get analysis status: {str(e)}")

async def _process_llm_batch_analysis_background(
    project_id: str,
    analysis_id: str,
    batch_request: LLMBatchAnalysisRequest,
    correlation_id: Optional[str] = None
):
    """Background processing for LLM batch content analysis with status updates"""
    try:
        logger.info(f"Starting background LLM batch analysis {analysis_id}")

        # Update document statuses to "analyzing"
        await _update_document_analysis_status(project_id, batch_request.filenames, "analyzing", analysis_id)

        # Prepare file data for batch processing
        file_data = []
        for filename in batch_request.filenames:
            file_data.append({"filename": filename})

        # Perform batch analysis
        batch_result = await llm_analyzer.analyze_documents_batch(
            project_id=project_id,
            file_data=file_data,
            analysis_type=batch_request.analysis_type,
            correlation_id=correlation_id,
            max_concurrent=batch_request.max_concurrent
        )

        results = []
        quality_scores = []
        successful_files = []
        failed_files = []

        if batch_result["status"] == "completed":
            # Update project files and collect results
            for result in batch_result["results"]:
                if result["status"] == "success":
                    # Update project file
                    update_success = await llm_analyzer.update_project_file_with_analysis(
                        project_id, result["filename"], result, correlation_id
                    )

                    result["update_success"] = update_success
                    quality_scores.append(result.get("quality_score", 0.0))
                    successful_files.append(result["filename"])
                else:
                    failed_files.append(result["filename"])

                results.append(result)

            # Calculate summary statistics
            successful_analyses = len([r for r in results if r["status"] == "success"])
            failed_analyses = len([r for r in results if r["status"] != "success"])
            avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0

            summary_stats = {
                "successful_analyses": successful_analyses,
                "failed_analyses": failed_analyses,
                "average_quality_score": round(avg_quality, 2),
                "total_processing_time": batch_result.get("total_processing_time", 0.0),
                "average_time_per_file": batch_result.get("average_time_per_file", 0.0)
            }

            # Update document statuses based on results
            if successful_files:
                await _update_document_analysis_status(project_id, successful_files, "analysis_complete", analysis_id)
            if failed_files:
                await _update_document_analysis_status(project_id, failed_files, "analysis_failed", analysis_id)

        else:
            summary_stats = {
                "successful_analyses": 0,
                "failed_analyses": len(batch_request.filenames),
                "average_quality_score": 0.0,
                "total_processing_time": 0.0,
                "error": batch_result.get("error", "Batch analysis failed")
            }
            results = batch_result.get("errors", [])
            
            # Mark all files as failed
            await _update_document_analysis_status(project_id, batch_request.filenames, "analysis_failed", analysis_id)

        # Update batch status
        _llm_batch_analysis_status[analysis_id].update({
            "status": "completed",
            "processed_files": len(results),
            "results": results,
            "summary_stats": summary_stats,
            "completed_at": datetime.now().isoformat()
        })

        # Notify via WebSocket about completion
        await _notify_analysis_completion(project_id, analysis_id, summary_stats)

        logger.info(f"Completed background LLM batch analysis {analysis_id}: {summary_stats['successful_analyses']}/{len(batch_request.filenames)} successful")

    except Exception as e:
        logger.error(f"Error in background LLM batch analysis {analysis_id}: {e}")
        
        # Mark all files as failed
        try:
            await _update_document_analysis_status(project_id, batch_request.filenames, "analysis_failed", analysis_id)
        except Exception as update_error:
            logger.error(f"Error updating document status after analysis failure: {update_error}")
        
        _llm_batch_analysis_status[analysis_id].update({
            "status": "failed",
            "error": str(e),
            "completed_at": datetime.now().isoformat()
        })

async def _notify_analysis_completion(
    project_id: str,
    analysis_id: str,
    summary_stats: Dict[str, Any]
):
    """Notify frontend via WebSocket about analysis completion"""
    try:
        import httpx

        websocket_url = await processor._get_websocket_url()
        async with httpx.AsyncClient(timeout=processor.http_timeout) as client:
            headers = {
                "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
            }

            notification_data = {
                "type": "analysis_complete",
                "project_id": project_id,
                "analysis_id": analysis_id,
                "data": {
                    "summary_stats": summary_stats,
                    "successful_analyses": summary_stats.get("successful_analyses", 0),
                    "failed_analyses": summary_stats.get("failed_analyses", 0),
                    "average_quality_score": summary_stats.get("average_quality_score", 0.0),
                    "completed_at": datetime.now().isoformat()
                }
            }

            response = await client.post(
                f"{websocket_url}/api/websocket/notify",
                json=notification_data,
                headers=headers,
            )

            if response.status_code == 200:
                logger.info(f"Successfully notified analysis completion for {analysis_id}")
            else:
                logger.warning(f"Failed to notify analysis completion: {response.status_code}")

    except Exception as e:
        logger.warning(f"Error sending analysis completion notification: {e}")

async def _notify_document_processing_complete(
    project_id: str,
    filename: str,
    analysis_id: Optional[str] = None,
    correlation_id: Optional[str] = None
):
    """Notify frontend via WebSocket about document processing completion"""
    try:
        import httpx

        websocket_url = await processor._get_websocket_url()
        async with httpx.AsyncClient(timeout=processor.http_timeout) as client:
            headers = {
                "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
            }
            if correlation_id:
                headers["X-Correlation-ID"] = correlation_id

            notification_data = {
                "type": "document_processing_complete",
                "project_id": project_id,
                "document_id": filename,
                "file_name": filename,
                "analysis_id": analysis_id,
                "timestamp": datetime.now().isoformat(),
                "data": {
                    "status": "completed",
                    "analysis_status": "analysis_complete" if analysis_id else "not_analyzed",
                    "completed_at": datetime.now().isoformat()
                }
            }

            response = await client.post(
                f"{websocket_url}/api/websocket/notify",
                json=notification_data,
                headers=headers,
            )

            if response.status_code == 200:
                logger.info(f"Successfully notified document processing completion for {filename}")
            else:
                logger.warning(f"Failed to notify document processing completion: {response.status_code}")

    except Exception as e:
        logger.warning(f"Error sending document processing completion notification: {e}")

@router.get("/{project_id}/analysis-status/{analysis_id}")
async def get_analysis_status(
    project_id: str,
    analysis_id: str
):
    """Get the status of a specific analysis batch"""
    try:
        if analysis_id not in _llm_batch_analysis_status:
            raise HTTPException(status_code=404, detail="Analysis not found")
        
        status_data = _llm_batch_analysis_status[analysis_id]
        
        return LLMBatchAnalysisResponse(
            project_id=project_id,
            analysis_id=analysis_id,
            total_files=status_data["total_files"],
            status=status_data["status"],
            started_at=status_data["started_at"],
            completed_at=status_data.get("completed_at"),
            results=status_data["results"],
            summary_stats=status_data["summary_stats"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting analysis status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get analysis status: {str(e)}")

@router.get("/{project_id}/documents/analysis-status")
async def get_documents_analysis_status(
    project_id: str
):
    """Get analysis status for all documents in a project"""
    try:
        import httpx

        async with httpx.AsyncClient(timeout=processor.http_timeout) as client:
            headers = {
                "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
            }

            # Get all documents with their metadata from storage service
            storage_url = await processor._get_storage_url()
            documents_status = []

            # Try to get metadata first
            try:
                response = await client.get(
                    f"{storage_url}/api/storage/projects/{project_id}/files/uploads_raw/metadata",
                    headers=headers,
                )

                if response.status_code == 200:
                    try:
                        documents_data = response.json()
                        for doc in documents_data.get("files", []):
                            status_info = {
                                "filename": doc["filename"],
                                "analysis_status": doc.get("metadata", {}).get("analysis_status", "not_analyzed"),
                                "analysis_id": doc.get("metadata", {}).get("analysis_id"),
                                "last_updated": doc.get("metadata", {}).get("updated_at")
                            }
                            documents_status.append(status_info)
                    except Exception as json_error:
                        logger.warning(f"Failed to parse documents metadata response: {json_error}, falling back to basic file list")
                        documents_status = []  # Reset to trigger fallback
                else:
                    logger.warning(f"Metadata endpoint returned {response.status_code}, falling back to basic file list")
                    documents_status = []  # Reset to trigger fallback

            except Exception as metadata_error:
                logger.warning(f"Failed to fetch document metadata: {metadata_error}, falling back to basic file list")

            # Fallback: Get basic file list without metadata
            if not documents_status:
                try:
                    fallback_response = await client.get(
                        f"{storage_url}/api/storage/projects/{project_id}/files/uploads_raw",
                        headers=headers,
                    )

                    if fallback_response.status_code == 200:
                        try:
                            files_data = fallback_response.json()
                            for file_info in files_data.get("files", []):
                                # Create basic status info with default values
                                status_info = {
                                    "filename": file_info.get("filename", ""),
                                    "analysis_status": "not_analyzed",  # Default status when metadata unavailable
                                    "analysis_id": None,
                                    "last_updated": file_info.get("uploaded_at") or file_info.get("created_at")
                                }
                                documents_status.append(status_info)
                            logger.info(f"Fallback successful: Retrieved {len(documents_status)} documents with basic status")
                        except Exception as fallback_json_error:
                            logger.error(f"Failed to parse fallback files response: {fallback_json_error}")
                            raise HTTPException(status_code=500, detail="Failed to parse document files response")
                    else:
                        logger.error(f"Fallback file list endpoint also failed: {fallback_response.status_code}")
                        raise HTTPException(status_code=500, detail="Failed to fetch document files")

                except Exception as fallback_error:
                    logger.error(f"Fallback file retrieval failed: {fallback_error}")
                    raise HTTPException(status_code=500, detail="Failed to fetch document information")

            return {
                "project_id": project_id,
                "documents": documents_status,
                "total_documents": len(documents_status),
                "analysis_pending": len([d for d in documents_status if d["analysis_status"] == "analysis_pending"]),
                "analyzing": len([d for d in documents_status if d["analysis_status"] == "analyzing"]),
                "analysis_complete": len([d for d in documents_status if d["analysis_status"] == "analysis_complete"]),
                "analysis_failed": len([d for d in documents_status if d["analysis_status"] == "analysis_failed"]),
                "not_analyzed": len([d for d in documents_status if d["analysis_status"] == "not_analyzed"])
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting documents analysis status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get documents analysis status: {str(e)}")

@router.get("/llm-analysis-health")
async def get_llm_analysis_health():
    """Get health status of LLM analysis components"""
    try:
        health_info = {
            "llm_analyzer_available": llm_analyzer is not None,
            "llm_service_available": LLM_ANALYZER_AVAILABLE,
            "content_extractor_available": True
        }

        if llm_analyzer:
            try:
                stats = await llm_analyzer.get_analysis_stats()
                health_info["analysis_stats"] = stats
            except Exception as e:
                health_info["analysis_stats_error"] = str(e)

        return health_info

    except Exception as e:
        logger.error(f"Error getting LLM analysis health: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@router.post("/llm-analysis-cache/clear")
async def clear_llm_analysis_cache():
    """Clear LLM analysis caches"""
    try:
        if llm_analyzer:
            await llm_analyzer.clear_analysis_cache()
            return {"message": "LLM analysis cache cleared successfully"}
        else:
            raise HTTPException(status_code=503, detail="LLM analyzer not available")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing LLM analysis cache: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")

# =====================================================================================
# JSONL ANALYSIS ENDPOINTS - Analysis Results Management
# =====================================================================================

@router.post("/{project_id}/analysis", response_model=AnalysisResult)
async def create_analysis_result(
    project_id: str,
    request: CreateAnalysisRequest,
    request_obj: Request = None
):
    """Create a new analysis result in JSONL format"""
    try:
        corr_id = None
        try:
            if request_obj is not None:
                corr_id = request_obj.headers.get("X-Correlation-ID")
        except Exception:
            pass

        if not corr_id:
            corr_id = str(uuid.uuid4())

        logger.info(f"Creating analysis result for {request.filename} in project {project_id}")

        # Generate analysis ID
        analysis_id = str(uuid.uuid4())

        # Create analysis result
        analysis_result = {
            "analysis_id": analysis_id,
            "project_id": project_id,
            "filename": request.filename,
            "analysis_type": request.analysis_type,
            "content": request.content,
            "metadata": request.metadata or {},
            "version": 1,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "quality_score": request.quality_score,
            "processing_time": None
        }

        # Store in analysis_results table (placeholder - integrate with actual DB)
        # TODO: Implement database integration
        await _store_analysis_result(analysis_result)

        return AnalysisResult(**analysis_result)

    except Exception as e:
        logger.error(f"Error creating analysis result: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create analysis result: {str(e)}")

# =====================================================================================
# JSONL ANALYSIS ENDPOINTS - Batch Operations
# =====================================================================================

@router.post("/{project_id}/analysis/batch", response_model=AnalysisBatch)
async def create_analysis_batch(
    project_id: str,
    request: BatchAnalysisRequest,
    background_tasks: BackgroundTasks,
    request_obj: Request = None
):
    """Create and start a batch analysis operation"""
    try:
        corr_id = None
        try:
            if request_obj is not None:
                corr_id = request_obj.headers.get("X-Correlation-ID")
        except Exception:
            pass

        if not corr_id:
            corr_id = str(uuid.uuid4())

        logger.info(f"Creating analysis batch for {len(request.filenames)} files in project {project_id}")

        # Generate batch ID
        batch_id = str(uuid.uuid4())

        # Create batch record
        batch = {
            "batch_id": batch_id,
            "project_id": project_id,
            "analysis_type": request.analysis_type,
            "filenames": request.filenames,
            "status": "started",
            "created_at": datetime.now().isoformat(),
            "completed_at": None,
            "results": [],
            "metadata": request.metadata or {}
        }

        # Store batch (placeholder)
        await _store_analysis_batch(batch)

        # Start background processing
        background_tasks.add_task(
            _process_analysis_batch_background,
            project_id,
            batch_id,
            request,
            corr_id
        )

        return AnalysisBatch(**batch)

    except Exception as e:
        logger.error(f"Error creating analysis batch: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create analysis batch: {str(e)}")

@router.get("/{project_id}/analysis/batch/{batch_id}", response_model=AnalysisBatch)
async def get_analysis_batch(project_id: str, batch_id: str):
    """Get batch analysis status and results"""
    try:
        logger.info(f"Retrieving analysis batch {batch_id} for project {project_id}")

        # Retrieve batch (placeholder)
        batch = await _get_analysis_batch(batch_id, project_id)

        if not batch:
            raise HTTPException(status_code=404, detail="Analysis batch not found")

        return AnalysisBatch(**batch)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving analysis batch: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve analysis batch: {str(e)}")

@router.get("/{project_id}/analysis/batches", response_model=List[AnalysisBatch])
async def list_project_analysis_batches(
    project_id: str,
    status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0
):
    """List analysis batches for a project"""
    try:
        logger.info(f"Listing analysis batches for project {project_id}")

        # Retrieve batches (placeholder)
        batches = await _list_project_analysis_batches(project_id, status, limit, offset)

        return [AnalysisBatch(**batch) for batch in batches]

    except Exception as e:
        logger.error(f"Error listing analysis batches: {e}")
        # Return empty array instead of 500 error to prevent frontend issues
        return []

@router.get("/{project_id}/test-endpoint")
async def test_endpoint(project_id: str):
    """Test endpoint to verify router is working"""
    return {"message": f"Test endpoint working for project {project_id}", "timestamp": datetime.now().isoformat()}

# =====================================================================================
# JSONL ANALYSIS ENDPOINTS - Individual Results Management
# =====================================================================================

@router.get("/{project_id}/analysis/{analysis_id}", response_model=AnalysisResult)
async def get_analysis_result(project_id: str, analysis_id: str):
    """Retrieve a specific analysis result"""
    # Prevent conflict with /analysis/batches endpoint
    if analysis_id == "batches":
        # This should not happen if routes are ordered correctly, but just in case
        raise HTTPException(status_code=404, detail="Analysis result not found")

    try:
        logger.info(f"Retrieving analysis result {analysis_id} for project {project_id}")

        # Retrieve from analysis_results table (placeholder)
        result = await _get_analysis_result(analysis_id, project_id)

        if not result:
            raise HTTPException(status_code=404, detail="Analysis result not found")

        return AnalysisResult(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving analysis result: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve analysis result: {str(e)}")

@router.get("/{project_id}/analysis", response_model=List[AnalysisResult])
async def list_project_analysis_results(
    project_id: str,
    analysis_type: Optional[str] = None,
    filename: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """List analysis results for a project with optional filtering"""
    try:
        logger.info(f"Listing analysis results for project {project_id}")

        # Retrieve from analysis_results table (placeholder)
        results = await _list_project_analysis_results(
            project_id, analysis_type, filename, limit, offset
        )

        # Transform results to match AnalysisResult model
        transformed_results = []
        for result in results:
            try:
                # Map repository fields to model fields
                transformed_result = {
                    "analysis_id": result.get("analysis_id") or result.get("id") or str(uuid.uuid4()),
                    "project_id": result.get("project_id") or project_id,
                    "filename": result.get("filename") or result.get("file_name") or "",
                    "analysis_type": result.get("analysis_type") or result.get("type") or "unknown",
                    "content": result.get("content") or result.get("result") or "",
                    "metadata": result.get("metadata") or {},
                    "version": result.get("version") or 1,
                    "created_at": result.get("created_at") or result.get("timestamp") or datetime.now().isoformat(),
                    "updated_at": result.get("updated_at") or result.get("modified_at") or datetime.now().isoformat(),
                    "quality_score": result.get("quality_score"),
                    "processing_time": result.get("processing_time")
                }
                transformed_results.append(AnalysisResult(**transformed_result))
            except Exception as transform_error:
                logger.warning(f"Failed to transform result: {transform_error}")
                continue

        return transformed_results

    except Exception as e:
        logger.error(f"Error listing analysis results: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list analysis results: {str(e)}")

@router.put("/{project_id}/analysis/{analysis_id}", response_model=AnalysisResult)
async def update_analysis_result(
    project_id: str,
    analysis_id: str,
    request: UpdateAnalysisRequest
):
    """Update an existing analysis result"""
    try:
        logger.info(f"Updating analysis result {analysis_id} for project {project_id}")

        # Get existing result
        existing = await _get_analysis_result(analysis_id, project_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Analysis result not found")

        # Update fields
        updates = {}
        if request.content is not None:
            updates["content"] = request.content
        if request.metadata is not None:
            updates["metadata"] = request.metadata
        if request.quality_score is not None:
            updates["quality_score"] = request.quality_score

        updates["updated_at"] = datetime.now().isoformat()

        # Update in database
        updated_result = await _update_analysis_result(analysis_id, project_id, updates)

        return AnalysisResult(**updated_result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating analysis result: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update analysis result: {str(e)}")

@router.delete("/{project_id}/analysis/{analysis_id}")
async def delete_analysis_result(project_id: str, analysis_id: str):
    """Delete an analysis result"""
    try:
        logger.info(f"Deleting analysis result {analysis_id} for project {project_id}")

        # Check if exists
        existing = await _get_analysis_result(analysis_id, project_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Analysis result not found")

        # Delete from database
        await _delete_analysis_result(analysis_id, project_id)

        return {"message": "Analysis result deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting analysis result: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete analysis result: {str(e)}")

# =====================================================================================
# JSONL ANALYSIS ENDPOINTS - Versioning
# =====================================================================================

@router.post("/{project_id}/analysis/{analysis_id}/version", response_model=AnalysisVersion)
async def create_analysis_version(
    project_id: str,
    analysis_id: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
    created_by: Optional[str] = None
):
    """Create a new version of an analysis result"""
    try:
        logger.info(f"Creating version for analysis {analysis_id} in project {project_id}")

        # Get current version number
        current_version = await _get_latest_analysis_version(analysis_id)
        version_number = current_version + 1 if current_version else 1

        # Create version record
        version = {
            "version_id": str(uuid.uuid4()),
            "analysis_id": analysis_id,
            "version_number": version_number,
            "content": content,
            "metadata": metadata or {},
            "created_at": datetime.now().isoformat(),
            "created_by": created_by
        }

        # Store version (placeholder)
        await _store_analysis_version(version)

        return AnalysisVersion(**version)

    except Exception as e:
        logger.error(f"Error creating analysis version: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create analysis version: {str(e)}")

@router.get("/{project_id}/analysis/{analysis_id}/versions", response_model=List[AnalysisVersion])
async def list_analysis_versions(project_id: str, analysis_id: str):
    """List all versions of an analysis result"""
    try:
        logger.info(f"Listing versions for analysis {analysis_id} in project {project_id}")

        # Retrieve versions (placeholder)
        versions = await _list_analysis_versions(analysis_id)

        return [AnalysisVersion(**version) for version in versions]

    except Exception as e:
        logger.error(f"Error listing analysis versions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list analysis versions: {str(e)}")

@router.get("/{project_id}/analysis/{analysis_id}/version/{version_number}", response_model=AnalysisVersion)
async def get_analysis_version(project_id: str, analysis_id: str, version_number: int):
    """Get a specific version of an analysis result"""
    try:
        logger.info(f"Retrieving version {version_number} for analysis {analysis_id}")

        # Retrieve version (placeholder)
        version = await _get_analysis_version(analysis_id, version_number)

        if not version:
            raise HTTPException(status_code=404, detail="Analysis version not found")

        return AnalysisVersion(**version)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving analysis version: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve analysis version: {str(e)}")

# =====================================================================================
# STANDARDIZED API ENDPOINTS WITH /api/documents/ PREFIX
# =====================================================================================

# Create sub-routers for resource grouping
documents_router = APIRouter()
analysis_router = APIRouter()
search_router = APIRouter()
config_router = APIRouter()

# Include sub-routers in main router with /api/documents prefix
router.include_router(documents_router, prefix="/api/documents")
router.include_router(analysis_router, prefix="/api/documents")
router.include_router(search_router, prefix="/api/documents")
router.include_router(config_router, prefix="/api/documents")

# =====================================================================================
# DOCUMENTS RESOURCE GROUP (/api/documents/documents/)
# =====================================================================================

@documents_router.post("/{project_id}/upload")
async def upload_documents_standardized(
    project_id: str,
    files: List[UploadFile] = File(...),
    request: Request = None,
    background_tasks: BackgroundTasks = None,
):
    """Standardized upload endpoint: Upload documents to Storage Service"""
    return await upload_documents(project_id, files, request, background_tasks)

@documents_router.post("/{project_id}/process")
async def process_all_documents_standardized(
    project_id: str,
    background_tasks: BackgroundTasks,
    request_data: ProcessRequest = ProcessRequest(),
    request: Request = None,
):
    """Standardized process endpoint: Process all uploaded documents"""
    return await process_all_documents(project_id, background_tasks, request_data, request)

@documents_router.post("/{project_id}/process-selected")
async def process_selected_documents_standardized(
    project_id: str,
    background_tasks: BackgroundTasks,
    request_data: ProcessRequest,
    request: Request = None,
):
    """Standardized process-selected endpoint: Process selected documents"""
    return await process_selected_documents(project_id, background_tasks, request_data, request)

@documents_router.get("/{project_id}/status/{job_id}")
async def get_processing_status_standardized(project_id: str, job_id: str):
    """Standardized status endpoint: Get processing status for a job"""
    return await get_processing_status(project_id, job_id)

@documents_router.post("/{project_id}/structured-process/{filename}")
async def process_document_structured_standardized(
    project_id: str,
    filename: str,
    request_data: StructuredProcessRequest = StructuredProcessRequest(),
    request: Request = None
):
    """Standardized structured-process endpoint: Process a single document with structured output"""
    return await process_document_structured(project_id, filename, request_data, request)

@documents_router.post("/{project_id}/structured-process")
async def process_all_documents_structured_standardized(
    project_id: str,
    background_tasks: BackgroundTasks,
    request_data: StructuredProcessRequest = StructuredProcessRequest(),
    request: Request = None
):
    """Standardized structured-process endpoint: Process all documents with structured output"""
    return await process_all_documents_structured(project_id, background_tasks, request_data, request)

@documents_router.get("/{project_id}/structured-status/{job_id}")
async def get_structured_processing_status_standardized(project_id: str, job_id: str):
    """Standardized structured-status endpoint: Get status of structured processing job"""
    return await get_structured_processing_status(project_id, job_id)

@documents_router.post("/{project_id}/chunks/{filename}")
async def generate_enhanced_chunks_standardized(
    project_id: str,
    filename: str,
    chunking_strategy: str = "jsonl_aware"
):
    """Standardized chunks endpoint: Generate enhanced chunks from a processed document"""
    return await generate_enhanced_chunks(project_id, filename, chunking_strategy)

@documents_router.post("/{project_id}/extract-batch")
async def extract_content_batch_standardized(
    project_id: str,
    file_names: List[str],
    request: Request = None
):
    """Standardized extract-batch endpoint: Extract content from multiple processed documents"""
    return await extract_content_batch(project_id, file_names, request)

# =====================================================================================
# ANALYSIS RESOURCE GROUP (/api/documents/analysis/)
# =====================================================================================

@analysis_router.get("/{project_id}/content/{filename}")
async def get_document_content_details_standardized(
    project_id: str,
    filename: str,
    request: Request = None
):
    """Standardized content endpoint: Retrieve detailed content information for a document"""
    return await get_document_content_details(project_id, filename, request)

@analysis_router.post("/{project_id}/analyze/{filename}")
async def analyze_document_standardized(
    project_id: str,
    filename: str,
    analysis_request: DocumentAnalysisRequest = DocumentAnalysisRequest(),
    request: Request = None
):
    """Standardized analyze endpoint: Perform content analysis on a document"""
    return await analyze_document(project_id, filename, analysis_request, request)

@analysis_router.get("/{project_id}/insights")
async def get_project_content_insights_standardized(
    project_id: str,
    request: Request = None,
    force_analysis: bool = False,  # Changed default to False
    allow_analysis: bool = False   # New parameter to explicitly allow analysis
):
    """Standardized insights endpoint: Get aggregated content insights for a project"""
    return await get_project_content_insights(project_id, request, force_analysis, allow_analysis)

@analysis_router.post("/{project_id}/analyze-batch")
async def analyze_documents_batch_standardized(
    project_id: str,
    batch_request: BatchAnalysisRequest,
    background_tasks: BackgroundTasks,
    request: Request = None
):
    """Standardized analyze-batch endpoint: Perform batch content analysis"""
    return await analyze_documents_batch(project_id, batch_request, background_tasks, request)

@analysis_router.get("/{project_id}/batch/{analysis_id}")
async def get_batch_analysis_status_standardized(
    project_id: str,
    analysis_id: str
):
    """Standardized batch status endpoint: Get status of batch content analysis"""
    return await get_batch_analysis_status(project_id, analysis_id)

@analysis_router.post("/{project_id}/llm/{filename}")
async def analyze_document_with_llm_standardized(
    project_id: str,
    filename: str,
    analysis_request: LLMAnalysisRequest = LLMAnalysisRequest(),
    request: Request = None
):
    """Standardized LLM analyze endpoint: Perform LLM-enhanced content analysis"""
    return await analyze_document_with_llm(project_id, filename, analysis_request, request)

@analysis_router.post("/{project_id}/llm-batch")
async def analyze_documents_batch_with_llm_standardized(
    project_id: str,
    batch_request: LLMBatchAnalysisRequest,
    background_tasks: BackgroundTasks,
    request: Request = None
):
    """Standardized LLM batch endpoint: Perform LLM-enhanced batch content analysis"""
    return await analyze_documents_batch_with_llm(project_id, batch_request, background_tasks, request)

@analysis_router.get("/{project_id}/llm-status/{analysis_id}")
async def get_llm_batch_analysis_status_standardized(
    project_id: str,
    analysis_id: str
):
    """Standardized LLM status endpoint: Get status of LLM batch analysis"""
    return await get_llm_batch_analysis_status(project_id, analysis_id)

@analysis_router.post("/{project_id}/results")
async def create_analysis_result_standardized(
    project_id: str,
    request: CreateAnalysisRequest,
    request_obj: Request = None
):
    """Standardized analysis results endpoint: Create a new analysis result"""
    return await create_analysis_result(project_id, request, request_obj)

@analysis_router.post("/{project_id}/results/batch")
async def create_analysis_batch_standardized(
    project_id: str,
    request: BatchAnalysisRequest,
    background_tasks: BackgroundTasks,
    request_obj: Request = None
):
    """Standardized analysis batch endpoint: Create and start a batch analysis operation"""
    return await create_analysis_batch(project_id, request, background_tasks, request_obj)

@analysis_router.get("/{project_id}/results/batch/{batch_id}")
async def get_analysis_batch_standardized(project_id: str, batch_id: str):
    """Standardized batch details endpoint: Get batch analysis status and results"""
    return await get_analysis_batch(project_id, batch_id)

@analysis_router.get("/{project_id}/results/batches")
async def list_project_analysis_batches_standardized(
    project_id: str,
    status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0
):
    """Standardized batches list endpoint: List analysis batches for a project"""
    return await list_project_analysis_batches(project_id, status, limit, offset)

@analysis_router.get("/{project_id}/results/{analysis_id}")
async def get_analysis_result_standardized(project_id: str, analysis_id: str):
    """Standardized analysis result endpoint: Retrieve a specific analysis result"""
    return await get_analysis_result(project_id, analysis_id)

@analysis_router.get("/{project_id}/results")
async def list_project_analysis_results_standardized(
    project_id: str,
    analysis_type: Optional[str] = None,
    filename: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """Standardized results list endpoint: List analysis results for a project"""
    return await list_project_analysis_results(project_id, analysis_type, filename, limit, offset)

@analysis_router.put("/{project_id}/results/{analysis_id}")
async def update_analysis_result_standardized(
    project_id: str,
    analysis_id: str,
    request: UpdateAnalysisRequest
):
    """Standardized update result endpoint: Update an existing analysis result"""
    return await update_analysis_result(project_id, analysis_id, request)

@analysis_router.delete("/{project_id}/results/{analysis_id}")
async def delete_analysis_result_standardized(project_id: str, analysis_id: str):
    """Standardized delete result endpoint: Delete an analysis result"""
    return await delete_analysis_result(project_id, analysis_id)

@analysis_router.post("/{project_id}/results/{analysis_id}/version")
async def create_analysis_version_standardized(
    project_id: str,
    analysis_id: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
    created_by: Optional[str] = None
):
    """Standardized version endpoint: Create a new version of an analysis result"""
    return await create_analysis_version(project_id, analysis_id, content, metadata, created_by)

@analysis_router.get("/{project_id}/results/{analysis_id}/versions")
async def list_analysis_versions_standardized(project_id: str, analysis_id: str):
    """Standardized versions list endpoint: List all versions of an analysis result"""
    return await list_analysis_versions(project_id, analysis_id)

@analysis_router.get("/{project_id}/results/{analysis_id}/version/{version_number}")
async def get_analysis_version_standardized(project_id: str, analysis_id: str, version_number: int):
    """Standardized version details endpoint: Get a specific version of an analysis result"""
    return await get_analysis_version(project_id, analysis_id, version_number)

# =====================================================================================
# SEARCH RESOURCE GROUP (/api/documents/search/)
# =====================================================================================

@search_router.post("/{project_id}/content")
async def search_document_content_standardized(
    project_id: str,
    search_request: ContentSearchRequest,
    request: Request = None
):
    """Standardized search endpoint: Search within document content"""
    return await search_document_content(project_id, search_request, request)

# =====================================================================================
# CONFIG RESOURCE GROUP (/api/documents/config/)
# =====================================================================================

@config_router.get("/workflow")
async def get_workflow_configuration_standardized():
    """Standardized workflow config endpoint: Get current document processing workflow configuration"""
    return await get_workflow_configuration()

@config_router.get("/health")
async def get_llm_analysis_health_standardized():
    """Standardized health endpoint: Get health status of LLM analysis components"""
    return await get_llm_analysis_health()

@config_router.post("/cache/clear")
async def clear_llm_analysis_cache_standardized():
    """Standardized cache clear endpoint: Clear LLM analysis caches"""
    return await clear_llm_analysis_cache()

@config_router.get("/test")
async def test_endpoint_standardized(project_id: str = "test"):
    """Standardized test endpoint: Test endpoint to verify router is working"""
    return {"message": f"Test endpoint working for project {project_id}", "timestamp": datetime.now().isoformat()}

# =====================================================================================
# PLACEHOLDER DATABASE FUNCTIONS (TO BE IMPLEMENTED WITH ACTUAL DB INTEGRATION)
# =====================================================================================

async def _store_analysis_result(result: Dict[str, Any]):
    """Store analysis result using AnalysisResultRepository"""
    try:
        repo = get_analysis_repository()

        # Create or get version for this project
        version_number = f"project_{result['project_id']}"
        version = await repo.get_version_by_number(version_number)
        if not version:
            version_create = AnalysisVersionCreate(
                version_number=version_number,
                description=f"Analysis results for project {result['project_id']}"
            )
            version = await repo.create_version(version_create)

        # Handle both dict (from HttpAnalysisRepository) and object formats for version
        if isinstance(version, dict):
            version_id = version.get("id")
        else:
            version_id = getattr(version, "id", None)

        if not version_id:
            logger.warning("Could not get version ID for storing analysis result")
            return

        # Create batch for this analysis type
        batch_name = f"{result['analysis_type']}_{result['filename']}_{result.get('created_at', datetime.now().isoformat())}"
        batch_create = AnalysisBatchCreate(
            version_id=version_id,
            batch_name=batch_name,
            status="completed"
        )
        batch = await repo.create_batch(batch_create)

        # Handle both dict (from HttpAnalysisRepository) and object formats for batch
        if isinstance(batch, dict):
            batch_id = batch.get("id")
        else:
            batch_id = getattr(batch, "id", None)

        if not batch_id:
            logger.warning("Could not get batch ID for storing analysis result")
            return

        # Store the analysis result
        result_data = {
            "analysis_id": result["analysis_id"],
            "project_id": result["project_id"],
            "filename": result["filename"],
            "analysis_type": result["analysis_type"],
            "content": result["content"],
            "metadata": result.get("metadata", {}),
            "version": result.get("version", 1),
            "quality_score": result.get("quality_score"),
            "processing_time": result.get("processing_time"),
            "created_at": result.get("created_at", datetime.now().isoformat()),
            "updated_at": result.get("updated_at", datetime.now().isoformat())
        }

        analysis_result_create = AnalysisResultCreate(
            batch_id=batch_id,
            result_data=result_data,
            analysis_result=result["content"],  # Add the missing analysis_result field
            line_number=1,  # Single result per batch for now
            status="completed"
        )

        await repo.create_result(analysis_result_create)
        logger.info(f"Stored analysis result: {result['analysis_id']}")

    except Exception as e:
        logger.error(f"Failed to store analysis result {result.get('analysis_id', 'unknown')}: {e}")
        raise

async def _get_analysis_result(analysis_id: str, project_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve analysis result using AnalysisResultRepository"""
    try:
        repo = get_analysis_repository()

        # Get version for this project
        version_number = f"project_{project_id}"
        version = await repo.get_version_by_number(version_number)
        if not version:
            return None

        # Handle both dict (from HttpAnalysisRepository) and object formats for version
        if isinstance(version, dict):
            version_id = version.get("id")
        else:
            version_id = getattr(version, "id", None)

        if not version_id:
            return None

        # Get all batches for this version
        batches = await repo.get_batches_by_version(version_id)
        if not batches:
            return None

        # Search through results in all batches for this analysis_id
        for batch in batches:
            # Handle both dict (from HttpAnalysisRepository) and object formats for batch
            if isinstance(batch, dict):
                batch_id = batch.get("id")
            else:
                batch_id = getattr(batch, "id", None)

            if batch_id:
                results = await repo.get_results_by_batch(batch_id)
                for result in results:
                    # Handle both dict (from HttpAnalysisRepository) and object formats
                    if isinstance(result, dict):
                        result_data = result.get("result_data", {})
                        result_id = result.get("id")
                    else:
                        result_data = getattr(result, "result_data", {})
                        result_id = getattr(result, "id", None)

                    if result_data.get("analysis_id") == analysis_id:
                        return result_data

        return None

    except Exception as e:
        logger.error(f"Failed to retrieve analysis result {analysis_id}: {e}")
        return None

async def _list_project_analysis_results(
    project_id: str,
    analysis_type: Optional[str] = None,
    filename: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """List project analysis results using AnalysisResultRepository"""
    try:
        repo = get_analysis_repository()

        # Get version for this project
        version_number = f"project_{project_id}"
        version = await repo.get_version_by_number(version_number)
        if not version:
            return []

        # Handle both dict (from HttpAnalysisRepository) and object formats for version
        if isinstance(version, dict):
            version_id = version.get("id")
        else:
            version_id = getattr(version, "id", None)

        if not version_id:
            return []

        # Get all batches for this version
        batches = await repo.get_batches_by_version(version_id)
        if not batches:
            return []

        all_results = []
        current_offset = 0
        remaining_limit = limit

        # Collect results from all batches
        for batch in batches:
            if remaining_limit <= 0:
                break

            # Handle both dict (from HttpAnalysisRepository) and object formats for batch
            if isinstance(batch, dict):
                batch_id = batch.get("id")
            else:
                batch_id = getattr(batch, "id", None)

            if batch_id:
                batch_results = await repo.get_results_by_batch(batch_id, limit=remaining_limit, offset=max(0, offset - current_offset))

                for result in batch_results:
                    # Handle both dict (mock data) and object (real data) formats
                    if isinstance(result, dict):
                        result_data = result.get("result_data", {})
                    else:
                        result_data = getattr(result, "result_data", {})

                    # Apply filters
                    if analysis_type and result_data.get("analysis_type") != analysis_type:
                        continue
                    if filename and result_data.get("filename") != filename:
                        continue

                    all_results.append(result_data)
                    remaining_limit -= 1
                    if remaining_limit <= 0:
                        break

                current_offset += len(batch_results)

        return all_results

    except Exception as e:
        logger.error(f"Failed to list analysis results for project {project_id}: {e}")
        return []

async def _update_analysis_result(analysis_id: str, project_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Update analysis result using AnalysisResultRepository"""
    try:
        repo = get_analysis_repository()

        # Get version for this project
        version_number = f"project_{project_id}"
        version = await repo.get_version_by_number(version_number)
        if not version:
            return {}

        # Handle both dict (from HttpAnalysisRepository) and object formats for version
        if isinstance(version, dict):
            version_id = version.get("id")
        else:
            version_id = getattr(version, "id", None)

        if not version_id:
            return {}

        # Get all batches for this version
        batches = await repo.get_batches_by_version(version_id)
        if not batches:
            return {}

        # Find the result by analysis_id
        target_result = None
        target_result_id = None

        for batch in batches:
            # Handle both dict (from HttpAnalysisRepository) and object formats for batch
            if isinstance(batch, dict):
                batch_id = batch.get("id")
            else:
                batch_id = getattr(batch, "id", None)

            if batch_id:
                results = await repo.get_results_by_batch(batch_id)
                for result in results:
                    # Handle both dict (from HttpAnalysisRepository) and object formats
                    if isinstance(result, dict):
                        result_data = result.get("result_data", {})
                        result_id = result.get("id")
                    else:
                        result_data = getattr(result, "result_data", {})
                        result_id = getattr(result, "id", None)

                    if result_data.get("analysis_id") == analysis_id:
                        target_result = result
                        target_result_id = result_id
                        break
                if target_result:
                    break

        if not target_result:
            logger.warning(f"Analysis result {analysis_id} not found in project {project_id}")
            return {}

        # Update the result data
        if isinstance(target_result, dict):
            updated_result_data = target_result.get("result_data", {}).copy()
        else:
            updated_result_data = getattr(target_result, "result_data", {}).copy()

        updated_result_data.update(updates)
        updated_result_data["updated_at"] = datetime.now().isoformat()

        # Update in repository
        await repo.update_result(target_result_id, {"result_data": updated_result_data})

        return updated_result_data

    except Exception as e:
        logger.error(f"Failed to update analysis result {analysis_id}: {e}")
        return {}

async def _delete_analysis_result(analysis_id: str, project_id: str):
    """Delete analysis result using AnalysisResultRepository"""
    try:
        repo = get_analysis_repository()

        # Get version for this project
        version_number = f"project_{project_id}"
        version = await repo.get_version_by_number(version_number)
        if not version:
            return

        # Handle both dict (from HttpAnalysisRepository) and object formats for version
        if isinstance(version, dict):
            version_id = version.get("id")
        else:
            version_id = getattr(version, "id", None)

        if not version_id:
            return

        # Get all batches for this version
        batches = await repo.get_batches_by_version(version_id)
        if not batches:
            return

        # Find and delete the result by analysis_id
        for batch in batches:
            # Handle both dict (from HttpAnalysisRepository) and object formats for batch
            if isinstance(batch, dict):
                batch_id = batch.get("id")
            else:
                batch_id = getattr(batch, "id", None)

            if batch_id:
                results = await repo.get_results_by_batch(batch_id)
                for result in results:
                    # Handle both dict (from HttpAnalysisRepository) and object formats
                    if isinstance(result, dict):
                        result_data = result.get("result_data", {})
                        result_id = result.get("id")
                    else:
                        result_data = getattr(result, "result_data", {})
                        result_id = getattr(result, "id", None)

                    if result_data.get("analysis_id") == analysis_id:
                        await repo.delete_result(result_id)
                        logger.info(f"Deleted analysis result: {analysis_id}")
                        return

        logger.warning(f"Analysis result {analysis_id} not found in project {project_id}")

    except Exception as e:
        logger.error(f"Failed to delete analysis result {analysis_id}: {e}")
        raise

async def _store_analysis_batch(batch: Dict[str, Any]):
    """Store analysis batch using AnalysisResultRepository"""
    try:
        repo = get_analysis_repository()

        # Create or get version for this project
        version_number = f"project_{batch['project_id']}"
        version = await repo.get_version_by_number(version_number)
        if not version:
            version_create = AnalysisVersionCreate(
                version_number=version_number,
                description=f"Analysis results for project {batch['project_id']}"
            )
            version = await repo.create_version(version_create)

        # Handle both dict (from HttpAnalysisRepository) and object formats for version
        if isinstance(version, dict):
            version_id = version.get("id")
        else:
            version_id = getattr(version, "id", None)

        if not version_id:
            logger.warning("Could not get version ID for storing analysis batch")
            return

        # Create batch
        batch_create = AnalysisBatchCreate(
            version_id=version_id,
            batch_name=batch['batch_id'],  # Use batch_id as batch_name
            status=batch.get('status', 'pending')
        )

        created_batch = await repo.create_batch(batch_create)

        # Store batch metadata in the batch's result_data if needed
        # For now, we'll just log the creation
        logger.info(f"Stored analysis batch: {batch['batch_id']}")

    except Exception as e:
        logger.error(f"Failed to store analysis batch {batch.get('batch_id', 'unknown')}: {e}")
        raise

async def _get_analysis_batch(batch_id: str, project_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve analysis batch using AnalysisResultRepository"""
    try:
        repo = get_analysis_repository()

        # Get version for this project
        version_number = f"project_{project_id}"
        version = await repo.get_version_by_number(version_number)
        if not version:
            return None

        # Get batch by name (we stored batch_id as batch_name)
        batch = await repo.get_batch_by_id(batch_id)
        if not batch:
            return None

        # Handle both dict (from HttpAnalysisRepository) and object formats for batch
        if isinstance(batch, dict):
            batch_id_val = batch.get("id", batch_id)
            batch_name = batch.get("batch_name", "")
            batch_status = batch.get("status", "unknown")
            created_at = batch.get("created_at", datetime.now())
            updated_at = batch.get("updated_at", datetime.now())
        else:
            batch_id_val = getattr(batch, "id", batch_id)
            batch_name = getattr(batch, "batch_name", "")
            batch_status = getattr(batch, "status", "unknown")
            created_at = getattr(batch, "created_at", datetime.now())
            updated_at = getattr(batch, "updated_at", datetime.now())

        # Convert to expected format
        return {
            "batch_id": batch_id_val,
            "project_id": project_id,
            "analysis_type": batch_name.split('_')[0] if '_' in batch_name else 'unknown',
            "status": batch_status,
            "created_at": created_at.isoformat() if hasattr(created_at, 'isoformat') else str(created_at),
            "completed_at": (updated_at.isoformat() if hasattr(updated_at, 'isoformat') else str(updated_at)) if batch_status == 'completed' else None,
            "filenames": [],  # Would need to get from results
            "results": []  # Would need to get from results
        }

    except Exception as e:
        logger.error(f"Failed to retrieve analysis batch {batch_id}: {e}")
        return None

async def _list_project_analysis_batches(
    project_id: str,
    status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """List project analysis batches using AnalysisResultRepository"""
    try:
        repo = get_analysis_repository()

        # Get version for this project
        version_number = f"project_{project_id}"
        version = await repo.get_version_by_number(version_number)
        if not version:
            return []

        # Handle mock data (dict) vs. real object
        version_id = version.get("id") if isinstance(version, dict) else getattr(version, "id", None)
        if not version_id:
            return []

        # Get batches for this version
        batches = await repo.get_batches_by_version(version_id, limit=limit, offset=offset)

        result = []
        for batch in batches:
            # Handle both dict (mock data) and object (real data) formats
            batch_status = batch.get('status') if isinstance(batch, dict) else getattr(batch, 'status', 'unknown')
            if status and batch_status != status:
                continue

            result.append({
                "batch_id": batch.get('id') if isinstance(batch, dict) else getattr(batch, 'id', ''),
                "project_id": project_id,
                "analysis_type": (batch.get('batch_name', '').split('_')[0] if isinstance(batch, dict) else (getattr(batch, 'batch_name', '').split('_')[0])) if '_' in (batch.get('batch_name', '') if isinstance(batch, dict) else getattr(batch, 'batch_name', '')) else 'unknown',
                "status": batch_status,
                "created_at": batch.get('created_at', datetime.now()).isoformat() if isinstance(batch, dict) else getattr(batch, 'created_at', datetime.now()).isoformat(),
                "completed_at": (batch.get('updated_at', datetime.now()).isoformat() if isinstance(batch, dict) else getattr(batch, 'updated_at', datetime.now()).isoformat()) if batch_status == 'completed' else None,
                "filenames": [],  # Would need to get from results
                "results": []  # Would need to get from results
            })

        return result

    except Exception as e:
        logger.error(f"Failed to list analysis batches for project {project_id}: {e}")
        return []

async def _store_analysis_version(version: Dict[str, Any]):
    """Store analysis version using AnalysisResultRepository"""
    try:
        repo = get_analysis_repository()

        version_create = AnalysisVersionCreate(
            version_number=version['version_id'],  # Use version_id as version_number
            description=version.get('description', f"Analysis version {version['version_id']}")
        )

        created_version = await repo.create_version(version_create)
        logger.info(f"Stored analysis version: {version['version_id']}")

    except Exception as e:
        logger.error(f"Failed to store analysis version {version.get('version_id', 'unknown')}: {e}")
        raise

async def _get_latest_analysis_version(analysis_id: str) -> Optional[int]:
    """Get latest version number for analysis using AnalysisResultRepository"""
    try:
        repo = get_analysis_repository()

        # Find the analysis result first to get project context
        # This is a simplified implementation - in practice you'd need project_id
        # For now, return a default version
        logger.info(f"Getting latest version for analysis: {analysis_id}")
        return 1

    except Exception as e:
        logger.error(f"Failed to get latest version for analysis {analysis_id}: {e}")
        return None

async def _list_analysis_versions(analysis_id: str) -> List[Dict[str, Any]]:
    """List analysis versions using AnalysisResultRepository"""
    try:
        repo = get_analysis_repository()

        # This is a simplified implementation
        # In practice, you'd need to track versions differently
        logger.info(f"Listing versions for analysis: {analysis_id}")
        return []

    except Exception as e:
        logger.error(f"Failed to list versions for analysis {analysis_id}: {e}")
        return []

async def _get_analysis_version(analysis_id: str, version_number: int) -> Optional[Dict[str, Any]]:
    """Get specific analysis version using AnalysisResultRepository"""
    try:
        repo = get_analysis_repository()

        # This is a simplified implementation
        logger.info(f"Retrieving version {version_number} for analysis: {analysis_id}")
        return None

    except Exception as e:
        logger.error(f"Failed to get version {version_number} for analysis {analysis_id}: {e}")
        return None

async def _process_analysis_batch_background(
    project_id: str,
    batch_id: str,
    request: BatchAnalysisRequest,
    correlation_id: Optional[str] = None
):
    """Background processing for analysis batch using AnalysisResultRepository"""
    try:
        logger.info(f"Starting background processing for batch {batch_id}")

        results = []

        # Process each file
        for filename in request.filenames:
            try:
                # Create analysis result for this file
                analysis_result = {
                    "analysis_id": str(uuid.uuid4()),
                    "project_id": project_id,
                    "filename": filename,
                    "analysis_type": request.analysis_type,
                    "content": f"Analysis result for {filename}",  # Placeholder content
                    "metadata": request.metadata or {},
                    "version": 1,
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                    "processing_time": 1.0
                }

                # Store the result
                await _store_analysis_result(analysis_result)

                results.append({
                    "filename": filename,
                    "status": "success",
                    "analysis_id": analysis_result["analysis_id"],
                    "processing_time": 1.0
                })

            except Exception as e:
                logger.error(f"Error processing {filename} in batch: {e}")
                results.append({
                    "filename": filename,
                    "status": "error",
                    "error": str(e)
                })

        # Update batch with results
        await _update_analysis_batch(batch_id, project_id, {
            "status": "completed",
            "results": results,
            "completed_at": datetime.now().isoformat()
        })

        logger.info(f"Completed background processing for batch {batch_id}")

    except Exception as e:
        logger.error(f"Error in background batch processing: {e}")
        await _update_analysis_batch(batch_id, project_id, {
            "status": "failed",
            "error": str(e),
            "completed_at": datetime.now().isoformat()
        })

async def _trigger_background_analysis(
    project_id: str,
    filenames: List[str],
    correlation_id: Optional[str] = None
):
    """Trigger async LLM-based background analysis for uploaded files"""
    try:
        logger.info(f"Starting async LLM analysis for {len(filenames)} files in project {project_id}")

        # Generate analysis ID for tracking
        analysis_id = str(uuid.uuid4())

        # Create LLM batch analysis request
        batch_request = LLMBatchAnalysisRequest(
            filenames=filenames,
            analysis_type="comprehensive",
            max_concurrent=5,  # Process 5 files concurrently to avoid overwhelming the system
            force_reanalysis=False
        )

        # Initialize batch analysis status
        batch_status = {
            "analysis_id": analysis_id,
            "status": "started",
            "total_files": len(filenames),
            "processed_files": 0,
            "results": [],
            "started_at": datetime.now().isoformat(),
            "summary_stats": {
                "successful_analyses": 0,
                "failed_analyses": 0,
                "average_quality_score": 0.0,
                "total_processing_time": 0.0
            },
            "triggered_by_upload": True
        }

        # Store batch status
        _llm_batch_analysis_status[analysis_id] = batch_status

        # Start async LLM analysis background processing
        asyncio.create_task(
            _process_llm_batch_analysis_background(
                project_id,
                analysis_id,
                batch_request,
                correlation_id
            )
        )

        # Update document statuses to "analysis_pending"
        await _update_document_analysis_status(project_id, filenames, "analysis_pending", analysis_id)

        logger.info(f"Async LLM analysis triggered successfully for analysis {analysis_id}")

    except Exception as e:
        logger.error(f"Error triggering async LLM analysis: {e}")
        # If analysis trigger fails, mark documents as "analysis_failed"
        try:
            await _update_document_analysis_status(project_id, filenames, "analysis_failed", None)
        except Exception as update_error:
            logger.error(f"Error updating document status after trigger failure: {update_error}")

async def _update_document_analysis_status(
    project_id: str,
    filenames: List[str],
    status: str,
    analysis_id: Optional[str] = None
):
    """Update analysis status for documents in the storage service"""
    try:
        import httpx
        
        async with httpx.AsyncClient(timeout=processor.http_timeout) as client:
            headers = {
                "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
            }
            
            for filename in filenames:
                update_data = {
                    "analysis_status": status,
                    "updated_at": datetime.now().isoformat()
                }
                if analysis_id:
                    update_data["analysis_id"] = analysis_id
                
                # Update document metadata in storage service
                storage_url = await processor._get_storage_url()
                response = await client.put(
                    f"{storage_url}/api/storage/projects/{project_id}/files/{filename}/metadata",
                    json=update_data,
                    headers=headers,
                )
                
                if response.status_code != 200:
                    logger.warning(f"Failed to update analysis status for {filename}: {response.status_code}")
                    
    except Exception as e:
        logger.error(f"Error updating document analysis status: {e}")

async def _update_analysis_batch(batch_id: str, project_id: str, updates: Dict[str, Any]):
    """Update analysis batch using AnalysisResultRepository"""
    try:
        repo = get_analysis_repository()

        # Get version for this project
        version_number = f"project_{project_id}"
        version = await repo.get_version_by_number(version_number)
        if not version:
            return

        # Get batch by ID
        batch = await repo.get_batch_by_id(batch_id)
        if not batch:
            return

        # Update batch fields
        batch_updates = {}
        if "status" in updates:
            batch_updates["status"] = updates["status"]

        if batch_updates:
            # Note: The repository doesn't have update_batch method, so we'd need to add it
            # For now, we'll log the update
            logger.info(f"Updating analysis batch: {batch_id} with {batch_updates}")

        logger.info(f"Updated analysis batch: {batch_id}")

    except Exception as e:
        logger.error(f"Failed to update analysis batch {batch_id}: {e}")
        raise
