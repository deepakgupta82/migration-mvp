#!/usr/bin/env python3
"""
LLM Router - Clean API endpoints for LLM orchestration
Handles process-specific LLM requests, configuration, and provider management
"""

from typing import Dict, List, Any, Optional, Union
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
import logging
import httpx
import os
import time
import socket
from datetime import datetime

from ..core.llm_processor import LLMProcessor, LLMProcessType
from ..core.vision_adapter import VisionAdapter
from ..core.vision_schemas import is_valid_table_payload, is_valid_diagram_payload
import asyncio as _asyncio

logger = logging.getLogger("llm-service")
router = APIRouter()
    
# -------------------------
# Wiring placeholders (guarded)
# -------------------------
def _flag_enabled(name: str, default: bool = False) -> bool:
    try:
        v = os.getenv(name, str(default)).strip().lower()
        return v in ("1", "true", "yes", "on")
    except Exception:
        return default

@router.get("/rag/attribution/v2/schema")
async def attribution_v2_schema():
    if not _flag_enabled("ADVANCED_RAG_ENABLED", False):
        raise HTTPException(status_code=404, detail="advanced rag disabled")
    return {
        "version": os.getenv("CITATION_SCHEMA_VERSION", "v2-proposed"),
        "per_citation": [
            "overlap_ratio",
            "embedding_similarity",
            "alignment_score",
            "coverage_ratio",
            "hallucination_score",
            "attribution_score",
            "attribution_class"
        ],
        "aggregates": [
            "avg_overlap",
            "avg_embedding_similarity",
            "avg_alignment",
            "avg_coverage",
            "avg_score",
            "low_quality_ratio",
            "strong_count",
            "partial_count",
            "weak_count"
        ]
    }

# ---------------- Streaming Metrics (SSE instrumentation) ----------------
_STREAMING_METRICS: Dict[str, Any] = {
    "total_streams": 0,
    "active_streams": 0,
    "completed_streams": 0,
    "cancelled_streams": 0,
    "error_streams": 0,
    "total_tokens_streamed": 0,
    "latency_buckets": {"<50": 0, "<100": 0, "<250": 0, "<500": 0, "<1000": 0, ">=1000": 0},
    "avg_token_latency_ms": 0.0,
    "p95_token_latency_ms": 0.0,
    "last_updated": None,
}

def _record_token_latency(lat_ms: float):
    try:
        if lat_ms < 50: _STREAMING_METRICS["latency_buckets"]["<50"] += 1
        elif lat_ms < 100: _STREAMING_METRICS["latency_buckets"]["<100"] += 1
        elif lat_ms < 250: _STREAMING_METRICS["latency_buckets"]["<250"] += 1
        elif lat_ms < 500: _STREAMING_METRICS["latency_buckets"]["<500"] += 1
        elif lat_ms < 1000: _STREAMING_METRICS["latency_buckets"]["<1000"] += 1
        else: _STREAMING_METRICS["latency_buckets"][">=1000"] += 1
        arr: List[float] = _STREAMING_METRICS.setdefault("_lat_samples", [])  # type: ignore
        arr.append(lat_ms)
        if len(arr) > 5000:
            del arr[: len(arr) - 5000]
        import statistics as _stats
        _STREAMING_METRICS["avg_token_latency_ms"] = round(_stats.mean(arr), 2)
        sorted_arr = sorted(arr)
        idx = int(0.95 * (len(sorted_arr) - 1))
        _STREAMING_METRICS["p95_token_latency_ms"] = round(sorted_arr[idx], 2)
    except Exception:
        pass
    from datetime import datetime as _dt
    _STREAMING_METRICS["last_updated"] = _dt.utcnow().isoformat() + "Z"

# Initialize clean processor + vision adapter
llm_processor = LLMProcessor()
vision_adapter = VisionAdapter()
_MULTIMODAL_ENABLED = str(os.getenv("MULTIMODAL_ENABLED", "true")).lower() in ("1", "true", "yes", "on")
_OCR_ENABLED = str(os.getenv("OCR_ENABLED", os.getenv("VISION_OCR_ENABLED", "auto"))).lower() in ("1", "true", "yes", "on", "auto")
_MAX_VISION_IN_FLIGHT = int(os.getenv("MAX_VISION_IN_FLIGHT", "4"))
_vision_sem = _asyncio.Semaphore(_MAX_VISION_IN_FLIGHT)
_FAKE_MODE = str(os.getenv("LLM_FAKE_RESPONSES", "false")).lower() in ("1", "true", "yes", "on")

# Request/Response Models
class ProcessLLMRequest(BaseModel):
    process_type: str = Field(..., description="Process type requiring LLM")
    prompt: str = Field(..., description="Prompt to process")
    project_id: Optional[str] = Field(None, description="Optional project ID")
    allow_global: Optional[bool] = Field(True, description="Allow fallback to global LLM configs if project configs are missing")

class ChatMessage(BaseModel):
    role: str = Field(..., description="Message role (system, user, assistant)")
    content: str = Field(..., description="Message content")

class ChatCompletionRequest(BaseModel):
    messages: List[ChatMessage] = Field(..., description="Chat messages")
    model: Optional[str] = Field(None, description="Model to use")
    temperature: Optional[float] = Field(0.7, description="Temperature for response generation")
    max_tokens: Optional[int] = Field(512, description="Maximum tokens to generate")
    project_id: Optional[str] = Field(None, description="Project ID for configuration")
    provider: Optional[str] = Field(None, description="LLM provider")

class ChatCompletionResponse(BaseModel):
    choices: List[Dict[str, Any]]
    usage: Optional[Dict[str, Any]] = None
    model: str
    id: str
    object: str = "chat.completion"
    created: int

class ProcessLLMResponse(BaseModel):
    process_type: str
    response: str
    success: bool
    error: Optional[str] = None

class ClusteringRequest(BaseModel):
    project_id: Optional[str] = None
    items: List[Dict[str, Any]] = Field(..., description="Items to cluster with 'text' and optional 'id'/'metadata'")
    max_clusters: Optional[int] = Field(8, description="Soft cap on clusters")
    hint: Optional[str] = Field(None, description="Optional domain hint")

class ClusteringResponse(BaseModel):
    clusters: List[Dict[str, Any]]
    success: bool
    error: Optional[str] = None

class EnrichRequest(BaseModel):
    project_id: Optional[str] = None
    text: str = Field(..., description="Text to enrich (facts/entities/relationships)")
    mode: str = Field("facts_entities", description="facts|entities|facts_entities|relationships")
    hint: Optional[str] = Field(None, description="Optional domain or schema hints")

class EnrichResponse(BaseModel):
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None
    cache_key: Optional[str] = None
    cache_enabled: Optional[bool] = None
    cache_forced: Optional[bool] = None
    # Advanced enrichment metadata (added by post-processing)
    normalized: Optional[bool] = None
    section_path_tags: Optional[List[str]] = None
    multimodal_flags: Optional[Dict[str, bool]] = None

class MultimodalTablesRequest(BaseModel):
    project_id: Optional[str] = None
    text: Optional[str] = Field(None, description="Textual context to help with table extraction")
    image_urls: Optional[List[str]] = Field(default_factory=list, description="Optional list of image URLs to analyze")
    hint: Optional[str] = Field(None, description="Domain/schema hints (e.g., column names)")

class MultimodalDiagramsRequest(BaseModel):
    project_id: Optional[str] = None
    text: Optional[str] = Field(None, description="Textual context")
    image_urls: Optional[List[str]] = Field(default_factory=list, description="Diagram images to analyze")
    hint: Optional[str] = Field(None, description="Domain/schema hints")

class MultimodalResponse(BaseModel):
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None

class RAGSynthesisRequest(BaseModel):
    project_id: str = Field(..., description="Project ID (required for governed retrieval)")
    question: str = Field(..., min_length=4, description="User question / query")
    top_k: int = Field(8, ge=1, le=25, description="Number of fused results to use")
    per_kind_k: int = Field(12, ge=2, le=50, description="Initial per-kind candidate cap before fusion")
    kinds: Optional[List[str]] = Field(None, description="Subset of kinds to search (raw_chunks, entity_cards, triple_cards)")
    semantic_weight: float = Field(0.7, ge=0.0, le=1.0, description="Semantic weight for hybrid search when available")
    rrf_k: int = Field(60, ge=10, le=200, description="RRF constant k value")
    include_sources: bool = Field(True, description="Return citation block with sources")
    ranking_strategy: str = Field("rrf", pattern="^(rrf|centrality_augmented)$", description="Ranking strategy: rrf|centrality_augmented")
    centrality_weight: float = Field(0.4, ge=0.0, le=2.0, description="Weight multiplier for centrality boost when strategy=centrality_augmented")

class RAGSynthesisResponse(BaseModel):
    project_id: str
    question: str
    answer: str
    citations: List[Dict[str, Any]]
    used_kinds: List[str]
    retrieval_stats: Dict[str, Any]
    model: Optional[str] = None
    timestamp: str
    attribution_stats: Optional[Dict[str, Any]] = None

class AdvancedRAGRequest(RAGSynthesisRequest):
    stream: bool = Field(False, description="Enable token streaming (placeholder)")
    validate_citations: bool = Field(True, description="Perform lightweight citation grounding validation")
    min_citation_overlap: float = Field(0.55, ge=0.0, le=1.0, description="Minimum token overlap ratio for citation acceptance")
    max_invalid_allow: int = Field(2, ge=0, le=10, description="Max invalid citations allowed before warning tag")

class AdvancedRAGResponse(RAGSynthesisResponse):
    invalid_citations: Optional[List[str]] = None
    validation_warnings: Optional[List[str]] = None
    streaming: bool = False

# ---------------- Card Summarization Models ----------------
class CardEvidence(BaseModel):
    content: str
    source_id: Optional[str] = None
    filename: Optional[str] = None
    weight: Optional[float] = 1.0

