"""
Vector Search API Routes (Weaviate)
FastAPI router for vector operations using Weaviate as the vector store.
"""

import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Query
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import time
from weaviate.classes.query import Filter
import os
import httpx

from ..core.vector_processor import VectorProcessor, get_vector_processor
from ..core.entity_resolution import cluster_entity_cards

logger = logging.getLogger("vector-service.router")

# Initialize processor
processor = VectorProcessor()

# Create router
router = APIRouter(tags=["vectors"])

# ----------------------- Bulk Embeddings (B2 Scaffold) -----------------------
class BulkEmbeddingsRequest(BaseModel):
    project_id: Optional[str] = None
    texts: List[str] = Field(..., min_length=1, description="List of texts to embed")
    model: Optional[str] = Field(None, description="Optional model override (future use)")
    force_refresh: Optional[bool] = False

class BulkEmbeddingsResponse(BaseModel):
    success: bool
    embeddings: List[List[float]]
    model: Optional[str] = None
    batch_size: int
    cached: int
    generated: int
    cache_enabled: bool
    metrics: Dict[str, Any]
    error: Optional[str] = None

_bulk_embed_metrics = {
    "requests": 0,
    "batches": 0,
    "cache_hits": 0,
    "cache_misses": 0,
    "total_texts": 0,
    "evictions": 0,
    "force_refreshes": 0,
    "model_load_latency_ms": 0.0,
}

class _LRUTTLEntry:
    __slots__ = ("vec", "ts")
    def __init__(self, vec: List[float], ts: float):
        self.vec = vec
        self.ts = ts

_bulk_cache: Dict[str, _LRUTTLEntry] = {}
_bulk_cache_order: List[str] = []  # simple list to track LRU order (front = most recent)

def _embed_cache_max_entries() -> int:
    return int(os.getenv("EMBED_CACHE_MAX_ENTRIES", "2048") or 2048)

def _embed_cache_ttl_seconds() -> float:
    return float(os.getenv("EMBED_CACHE_TTL_SECONDS", "3600") or 3600)

def _cache_get(key: str) -> Optional[List[float]]:
    ent = _bulk_cache.get(key)
    if not ent:
        return None
    # TTL check
    if (time.time() - ent.ts) > _embed_cache_ttl_seconds():
        # expired
        try:
            del _bulk_cache[key]
            _bulk_cache_order.remove(key)
        except Exception:
            pass
        return None
    # Move to front for LRU (most recent)
    try:
        _bulk_cache_order.remove(key)
    except ValueError:
        pass
    _bulk_cache_order.insert(0, key)
    return ent.vec

def _cache_set(key: str, vec: List[float]):
    _bulk_cache[key] = _LRUTTLEntry(vec, time.time())
    try:
        _bulk_cache_order.remove(key)
    except ValueError:
        pass
    _bulk_cache_order.insert(0, key)
    # Evict if over capacity
    cap = _embed_cache_max_entries()
    if len(_bulk_cache_order) > cap:
        lru_key = _bulk_cache_order.pop()  # oldest
        try:
            del _bulk_cache[lru_key]
        except KeyError:
            pass
        _bulk_embed_metrics["evictions"] += 1

def _bulk_cache_enabled() -> bool:
    return str(os.getenv("EMBED_CACHE_ENABLED", "true")).lower() in ("1","true","yes","on")

def _embed_batch_cap() -> int:
    return int(os.getenv("EMBED_BATCH_MAX", "32"))

async def _real_embed(texts: List[str], model_override: Optional[str] = None) -> List[List[float]]:
    # Use underlying vector processor's sentence transformer (async lazy load)
    # We reuse the global processor instance already created (processor variable)
    from ..core.vector_processor import get_sentence_transformer_async
    t0 = time.perf_counter()
    st_model = await get_sentence_transformer_async()
    load_latency = (time.perf_counter() - t0) * 1000
    if _bulk_embed_metrics["model_load_latency_ms"] == 0.0:
        _bulk_embed_metrics["model_load_latency_ms"] = round(load_latency, 2)
    # Encode (SentenceTransformer handles batching internally but we could chunk if needed)
    emb = st_model.encode(texts, convert_to_numpy=False, show_progress_bar=False)  # type: ignore
    # Ensure list of lists (floats)
    return [list(map(float, v)) for v in emb]

@router.post("/bulk-embeddings", response_model=BulkEmbeddingsResponse, summary="Batch embedding generation with LRU+TTL cache")
async def bulk_embeddings(req: BulkEmbeddingsRequest):
    try:
        cap = _embed_batch_cap()
        if len(req.texts) > cap:
            raise HTTPException(status_code=400, detail=f"Batch size {len(req.texts)} exceeds EMBED_BATCH_MAX={cap}")
        cache_enabled = _bulk_cache_enabled()
        force_refresh = bool(req.force_refresh)
        _bulk_embed_metrics["requests"] += 1
        _bulk_embed_metrics["total_texts"] += len(req.texts)
        embeddings: List[List[float]] = []
        cached = 0
        generated = 0
        if force_refresh:
            _bulk_embed_metrics["force_refreshes"] += 1
        # First collect which need generation
        to_generate: List[Tuple[int, str]] = []
        for idx, t in enumerate(req.texts):
            key = f"{req.model or 'default'}|{hash(t)}"
            vec = None
            if not force_refresh and cache_enabled:
                vec = _cache_get(key)
            if vec is not None:
                cached += 1
                _bulk_embed_metrics["cache_hits"] += 1
                embeddings.append(vec)
            else:
                _bulk_embed_metrics["cache_misses"] += 1
                embeddings.append([])  # placeholder to fill after generation
                to_generate.append((idx, t))
        if to_generate:
            # Generate in one batch for efficiency
            gen_texts = [t for _, t in to_generate]
            gen_vectors = await _real_embed(gen_texts, req.model)
            for (slot_idx, _), vec in zip(to_generate, gen_vectors):
                embeddings[slot_idx] = vec
                generated += 1
                if cache_enabled:
                    key = f"{req.model or 'default'}|{hash(req.texts[slot_idx])}"
                    _cache_set(key, vec)
        _bulk_embed_metrics["batches"] += 1
        return BulkEmbeddingsResponse(
            success=True,
            embeddings=embeddings,
            model=req.model or "default",
            batch_size=len(req.texts),
            cached=cached,
            generated=generated,
            cache_enabled=cache_enabled,
            metrics=dict(_bulk_embed_metrics),
        )
    except HTTPException:
        raise
    except Exception as e:
        return BulkEmbeddingsResponse(success=False, embeddings=[], model=req.model, batch_size=0, cached=0, generated=0, cache_enabled=_bulk_cache_enabled(), metrics=dict(_bulk_embed_metrics), error=str(e))

# Add cleanup endpoint
@router.post("/cleanup", summary="Cleanup connections")
async def cleanup_connections():
    """Cleanup database connections to prevent resource warnings"""
    try:
        processor.cleanup()
        return {
            "status": "success",
            "message": "Connections cleaned up successfully"
        }
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")

# Context manager for operations that need connection cleanup
async def with_vector_processor(operation_func, *args, **kwargs):
    """Execute operation with proper connection management"""
    with VectorProcessor() as vp:
        return await operation_func(vp, *args, **kwargs)