class CardSummarizeRequest(BaseModel):
    project_id: Optional[str] = None
    card_type: str = Field("entity", pattern="^(entity|triple)$", description="Type of card inputs")
    subject: Optional[str] = Field(None, description="Entity name or (subject) for triple context")
    predicate: Optional[str] = Field(None, description="Predicate when card_type=triple")
    object: Optional[str] = Field(None, description="Object when card_type=triple")
    evidences: List[CardEvidence] = Field(..., description="List of evidence snippets")
    max_summary_tokens: int = Field(160, ge=40, le=600, description="Soft cap for summary generation")
    include_variants: bool = Field(True, description="Return key variant phrases")
    centrality_boost: bool = Field(True, description="If project_id present, attempt centrality weighting via graph-service")
    force_refresh: bool = Field(False, description="Bypass cache if enrichment-like caching added later")

class CardSummarizeResponse(BaseModel):
    project_id: Optional[str]
    card_type: str
    subject: Optional[str]
    predicate: Optional[str]
    object: Optional[str]
    summary: str
    provenance_refs: List[Dict[str, Any]]
    key_variants: Optional[List[str]] = None
    stats: Dict[str, Any]
    model: Optional[str] = None
    timestamp: str
    cache_key: Optional[str] = None
    cache_hit: Optional[bool] = None

@router.post("/cards/summarize", response_model=CardSummarizeResponse, summary="Advanced summarization of entity/triple cards with provenance weighting")
async def summarize_cards(req: CardSummarizeRequest, http_request: Request):
    # Entire implementation in a single outer try to avoid partial try blocks triggering SyntaxError
    try:
        if not req.evidences:
            raise HTTPException(status_code=400, detail="At least one evidence required")
        import json as _json
        from hashlib import sha256
        from app.core.evidence_utils import dedupe_evidences
        from app.cache.card_cache import get_card_cache

        corr_id = http_request.headers.get("X-Correlation-ID")
        # Centrality (best-effort)
        centrality_map: Dict[str, float] = {}
        if req.project_id and req.centrality_boost:
            graph_url = os.getenv("GRAPH_SERVICE_URL", "http://localhost:8006")
            try:
                async with httpx.AsyncClient(timeout=3.5) as client:
                    r = await client.get(f"{graph_url}/api/graphs/projects/{req.project_id}/canonical/centrality?limit=500")
                    if r.status_code == 200:
                        for item in r.json().get("items", []):
                            nm = (item.get("name") or "").lower()
                            centrality_map[nm] = float(item.get("normalized_total_degree") or 0.0)
            except Exception:
                pass

        subj_lower = (req.subject or "").lower()
        raw_items: List[Dict[str, Any]] = []
        for ev in req.evidences:
            base_w = float(ev.weight or 1.0)
            boost = centrality_map.get(subj_lower, 0.0) * 0.5 if subj_lower else 0.0
            weight = base_w * (1.0 + boost)
            raw_items.append({
                "content": (ev.content or "").strip()[:800],
                "source_id": ev.source_id,
                "filename": ev.filename,
                "weight": weight,
            })
        deduped, groups_meta = dedupe_evidences(raw_items)
        processed = deduped

        cache = get_card_cache()
        subj = req.subject or "_"
        pred = req.predicate or "_"
        obj = req.object or "_"
        evid_sig = sha256("|".join(sorted([d['content'] for d in processed])).encode("utf-8")).hexdigest()[:32]
        card_cache_schema_version = os.getenv("CARD_CACHE_SCHEMA_VERSION", "v1")
        key = f"{req.card_type}|{subj}|{pred}|{obj}|{evid_sig}|{req.max_summary_tokens}|{card_cache_schema_version}"

        processed.sort(key=lambda x: x["weight"], reverse=True)
        top_for_prompt = processed[: min(18, len(processed))]
        header = "You are an expert summarization engine. Create a concise, factual summary. Avoid redundancy.\n"
        if req.card_type == "entity":
            header += f"FOCUS ENTITY: {req.subject}\n"
        else:
            header += f"FOCUS TRIPLE: ({req.subject}) -[{req.predicate}]-> ({req.object})\n"
        header += "Return JSON: {\"summary\": str, \"key_variants\": [..]} ONLY.\nEVIDENCE BLOCKS:\n"
        evidence_block = "\n".join([f"[{i}] (w={ev['weight']}) {ev['content']}" for i, ev in enumerate(top_for_prompt)])
        prompt = header + evidence_block + f"\nMAX_TOKENS_HINT={req.max_summary_tokens}\nJSON:"

        async def _invoke_llm():
            return await llm_processor.process_llm_request(
                process_type="content_summarization",
                prompt=prompt,
                project_id=req.project_id,
                corr_id=corr_id,
                allow_global=True,
            )

        force_refresh = bool(req.force_refresh)
        if cache.enabled:
            llm_resp = await cache.get_or_set(key, _invoke_llm, force_refresh=force_refresh)
            cache_hit = not force_refresh and len(processed) > 0 and not any(g.get('dup_count',0)>1 for g in groups_meta)
        else:
            llm_resp = await _invoke_llm()

        summary_text = ""
        key_variants: List[str] = []
        try:
            parsed = _json.loads(llm_resp)
            summary_text = str(parsed.get("summary") or "")[:1200]
            if req.include_variants:
                kv = parsed.get("key_variants") or []
                if isinstance(kv, list):
                    key_variants = [str(k)[:120] for k in kv[:12]]
        except Exception:
            summary_text = llm_resp[:1200]

        provenance_refs = processed[: min(12, len(processed))]
        duplicate_groups = [g for g in groups_meta if g.get("dup_count", 0) > 1]
        original_count = len(req.evidences)
        stats = {
            "evidence_count": len(processed),
            "original_evidence_count": original_count,
            "duplicates_removed": original_count - len(processed),
            "duplicate_groups": len(duplicate_groups),
            "used_for_prompt": len(top_for_prompt),
            "centrality_subject_boost": centrality_map.get(subj_lower, 0.0) if subj_lower else 0.0,
            "avg_weight": round(sum(p['weight'] for p in processed)/len(processed), 4) if processed else 0.0,
            "cache_enabled": cache.enabled if 'cache' in locals() else False,
            "cache_key": key,
            "cache_hit_heuristic": cache_hit if 'cache_hit' in locals() else False,
        }
        return CardSummarizeResponse(
            project_id=req.project_id,
            card_type=req.card_type,
            subject=req.subject,
            predicate=req.predicate,
            object=req.object,
            summary=summary_text,
            provenance_refs=provenance_refs,
            key_variants=key_variants or None,
            stats=stats,
            model="governed-config",
            timestamp=datetime.utcnow().isoformat(),
            cache_key=key,
            cache_hit=(cache_hit if 'cache_hit' in locals() and cache_hit else None),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Card summarization failed: {e}")
        raise HTTPException(status_code=500, detail="Card summarization failed")

class LLMConfigurationCreate(BaseModel):
    name: str = Field(..., description="Configuration name")
    provider: str = Field(..., description="LLM provider (openai, gemini, anthropic, ollama)")
    model: str = Field(..., description="Model name")
    api_key: str = Field(..., description="API key")
    google_cloud_project_id: Optional[str] = Field(None, description="Google Cloud Project ID (for Gemini)")
    temperature: Optional[str] = Field("0.1", description="Temperature setting")
    max_tokens: Optional[str] = Field("20000", description="Max tokens setting")
    description: Optional[str] = Field(None, description="Configuration description")

class LLMConfigurationUpdate(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    google_cloud_project_id: Optional[str] = None
    temperature: Optional[str] = None
    max_tokens: Optional[str] = None
    description: Optional[str] = None

class LLMConfigurationResponse(BaseModel):
    id: str
    name: str
    provider: str
    model: str
    google_cloud_project_id: Optional[str] = None
    temperature: str
    max_tokens: str
    description: Optional[str] = None
    created_at: str
    updated_at: str

class TestLLMConfigRequest(BaseModel):
    config_id: Optional[str] = None
    provider: str
    model: str
    api_key: Optional[str] = None
    temperature: Optional[float] = 0.1
    max_tokens: Optional[int] = 100
    query: Optional[str] = "TEST REQUEST: Please respond with 'TEST SUCCESSFUL - LLM is working correctly' to confirm connectivity."

class HealthResponse(BaseModel):
    service: str
    status: str
    uptime: int
    timestamp: str
    version: str = "1.0.0"
    langchain_available: bool
    supported_providers: List[str]
    process_types: List[str]
    cache_status: Dict[str, Any]
    dependencies: Dict[str, str]
    streaming_status: Optional[Dict[str, Any]] = None

async def check_dependencies():
    """Check service dependencies for readiness"""
    dependencies = {}

    # Check PostgreSQL
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            database=os.getenv("POSTGRES_DB", "migration_platform"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", "postgres")
        )
        conn.close()
        dependencies["postgresql"] = "healthy"
    except Exception:
        dependencies["postgresql"] = "unhealthy"

    # Check Redis
    try:
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        with socket.create_connection((redis_host, redis_port), timeout=2):
            dependencies["redis"] = "healthy"
    except Exception:
        dependencies["redis"] = "unhealthy"

    return dependencies

@router.get("/livez")
async def liveness_check():
    """Liveness probe - checks if service is running"""
    return {
        "status": "healthy",
        "service": "llm-service",
        "uptime": 0,  # Would need global start time
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

@router.get("/healthz")
async def readiness_check():
    """Readiness probe - checks if service is ready to accept traffic"""
    dependencies = await check_dependencies()

    # Determine overall status
    overall_status = "healthy" if all(status == "healthy" for status in dependencies.values()) else "unhealthy"

    return {
        "status": overall_status,
        "service": "llm-service",
        "uptime": 0,  # Would need global start time
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "dependencies": dependencies
    }

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Clean health check endpoint"""
    try:
        health_data = await llm_processor.health_check()
        dependencies = await check_dependencies()

        # Calculate uptime (approximate, since we don't have exact start time)
        uptime = int(time.time() - time.time())  # Placeholder, would need global start time

        # Merge in vision adapter metrics if available
        vision_metrics = {}
        try:
            if vision_adapter and hasattr(vision_adapter, "get_cache_metrics"):
                vision_metrics = vision_adapter.get_cache_metrics()
        except Exception:
            vision_metrics = {"error": "vision_metrics_unavailable"}

        # Append to cache_status (vision + enrichment)
        if isinstance(health_data.get("cache_status"), dict):
            health_data["cache_status"].update({"vision": vision_metrics})
            # Enrichment cache metrics (A8)
            try:
                from app.cache.enrich_cache import get_enrichment_cache  # local import to avoid early init cost
                enrichment_cache = get_enrichment_cache()
                health_data["cache_status"].update({"enrichment": enrichment_cache.metrics()})
            except Exception:
                health_data["cache_status"].update({"enrichment": {"error": "unavailable"}})
            # Card summary cache metrics
            try:
                from app.cache.card_cache import get_card_cache
                card_cache = get_card_cache()
                health_data["cache_status"].update({"card_summary": card_cache.metrics()})
            except Exception:
                health_data["cache_status"].update({"card_summary": {"error": "unavailable"}})

        # Attach streaming metrics (SSE) if available
        try:
            from collections import deque as _dq  # noqa: F401  (ensures import present if not already)
            health_streaming = dict(_STREAMING_METRICS)
            # Copy latency buckets reference (already primitive types)
            health_streaming["latency_buckets"] = dict(_STREAMING_METRICS["latency_buckets"])  # type: ignore
        except Exception:
            health_streaming = {"error": "unavailable"}

        # Collect schema versions (enrichment + card caches)
        try:
            enrich_version = os.getenv("ENRICH_SCHEMA_VERSION", "v1")
        except Exception:
            enrich_version = "unknown"
        try:
            card_version = os.getenv("CARD_CACHE_SCHEMA_VERSION", "v1")
        except Exception:
            card_version = "unknown"
        if isinstance(health_data.get("cache_status"), dict):
            health_data["cache_status"].setdefault("schema_versions", {"enrich": enrich_version, "cards": card_version})

        return HealthResponse(
            service="llm-service",
            status=health_data["status"],
            uptime=uptime,
            timestamp=datetime.now().isoformat(),
            version="1.0.0",
            langchain_available=health_data["langchain_available"],
            supported_providers=list(health_data.get("supported_providers", [])),
            process_types=health_data["process_types"],
            cache_status=health_data["cache_status"],
            dependencies=dependencies,
            streaming_status=health_streaming,
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@router.get("/providers")
async def list_providers():
    """List available LLM providers"""
    try:
        providers = await llm_processor.list_providers()
        return {"providers": providers}
    except Exception as e:
        logger.error(f"Error listing providers: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/providers/status")
async def get_provider_status():
    """Get status and configuration info for all providers"""
    try:
        status = await llm_processor.get_provider_status()
        return {"provider_status": status}
    except Exception as e:
        logger.error(f"Error getting provider status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/process-types")
async def list_process_types():
    """List supported LLM process types"""
    try:
        process_types = await llm_processor.list_process_types()
        return {"process_types": process_types}
    except Exception as e:
        logger.error(f"Error listing process types: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/recommendations/{process_type}")
async def get_model_recommendations(process_type: str):
    """Get model recommendations for specific process type"""
    try:
        recommendations = llm_processor.get_model_recommendations(process_type)
        return {
            "process_type": process_type,
            "recommendations": recommendations
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid process type: {process_type}")
    except Exception as e:
        logger.error(f"Error getting recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process", response_model=ProcessLLMResponse)
async def process_llm_request(request: ProcessLLMRequest, http_request: Request):
    """Process LLM request for specific process type"""
    try:
        corr_id = http_request.headers.get("X-Correlation-ID")
        # Enforce policy: require project_id and disallow global fallback if configured
        enforce_val = os.getenv("ENFORCE_PROJECT_LLM")
        try:
            from app.core.config_client import cfg_get as _cfg
            cfg_flag = _cfg(["llm_service", "enforce_project_llm"], enforce_val)
        except Exception:
            cfg_flag = enforce_val
        enforce = (cfg_flag if isinstance(cfg_flag, bool) else str(cfg_flag).lower() in ("1", "true", "yes"))
        if enforce and not request.project_id:
            raise HTTPException(status_code=400, detail="Project ID is required by policy (enforce_project_llm=true)")
        effective_allow_global = False if enforce else bool(request.allow_global if request.allow_global is not None else True)
        response_text = await llm_processor.process_llm_request(
            process_type=request.process_type,
            prompt=request.prompt,
            project_id=request.project_id,
            corr_id=corr_id,
            allow_global=effective_allow_global
        )
        
        return ProcessLLMResponse(
            process_type=request.process_type,
            response=response_text,
            success=True
        )
        
    except ValueError as e:
        return ProcessLLMResponse(
            process_type=request.process_type,
            response="",
            success=False,
            error=f"Invalid process type: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error processing LLM request: {e}")
        return ProcessLLMResponse(
            process_type=request.process_type,
            response="",
            success=False,
            error=str(e)
        )

@router.post("/rag/synthesize", response_model=RAGSynthesisResponse, summary="Hybrid RAG synthesis across multi-kind embeddings (RRF + optional centrality boost)")
async def rag_synthesize(req: RAGSynthesisRequest, http_request: Request, _emit_analytics: bool = True):
    """Perform governed RAG synthesis over raw_chunks, entity_cards, triple_cards using Reciprocal Rank Fusion.

    Steps:
      1. For each selected kind perform similarity search (semantic) limited to per_kind_k
      2. Apply RRF over ranks to produce fused ordering
      3. Build structured context block with citations
      4. Call LLM with governed process_type 'rag_synthesis' (enforcing project config policy)
      5. Emit analytics/websocket event (best-effort)
    """
    try:
        import time as _time
        start_ts = _time.time()
        corr_id = http_request.headers.get("X-Correlation-ID")
        kinds_all = ["raw_chunks", "entity_cards", "triple_cards"]
        kinds = [k for k in (req.kinds or kinds_all) if k in kinds_all]
        if not kinds:
            kinds = kinds_all

        vector_url = os.getenv("VECTOR_SERVICE_URL", "http://localhost:8005")
        headers = {"Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"}
        if corr_id:
            headers["X-Correlation-ID"] = corr_id

        async def fetch_kind(kind: str):
            payload = {"query": req.question, "limit": req.per_kind_k, "include_metadata": True}
            url = f"{vector_url}/projects/{req.project_id}/collections/{kind}/search"
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.post(url, json=payload, headers=headers)
                if r.status_code >= 400:
                    return kind, []
                data = r.json()
                return kind, data.get("results", [])

        # Parallel fetch
        import asyncio
        fetch_results = await asyncio.gather(*[fetch_kind(k) for k in kinds])
        by_kind = {k: res for k, res in fetch_results}

        # Build base RRF scores
        rrf_k = req.rrf_k
        fused: Dict[str, Dict[str, Any]] = {}
        for kind, results in by_kind.items():
            for rank, item in enumerate(results):
                doc_id = item.get("id") or f"{kind}:{rank}:{item.get('filename','')}"
                score = 1.0 / (rrf_k + rank + 1)
                entry = fused.setdefault(doc_id, {"doc_id": doc_id, "kinds": set(), "rrf_score": 0.0, "payload": item, "primary_kind": kind})
                entry["rrf_score"] += score
                entry["kinds"].add(kind)
        fused_list = list(fused.values())

        # Optional centrality augmentation
        centrality_hits = 0
        if req.ranking_strategy == "centrality_augmented":
            try:
                graph_url = os.getenv("GRAPH_SERVICE_URL", "http://localhost:8006")
                # Fetch centrality (normalized_total_degree)
                async with httpx.AsyncClient(timeout=8.0) as client:
                    rcent = await client.get(f"{graph_url}/api/graphs/projects/{req.project_id}/canonical/centrality?limit=1000", headers=headers)
                    cent_map: Dict[str, float] = {}
                    if rcent.status_code < 400:
                        for row in rcent.json().get("items", []):
                            cent_map[row.get("id")] = float(row.get("normalized_total_degree", 0.0))
                import re
                # Filenames from canonical entity vectors: canonical_entity_<id>.txt
                ent_pattern = re.compile(r"canonical_entity_([0-9a-fA-F-]{32,36})\.txt")
                subj_pat = re.compile(r"Subject Canonical ID:\s*(\S+)")
                obj_pat = re.compile(r"Object Canonical ID:\s*(\S+)")
                for item in fused_list:
                    payload = item.get("payload", {}) or {}
                    meta = payload.get("metadata", {}) or {}
                    fname = meta.get("filename", "")
                    associated: List[str] = []
                    # entity_cards
                    m = ent_pattern.search(fname)
                    if m:
                        associated.append(m.group(1))
                    # triple_cards: parse content lines for subject/object canonical IDs if present
                    if item.get("primary_kind") == "triple_cards":
                        content = payload.get("content") or ""
                        for pat in (subj_pat, obj_pat):
                            for mm in pat.finditer(content):
                                associated.append(mm.group(1))
                    if associated:
                        cval = max(cent_map.get(a, 0.0) for a in associated)
                        if cval > 0:
                            centrality_hits += 1
                        item["centrality_score"] = cval
                        item["aug_score"] = item["rrf_score"] * (1 + req.centrality_weight * cval)
                    else:
                        item["centrality_score"] = 0.0
                        item["aug_score"] = item["rrf_score"]
            except Exception as e:
                logger.warning(f"Centrality augmentation failed: {e}")
                for item in fused_list:
                    item["centrality_score"] = 0.0
                    item["aug_score"] = item["rrf_score"]
        else:
            for item in fused_list:
                item["centrality_score"] = 0.0
                item["aug_score"] = item["rrf_score"]

        sort_key = "aug_score" if req.ranking_strategy == "centrality_augmented" else "rrf_score"
        fused_list.sort(key=lambda x: x[sort_key], reverse=True)
        top_fused = fused_list[: req.top_k]

        # Build context block
        context_sections = []
        citations = []
        # Precompute answer later => placeholder; we build citations first then after answer we compute alignment
        for i, doc in enumerate(top_fused):
            payload = doc["payload"]
            content = payload.get("content") or payload.get("text") or payload.get("chunk") or ""
            snippet = content[:1200]
            source = payload.get("filename") or payload.get("source") or "unknown"
            section = f"[Source {i+1} | kinds={','.join(sorted(doc['kinds']))} | id={doc['doc_id']} | score={doc['rrf_score']:.4f}]\n{snippet}"
            context_sections.append(section)
            citations.append({
                "rank": i + 1,
                "doc_id": doc["doc_id"],
                "kinds": sorted(doc["kinds"]),
                "score": doc["rrf_score"],
                "filename": source,
                "preview": snippet[:280],
            })

        context_block = "\n\n".join(context_sections)
        synthesis_prompt = (
            "You are a migration knowledge synthesis engine. Answer the user question strictly grounded in the provided sources.\n"
            "Return a concise, factual answer (<= 350 words) with no hallucinations. If insufficient data, explicitly state that.\n"
            "After the answer, include a JSON block: {\"citations_used\": [ids]} enumerating source ids referenced.\n"
            f"QUESTION: {req.question}\n\nSOURCES:\n{context_block}\n\nANSWER:" )

        # Governed LLM call
        answer_text = await llm_processor.process_llm_request(
            process_type="rag_synthesis",
            prompt=synthesis_prompt,
            project_id=req.project_id,
            corr_id=corr_id,
            allow_global=True,  # still allow fallback unless enforcement forbids
        )

        # Emit event (best-effort)
        try:
            backend_url = os.getenv("BACKEND_SERVICE_URL", "http://localhost:8000")
            evt_payload = {
                "project_id": req.project_id,
                "event_type": "rag_synthesized",
                "question": req.question,
                "retrieval": {"kinds": kinds, "per_kind_k": req.per_kind_k, "fused_top_k": req.top_k},
                "timestamp": datetime.utcnow().isoformat(),
            }
            async with httpx.AsyncClient(timeout=3.0) as client:
                await client.post(f"{backend_url}/api/stats/events", json=evt_payload, headers=headers)
        except Exception:
            pass

        # Attribution scoring v1: lexical overlap + embedding similarity -> combined score
        import re as _re, math as _math
        answer_tokens = [t for t in _re.split(r"[^a-z0-9]+", answer_text.lower()) if t]
        answer_set = set(answer_tokens)
        def _overlap_ratio(preview: str) -> float:
            if not preview:
                return 0.0
            pv_tokens = [t for t in _re.split(r"[^a-z0-9]+", preview.lower()) if t]
            if not pv_tokens:
                return 0.0
            inter = sum(1 for t in pv_tokens if t in answer_set)
            return inter / len(pv_tokens)

        # Attempt embedding similarity (best-effort; degrade gracefully)
        embed_sim_available = False
        answer_embed = None
        embed_model = os.getenv("ATTRIBUTION_EMBED_MODEL") or os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        try:
            # Simple reuse of vector-service embedding endpoint if available
            vector_url = os.getenv("VECTOR_SERVICE_URL", "http://localhost:8005")
            payload = {"texts": [answer_text], "model": embed_model}
            async with httpx.AsyncClient(timeout=5.0) as _client:
                r = await _client.post(f"{vector_url}/embed/batch", json=payload)
                if r.status_code == 200:
                    data = r.json()
                    if data.get("embeddings"):
                        answer_embed = data["embeddings"][0]
                        embed_sim_available = True
        except Exception:
            pass

        def _cos(a: List[float], b: List[float]) -> float:
            if not a or not b or len(a) != len(b):
                return 0.0
            num = sum(x*y for x,y in zip(a,b))
            da = _math.sqrt(sum(x*x for x in a))
            db = _math.sqrt(sum(y*y for y in b))
            if not da or not db:
                return 0.0
            return num/(da*db)

        overlap_scores = []
        embed_scores = []
        combined_scores = []
        hallucinated = 0
        w_embed = 0.65
        w_lex = 0.35
        for c in citations:
            ov = _overlap_ratio(c.get("preview", ""))
            c["overlap_ratio"] = round(ov, 4)
            emb_sim = 0.0
            if embed_sim_available and answer_embed and isinstance(c.get("embedding"), list):
                emb_sim = _cos(answer_embed, c["embedding"])
            c["embedding_similarity"] = round(emb_sim, 4)
            combined = (w_embed * emb_sim) + (w_lex * ov)
            c["attribution_score"] = round(combined,4)
            # classify by combined score thresholds
            if combined < 0.25:
                c["attribution_class"] = "weak"
                hallucinated += 1
            elif combined < 0.55:
                c["attribution_class"] = "partial"
            else:
                c["attribution_class"] = "strong"
            overlap_scores.append(ov)
            embed_scores.append(emb_sim)
            combined_scores.append(combined)
        def _avg(arr):
            return (sum(arr)/len(arr)) if arr else 0.0
        low_quality_ratio = (sum(1 for s in combined_scores if s < 0.45)/len(combined_scores)) if combined_scores else 0.0
        attribution_stats = {
            "avg_overlap": round(_avg(overlap_scores),4),
            "avg_embedding_similarity": round(_avg(embed_scores),4),
            "avg_score": round(_avg(combined_scores),4),
            "min_score": round(min(combined_scores),4) if combined_scores else 0.0,
            "low_quality_ratio": round(low_quality_ratio,4),
            "strong": sum(1 for c in citations if c.get("attribution_class") == "strong"),
            "partial": sum(1 for c in citations if c.get("attribution_class") == "partial"),
            "weak": sum(1 for c in citations if c.get("attribution_class") == "weak"),
            "hallucination_ratio": round(hallucinated/len(citations),4) if citations else 0.0,
            "embedding_model": embed_model,
            "degraded_mode": not embed_sim_available,
        }
        resp = RAGSynthesisResponse(
            project_id=req.project_id,
            question=req.question,
            answer=answer_text,
            citations=citations if req.include_sources else [],
            used_kinds=kinds,
            retrieval_stats={
                "fused_candidates": len(fused_list),
                "selected": len(top_fused),
                "rrf_k": rrf_k,
                "ranking_strategy": req.ranking_strategy,
                "centrality_weight": req.centrality_weight if req.ranking_strategy == "centrality_augmented" else 0.0,
                "centrality_hits": centrality_hits if req.ranking_strategy == "centrality_augmented" else 0,
            },
            model="governed-config",
            timestamp=datetime.utcnow().isoformat(),
            attribution_stats=attribution_stats,
        )
        # Emit attribution analytics (best-effort)
        try:
            import httpx as _httpx, os as _os
            analytics_url = _os.getenv("ANALYTICS_SERVICE_URL", "http://localhost:8014")
            headers = {"Authorization": f"Bearer {_os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"}
            if corr_id:
                headers["X-Correlation-ID"] = corr_id
            if attribution_stats:
                attr_metrics = {
                    "avg_score": attribution_stats.get("avg_score"),
                    "min_score": attribution_stats.get("min_score"),
                    "low_quality_ratio": attribution_stats.get("low_quality_ratio"),
                    "strong": attribution_stats.get("strong"),
                    "partial": attribution_stats.get("partial"),
                    "weak": attribution_stats.get("weak"),
                    "hallucination_ratio": attribution_stats.get("hallucination_ratio"),
                    "avg_embedding_similarity": attribution_stats.get("avg_embedding_similarity"),
                    "avg_overlap": attribution_stats.get("avg_overlap"),
                    "citation_count": len(citations),
                }
                metrics_payload = {
                    "source": "llm-service",
                    "project_id": req.project_id,
                    "metrics": {"attribution_pipeline": attr_metrics}
                }
                async with _httpx.AsyncClient(timeout=2.5) as _client:
                    await _client.post(f"{analytics_url}/ingest", json=metrics_payload, headers=headers)
        except Exception:
            pass
        # Emit analytics ingest (best-effort) only when not called internally by advanced variant
        if _emit_analytics:
            try:
                import httpx, os as _os
                analytics_url = _os.getenv("ANALYTICS_SERVICE_URL", "http://localhost:8014")
                headers = {"Authorization": f"Bearer {_os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"}
                if corr_id:
                    headers["X-Correlation-ID"] = corr_id
                # answer token count
                answer_tokens_count = len(answer_tokens)
                latency_ms = round((_time.time() - start_ts) * 1000, 2)
                metrics_payload = {
                    "source": "llm-service",
                    "project_id": req.project_id,
                    "metrics": {
                        "rag": {
                            "kinds": kinds,
                            "fused_candidates": len(fused_list),
                            "used": len(top_fused),
                            "invalid_citations": 0,
                            "centrality_augmented": (req.ranking_strategy == "centrality_augmented"),
                            "answer_tokens": answer_tokens_count,
                            "latency_ms": latency_ms,
                        }
                    }
                }
                async with httpx.AsyncClient(timeout=2.5) as client:
                    await client.post(f"{analytics_url}/ingest", json=metrics_payload, headers=headers)
            except Exception:
                pass
        return resp
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"RAG synthesis failed: {e}")
        raise HTTPException(status_code=500, detail="RAG synthesis failed")

@router.post("/rag/advanced", response_model=AdvancedRAGResponse, summary="Advanced RAG with optional citation validation & streaming (Phase C4 scaffold)")
async def rag_advanced(req: AdvancedRAGRequest, http_request: Request):
    if os.getenv("ADVANCED_RAG_ENABLED", "false").lower() not in {"1","true","yes","on"}:
        raise HTTPException(status_code=403, detail="Advanced RAG disabled. Set ADVANCED_RAG_ENABLED=true to enable.")
    # Reuse baseline synthesis for retrieval + answer, then post-process citations
    base_req = RAGSynthesisRequest(
        project_id=req.project_id,
        question=req.question,
        top_k=req.top_k,
        per_kind_k=req.per_kind_k,
        kinds=req.kinds,
        semantic_weight=req.semantic_weight,
        rrf_k=req.rrf_k,
        include_sources=True,
        ranking_strategy=req.ranking_strategy,
        centrality_weight=req.centrality_weight,
    )
    base = await rag_synthesize(base_req, http_request, _emit_analytics=False)  # type: ignore
    invalid: List[str] = []
    warnings: List[str] = []
    if req.validate_citations and base.citations:
        # Lightweight grounding: compute token overlap between citation id snippet and answer body
        import re
        from collections import Counter
        ans_tokens = [t for t in re.split(r"[^a-z0-9]+", base.answer.lower()) if t]
        ans_counts = Counter(ans_tokens)
        vector_url = os.getenv("VECTOR_SERVICE_URL", "http://localhost:8005")
        headers = {"Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"}
        async def fetch_preview(cid: Dict[str, Any]):
            # No dedicated fetch endpoint; attempt similarity on a synthetic query of doc_id not available.
            # Placeholder: trust content preview aggregated during baseline; future: dedicated fetch API.
            return cid.get("filename", "")
        import asyncio
        previews = await asyncio.gather(*[fetch_preview(c) for c in base.citations])
        for c, prev in zip(base.citations, previews):
            # Token overlap heuristic
            prev_tokens = [t for t in re.split(r"[^a-z0-9]+", str(prev).lower()) if t]
            if not prev_tokens:
                continue
            overlap = sum((ans_counts.get(t, 0) > 0) for t in prev_tokens) / len(prev_tokens)
            if overlap < req.min_citation_overlap:
                invalid.append(c.get("doc_id", "?"))
        if len(invalid) > req.max_invalid_allow:
            warnings.append(f"High number of low-overlap citations: {len(invalid)} > {req.max_invalid_allow}")
    resp = AdvancedRAGResponse(
        project_id=base.project_id,
        question=base.question,
        answer=base.answer,
        citations=base.citations,
        used_kinds=base.used_kinds,
        retrieval_stats=base.retrieval_stats,
        model=base.model,
        timestamp=base.timestamp,
        invalid_citations=invalid or None,
        validation_warnings=warnings or None,
        streaming=bool(req.stream),
    )
    # Emit enriched RAG analytics (includes invalid citation counts) best-effort
    try:
        import time as _time, httpx, os as _os
        analytics_url = _os.getenv("ANALYTICS_SERVICE_URL", "http://localhost:8014")
        headers = {"Authorization": f"Bearer {_os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"}
        corr_id = http_request.headers.get("X-Correlation-ID")
        if corr_id:
            headers["X-Correlation-ID"] = corr_id
        answer_tokens_count = len(base.answer.split())
        # base.retrieval_stats has fused_candidates & selected
        retrieval = base.retrieval_stats or {}
        metrics_payload = {
            "source": "llm-service",
            "project_id": req.project_id,
            "metrics": {
                "rag": {
                    "kinds": base.used_kinds,
                    "fused_candidates": retrieval.get("fused_candidates", 0),
                    "used": retrieval.get("selected", 0),
                    "invalid_citations": len(invalid),
                    "validation_warnings": warnings if warnings else None,
                    "centrality_augmented": (req.ranking_strategy == "centrality_augmented"),
                    "answer_tokens": answer_tokens_count,
                    # approximate latency not tracked separately here (baseline already emitted); optional omit
                }
            }
        }
        async with httpx.AsyncClient(timeout=2.5) as client:
            await client.post(f"{analytics_url}/ingest", json=metrics_payload, headers=headers)
    except Exception:
        pass
    return resp

# ---------------- Streaming Variant (SSE) ----------------
@router.post("/rag/advanced/stream")
async def rag_advanced_stream(req: AdvancedRAGRequest, http_request: Request):
    """Server-Sent Events streaming variant of advanced RAG synthesis.

    Requires env STREAM_ANSWERS=true. Emits events:
      - meta: initial retrieval metadata
      - token: partial answer tokens
      - done: final answer payload (AdvancedRAGResponse shape)
    """
    if os.getenv("STREAM_ANSWERS", "false").lower() not in {"1","true","yes","on"}:
        raise HTTPException(status_code=403, detail="Streaming disabled. Set STREAM_ANSWERS=true to enable.")
    from fastapi import Response
    import json, asyncio

    # Reuse non-stream advanced logic to build final answer; we will simulate token streaming
    req.stream = True  # mark
    base_resp = await rag_advanced(req, http_request)
    answer_text = base_resp.answer
    tokens = answer_text.split()

    async def event_generator():
        import time as _t
        start_stream = _t.time()
        _STREAMING_METRICS["total_streams"] += 1
        _STREAMING_METRICS["active_streams"] += 1
        last_ts = _t.time()
        first_token_latency_ms = None
        tokens_emitted = 0
        cancelled = False
        try:
            # meta event
            meta = {
                "project_id": base_resp.project_id,
                "question": base_resp.question,
                "used_kinds": base_resp.used_kinds,
                "retrieval_stats": base_resp.retrieval_stats,
                "model": base_resp.model,
                "timestamp": base_resp.timestamp,
            }
            yield f"event: meta\ndata: {json.dumps(meta)}\n\n"
            # stream tokens
            for t in tokens:
                now = _t.time()
                lat_ms = (now - last_ts) * 1000.0
                last_ts = now
                _record_token_latency(lat_ms)
                if first_token_latency_ms is None:
                    first_token_latency_ms = round((now - start_stream) * 1000.0, 2)
                _STREAMING_METRICS["total_tokens_streamed"] += 1
                tokens_emitted += 1
                yield f"event: token\ndata: {json.dumps({'token': t})}\n\n"
                await asyncio.sleep(0.01)
            # final payload
            final_payload = base_resp.model_dump()
            yield f"event: done\ndata: {json.dumps(final_payload)}\n\n"
            _STREAMING_METRICS["completed_streams"] += 1
        except asyncio.CancelledError:
            cancelled = True
            _STREAMING_METRICS["cancelled_streams"] += 1
            raise
        except Exception:
            _STREAMING_METRICS["error_streams"] += 1
            raise
        finally:
            _STREAMING_METRICS["active_streams"] = max(0, _STREAMING_METRICS["active_streams"] - 1)
            # Optionally emit analytics for streaming session
            try:
                import httpx as _httpx, os as _os
                analytics_url = _os.getenv("ANALYTICS_SERVICE_URL", "http://localhost:8014")
                headers = {"Authorization": f"Bearer {_os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"}
                corr_id = http_request.headers.get("X-Correlation-ID")
                if corr_id:
                    headers["X-Correlation-ID"] = corr_id
                duration_s = max(1e-6, (_t.time() - start_stream))
                tokens_per_second = round(tokens_emitted / duration_s, 3) if tokens_emitted else 0.0
                payload = {
                    "source": "llm-service",
                    "project_id": req.project_id,
                    "metrics": {
                        "streaming": {
                            "tokens": tokens_emitted,
                            "cancelled": cancelled,
                            "duration_ms": int((_t.time() - start_stream) * 1000),
                            "first_token_latency_ms": first_token_latency_ms,
                            "tokens_per_second": tokens_per_second,
                        }
                    }
                }
                async with _httpx.AsyncClient(timeout=2.0) as client:
                    await client.post(f"{analytics_url}/ingest", json=payload, headers=headers)
            except Exception:
                pass

    return Response(event_generator(), media_type="text/event-stream")

@router.post("/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(request: ChatCompletionRequest, http_request: Request):
    """OpenAI-compatible chat completions endpoint"""
    try:
        corr_id = http_request.headers.get("X-Correlation-ID")
        
        # Convert messages to a single prompt for the LLM processor
        prompt_parts = []
        for message in request.messages:
            if message.role == "system":
                prompt_parts.append(f"System: {message.content}")
            elif message.role == "user":
                prompt_parts.append(f"User: {message.content}")
            elif message.role == "assistant":
                prompt_parts.append(f"Assistant: {message.content}")
        
        prompt = "\n".join(prompt_parts)
        
        # Use a general conversation process type
        response_text = await llm_processor.process_llm_request(
            process_type="conversation",
            prompt=prompt,
            project_id=request.project_id,
            corr_id=corr_id,
            allow_global=True
        )
        
        # Format as OpenAI-compatible response
        import uuid
        import time
        
        response = ChatCompletionResponse(
            choices=[{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_text
                },
                "finish_reason": "stop"
            }],
            usage={
                "prompt_tokens": len(prompt.split()),
                "completion_tokens": len(response_text.split()),
                "total_tokens": len(prompt.split()) + len(response_text.split())
            },
            model=request.model or "default",
            id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
            created=int(time.time())
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error in chat completions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/resolve")
async def resolve_process_configuration(process_type: str, project_id: Optional[str] = None, request: Request = None, allow_global: bool = Query(True)):
    """Resolve provider/model configuration for a process+project without instantiating an LLM."""
    try:
        corr_id = request.headers.get("X-Correlation-ID") if request else None
        # Apply enforcement
        enforce_val = os.getenv("ENFORCE_PROJECT_LLM")
        try:
            from app.core.config_client import cfg_get as _cfg
            cfg_flag = _cfg(["llm_service", "enforce_project_llm"], enforce_val)
        except Exception:
            cfg_flag = enforce_val
        enforce = (cfg_flag if isinstance(cfg_flag, bool) else str(cfg_flag).lower() in ("1", "true", "yes"))
        if enforce and not project_id:
            raise HTTPException(status_code=400, detail="Project ID is required by policy (enforce_project_llm=true)")
        eff_allow = False if enforce else allow_global
        cfg = await llm_processor.resolve_process_configuration(process_type, project_id, corr_id=corr_id, allow_global=eff_allow)
        if not cfg:
            raise HTTPException(status_code=404, detail="No configuration found")
        return cfg
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving process configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cluster", response_model=ClusteringResponse, summary="LLM-assisted semantic clustering")
async def cluster_items(req: ClusteringRequest, http_request: Request):
    """Group items by semantic similarity using a lightweight LLM summarization + heuristic merge.
    Input item format: { id?: string, text: string, metadata?: any }
    Output clusters: [ { id, label, items: [ids], size } ]
    """
    try:
        if not req.items:
            return ClusteringResponse(clusters=[], success=True)
        # Use processor to summarize themes; then simple token overlap grouping as baseline
        corr_id = http_request.headers.get("X-Correlation-ID")
        summary_prompt = (
            "Summarize main themes from the following bullet points in 5-8 concise labels. "
            "Respond as a JSON array of strings only.\n\nITEMS:\n" + "\n".join([f"- {i.get('text','')[:400]}" for i in req.items])
        )
        summary = await llm_processor.process_llm_request(
            process_type="rag_synthesis",
            prompt=summary_prompt,
            project_id=req.project_id,
            corr_id=corr_id,
            allow_global=True,
        )
        try:
            import json as _json
            labels = _json.loads(summary)
            if not isinstance(labels, list):
                labels = []
        except Exception:
            labels = []
        labels = [str(l) for l in labels][: max(1, min(int(req.max_clusters or 8), 20))]

        # Heuristic assign by simple cosine-ish token overlap
        def tokenize(s: str) -> set:
            import re
            return set([t for t in re.split(r"[^a-z0-9]+", (s or "").lower()) if t and len(t) > 2])

        label_tokens = [tokenize(l) for l in labels]
        clusters = [ {"id": f"c{i}", "label": labels[i], "items": [], "size": 0} for i in range(len(labels)) ] or [ {"id": "c0", "label": "General", "items": [], "size": 0} ]
        for it in req.items:
            t = tokenize(it.get("text", ""))
            # score against labels
            best = 0
            best_i = 0
            for i, lt in enumerate(label_tokens or [set()]):
                if not lt:
                    continue
                inter = len(t & lt)
                score = inter / max(1, len(lt))
                if score > best:
                    best = score
                    best_i = i
            clusters[best_i]["items"].append(it.get("id") or it.get("text")[:50])
            clusters[best_i]["size"] += 1
        return ClusteringResponse(clusters=clusters, success=True)
    except Exception as e:
        logger.error(f"Clustering failed: {e}")
        return ClusteringResponse(clusters=[], success=False, error=str(e))

@router.post("/enrich", response_model=EnrichResponse, summary="LLM enrichment for facts/entities/relationships")
async def enrich(req: EnrichRequest, http_request: Request):
    """Perform targeted enrichment using the appropriate LLM configuration.

    Honors `ENFORCE_PROJECT_LLM` (or config override) to require `project_id` when enabled.
    """
    try:
        import os, json  # local imports to satisfy runtime and lint
        corr_id = http_request.headers.get("X-Correlation-ID")
        # Enforce per-project policy
        enforce_val = os.getenv("ENFORCE_PROJECT_LLM")
        try:
            from app.core.config_client import cfg_get as _cfg
            cfg_flag = _cfg(["llm_service", "enforce_project_llm"], enforce_val)
        except Exception:
            cfg_flag = enforce_val
        enforce = (cfg_flag if isinstance(cfg_flag, bool) else str(cfg_flag).lower() in ("1", "true", "yes"))
        if enforce and not req.project_id:
            raise HTTPException(status_code=400, detail="Project ID is required by policy (enforce_project_llm=true)")

        # Choose process type based on mode
        mode = (req.mode or "facts_entities").lower()
        if mode in ("facts", "facts_entities"):
            process_type = "fact_extraction"
        elif mode == "entities":
            process_type = "entity_extraction"
        else:
            process_type = "rag_synthesis"

        prompt = (
            "You are an enrichment engine. Given the text, return STRICT JSON with the requested fields. "
            "Never include commentary. "
        )
        if mode == "facts":
            prompt += '{"facts": [{"name": "...", "value": "...", "evidence": "..."}]}'
        elif mode == "entities":
            prompt += '{"entities": [{"name": "...", "type": "...", "aliases": []}]}'
        elif mode == "facts_entities":
            prompt += '{"facts": [...], "entities": [...]}'
        else:
            prompt += '{"relationships": [{"source": "...", "type": "...", "target": "...", "evidence": "..."}]}'
        if req.hint:
            prompt += f"\nHINT: {req.hint}\n"
        prompt += "\nTEXT:\n" + req.text[:180000]

        # ---------------- Enrichment cache integration (A8) ----------------
        # Key includes process_type, project scope (or global), and a stable hash of prompt body
        from hashlib import sha256
        from app.cache.enrich_cache import get_enrichment_cache
        cache = get_enrichment_cache()
        # Derive short hash to control key length
        phash = sha256(prompt.encode("utf-8")).hexdigest()[:40]
        scope = req.project_id or "global"
        cache_key = f"{process_type}|{scope}|{phash}"
        force_refresh = str(os.getenv("FORCE_REFRESH_ENRICH", "false")).lower() in ("1","true","yes","on") or bool(req.force_refresh)

        async def _invoke():
            return await llm_processor.process_llm_request(
                process_type=process_type,
                prompt=prompt,
                project_id=req.project_id,
                corr_id=corr_id,
                allow_global=not enforce,
            )

        resp_text = await cache.get_or_set(cache_key, _invoke, force_refresh=force_refresh)
        try:
            data = json.loads(resp_text)
        except Exception:
            # Try to extract JSON from text
            import re
            m = re.search(r"\{[\s\S]*\}$", resp_text.strip())
            data = json.loads(m.group(0)) if m else {"raw": resp_text}
        # ---------------- Advanced Post Processing (A9) ----------------
        normalized = False
        section_tags: List[str] = []
        multimodal_flags: Dict[str, bool] = {}
        try:
            # 1. Normalize entity structures
            if isinstance(data, dict):
                # Entities normalization
                ents = data.get("entities") if isinstance(data.get("entities"), list) else []
                norm_entities = []
                seen = set()
                from hashlib import sha1 as _sha1
                for e in ents:
                    if not isinstance(e, dict):
                        continue
                    name = str(e.get("name") or "").strip()
                    if not name:
                        continue
                    key = name.lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    etype = str(e.get("type") or e.get("category") or "Entity").strip() or "Entity"
                    aliases = e.get("aliases") if isinstance(e.get("aliases"), list) else []
                    aliases = [str(a).strip() for a in aliases if a and isinstance(a, (str,int,float))]
                    aliases = list(dict.fromkeys([a for a in aliases if a and a.lower() != name.lower()]) )[:10]
                    sig_src = f"{name}|{etype}|{'|'.join(sorted([a.lower() for a in aliases]))}"
                    sig = _sha1(sig_src.encode('utf-8')).hexdigest()[:20]
                    norm_entities.append({
                        "id": f"ent_{len(norm_entities)+1}",
                        "name": name,
                        "type": etype,
                        "aliases": aliases,
                        "source": e.get("source") or e.get("provenance") or None,
                        "signature": sig,
                    })
                if norm_entities:
                    data["entities_normalized"] = norm_entities
                    normalized = True

                # Facts normalization
                facts = data.get("facts") if isinstance(data.get("facts"), list) else []
                norm_facts = []
                for f in facts:
                    if not isinstance(f, dict):
                        continue
                    fname = str(f.get("name") or f.get("key") or f.get("property") or "").strip()
                    fval = f.get("value")
                    if isinstance(fval, (dict,list)):
                        try:
                            import json as _json
                            fval = _json.dumps(fval)[:400]
                        except Exception:
                            fval = str(fval)
                    fval = (str(fval).strip() if fval is not None else "")
                    if not fname and not fval:
                        continue
                    evidence = f.get("evidence") or f.get("source") or f.get("provenance")
                    sig_src = f"{fname}|{fval}" if fname or fval else evidence or ''
                    sig = _sha1(sig_src.encode('utf-8')).hexdigest()[:20]
                    norm_facts.append({
                        "id": f"fact_{len(norm_facts)+1}",
                        "name": fname or None,
                        "value": fval or None,
                        "evidence": evidence,
                        "signature": sig,
                    })
                if norm_facts:
                    data["facts_normalized"] = norm_facts
                    normalized = True

                # Relationships normalization (if present)
                rels = data.get("relationships") if isinstance(data.get("relationships"), list) else []
                norm_rels = []
                for r in rels:
                    if not isinstance(r, dict):
                        continue
                    src = str(r.get("source") or r.get("from") or "").strip()
                    dst = str(r.get("target") or r.get("to") or "").strip()
                    rtype = str(r.get("type") or r.get("relation") or "RELATED").strip() or "RELATED"
                    if not src or not dst:
                        continue
                    ev = r.get("evidence") or r.get("source") or r.get("provenance")
                    sig_src = f"{src}|{rtype}|{dst}" 
                    sig = _sha1(sig_src.encode('utf-8')).hexdigest()[:20]
                    norm_rels.append({
                        "id": f"rel_{len(norm_rels)+1}",
                        "source": src,
                        "target": dst,
                        "type": rtype.upper(),
                        "evidence": ev,
                        "signature": sig,
                    })
                if norm_rels:
                    data["relationships_normalized"] = norm_rels
                    normalized = True

                # 2. Extract MinerU style section path tags (if caller included them in text marker lines like [SECTION:path])
                import re as _re
                section_tags = list(dict.fromkeys([
                    m.group(1).strip()[:80]
                    for m in _re.finditer(r"\[SECTION:([^\]]+)\]", req.text[:200000])
                    if m.group(1).strip()
                ]))[:25]
                if section_tags:
                    data["detected_section_paths"] = section_tags

                # 3. Multimodal flags heuristics (presence of table/diagram markers or image URLs)
                # Simple detection of inline pseudo tables (lines with pipes) and figure captions (Figure X: ...)
                text_sample = req.text[:20000]
                table_lines = [ln for ln in text_sample.splitlines() if ln.count('|') >= 2][:15]
                figure_caps = list(dict.fromkeys([
                    m.group(0).strip()
                    for m in _re.finditer(r"figure\s+\d+[^\n]{0,120}", text_sample, _re.I)
                ]))[:15]
                if table_lines:
                    data["tables_detected"] = table_lines
                if figure_caps:
                    data["figures_detected"] = figure_caps
                multimodal_flags = {
                    "has_table_markers": bool(_re.search(r"\btable\b", text_sample, _re.I)) or bool(table_lines),
                    "has_diagram_markers": bool(_re.search(r"diagram|figure", text_sample, _re.I)) or bool(figure_caps),
                    "has_section_tags": bool(section_tags),
                    "inline_tables_detected": bool(table_lines),
                    "figure_captions_detected": bool(figure_caps),
                }
                if any(multimodal_flags.values()):
                    data["multimodal_flags"] = multimodal_flags
        except Exception as _ppe:  # Post-processing errors should not fail endpoint
            logger.warning(f"Enrich post-processing warning: {_ppe}")

        return EnrichResponse(
            success=True,
            data=data,
            cache_key=cache_key,
            cache_enabled=cache.enabled,
            cache_forced=force_refresh,
            normalized=normalized or None,
            section_path_tags=section_tags or None,
            multimodal_flags=multimodal_flags or None,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Enrich failed: {e}")
        return EnrichResponse(success=False, data={}, error=str(e))

@router.get("/configurations")
async def get_configurations():
    """Get LLM configurations"""
    try:
        configurations = await llm_processor.get_configurations()
        # Frontend expects a list; our processor returns a dict keyed by id
        if isinstance(configurations, dict):
            return list(configurations.values())
        return configurations
    except Exception as e:
        logger.error(f"Error getting configurations: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cache/invalidate")
async def invalidate_cache():
    """Invalidate configuration cache"""
    try:
        llm_processor.invalidate_cache()
        return {"message": "Cache invalidated successfully"}
    except Exception as e:
        logger.error(f"Error invalidating cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Legacy compatibility endpoints
@router.get("/entity-extraction/{project_id}")
async def get_entity_extraction_llm(project_id: str):
    """Legacy endpoint: Get LLM for entity extraction"""
    try:
        llm = await llm_processor.get_llm_for_entity_extraction(project_id)
        return {
            "project_id": project_id,
            "process_type": "entity_extraction", 
            "llm_available": llm is not None,
            "llm_type": str(type(llm).__name__) if llm else None
        }
    except Exception as e:
        logger.error(f"Error getting entity extraction LLM: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/crew-assessment/{project_id}")
async def get_crew_assessment_llm(project_id: str):
    """Legacy endpoint: Get LLM for crew assessment"""
    try:
        llm = await llm_processor.get_llm_for_crew_assessment(project_id)
        return {
            "project_id": project_id,
            "process_type": "crew_assessment",
            "llm_available": llm is not None,
            "llm_type": str(type(llm).__name__) if llm else None
        }
    except Exception as e:
        logger.error(f"Error getting crew assessment LLM: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/crew-documentation/{project_id}")
async def get_crew_documentation_llm(project_id: str):
    """Legacy endpoint: Get LLM for crew documentation"""
    try:
        llm = await llm_processor.get_llm_for_crew_documentation(project_id)
        return {
            "project_id": project_id,
            "process_type": "crew_documentation",
            "llm_available": llm is not None, 
            "llm_type": str(type(llm).__name__) if llm else None
        }
    except Exception as e:
        logger.error(f"Error getting crew documentation LLM: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# =====================================================================================
# LLM Configuration Management Endpoints
# =====================================================================================

@router.get("/configurations", summary="Get all LLM configurations")
async def get_llm_configurations():
    """List all LLM configurations"""
    try:
        # Use service discovery to get project service URL
        service_registry_url = os.getenv("SERVICE_REGISTRY_URL", "http://localhost:8011")
        async with httpx.AsyncClient() as client:
            # Query service registry for project service
            registry_response = await client.get(f"{service_registry_url}/services/project-service")
            if registry_response.status_code == 200:
                service_info = registry_response.json().get("service", {})
                if service_info.get("status") == "healthy":
                    project_service_url = f"http://{service_info['host']}:{service_info['port']}"
                else:
                    # Fallback to default
                    project_service_url = "http://localhost:8002"
            else:
                # Fallback to default
                project_service_url = "http://localhost:8002"

        url = f"{project_service_url}/llm-configurations"
        logger.info(f"Fetching LLM configurations from: {url}")

        # Add service authentication token
        headers = {"Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"}

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            logger.info(f"Response status: {response.status_code}, URL: {response.url}")
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Project service error: {response.status_code} - {response.text}")
                raise HTTPException(status_code=response.status_code, detail="Failed to fetch configurations")
    except httpx.RequestError as e:
        logger.error(f"Request error: {e}")
        raise HTTPException(status_code=503, detail="Project service unavailable")
    except Exception as e:
        logger.error(f"Error getting LLM configurations: {str(e)}")
        return []

@router.post("/configurations", summary="Create a new LLM configuration")
async def create_llm_configuration(config: LLMConfigurationCreate):
    """Create a new LLM configuration"""
    try:
        # Validate required fields
        if not config.api_key or config.api_key.strip() == '':
            raise HTTPException(status_code=400, detail="API key is required and cannot be empty")

        # Use service discovery to get project service URL
        service_registry_url = os.getenv("SERVICE_REGISTRY_URL", "http://localhost:8011")
        async with httpx.AsyncClient() as client:
            # Query service registry for project service
            registry_response = await client.get(f"{service_registry_url}/services/project-service")
            if registry_response.status_code == 200:
                service_info = registry_response.json().get("service", {})
                if service_info.get("status") == "healthy":
                    project_service_url = f"http://{service_info['host']}:{service_info['port']}"
                else:
                    # Fallback to default
                    project_service_url = "http://localhost:8002"
            else:
                # Fallback to default
                project_service_url = "http://localhost:8002"

        payload = {
            "name": config.name,
            "provider": config.provider,
            "model": config.model,
            "api_key": config.api_key,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "description": config.description or f"{config.name} - {config.provider}/{config.model}",
            "google_cloud_project_id": config.google_cloud_project_id
        }

        # Add service authentication token
        headers = {"Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"}

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{project_service_url}/llm-configurations",
                json=payload,
                headers=headers,
                timeout=15.0
            )
            if response.status_code == 201:
                return response.json()
            else:
                logger.error(f"Project service error: {response.status_code} - {response.text}")
                raise HTTPException(status_code=response.status_code, detail=f"Failed to create configuration: {response.text}")
    except httpx.RequestError as e:
        logger.error(f"Request error: {e}")
        raise HTTPException(status_code=503, detail="Project service unavailable")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating LLM configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create LLM configuration: {str(e)}")

@router.put("/configurations/{config_id}", summary="Update an LLM configuration")
async def update_llm_configuration(config_id: str, config: LLMConfigurationUpdate):
    """Update an LLM configuration"""
    try:
        # Validate API key if it's being updated
        update_data = config.model_dump(exclude_unset=True)
        if 'api_key' in update_data and (not update_data['api_key'] or update_data['api_key'].strip() == ''):
            raise HTTPException(status_code=400, detail="API key cannot be empty")

        # Use service discovery to get project service URL
        service_registry_url = os.getenv("SERVICE_REGISTRY_URL", "http://localhost:8011")
        async with httpx.AsyncClient() as client:
            # Query service registry for project service
            registry_response = await client.get(f"{service_registry_url}/services/project-service")
            if registry_response.status_code == 200:
                service_info = registry_response.json().get("service", {})
                if service_info.get("status") == "healthy":
                    project_service_url = f"http://{service_info['host']}:{service_info['port']}"
                else:
                    # Fallback to default
                    project_service_url = "http://localhost:8002"
            else:
                # Fallback to default
                project_service_url = "http://localhost:8002"

        # Add service authentication token
        headers = {"Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"}

        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{project_service_url}/llm-configurations/{config_id}",
                json=update_data,
                headers=headers,
                timeout=15.0
            )
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Project service error: {response.status_code} - {response.text}")
                raise HTTPException(status_code=response.status_code, detail=f"Failed to update configuration: {response.text}")
    except httpx.RequestError as e:
        logger.error(f"Request error: {e}")
        raise HTTPException(status_code=503, detail="Project service unavailable")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating LLM configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update LLM configuration: {str(e)}")

@router.delete("/configurations/{config_id}", summary="Delete an LLM configuration")
async def delete_llm_configuration(config_id: str):
    """Delete an LLM configuration"""
    try:
        # Use service discovery to get project service URL
        service_registry_url = os.getenv("SERVICE_REGISTRY_URL", "http://localhost:8011")
        async with httpx.AsyncClient() as client:
            # Query service registry for project service
            registry_response = await client.get(f"{service_registry_url}/services/project-service")
            if registry_response.status_code == 200:
                service_info = registry_response.json().get("service", {})
                if service_info.get("status") == "healthy":
                    project_service_url = f"http://{service_info['host']}:{service_info['port']}"
                else:
                    # Fallback to default
                    project_service_url = "http://localhost:8002"
            else:
                # Fallback to default
                project_service_url = "http://localhost:8002"

        # Add service authentication token
        headers = {"Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"}

        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{project_service_url}/llm-configurations/{config_id}",
                headers=headers,
                timeout=15.0
            )
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Project service error: {response.status_code} - {response.text}")
                raise HTTPException(status_code=response.status_code, detail=f"Failed to delete configuration: {response.text}")
    except httpx.RequestError as e:
        logger.error(f"Request error: {e}")
        raise HTTPException(status_code=503, detail="Project service unavailable")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting LLM configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete LLM configuration: {str(e)}")

@router.get("/models/{provider}", summary="List available models for provider")
async def list_provider_models(provider: str, api_key: str = Query(None)):
    """List available models for a provider"""
    try:
        if provider.lower() == "gemini" and api_key:
            # Dynamically fetch Gemini models
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                
                available_models = []
                models_iterator = genai.list_models()
                for model in models_iterator:
                    if hasattr(model, 'supported_generation_methods') and 'generateContent' in model.supported_generation_methods:
                        model_name = model.name.replace('models/', '')
                        available_models.append({
                            "id": model_name,
                            "name": model_name,
                            "description": f"Google Gemini {model_name}"
                        })
                
                if available_models:
                    return {"provider": provider, "models": available_models, "cached": False}
                else:
                    # Fallback to static models
                    static_models = [
                        {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro", "description": "Google Gemini 2.5 Pro"},
                        {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash", "description": "Google Gemini 2.5 Flash"},
                        {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro", "description": "Google Gemini 1.5 Pro"},
                        {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash", "description": "Google Gemini 1.5 Flash"}
                    ]
                    return {"provider": provider, "models": static_models, "cached": True}
                    
            except Exception as e:
                logger.warning(f"Failed to fetch Gemini models dynamically: {e}")
                # Fallback to static models
                static_models = [
                    {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro", "description": "Google Gemini 2.5 Pro"},
                    {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash", "description": "Google Gemini 2.5 Flash"},
                    {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro", "description": "Google Gemini 1.5 Pro"},
                    {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash", "description": "Google Gemini 1.5 Flash"}
                ]
                return {"provider": provider, "models": static_models, "cached": True}
        
        # For other providers, return static models for now
        static_provider_models = {
            "openai": [
                {"id": "gpt-4o", "name": "GPT-4o", "description": "OpenAI GPT-4o"},
                {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "description": "OpenAI GPT-4o Mini"},
                {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "description": "OpenAI GPT-4 Turbo"},
                {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo", "description": "OpenAI GPT-3.5 Turbo"}
            ],
            "anthropic": [
                {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet", "description": "Anthropic Claude 3.5 Sonnet"},
                {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus", "description": "Anthropic Claude 3 Opus"},
                {"id": "claude-3-sonnet-20240229", "name": "Claude 3 Sonnet", "description": "Anthropic Claude 3 Sonnet"},
                {"id": "claude-3-haiku-20240307", "name": "Claude 3 Haiku", "description": "Anthropic Claude 3 Haiku"}
            ],
            "ollama": [
                {"id": "llama3.1:8b", "name": "Llama 3.1 8B", "description": "Meta Llama 3.1 8B"},
                {"id": "llama3.1:70b", "name": "Llama 3.1 70B", "description": "Meta Llama 3.1 70B"},
                {"id": "mistral:7b", "name": "Mistral 7B", "description": "Mistral 7B"},
                {"id": "codellama:13b", "name": "Code Llama 13B", "description": "Meta Code Llama 13B"}
            ]
        }
        
        models = static_provider_models.get(provider.lower(), [])
        return {"provider": provider, "models": models, "cached": True}
        
    except Exception as e:
        logger.error(f"Error listing models for {provider}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list models: {str(e)}")

@router.post("/multimodal/tables", response_model=MultimodalResponse, summary="Extract tables (JSON) from text/images")
async def extract_tables(req: MultimodalTablesRequest, http_request: Request):
    """Strict-JSON table extraction; now with real vision enrichment.

    Steps added:
    - Optionally fetch & OCR images (VisionAdapter) when vision is enabled.
    - Inject summarized vision segment into prompt for more faithful extraction.
    """
    try:
        import json
        corr_id = http_request.headers.get("X-Correlation-ID")
        if not _MULTIMODAL_ENABLED or not vision_adapter.is_enabled():
            return MultimodalResponse(success=False, data={}, error="Multimodal vision disabled")
        enforce_val = os.getenv("ENFORCE_PROJECT_LLM")
        try:
            from app.core.config_client import cfg_get as _cfg
            cfg_flag = _cfg(["llm_service", "enforce_project_llm"], enforce_val)
        except Exception:
            cfg_flag = enforce_val
        enforce = (cfg_flag if isinstance(cfg_flag, bool) else str(cfg_flag).lower() in ("1", "true", "yes"))
        if enforce and not req.project_id:
            raise HTTPException(status_code=400, detail="Project ID is required by policy (enforce_project_llm=true)")

        # Compose prompt for table extraction; models that support vision can use URLs as hints in text
        pieces = [
            "You are a table extraction engine. Return STRICT JSON only.",
            "Schema: { \"tables\": [ { \"caption\": str|null, \"columns\": [str], \"rows\": [ [str|number|null] ] } ] }",
        ]
        if req.hint:
            pieces.append(f"HINT: {req.hint}")
        if req.text:
            pieces.append(f"CONTEXT:\n{req.text[:120000]}")
        vision_segment = ""
        if req.image_urls and vision_adapter.is_enabled():
            try:
                imgs = await vision_adapter.prepare_images(req.image_urls)
                vision_segment = await vision_adapter.build_enhanced_prompt_segment(imgs, mode="tables")
            except Exception as ve:
                logger.debug(f"Vision enrichment failed (tables): {ve}")
        if vision_segment:
            pieces.append(vision_segment)
        elif req.image_urls:
            pieces.append("IMAGES (listing only, vision disabled):\n" + "\n".join(req.image_urls[:10]))
        prompt = "\n\n".join(pieces)

        async with _vision_sem:
            if _FAKE_MODE:
                # Deterministic minimal structure for tests
                data = {"tables": [{"caption": None, "columns": ["Col1", "Col2"], "rows": [["A", "B"], ["C", "D"]]}]}
                return MultimodalResponse(success=True, data=data)
            resp_text = await llm_processor.process_llm_request(
                process_type=LLMProcessType.TABLE_EXTRACTION.value,
                prompt=prompt,
                project_id=req.project_id,
                corr_id=corr_id,
                allow_global=not enforce,
            )
            try:
                data = json.loads(resp_text)
            except Exception:
                import re
                m = re.search(r"\{[\s\S]*\}$", (resp_text or "").strip())
                data = json.loads(m.group(0)) if m else {"raw": resp_text}
            # Basic schema validation
            if not is_valid_table_payload(data):
                data = {"tables": [] , "raw": data}
            return MultimodalResponse(success=True, data=data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Table extraction failed: {e}")
        return MultimodalResponse(success=False, data={}, error=str(e))

@router.post("/multimodal/diagrams", response_model=MultimodalResponse, summary="Understand diagrams to entities/relations JSON")
async def understand_diagrams(req: MultimodalDiagramsRequest, http_request: Request):
    """Extract entities & directed relationships from diagrams; enriched with vision if enabled."""
    try:
        import json
        corr_id = http_request.headers.get("X-Correlation-ID")
        if not _MULTIMODAL_ENABLED or not vision_adapter.is_enabled():
            return MultimodalResponse(success=False, data={}, error="Multimodal vision disabled")
        enforce_val = os.getenv("ENFORCE_PROJECT_LLM")
        try:
            from app.core.config_client import cfg_get as _cfg
            cfg_flag = _cfg(["llm_service", "enforce_project_llm"], enforce_val)
        except Exception:
            cfg_flag = enforce_val
        enforce = (cfg_flag if isinstance(cfg_flag, bool) else str(cfg_flag).lower() in ("1", "true", "yes"))
        if enforce and not req.project_id:
            raise HTTPException(status_code=400, detail="Project ID is required by policy (enforce_project_llm=true)")

        pieces = [
            "You are a diagram understanding engine. Return STRICT JSON only.",
            "Schema: { \"entities\": [ { \"name\": str, \"type\": str|null } ], \"relationships\": [ { \"source\": str, \"type\": str, \"target\": str } ] }",
        ]
        if req.hint:
            pieces.append(f"HINT: {req.hint}")
        if req.text:
            pieces.append(f"CONTEXT:\n{req.text[:80000]}")
        vision_segment = ""
        if req.image_urls and vision_adapter.is_enabled():
            try:
                imgs = await vision_adapter.prepare_images(req.image_urls)
                vision_segment = await vision_adapter.build_enhanced_prompt_segment(imgs, mode="diagrams")
            except Exception as ve:
                logger.debug(f"Vision enrichment failed (diagrams): {ve}")
        if vision_segment:
            pieces.append(vision_segment)
        elif req.image_urls:
            pieces.append("IMAGES (listing only, vision disabled):\n" + "\n".join(req.image_urls[:10]))
        prompt = "\n\n".join(pieces)

        async with _vision_sem:
            if _FAKE_MODE:
                fake = {"entities": [{"name": "Server", "type": "Component"}], "relationships": []}
                return MultimodalResponse(success=True, data=fake)
            resp_text = await llm_processor.process_llm_request(
                process_type=LLMProcessType.DIAGRAM_UNDERSTANDING.value,
                prompt=prompt,
                project_id=req.project_id,
                corr_id=corr_id,
                allow_global=not enforce,
            )
            try:
                data = json.loads(resp_text)
                if not isinstance(data, dict):
                    data = {"entities": data if isinstance(data, list) else [], "relationships": []}
            except Exception:
                import re
                m = re.search(r"\{[\s\S]*\}$", (resp_text or "").strip())
                data = json.loads(m.group(0)) if m else {"raw": resp_text}
            if not is_valid_diagram_payload(data):
                data = {"entities": [], "relationships": [], "raw": data}
            return MultimodalResponse(success=True, data=data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Diagram understanding failed: {e}")
        return MultimodalResponse(success=False, data={}, error=str(e))

@router.post("/test-llm-config", summary="Test LLM configuration")
async def test_llm_config(request: TestLLMConfigRequest):
    """Test LLM configuration by making a real API call"""
    try:
        # Use the processor to test the configuration
        provider = request.provider
        model = request.model
        api_key = request.api_key
        
        # If config_id is provided, fetch the configuration
        if request.config_id and not api_key:
            configs = await llm_processor.get_configurations()
            if request.config_id in configs:
                saved_config = configs[request.config_id]
                api_key = saved_config.get('api_key')
                provider = saved_config.get('provider', provider)
                model = saved_config.get('model', model)
        
        # Validate API key
        if not api_key or api_key.strip() == '':
            return {
                "status": "error",
                "message": f"No API key provided for {provider} provider. Please ensure the configuration has a valid API key.",
                "provider": provider,
                "model": model,
                "query": request.query
            }
        
        # Instantiate and test the LLM
        provider_config = llm_processor._provider_configs.get(provider.lower())
        if not provider_config or not provider_config['class']:
            return {
                "status": "error",
                "message": f"Provider {provider} is not supported or not available",
                "provider": provider,
                "model": model,
                "query": request.query
            }
        
        llm = llm_processor._instantiate_llm(
            provider=provider.lower(),
            llm_class=provider_config['class'],
            model=model,
            api_key=api_key,
            temperature=request.temperature or 0.1,
            max_tokens=request.max_tokens or 100
        )
        
        # Test with the query
        if provider.lower() == 'ollama':
            # Special handling for Ollama
            response = llm.invoke(request.query)
        else:
            # For other providers, use standard invoke
            from langchain.schema import HumanMessage
            response = llm.invoke([HumanMessage(content=request.query)])
            response = response.content if hasattr(response, 'content') else str(response)
        
        return {
            "status": "success",
            "provider": provider,
            "model": model,
            "query": request.query,
            "response": response,
            "echo": response,
            "timestamp": "current"
        }
        
    except Exception as e:
        logger.error(f"LLM config test failed: {e}")
        return {
            "status": "error",
            "message": f"LLM config test failed: {str(e)}",
            "provider": request.provider,
            "model": request.model,
            "query": request.query
        }