# Pydantic models for request/response
class DocumentInput(BaseModel):
    id: Optional[str] = None
    content: str = Field(..., min_length=1, description="Document content to embed")
    filename: Optional[str] = "unknown"
    source: Optional[str] = "api"
    # Optional chunk index to preserve ordering/position from upstream chunkers
    chunk_index: Optional[int] = 0

class AddDocumentsRequest(BaseModel):
    documents: List[DocumentInput] = Field(..., min_length=1)

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query")
    limit: int = Field(default=10, ge=1, le=100, description="Maximum number of results")
    include_metadata: bool = Field(default=True, description="Include document metadata")

class HybridSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query")
    limit: int = Field(default=10, ge=1, le=100, description="Maximum number of results")
    semantic_weight: float = Field(default=0.7, ge=0.0, le=1.0, description="Weight for semantic vs keyword search")

class SearchResponse(BaseModel):
    query: str
    results: List[Dict[str, Any]]
    total_found: int
    collection_name: str
    search_timestamp: str

class CollectionResponse(BaseModel):
    collection_name: str
    document_count: int

# New models for structured document processing
class StructuredDocumentElement(BaseModel):
    element_id: str
    content: str
    element_type: str
    page_number: Optional[int] = None
    hierarchy_level: Optional[int] = None
    semantic_tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None

class ProcessStructuredRequest(BaseModel):
    documents: List[StructuredDocumentElement] = Field(..., min_length=1)
    processing_type: str = Field(default="structured", description="Type of processing")
    source: str = Field(default="document-service", description="Source of the request")
    chunking_strategy: str = Field(default="element_based", description="smart_element, element_based, or traditional")

class ProcessStructuredResponse(BaseModel):
    status: str
    elements_processed: int
    embeddings_created: int
    processing_time_seconds: float
    chunking_strategy: str
    chunks_created: int
    status: str

class HealthResponse(BaseModel):
    weaviate_connected: bool
    weaviate_classes: int
    redis_connected: bool
    status: str

# --- Entity Resolution Models ---
class EntityResolutionRequest(BaseModel):
    similarity_threshold: float = Field(0.82, ge=0.5, le=0.99, description="Cosine similarity threshold for clustering")
    max_cards: int = Field(2000, ge=10, le=20000, description="Safety cap on number of entity cards to fetch/cluster")

class EntityClusterMember(BaseModel):
    index: int
    filename: Optional[str] = None
    chunk_index: Optional[int] = None
    content_preview: str

class EntityCluster(BaseModel):
    cluster_id: int
    canonical_index: int
    canonical_content_preview: str
    size: int
    members: List[EntityClusterMember]

class EntityResolutionResponse(BaseModel):
    project_id: str
    clusters: List[EntityCluster]
    stats: Dict[str, Any]
    similarity_threshold: float
    status: str

@router.post("/entity-resolution", response_model=EntityResolutionResponse, summary="Entity resolution clustering (scaffold)")
async def entity_resolution(req: EntityResolutionRequest, project_id: Optional[str] = None):
    """Phase C Scaffold: cluster entity cards using existing helper (placeholder).

    Currently fetches limited entity cards (placeholder retrieval) and applies cosine threshold clustering
    via `cluster_entity_cards` if available. Retrieval integration with vector store / graph to be added.
    """
    try:
        # Placeholder: fetch top N raw chunk vectors (future: entity_cards collection)
        # For now, simulate with empty list -> returns empty clusters
        cards: List[Dict[str, Any]] = []
        clusters, stats = cluster_entity_cards(cards, threshold=req.similarity_threshold) if callable(cluster_entity_cards) else ([], {"note": "cluster function unavailable"})
        resp_clusters: List[EntityCluster] = []
        for idx, c in enumerate(clusters):
            members = [EntityClusterMember(index=m.get("index", i), filename=m.get("filename"), chunk_index=m.get("chunk_index"), content_preview=(m.get("content") or "")[:120]) for i, m in enumerate(c.get("members", []))]
            resp_clusters.append(EntityCluster(
                cluster_id=idx,
                canonical_index=c.get("canonical_index", 0),
                canonical_content_preview=(c.get("canonical_content") or "")[:160],
                size=len(members),
                members=members,
            ))
        return EntityResolutionResponse(
            project_id=project_id or "unknown",
            clusters=resp_clusters,
            stats=stats,
            similarity_threshold=req.similarity_threshold,
            status="success",
        )
    except Exception as e:
        logger.error(f"Entity resolution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class VectorMetricsResponse(BaseModel):
    project_id: str
    total_vectors: int
    counts_by_kind: Dict[str, int]
    timestamp: str
    status: str

# -------------------- Cards Generation (Phase C3 Scaffold) --------------------
class GenerateCardsRequest(BaseModel):
    max_raw_chunks: int = Field(1500, ge=10, le=10000, description="Safety cap on raw_chunks to scan")
    entity_min_occurrences: int = Field(2, ge=1, le=50, description="Minimum occurrences to promote candidate entity card")
    triple_pattern: str = Field(r"([A-Z][A-Za-z0-9_]{2,})\s+is\s+([A-Z][A-Za-z0-9_]{2,})", description="Regex for naive triple extraction 'X is Y'")
    force: bool = Field(False, description="Force generation even if pipeline flag disabled (service auth contexts)")
    regen_key: Optional[str] = Field(None, description="Optional regeneration key to bust previous run cache")

class GenerateCardsResponse(BaseModel):
    project_id: str
    entity_cards_created: int
    triple_cards_created: int
    entity_candidates: int
    triple_candidates: int
    elapsed_ms: float
    status: str
    notes: Optional[str] = None
    params: Dict[str, Any]
    weighting_stats: Optional[Dict[str, Any]] = None

def _build_entity_and_triple_cards(raw_texts: List[str], entity_min_occurrences: int, triple_pattern: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    """Derive entity and triple cards with frequency+dispersion weighting (Phase C3 → Phase 2 upgrade).

    Upgrades:
      - Compute occurrences per entity AND number of distinct raw chunks containing it (dispersion).
      - Weighting formula: weight = occurrences * (1 + 0.35 * log10(1 + dispersion)).
      - Store metadata block in card content for downstream summarization.
      - Return weighting stats (min/max/avg weight, retained entities).

    Triple heuristic unchanged (regex pattern 'X is Y').
    """
    import re, math
    entity_counts: Dict[str, int] = {}
    entity_chunk_spans: Dict[str, int] = {}
    token_re = re.compile(r"\b([A-Z][A-Za-z0-9_]{2,})\b")
    for idx, txt in enumerate(raw_texts):
        seen_this_chunk = set()
        for m in token_re.finditer(txt or ""):
            tok = m.group(1)
            if tok.upper() == tok:  # skip ALLCAPS
                continue
            entity_counts[tok] = entity_counts.get(tok, 0) + 1
            if tok not in seen_this_chunk:
                entity_chunk_spans[tok] = entity_chunk_spans.get(tok, 0) + 1
                seen_this_chunk.add(tok)
    entity_cards: List[Dict[str, Any]] = []
    weights: List[float] = []
    for ent, cnt in entity_counts.items():
        if cnt < entity_min_occurrences:
            continue
        dispersion = entity_chunk_spans.get(ent, 1)
        weight = cnt * (1.0 + 0.35 * math.log10(1 + dispersion))
        weights.append(weight)
        meta_block = (
            f"Entity: {ent}\n"
            f"Occurrences: {cnt}\n"
            f"DispersionChunks: {dispersion}\n"
            f"WeightedScore: {weight:.4f}\n"
            "Summary: Placeholder summary for {ent} (Phase C3+ weighting)."
        )
        entity_cards.append({
            "content": meta_block,
            "filename": f"entity_card_{ent}.txt",
            "source": "entity_cards",
            "weight": weight,
            "occurrences": cnt,
            "dispersion_chunks": dispersion,
        })
    # Triples (same as before)
    trip_re = re.compile(triple_pattern)
    seen_triples = set()
    triple_cards: List[Dict[str, Any]] = []
    for txt in raw_texts:
        for m in trip_re.finditer(txt or ""):
            subj, obj = m.group(1), m.group(2)
            key = (subj, obj)
            if key in seen_triples:
                continue
            seen_triples.add(key)
            snippet = txt[max(0, m.start()-60):m.end()+60]
            triple_cards.append({
                "content": f"Triple: {subj} is {obj}\nEvidence: {snippet[:400]}",
                "filename": f"triple_card_{subj}_{obj}.txt",
                "source": "triple_cards",
            })
    stats = {
        "entity_candidate_tokens": len(entity_counts),
        "entity_cards_retained": len(entity_cards),
        "triple_candidates": len(seen_triples),
        "weight_min": round(min(weights),4) if weights else 0.0,
        "weight_max": round(max(weights),4) if weights else 0.0,
        "weight_avg": round(sum(weights)/len(weights),4) if weights else 0.0,
    }
    return entity_cards, triple_cards, stats

# Allowed kinds for multi-embedding collections
KIND_VALUES = {"raw_chunks", "entity_cards", "triple_cards"}

# -------------------- Fusion Search (Phase C2 Scaffold) --------------------
class FusionSearchRequest(BaseModel):
    query: str = Field(..., min_length=2, description="User query text")
    top_k: int = Field(12, ge=1, le=50, description="Final fused results to return")
    per_kind_k: int = Field(25, ge=2, le=100, description="Initial per-kind candidate cap before fusion")
    kinds: Optional[List[str]] = Field(None, description="Subset of kinds to include (defaults to all kinds)")
    rrf_k: int = Field(60, ge=10, le=300, description="Reciprocal Rank Fusion constant k")
    include_metadata: bool = Field(True, description="Return metadata for each result")

class FusionResult(BaseModel):
    doc_id: str
    content_preview: str
    kinds: List[str]
    rrf_score: float
    primary_kind: str
    source: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class CitationPreviewResponse(BaseModel):
    project_id: str
    doc_id: str
    snippet: str
    score_components: Dict[str, Any]
    attribution_score: float
    source_metadata: Optional[Dict[str, Any]] = None
    timestamp: str

@router.get("/projects/{project_id}/citations/preview", response_model=CitationPreviewResponse, summary="Preview citation snippet and attribution score")
async def citation_preview(project_id: str, doc_id: str, window: int = Query(320, ge=60, le=1200)):
    """Return a best-effort preview snippet & lightweight attribution score for a fused doc_id.

    The doc_id encodes (filename, chunk_index, hash preview) produced by fusion_search. We approximate
    retrieval by querying each kind with filename and matching hash of first 80 chars.
    Attribution score = 0.6*length_factor + 0.4*(kind_diversity/3).
    """
    if os.getenv("FUSION_ENABLED", "false").lower() not in {"1","true","yes","on"}:
        raise HTTPException(status_code=403, detail="Fusion feature disabled")
    try:
        parts = doc_id.split(":")
        filename = parts[0] if parts else "unknown"
        import asyncio
        async def fetch_kind(kind: str):
            try:
                res = await processor.similarity_search_by_kind(project_id, kind, filename, limit=12, include_metadata=True)
                return kind, res.get("results", [])
            except Exception:
                return kind, []
        results = await asyncio.gather(*[fetch_kind(k) for k in KIND_VALUES])
        candidates = []
        for kind, items in results:
            for it in items:
                content = it.get("content") or ""
                h = str(hash(content[:80]))
                if doc_id.endswith(h):
                    candidates.append((kind, it))
        chosen_kind, chosen_item = candidates[0] if candidates else (None, None)
        snippet = ""
        meta = None
        if chosen_item:
            meta = chosen_item.get("metadata") if isinstance(chosen_item.get("metadata"), dict) else {}
            full = chosen_item.get("content") or ""
            snippet = full[:window]
        diversity = len({k for k,_ in candidates})
        length_factor = min(1.0, len(snippet)/float(window)) if snippet else 0.0
        attribution = round((0.6 * length_factor) + (0.4 * (diversity/3.0)), 4)
        return CitationPreviewResponse(
            project_id=project_id,
            doc_id=doc_id,
            snippet=snippet,
            score_components={
                "diversity_kinds": diversity,
                "length_factor": length_factor,
                "matched_candidates": len(candidates),
                "chosen_kind": chosen_kind,
            },
            attribution_score=attribution,
            source_metadata=meta,
            timestamp=datetime.utcnow().isoformat(),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Citation preview failed for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Citation preview failed")

class FusionSearchResponse(BaseModel):
    project_id: str
    query: str
    results: List[FusionResult]
    retrieval_stats: Dict[str, Any]
    timestamp: str
    status: str


# Health check endpoint
@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Check if vector service is healthy"""
    try:
        health_info = await processor.health_check()
        return HealthResponse(**health_info)
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

# Model warm-up endpoint for optimized startup
@router.post("/warm-up")
async def warm_up_models(background_tasks: BackgroundTasks):
    """Warm up AI models in background to reduce first request latency"""
    try:
        # Check if models are already loaded
        model_status = {
            "embedding_model_loaded": processor._embedding_model is not None,
            "warm_up_started": False
        }
        
        # Start background model loading if not already loaded
        if not processor._embedding_model:
            background_tasks.add_task(warm_up_models_background)
            model_status["warm_up_started"] = True
            logger.info("Started background model warm-up")
        
        return {
            "status": "success",
            "message": "Model warm-up initiated" if model_status["warm_up_started"] else "Models already loaded",
            **model_status
        }
    except Exception as e:
        logger.error(f"Model warm-up failed: {e}")
        raise HTTPException(status_code=500, detail=f"Model warm-up failed: {str(e)}")

@router.get("/model-status")
async def get_model_status():
    """Get current model loading status"""
    try:
        from ..core.vector_processor import _sentence_transformer, _model_loading
        
        return {
            "embedding_model_loaded": processor._embedding_model is not None,
            "global_model_loaded": _sentence_transformer is not None,
            "model_loading_in_progress": _model_loading,
            "service_ready": True
        }
    except Exception as e:
        logger.error(f"Failed to get model status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get model status: {str(e)}")

# Collection management endpoints
@router.post("/projects/{project_id}/collection", response_model=CollectionResponse)
async def create_collection(project_id: str):
    """Prepare project in Weaviate (no physical collection) and return counts"""
    try:
        result = await processor.create_collection(project_id)
        return CollectionResponse(**result)
    except Exception as e:
        logger.error(f"Failed to create collection for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create collection: {str(e)}")

@router.get("/projects/{project_id}/collection", response_model=CollectionResponse)
async def get_collection_info(project_id: str):
    """Get information about a project's vector set in Weaviate"""
    try:
        result = await processor.get_collection_info(project_id)
        return CollectionResponse(**result)
    except Exception as e:
        logger.error(f"Failed to get collection info for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get collection info: {str(e)}")

@router.get("/projects/{project_id}/metrics", response_model=VectorMetricsResponse, summary="Vector metrics (counts per kind and total)")
async def get_vector_metrics(project_id: str):
    """Return aggregate counts of vectors per logical kind (raw_chunks, entity_cards, triple_cards) plus total.

    Implementation note: Uses fetch_objects with a high limit per kind. For large-scale production consider
    replacing with Weaviate aggregate queries once available for combined filters in v4 client.
    """
    start_time = time.time()
    try:
        col = processor.wclient.collections.get("DocumentChunk")
        counts: Dict[str, int] = {}
        total = 0
        for kind in sorted(KIND_VALUES):
            project_filter = Filter.by_property("project_id").equal(project_id)
            kind_filter = Filter.by_property("source").equal(kind)
            combined = project_filter & kind_filter
            try:
                res = col.query.fetch_objects(limit=15000, filters=combined, return_properties=["project_id", "source"])  # safety cap
                kcount = len(res.objects or [])
            except Exception:
                kcount = 0
            counts[kind] = kcount
            total += kcount
        resp = VectorMetricsResponse(
            project_id=project_id,
            total_vectors=total,
            counts_by_kind=counts,
            timestamp=datetime.utcnow().isoformat(),
            status="ok",
        )
        duration = time.time() - start_time
        logger.info(f"vector_metrics project={project_id} total={total} duration_sec={duration:.3f}")
        return resp
    except Exception as e:
        logger.error(f"Failed to get metrics for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get vector metrics: {str(e)}")

_LAST_GENERATION_SIGNATURE: Dict[str, str] = {}

def _cards_generation_signature(project_id: str, max_raw: int, entity_min: int, triple_pattern: str, regen_key: Optional[str]) -> str:
    base = f"{project_id}|{max_raw}|{entity_min}|{triple_pattern}|{regen_key or ''}"
    return str(hash(base))

@router.post("/projects/{project_id}/generate-cards", response_model=GenerateCardsResponse, summary="Generate entity & triple cards from raw_chunks (Phase C3 scaffold + weighting v2)")
async def generate_cards(project_id: str, req: GenerateCardsRequest):
    if os.getenv("ENABLE_CARDS_PIPELINE", "false").lower() not in {"1","true","yes","on"} and not req.force:
        raise HTTPException(status_code=403, detail="Cards pipeline disabled. Set ENABLE_CARDS_PIPELINE=true to enable.")
    t0 = time.perf_counter()
    try:
        # Regeneration key handling
        env_regen_default = os.getenv("REGENERATE_CARDS_KEY")
        effective_regen_key = req.regen_key or env_regen_default
        sig = _cards_generation_signature(project_id, req.max_raw_chunks, req.entity_min_occurrences, req.triple_pattern, effective_regen_key)
        last_sig = _LAST_GENERATION_SIGNATURE.get(project_id)
        if (not req.force) and last_sig == sig:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            return GenerateCardsResponse(
                project_id=project_id,
                entity_cards_created=0,
                triple_cards_created=0,
                entity_candidates=0,
                triple_candidates=0,
                elapsed_ms=round(elapsed_ms,2),
                status="skipped",
                notes="Generation skipped (signature unchanged; use force=true or new regen_key to regenerate)",
                params=req.dict(),
            )
        col = processor.wclient.collections.get("DocumentChunk")
        proj_filter = Filter.by_property("project_id").equal(project_id)
        raw_filter = Filter.by_property("source").equal("raw_chunks")
        combined = proj_filter & raw_filter
        res = col.query.fetch_objects(limit=req.max_raw_chunks, filters=combined, return_properties=["content","filename","chunk_index","source"])
        objs = res.objects or []
        raw_texts = []
        for o in objs:
            props = o.properties or {}
            raw_texts.append(props.get("content") or "")
        entity_cards, triple_cards, stats = _build_entity_and_triple_cards(raw_texts, req.entity_min_occurrences, req.triple_pattern)
        # Persist cards as vectors (embedding generation delegated to add_documents)
        docs: List[Dict[str, Any]] = []
        for ec in entity_cards:
            # Preserve weighting metadata in metadata map for downstream analytics / retrieval
            docs.append({
                "content": ec["content"],
                "filename": ec["filename"],
                "source": "entity_cards",
                "chunk_index": 0,
                "metadata": {
                    "weight": ec.get("weight"),
                    "occurrences": ec.get("occurrences"),
                    "dispersion_chunks": ec.get("dispersion_chunks"),
                },
            })
        for tc in triple_cards:
            docs.append({"content": tc["content"], "filename": tc["filename"], "source": "triple_cards", "chunk_index": 0})
        added = 0
        if docs:
            add_res = await processor.add_documents(project_id, docs)
            added = int(add_res.get("added_count", 0))
        elapsed_ms = (time.perf_counter() - t0) * 1000
        resp = GenerateCardsResponse(
            project_id=project_id,
            entity_cards_created=len(entity_cards),
            triple_cards_created=len(triple_cards),
            entity_candidates=stats.get("entity_candidate_tokens", 0),
            triple_candidates=stats.get("triple_candidates", 0),
            elapsed_ms=round(elapsed_ms,2),
            status="success",
            notes=f"Inserted {added} new card vectors (entity+triple)",
            params=req.dict(),
            weighting_stats={
                "entity_cards_retained": stats.get("entity_cards_retained"),
                "weight_min": stats.get("weight_min"),
                "weight_max": stats.get("weight_max"),
                "weight_avg": stats.get("weight_avg"),
            },
        )
        _LAST_GENERATION_SIGNATURE[project_id] = sig
        # Emit analytics ingest (best-effort)
        try:
            ingest_url = os.getenv("ANALYTICS_SERVICE_URL", "http://localhost:8014") + "/ingest"
            payload = {
                "source": "vector-service",
                "project_id": project_id,
                "metrics": {
                    "cards_pipeline": {
                        "entity_cards_created": len(entity_cards),
                        "triple_cards_created": len(triple_cards),
                        "entity_candidates": stats.get("entity_candidate_tokens", 0),
                        "triple_candidates": stats.get("triple_candidates", 0),
                        "weight_min": stats.get("weight_min"),
                        "weight_max": stats.get("weight_max"),
                        "weight_avg": stats.get("weight_avg"),
                        "elapsed_ms": round(elapsed_ms,2),
                    }
                }
            }
            import asyncio, httpx
            async def _post_ingest():
                async with httpx.AsyncClient(timeout=2.5) as client:
                    await client.post(ingest_url, json=payload)
            # Fire and forget
            asyncio.create_task(_post_ingest())
        except Exception:
            pass
        return resp
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Card generation failed for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Card generation failed: {str(e)}")

@router.post("/projects/{project_id}/fusion/search", response_model=FusionSearchResponse, summary="Multi-kind fusion search with RRF (Phase C2 scaffold)")
async def fusion_search(project_id: str, req: FusionSearchRequest):
    """Perform multi-kind retrieval and fuse with Reciprocal Rank Fusion.

    Notes:
      - Uses similarity_search_by_kind internally (semantic only baseline)
      - Dedupes by (filename, chunk_index, first 80 chars hash)
      - Emits optional analytics ingest event (best-effort)
      - Governed by FUSION_ENABLED env flag
    """
    if os.getenv("FUSION_ENABLED", "false").lower() not in {"1","true","yes","on"}:
        raise HTTPException(status_code=403, detail="Fusion feature disabled. Set FUSION_ENABLED=true to enable.")
    try:
        kinds_all = sorted(KIND_VALUES)
        kinds = [k for k in (req.kinds or kinds_all) if k in kinds_all]
        if not kinds:
            kinds = kinds_all
        # Gather per-kind candidates
        import asyncio
        async def fetch_kind(kind: str):
            try:
                res = await processor.similarity_search_by_kind(project_id, kind, req.query, limit=req.per_kind_k, include_metadata=req.include_metadata)
                return kind, res.get("results", [])
            except Exception:
                return kind, []
        fetch_results = await asyncio.gather(*[fetch_kind(k) for k in kinds])
        by_kind = {k: items for k, items in fetch_results}
        # RRF fusion with optional hybrid lexical + centrality augmentation
        rrf_k = req.rrf_k
        fused: Dict[str, Dict[str, Any]] = {}
        candidate_counts: Dict[str, int] = {}
        hybrid_enabled = os.getenv("FUSION_HYBRID_ENABLED", "false").lower() in {"1","true","yes","on"}
        # Precompute query term set for lexical approximation (simple IDF-less BM25 variant)
        import re, math
        q_terms = [t for t in re.split(r"[^a-z0-9]+", req.query.lower()) if t and len(t) > 2]
        q_term_set = set(q_terms)
        # Centrality map (optional) fetched once if enabled
        centrality_map: Dict[str, float] = {}
        if hybrid_enabled:
            try:
                graph_url = os.getenv("GRAPH_SERVICE_URL", "http://localhost:8006")
                async with httpx.AsyncClient(timeout=3.0) as client:
                    rcent = await client.get(f"{graph_url}/api/graphs/projects/{project_id}/canonical/centrality?limit=1000")
                    if rcent.status_code == 200:
                        for item in rcent.json().get("items", []):
                            nm = (item.get("name") or "").lower()
                            centrality_map[nm] = float(item.get("normalized_total_degree") or 0.0)
            except Exception:
                pass
        for kind, items in by_kind.items():
            candidate_counts[kind] = len(items)
            for rank, item in enumerate(items):
                # Build stable key
                md = item.get("metadata") or {}
                fname = md.get("filename") or "unknown"
                cidx = md.get("chunk_index")
                preview = (item.get("content") or "")[:80]
                key = f"{fname}:{cidx}:{hash(preview)}"
                score = 1.0 / (rrf_k + rank + 1)
                ent = fused.setdefault(key, {"doc_id": key, "kinds": set(), "rrf_score": 0.0, "payload": item, "primary_kind": kind, "lexical_score": 0.0, "centrality": 0.0})
                ent["rrf_score"] += score
                ent["kinds"].add(kind)
                if hybrid_enabled:
                    content = (item.get("content") or "").lower()
                    tokens = [t for t in re.split(r"[^a-z0-9]+", content) if t]
                    if tokens:
                        # Simple BM25-ish: term frequency normalization only
                        tf_sum = 0.0
                        for qt in q_term_set:
                            tf = tokens.count(qt)
                            if tf:
                                tf_sum += (tf / (tf + 1.5))  # dampen
                        ent["lexical_score"] += tf_sum
                    # Centrality boost if file base name matches an entity name segment
                    base_name = os.path.splitext(os.path.basename(fname))[0].lower()
                    ent["centrality"] = max(ent["centrality"], centrality_map.get(base_name, 0.0))
        fused_list = list(fused.values())
        if hybrid_enabled:
            # Normalize lexical & centrality
            max_lex = max((f["lexical_score"] for f in fused_list), default=1.0)
            max_cen = max((f["centrality"] for f in fused_list), default=1.0)
            for f in fused_list:
                f["lexical_norm"] = (f["lexical_score"] / max_lex) if max_lex else 0.0
                f["centrality_norm"] = (f["centrality"] / max_cen) if max_cen else 0.0
                # Blend weights (env configurable)
                alpha = float(os.getenv("FUSION_WEIGHT_RRF", "0.6"))
                beta = float(os.getenv("FUSION_WEIGHT_LEX", "0.25"))
                gamma = float(os.getenv("FUSION_WEIGHT_CENTRALITY", "0.15"))
                f["hybrid_score"] = (
                    alpha * f["rrf_score"] +
                    beta * f["lexical_norm"] +
                    gamma * f["centrality_norm"]
                )
            fused_list.sort(key=lambda x: x["hybrid_score"], reverse=True)
        else:
            fused_list.sort(key=lambda x: x["rrf_score"], reverse=True)
        top = fused_list[: req.top_k]
        results: List[FusionResult] = []
        for f in top:
            payload = f.get("payload", {})
            md = payload.get("metadata") if req.include_metadata else None
            results.append(FusionResult(
                doc_id=f["doc_id"],
                content_preview=(payload.get("content") or "")[:300],
                kinds=sorted(list(f["kinds"])),
                rrf_score=round(f["rrf_score"], 6),
                primary_kind=f.get("primary_kind"),
                source=(md or {}).get("source") if isinstance(md, dict) else None,
                metadata=md,
            ))
        dedupe_ratio = 0.0
        total_initial = sum(candidate_counts.values())
        if total_initial > 0:
            dedupe_ratio = 1 - (len(fused_list) / total_initial)
        retrieval_stats = {
            "candidate_counts": candidate_counts,
            "fused_candidates": len(fused_list),
            "returned": len(results),
            "rrf_k": rrf_k,
            "dedupe_ratio": round(dedupe_ratio, 4),
            "hybrid_enabled": hybrid_enabled,
        }
        if hybrid_enabled:
            retrieval_stats["weights"] = {
                "rrf": os.getenv("FUSION_WEIGHT_RRF", "0.6"),
                "lexical": os.getenv("FUSION_WEIGHT_LEX", "0.25"),
                "centrality": os.getenv("FUSION_WEIGHT_CENTRALITY", "0.15"),
            }
        # Emit analytics ingest (best-effort)
        try:
            analytics_url = os.getenv("ANALYTICS_SERVICE_URL", "http://localhost:8014")
            headers = {"Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"}
            payload = {"source": "vector-service", "project_id": project_id, "metrics": {"fusion": retrieval_stats}}
            async with httpx.AsyncClient(timeout=2.5) as client:
                await client.post(f"{analytics_url}/ingest", json=payload, headers=headers)
        except Exception:
            pass
        return FusionSearchResponse(
            project_id=project_id,
            query=req.query,
            results=results,
            retrieval_stats=retrieval_stats,
            timestamp=datetime.utcnow().isoformat(),
            status="success",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fusion search failed for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Fusion search failed: {str(e)}")

@router.delete("/projects/{project_id}/collection", response_model=CollectionResponse)
async def delete_collection(project_id: str):
    """Delete a project's vectors from Weaviate"""
    try:
        result = await processor.delete_collection(project_id)
        return CollectionResponse(**result)
    except Exception as e:
        logger.error(f"Failed to delete collection for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete collection: {str(e)}")

# Document management endpoints
@router.post("/projects/{project_id}/documents")
async def add_documents(
    project_id: str, 
    request: AddDocumentsRequest,
    background_tasks: BackgroundTasks
):
    """Add documents to Weaviate with background embedding generation"""
    try:
        # Convert Pydantic models to dict for processor
        documents = [doc.dict() for doc in request.documents]
        
        # Process in background for better UX
        background_tasks.add_task(
            process_documents_background,
            project_id,
            documents
        )
        
        return {
            "message": f"Started processing {len(documents)} documents for project {project_id}",
            "status": "processing",
            "document_count": len(documents)
        }
        
    except Exception as e:
        logger.error(f"Failed to queue documents for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to queue documents: {str(e)}")

@router.post("/projects/{project_id}/documents/sync")
async def add_documents_sync(
    project_id: str, 
    request: AddDocumentsRequest
):
    """Add documents to Weaviate synchronously (for smaller batches)"""
    async def _add_docs(vp, project_id, documents):
        result = await vp.add_documents(project_id, documents)
        return result
    
    try:
        # Convert Pydantic models to dict for processor
        documents = [doc.model_dump() for doc in request.documents]
        
        result = await with_vector_processor(_add_docs, project_id, documents)
        # Notify stats-service about embeddings update
        try:
            stats_url = os.getenv("STATS_SERVICE_URL", "http://localhost:8004")
            payload = {"embeddings": {"count": result.get("documents_added", len(documents))}, "timestamp": datetime.now().isoformat()}
            headers = {"Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"}
            async with httpx.AsyncClient(timeout=3.0) as client:
                await client.post(f"{stats_url}/api/stats/projects/{project_id}/events/embeddings-updated", json=payload, headers=headers)
        except Exception:
            pass
        return result
        
    except Exception as e:
        logger.error(f"Failed to add documents for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add documents: {str(e)}")

# --- Multi-embedding per-kind collection endpoints ---
@router.post("/projects/{project_id}/collections/{kind}", response_model=CollectionResponse)
async def ensure_kind_collection(project_id: str, kind: str):
    """Initialize per-kind collection view (uses single underlying Weaviate collection with kind tagged in 'source')."""
    try:
        if kind not in KIND_VALUES:
            raise HTTPException(status_code=400, detail=f"Invalid kind '{kind}'. Allowed: {sorted(KIND_VALUES)}")
        # Ensure base collection exists
        await processor.ensure_collection_exists(f"project_{project_id}")
        # Get stats filtered by kind
        info = await processor.get_collection_info_by_kind(project_id, kind)
        return CollectionResponse(collection_name=f"weaviate:DocumentChunk(project={project_id},kind={kind})", document_count=info.get("document_count", 0))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to ensure kind collection for project {project_id}, kind {kind}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to ensure kind collection: {str(e)}")

@router.get("/projects/{project_id}/collections/{kind}", response_model=CollectionResponse)
async def get_kind_collection_info(project_id: str, kind: str):
    """Get information about a per-kind collection view"""
    try:
        if kind not in KIND_VALUES:
            raise HTTPException(status_code=400, detail=f"Invalid kind '{kind}'. Allowed: {sorted(KIND_VALUES)}")
        info = await processor.get_collection_info_by_kind(project_id, kind)
        return CollectionResponse(collection_name=f"weaviate:DocumentChunk(project={project_id},kind={kind})", document_count=info.get("document_count", 0))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get kind collection info for project {project_id}, kind {kind}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get kind collection info: {str(e)}")

@router.post("/projects/{project_id}/collections/{kind}/documents/sync")
async def add_documents_sync_kind(project_id: str, kind: str, request: AddDocumentsRequest):
    """Add documents to a per-kind collection (sets 'source' to the kind)."""
    async def _add_docs(vp, project_id, documents):
        # Force source to kind for each document
        for d in documents:
            d["source"] = kind
        result = await vp.add_documents(project_id, documents)
        return result

    try:
        if kind not in KIND_VALUES:
            raise HTTPException(status_code=400, detail=f"Invalid kind '{kind}'. Allowed: {sorted(KIND_VALUES)}")

        documents = [doc.model_dump() for doc in request.documents]
        result = await with_vector_processor(_add_docs, project_id, documents)

        # Notify stats-service about embeddings update
        try:
            stats_url = os.getenv("STATS_SERVICE_URL", "http://localhost:8004")
            payload = {"embeddings": {"count": result.get("documents_added", len(documents))}, "timestamp": datetime.now().isoformat()}
            headers = {"Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"}
            async with httpx.AsyncClient(timeout=3.0) as client:
                await client.post(f"{stats_url}/api/stats/projects/{project_id}/events/embeddings-updated", json=payload, headers=headers)
        except Exception:
            pass

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add documents for project {project_id}, kind {kind}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add documents: {str(e)}")

@router.delete("/projects/{project_id}/documents/{filename}", summary="Delete document vectors")
async def delete_document_vectors(
    project_id: str,
    filename: str,
    vector_processor=Depends(get_vector_processor)
):
    """Delete vectors for a specific document"""
    try:
        # Delete vectors where document_id matches the filename
        try:
            col = vector_processor.wclient.collections.get("DocumentChunk")
            where_filter = Filter.by_property("document_id").equal(filename)
            result = col.data.delete_many(where=where_filter)
            
            deleted_count = result.deleted
            logger.info(f"Deleted {deleted_count} vectors for document {filename} in project {project_id}")
            
            # Clear cache
            cache_key = f"collection_stats:{project_id}"
            vector_processor.redis_client.delete(cache_key)
            
            return {
                "message": f"Deleted vectors for document {filename}",
                "deleted_count": deleted_count,
                "project_id": project_id,
                "document_id": filename
            }
        except Exception as e:
            logger.warning(f"No vectors found for document {filename}: {e}")
            return {
                "message": f"No vectors found for document {filename}",
                "deleted_count": 0,
                "project_id": project_id,
                "document_id": filename
            }
            
    except Exception as e:
        logger.error(f"Failed to delete vectors for document {filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete document vectors: {str(e)}")

# Search endpoints
@router.post("/projects/{project_id}/search", response_model=SearchResponse)
async def similarity_search(project_id: str, request: SearchRequest):
    """Perform similarity search in project's vectors (Weaviate)"""
    try:
        result = await processor.similarity_search(
            project_id=project_id,
            query=request.query,
            limit=request.limit,
            include_metadata=request.include_metadata
        )
        return SearchResponse(**result)
        
    except Exception as e:
        logger.error(f"Search failed for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@router.post("/projects/{project_id}/search/hybrid", response_model=SearchResponse)
async def hybrid_search(project_id: str, request: HybridSearchRequest):
    """Perform hybrid search combining semantic and keyword matching (Weaviate)"""
    try:
        result = await processor.hybrid_search(
            project_id=project_id,
            query=request.query,
            limit=request.limit,
            semantic_weight=request.semantic_weight
        )
        return SearchResponse(**result)
        
    except Exception as e:
        logger.error(f"Hybrid search failed for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Hybrid search failed: {str(e)}")

# --- Kind-aware search endpoints ---
@router.post("/projects/{project_id}/collections/{kind}/search", response_model=SearchResponse)
async def similarity_search_kind(project_id: str, kind: str, request: SearchRequest):
    """Perform similarity search filtered to a specific kind (source==kind)."""
    try:
        if kind not in KIND_VALUES:
            raise HTTPException(status_code=400, detail=f"Invalid kind '{kind}'. Allowed: {sorted(KIND_VALUES)}")
        result = await processor.similarity_search_by_kind(
            project_id=project_id,
            kind=kind,
            query=request.query,
            limit=request.limit,
            include_metadata=request.include_metadata,
        )
        return SearchResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Kind search failed for project {project_id}, kind {kind}: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@router.post("/projects/{project_id}/collections/{kind}/search/hybrid", response_model=SearchResponse)
async def hybrid_search_kind(project_id: str, kind: str, request: HybridSearchRequest):
    """Hybrid search filtered to a specific kind (source==kind)."""
    try:
        if kind not in KIND_VALUES:
            raise HTTPException(status_code=400, detail=f"Invalid kind '{kind}'. Allowed: {sorted(KIND_VALUES)}")
        result = await processor.hybrid_search_by_kind(
            project_id=project_id,
            kind=kind,
            query=request.query,
            limit=request.limit,
            semantic_weight=request.semantic_weight,
        )
        return SearchResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Kind hybrid search failed for project {project_id}, kind {kind}: {e}")
        raise HTTPException(status_code=500, detail=f"Hybrid search failed: {str(e)}")

# Utility endpoints
@router.get("/projects/{project_id}/stats")
async def get_collection_stats(project_id: str):
    """Get detailed statistics about a project's vector collection"""
    try:
        info = await processor.get_collection_info(project_id)
        
        # Return meaningful stats even if collection doesn't exist yet
        if info["status"] == "not_found":
            stats = {
                "project_id": project_id,
                "collection_name": f"project_{project_id}",
                "document_count": 0,
                "embeddings_count": 0,
                "last_updated": datetime.now().isoformat(),
                "status": "empty",
                "message": "No documents processed yet"
            }
            return stats
        
        # Add more detailed stats for existing collections
        stats = {
            "project_id": project_id,
            "collection_name": info["collection_name"],
            "document_count": info["document_count"],
            "embeddings_count": info["document_count"],  # Same as document count for now
            "last_updated": datetime.now().isoformat(),
            "status": info["status"]
        }
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get stats for project {project_id}: {e}")
        # Return empty stats instead of error to prevent 404s in document processing
        return {
            "project_id": project_id,
            "collection_name": f"project_{project_id}",
            "document_count": 0,
            "embeddings_count": 0,
            "last_updated": datetime.now().isoformat(),
            "status": "error",
            "error": str(e)
        }

@router.get("/projects/{project_id}/status")
async def get_collection_status(project_id: str):
    """Alias of stats for backward compatibility: returns the same payload as stats."""
    try:
        # Reuse existing stats logic
        return await get_collection_stats(project_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get status for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")

@router.get("/projects/{project_id}/search/cache")
async def get_search_cache_stats(project_id: str):
    """Get search cache statistics for debugging"""
    try:
        # Access Redis client from processor
        redis_client = processor.redis_client
        
        # Get all search cache keys for this project
        search_keys = redis_client.keys(f"search:{project_id}:*")
        collection_key = f"collection_stats:{project_id}"
        
        cache_info = {
            "project_id": project_id,
            "cached_searches": len(search_keys),
            "collection_cache_exists": redis_client.exists(collection_key) == 1,
            "cache_keys_sample": search_keys[:5] if search_keys else []
        }
        
        return cache_info
        
    except Exception as e:
        logger.error(f"Failed to get cache stats for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get cache stats: {str(e)}")

# ---------------- Entity Resolution Endpoint -----------------
@router.post("/projects/{project_id}/entity-resolution/cluster", response_model=EntityResolutionResponse)
async def entity_resolution_cluster(project_id: str, request: EntityResolutionRequest):
    """Cluster entity card vectors to propose canonical entities.

    Governance: gated by ENTITY_RESOLUTION_ENABLED env var (default disabled).
    Returns cluster list with canonical representative previews and stats; does not mutate state.
    """
    if os.getenv("ENTITY_RESOLUTION_ENABLED", "false").lower() not in {"1", "true", "yes"}:
        raise HTTPException(status_code=403, detail="Entity resolution feature disabled. Set ENTITY_RESOLUTION_ENABLED=true to enable.")
    try:
        result = await cluster_entity_cards(processor, project_id, request.similarity_threshold, request.max_cards)
        # Coerce into Pydantic response (nested parsing)
        return EntityResolutionResponse(**result)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Entity resolution failed for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Entity resolution failed: {str(e)}")

# Background task functions
async def process_documents_background(project_id: str, documents: List[Dict[str, Any]]):
    """Background task to process documents asynchronously"""
    try:
        logger.info(f"Starting background processing for {len(documents)} documents in project {project_id}")
        result = await processor.add_documents(project_id, documents)
        logger.info(f"Background processing completed: {result}")
        # Notify stats-service
        try:
            stats_url = os.getenv("STATS_SERVICE_URL", "http://localhost:8004")
            payload = {"embeddings": {"count": result.get("documents_added", len(documents))}, "timestamp": datetime.now().isoformat()}
            headers = {"Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"}
            async with httpx.AsyncClient(timeout=3.0) as client:
                await client.post(f"{stats_url}/api/stats/projects/{project_id}/events/embeddings-updated", json=payload, headers=headers)
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Background document processing failed for project {project_id}: {e}")

async def warm_up_models_background():
    """Background task to warm up AI models for faster first requests"""
    try:
        logger.info("Starting background model warm-up...")
        start_time = datetime.now()
        
        # Load the embedding model asynchronously
        model = await processor._get_embedding_model_async()
        
        if model:
            # Test the model with a small embedding to ensure it's working
            import asyncio
            test_embedding = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: model.encode(["test document for warming up model"])
            )
            load_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"Model warm-up completed successfully in {load_time:.2f}s")
        else:
            logger.warning("Model warm-up completed but model is None")
            
    except Exception as e:
        logger.error(f"Background model warm-up failed: {e}")

# Debug endpoints (only in development)
@router.get("/debug/collections")
async def list_all_collections():
    """Debug endpoint to list Weaviate classes"""
    try:
        # Weaviate v4: list collections
        cols_iter = processor.wclient.collections.list_all()
        class_names = [getattr(c, "name", str(c)) for c in cols_iter]
        return {"classes": class_names, "total_count": len(class_names)}
    except Exception as e:
        logger.error(f"Failed to list collections: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list collections: {str(e)}")

@router.get("/debug/model-info")
async def get_model_info():
    """Debug endpoint to get information about the embedding model"""
    try:
        import os
        model = processor._get_embedding_model()
        model_name = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        
        # Resolve actual model name for supported aliases
        supported_models = {
            "all-MiniLM-L6-v2": "all-MiniLM-L6-v2",
            "jina-embeddings-v2-base-en": "jinaai/jina-embeddings-v2-base-en",
            "jinaai/jina-embeddings-v2-base-en": "jinaai/jina-embeddings-v2-base-en"
        }
        actual_model_name = supported_models.get(model_name, model_name)
        
        return {
            "model_name": actual_model_name,
            "configured_name": model_name,
            "max_seq_length": getattr(model, "max_seq_length", "unknown"),
            "embedding_dimension": model.get_sentence_embedding_dimension() if hasattr(model, "get_sentence_embedding_dimension") else "unknown",
            "model_loaded": processor._embedding_model is not None
        }
    except Exception as e:
        logger.error(f"Failed to get model info: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get model info: {str(e)}")

# Enhanced Structured Document Processing Endpoints
@router.post("/projects/{project_id}/process-structured", response_model=ProcessStructuredResponse)
async def process_structured_documents(
    project_id: str,
    request: ProcessStructuredRequest
):
    """
    Process structured document elements with smart chunking and embedding
    This endpoint implements Step 4 of the enhanced document workflow
    """
    try:
        start_time = datetime.now()
        logger.info(f"Processing {len(request.documents)} structured elements for project {project_id}")
        
        # Ensure collection exists
        collection_name = f"project_{project_id}"
        await processor.ensure_collection_exists(collection_name)
        
        # Smart chunking based on element types and strategy
        chunks = await _smart_chunk_structured_elements(request.documents, request.chunking_strategy)
        
        # Convert chunks to documents for embedding
        documents_for_embedding = []
        for chunk in chunks:
            documents_for_embedding.append({
                "id": chunk["chunk_id"],
                "content": chunk["content"],
                "filename": chunk.get("source_filename", "unknown"),
                "source": request.source,
                "metadata": {
                    "element_type": chunk["element_type"],
                    "element_id": chunk["source_element_id"],
                    "page_number": chunk.get("page_number"),
                    "hierarchy_level": chunk.get("hierarchy_level"),
                    "semantic_tags": chunk.get("semantic_tags", []),
                    "chunk_index": chunk["chunk_index"],
                    "total_chunks": chunk["total_chunks"],
                    "processing_type": "structured",
                    "chunking_strategy": request.chunking_strategy
                }
            })
        
        # Create embeddings
        result = await processor.add_documents(project_id, documents_for_embedding)
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        logger.info(f"Structured processing completed: {len(chunks)} chunks embedded")
        
        return ProcessStructuredResponse(
            status="success",
            elements_processed=len(request.documents),
            embeddings_created=result.get("documents_added", len(chunks)),
            processing_time_seconds=processing_time,
            chunking_strategy=request.chunking_strategy,
            chunks_created=len(chunks)
        )
        
    except Exception as e:
        logger.error(f"Structured processing failed for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Structured processing failed: {str(e)}")

async def _smart_chunk_structured_elements(
    elements: List[StructuredDocumentElement],
    strategy: str = "element_based"
) -> List[Dict[str, Any]]:
    """
    Smart chunking based on element types and content structure
    
    Strategies:
    - element_based: Each element becomes one chunk (preserves structure)
    - smart_element: Intelligent merging of related elements
    - traditional: Text-based chunking ignoring structure
    """
    chunks = []
    
    if strategy == "element_based":
        # Each element becomes one chunk
        for i, element in enumerate(elements):
            if len(element.content.strip()) > 10:  # Only chunk non-empty elements
                chunks.append({
                    "chunk_id": f"{element.element_id}_chunk_0",
                    "content": element.content,
                    "element_type": element.element_type,
                    "source_element_id": element.element_id,
                    "page_number": element.page_number,
                    "hierarchy_level": element.hierarchy_level,
                    "semantic_tags": element.semantic_tags,
                    "chunk_index": 0,
                    "total_chunks": 1,
                    "source_filename": element.metadata.get("filename") if element.metadata else None
                })
    
    elif strategy == "smart_element":
        # Intelligent merging of related elements
        current_chunk = []
        current_chunk_size = 0
        max_chunk_size = 1000  # Characters
        
        for element in elements:
            element_size = len(element.content)
            
            # Start new chunk if:
            # 1. Current chunk would be too large
            # 2. Element is a title/header (semantic boundary)
            # 3. Different hierarchy level
            if (current_chunk and 
                (current_chunk_size + element_size > max_chunk_size or
                 element.element_type in ['title', 'header'] or
                 (current_chunk and element.hierarchy_level != current_chunk[-1].hierarchy_level))):
                
                # Create chunk from current elements
                if current_chunk:
                    chunk_content = "\n\n".join(elem.content for elem in current_chunk)
                    chunks.append({
                        "chunk_id": f"smart_chunk_{len(chunks)}",
                        "content": chunk_content,
                        "element_type": "merged",
                        "source_element_id": ",".join(elem.element_id for elem in current_chunk),
                        "page_number": current_chunk[0].page_number,
                        "hierarchy_level": current_chunk[0].hierarchy_level,
                        "semantic_tags": list(set(tag for elem in current_chunk for tag in (elem.semantic_tags or []))),
                        "chunk_index": len(chunks),
                        "total_chunks": -1,  # Will be updated later
                        "source_filename": current_chunk[0].metadata.get("filename") if current_chunk[0].metadata else None
                    })
                
                current_chunk = []
                current_chunk_size = 0
            
            current_chunk.append(element)
            current_chunk_size += element_size
        
        # Add final chunk
        if current_chunk:
            chunk_content = "\n\n".join(elem.content for elem in current_chunk)
            chunks.append({
                "chunk_id": f"smart_chunk_{len(chunks)}",
                "content": chunk_content,
                "element_type": "merged",
                "source_element_id": ",".join(elem.element_id for elem in current_chunk),
                "page_number": current_chunk[0].page_number,
                "hierarchy_level": current_chunk[0].hierarchy_level,
                "semantic_tags": list(set(tag for elem in current_chunk for tag in (elem.semantic_tags or []))),
                "chunk_index": len(chunks),
                "total_chunks": len(chunks) + 1,
                "source_filename": current_chunk[0].metadata.get("filename") if current_chunk[0].metadata else None
            })
        
        # Update total_chunks for all chunks
        for chunk in chunks:
            chunk["total_chunks"] = len(chunks)
    
    elif strategy == "traditional":
        # Traditional text-based chunking
        all_text = "\n\n".join(elem.content for elem in elements if elem.content.strip())
        chunk_size = 1000
        overlap = 100
        
        for i in range(0, len(all_text), chunk_size - overlap):
            chunk_text = all_text[i:i + chunk_size]
            if chunk_text.strip():
                chunks.append({
                    "chunk_id": f"traditional_chunk_{len(chunks)}",
                    "content": chunk_text,
                    "element_type": "text_chunk",
                    "source_element_id": "traditional_chunking",
                    "page_number": None,
                    "hierarchy_level": None,
                    "semantic_tags": ["traditional_chunk"],
                    "chunk_index": len(chunks),
                    "total_chunks": -1,  # Will be updated later
                    "source_filename": elements[0].metadata.get("filename") if elements and elements[0].metadata else None
                })
        
        # Update total_chunks
        for chunk in chunks:
            chunk["total_chunks"] = len(chunks)
    
    logger.info(f"Smart chunking ({strategy}): {len(elements)} elements → {len(chunks)} chunks")
    return chunks
