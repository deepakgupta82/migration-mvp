#!/usr/bin/env python3
"""
Knowledge Graph Router

REST API endpoints for Neo4j operations, entity extraction, and graph management.
Extracts graph-related functionality from the main backend.

Endpoints:
- Health check and service status
- Entity extraction from documents
- Graph construction and management
- Project graph retrieval and statistics
- Infrastructure topology mapping
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from fastapi import APIRouter, HTTPException, BackgroundTasks, Request, Depends, Query, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import json
import uuid
import os as _os
import math

logger = logging.getLogger(__name__)

router = APIRouter()

# simple in-process cache for health endpoint
_health_cache: Dict[str, Any] = {"data": None, "ts": 0.0}
import os, time
_HEALTH_TTL_SEC = float(os.getenv("GRAPH_HEALTH_CACHE_TTL_SEC", "60"))

# In-memory TTL cache for canonical exploration endpoints
_canonical_cache: Dict[str, Dict[str, Any]] = {}
_CANONICAL_TTL_SEC = float(os.getenv("GRAPH_CANONICAL_CACHE_TTL_SEC", "30"))

# Async job registry defaults (Redis-backed)
_JOB_TTL_SEC = int(os.getenv("GRAPH_JOB_TTL_SEC", "86400"))  # 24h
_JOB_NS = os.getenv("GRAPH_JOB_NS", "graph:jobs")

async def _job_key(job_id: str) -> str:
    return f"{_JOB_NS}:{job_id}"

async def _job_write(graph_processor, job_id: str, payload: Dict[str, Any]):
    try:
        val = json.dumps(payload)
        await graph_processor.redis_client.set(await _job_key(job_id), val, ex=_JOB_TTL_SEC)
    except Exception as e:
        logger.warning(f"job_write failed job={job_id}: {e}")

async def _job_read(graph_processor, job_id: str) -> Optional[Dict[str, Any]]:
    try:
        raw = await graph_processor.redis_client.get(await _job_key(job_id))
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            try:
                return json.loads(raw.decode())
            except Exception:
                return None
    except Exception as e:
        logger.warning(f"job_read failed job={job_id}: {e}")
        return None

def _cache_key(prefix: str, project_id: str, **params) -> str:
    base = "|".join([prefix, project_id] + [f"{k}={v}" for k, v in sorted(params.items())])
    return base

def _cache_get(key: str):
    entry = _canonical_cache.get(key)
    if not entry:
        return None
    if (time.time() - entry.get("ts", 0)) > _CANONICAL_TTL_SEC:
        _canonical_cache.pop(key, None)
        return None
    return entry.get("data")

def _cache_set(key: str, data: Any):
    _canonical_cache[key] = {"data": data, "ts": time.time()}

def _canonical_cache_invalidate(project_id: str):
    to_del = [k for k in _canonical_cache.keys() if f"|{project_id}" in k]
    for k in to_del:
        _canonical_cache.pop(k, None)
    if to_del:
        logger.info(f"Canonical cache invalidated entries={len(to_del)} project={project_id}")

# -------------------------
# Minimal RBAC header check (optional)
# -------------------------
def _enforce_project_header(request: Request, project_id: str):
    """If GRAPH_ENFORCE_PROJECT_HEADER is true, require X-Project-Id header to match path param.

    This is a light defense-in-depth measure for shared environments. Default disabled.
    """
    try:
        if _flag_enabled("GRAPH_ENFORCE_PROJECT_HEADER", False):
            hdr = request.headers.get("X-Project-Id") if request else None
            if not hdr or hdr.strip() != project_id:
                raise HTTPException(status_code=403, detail="project header mismatch")
    except HTTPException:
        raise
    except Exception:
        # Fail closed when enabled but header read fails
        raise HTTPException(status_code=403, detail="project header required")

# -------------------------
# Optional admin role + throttle + audit helpers
# -------------------------
async def _throttle_non_dry_run(graph_processor, project_id: str, dry_run: bool):
    try:
        if dry_run:
            return
        secs = int(_os.getenv("GRAPH_WRITE_THROTTLE_SECONDS", "0") or "0")
        if secs <= 0:
            return
        key = f"graph:maint:throttle:{project_id}"
        now = int(time.time())
        last = await graph_processor.redis_client.get(key)
        if last is not None:
            try:
                last_i = int(last)
            except Exception:
                last_i = 0
            if now - last_i < secs:
                raise HTTPException(status_code=429, detail="maintenance throttled")
        await graph_processor.redis_client.set(key, str(now))
    except HTTPException:
        raise
    except Exception:
        # Do not block on throttle errors; proceed
        pass

def _enforce_admin_role(request: Request, dry_run: bool):
    try:
        if dry_run:
            return
        if not _flag_enabled("GRAPH_ENFORCE_ADMIN_ROLE", False):
            return
        role = (request.headers.get("X-User-Role") or "").strip().lower() if request else ""
        if role != "admin":
            raise HTTPException(status_code=403, detail="admin role required")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=403, detail="admin role required")

async def _audit_maintenance(graph_processor, project_id: str, entry: Dict[str, Any]):
    try:
        key = f"graph:maint:history:{project_id}"
        entry = dict(entry or {})
        entry.setdefault("project_id", project_id)
        entry.setdefault("ts", datetime.utcnow().isoformat())
        val = json.dumps(entry)[:50000]
        await graph_processor.redis_client.lpush(key, val)
        # Keep last 200
        await graph_processor.redis_client.ltrim(key, 0, 199)
    except Exception:
        # Non-fatal
        pass

# -------------------------
# Wiring placeholders (guarded)
# -------------------------
def _flag_enabled(name: str, default: bool = False) -> bool:
    try:
        v = _os.getenv(name, str(default)).strip().lower()
        return v in ("1", "true", "yes", "on")
    except Exception:
        return default

# FastAPI dependency to access graph processor; must be defined before first use
def get_graph_processor(request: Request):
    """Dependency to get graph processor from request state"""
    return request.state.graph_processor

@router.get("/projects/{project_id}/explorer/overview")
async def explorer_overview(project_id: str):
    if not _flag_enabled("GRAPH_EXPLORER_ENABLED", False):
        raise HTTPException(status_code=404, detail="graph explorer disabled")
    try:
        from fastapi import Request
        # We need access to graph_processor; use a lightweight session
        # Instead of Depends, we fetch it from app state via a minimal trick through router dependency is not here.
        # Use a global reference by importing main app if available.
        # Fallback: return 501 if not accessible.
        gp = None
        try:
            from ..main import app as _app  # type: ignore
            gp = getattr(_app.state, "graph_processor", None)
        except Exception:
            gp = None
        if gp is None:
            raise HTTPException(status_code=501, detail="graph processor unavailable")
        async with gp.neo4j_driver.session() as session:  # type: ignore
            # Counts
            ent_rec = await (await session.run(
                """
                MATCH (p:Project {id:$pid})-[:CONTAINS]->(e:Entity)
                RETURN count(e) as c
                """,
                pid=project_id,
            )).single()
            rel_rec = await (await session.run(
                """
                MATCH (p:Project {id:$pid})-[:CONTAINS]->()-[r]->()
                RETURN count(r) as c
                """,
                pid=project_id,
            )).single()
            # Top entity types by labels (excluding system labels)
            top_entities = []
            eres = await session.run(
                """
                MATCH (p:Project {id:$pid})-[:CONTAINS]->(e:Entity)
                WITH e, [l IN labels(e) WHERE NOT l IN ['Entity','CanonicalEntity','Project','Document']] as ls
                UNWIND (CASE WHEN size(ls)=0 THEN ['Entity'] ELSE ls END) AS t
                RETURN t as type, count(*) as cnt
                ORDER BY cnt DESC, toLower(type) ASC
                LIMIT 10
                """,
                pid=project_id,
            )
            async for rec in eres:
                top_entities.append({"type": rec.get("type"), "count": rec.get("cnt", 0)})
            # Top relationship types
            top_rels = []
            rres = await session.run(
                """
                MATCH (p:Project {id:$pid})-[:CONTAINS]->()-[r]->()
                RETURN type(r) as type, count(r) as cnt
                ORDER BY cnt DESC, toLower(type) ASC
                LIMIT 10
                """,
                pid=project_id,
            )
            async for rec in rres:
                top_rels.append({"type": rec.get("type"), "count": rec.get("cnt", 0)})
            return {
                "project_id": project_id,
                "entity_count": int(ent_rec.get("c", 0) if ent_rec else 0),
                "relationship_count": int(rel_rec.get("c", 0) if rel_rec else 0),
                "top_entity_types": top_entities,
                "top_relationship_types": top_rels,
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"explorer_overview error: {e}")
        raise HTTPException(status_code=500, detail="explorer overview failed")

@router.get("/projects/{project_id}/search/fuse")
async def fused_search(
    project_id: str,
    q: str = Query(..., description="Query text"),
    kinds: Optional[str] = Query("entity_cards,raw_chunks", description="Comma list of vector kinds to search (entity_cards,raw_chunks,triple_cards)"),
    k: int = Query(10, ge=1, le=50, description="Top-k results to return after fusion"),
    use_hybrid: bool = Query(True, description="Use hybrid search when available in vector service"),
    boost_centrality: bool = Query(False, description="Apply a small boost using canonical degree centrality if entity is mapped"),
    weights: Optional[str] = Query(None, description="Per-kind weights CSV e.g. entity_cards:1.0,raw_chunks:0.7,triple_cards:0.5"),
    centrality_scale: float = Query(0.05, ge=0.0, le=1.0, description="Scale factor for centrality boost (default 0.05)"),
    normalized_centrality: bool = Query(True, description="Normalize centrality by max degree before scaling"),
    graph_processor = Depends(get_graph_processor),
):
    """RRF-style fused search across multiple vector kinds, with optional centrality boost.

    Returns a list of items with fields: id, name?, text, source(kind), score, fused_score.
    """
    try:
        # Prepare vector-service queries
        kinds_list = [s.strip() for s in (kinds or "").split(",") if s.strip()]
        if not kinds_list:
            kinds_list = ["entity_cards", "raw_chunks"]
        token = _os.getenv("SERVICE_AUTH_TOKEN", "service-backend-token")
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        async def _search_one(kind: Optional[str]):
            base = _os.getenv("VECTOR_SERVICE_URL", getattr(graph_processor, "vector_url", "http://localhost:8005").rstrip("/"))
            if use_hybrid:
                url = f"{base}/projects/{project_id}/collections/{kind}/search/hybrid" if kind else f"{base}/projects/{project_id}/search/hybrid"
            else:
                url = f"{base}/projects/{project_id}/collections/{kind}/search" if kind else f"{base}/projects/{project_id}/search"
            try:
                resp = await graph_processor.http.post(url, json={"query": q, "limit": max(20, k)}, headers=headers)  # type: ignore
                if resp.status_code >= 400:
                    return []
                data = resp.json() or {}
                items = data.get("items") or data.get("results") or []
                out = []
                for it in items:
                    out.append({
                        "id": it.get("id") or it.get("ref") or "",
                        "name": it.get("name") or it.get("title"),
                        "text": it.get("content") or it.get("text"),
                        "score": float(it.get("score", it.get("_additional", {}).get("score", 0)) or 0),
                        "source": kind or "hybrid",
                    })
                return out
            except Exception:
                return []

        # Run per-kind queries serially (http client may not be thread-safe)
        per_kind = []
        for kind in kinds_list:
            per_kind.append(await _search_one(kind))

        # Build weights map
        weight_map: Dict[str, float] = {}
        try:
            if weights:
                for tok in weights.split(","):
                    if ":" in tok:
                        knd, val = tok.split(":", 1)
                        knd = knd.strip()
                        try:
                            weight_map[knd] = float(val.strip())
                        except Exception:
                            pass
        except Exception:
            weight_map = {}

        # Reciprocal Rank Fusion with per-kind weights (using helper for testability)
        try:
            from ....common.ranking import compute_rrf_fusion  # type: ignore
        except Exception:
            compute_rrf_fusion = None  # type: ignore

        if compute_rrf_fusion:
            items = compute_rrf_fusion(per_kind, weights=weight_map, rrf_k=60.0)
        else:
            RRF_K = 60.0
            fused: Dict[str, Dict[str, Any]] = {}
            for results in per_kind:
                for rank, item in enumerate(results):
                    if not item.get("id"):
                        continue
                    rec = fused.setdefault(item["id"], {"id": item["id"], "name": item.get("name"), "text": item.get("text"), "sources": [], "fused_score": 0.0})
                    rec["sources"].append({"source": item.get("source"), "rank": rank+1, "score": item.get("score", 0)})
                    w = weight_map.get(item.get("source"), 1.0)
                    rec["fused_score"] += (1.0 / (RRF_K + (rank + 1))) * max(0.0, float(w))
            items = list(fused.values())

        # Optional degree centrality boost if canonical mapping exists
        if boost_centrality and items:
            # Build a temp map of canonical degrees
            deg_map: Dict[str, float] = {}
            async with graph_processor.neo4j_driver.session() as session:  # type: ignore
                cy = (
                    """
                    MATCH (p:Project {id:$pid})-[:CONTAINS]->(c:CanonicalEntity)
                    OPTIONAL MATCH (c)-[r1]->(:CanonicalEntity)
                    WITH c, count(r1) as out
                    OPTIONAL MATCH (:CanonicalEntity)-[r2]->(c)
                    WITH c, out, count(r2) as inn
                    RETURN c.id as id, (out+inn) as deg
                    """
                )
                res = await session.run(cy, pid=project_id)
                async for rec in res:
                    deg_map[str(rec.get("id"))] = float(rec.get("deg") or 0.0)
            if deg_map:
                try:
                    from ....common.ranking import apply_centrality_boost  # type: ignore
                except Exception:
                    apply_centrality_boost = None  # type: ignore
                if apply_centrality_boost:
                    apply_centrality_boost(items, deg_map, scale=float(centrality_scale), normalized=bool(normalized_centrality))
                else:
                    max_deg = max(deg_map.values()) if deg_map else 1.0
                    for rec in items:
                        cid = rec.get("id")
                        raw = deg_map.get(cid, 0.0)
                        base = (raw / max_deg) if (normalized_centrality and max_deg > 0) else raw
                        boost = float(base) * float(centrality_scale)
                        rec["fused_score"] += boost

        items.sort(key=lambda x: x.get("fused_score", 0.0), reverse=True)
        return {"project_id": project_id, "query": q, "count": min(k, len(items)), "items": items[:k]}
    except Exception as e:
        logger.error(f"fused_search error: {e}")
        raise HTTPException(status_code=500, detail="fused search failed")

@router.get("/projects/{project_id}/maintenance/history")
async def maintenance_history(project_id: str, limit: int = Query(20, ge=1, le=200), graph_processor = Depends(get_graph_processor)):
    """Return recent maintenance runs (dry-run and applied)."""
    try:
        key = f"graph:maint:history:{project_id}"
        raw = await graph_processor.redis_client.lrange(key, 0, int(limit) - 1)
        items: List[Dict[str, Any]] = []
        for s in raw or []:
            try:
                items.append(json.loads(s))
            except Exception:
                continue
        return {"project_id": project_id, "count": len(items), "items": items}
    except Exception as e:
        logger.error(f"maintenance_history failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail="maintenance history failed")

@router.get("/projects/{project_id}/commits/summary")
async def commits_summary(project_id: str, limit: int = 20, offset: int = 0):
    if not _flag_enabled("GRAPH_EXPLORER_ENABLED", False):
        raise HTTPException(status_code=404, detail="graph explorer disabled")
    return {
        "project_id": project_id,
        "items": [],
        "paging": {"limit": limit, "offset": offset, "total": 0},
        "version": "v1",
    }

# Pydantic models for API requests/responses

class DocumentExtractionRequest(BaseModel):
    """Request to extract entities from document content"""
    document_content: str = Field(..., min_length=10, description="Document content to analyze")
    filename: str = Field(..., description="Document filename")
    document_id: str = Field(..., description="Unique document identifier")

class EntityExtractionResponse(BaseModel):
    """Response from entity extraction"""
    project_id: str
    document_id: str
    entities_found: int
    relationships_found: int
    processing_time_ms: float
    extraction_timestamp: str

class ExtractionJobEnqueueResponse(BaseModel):
    job_id: str
    status: str = Field(default="queued")
    project_id: str
    document_id: str
    filename: str
    queued_at: str

class ExtractionJobStatusResponse(BaseModel):
    job_id: str
    project_id: str
    status: str
    document_id: Optional[str] = None
    filename: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    entities_found: Optional[int] = None
    relationships_found: Optional[int] = None
    error: Optional[str] = None
    progress: Optional[List[Dict[str, Any]]] = None

class GraphStatsResponse(BaseModel):
    """Graph statistics response"""
    project_id: str
    total_nodes: int
    total_relationships: int
    node_types: Dict[str, int]
    relationship_types: Dict[str, int]
    last_updated: str

# New models for structured document processing
class StructuredDocumentElement(BaseModel):
    """Structured document element for entity extraction"""
    element_id: str
    content: str
    element_type: str
    page_number: Optional[int] = None
    hierarchy_level: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None

class ProcessStructuredRequest(BaseModel):
    """Request to process structured document elements"""
    document_id: str = Field(..., description="Unique document identifier")
    filename: str = Field(..., description="Document filename")
    structured_elements: List[StructuredDocumentElement] = Field(..., min_items=1)
    processing_type: str = Field(default="structured_extraction")
    extract_entities: bool = Field(default=True)
    extract_relationships: bool = Field(default=True)

class ProcessStructuredResponse(BaseModel):
    """Response from structured processing"""
    status: str
    document_id: str
    filename: str
    elements_analyzed: int
    entities_extracted: int
    relationships_found: int
    processing_time_seconds: float
    entity_types: Dict[str, int]
    relationship_types: Dict[str, int]

class GraphDataResponse(BaseModel):
    """Complete graph data response"""
    project_id: str
    nodes: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    stats: Dict[str, Any]
    timestamp: str

# Unified extractor models
class UnifiedExtractRequest(BaseModel):
    """Request to run a single unified extraction over structured rows.

    rows: actual spreadsheet/CSV rows as JSON objects (header->value). Keep values compact strings/numbers.
    chunk_rows: if >0 and rows exceed this, split into up to max_parts chunks; each part runs at most once.
    max_parts: safety cap for number of LLM calls (default 2).
    """
    document_id: str
    filename: str
    rows: List[Dict[str, Any]] = Field(..., min_items=1)
    chunk_rows: int = Field(0, ge=0, le=1000)
    max_parts: int = Field(2, ge=1, le=4)

class UnifiedExtractJobResponse(BaseModel):
    job_id: str
    status: str = Field(default="queued")
    project_id: str
    document_id: str
    filename: str
    queued_at: str

class UnifiedExtractResult(BaseModel):
    status: str
    document_id: str
    filename: str
    entities: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    facts: List[Dict[str, Any]]
    summary: Dict[str, Any]

class UiMinimalGraphResponse(BaseModel):
    """UI-minimal graph response"""
    project_id: str
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    stats: Dict[str, Any]
    timestamp: str

class GraphNodeSearchResponse(BaseModel):
    """Response model for node search"""
    project_id: str
    query: str
    node_type: Optional[str] = None
    limit: int = 20
    results: List[Dict[str, Any]]

class GraphRelationshipSearchResponse(BaseModel):
    """Response model for relationship search"""
    project_id: str
    rel_type: Optional[str] = None
    limit: int = 50
    results: List[Dict[str, Any]]

class NL2CypherRequest(BaseModel):
    nl: str = Field(..., min_length=3, description="Natural language query")
    limit: int = Field(50, ge=1, le=200)

class NL2CypherResponse(BaseModel):
    project_id: str
    nl: str
    cypher: str
    parameters: Dict[str, Any]

class RunCypherRequest(BaseModel):
    cypher: str = Field(..., min_length=3)
    limit: int = Field(100, ge=1, le=1000)

class RunCypherResponse(BaseModel):
    project_id: str
    rows: List[Dict[str, Any]]
    columns: List[str]
    stats: Dict[str, Any] = {}

class GraphNeighborhoodResponse(BaseModel):
    """Response model for neighborhood subgraph"""
    project_id: str
    node_id: str
    depth: int
    direction: str
    rel_types: Optional[List[str]] = None
    nodes: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]

class CountResponse(BaseModel):
    """Generic count response"""
    project_id: str
    count: int

class PyvisGraphResponse(BaseModel):
    """Response model for PyVis/vis-network graph data"""
    project_id: str
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    timestamp: str

class DiscoveryNode(BaseModel):
    """Discovery node model"""
    id: str
    text: str
    category: str
    confidence: float
    source_document: str
    extracted_at: str
    project_id: str

class DiscoveryResponse(BaseModel):
    """Response model for discoveries"""
    project_id: str
    discoveries: List[Dict[str, Any]]
    total_count: int
    categories: Dict[str, int]
    timestamp: str

class MaintenanceResult(BaseModel):
    project_id: str
    created_nodes: int = 0
    created_relationships: int = 0
    details: Optional[Dict[str, Any]] = None

class GraphHealthResponse(BaseModel):
    """Graph service health response"""
    neo4j_connected: bool
    redis_connected: bool
    total_projects: int
    total_nodes: int
    total_relationships: int
    status: str

# Fusion models
class FusionPersistenceRequest(BaseModel):
    canonical_entities: List[Dict[str, Any]] = []
    canonical_relationships: List[Dict[str, Any]] = []
    entity_mapping: Dict[str, str] = {}
    relationship_mapping: Dict[str, str] = {}
    stats: Dict[str, Any] = {}
    project_id: Optional[str] = None

class FusionPersistenceResponse(BaseModel):
    status: str
    proposal_id: Optional[str] = None
    mode: str
    committed_entities: Optional[int] = None
    committed_relationships: Optional[int] = None

class CanonicalEntitySummary(BaseModel):
    id: str
    name: str
    types: List[str] = []
    canonical: bool = True
    properties: Dict[str, Any] = {}
    provenance: Optional[List[Dict[str, Any]]] = None

class CanonicalRelationshipSummary(BaseModel):
    id: str
    type: str
    from_id: str
    to_id: str
    canonical: bool = True
    properties: Dict[str, Any] = {}
    provenance: Optional[List[Dict[str, Any]]] = None

# --- PVC scaffolding models (Type Registry / Proposals) ---
class TypeDefinition(BaseModel):
    name: str
    properties: Dict[str, Any] = {}

class RelationshipDefinition(BaseModel):
    name: str
    from_type: str
    to_type: str
    properties: Dict[str, Any] = {}
    description: Optional[str] = None

class TypeRegistrySnapshot(BaseModel):
    project_id: str
    entity_types: List[TypeDefinition] = []
    relationship_types: List[RelationshipDefinition] = []
    version: Optional[int] = None
    updated_at: Optional[str] = None

class Proposal(BaseModel):
    project_id: str
    entities: List[Dict[str, Any]] = []
    relationships: List[Dict[str, Any]] = []
    facts: List[Dict[str, Any]] = []
    source_documents: List[Dict[str, Any]] = []

class EntityTypeRegistration(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    properties: Dict[str, Any] = {}
    status: str = Field(default="pending_approval", description="pending_approval|active|deprecated")

class RelationshipTypeRegistration(BaseModel):
    name: str = Field(..., min_length=1)
    from_type: str = Field(..., min_length=1)
    to_type: str = Field(..., min_length=1)
    description: Optional[str] = None
    properties: Dict[str, Any] = {}
    status: str = Field(default="pending_approval")

class AssetUpsertRequest(BaseModel):
    """Request model for upserting an asset (e.g., Server/Application)"""
    hostname: str = Field(..., description="Unique host name or asset name")
    external_id: Optional[str] = Field(None, description="External unique id if available")
    os: Optional[str] = None
    cpu: Optional[int] = None
    memory_gb: Optional[float] = None
    storage_gb: Optional[float] = None
    avg_cpu: Optional[float] = None
    avg_mem: Optional[float] = None
    env: Optional[str] = None
    tags: Optional[Dict[str, Any]] = None
    type: Optional[str] = Field("Server", description="Asset type label (Server/Application/Database)")

def serialize_neo4j_value(value):
    """Convert Neo4j objects to JSON-serializable values"""
    if hasattr(value, "iso_format"):
        return value.iso_format()
    elif hasattr(value, "isoformat"):
        return value.isoformat()
    elif hasattr(value, "__class__") and "neo4j" in str(type(value)):
        return str(value)
    else:
        return value

@router.get("/health", response_model=GraphHealthResponse)
async def health_check(response: Response, graph_processor = Depends(get_graph_processor)):
    """
    Check if graph service is healthy
    
    Returns Neo4j and Redis connection status plus overall statistics
    """
    try:
        # serve from cache when fresh
        now = time.time()
        if _health_cache["data"] is not None and (now - _health_cache["ts"]) < _HEALTH_TTL_SEC:
            response.headers["Cache-Control"] = f"public, max-age={int(_HEALTH_TTL_SEC)}"
            return _health_cache["data"]
        # Test Neo4j connection
        neo4j_connected = False
        total_projects = 0
        total_nodes = 0
        total_relationships = 0
        
        try:
            async with graph_processor.neo4j_driver.session() as session:
                # Test connection and get basic stats
                result = await session.run("RETURN 1 as test")
                single_result = await result.single()
                neo4j_connected = True
                
                # Get total counts
                projects_result = await session.run("MATCH (p:Project) RETURN count(p) as count")
                projects_record = await projects_result.single()
                total_projects = projects_record['count'] if projects_record else 0
                
                nodes_result = await session.run("MATCH (n) RETURN count(n) as count")
                nodes_record = await nodes_result.single()
                total_nodes = nodes_record['count'] if nodes_record else 0
                
                rels_result = await session.run("MATCH ()-[r]->() RETURN count(r) as count")
                rels_record = await rels_result.single()
                total_relationships = rels_record['count'] if rels_record else 0
                
        except Exception as e:
            logger.error(f"Neo4j health check failed: {e}")
        
        # Test Redis connection
        redis_connected = False
        try:
            await graph_processor.redis_client.ping()
            redis_connected = True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
        
        status = "healthy" if neo4j_connected and redis_connected else "degraded"

        result = GraphHealthResponse(
            neo4j_connected=neo4j_connected,
            redis_connected=redis_connected,
            total_projects=total_projects,
            total_nodes=total_nodes,
            total_relationships=total_relationships,
            status=status,
        )
        _health_cache["data"] = result
        _health_cache["ts"] = now
        response.headers["Cache-Control"] = f"public, max-age={int(_HEALTH_TTL_SEC)}"
        return result

    except Exception as e:
        logger.error(f"Health check error: {e}")
        raise HTTPException(status_code=500, detail="Health check failed")

# ---------------- Fusion Persistence Endpoints -----------------
@router.post("/api/graphs/projects/{project_id}/fusion/proposals", response_model=FusionPersistenceResponse)
async def create_fusion_proposal(project_id: str, request: FusionPersistenceRequest):
    """Store fusion result as a proposal (proposal_type=fusion)."""
    try:
        from ..pvc_repo.repository import PVCRepository
        repo = PVCRepository()
        payload = request.dict()
        payload['project_id'] = project_id
        result = repo.create_fusion_proposal(project_id, payload)
        resp = FusionPersistenceResponse(status="ok", proposal_id=result.get("proposal_id"), mode="proposal")
        # Proposal creation may later lead to commit; optional early invalidation if proposals influence exploration soon
        _canonical_cache_invalidate(project_id)
        return resp
    except Exception as e:
        logger.error(f"Fusion proposal persistence failed: {e}")
        raise HTTPException(status_code=500, detail="Fusion proposal persistence failed")

@router.post("/api/graphs/projects/{project_id}/fusion/commit", response_model=FusionPersistenceResponse)
async def commit_fusion_direct(project_id: str, request: FusionPersistenceRequest, graph_processor = Depends(get_graph_processor)):
    """Directly commit canonical entities & relationships to Neo4j, labeling as CanonicalEntity and canonical=true."""
    try:
        committed_entities = 0
        committed_relationships = 0
        # Upsert entities
        async with graph_processor.neo4j_driver.session() as session:
            # Helper to sanitize provenance list entries
            def _sanitize_provenance(pval):
                if not isinstance(pval, list):
                    return None
                cleaned = []
                for it in pval:
                    if not isinstance(it, dict):
                        continue
                    ref = it.get('ref') or it.get('id') or it.get('source_id')
                    if not ref:
                        continue
                    cleaned.append({
                        'ref': str(ref)[:120],
                        'score': float(it.get('score', 1.0)) if isinstance(it.get('score'), (int,float,str)) else 1.0,
                        'chunk': it.get('chunk') or None,
                        'offset': int(it.get('offset', 0)) if isinstance(it.get('offset'), (int,float,str)) else 0,
                        'evidence': (str(it.get('evidence'))[:500] if it.get('evidence') else None)
                    })
                return cleaned[:50] if cleaned else None
            for ent in request.canonical_entities:
                ent_id = ent.get('id')
                name = ent.get('name')
                types = ent.get('types') or []
                props = ent.get('properties') or {}
                prov = _sanitize_provenance(ent.get('provenance'))
                if prov:
                    props['provenance'] = prov
                labels = ":".join({t for t in types if t})
                # Always include CanonicalEntity
                cypher = f"MERGE (e:CanonicalEntity:{labels} {{id:$id}}) SET e.name=$name, e.canonical=true, e.properties=$props"
                await session.run(cypher, id=ent_id, name=name, props=props)
                committed_entities += 1
            # Upsert relationships
            for rel in request.canonical_relationships:
                rid = rel.get('id')
                rtype = rel.get('type') or 'RELATED'
                src = rel.get('from_id')
                dst = rel.get('to_id')
                props = rel.get('properties') or {}
                prov = _sanitize_provenance(rel.get('provenance'))
                if prov:
                    props['provenance'] = prov
                cypher_rel = ("MATCH (s {id:$src}), (t {id:$dst}) "
                              "MERGE (s)-[r:`" + rtype + "` {id:$rid}]->(t) SET r.canonical=true, r.properties=$props")
                await session.run(cypher_rel, src=src, dst=dst, rid=rid, props=props)
                committed_relationships += 1
        # Invalidate canonical exploration cache after direct commit
        _canonical_cache_invalidate(project_id)
        return FusionPersistenceResponse(status="ok", mode="direct", committed_entities=committed_entities, committed_relationships=committed_relationships)
    except Exception as e:
        logger.error(f"Fusion direct commit failed: {e}")
        raise HTTPException(status_code=500, detail="Fusion direct commit failed")

# ---------------- Canonical Exploration Endpoints -----------------
@router.get("/api/graphs/projects/{project_id}/canonical/entities")
async def list_canonical_entities(
    project_id: str,
    q: Optional[str] = Query(None, description="Substring match on name"),
    type: Optional[str] = Query(None, description="Filter by included label/type"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    graph_processor = Depends(get_graph_processor),
):
    """List canonical entities (label CanonicalEntity) with optional filters.

    Includes basic properties + provenance if stored in properties.provenance.
    """
    try:
        ck = _cache_key("canonical_entities", project_id, q=q or "", type=type or "", limit=limit, offset=offset)
        cached = _cache_get(ck)
        if cached:
            return cached
        async with graph_processor.neo4j_driver.session() as session:  # type: ignore
            filters = ["c.canonical = true"]
            params: Dict[str, Any] = {"pid": project_id, "skip": offset, "lim": limit}
            if q:
                filters.append("toLower(c.name) CONTAINS toLower($q)")
                params["q"] = q
            if type:
                # match if label exists or type property matches
                filters.append("($type IN labels(c) OR c.type = $type)")
                params["type"] = type
            where_clause = " AND ".join(filters)
            cypher = (
                "MATCH (p:Project {id:$pid})-[:CONTAINS]->(c:CanonicalEntity) "
                f"WHERE {where_clause} "
                "RETURN c.id as id, c.name as name, labels(c) as labels, c.properties as props "
                "ORDER BY toLower(c.name) SKIP $skip LIMIT $lim"
            )
            count_cypher = (
                "MATCH (p:Project {id:$pid})-[:CONTAINS]->(c:CanonicalEntity) "
                f"WHERE {where_clause} RETURN count(c) as total"
            )
            res = await session.run(cypher, **params)
            items: List[Dict[str, Any]] = []
            async for rec in res:
                props = rec.get("props") or {}
                provenance = props.get("provenance") if isinstance(props.get("provenance"), list) else None
                items.append(
                    {
                        "id": rec.get("id"),
                        "name": rec.get("name"),
                        "types": [l for l in rec.get("labels", []) if l not in {"Entity", "CanonicalEntity"}],
                        "properties": {k: v for k, v in props.items() if k != "provenance"},
                        "provenance": provenance,
                    }
                )
            total_rec = await (await session.run(count_cypher, **{k: v for k, v in params.items() if k not in {"skip", "lim"}})).single()
            total = total_rec.get("total") if total_rec else len(items)
            result = {
                "project_id": project_id,
                "items": items,
                "count": len(items),
                "total": total,
                "offset": offset,
                "limit": limit,
            }
            _cache_set(ck, result)
            return result
    except Exception as e:
        logger.error(f"Canonical entity list failed: {e}")
        raise HTTPException(status_code=500, detail="Canonical entity list failed")

@router.get("/api/graphs/projects/{project_id}/canonical/entities/{entity_id}")
async def get_canonical_entity(project_id: str, entity_id: str, graph_processor = Depends(get_graph_processor)):
    """Get a single canonical entity with its immediate canonical relationships (both directions)."""
    try:
        async with graph_processor.neo4j_driver.session() as session:  # type: ignore
            cypher = (
                "MATCH (p:Project {id:$pid})-[:CONTAINS]->(c:CanonicalEntity {id:$id}) "
                "OPTIONAL MATCH (c)-[r]->(o:CanonicalEntity) "
                "OPTIONAL MATCH (i:CanonicalEntity)-[r2]->(c) "
                "RETURN c, collect(distinct {type:type(r), id:r.id, to:o.id}) as outRels, "
                "       collect(distinct {type:type(r2), id:r2.id, from:i.id}) as inRels"
            )
            rec = await (await session.run(cypher, pid=project_id, id=entity_id)).single()
            if not rec:
                raise HTTPException(status_code=404, detail="Not found")
            cnode = rec.get("c")
            props = cnode.get("properties") if isinstance(cnode, dict) else getattr(cnode, "properties", {}) or {}
            provenance = props.get("provenance") if isinstance(props.get("provenance"), list) else None
            entity = {
                "id": cnode.get("id") if isinstance(cnode, dict) else getattr(cnode, "id", entity_id),
                "name": cnode.get("name") if isinstance(cnode, dict) else getattr(cnode, "name", entity_id),
                "types": [l for l in (cnode.get("labels") if isinstance(cnode, dict) else getattr(cnode, "labels", [])) if l not in {"Entity", "CanonicalEntity"}],
                "properties": {k: v for k, v in props.items() if k != "provenance"},
                "provenance": provenance,
            }
            return {
                "project_id": project_id,
                "entity": entity,
                "outgoing": rec.get("outRels", []),
                "incoming": rec.get("inRels", []),
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Canonical entity get failed: {e}")
        raise HTTPException(status_code=500, detail="Canonical entity get failed")

@router.get("/api/graphs/projects/{project_id}/canonical/relationships")
async def list_canonical_relationships(
    project_id: str,
    type: Optional[str] = Query(None, description="Filter by relationship type"),
    from_id: Optional[str] = None,
    to_id: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    graph_processor = Depends(get_graph_processor),
):
    """List canonical relationships between canonical entities with optional filters."""
    try:
        ck = _cache_key("canonical_relationships", project_id, type=type or "", from_id=from_id or "", to_id=to_id or "", limit=limit, offset=offset)
        cached = _cache_get(ck)
        if cached:
            return cached
        async with graph_processor.neo4j_driver.session() as session:  # type: ignore
            filters = ["r.canonical = true"]
            params: Dict[str, Any] = {"pid": project_id, "skip": offset, "lim": limit}
            if type:
                filters.append("type(r) = $rtype")
                params["rtype"] = type
            if from_id:
                filters.append("s.id = $from_id")
                params["from_id"] = from_id
            if to_id:
                filters.append("t.id = $to_id")
                params["to_id"] = to_id
            where_clause = " AND ".join(filters)
            cypher = (
                "MATCH (p:Project {id:$pid})-[:CONTAINS]->(s:CanonicalEntity)-[r]->(t:CanonicalEntity) "
                f"WHERE {where_clause} "
                "RETURN r.id as id, type(r) as type, s.id as from_id, t.id as to_id, r.properties as props "
                "ORDER BY toLower(type(r)) SKIP $skip LIMIT $lim"
            )
            count_cypher = (
                "MATCH (p:Project {id:$pid})-[:CONTAINS]->(s:CanonicalEntity)-[r]->(t:CanonicalEntity) "
                f"WHERE {where_clause} RETURN count(r) as total"
            )
            res = await session.run(cypher, **params)
            items: List[Dict[str, Any]] = []
            async for rec in res:
                props = rec.get("props") or {}
                items.append(
                    {
                        "id": rec.get("id"),
                        "type": rec.get("type"),
                        "from_id": rec.get("from_id"),
                        "to_id": rec.get("to_id"),
                        "properties": {k: v for k, v in props.items() if k != "provenance"},
                        "provenance": props.get("provenance") if isinstance(props.get("provenance"), list) else None,
                    }
                )
            total_rec = await (await session.run(count_cypher, **{k: v for k, v in params.items() if k not in {"skip", "lim"}})).single()
            total = total_rec.get("total") if total_rec else len(items)
            result = {
                "project_id": project_id,
                "items": items,
                "count": len(items),
                "total": total,
                "offset": offset,
                "limit": limit,
            }
            _cache_set(ck, result)
            return result
    except Exception as e:
        logger.error(f"Canonical relationship list failed: {e}")
        raise HTTPException(status_code=500, detail="Canonical relationship list failed")

@router.get("/api/graphs/projects/{project_id}/canonical/centrality")
async def canonical_centrality(
    project_id: str,
    limit: int = Query(100, ge=1, le=1000),
    graph_processor = Depends(get_graph_processor),
):
    """Compute simple degree centrality metrics for canonical entities.

    Returns top nodes by total_degree (out+in). This is a lightweight query to support
    ranking augmentation and diagnostics without full graph analytics tooling.
    """
    try:
        async with graph_processor.neo4j_driver.session() as session:  # type: ignore
            cypher = (
                "MATCH (p:Project {id:$pid})-[:CONTAINS]->(c:CanonicalEntity) "
                "OPTIONAL MATCH (c)-[r1]->(:CanonicalEntity) "
                "WITH c, count(r1) as out_deg "
                "OPTIONAL MATCH (:CanonicalEntity)-[r2]->(c) "
                "WITH c, out_deg, count(r2) as in_deg "
                "RETURN c.id as id, c.name as name, out_deg, in_deg, (out_deg + in_deg) as total_deg "
                "ORDER BY total_deg DESC, toLower(name) ASC LIMIT $lim"
            )
            res = await session.run(cypher, pid=project_id, lim=limit)
            rows = []
            async for rec in res:
                rows.append({
                    "id": rec.get("id"),
                    "name": rec.get("name"),
                    "out_degree": rec.get("out_deg", 0),
                    "in_degree": rec.get("in_deg", 0),
                    "total_degree": rec.get("total_deg", 0),
                })
            # Normalization factors for augmentation use
            max_total = max((r["total_degree"] for r in rows), default=1)
            for r in rows:
                r["normalized_total_degree"] = (r["total_degree"] / max_total) if max_total else 0.0
            return {"project_id": project_id, "count": len(rows), "items": rows}
    except Exception as e:
        logger.error(f"Centrality computation failed: {e}")
        raise HTTPException(status_code=500, detail="Centrality computation failed")

@router.post("/projects/{project_id}/maintenance/run-phases")
async def run_phases(
    project_id: str,
    dry_run: bool = Query(False, description="Plan-only for all steps"),
    min_score: float = Query(0.55, ge=0.0, le=1.0),
    max_candidates: int = Query(5, ge=1, le=20),
    preferred_kind: str = Query("entity_cards"),
    use_hybrid: bool = Query(True),
    min_support: int = Query(2, ge=1, le=1000),
    max_pairs: int = Query(1000, ge=1, le=10000),
    allow_types: Optional[str] = Query(None),
    graph_processor = Depends(get_graph_processor),
    http_request: Request = None,
):
    """Run end-to-end: REFERS_TO linking → canonical relationship materialization.

    When dry_run=true, returns plans from both steps without writes.
    """
    try:
        _enforce_project_header(http_request, project_id)
        corr_id = None
        try:
            if http_request is not None:
                corr_id = http_request.headers.get("X-Correlation-ID")
        except Exception:
            pass
        # Role + throttle for non-dry runs
        _enforce_admin_role(http_request, dry_run)
        await _throttle_non_dry_run(graph_processor, project_id, dry_run)
        # Step 1: REFERS_TO
        ref_res = await graph_processor.materialize_refers_to_links(
            project_id=project_id,
            min_score=float(min_score),
            max_candidates=int(max_candidates),
            preferred_kind=str(preferred_kind or "entity_cards"),
            use_hybrid=bool(use_hybrid),
            dry_run=bool(dry_run),
            correlation_id=corr_id,
        )
        # Step 2: Canonical relationships
        allow_list = [t.strip() for t in allow_types.split(",")] if allow_types else None
        can_res = await graph_processor.materialize_canonical_relationships(
            project_id=project_id,
            min_support=int(min_support),
            max_pairs=int(max_pairs),
            allow_types=allow_list,
            dry_run=bool(dry_run),
            correlation_id=corr_id,
        )
        result = {
            "project_id": project_id,
            "dry_run": bool(dry_run),
            "refers_to": ref_res,
            "canonical_relationships": can_res,
        }
        # Audit
        try:
            await _audit_maintenance(graph_processor, project_id, {
                "dry_run": bool(dry_run),
                "action": "run-phases",
                "params": {
                    "min_score": float(min_score),
                    "max_candidates": int(max_candidates),
                    "preferred_kind": str(preferred_kind or "entity_cards"),
                    "use_hybrid": bool(use_hybrid),
                    "min_support": int(min_support),
                    "max_pairs": int(max_pairs),
                    "allow_types": allow_list,
                },
                "summary": {
                    "refers_to": ref_res,
                    "canonical_relationships": can_res,
                }
            })
        except Exception:
            pass
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"run_phases error: {e}")
        raise HTTPException(status_code=500, detail="run phases failed")

@router.post("/projects/{project_id}/assets")
async def upsert_asset(
    project_id: str,
    request: AssetUpsertRequest,
    graph_processor = Depends(get_graph_processor),
):
    """Upsert a basic asset node (default label Server) and attach to project."""
    try:
        # Delegate to graph processor method
        node_id = await graph_processor.upsert_asset(
            project_id=project_id,
            asset_type=request.type or "Server",
            hostname=request.hostname,
            properties={
                "external_id": request.external_id,
                "os": request.os,
                "cpu": request.cpu,
                "memory_gb": request.memory_gb,
                "storage_gb": request.storage_gb,
                "avg_cpu": request.avg_cpu,
                "avg_mem": request.avg_mem,
                "env": request.env,
                **(request.tags or {}),
            },
        )
        return {"status": "ok", "id": node_id}
    except Exception as e:
        logger.error(f"Asset upsert failed for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Asset upsert failed")

@router.post("/projects/{project_id}/extract", response_model=EntityExtractionResponse)
async def extract_entities(
    project_id: str,
    request: DocumentExtractionRequest,
    background_tasks: BackgroundTasks,
    graph_processor = Depends(get_graph_processor),
    http_request: Request = None,
):
    """
    Extract entities and relationships from document content
    
    Processes document content to identify:
    - Servers, applications, databases
    - Technologies and frameworks  
    - Dependencies and relationships
    """
    try:
        start_time = datetime.utcnow()
        
        # Extract entities from document content
        corr_id = None
        try:
            if http_request is not None:
                corr_id = http_request.headers.get("X-Correlation-ID")
        except Exception:
            pass
        try:
            logger.info(
                "Extract request received: proj=%s doc=%s file=%s corr_id=%s",
                project_id,
                request.document_id,
                request.filename,
                corr_id or "-",
            )
        except Exception:
            pass
        extraction_result = await graph_processor.extract_entities_from_document(
            project_id=project_id,
            document_content=request.document_content,
            filename=request.filename,
            document_id=request.document_id,
            correlation_id=corr_id,
        )
        
        # Add entities to graph in background
        background_tasks.add_task(
            graph_processor.add_entities_to_graph,
            project_id,
            extraction_result
        )
        try:
            logger.info(
                "Queued graph upsert: proj=%s doc=%s entities=%d rels=%d",
                project_id,
                request.document_id,
                len(extraction_result.entities),
                len(extraction_result.relationships),
            )
        except Exception:
            pass
        
        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return EntityExtractionResponse(
            project_id=project_id,
            document_id=request.document_id,
            entities_found=len(extraction_result.entities),
            relationships_found=len(extraction_result.relationships),
            processing_time_ms=processing_time,
            extraction_timestamp=extraction_result.metadata["extraction_timestamp"]
        )
        
    except Exception as e:
        logger.error(f"Entity extraction failed for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Entity extraction failed")

@router.post("/projects/{project_id}/extract-async", response_model=ExtractionJobEnqueueResponse)
async def extract_entities_async(
    project_id: str,
    request: DocumentExtractionRequest,
    background_tasks: BackgroundTasks,
    graph_processor = Depends(get_graph_processor),
    http_request: Request = None,
):
    """
    Asynchronously extract entities and upsert to the graph.

    Returns 202 Accepted with a job_id that can be polled for status.
    """
    try:
        corr_id = None
        try:
            if http_request is not None:
                corr_id = http_request.headers.get("X-Correlation-ID")
        except Exception:
            pass
        job_id = str(uuid.uuid4())
        enqueued_at = datetime.utcnow().isoformat()
        # Seed job status
        job = {
            "job_id": job_id,
            "project_id": project_id,
            "status": "queued",
            "document_id": request.document_id,
            "filename": request.filename,
            "queued_at": enqueued_at,
            "progress": [
                {"ts": enqueued_at, "stage": "queued", "message": "Job enqueued"}
            ],
        }
        await _job_write(graph_processor, job_id, job)

        async def _run_job():
            # Local helper to update job
            async def _update(stage: str, message: str, extra: Optional[Dict[str, Any]] = None):
                current = await _job_read(graph_processor, job_id) or {}
                current.setdefault("progress", []).append({"ts": datetime.utcnow().isoformat(), "stage": stage, "message": message})
                if extra:
                    current.update(extra)
                await _job_write(graph_processor, job_id, current)

            try:
                await _update("extracting", "Starting entity extraction", {"status": "running", "started_at": datetime.utcnow().isoformat()})
                extraction_result = await graph_processor.extract_entities_from_document(
                    project_id=project_id,
                    document_content=request.document_content,
                    filename=request.filename,
                    document_id=request.document_id,
                    correlation_id=corr_id,
                )
                await _update("extracted", "Extraction complete", {
                    "entities_found": len(extraction_result.entities),
                    "relationships_found": len(extraction_result.relationships),
                    "extraction_timestamp": extraction_result.metadata.get("extraction_timestamp") if getattr(extraction_result, "metadata", None) else None,
                })
                await _update("upserting", "Upserting entities to graph")
                await graph_processor.add_entities_to_graph(project_id, extraction_result)
                await _update("completed", "Graph upsert complete", {
                    "status": "succeeded",
                    "finished_at": datetime.utcnow().isoformat(),
                })
            except Exception as e:
                logger.error(f"Async extract job failed job={job_id}: {e}")
                await _update("failed", "Job failed", {"status": "failed", "error": str(e), "finished_at": datetime.utcnow().isoformat()})

        # Kick background task
        background_tasks.add_task(_run_job)

        # FastAPI 202 response with body
        payload = ExtractionJobEnqueueResponse(
            job_id=job_id,
            status="queued",
            project_id=project_id,
            document_id=request.document_id,
            filename=request.filename,
            queued_at=enqueued_at,
        )
        return JSONResponse(status_code=202, content=payload.dict())
    except Exception as e:
        logger.error(f"Failed to enqueue async extract for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to enqueue async extract")

@router.get("/projects/{project_id}/jobs/{job_id}", response_model=ExtractionJobStatusResponse)
async def get_extraction_job_status(
    project_id: str,
    job_id: str,
    graph_processor = Depends(get_graph_processor),
):
    """
    Return the status of an async extract job.
    """
    try:
        job = await _job_read(graph_processor, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="job not found or expired")
        if job.get("project_id") != project_id:
            # Do not leak other project jobs
            raise HTTPException(status_code=404, detail="job not found")
        # Shape response
        return ExtractionJobStatusResponse(
            job_id=job.get("job_id"),
            project_id=job.get("project_id"),
            status=job.get("status", "unknown"),
            document_id=job.get("document_id"),
            filename=job.get("filename"),
            started_at=job.get("started_at"),
            finished_at=job.get("finished_at"),
            entities_found=job.get("entities_found"),
            relationships_found=job.get("relationships_found"),
            error=job.get("error"),
            progress=job.get("progress"),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job status job={job_id} proj={project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get job status")

@router.post("/projects/{project_id}/extract-sync", response_model=EntityExtractionResponse)
async def extract_entities_sync(
    project_id: str,
    request: DocumentExtractionRequest,
    graph_processor = Depends(get_graph_processor),
    http_request: Request = None,
):
    """
    Extract entities and add to graph synchronously
    
    Similar to extract_entities but waits for graph insertion to complete.
    Use for smaller documents or when immediate consistency is required.
    """
    try:
        start_time = datetime.utcnow()
        
        # Extract entities from document content
        corr_id = None
        try:
            if http_request is not None:
                corr_id = http_request.headers.get("X-Correlation-ID")
        except Exception:
            pass
        try:
            logger.info(
                "Extract-sync request: proj=%s doc=%s file=%s corr_id=%s",
                project_id,
                request.document_id,
                request.filename,
                corr_id or "-",
            )
        except Exception:
            pass
        extraction_result = await graph_processor.extract_entities_from_document(
            project_id=project_id,
            document_content=request.document_content,
            filename=request.filename,
            document_id=request.document_id,
            correlation_id=corr_id,
        )
        
        # Add entities to graph synchronously
        await graph_processor.add_entities_to_graph(project_id, extraction_result)
        try:
            logger.info(
                "Graph upsert complete (sync): proj=%s doc=%s entities=%d rels=%d",
                project_id,
                request.document_id,
                len(extraction_result.entities),
                len(extraction_result.relationships),
            )
        except Exception:
            pass
        
        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return EntityExtractionResponse(
            project_id=project_id,
            document_id=request.document_id,
            entities_found=len(extraction_result.entities),
            relationships_found=len(extraction_result.relationships),
            processing_time_ms=processing_time,
            extraction_timestamp=extraction_result.metadata["extraction_timestamp"]
        )
        
    except Exception as e:
        logger.error(f"Sync entity extraction failed for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Sync entity extraction failed")

@router.get("/projects/{project_id}/graph", response_model=GraphDataResponse)
async def get_project_graph(
    project_id: str,
    graph_processor = Depends(get_graph_processor)
):
    """
    Get complete graph data for a project
    
    Returns all nodes, relationships, and statistics for the specified project.
    Results are cached to improve performance.
    """
    def serialize_value(val):
        # Neo4j DateTime and similar objects
        try:
            import neo4j
            if isinstance(val, getattr(neo4j.time, "DateTime", ())):
                return val.iso_format() if hasattr(val, "iso_format") else str(val)
        except Exception:
            pass
        if hasattr(val, "isoformat"):
            return val.isoformat()
        return str(val) if type(val).__module__.startswith("neo4j") else val

    def serialize_dict(d):
        if isinstance(d, dict):
            return {k: serialize_dict(v) for k, v in d.items()}
        elif isinstance(d, list):
            return [serialize_dict(v) for v in d]
        else:
            return serialize_value(d)

    try:
        graph_data = await graph_processor.get_project_graph(project_id)
        # Serialize nodes and relationships to handle Neo4j DateTime
        nodes = serialize_dict(graph_data["nodes"])
        relationships = serialize_dict(graph_data["relationships"])
        stats = serialize_dict(graph_data["stats"])
        timestamp = serialize_value(graph_data["timestamp"])

        return GraphDataResponse(
            project_id=graph_data["project_id"],
            nodes=nodes,
            relationships=relationships,
            stats=stats,
            timestamp=timestamp
        )
        
    except Exception as e:
        logger.error(f"Failed to get graph for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve project graph")

# ---------------- Unified Extractor (1–2 calls, async) -----------------
@router.post("/projects/{project_id}/extract-unified", response_model=UnifiedExtractJobResponse)
async def extract_unified_async(
    project_id: str,
    request: UnifiedExtractRequest,
    background_tasks: BackgroundTasks,
    graph_processor = Depends(get_graph_processor),
    http_request: Request = None,
):
    """Accept actual JSONL rows and run a unified extraction that returns entities, relationships, facts, summary.

    Behavior
    - Splits rows into at most `max_parts` chunks if `chunk_rows` > 0 and len(rows) is large
    - Performs 1–2 LLM calls (parts) max; merges results deterministically
    - Persists entities/relationships to Neo4j and facts as Discovery nodes
    - Returns 202 with job id and progress; use existing jobs endpoint for status
    """
    try:
        corr_id = None
        try:
            if http_request is not None:
                corr_id = http_request.headers.get("X-Correlation-ID") or None
        except Exception:
            pass

        if not (request.rows and isinstance(request.rows, list)):
            raise HTTPException(status_code=400, detail="rows must be a non-empty list of objects")

        job_id = str(uuid.uuid4())
        enqueued_at = datetime.utcnow().isoformat()
        # Seed job
        job = {
            "job_id": job_id,
            "project_id": project_id,
            "status": "queued",
            "document_id": request.document_id,
            "filename": request.filename,
            "queued_at": enqueued_at,
            "progress": [
                {"ts": enqueued_at, "stage": "queued", "message": f"Rows received: {len(request.rows)}"}
            ],
        }
        await _job_write(graph_processor, job_id, job)

        # Background worker
        async def _run_unified_job():
            async def _update(stage: str, message: str, extra: Optional[Dict[str, Any]] = None):
                cur = await _job_read(graph_processor, job_id) or {}
                cur.setdefault("progress", []).append({"ts": datetime.utcnow().isoformat(), "stage": stage, "message": message})
                if extra:
                    cur.update(extra)
                await _job_write(graph_processor, job_id, cur)

            try:
                await _update("starting", "Unified extraction started", {"status": "running", "started_at": datetime.utcnow().isoformat()})

                # Build chunks of rows
                rows = list(request.rows)
                chunk_rows = int(request.chunk_rows or 0)
                max_parts = int(request.max_parts or 2)
                parts: List[List[Dict[str, Any]]] = []
                if chunk_rows and chunk_rows > 0 and len(rows) > chunk_rows:
                    total_parts = min(max_parts, int(math.ceil(len(rows) / float(chunk_rows))))
                    for i in range(total_parts):
                        start = i * chunk_rows
                        end = min(len(rows), start + chunk_rows)
                        if start < end:
                            parts.append(rows[start:end])
                else:
                    parts = [rows]

                await _update("prepare", f"Prepared {len(parts)} part(s) for LLM", {"parts": len(parts)})

                # Helper to create compact textual input for LLM from rows
                def _rows_to_text(rows_part: List[Dict[str, Any]]) -> str:
                    # Keep stable header order by union of keys across sample
                    keys: List[str] = []
                    seen = set()
                    for r in rows_part[:50]:
                        for k in r.keys():
                            if k not in seen:
                                seen.add(k)
                                keys.append(k)
                    # Emit header then rows as CSV-like lines
                    header = ",".join(keys)
                    lines = [header]
                    for r in rows_part:
                        vals = []
                        for k in keys:
                            v = r.get(k)
                            s = "" if v is None else str(v)
                            # strip newlines and commas to keep compact
                            s = s.replace("\n", " ").replace("\r", " ").replace(",", ";")
                            vals.append(s)
                        lines.append(",".join(vals))
                    return "\n".join(lines)

                # Aggregate outputs
                all_entities: List[Dict[str, Any]] = []
                all_relationships: List[Dict[str, Any]] = []
                all_facts: List[Dict[str, Any]] = []
                summary: Dict[str, Any] = {"parts": len(parts)}

                # For each part, call existing LLM helpers: entity + fact extraction, then merge
                for idx, part_rows in enumerate(parts, start=1):
                    await _update("llm_call", f"Part {idx}/{len(parts)}: building prompt")
                    text = _rows_to_text(part_rows)
                    # Use entity extractor first
                    doc_id = f"structured_rows_{request.document_id}_p{idx}"
                    filename = f"{request.filename}#rows_part{idx}"
                    res = await graph_processor.extract_entities_from_document(
                        project_id=project_id,
                        document_content=text,
                        filename=filename,
                        document_id=doc_id,
                        correlation_id=corr_id,
                    )
                    # Merge raw dicts for persistence later
                    for e in getattr(res, "entities", []) or []:
                        all_entities.append({"id": e.id, "type": e.type, "name": e.name, "properties": e.properties or {}})
                    for r in getattr(res, "relationships", []) or []:
                        all_relationships.append({"source_id": r.source_id, "target_id": r.target_id, "type": r.type, "properties": r.properties or {}})
                    await _update("llm_entities", f"Part {idx}: entities={len(getattr(res,'entities',[]) or [])} rels={len(getattr(res,'relationships',[]) or [])}")

                    # Facts extraction once over the same text
                    facts = await graph_processor._llm_extract_key_facts(  # type: ignore
                        project_id=project_id, document_content=text, filename=filename, correlation_id=corr_id, allow_chunking=False
                    )
                    if facts:
                        all_facts.extend(facts)

                # Deduplicate entities/relationships/facts
                def _dedup_entities(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
                    seen: set = set()
                    out: List[Dict[str, Any]] = []
                    for it in items:
                        key = (str(it.get("type","")), str(it.get("name",""))).__str__().lower()
                        if key in seen:
                            continue
                        seen.add(key)
                        out.append(it)
                    return out

                def _dedup_relationships(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
                    seen: set = set()
                    out: List[Dict[str, Any]] = []
                    for it in items:
                        key = (str(it.get("source_id","")), str(it.get("target_id","")), str(it.get("type",""))).__str__().lower()
                        if key in seen:
                            continue
                        seen.add(key)
                        out.append(it)
                    return out

                def _dedup_facts(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
                    seen: set = set()
                    out: List[Dict[str, Any]] = []
                    for it in items:
                        text = str(it.get("text",""))
                        k = text.strip().lower()
                        if not k or k in seen:
                            continue
                        seen.add(k)
                        # normalize category
                        try:
                            it["category"] = graph_processor._normalize_fact_category(str(it.get("category","infrastructure")))  # type: ignore
                        except Exception:
                            it["category"] = "infrastructure"
                        out.append(it)
                    return out

                ents_d = _dedup_entities(all_entities)
                rels_d = _dedup_relationships(all_relationships)
                facts_d = _dedup_facts(all_facts)

                await _update("merge", f"Merged entities={len(ents_d)} rels={len(rels_d)} facts={len(facts_d)}")

                # Persist entities/relationships
                if ents_d or rels_d:
                    # Reuse GraphProcessor dataclasses for upsert
                    try:
                        from app.core.graph_processor import Entity as _E, Relationship as _R, EntityExtractionResult as _Rsl
                        e_objs = [_E(id=e["id"], type=e["type"], name=e["name"], properties=e.get("properties") or {}) for e in ents_d]
                        r_objs = [_R(source_id=r["source_id"], target_id=r["target_id"], type=r["type"], properties=r.get("properties") or {}) for r in rels_d]
                        meta = {"extraction_timestamp": datetime.utcnow().isoformat(), "strategy": "unified_extractor", "parts": len(parts)}
                        rsl = _Rsl(project_id=project_id, document_id=request.document_id, entities=e_objs, relationships=r_objs, metadata=meta)
                        await graph_processor.add_entities_to_graph(project_id, rsl)
                        await _update("persist_graph", f"Persisted entities={len(e_objs)} rels={len(r_objs)}")
                    except Exception as pe:
                        await _update("persist_graph_failed", f"Graph upsert failed: {pe}")

                # Persist facts as Discovery nodes exactly once for this document
                if facts_d:
                    try:
                        await graph_processor._store_discovery_nodes(project_id, request.document_id, facts_d, request.filename)  # type: ignore
                        await _update("persist_facts", f"Stored facts={len(facts_d)}")
                    except Exception as fe:
                        await _update("persist_facts_failed", f"Store facts failed: {fe}")

                # Finalize
                await _update("completed", "Unified extraction finished", {
                    "status": "succeeded",
                    "finished_at": datetime.utcnow().isoformat(),
                    "entities_found": len(ents_d),
                    "relationships_found": len(rels_d),
                    "facts_found": len(facts_d),
                    "summary": {
                        "parts": len(parts),
                        "filename": request.filename,
                        "rows": len(rows),
                    },
                })
            except Exception as e:
                logger.error(f"Unified extractor job failed job={job_id}: {e}")
                await _update("failed", "Job failed", {"status": "failed", "error": str(e), "finished_at": datetime.utcnow().isoformat()})

        background_tasks.add_task(_run_unified_job)

        payload = UnifiedExtractJobResponse(
            job_id=job_id,
            status="queued",
            project_id=project_id,
            document_id=request.document_id,
            filename=request.filename,
            queued_at=enqueued_at,
        )
        return JSONResponse(status_code=202, content=payload.dict())
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to enqueue unified extraction: {e}")
        raise HTTPException(status_code=500, detail="Failed to enqueue unified extraction")

@router.get("/projects/{project_id}/stats", response_model=GraphStatsResponse)
async def get_graph_stats(
    project_id: str,
    graph_processor = Depends(get_graph_processor)
):
    """
    Get comprehensive graph statistics for a project
    
    Returns node counts, relationship counts, and breakdown by types.
    Useful for project dashboards and monitoring.
    """
    try:
        stats = await graph_processor.get_graph_stats(project_id)
        
        return GraphStatsResponse(
            project_id=project_id,
            total_nodes=stats.total_nodes,
            total_relationships=stats.total_relationships,
            node_types=stats.node_types,
            relationship_types=stats.relationship_types,
            last_updated=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Failed to get stats for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve graph statistics")

@router.get("/projects/{project_id}/graph/ui-minimal", response_model=UiMinimalGraphResponse)
async def get_ui_minimal_graph(
    project_id: str,
    include_types: Optional[str] = Query(None, description="Comma-separated list of types to include"),
    exclude_types: Optional[str] = Query(None, description="Comma-separated list of types to exclude"),
    hide_system: bool = Query(True, description="Hide system/internal nodes like structured_doc_*, Chunk/Page/Table, GUID-like"),
    include_inferred_has_ip: bool = Query(False, description="Derive Server→IP edges from Discovery co-mentions (UI only, no DB writes)"),
    graph_processor = Depends(get_graph_processor),
):
    """Return a UI-optimized minimal graph for the project.

    This endpoint filters out internal nodes and returns simplified nodes/edges for rendering.
    """
    try:
        inc = [s.strip() for s in include_types.split(",")] if include_types else None
        exc = [s.strip() for s in exclude_types.split(",")] if exclude_types else None
        data = await graph_processor.get_ui_minimal_graph(
            project_id,
            include_types=inc,
            exclude_types=exc,
            hide_system=hide_system,
            include_has_ip=True,
            include_inferred_has_ip=include_inferred_has_ip,
        )
        return UiMinimalGraphResponse(**data)
    except Exception as e:
        logger.error(f"Failed to get ui-minimal graph for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve ui-minimal graph")

@router.get("/projects/{project_id}/graph/ui-minimal/has-ip-count")
async def get_ui_minimal_has_ip_count(
    project_id: str,
    include_inferred_has_ip: bool = Query(False, description="Derive Server→IP edges from Discovery co-mentions (UI only, no DB writes)"),
    graph_processor = Depends(get_graph_processor),
):
    """Lightweight helper: return HAS_IP edge count in the ui-minimal graph.

    Useful for validation and smoke tests without fetching the full payload.
    """
    try:
        data = await graph_processor.get_ui_minimal_graph(
            project_id,
            include_types=None,
            exclude_types=None,
            hide_system=True,
            include_has_ip=True,
            include_inferred_has_ip=include_inferred_has_ip,
        )
        edges = data.get("edges", []) or []
        has_ip_count = sum(1 for e in edges if (e.get("label") or "").strip() == "HAS_IP")
        return {"project_id": project_id, "has_ip": has_ip_count, "total_edges": len(edges), "inferred": bool(include_inferred_has_ip)}
    except Exception as e:
        logger.error(f"Failed to compute HAS_IP count for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to compute HAS_IP count")

@router.delete("/projects/{project_id}/graph")
async def delete_project_graph(
    project_id: str,
    graph_processor = Depends(get_graph_processor)
):
    """
    Delete all graph data for a project
    
    Removes all nodes, relationships, and cached data for the specified project.
    This operation is irreversible.
    """
    try:
        # Optional RBAC header enforcement
        from fastapi import Request as _Req
        # FastAPI injects only if parameter present, so we pull using starlette context via router is non-trivial here.
        # Instead, rely on endpoints below which do have Request param. This delete remains open.
        result = await graph_processor.delete_project_graph(project_id)
        
        return {
            "message": f"Graph data deleted for project {project_id}",
            "nodes_deleted": result["nodes_deleted"],
            "timestamp": result["timestamp"]
        }
        
    except Exception as e:
        logger.error(f"Failed to delete graph for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete project graph")

@router.get("/projects/{project_id}/topology")
async def get_infrastructure_topology(
    project_id: str,
    include_technologies: bool = True,
    graph_processor = Depends(get_graph_processor)
):
    """
    Get infrastructure topology for visualization
    
    Returns a simplified graph structure optimized for network diagrams
    and infrastructure visualization tools.
    """
    try:
        # Get the complete graph
        graph_data = await graph_processor.get_project_graph(project_id)
        
        # Filter nodes for infrastructure topology
        infrastructure_nodes = []
        for node in graph_data["nodes"]:
            node_labels = node.get("labels", [])
            if any(label in ["Server", "Application", "Database"] for label in node_labels):
                infrastructure_nodes.append({
                    "id": node["id"],
                    "name": node.get("name", "Unknown"),
                    "type": node_labels[0] if node_labels else "Unknown",
                    "properties": node
                })
            elif include_technologies and "Technology" in node_labels:
                infrastructure_nodes.append({
                    "id": node["id"],
                    "name": node.get("name", "Unknown"),
                    "type": "Technology",
                    "properties": node
                })
        
        # Filter relationships for infrastructure
        infrastructure_relationships = []
        node_ids = {node["id"] for node in infrastructure_nodes}
        
        for rel in graph_data["relationships"]:
            if rel["source_id"] in node_ids and rel["target_id"] in node_ids:
                infrastructure_relationships.append({
                    "source": rel["source_id"],
                    "target": rel["target_id"],
                    "type": rel["type"],
                    "properties": rel
                })
        
        return {
            "project_id": project_id,
            "topology": {
                "nodes": infrastructure_nodes,
                "relationships": infrastructure_relationships
            },
            "stats": {
                "servers": len([n for n in infrastructure_nodes if n["type"] == "Server"]),
                "applications": len([n for n in infrastructure_nodes if n["type"] == "Application"]),
                "databases": len([n for n in infrastructure_nodes if n["type"] == "Database"]),
                "technologies": len([n for n in infrastructure_nodes if n["type"] == "Technology"]),
                "connections": len(infrastructure_relationships)
            },
            "timestamp": serialize_neo4j_value(datetime.utcnow())
        }
        
    except Exception as e:
        logger.error(f"Failed to get topology for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve infrastructure topology")

@router.get("/projects/{project_id}/nodes/search", response_model=GraphNodeSearchResponse)
async def search_project_nodes(
    project_id: str,
    q: str = Query(..., description="Case-insensitive substring to search in node names"),
    node_type: Optional[str] = Query(None, description="Optional node label/type to filter"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results to return"),
    graph_processor = Depends(get_graph_processor)
):
    """Search nodes by name substring within a project with optional type filter."""
    try:
        results = await graph_processor.search_nodes_by_name(project_id, q, node_type=node_type, limit=limit)
        return GraphNodeSearchResponse(
            project_id=project_id,
            query=q,
            node_type=node_type,
            limit=limit,
            results=results,
        )
    except Exception as e:
        logger.error(f"Failed to search nodes for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to search nodes")

@router.get("/projects/{project_id}/relationships/search", response_model=GraphRelationshipSearchResponse)
async def search_project_relationships(
    project_id: str,
    rel_type: Optional[str] = Query(None, description="Relationship type to filter (e.g., HOSTS, CONNECTS_TO)"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of results to return"),
    graph_processor = Depends(get_graph_processor)
):
    """Search relationships within a project by type."""
    try:
        results = await graph_processor.search_relationships(project_id, rel_type=rel_type, limit=limit)
        return GraphRelationshipSearchResponse(
            project_id=project_id,
            rel_type=rel_type,
            limit=limit,
            results=results,
        )
    except Exception as e:
        logger.error(f"Failed to search relationships for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to search relationships")

@router.post("/projects/{project_id}/query/nl2cypher", response_model=NL2CypherResponse)
async def nl2cypher_build(project_id: str, request: NL2CypherRequest, graph_processor = Depends(get_graph_processor)):
    """Build a safe, read-only, project-scoped Cypher from NL using heuristics/templates.

    This endpoint does not execute the query; it only assembles and returns Cypher + params.
    Also instruments basic metrics in Redis (build attempts/success).
    """
    # Import helper with robust path handling: prefer absolute repo-level `common`, fallback to relative
    try:
        from common.nl2cypher import build_cypher_from_nl  # type: ignore
    except Exception:
        try:
            from ...common.nl2cypher import build_cypher_from_nl  # type: ignore
        except Exception:
            raise HTTPException(status_code=500, detail="nl2cypher helper unavailable")
    # Instrument attempts
    try:
        r = getattr(graph_processor, "redis_client", None)
        if r is not None:
            await r.incr(f"metrics:{project_id}:nl2c:build_attempts")
    except Exception:
        pass
    try:
        cy = build_cypher_from_nl(request.nl, project_id, limit=request.limit)
        params = {"pid": project_id, "lim": request.limit}
        # Instrument success
        try:
            r = getattr(graph_processor, "redis_client", None)
            if r is not None:
                await r.incr(f"metrics:{project_id}:nl2c:build_success")
        except Exception:
            pass
        return NL2CypherResponse(project_id=project_id, nl=request.nl, cypher=cy, parameters=params)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"nl2cypher_build failed: {e}")
        # instrument failure
        try:
            r = getattr(graph_processor, "redis_client", None)
            if r is not None:
                await r.incr(f"metrics:{project_id}:nl2c:build_failure")
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="failed to build cypher")

@router.post("/projects/{project_id}/query/run", response_model=RunCypherResponse)
async def nl2cypher_run(project_id: str, request: RunCypherRequest, graph_processor = Depends(get_graph_processor)):
    """Execute a read-only, project-scoped Cypher with EXPLAIN validation.

    - Sanitizes user-provided Cypher to enforce read-only + project scope
    - Validates via EXPLAIN before execution
    - Returns rows/columns only (no writes)
    Also instruments run attempts/success and pass rate in Redis.
    """
    # Import helper with robust path handling: prefer absolute repo-level `common`, fallback to relative
    try:
        from common.nl2cypher import sanitize_readonly_cypher  # type: ignore
    except Exception:
        try:
            from ...common.nl2cypher import sanitize_readonly_cypher  # type: ignore
        except Exception:
            raise HTTPException(status_code=500, detail="nl2cypher helper unavailable")
    # Instrument attempts
    try:
        r = getattr(graph_processor, "redis_client", None)
        if r is not None:
            await r.incr(f"metrics:{project_id}:nl2c:run_attempts")
    except Exception:
        pass
    # Sanitize and validate
    try:
        cypher = sanitize_readonly_cypher(request.cypher, project_id, limit=request.limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    params = {"pid": project_id, "lim": request.limit}
    try:
        async with graph_processor.neo4j_driver.session() as session:  # type: ignore
            # Validate plan with one quick retry on transient failure
            try:
                await session.run("EXPLAIN " + cypher, **params)
            except Exception:
                try:
                    import asyncio
                    await asyncio.sleep(0.2)
                    await session.run("EXPLAIN " + cypher, **params)
                except Exception:
                    raise
            # Execute
            res = await session.run(cypher, **params)
            cols = res.keys()
            rows: List[Dict[str, Any]] = []
            async for rec in res:
                rows.append({k: serialize_neo4j_value(rec.get(k)) for k in cols})
        # Instrument success and pass rate
        try:
            r = getattr(graph_processor, "redis_client", None)
            if r is not None:
                await r.incr(f"metrics:{project_id}:nl2c:run_success")
                # Compute pass rate = run_success / max(run_attempts,1)
                attempts_raw = await r.get(f"metrics:{project_id}:nl2c:run_attempts")
                success_raw = await r.get(f"metrics:{project_id}:nl2c:run_success")
                try:
                    attempts = float(attempts_raw.decode()) if attempts_raw else 0.0
                except Exception:
                    attempts = 0.0
                try:
                    success = float(success_raw.decode()) if success_raw else 0.0
                except Exception:
                    success = 0.0
                pr = (success / attempts) if attempts > 0 else 0.0
                await r.set(f"metrics:{project_id}:nl2c:pass_rate", str(pr))
        except Exception:
            pass
        return RunCypherResponse(project_id=project_id, rows=rows, columns=list(cols), stats={"count": len(rows)})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"nl2cypher_run failed: {e}")
        # instrument failure
        try:
            r = getattr(graph_processor, "redis_client", None)
            if r is not None:
                await r.incr(f"metrics:{project_id}:nl2c:run_failure")
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="cypher execution failed")

@router.get("/projects/{project_id}/metrics")
async def project_metrics(project_id: str, graph_processor = Depends(get_graph_processor)):
    """Return simple metrics for the project (best-effort, accumulators in Redis).

    Metrics exposed:
    - extraction_yield (documents processed / discoveries) [placeholder]
    - link_coverage (entities with REFERS_TO / total entities)
    - nl2cypher_pass_rate (run_success / run_attempts)
    - schema_conformance (placeholder percent)
    """
    try:
        r = getattr(graph_processor, "redis_client", None)
        async def getf(key: str) -> float:
            try:
                if r is None:
                    return 0.0
                v = await r.get(key)
                if v is None:
                    return 0.0
                try:
                    return float(v.decode())
                except Exception:
                    return float(v)
            except Exception:
                return 0.0
        # Calculate coverage from Neo4j quickly
        link_cov = 0.0
        try:
            async with graph_processor.neo4j_driver.session() as session:  # type: ignore
                ent = await (await session.run(
                    "MATCH (p:Project {id:$pid})-[:CONTAINS]->(e:Entity) RETURN count(e) as c", pid=project_id)).single()
                linked = await (await session.run(
                    "MATCH (p:Project {id:$pid})-[:CONTAINS]->(:Entity)-[:REFERS_TO]->(:CanonicalEntity) RETURN count(*) as c", pid=project_id)).single()
                e_total = float(ent.get("c", 0) if ent else 0)
                e_linked = float(linked.get("c", 0) if linked else 0)
                link_cov = (e_linked / e_total) if e_total > 0 else 0.0
        except Exception:
            pass
        # Prefer stored pass_rate; fall back to recompute if needed
        pr = await getf(f"metrics:{project_id}:nl2c:pass_rate")
        if pr == 0.0:
            try:
                if r is not None:
                    a = await r.get(f"metrics:{project_id}:nl2c:run_attempts")
                    s = await r.get(f"metrics:{project_id}:nl2c:run_success")
                    attempts = float(a.decode()) if a else 0.0
                    success = float(s.decode()) if s else 0.0
                    pr = (success / attempts) if attempts > 0 else 0.0
            except Exception:
                pr = 0.0
        return {
            "project_id": project_id,
            "extraction_yield": await getf(f"metrics:{project_id}:extraction_yield"),
            "link_coverage": link_cov,
            "nl2cypher_pass_rate": pr,
            "schema_conformance": await getf(f"metrics:{project_id}:schema_conformance"),
        }
    except Exception as e:
        logger.error(f"metrics failed: {e}")
        raise HTTPException(status_code=500, detail="metrics failed")

@router.get("/projects/{project_id}/neighborhood", response_model=GraphNeighborhoodResponse)
async def get_project_neighborhood(
    project_id: str,
    node_id: str = Query(..., description="Center node id"),
    depth: int = Query(1, ge=0, le=3, description="Traversal depth (hops)"),
    direction: str = Query("both", description="Direction: out|in|both"),
    rel_types: Optional[str] = Query(None, description="Comma-separated relationship types to include"),
    limit: int = Query(200, ge=1, le=1000, description="Limit on paths to explore"),
    graph_processor = Depends(get_graph_processor)
):
    """Return a neighborhood subgraph around a node within the project."""
    try:
        types_list = [t.strip().upper() for t in rel_types.split(",")] if rel_types else None
        sub = await graph_processor.get_neighborhood(
            project_id, node_id=node_id, depth=depth, rel_types=types_list, direction=direction, limit=limit
        )
        return GraphNeighborhoodResponse(
            project_id=project_id,
            node_id=node_id,
            depth=depth,
            direction=direction,
            rel_types=types_list,
            nodes=sub.get("nodes", []),
            relationships=sub.get("relationships", []),
        )
    except Exception as e:
        logger.error(f"Failed to get neighborhood for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve neighborhood")

@router.get("/projects/{project_id}/counts/nodes", response_model=CountResponse)
async def count_project_nodes(
    project_id: str,
    node_type: Optional[str] = Query(None, description="Optional node type/label to filter (e.g., Server, Application)"),
    graph_processor = Depends(get_graph_processor)
):
    """Return count of nodes within a project, optionally filtered by type."""
    try:
        cnt = await graph_processor.count_nodes(project_id, node_type=node_type)
        return CountResponse(project_id=project_id, count=cnt)
    except Exception as e:
        logger.error(f"Failed to count nodes for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to count nodes")

@router.get("/projects/{project_id}/counts/servers/by-os", response_model=CountResponse)
async def count_project_servers_by_os(
    project_id: str,
    q: str = Query(..., description="Case-insensitive substring to match OS name (e.g., 'windows')"),
    graph_processor = Depends(get_graph_processor)
):
    """Return count of Server nodes whose OS matches the provided substring.

    Matches either a direct `n.os` property or via a `(s:Server)-[:RUNS_ON]->(os:OS)` relationship by `os.name`.
    """
    try:
        cnt = await graph_processor.count_servers_by_os(project_id, os_query=q)
        return CountResponse(project_id=project_id, count=cnt)
    except Exception as e:
        logger.error(f"Failed to count servers by OS for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to count servers by OS")

@router.get("/projects/{project_id}/pyvis", response_model=PyvisGraphResponse)
async def get_pyvis_graph(
    project_id: str,
    graph_processor = Depends(get_graph_processor)
):
    """Return PyVis/vis-network friendly graph data for the project."""
    try:
        data = await graph_processor.get_pyvis_data(project_id)
        return PyvisGraphResponse(**data)
    except Exception as e:
        logger.error(f"Failed to get pyvis data for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve pyvis graph data")

@router.post("/projects/{project_id}/maintenance/materialize-ip-edges", response_model=MaintenanceResult)
async def materialize_ip_edges(project_id: str, graph_processor = Depends(get_graph_processor)):
    """Create IP nodes and HAS_IP relationships from Server.ip_address properties.

    This is a safe, idempotent maintenance endpoint to backfill IP nodes/edges
    when ingestion has stored IPs only as server properties.
    """
    try:
        created_nodes = 0
        created_rels = 0
        import re
        async with graph_processor.neo4j_driver.session() as session:  # type: ignore
            # Fetch servers with ip_address property under this project
            cy_fetch = (
                """
                MATCH (p:Project {id:$pid})-[:CONTAINS]->(s:Server)
                WHERE s.ip_address IS NOT NULL AND toString(s.ip_address) <> ''
                RETURN s.id as sid, s.name as sname, toString(s.ip_address) as ip
                """
            )
            res = await session.run(cy_fetch, pid=project_id)
            servers: List[Dict[str, str]] = []
            async for rec in res:
                servers.append({"sid": rec.get("sid"), "sname": rec.get("sname"), "ip": rec.get("ip")})
        # Build Cypher batches to MERGE IP nodes and HAS_IP edges
        ip_merge_q = (
            """
            MATCH (p:Project {id:$pid})
            MATCH (s:Server {id:$sid})
            MERGE (ip:Entity:IP {id:$ipid})
              ON CREATE SET ip.name=$ipval, ip.type='IP', ip.created_at=datetime()
              ON MATCH  SET ip.name=coalesce(ip.name, $ipval), ip.type=coalesce(ip.type, 'IP')
            MERGE (p)-[:CONTAINS]->(ip)
            MERGE (s)-[r:HAS_IP]->(ip)
                            ON CREATE SET r.created_at=datetime()
                        RETURN r.created_at IS NOT NULL as created_rel
            """
        )
        ipv4_re = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")
        ipv6_re = re.compile(r"^[0-9A-Fa-f:]{2,}$")
        async with graph_processor.neo4j_driver.session() as session:  # type: ignore
            for sv in servers:
                raw = (sv.get("ip") or "").strip()
                if not raw:
                    continue
                tokens = [t.strip() for t in re.split(r"[,|;/\s]+", raw) if t.strip()]
                for ip in tokens:
                    if not (ipv4_re.match(ip) or ipv6_re.match(ip)):
                        continue
                    ipid = f"ip:{ip.lower()}"
                    rec = await (await session.run(ip_merge_q, pid=project_id, sid=sv.get("sid"), ipid=ipid, ipval=ip)).single()
                    # We can't reliably detect node creation here without additional RETURNs; count rel creation
                    if rec and rec.get("created_rel"):
                        created_rels += 1
                    # Count node existence by attempting a node fetch
                    chk = await (await session.run("MATCH (n:IP {id:$id}) RETURN count(n) as c", id=ipid)).single()
                    if chk and int(chk.get("c") or 0) == 1:
                        created_nodes += 0  # do not double count across multiple servers
        return MaintenanceResult(project_id=project_id, created_nodes=created_nodes, created_relationships=created_rels)
    except Exception as e:
        logger.error(f"IP materialization failed for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="IP materialization failed")

@router.post("/projects/{project_id}/maintenance/materialize-from-text", response_model=MaintenanceResult)
async def materialize_from_text(
    project_id: str,
    include_ip: bool = Query(True, description="Extract IP addresses from discovery text"),
    include_os: bool = Query(True, description="Extract Operating Systems from discovery text"),
    include_env: bool = Query(True, description="Extract Environments (DEV/UAT/PROD etc.) from discovery text"),
    include_location: bool = Query(True, description="Extract Locations/Regions/Datacenters from discovery text"),
    link_to_assets: bool = Query(True, description="Attempt to link extracted items to existing Server/Application nodes using name heuristics"),
    graph_processor = Depends(get_graph_processor)
):
    """Parse Discovery text facts to materialize canonical nodes (IP/OS/Environment/Location),
    create MENTIONS links from discoveries, and best-effort attach edges to assets.

    Safe and idempotent: MERGE operations only; relationships carry provenance properties.
    """
    try:
        import re
        created_nodes = 0
        created_rels = 0

        # Compile regexes
        ipv4_re = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")
        # Simple OS indicators
        os_patterns = [
            r"windows server\s*\d{2,4}", r"windows\s*\d{2,4}", r"win(?:dows)?\b",
            r"rhel\s*\d+(?:\.\d+)?", r"red\s*hat", r"centos\s*\d+", r"ubuntu\s*\d+\.?\d*",
            r"debian\s*\d+\.?\d*", r"suse\b|sles\b", r"aix\s*\d+\.?\d*", r"solaris\b"
        ]
        os_re = re.compile("|".join(os_patterns), re.IGNORECASE)
        # Environment names (word boundaries, various cases)
        env_terms = ["dev","development","test","qa","sit","uat","preprod","pp","prod","production","dr","staging"]
        env_re = re.compile(r"\b(" + "|".join(env_terms) + r")\b", re.IGNORECASE)
        # Location/Region/DC heuristics
        loc_patterns = [r"datacenter|data\s*center|dc-?\w+", r"region\s*[:\-]?\s*\w+", r"\b(us|eu|apac|emea|in|uk|au)-?\w*\b", r"mumbai|pune|delhi|bangalore|bengaluru|hyd(erabad)?|chennai|gurgaon|noida|london|frankfurt|paris|dubai|tokyo|sydney|singapore"]
        loc_re = re.compile("|".join(loc_patterns), re.IGNORECASE)

        # Preload assets for heuristic linking
        servers: List[Dict[str, Any]] = []
        applications: List[Dict[str, Any]] = []
        async with graph_processor.neo4j_driver.session() as session:  # type: ignore
            # Collect discoveries for this project
            cy_discoveries = (
                """
                MATCH (p:Project {id:$pid})-[:CONTAINS]->(d:Document)-[:CONTAINS_DISCOVERY]->(dis:Discovery)
                RETURN dis.id as did, dis.text as text, d.id as doc_id, d.filename as filename
                """
            )
            dres = await session.run(cy_discoveries, pid=project_id)
            discoveries = []
            async for rec in dres:
                discoveries.append({
                    "did": rec.get("did"),
                    "text": rec.get("text") or "",
                    "doc_id": rec.get("doc_id"),
                    "filename": rec.get("filename"),
                })

            if link_to_assets:
                cy_assets = (
                    """
                    MATCH (p:Project {id:$pid})-[:CONTAINS]->(n:Server)
                    RETURN n.id as id, n.name as name
                    """
                )
                sres = await session.run(cy_assets, pid=project_id)
                async for rec in sres:
                    servers.append({"id": rec.get("id"), "name": rec.get("name") or ""})
                cy_apps = (
                    """
                    MATCH (p:Project {id:$pid})-[:CONTAINS]->(n:Application)
                    RETURN n.id as id, n.name as name
                    """
                )
                ares = await session.run(cy_apps, pid=project_id)
                async for rec in ares:
                    applications.append({"id": rec.get("id"), "name": rec.get("name") or ""})

        if not discoveries:
            return MaintenanceResult(project_id=project_id, created_nodes=0, created_relationships=0, details={"message": "no discoveries"})

        # Helper Cypher
        cy_merge_ip = (
            """
            MATCH (p:Project {id:$pid})
            MERGE (ip:Entity:IP {id:$id})
              ON CREATE SET ip.name=$name, ip.type='IP', ip.created_at=datetime()
            MERGE (p)-[:CONTAINS]->(ip)
            RETURN 1 as ok
            """
        )
        cy_merge_os = (
            """
            MATCH (p:Project {id:$pid})
            MERGE (o:Entity:OS {id:$id})
              ON CREATE SET o.name=$name, o.type='OS', o.created_at=datetime()
            MERGE (p)-[:CONTAINS]->(o)
            RETURN 1 as ok
            """
        )
        cy_merge_env = (
            """
            MATCH (p:Project {id:$pid})
            MERGE (e:Entity:Environment {id:$id})
              ON CREATE SET e.name=$name, e.type='Environment', e.created_at=datetime()
            MERGE (p)-[:CONTAINS]->(e)
            RETURN 1 as ok
            """
        )
        cy_merge_loc = (
            """
            MATCH (p:Project {id:$pid})
            MERGE (l:Entity:Location {id:$id})
              ON CREATE SET l.name=$name, l.type='Location', l.created_at=datetime()
            MERGE (p)-[:CONTAINS]->(l)
            RETURN 1 as ok
            """
        )
        cy_link_mentions = (
            """
            MATCH (dis:Discovery {id:$did})
            MATCH (n {id:$nid})
            MERGE (dis)-[r:MENTIONS]->(n)
                            ON CREATE SET r.created_at=datetime(), r.provenance=$prov
                        RETURN r.created_at IS NOT NULL as created
            """
        )
        cy_link_has_ip = (
            """
            MATCH (s:Server {id:$sid})
            MATCH (ip:IP {id:$iid})
            MERGE (s)-[r:HAS_IP]->(ip)
                            ON CREATE SET r.created_at=datetime(), r.provenance=$prov
                        RETURN r.created_at IS NOT NULL as created
            """
        )
        cy_link_runs_on = (
            """
            MATCH (s:Server {id:$sid})
            MATCH (o:OS {id:$oid})
            MERGE (s)-[r:RUNS_ON]->(o)
                            ON CREATE SET r.created_at=datetime(), r.provenance=$prov
                        RETURN r.created_at IS NOT NULL as created
            """
        )
        cy_link_has_env = (
            """
            MATCH (a:Application {id:$aid})
            MATCH (e:Environment {id:$eid})
            MERGE (a)-[r:HAS_ENV]->(e)
                            ON CREATE SET r.created_at=datetime(), r.provenance=$prov
                        RETURN r.created_at IS NOT NULL as created
            """
        )
        cy_link_located_in = (
            """
            MATCH (s:Server {id:$sid})
            MATCH (l:Location {id:$lid})
            MERGE (s)-[r:LOCATED_IN]->(l)
                            ON CREATE SET r.created_at=datetime(), r.provenance=$prov
                        RETURN r.created_at IS NOT NULL as created
            """
        )

        # Utility: find best single asset match by name token presence
        def find_asset(text: str, assets: List[Dict[str, Any]]) -> Optional[str]:
            """Heuristic link: find best single asset id whose name appears in text.

            - Case-insensitive, prefer exact token match (word boundaries)
            - Fallback: normalized hostnames (strip domain), partial token match for names >= 4 chars
            - Returns a single id only when unambiguous
            """
            if not text or not assets:
                return None
            t = (text or "").lower()
            # Quick token set for loose contains
            tokens = set(re.findall(r"[a-z0-9._-]+", t))
            candidates: List[str] = []
            scores: Dict[str, int] = {}

            def norm_host(n: str) -> str:
                n = (n or "").lower().strip()
                if not n:
                    return n
                # strip domain if present
                if "." in n:
                    n = n.split(".")[0]
                return n

            for a in assets:
                nm_raw = (a.get("name") or "").strip()
                if not nm_raw:
                    continue
                nm = nm_raw.lower()
                # 1) Exact token match
                pattern = r"\b" + re.escape(nm) + r"\b"
                if re.search(pattern, t):
                    candidates.append(a.get("id"))
                    scores[a.get("id")] = scores.get(a.get("id"), 0) + 3
                    continue
                # 2) Hostname-normalized token
                host = norm_host(nm)
                if host and host != nm:
                    pattern2 = r"\b" + re.escape(host) + r"\b"
                    if re.search(pattern2, t):
                        candidates.append(a.get("id"))
                        scores[a.get("id")] = scores.get(a.get("id"), 0) + 2
                        continue
                # 3) Partial token match for names >=4 chars
                if len(nm) >= 4 and nm in " ".join(tokens):
                    candidates.append(a.get("id"))
                    scores[a.get("id")] = scores.get(a.get("id"), 0) + 1

            # Choose the highest score if unique
            if not candidates:
                return None
            # Aggregate by id
            best_id = None
            best_score = -1
            ties = 0
            for cid in set(candidates):
                sc = scores.get(cid, 0)
                if sc > best_score:
                    best_score = sc
                    best_id = cid
                    ties = 1
                elif sc == best_score:
                    ties += 1
            if best_id and ties == 1:
                return best_id
            return None

        # Process discoveries
        async with graph_processor.neo4j_driver.session() as session:  # type: ignore
            # Ensure Project node exists
            await session.run("MERGE (p:Project {id:$pid}) ON CREATE SET p.created_at=datetime()", pid=project_id)
            for dis in discoveries:
                text = dis.get("text") or ""
                did = dis.get("did")
                provenance = {"source": "discovery_text", "discovery_id": did, "doc_id": dis.get("doc_id"), "filename": dis.get("filename")}
                try:
                    prov_str = json.dumps(provenance)
                except Exception:
                    prov_str = str(provenance)

                # IPs
                if include_ip:
                    ips = set(ipv4_re.findall(text))
                    for ip in ips:
                        ipid = f"ip:{ip.lower()}"
                        await session.run(cy_merge_ip, pid=project_id, id=ipid, name=ip)
                        created_nodes += 0  # nodes are merged; avoid overcount
                        rec = await (await session.run(cy_link_mentions, did=did, nid=ipid, prov=prov_str)).single()
                        if rec and rec.get("created"):
                            created_rels += 1
                        # Connect discovery to project to ensure project-scoped queries include its relationships
                        try:
                            await session.run("MATCH (p:Project {id:$pid}),(dis:Discovery {id:$did}) MERGE (p)-[:CONTAINS]->(dis)", pid=project_id, did=did)
                        except Exception:
                            pass
                        if link_to_assets:
                            sid = find_asset(text, servers)
                            if sid:
                                rec2 = await (await session.run(cy_link_has_ip, sid=sid, iid=ipid, prov=prov_str)).single()
                                if rec2 and rec2.get("created"):
                                    created_rels += 1
                                # Also record that this discovery mentions the server asset explicitly
                                try:
                                    rec2m = await (await session.run(cy_link_mentions, did=did, nid=sid, prov=prov_str)).single()
                                    if rec2m and rec2m.get("created"):
                                        created_rels += 1
                                except Exception:
                                    pass

                # OS
                if include_os:
                    m = os_re.findall(text)
                    for raw in set([s if isinstance(s, str) else (s[0] if s else "") for s in m]):
                        os_name = raw.strip()
                        if not os_name:
                            continue
                        norm = re.sub(r"\s+", " ", os_name).strip().lower()
                        oid = f"os:{norm}"
                        await session.run(cy_merge_os, pid=project_id, id=oid, name=os_name)
                        rec = await (await session.run(cy_link_mentions, did=did, nid=oid, prov=prov_str)).single()
                        if rec and rec.get("created"):
                            created_rels += 1
                        try:
                            await session.run("MATCH (p:Project {id:$pid}),(dis:Discovery {id:$did}) MERGE (p)-[:CONTAINS]->(dis)", pid=project_id, did=did)
                        except Exception:
                            pass
                        if link_to_assets:
                            sid = find_asset(text, servers)
                            if sid:
                                rec2 = await (await session.run(cy_link_runs_on, sid=sid, oid=oid, prov=prov_str)).single()
                                if rec2 and rec2.get("created"):
                                    created_rels += 1
                                # Also MENTION the server asset
                                try:
                                    rec2m = await (await session.run(cy_link_mentions, did=did, nid=sid, prov=prov_str)).single()
                                    if rec2m and rec2m.get("created"):
                                        created_rels += 1
                                except Exception:
                                    pass

                # Environment
                if include_env:
                    envs = set(env_re.findall(text))
                    for env in envs:
                        label = str(env).upper()
                        eid = f"environment:{label}"
                        await session.run(cy_merge_env, pid=project_id, id=eid, name=label)
                        rec = await (await session.run(cy_link_mentions, did=did, nid=eid, prov=prov_str)).single()
                        if rec and rec.get("created"):
                            created_rels += 1
                        try:
                            await session.run("MATCH (p:Project {id:$pid}),(dis:Discovery {id:$did}) MERGE (p)-[:CONTAINS]->(dis)", pid=project_id, did=did)
                        except Exception:
                            pass
                        if link_to_assets:
                            aid = find_asset(text, applications)
                            if aid:
                                rec2 = await (await session.run(cy_link_has_env, aid=aid, eid=eid, prov=prov_str)).single()
                                if rec2 and rec2.get("created"):
                                    created_rels += 1
                                # Also MENTION the application asset
                                try:
                                    rec2m = await (await session.run(cy_link_mentions, did=did, nid=aid, prov=prov_str)).single()
                                    if rec2m and rec2m.get("created"):
                                        created_rels += 1
                                except Exception:
                                    pass

                # Location
                if include_location:
                    locs = set(loc_re.findall(text))
                    for loc in locs:
                        # loc may be tuple if regex has groups
                        val = loc if isinstance(loc, str) else " ".join([p for p in loc if p])
                        val = re.sub(r"\s+", " ", val).strip()
                        if not val:
                            continue
                        lid = f"location:{val.lower()}"
                        await session.run(cy_merge_loc, pid=project_id, id=lid, name=val)
                        rec = await (await session.run(cy_link_mentions, did=did, nid=lid, prov=prov_str)).single()
                        if rec and rec.get("created"):
                            created_rels += 1
                        try:
                            await session.run("MATCH (p:Project {id:$pid}),(dis:Discovery {id:$did}) MERGE (p)-[:CONTAINS]->(dis)", pid=project_id, did=did)
                        except Exception:
                            pass
                        if link_to_assets:
                            sid = find_asset(text, servers)
                            if sid:
                                rec2 = await (await session.run(cy_link_located_in, sid=sid, lid=lid, prov=prov_str)).single()
                                if rec2 and rec2.get("created"):
                                    created_rels += 1
                                # Also MENTION the server asset
                                try:
                                    rec2m = await (await session.run(cy_link_mentions, did=did, nid=sid, prov=prov_str)).single()
                                    if rec2m and rec2m.get("created"):
                                        created_rels += 1
                                except Exception:
                                    pass

        # Invalidate caches for this project
        try:
            await graph_processor.redis_client.delete(f"project_graph:{project_id}")
            await graph_processor.redis_client.delete(f"graph_stats:{project_id}")
        except Exception:
            pass

        return MaintenanceResult(project_id=project_id, created_nodes=created_nodes, created_relationships=created_rels)
    except Exception as e:
        logger.error(f"materialize-from-text failed for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Text materialization failed")

@router.post("/projects/{project_id}/maintenance/materialize-canonical-relationships", response_model=MaintenanceResult)
async def materialize_canonical_relationships(
    project_id: str,
    min_support: int = Query(2, ge=1, le=1000, description="Minimum support (entity edges) to create/update canonical edge"),
    max_pairs: int = Query(1000, ge=1, le=10000, description="Max canonical pairs to process"),
    allow_types: Optional[str] = Query(None, description="Comma-separated whitelist of relationship types to consider (UPPER_SNAKE_CASE)"),
    dry_run: bool = Query(False, description="If true, returns a plan of changes without writing to the DB"),
    graph_processor = Depends(get_graph_processor),
    http_request: Request = None,
):
    """Promote entity-level relationships to canonical-level ones by aggregation.

    Aggregates (Entity)-[REL]->(Entity) edges into (CanonicalEntity)-[REL]->(CanonicalEntity), with support counts.
    """
    try:
        # Optional RBAC header enforcement
        _enforce_project_header(http_request, project_id)
        corr_id = None
        try:
            if http_request is not None:
                corr_id = http_request.headers.get("X-Correlation-ID")
        except Exception:
            pass
        _enforce_admin_role(http_request, dry_run)
        await _throttle_non_dry_run(graph_processor, project_id, dry_run)
        allow_list = None
        if allow_types:
            allow_list = [t.strip() for t in allow_types.split(",") if t.strip()]
        result = await graph_processor.materialize_canonical_relationships(
            project_id=project_id,
            min_support=int(min_support),
            max_pairs=int(max_pairs),
            allow_types=allow_list,
            dry_run=bool(dry_run),
            correlation_id=corr_id,
        )
        # Map to MaintenanceResult shape
        total = int(result.get("created", 0)) + int(result.get("updated", 0))
        out = MaintenanceResult(
            project_id=project_id,
            created_nodes=0,
            created_relationships=total,
            details={k: v for k, v in result.items() if k not in {"project_id"}},
        )
        try:
            await _audit_maintenance(graph_processor, project_id, {
                "dry_run": bool(dry_run),
                "action": "materialize-canonical-relationships",
                "params": {"min_support": int(min_support), "max_pairs": int(max_pairs), "allow_types": allow_list},
                "summary": {"created": int(result.get("created", 0)), "updated": int(result.get("updated", 0))},
            })
        except Exception:
            pass
        return out
    except Exception as e:
        logger.error(f"materialize-canonical-relationships failed for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Canonical relationship materialization failed")

@router.post("/projects/{project_id}/maintenance/materialize-refers-to", response_model=MaintenanceResult)
async def materialize_refers_to(
    project_id: str,
    min_score: float = Query(0.55, ge=0.0, le=1.0, description="Minimum vector score threshold for linking"),
    max_candidates: int = Query(5, ge=1, le=20, description="Max candidates to inspect per entity"),
    preferred_kind: str = Query("entity_cards", description="Preferred vector kind: entity_cards|raw_chunks|triple_cards"),
    use_hybrid: bool = Query(True, description="Use hybrid search when available"),
    dry_run: bool = Query(False, description="If true, returns a plan of links without writing to the DB"),
    graph_processor = Depends(get_graph_processor),
    http_request: Request = None,
):
    """Create REFERS_TO links from Entities to CanonicalEntity using vector-service search.

    Idempotent via MERGE; writes r.score and r.provenance (JSON string). Useful as a batch maintenance step
    after loading canonical entities and running the cards pipeline in vector-service.
    """
    try:
        # Optional RBAC header enforcement
        _enforce_project_header(http_request, project_id)
        corr_id = None
        try:
            if http_request is not None:
                corr_id = http_request.headers.get("X-Correlation-ID")
        except Exception:
            pass
        _enforce_admin_role(http_request, dry_run)
        await _throttle_non_dry_run(graph_processor, project_id, dry_run)
        result = await graph_processor.materialize_refers_to_links(
            project_id=project_id,
            min_score=float(min_score),
            max_candidates=int(max_candidates),
            preferred_kind=str(preferred_kind or "entity_cards"),
            use_hybrid=bool(use_hybrid),
            dry_run=bool(dry_run),
            correlation_id=corr_id,
        )
        # created_relationships approximates linked count
        out = MaintenanceResult(
            project_id=project_id,
            created_nodes=0,
            created_relationships=int(result.get("linked", 0)),
            details={k: v for k, v in result.items() if k not in {"project_id", "linked"}},
        )
        try:
            await _audit_maintenance(graph_processor, project_id, {
                "dry_run": bool(dry_run),
                "action": "materialize-refers-to",
                "params": {"min_score": float(min_score), "max_candidates": int(max_candidates), "preferred_kind": str(preferred_kind or "entity_cards"), "use_hybrid": bool(use_hybrid)},
                "summary": {"linked": int(result.get("linked", 0))},
            })
        except Exception:
            pass
        return out
    except Exception as e:
        logger.error(f"materialize-refers-to failed for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="REFERS_TO materialization failed")

@router.get("/debug/all-collections")
async def list_all_projects(graph_processor = Depends(get_graph_processor)):
    """
    Debug endpoint to list all projects in the graph database
    
    Returns a list of all projects with basic statistics.
    Useful for debugging and administrative tasks.
    """
    try:
        async with graph_processor.neo4j_driver.session() as session:
            result = await session.run(
                """
                MATCH (p:Project)
                OPTIONAL MATCH (p)-[:CONTAINS]->(n)
                RETURN p.id as project_id, 
                       p.created_at as created_at,
                       count(n) as node_count
                ORDER BY p.created_at DESC
                """
            )
            
            projects = []
            async for record in result:
                projects.append({
                    "project_id": record["project_id"],
                    "created_at": record["created_at"],
                    "node_count": record["node_count"]
                })
        
        return {
            "projects": projects,
            "total_projects": len(projects),
            "timestamp": serialize_neo4j_value(datetime.utcnow())
        }
        
    except Exception as e:
        logger.error(f"Failed to list projects: {e}")
        raise HTTPException(status_code=500, detail="Failed to list projects")

@router.get("/debug/cache-stats")
@router.get("/projects/{project_id}/maintenance/summary")
async def maintenance_summary(project_id: str, graph_processor = Depends(get_graph_processor)):
    try:
        summary = await graph_processor.get_maintenance_summary(project_id)
        return summary
    except Exception as e:
        logger.error(f"maintenance summary failed for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Maintenance summary failed")
async def get_cache_stats(graph_processor = Depends(get_graph_processor)):
    """
    Debug endpoint to get Redis cache statistics
    
    Returns information about cached data for debugging and monitoring.
    """
    try:
        # Get cache info from Redis
        cache_info = await graph_processor.redis_client.info('memory')
        
        # Get key counts by pattern
        cache_patterns = [
            "project_graph:*",
            "graph_stats:*", 
            "entities:*"
        ]
        
        key_counts = {}
        for pattern in cache_patterns:
            keys = await graph_processor.redis_client.keys(pattern)
            key_counts[pattern] = len(keys) if keys else 0
        
        return {
            "cache_memory_usage": cache_info.get('used_memory_human', 'Unknown'),
            "key_counts": key_counts,
            "cache_db": graph_processor.redis_db,
            "timestamp": serialize_neo4j_value(datetime.utcnow())
        }
        
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve cache statistics")

# =====================================================================================
# PVC STUB ENDPOINTS - Type Registry and Proposal lifecycle (return 501 for now)
# =====================================================================================

@router.get("/projects/{project_id}/types")
async def get_type_registry(project_id: str, graph_processor = Depends(get_graph_processor)):
    """Retrieve the project's Type Registry snapshot from Redis (temporary store).

    Redis keys used:
    - pvc:types:{project_id} -> JSON snapshot
    """
    try:
        pvc_store = (_os.getenv("PVC_STORE") or "redis").lower()
        if pvc_store == "postgres":
            try:
                from app.pvc_repo.repository import PVCRepository, init_db
                init_db()
                repo = PVCRepository()
                return repo.get_type_registry(project_id)
            except Exception as e:
                logger.error(f"PVC postgres get_type_registry failed, falling back to redis: {e}")
        # Default: Redis
        key = f"pvc:types:{project_id}"
        raw = await graph_processor.redis_client.get(key)
        if raw:
            try:
                snapshot = json.loads(raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw)
            except Exception:
                snapshot = None
            if snapshot:
                return snapshot
        # default empty snapshot
        return {
            "project_id": project_id,
            "entity_types": [],
            "relationship_types": [],
            "version": 1,
            "updated_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get type registry for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve type registry")

@router.put("/projects/{project_id}/types")
async def upsert_type_registry(project_id: str, snapshot: TypeRegistrySnapshot, graph_processor = Depends(get_graph_processor)):
    """Upsert the project's Type Registry snapshot into Redis (temporary store)."""
    try:
        pvc_store = (_os.getenv("PVC_STORE") or "redis").lower()
        if pvc_store == "postgres":
            try:
                from app.pvc_repo.repository import PVCRepository, init_db
                init_db()
                repo = PVCRepository()
                data = snapshot.model_dump()
                data["project_id"] = project_id
                result = repo.upsert_type_registry(project_id, data.get("entity_types") or [], data.get("relationship_types") or [])
                return {"status": "ok", **result}
            except Exception as e:
                logger.error(f"PVC postgres upsert_type_registry failed, falling back to redis: {e}")
        # Default: Redis path
        data = snapshot.model_dump()
        data["project_id"] = project_id  # enforce path param
        # simple version bump
        try:
            existing_raw = await graph_processor.redis_client.get(f"pvc:types:{project_id}")
            if existing_raw:
                existing = json.loads(existing_raw.decode("utf-8") if isinstance(existing_raw, (bytes, bytearray)) else existing_raw)
                v = int(existing.get("version", 1)) + 1
            else:
                v = 1
        except Exception:
            v = 1
        data["version"] = v
        data["updated_at"] = datetime.utcnow().isoformat()
        await graph_processor.redis_client.set(f"pvc:types:{project_id}", json.dumps(data))
        return {"status": "ok", "project_id": project_id, "version": v}
    except Exception as e:
        logger.error(f"Failed to upsert type registry for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to upsert type registry")

@router.post("/projects/{project_id}/types/entity")
async def register_entity_type(project_id: str, req: EntityTypeRegistration, graph_processor = Depends(get_graph_processor)):
    """Register or update a single entity type with metadata and status.

    Persists into the Type Registry (Postgres or Redis) and bumps the version.
    """
    try:
        # Load current registry
        pvc_store = (_os.getenv("PVC_STORE") or "redis").lower()
        registry = None
        if pvc_store == "postgres":
            try:
                from app.pvc_repo.repository import PVCRepository, init_db
                init_db()
                repo = PVCRepository()
                registry = repo.get_type_registry(project_id)
            except Exception as e:
                logger.error(f"PVC postgres get_type_registry failed, fallback to redis: {e}")
        if registry is None:
            raw = await graph_processor.redis_client.get(f"pvc:types:{project_id}")
            if raw:
                registry = json.loads(raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw)
            else:
                registry = {"project_id": project_id, "entity_types": [], "relationship_types": [], "version": 1}

        # Upsert entity type
        etypes = registry.get("entity_types") or []
        # Normalize by name (case-sensitive to preserve)
        found = False
        for et in etypes:
            if (et.get("name") or et.get("type")) == req.name:
                et["name"] = req.name
                et["properties"] = req.properties or {}
                et["description"] = req.description
                et["status"] = req.status
                found = True
                break
        if not found:
            etypes.append({
                "name": req.name,
                "properties": req.properties or {},
                "description": req.description,
                "status": req.status
            })
        registry["entity_types"] = etypes

        # Save with version bump
        try:
            registry["version"] = int(registry.get("version", 1)) + 1
        except Exception:
            registry["version"] = 1
        registry["updated_at"] = datetime.utcnow().isoformat()

        if pvc_store == "postgres":
            try:
                from app.pvc_repo.repository import PVCRepository
                repo = PVCRepository()
                repo.upsert_type_registry(project_id, registry.get("entity_types") or [], registry.get("relationship_types") or [])
            except Exception as e:
                logger.error(f"PVC postgres upsert_type_registry failed, fallback to redis: {e}")
                await graph_processor.redis_client.set(f"pvc:types:{project_id}", json.dumps(registry))
        else:
            await graph_processor.redis_client.set(f"pvc:types:{project_id}", json.dumps(registry))

        return {"status": "ok", "project_id": project_id, "type": req.name, "version": registry["version"]}
    except Exception as e:
        logger.error(f"Failed to register entity type for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to register entity type")

@router.post("/projects/{project_id}/types/relationship")
async def register_relationship_type(project_id: str, req: RelationshipTypeRegistration, graph_processor = Depends(get_graph_processor)):
    """Register or update a single relationship type with metadata and status."""
    try:
        pvc_store = (_os.getenv("PVC_STORE") or "redis").lower()
        registry = None
        if pvc_store == "postgres":
            try:
                from app.pvc_repo.repository import PVCRepository, init_db
                init_db()
                repo = PVCRepository()
                registry = repo.get_type_registry(project_id)
            except Exception as e:
                logger.error(f"PVC postgres get_type_registry failed, fallback to redis: {e}")
        if registry is None:
            raw = await graph_processor.redis_client.get(f"pvc:types:{project_id}")
            if raw:
                registry = json.loads(raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw)
            else:
                registry = {"project_id": project_id, "entity_types": [], "relationship_types": [], "version": 1}

        rtypes = registry.get("relationship_types") or []
        found = False
        for rt in rtypes:
            if (rt.get("name") or rt.get("type")) == req.name:
                rt["name"] = req.name
                rt["from_type"] = req.from_type
                rt["to_type"] = req.to_type
                rt["properties"] = req.properties or {}
                rt["description"] = req.description
                rt["status"] = req.status
                found = True
                break
        if not found:
            rtypes.append({
                "name": req.name,
                "from_type": req.from_type,
                "to_type": req.to_type,
                "properties": req.properties or {},
                "description": req.description,
                "status": req.status
            })
        registry["relationship_types"] = rtypes

        try:
            registry["version"] = int(registry.get("version", 1)) + 1
        except Exception:
            registry["version"] = 1
        registry["updated_at"] = datetime.utcnow().isoformat()

        if pvc_store == "postgres":
            try:
                from app.pvc_repo.repository import PVCRepository
                repo = PVCRepository()
                repo.upsert_type_registry(project_id, registry.get("entity_types") or [], registry.get("relationship_types") or [])
            except Exception as e:
                logger.error(f"PVC postgres upsert_type_registry failed, fallback to redis: {e}")
                await graph_processor.redis_client.set(f"pvc:types:{project_id}", json.dumps(registry))
        else:
            await graph_processor.redis_client.set(f"pvc:types:{project_id}", json.dumps(registry))

        return {"status": "ok", "project_id": project_id, "type": req.name, "version": registry["version"]}
    except Exception as e:
        logger.error(f"Failed to register relationship type for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to register relationship type")

class CommitProposalsRequest(BaseModel):
    proposal_ids: Optional[List[str]] = None
    status_filter: str = Field(default="validated", description="Only commit proposals with this status when IDs not provided")

@router.post("/projects/{project_id}/commit-proposals")
async def commit_proposals_batch(project_id: str, req: CommitProposalsRequest = CommitProposalsRequest(), graph_processor = Depends(get_graph_processor)):
    """Commit multiple proposals for a project. If proposal_ids not provided, commit by status (default validated)."""
    try:
        pvc_store = (_os.getenv("PVC_STORE") or "redis").lower()
        proposals: List[Dict[str, Any]] = []
        if req.proposal_ids:
            # Fetch individually
            for pid in req.proposal_ids:
                prop = None
                if pvc_store == "postgres":
                    try:
                        from app.pvc_repo.repository import PVCRepository, init_db
                        init_db()
                        repo = PVCRepository()
                        prop = repo.get_proposal(pid)
                    except Exception as e:
                        logger.error(f"PVC postgres get_proposal failed, fallback to redis: {e}")
                if not prop:
                    raw = await graph_processor.redis_client.get(f"pvc:proposal:{pid}")
                    if raw:
                        prop = json.loads(raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw)
                if prop and prop.get("project_id") == project_id:
                    proposals.append(prop)
        else:
            # List by status for project
            if pvc_store == "postgres":
                try:
                    from app.pvc_repo.repository import PVCRepository, init_db
                    init_db()
                    repo = PVCRepository()
                    proposals = repo.list_proposals(project_id, status=req.status_filter)
                except Exception as e:
                    logger.error(f"PVC postgres list_proposals failed, fallback to redis: {e}")
            if not proposals:
                # Redis: iterate set and filter
                ids = await graph_processor.redis_client.smembers(f"pvc:project:{project_id}:proposals")
                ids_list = []
                if isinstance(ids, (list, set)):
                    ids_list = list(ids)
                else:
                    try:
                        ids_list = list(ids)
                    except Exception:
                        ids_list = []
                for pid in ids_list:
                    try:
                        key = f"pvc:proposal:{pid.decode('utf-8') if isinstance(pid, (bytes, bytearray)) else pid}"
                        raw = await graph_processor.redis_client.get(key)
                        if not raw:
                            continue
                        prop = json.loads(raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw)
                        if prop.get("project_id") == project_id and prop.get("status") == req.status_filter:
                            proposals.append(prop)
                    except Exception:
                        continue

        if not proposals:
            return {"status": "no_op", "project_id": project_id, "committed": 0, "message": "No proposals to commit"}

        total_entities = 0
        total_relationships = 0
        committed = 0
        # Reuse commit logic per proposal
        for prop in proposals:
            try:
                # Temporarily assign to redis for reuse of existing commit endpoint logic
                pid = prop.get("proposal_id") or prop.get("id")
                if not pid:
                    pid = str(uuid.uuid4())
                await graph_processor.redis_client.set(f"pvc:proposal:{pid}", json.dumps(prop))
                # Call commit_proposal function
                res = await commit_proposal(pid, graph_processor)
                total_entities += int(res.get("entities_processed", 0))
                total_relationships += int(res.get("relationships_processed", 0))
                committed += 1
            except Exception as ce:
                logger.warning(f"Batch commit failed for one proposal: {ce}")

        return {
            "status": "committed",
            "project_id": project_id,
            "proposals_committed": committed,
            "entities_processed": total_entities,
            "relationships_processed": total_relationships
        }
    except Exception as e:
        logger.error(f"Failed to batch commit proposals for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to batch commit proposals")

@router.get("/projects/{project_id}/proposals")
async def list_proposals(project_id: str, status: Optional[str] = Query(default=None), graph_processor = Depends(get_graph_processor)):
    """List proposals for a given project. Optional `status` filter.

    When `PVC_STORE=postgres`, use the SQL-backed repository. Otherwise, scan Redis keys for the project set.
    """
    try:
        pvc_store = (_os.getenv("PVC_STORE") or "redis").lower()
        if pvc_store == "postgres":
            try:
                from app.pvc_repo.repository import PVCRepository, init_db
                init_db()
                repo = PVCRepository()
                rows = repo.list_proposals(project_id, status=status)
                # Normalize response to a consistent schema
                return {
                    "project_id": project_id,
                    "count": len(rows),
                    "proposals": rows,
                }
            except Exception as e:
                logger.error(f"PVC postgres list_proposals failed, fallback to redis: {e}")

        # Redis fallback: use a set of proposal ids per project
        ids = await graph_processor.redis_client.smembers(f"pvc:project:{project_id}:proposals")
        results: List[Dict[str, Any]] = []
        for pid in ids or []:
            key = f"pvc:proposal:{pid.decode('utf-8') if isinstance(pid, (bytes, bytearray)) else pid}"
            raw = await graph_processor.redis_client.get(key)
            if not raw:
                continue
            try:
                prop = json.loads(raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw)
            except Exception:
                continue
            if prop.get("project_id") != project_id:
                continue
            if status and (prop.get("status") != status):
                continue
            # Basic normalization to match SQL path
            results.append({
                "proposal_id": prop.get("id") or prop.get("proposal_id"),
                "project_id": prop.get("project_id"),
                "status": prop.get("status", "pending"),
                "entities": prop.get("entities") or [],
                "relationships": prop.get("relationships") or [],
                "facts": prop.get("facts") or [],
                "source_documents": prop.get("source_documents") or [],
                "counts_entities": (prop.get("counts") or {}).get("entities", 0),
                "counts_relationships": (prop.get("counts") or {}).get("relationships", 0),
            })

        return {
            "project_id": project_id,
            "count": len(results),
            "proposals": results,
        }
    except Exception as e:
        logger.error(f"Failed to list proposals for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list proposals")

@router.get("/projects/{project_id}/proposals/validation-summary")
async def proposals_validation_summary(
    project_id: str,
    status: Optional[str] = Query(default=None, description="Filter proposals by status before summarizing (e.g., validated)"),
    graph_processor = Depends(get_graph_processor)
):
    """Aggregate validation metrics across a project's proposals.

    Sums numeric fields and computes averages for ratios. Returns keys present in at least one proposal.
    """
    try:
        pvc_store = (_os.getenv("PVC_STORE") or "redis").lower()
        proposals: List[Dict[str, Any]] = []
        if pvc_store == "postgres":
            try:
                from app.pvc_repo.repository import PVCRepository, init_db
                init_db()
                repo = PVCRepository()
                proposals = repo.list_proposals(project_id, status=status)
            except Exception as e:
                logger.error(f"PVC postgres list_proposals failed in validation summary, fallback to redis: {e}")
        if not proposals:
            ids = await graph_processor.redis_client.smembers(f"pvc:project:{project_id}:proposals")
            for pid in ids or []:
                key = f"pvc:proposal:{pid.decode('utf-8') if isinstance(pid, (bytes, bytearray)) else pid}"
                raw = await graph_processor.redis_client.get(key)
                if not raw:
                    continue
                try:
                    prop = json.loads(raw.decode('utf-8') if isinstance(raw, (bytes, bytearray)) else raw)
                except Exception:
                    continue
                if prop.get("project_id") != project_id:
                    continue
                if status and prop.get("status") != status:
                    continue
                proposals.append(prop)

        if not proposals:
            return {
                "project_id": project_id,
                "status_filter": status,
                "proposal_count": 0,
                "aggregated_metrics": {},
            }

        # Aggregate
        numeric_sums: Dict[str, float] = {}
        ratio_fields = {"duplicate_entity_ratio"}
        ratio_accumulate: Dict[str, List[float]] = {k: [] for k in ratio_fields}
        encountered_keys = set()
        for p in proposals:
            vm = p.get("validation_metrics") or {}
            for k, v in vm.items():
                encountered_keys.add(k)
                if isinstance(v, (int, float)):
                    if k in ratio_fields:
                        ratio_accumulate[k].append(float(v))
                    else:
                        numeric_sums[k] = numeric_sums.get(k, 0.0) + float(v)

        aggregated: Dict[str, Any] = {}
        for k, total in numeric_sums.items():
            aggregated[k] = total
        for k, vals in ratio_accumulate.items():
            if vals:
                aggregated[k] = sum(vals) / len(vals)
        aggregated["proposal_count"] = len(proposals)

        return {
            "project_id": project_id,
            "status_filter": status,
            "proposal_count": len(proposals),
            "aggregated_metrics": aggregated,
            "metric_keys": sorted(list(encountered_keys)),
        }
    except Exception as e:
        logger.error(f"Failed to build validation summary for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to build validation summary")

@router.get("/proposals/{proposal_id}")
async def get_proposal_by_id(proposal_id: str, graph_processor = Depends(get_graph_processor)):
    """Fetch a single proposal by ID from the configured PVC store.

    Returns 404 if not found.
    """
    try:
        pvc_store = (_os.getenv("PVC_STORE") or "redis").lower()
        if pvc_store == "postgres":
            try:
                from app.pvc_repo.repository import PVCRepository, init_db
                init_db()
                repo = PVCRepository()
                row = repo.get_proposal(proposal_id)
                if row is None:
                    raise HTTPException(status_code=404, detail="Proposal not found")
                return row
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"PVC postgres get_proposal failed, fallback to redis: {e}")

        raw = await graph_processor.redis_client.get(f"pvc:proposal:{proposal_id}")
        if not raw:
            raise HTTPException(status_code=404, detail="Proposal not found")
        try:
            prop = json.loads(raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw)
        except Exception:
            raise HTTPException(status_code=500, detail="Corrupt proposal data")
        return {
            "proposal_id": prop.get("id") or prop.get("proposal_id") or proposal_id,
            "project_id": prop.get("project_id"),
            "status": prop.get("status", "pending"),
            "entities": prop.get("entities") or [],
            "relationships": prop.get("relationships") or [],
            "facts": prop.get("facts") or [],
            "source_documents": prop.get("source_documents") or [],
            "counts_entities": (prop.get("counts") or {}).get("entities", 0),
            "counts_relationships": (prop.get("counts") or {}).get("relationships", 0),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get proposal {proposal_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get proposal")

@router.post("/projects/{project_id}/proposals")
async def create_proposal(project_id: str, proposal: Proposal, graph_processor = Depends(get_graph_processor)):
    """Create a proposal of entities/relationships and store in Redis (temporary).

    Returns a proposal_id to be used for validation and commit.
    """
    try:
        pid = str(uuid.uuid4())
        data = proposal.model_dump()
        data["id"] = pid
        data["project_id"] = project_id
        data["status"] = "pending"
        data["created_at"] = datetime.utcnow().isoformat()
        data["validated_at"] = None
        data["committed_at"] = None
        data["counts"] = {
            "entities": len(data.get("entities", []) or []),
            "relationships": len(data.get("relationships", []) or []),
        }

        pvc_store = (_os.getenv("PVC_STORE") or "redis").lower()
        if pvc_store == "postgres":
            try:
                from app.pvc_repo.repository import PVCRepository, init_db
                init_db()
                repo = PVCRepository()
                result = repo.create_proposal(
                    pid,
                    project_id,
                    data.get("entities") or [],
                    data.get("relationships") or [],
                    data.get("facts") or [],
                    data.get("source_documents") or [],
                )
                return result
            except Exception as e:
                logger.error(f"PVC postgres create_proposal failed, falling back to redis: {e}")
        # Redis persist
        await graph_processor.redis_client.set(f"pvc:proposal:{pid}", json.dumps(data))
        await graph_processor.redis_client.sadd(f"pvc:project:{project_id}:proposals", pid)

        return {"proposal_id": pid, "status": "pending", **data["counts"]}
    except Exception as e:
        logger.error(f"Failed to create proposal for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to create proposal")

@router.post("/proposals/{proposal_id}/validate")
async def validate_proposal(proposal_id: str, graph_processor = Depends(get_graph_processor)):
    """Validate a proposal against the Type Registry.

    Behavior depends on AUTO_REGISTER_TYPES (env var, default true):
        - If true: unknown entity/relationship types are auto-added (current behavior) and status -> validated.
        - If false: unknown types collected into pending_* arrays, status -> pending_types, registry NOT modified.
    """
    try:
        pvc_store = (_os.getenv("PVC_STORE") or "redis").lower()
        prop = None
        if pvc_store == "postgres":
            try:
                from app.pvc_repo.repository import PVCRepository, init_db
                init_db()
                repo = PVCRepository()
                prop = repo.get_proposal(proposal_id)
            except Exception as e:
                logger.error(f"PVC postgres get_proposal failed, falling back to redis: {e}")
        if not prop:
            raw = await graph_processor.redis_client.get(f"pvc:proposal:{proposal_id}")
            if not raw:
                raise HTTPException(status_code=404, detail="Proposal not found")
            prop = json.loads(raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw)
        project_id = prop.get("project_id")
        if not project_id:
            raise HTTPException(status_code=400, detail="Proposal missing project_id")

        # Load registry
        registry = None
        if pvc_store == "postgres":
            try:
                from app.pvc_repo.repository import PVCRepository
                repo = PVCRepository()
                registry = repo.get_type_registry(project_id)
            except Exception as e:
                logger.error(f"PVC postgres get_type_registry failed during validate, fallback to redis: {e}")
        if registry is None:
            reg_raw = await graph_processor.redis_client.get(f"pvc:types:{project_id}")
            if reg_raw:
                registry = json.loads(reg_raw.decode("utf-8") if isinstance(reg_raw, (bytes, bytearray)) else reg_raw)
            else:
                registry = {"project_id": project_id, "entity_types": [], "relationship_types": [], "version": 1}

        # Build sets for quick membership (before auto-registration for accurate unknown counts)
        existing_entity_types = { (et.get("name") or et.get("type") or "").strip() for et in (registry.get("entity_types") or []) if (et.get("name") or et.get("type")) }
        existing_rel_types = { (rt.get("name") or rt.get("type") or "").strip() for rt in (registry.get("relationship_types") or []) if (rt.get("name") or rt.get("type")) }

        entities_list = prop.get("entities") or []
        rels_list = prop.get("relationships") or []

        # Collect proposed types
        proposed_entity_types = set()
        for ent in entities_list:
            t = (ent.get("type") or ent.get("entity_type") or ent.get("label") or "").strip()
            if t:
                proposed_entity_types.add(t)
        proposed_rel_types = set()
        for rel in rels_list:
            t = (rel.get("type") or rel.get("relation_type") or rel.get("label") or "").strip()
            if t:
                proposed_rel_types.add(t)

        # Compute unknowns BEFORE auto-register
        unknown_entity_types = sorted([t for t in proposed_entity_types if t not in existing_entity_types])
        unknown_relationship_types = sorted([t for t in proposed_rel_types if t not in existing_rel_types])

        # Metrics: duplicates, empty names, name length stats, type distribution
        name_counts: Dict[str, int] = {}
        empty_name_entities = 0
        name_lengths: List[int] = []
        for e in entities_list:
            raw_name = (e.get("name") or e.get("id") or "").strip()
            if not raw_name:
                empty_name_entities += 1
                continue
            nm = raw_name.lower()
            name_counts[nm] = name_counts.get(nm, 0) + 1
            name_lengths.append(len(raw_name))
        duplicate_entity_names = sum(1 for c in name_counts.values() if c > 1)
        duplicate_entity_ratio = (duplicate_entity_names / max(1, len(entities_list))) if entities_list else 0.0
        avg_name_length = (sum(name_lengths) / len(name_lengths)) if name_lengths else 0.0
        p95_name_length = 0.0
        if name_lengths:
            sl = sorted(name_lengths)
            p95_index = int(0.95 * (len(sl) - 1))
            p95_name_length = float(sl[p95_index])

        entity_type_counts: Dict[str, int] = {}
        for e in entities_list:
            t = (e.get("type") or e.get("entity_type") or e.get("label") or "").strip() or "(unset)"
            entity_type_counts[t] = entity_type_counts.get(t, 0) + 1
        relationship_type_counts: Dict[str, int] = {}
        endpoint_missing = 0
        for r in rels_list:
            t = (r.get("type") or r.get("relation_type") or r.get("label") or "").strip() or "(unset)"
            relationship_type_counts[t] = relationship_type_counts.get(t, 0) + 1
            src = (r.get("source") or r.get("from") or r.get("source_name") or "").strip()
            dst = (r.get("target") or r.get("to") or r.get("target_name") or "").strip()
            if not (src and dst):
                endpoint_missing += 1

        validation_metrics = {
            "entity_count": len(entities_list),
            "relationship_count": len(rels_list),
            "duplicate_entity_names": duplicate_entity_names,
            "duplicate_entity_ratio": duplicate_entity_ratio,
            "empty_name_entities": empty_name_entities,
            "avg_entity_name_length": round(avg_name_length, 2),
            "p95_entity_name_length": p95_name_length,
            "unknown_entity_types": len(unknown_entity_types),
            "unknown_entity_type_list": unknown_entity_types,
            "unknown_relationship_types": len(unknown_relationship_types),
            "unknown_relationship_type_list": unknown_relationship_types,
            "entity_type_counts": entity_type_counts,
            "relationship_type_counts": relationship_type_counts,
            "relationships_missing_endpoints": endpoint_missing,
            "generated_at": datetime.utcnow().isoformat(),
        }

        auto_register = (os.getenv("AUTO_REGISTER_TYPES", "1").lower() not in ("0", "false", "no"))
        new_entity_defs = []
        new_rel_defs = []
        pending_mode = False
        if auto_register:
            # Auto-register path (unchanged behavior)
            new_entity_defs = [{"name": t, "properties": {}} for t in unknown_entity_types]
            new_rel_defs = [{"name": t, "from_type": "*", "to_type": "*", "properties": {}} for t in unknown_relationship_types]
            if new_entity_defs:
                registry.setdefault("entity_types", []).extend(new_entity_defs)
            if new_rel_defs:
                registry.setdefault("relationship_types", []).extend(new_rel_defs)
            # Persist registry bump
            try:
                registry["version"] = int(registry.get("version", 1)) + 1
            except Exception:
                registry["version"] = 1
            registry["updated_at"] = datetime.utcnow().isoformat()
            if pvc_store == "postgres":
                try:
                    from app.pvc_repo.repository import PVCRepository
                    repo = PVCRepository()
                    repo.upsert_type_registry(project_id, registry.get("entity_types") or [], registry.get("relationship_types") or [])
                except Exception as e:
                    logger.error(f"PVC postgres upsert_type_registry failed during validate, fallback to redis: {e}")
                    await graph_processor.redis_client.set(f"pvc:types:{project_id}", json.dumps(registry))
            else:
                await graph_processor.redis_client.set(f"pvc:types:{project_id}", json.dumps(registry))
        else:
            # Gating mode: do not modify registry; mark proposal pending_types
            pending_mode = True
            validation_metrics["pending_entity_type_list"] = unknown_entity_types
            validation_metrics["pending_relationship_type_list"] = unknown_relationship_types

        # Evidence block
        evidence_block = {
            "kind": "validation_summary",
            "data": {
                "entity_types_added": len(new_entity_defs),
                "relationship_types_added": len(new_rel_defs),
                "auto_register": auto_register,
                "pending_entity_types": unknown_entity_types if pending_mode else [],
                "pending_relationship_types": unknown_relationship_types if pending_mode else [],
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

        if pvc_store == "postgres":
            try:
                from app.pvc_repo.repository import PVCRepository
                repo = PVCRepository()
                updated = repo.update_proposal_validation(proposal_id, validation_metrics, evidence=[evidence_block], auto_status=auto_register)
                if updated and pending_mode:
                    # Direct SQL update for pending arrays
                    from sqlalchemy import update
                    from .pvc_repo.models import ProposalORM  # type: ignore
            except Exception as e:
                logger.error(f"PVC postgres update_proposal_validation failed, fallback to redis: {e}")
                # fallback to redis path below
        # Redis or fallback path
        if not auto_register:
            prop["status"] = "pending_types"
            prop["pending_entity_types"] = unknown_entity_types
            prop["pending_relationship_types"] = unknown_relationship_types
        else:
            prop["status"] = "validated"
            prop["validated_at"] = datetime.utcnow().isoformat()
        prop["validation_metrics"] = validation_metrics
        prop.setdefault("evidence", []).append(evidence_block)
        await graph_processor.redis_client.set(f"pvc:proposal:{proposal_id}", json.dumps(prop))

        return {
            "proposal_id": proposal_id,
            "status": prop.get("status"),
            "new_entity_types": [d["name"] for d in new_entity_defs],
            "new_relationship_types": [d["name"] for d in new_rel_defs],
            "pending_entity_types": unknown_entity_types if pending_mode else [],
            "pending_relationship_types": unknown_relationship_types if pending_mode else [],
            "validation_metrics": validation_metrics,
            "auto_register": auto_register,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to validate proposal {proposal_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to validate proposal")

@router.post("/proposals/{proposal_id}/commit")
async def commit_proposal(proposal_id: str, graph_processor = Depends(get_graph_processor)):
    """Commit a validated proposal to Neo4j with idempotent MERGE operations."""
    try:
        pvc_store = (_os.getenv("PVC_STORE") or "redis").lower()
        prop = None
        if pvc_store == "postgres":
            try:
                from app.pvc_repo.repository import PVCRepository, init_db
                init_db()
                repo = PVCRepository()
                prop = repo.get_proposal(proposal_id)
            except Exception as e:
                logger.error(f"PVC postgres get_proposal failed, falling back to redis: {e}")
        if not prop:
            raw = await graph_processor.redis_client.get(f"pvc:proposal:{proposal_id}")
            if not raw:
                raise HTTPException(status_code=404, detail="Proposal not found")
            prop = json.loads(raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw)
        project_id = prop.get("project_id")
        if not project_id:
            raise HTTPException(status_code=400, detail="Proposal missing project_id")

        # Proceed regardless of status; MERGE operations are idempotent
        entities = prop.get("entities") or []
        relationships = prop.get("relationships") or []

        # Helper to extract entity core fields
        def _ent_fields(ent: Dict[str, Any]) -> Optional[Dict[str, str]]:
            name = (ent.get("name") or ent.get("id") or ent.get("label") or "").strip()
            etype = (ent.get("type") or ent.get("entity_type") or ent.get("label") or "").strip()
            if not name:
                return None
            return {"name": name, "type": etype or "Entity"}

        # Helper to extract relationship core fields
        def _rel_fields(rel: Dict[str, Any]) -> Optional[Dict[str, str]]:
            rtype = (rel.get("type") or rel.get("relation_type") or rel.get("label") or "").strip()
            s = (rel.get("source") or rel.get("from") or rel.get("source_name") or "").strip()
            t = (rel.get("target") or rel.get("to") or rel.get("target_name") or "").strip()
            if not (rtype and s and t):
                return None
            return {"type": rtype, "source": s, "target": t}

        ent_core = [e for e in (_ent_fields(e) for e in entities) if e]
        rel_core = [r for r in (_rel_fields(r) for r in relationships) if r]

        created_nodes = 0
        created_rels = 0

        # Pre-compute degree metrics for canonical entity index
        # We'll build maps: occurrences per entity name, in/out degree, relationship type counts per entity
        occ: Dict[str, int] = {}
        deg_in: Dict[str, int] = {}
        deg_out: Dict[str, int] = {}
        rel_type_counts_by_entity: Dict[str, Dict[str, int]] = {}
        for e in ent_core:
            nm = e["name"].strip()
            occ[nm] = occ.get(nm, 0) + 1
        for r in rel_core:
            s = r["source"].strip()
            t = r["target"].strip()
            rt = r["type"].strip() or "REL"
            deg_out[s] = deg_out.get(s, 0) + 1
            deg_in[t] = deg_in.get(t, 0) + 1
            rel_type_counts_by_entity.setdefault(s, {})[rt] = rel_type_counts_by_entity.get(s, {}).get(rt, 0) + 1
            rel_type_counts_by_entity.setdefault(t, {})[rt] = rel_type_counts_by_entity.get(t, {}).get(rt, 0) + 1

        async with graph_processor.neo4j_driver.session() as session:
            # Ensure Project exists
            await session.run("MERGE (p:Project {id: $pid}) SET p.updated_at = datetime()", pid=project_id)

            # Upsert entities
            # Use canonical_id-based merges to avoid name collisions within a project
            try:
                from app.core.id_utils import make_canonical_id as _make_canonical_id
            except Exception:
                _make_canonical_id = None  # type: ignore

            # Precompute name->type map for later relationship endpoint resolution
            name_to_type: Dict[str, str] = {}
            for e in ent_core:
                nm = e["name"].strip()
                et = (e.get("type") or "Entity").strip() or "Entity"
                if nm:
                    name_to_type[nm] = et

            for e in ent_core:
                etype = (e.get("type") or "Entity").strip() or "Entity"
                ename = e["name"].strip()
                # Compute canonical id; fall back to simple deterministic id if util not available
                if _make_canonical_id is not None:
                    cid = _make_canonical_id(project_id, etype, ename, None)
                else:
                    import hashlib as _hashlib
                    cid = f"{project_id}:{etype.lower()}:{_hashlib.sha1((ename or '').encode('utf-8', errors='ignore')).hexdigest()[:12]}"

                q = (
                    "MATCH (p:Project {id: $pid}) "
                    "MERGE (n:Entity:$$label {canonical_id: $cid}) "
                    "ON CREATE SET n.created_at = datetime(), n.project_id = $pid, n.type = $type "
                    "SET n.id = $cid, n.name = $name, n.updated_at = datetime() "
                    "MERGE (p)-[:CONTAINS]->(n)"
                ).replace("$$label", etype)
                res = await session.run(q, pid=project_id, cid=cid, name=ename, type=etype)
                try:
                    _ = await res.consume()
                except Exception:
                    pass
                created_nodes += 1

            # Upsert relationships
            for r in rel_core:
                sname = r["source"].strip()
                tname = r["target"].strip()
                rtype = (r["type"].strip() or "RELATIONSHIP")
                stype = name_to_type.get(sname, "Entity")
                ttype = name_to_type.get(tname, "Entity")
                # Compute canonical ids for endpoints
                if _make_canonical_id is not None:
                    sid = _make_canonical_id(project_id, stype, sname, None)
                    tid = _make_canonical_id(project_id, ttype, tname, None)
                else:
                    import hashlib as _hashlib
                    sid = f"{project_id}:{stype.lower()}:{_hashlib.sha1((sname or '').encode('utf-8', errors='ignore')).hexdigest()[:12]}"
                    tid = f"{project_id}:{ttype.lower()}:{_hashlib.sha1((tname or '').encode('utf-8', errors='ignore')).hexdigest()[:12]}"

                q = (
                    "MATCH (p:Project {id: $pid}) "
                    "MERGE (s:Entity {canonical_id: $sid}) "
                    "ON CREATE SET s.created_at = datetime(), s.project_id = $pid, s.type = $stype, s.id = $sid, s.name = $sname "
                    "MERGE (t:Entity {canonical_id: $tid}) "
                    "ON CREATE SET t.created_at = datetime(), t.project_id = $pid, t.type = $ttype, t.id = $tid, t.name = $tname "
                    "MERGE (p)-[:CONTAINS]->(s) "
                    "MERGE (p)-[:CONTAINS]->(t) "
                    "MERGE (s)-[rel:RELATIONSHIP {type: $rtype}]->(t) "
                    "SET rel.updated_at = datetime(), rel.project_id = $pid"
                )
                res = await session.run(
                    q,
                    pid=project_id,
                    sid=sid,
                    tid=tid,
                    rtype=rtype,
                    stype=stype,
                    ttype=ttype,
                    sname=sname,
                    tname=tname,
                )
                try:
                    _ = await res.consume()
                except Exception:
                    pass
                created_rels += 1

        # Update proposal status
        if pvc_store == "postgres":
            try:
                from app.pvc_repo.repository import PVCRepository
                repo = PVCRepository()
                repo.set_proposal_status(proposal_id, "committed")
                # Build canonical entity index rows
                # slug strategy: lowercased name with non-alphanumerics replaced by hyphen, collapse repeats
                import re as _re
                rows = []
                # Aggregate global relationship type counts (Phase 2 metrics)
                global_rel_type_counts: Dict[str, int] = {}
                reserved_slugs = {"__aggregate__"}
                for e in ent_core:
                    nm = e["name"].strip()
                    if not nm:
                        continue
                    slug = _re.sub(r"[^a-z0-9]+", "-", nm.lower()).strip('-')
                    if slug in reserved_slugs:
                        # Append numeric discriminator to avoid collision with metrics row
                        slug = f"{slug}-{proposal_id[:8]}"
                    d_in = deg_in.get(nm, 0)
                    d_out = deg_out.get(nm, 0)
                    row = {
                        "slug": slug,
                        "name": nm,
                        "type": e.get("type") or "Entity",
                        "occurrences": occ.get(nm, 0),
                        "degree_in": d_in,
                        "degree_out": d_out,
                        "total_degree": d_in + d_out,
                        "relationship_type_counts": rel_type_counts_by_entity.get(nm, {}),
                    }
                    # Accumulate global counts
                    for rt_key, rt_val in (rel_type_counts_by_entity.get(nm, {}) or {}).items():
                        try:
                            global_rel_type_counts[rt_key] = int(global_rel_type_counts.get(rt_key, 0)) + int(rt_val)
                        except Exception:
                            pass
                    rows.append(row)
                # Inject synthetic aggregate metrics row (slug = '__aggregate__') if we have data
                if global_rel_type_counts:
                    rows.append({
                        "slug": "__aggregate__",
                        "name": "__aggregate__",
                        "type": "_metrics",
                        "occurrences": 0,
                        "degree_in": 0,
                        "degree_out": 0,
                        "total_degree": 0,
                        "relationship_type_counts": global_rel_type_counts,
                    })
                if rows:
                    try:
                        repo.upsert_canonical_entities(project_id, proposal_id, rows)
                    except Exception as _ce:
                        logger.error(f"Canonical entity index upsert failed for proposal {proposal_id}: {_ce}")
                # Emit analytics event for relationship distribution (best-effort)
                if global_rel_type_counts:
                    try:
                        import os as _os, httpx as _httpx
                        analytics_url = _os.getenv("ANALYTICS_SERVICE_URL", "http://localhost:8014")
                        headers = {"Authorization": f"Bearer {_os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"}
                        payload = {
                            "source": "graph-service",
                            "project_id": project_id,
                            "metrics": {
                                "graph_commit": {
                                    "proposal_id": proposal_id,
                                    "relationship_type_distribution": global_rel_type_counts,
                                    "entity_count": len(ent_core),
                                    "relationship_count": len(rel_core)
                                }
                            }
                        }
                        async def _post():
                            async with _httpx.AsyncClient(timeout=2.5) as client:
                                await client.post(f"{analytics_url}/ingest", json=payload, headers=headers)
                        import asyncio as _asyncio
                        _asyncio.create_task(_post())
                    except Exception:
                        pass
            except Exception as e:
                logger.error(f"PVC postgres set_proposal_status failed during commit, fallback to redis: {e}")
                prop["status"] = "committed"
                prop["committed_at"] = datetime.utcnow().isoformat()
                prop["commit_counts"] = {"entities_processed": len(ent_core), "relationships_processed": len(rel_core)}
                await graph_processor.redis_client.set(f"pvc:proposal:{proposal_id}", json.dumps(prop))
        else:
            prop["status"] = "committed"
            prop["committed_at"] = datetime.utcnow().isoformat()
            prop["commit_counts"] = {"entities_processed": len(ent_core), "relationships_processed": len(rel_core)}
            await graph_processor.redis_client.set(f"pvc:proposal:{proposal_id}", json.dumps(prop))

        return {
            "proposal_id": proposal_id,
            "status": "committed",
            "entities_processed": len(ent_core),
            "relationships_processed": len(rel_core)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to commit proposal {proposal_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to commit proposal")

@router.post("/proposals/{proposal_id}/approve-pending-types")
async def approve_pending_types(proposal_id: str, graph_processor = Depends(get_graph_processor)):
    """Approve pending (unknown) types for a proposal previously validated in gating mode.

    Moves types from pending arrays into the Type Registry and transitions status -> validated.
    No-op if proposal already validated or has no pending types.
    """
    try:
        pvc_store = (_os.getenv("PVC_STORE") or "redis").lower()
        prop = None
        if pvc_store == "postgres":
            try:
                from app.pvc_repo.repository import PVCRepository, init_db
                init_db()
                repo = PVCRepository()
                prop = repo.get_proposal(proposal_id)
            except Exception as e:
                logger.error(f"PVC postgres get_proposal failed, fallback to redis: {e}")
        if not prop:
            raw = await graph_processor.redis_client.get(f"pvc:proposal:{proposal_id}")
            if not raw:
                raise HTTPException(status_code=404, detail="Proposal not found")
            prop = json.loads(raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw)
        if prop.get("status") == "validated":
            return {"status": "already_validated", "proposal_id": proposal_id}
        pend_entities = prop.get("pending_entity_types") or []
        pend_rels = prop.get("pending_relationship_types") or []
        if not pend_entities and not pend_rels:
            return {"status": "no_pending_types", "proposal_id": proposal_id}
        project_id = prop.get("project_id")
        if not project_id:
            raise HTTPException(status_code=400, detail="Proposal missing project_id")
        # Load registry
        registry = None
        if pvc_store == "postgres":
            try:
                from app.pvc_repo.repository import PVCRepository
                repo = PVCRepository()
                registry = repo.get_type_registry(project_id)
            except Exception as e:
                logger.error(f"PVC postgres get_type_registry failed during approve, fallback to redis: {e}")
        if registry is None:
            reg_raw = await graph_processor.redis_client.get(f"pvc:types:{project_id}")
            if reg_raw:
                registry = json.loads(reg_raw.decode("utf-8") if isinstance(reg_raw, (bytes, bytearray)) else reg_raw)
            else:
                registry = {"project_id": project_id, "entity_types": [], "relationship_types": [], "version": 1}
        # Append new types
        if pend_entities:
            registry.setdefault("entity_types", []).extend([{"name": t, "properties": {}} for t in pend_entities])
        if pend_rels:
            registry.setdefault("relationship_types", []).extend([{"name": t, "from_type": "*", "to_type": "*", "properties": {}} for t in pend_rels])
        try:
            registry["version"] = int(registry.get("version", 1)) + 1
        except Exception:
            registry["version"] = 1
        registry["updated_at"] = datetime.utcnow().isoformat()
        if pvc_store == "postgres":
            try:
                from app.pvc_repo.repository import PVCRepository
                repo = PVCRepository()
                repo.upsert_type_registry(project_id, registry.get("entity_types") or [], registry.get("relationship_types") or [])
            except Exception as e:
                logger.error(f"PVC postgres upsert_type_registry failed during approve, fallback to redis: {e}")
                await graph_processor.redis_client.set(f"pvc:types:{project_id}", json.dumps(registry))
        else:
            await graph_processor.redis_client.set(f"pvc:types:{project_id}", json.dumps(registry))
        # Update proposal status
        prop["status"] = "validated"
        prop["validated_at"] = datetime.utcnow().isoformat()
        prop["pending_entity_types"] = []
        prop["pending_relationship_types"] = []
        prop.setdefault("evidence", []).append({
            "kind": "pending_types_approved",
            "data": {"entity_types": pend_entities, "relationship_types": pend_rels},
            "timestamp": datetime.utcnow().isoformat(),
        })
        await graph_processor.redis_client.set(f"pvc:proposal:{proposal_id}", json.dumps(prop))
        return {"status": "validated", "proposal_id": proposal_id, "entity_types_added": pend_entities, "relationship_types_added": pend_rels}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to approve pending types for proposal {proposal_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to approve pending types")

# Enhanced Structured Document Processing Endpoint
@router.post("/projects/{project_id}/process-structured", response_model=ProcessStructuredResponse)
async def process_structured_document(
    project_id: str,
    request: ProcessStructuredRequest,
    background_tasks: BackgroundTasks,
    graph_processor = Depends(get_graph_processor),
    http_request: Request = None,
):
    """
    Process structured document elements for entity and relationship extraction
    This endpoint implements Step 5 of the enhanced document workflow
    """
    try:
        start_time = datetime.now()
        logger.info(f"Processing structured document {request.filename} with {len(request.structured_elements)} elements")
        
        # Capture correlation id if provided (for downstream LLM calls)
        corr_id = None
        try:
            if http_request is not None:
                corr_id = http_request.headers.get("X-Correlation-ID") or None
        except Exception:
            pass

        # Initialize counters
        entities_extracted = 0
        relationships_found = 0
        entity_types = {}
        relationship_types = {}
        
        # Process elements for entity extraction
        if request.extract_entities:
            entities_extracted, entity_types, rel_count_from_entities, rel_types_from_entities = await _extract_entities_from_structured_elements(
                project_id,
                request.structured_elements,
                graph_processor,
                request.filename,
                corr_id,
            )
            # Accumulate relationship counts/types produced alongside entity extraction
            try:
                relationships_found += int(rel_count_from_entities or 0)
            except Exception:
                pass
            if rel_types_from_entities:
                for k, v in rel_types_from_entities.items():
                    relationship_types[k] = relationship_types.get(k, 0) + int(v or 0)
        
        # Process elements for relationship extraction
        if request.extract_relationships:
            relationships_found, relationship_types = await _extract_relationships_from_structured_elements(
                project_id, request.structured_elements, graph_processor
            )
        
        # Create document node in the graph
        await _create_document_node(
            project_id, request.document_id, request.filename, 
            len(request.structured_elements), graph_processor
        )
        
        # Post-write aggregation: compute actual relationship counts from Neo4j (project-scoped, doc-scoped if available)
        try:
            async with graph_processor.neo4j_driver.session() as session:  # type: ignore
                # Count all relationships between nodes contained in the project, optionally filtered by rel.document_id
                rel_count_query = (
                    """
                    MATCH (p:Project {id: $pid})-[:CONTAINS]->(a)
                    MATCH (p)-[:CONTAINS]->(b)
                    MATCH (a)-[r]->(b)
                    WHERE ($docid IS NULL OR coalesce(r.document_id, $docid) = $docid)
                    RETURN count(r) as cnt
                    """
                )
                rec = await (await session.run(rel_count_query, pid=project_id, docid=request.document_id or None)).single()
                if rec and rec.get("cnt") is not None:
                    relationships_found = int(rec.get("cnt"))

                # Breakdown by type
                rel_type_query = (
                    """
                    MATCH (p:Project {id: $pid})-[:CONTAINS]->(a)
                    MATCH (p)-[:CONTAINS]->(b)
                    MATCH (a)-[r]->(b)
                    WHERE ($docid IS NULL OR coalesce(r.document_id, $docid) = $docid)
                    RETURN type(r) as t, count(r) as c
                    """
                )
                relationship_types = {}
                res = await session.run(rel_type_query, pid=project_id, docid=request.document_id or None)
                async for row in res:
                    t = row.get("t") or ""
                    c = int(row.get("c") or 0)
                    if t:
                        relationship_types[t] = c
        except Exception as agg_err:
            logger.debug(f"Post-write relationship aggregation failed (non-fatal): {agg_err}")

        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()

        logger.info(f"Structured processing completed: {entities_extracted} entities, {relationships_found} relationships")

        return ProcessStructuredResponse(
            status="success",
            document_id=request.document_id,
            filename=request.filename,
            elements_analyzed=len(request.structured_elements),
            entities_extracted=entities_extracted,
            relationships_found=relationships_found,
            processing_time_seconds=processing_time,
            entity_types=entity_types,
            relationship_types=relationship_types
        )
        
    except Exception as e:
        logger.error(f"Structured processing failed for document {request.filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Structured processing failed: {str(e)}")

# Async variant returning 202 + job id
@router.post("/projects/{project_id}/process-structured/async")
async def process_structured_document_async(
    project_id: str,
    request: ProcessStructuredRequest,
    background_tasks: BackgroundTasks,
    graph_processor = Depends(get_graph_processor),
    http_request: Request = None,
):
    """Async structured processing that enqueues a background job and returns 202 with job_id.

    Uses the same extraction internals as the sync endpoint, but reports progress via the jobs store.
    """
    try:
        corr_id = None
        try:
            if http_request is not None:
                corr_id = http_request.headers.get("X-Correlation-ID") or None
        except Exception:
            pass

        if not request.structured_elements:
            raise HTTPException(status_code=400, detail="structured_elements must be non-empty")

        job_id = str(uuid.uuid4())
        enqueued_at = datetime.utcnow().isoformat()
        job = {
            "job_id": job_id,
            "project_id": project_id,
            "status": "queued",
            "document_id": request.document_id,
            "filename": request.filename,
            "queued_at": enqueued_at,
            "progress": [
                {"ts": enqueued_at, "stage": "queued", "message": f"Elements received: {len(request.structured_elements)}"}
            ],
        }
        await _job_write(graph_processor, job_id, job)

        async def _update(stage: str, message: str, extra: Optional[Dict[str, Any]] = None):
            cur = await _job_read(graph_processor, job_id) or {}
            cur.setdefault("progress", []).append({"ts": datetime.utcnow().isoformat(), "stage": stage, "message": message})
            if extra:
                cur.update(extra)
            await _job_write(graph_processor, job_id, cur)

        async def _run_job():
            try:
                await _update("starting", "Structured processing started", {"status": "running", "started_at": datetime.utcnow().isoformat()})
                t0 = time.perf_counter()
                # Reuse existing helper for extraction + persistence
                entities_extracted, entity_types, rel_count_from_entities, rel_types_from_entities = await _extract_entities_from_structured_elements(
                    project_id,
                    request.structured_elements,
                    graph_processor,
                    request.filename,
                    corr_id,
                )
                # Optional relationship extraction phase (if any specialized additional logic present)
                relationships_found, relationship_types = rel_count_from_entities, rel_types_from_entities
                await _update("persist", f"Persisted entities={entities_extracted} rels={relationships_found}")

                # Post-write aggregation filtered by document if provided
                rels_final = relationships_found
                rel_types_final = dict(relationship_types)
                try:
                    async with graph_processor.neo4j_driver.session() as session:
                        if request.document_id:
                            qry = (
                                "MATCH (p:Project {id:$pid})-[:CONTAINS]->(a)-[r]->(b) "
                                "WHERE r.project_id=$pid AND r.document_id=$docid RETURN count(r) as cnt"
                            )
                            rec = await (await session.run(qry, pid=project_id, docid=request.document_id)).single()
                            rels_final = rec["cnt"] if rec else relationships_found
                            qry2 = (
                                "MATCH (p:Project {id:$pid})-[:CONTAINS]->(a)-[r]->(b) "
                                "WHERE r.project_id=$pid AND r.document_id=$docid RETURN type(r) as t, count(r) as c"
                            )
                            res = await session.run(qry2, pid=project_id, docid=request.document_id)
                        else:
                            qry = "MATCH (p:Project {id:$pid})-[:CONTAINS]->(a)-[r]->(b) WHERE r.project_id=$pid RETURN count(r) as cnt"
                            rec = await (await session.run(qry, pid=project_id)).single()
                            rels_final = rec["cnt"] if rec else relationships_found
                            qry2 = (
                                "MATCH (p:Project {id:$pid})-[:CONTAINS]->(a)-[r]->(b) WHERE r.project_id=$pid RETURN type(r) as t, count(r) as c"
                            )
                            res = await session.run(qry2, pid=project_id)
                        rel_types_final = {}
                        async for row in res:
                            rel_types_final[str(row["t"]) or "REL"] = int(row["c"]) if row and row.get("c") is not None else 0
                except Exception:
                    pass

                dur = round(time.perf_counter() - t0, 2)
                await _update("completed", "Structured processing finished", {
                    "status": "succeeded",
                    "finished_at": datetime.utcnow().isoformat(),
                    "entities_found": entities_extracted,
                    "relationships_found": rels_final,
                    "summary": {
                        "elements": len(request.structured_elements),
                        "filename": request.filename,
                        "duration_seconds": dur,
                    }
                })
            except Exception as e:
                logger.error(f"Async structured job failed job={job_id}: {e}")
                await _update("failed", "Job failed", {"status": "failed", "error": str(e), "finished_at": datetime.utcnow().isoformat()})

        background_tasks.add_task(_run_job)
        payload = {
            "job_id": job_id,
            "status": "queued",
            "project_id": project_id,
            "document_id": request.document_id,
            "filename": request.filename,
            "queued_at": enqueued_at,
        }
        return JSONResponse(status_code=202, content=payload)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to enqueue structured processing: {e}")
        raise HTTPException(status_code=500, detail="Failed to enqueue structured processing")

# New endpoint: extract facts directly from structured elements (JSONL-origin) after entity/relationship extraction
@router.post("/projects/{project_id}/structured/facts")
async def extract_facts_from_structured(
    project_id: str,
    request: ProcessStructuredRequest,
    graph_processor = Depends(get_graph_processor),
    http_request: Request = None,
):
    """Extract a comprehensive set of key facts directly from structured elements.

    This allows clients to trigger fact extraction explicitly using the structured representation
    (e.g., JSONL-derived elements) rather than relying only on implicit extraction in the normal
    entity pipeline. Returns the extracted facts (not just counts) for immediate client use.
    """
    try:
        # Correlation ID for tracing
        corr_id = None
        try:
            if http_request is not None:
                corr_id = http_request.headers.get("X-Correlation-ID") or None
        except Exception:
            pass

        # Concatenate element content in logical order preserving page number and hierarchy
        # Provide light separators to help the LLM segment facts.
        parts = []
        for elem in request.structured_elements:
            if not elem.content:
                continue
            meta_bits = []
            if elem.page_number is not None:
                meta_bits.append(f"page {elem.page_number}")
            if elem.element_type:
                meta_bits.append(elem.element_type)
            prefix = f"[{', '.join(meta_bits)}] " if meta_bits else ""
            parts.append(prefix + elem.content.strip())
        combined_content = "\n".join(parts)
        if not combined_content.strip():
            return {"status": "success", "facts": [], "count": 0, "document_id": request.document_id, "filename": request.filename}

        # Call internal fact extraction helper (Stage 1 logic) but without storing twice; we reuse the private method.
        # We invoke _llm_extract_key_facts directly and then (optionally) store discoveries if requested.
        facts = await graph_processor._llm_extract_key_facts(  # type: ignore
            project_id=project_id,
            document_content=combined_content,
            filename=request.filename or "structured_document",
            correlation_id=corr_id,
        )

        store = True
        if os.getenv("GRAPH_STORE_STRUCTURED_FACTS", "1").lower() in ("0", "false", "no"):
            store = False
        if store and facts:
            try:
                await graph_processor._store_discovery_nodes(  # type: ignore
                    project_id=project_id,
                    document_id=request.document_id or f"doc_{hash(request.filename) % 100000}",
                    facts=facts,
                    filename=request.filename or "structured_document",
                )
            except Exception as e:  # non-fatal
                logger.warning(f"Storing structured facts failed: {e}")

        return {
            "status": "success",
            "document_id": request.document_id,
            "filename": request.filename,
            "count": len(facts),
            "facts": facts,
            "stored": store and bool(facts)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Structured fact extraction failed for document {request.filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Structured fact extraction failed: {str(e)}")

async def _extract_entities_from_structured_elements(
    project_id: str,
    elements: List[StructuredDocumentElement],
    graph_processor,
    original_filename: str,
    correlation_id: Optional[str] = None,
) -> tuple[int, Dict[str, int], int, Dict[str, int]]:
    """Enhanced entity extraction with document type detection and specialized processing"""
    # Local import to avoid circulars at module import time
    try:
        from app.core.graph_processor import Entity, Relationship, EntityExtractionResult
    except Exception:
        Entity = None  # type: ignore
        Relationship = None  # type: ignore
        EntityExtractionResult = None  # type: ignore
    entities_count = 0
    entity_types: Dict[str, int] = {}
    relationships_count = 0
    relationship_types: Dict[str, int] = {}

    try:
        # Convert StructuredDocumentElement to dict format for graph processor
        element_dicts = []
        for elem in elements:
            element_dicts.append({
                'text': elem.content or '',
                'element_type': elem.element_type,
                'metadata': elem.metadata or {},
                'element_id': elem.element_id,
                'page_number': elem.page_number,
                'hierarchy_level': elem.hierarchy_level
            })

        # Detect document type using the enhanced graph processor
        document_type = graph_processor.detect_document_type(element_dicts, original_filename)
        logger.info(f"Detected document type: {document_type}")

        # Filter elements based on document type
        filtered_elements = graph_processor.filter_elements_for_extraction(element_dicts, document_type)
        logger.info(f"Filtered {len(element_dicts)} elements down to {len(filtered_elements)} suitable elements")

        # NEW: Preserve table-like elements from the original list for specialized handling
        # Some sources (e.g., CSV uploads) may be emitted as generic text/narrative elements.
        # Detect "table-like" by type OR by delimiter heuristics in content.
        def _is_table_like_structured_element(elem: StructuredDocumentElement) -> bool:
            """Detect table-like elements by type, content delimiters, or structured metadata (columns/rows)."""
            try:
                # 1) Type hint
                t = (elem.element_type or '').strip().lower()
                if t in ("table", "table_row", "tabular", "csv"):
                    return True

                # 2) Metadata hint (columns/rows present under metadata)
                md = elem.metadata or {}
                if isinstance(md, dict):
                    # metadata.table_data with columns/rows
                    td = md.get("table_data") or md.get("table")
                    if isinstance(td, dict):
                        cols = td.get("columns")
                        rows = td.get("rows")
                        if cols and rows:
                            return True
                    # metadata with top-level columns/rows
                    if md.get("columns") and md.get("rows"):
                        return True

                # 3) Content heuristic: delimiter-based header + data row
                content = (elem.content or '').strip()
                if not content:
                    return False
                lines = [ln.strip() for ln in content.replace('\r\n', '\n').replace('\r', '\n').split('\n') if ln.strip()]
                if len(lines) < 2:
                    return False
                for d in [',', '\t', '|', ';']:
                    if (d in lines[0]) and (d in lines[1]):
                        if len([c for c in lines[0].split(d) if c.strip()]) >= 2:
                            return True
                return False
            except Exception:
                return False

        def _table_metadata_to_csv(elem: StructuredDocumentElement) -> Optional[str]:
            """Materialize CSV text from metadata-contained table schema if available.
            Looks for metadata.table_data.columns/rows or metadata.columns/rows.
            """
            try:
                md = elem.metadata or {}
                if not isinstance(md, dict):
                    return None
                td = md.get("table_data") or md.get("table")
                columns = None
                rows = None
                if isinstance(td, dict):
                    columns = td.get("columns")
                    rows = td.get("rows")
                if (columns is None or rows is None) and md:
                    if md.get("columns") and md.get("rows"):
                        columns = md.get("columns")
                        rows = md.get("rows")
                if not columns or not rows:
                    return None
                # Flatten to CSV lines
                def _flat(v: Any) -> str:
                    try:
                        if v is None:
                            return ''
                        if isinstance(v, str):
                            return v
                        if isinstance(v, (list, tuple)):
                            return ' '.join(str(x) for x in v)
                        if isinstance(v, dict):
                            return ','.join(f"{k}={v[k]}" for k in v)
                        return str(v)
                    except Exception:
                        return str(v)
                header = ','.join(_flat(c) for c in columns)
                row_lines = []
                for r in rows:
                    if isinstance(r, (list, tuple)):
                        row_lines.append(','.join(_flat(x) for x in r))
                    else:
                        row_lines.append(_flat(r))
                if not header or not row_lines:
                    return None
                return header + "\n" + "\n".join(row_lines)
            except Exception:
                return None

        table_like = [e for e in elements if _is_table_like_structured_element(e)]
        # If element looks table-like only by metadata, but has no CSV content, materialize CSV in-place for deterministic parsing
        table_like_ready: List[StructuredDocumentElement] = []
        for e in table_like:
            try:
                content_ok = False
                ctext = (e.content or '').strip()
                if ctext:
                    lines = [ln.strip() for ln in ctext.replace('\r\n', '\n').replace('\r', '\n').split('\n') if ln.strip()]
                    content_ok = len(lines) >= 2
                if not content_ok:
                    csv_txt = _table_metadata_to_csv(e)
                    if csv_txt:
                        try:
                            e = StructuredDocumentElement(
                                element_id=e.element_id,
                                content=csv_txt,
                                element_type=e.element_type or 'table',
                                page_number=e.page_number,
                                hierarchy_level=e.hierarchy_level,
                                metadata=e.metadata,
                            )
                        except Exception:
                            # fallback: mutate content on existing instance
                            try:
                                setattr(e, 'content', csv_txt)
                                if not getattr(e, 'element_type', None):
                                    setattr(e, 'element_type', 'table')
                            except Exception:
                                pass
                table_like_ready.append(e)
            except Exception:
                table_like_ready.append(e)

        table_like = table_like_ready
        logger.info(f"Detected {len(table_like)} table-like structured elements for specialized processing (type, delimiter, or metadata-based)")

        if not filtered_elements and not table_like:
            logger.warning(f"No suitable elements found for {document_type} document type (including tables)")
            return 0, {}, 0, {}

        # Use specialized extraction based on document type
        if document_type == 'diagram':
            # Use diagram-specific entity extraction
            entities = graph_processor.extract_diagram_entities(filtered_elements)
            relationships = []  # Diagrams typically don't have explicit relationships

            logger.info(f"Diagram extraction completed: {len(entities)} entities extracted")

            # Create extraction result for diagram entities
            if entities:
                extraction_result = EntityExtractionResult(
                    project_id=project_id,
                    document_id=f"diagram_doc_{project_id}_{hash(str(filtered_elements)) % 10000}",
                    entities=entities,
                    relationships=relationships,
                    metadata={
                        "extraction_timestamp": datetime.utcnow().isoformat(),
                        "strategy": "diagram_specialized_extraction",
                        "document_type": document_type,
                        "filtered_elements": len(filtered_elements)
                    },
                )

                # Add entities to graph
                await graph_processor.add_entities_to_graph(project_id, extraction_result)
                entities_count = len(entities)
                relationships_count = 0
                relationship_types = {}

                # Count entity types
                for entity in entities:
                    entity_type = entity.type
                    entity_types[entity_type] = entity_types.get(entity_type, 0) + 1

                logger.info(f"Successfully extracted and stored {entities_count} diagram entities with types: {entity_types}")
        else:
                # Use standard LLM-based extraction for regular documents
                # Prefer actual JSONL-like rows from table elements; cap non-table narrative to avoid huge prompts
                def _rows_from_tables(elems: List[StructuredDocumentElement]) -> List[Dict[str, Any]]:
                    rows_out: List[Dict[str, Any]] = []
                    try:
                        import csv
                        from io import StringIO
                    except Exception:
                        csv = None  # type: ignore
                        StringIO = None  # type: ignore

                    # 1) Use explicit metadata (columns/rows)
                    for e in elems:
                        md = e.metadata or {}
                        td = None
                        if isinstance(md, dict):
                            td = md.get("table_data") or md.get("table")
                        if isinstance(td, dict) and td.get("columns") and td.get("rows"):
                            cols = [str(c) for c in td["columns"]]
                            for r in td["rows"]:
                                if isinstance(r, (list, tuple)):
                                    obj = {str(cols[i]): (None if i >= len(r) else (r[i] if r[i] is not None else "")) for i in range(len(cols))}
                                    rows_out.append(obj)
                                elif isinstance(r, dict):
                                    # already keyed
                                    rows_out.append({str(k): r.get(k) for k in r.keys()})
                            continue

                    # 2) Parse CSV/TSV/pipe text when present
                    for e in elems:
                        content = (e.content or '').strip()
                        if not content:
                            continue
                        try:
                            text = content.replace('\r\n', '\n').replace('\r', '\n')
                            sample = '\n'.join(text.split('\n')[:5])
                            delimiter = None
                            try:
                                import csv as _csv
                                sniffed = _csv.Sniffer().sniff(sample, delimiters=",\t|;")
                                delimiter = sniffed.delimiter
                            except Exception:
                                # fallback: pick most frequent in header
                                header_line = text.split('\n', 1)[0]
                                counts = {d: header_line.count(d) for d in [',','\t','|',';']}
                                delimiter = max(counts, key=counts.get) if any(counts.values()) else ','
                            reader = csv.reader(StringIO(text), delimiter=delimiter) if (csv and StringIO) else None  # type: ignore
                            if reader is None:
                                continue
                            matrix = [r for r in reader if any((c or '').strip() for c in r)]
                            if len(matrix) < 2:
                                continue
                            headers = [str(h).strip() for h in matrix[0]]
                            for row in matrix[1:]:
                                obj = {headers[i]: (None if i >= len(row) else row[i]) for i in range(len(headers))}
                                rows_out.append(obj)
                        except Exception:
                            continue
                    return rows_out

                def _rows_to_text(rows_part: List[Dict[str, Any]]) -> str:
                    # Same approach as unified extractor: stable header order across sample
                    keys: List[str] = []
                    seen = set()
                    for r in rows_part[:50]:
                        for k in r.keys():
                            if k not in seen:
                                seen.add(k)
                                keys.append(k)
                    header = ",".join(keys)
                    lines = [header]
                    for r in rows_part:
                        vals = []
                        for k in keys:
                            v = r.get(k)
                            s = "" if v is None else str(v)
                            s = s.replace("\n", " ").replace("\r", " ").replace(",", ";")
                            vals.append(s)
                        lines.append(",".join(vals))
                    return "\n".join(lines)

                table_rows = _rows_from_tables(table_like)
                logger.info(f"Materialized {len(table_rows)} JSONL-like rows from table elements")

                # Build compact narrative from filtered non-table elements (cap to 10 items and ~10k chars)
                narrative_parts: List[str] = []
                for elem in filtered_elements[:10]:
                    txt = str(elem.get('text', '')).strip()
                    if not txt:
                        continue
                    narrative_parts.append(f"[{elem.get('element_type', 'unknown').upper()}] {txt}")
                narrative = "\n\n".join(narrative_parts)
                if len(narrative) > 10000:
                    narrative = narrative[:10000]

                # Prefer rows; if none, fall back to narrative
                if table_rows:
                    text = _rows_to_text(table_rows[:1000])  # safety cap
                    filename = f"{original_filename or 'structured'}#rows.csv"
                    document_id = f"structured_rows_{project_id}_{hash(text) % 10000}"
                else:
                    if not narrative.strip():
                        logger.warning("No meaningful content found after filtering")
                        return 0, {}, 0, {}
                    text = narrative
                    filename = f"{original_filename or 'structured'}#narrative.txt"
                    document_id = f"structured_doc_{project_id}_{hash(text) % 10000}"

                logger.info(f"Calling LLM entity extraction with document_id: {document_id}")

                extraction_result = await graph_processor.extract_entities_from_document(
                    project_id=project_id,
                    document_content=text,
                    filename=filename,
                    document_id=document_id,
                    correlation_id=correlation_id,
                )

                logger.info(f"LLM extraction completed: {len(extraction_result.entities)} entities, {len(extraction_result.relationships)} relationships")

                # If table-like data exists, complement with deterministic parsing to capture rows
                det_entities = []
                det_relationships = []
                if table_like:
                    try:
                        det_entities, det_relationships = _deterministic_entities_from_tables(table_like)
                        logger.info(f"Deterministic table parsing produced {len(det_entities)} entities and {len(det_relationships)} relationships")
                    except Exception as de:
                        logger.warning(f"Deterministic table parsing failed: {de}")

                # Add entities to graph
                if extraction_result.entities or extraction_result.relationships or det_entities or det_relationships:
                    # Merge LLM and deterministic outputs when available
                    if (det_entities or det_relationships) and hasattr(extraction_result, 'entities'):
                        try:
                            extraction_result.entities.extend(det_entities)
                            extraction_result.relationships.extend(det_relationships)
                            # Update metadata counts
                            if hasattr(extraction_result, 'metadata') and isinstance(extraction_result.metadata, dict):
                                extraction_result.metadata["deterministic_tables"] = {
                                    "entities": len(det_entities),
                                    "relationships": len(det_relationships)
                                }
                        except Exception:
                            pass

                    # Compute counts before persisting
                    entities_count = len(extraction_result.entities)
                    relationships_count = len(extraction_result.relationships)

                    # Count entity and relationship types
                    for entity in extraction_result.entities:
                        entity_type = entity.type
                        entity_types[entity_type] = entity_types.get(entity_type, 0) + 1
                    for rel in extraction_result.relationships:
                        try:
                            rtype = rel.type
                        except Exception:
                            rtype = getattr(rel, 'relation_type', 'REL')
                        relationship_types[rtype] = relationship_types.get(rtype, 0) + 1

                    # Persist to graph
                    await graph_processor.add_entities_to_graph(project_id, extraction_result)

                    logger.info(f"Successfully extracted and stored {entities_count} entities with types: {entity_types}")
                else:
                    logger.warning("LLM extraction returned no entities or relationships")
            
        return entities_count, entity_types, relationships_count, relationship_types

    except Exception as e:
        logger.error(f"Enhanced entity extraction failed: {e}")
        logger.error(f"Error details: {type(e).__name__}: {str(e)}")
        # Don't fail the entire process, return empty results
        return 0, {}, 0, {}

def _summarize_tables_to_text(table_elements: List[StructuredDocumentElement]) -> List[str]:
    """Convert table-like structured elements into a compact, LLM-friendly textual summary.
    Heuristics: detect delimiter-based rows and join first few rows; otherwise return raw content trimmed.
    """
    summaries: List[str] = []
    for elem in table_elements[:10]:  # cap to avoid huge prompts
        content = (elem.content or '').strip()
        if not content:
            continue
        # Normalize line breaks and trim
        lines = [ln.strip() for ln in content.replace('\r\n', '\n').replace('\r', '\n').split('\n') if ln.strip()]
        if not lines:
            continue
        # Detect delimiter: prefer comma, then tab, then pipe
        delim = None
        for d in [',', '\t', '|', ';']:
            if any(d in ln for ln in lines[:3]):
                delim = d
                break
        if delim:
            # Keep header + first few rows
            head = lines[0]
            rows = lines[1:6]
            summaries.append(f"TABLE: headers={head} rows={'; '.join(rows)}")
        else:
            # Fallback: join first 5 lines
            summaries.append("TABLE: " + " | ".join(lines[:5]))
    return summaries

def _deterministic_entities_from_tables(table_elements: List[StructuredDocumentElement]) -> Tuple[List[Any], List[Any]]:
    """Robust parser for CSV/TSV/Pipe tables to create Entities and Relationships without LLM.
    Uses Python's csv module (with delimiter sniffing) to correctly handle quoted fields and commas.
    Recognizes rich header aliases and builds nodes for Server/Application/Database/Technology and auxiliary
    types (Environment, InfrastructureComponent for OS, Network, Location, Team, Port). Creates edges:
        - HOSTS: Server -> Application
        - CONNECTS_TO: Application -> Database; Server -> Server (from connections column); Application -> inferred DBs
        - USES: Application -> Technology (or Server -> Technology in regex fallback)
        - RUNS_ON: Server -> OS
        - BELONGS_TO: Server -> Environment
        - LOCATED_IN: Server -> Location (Region/Datacenter)
        - IN_SUBNET: Server -> Network (Subnet/VLAN)
        - OWNS: Team -> (Server|Application)
        - EXPOSES_PORT: Server -> Port
    """
    try:
        from app.core.graph_processor import Entity, Relationship
    except Exception:
        # If imports fail (during static analysis), return no-op
        return [], []

    import csv
    import re
    from io import StringIO

    def norm(s: Optional[str]) -> str:
        return (s or '').strip()

    # Header alias maps (expanded)
    server_aliases = [
        'server', 'host', 'hostname', 'server name', 'servername', 'vm', 'vm name', 'machine', 'node', 'instance'
    ]
    app_aliases = [
        'application', 'app', 'service', 'svc', 'component', 'app name', 'application name', 'service name',
        'purpose', 'function', 'business function', 'role', 'system', 'product'
    ]
    db_aliases = [
        'database', 'db', 'db name', 'database name', 'schema', 'datasource', 'db server', 'database server', 'dbms', 'rdbms'
    ]
    tech_aliases = [
        'technology', 'tech', 'framework', 'platform', 'stack', 'tech stack', 'technology stack', 'language', 'runtime', 'middleware'
    ]
    os_aliases = [
        'os', 'operating system', 'platform', 'os version', 'operating system version', 'os_name', 'os name', 'os type', 'operating system name'
    ]
    env_aliases = [
        'environment', 'env', 'stage', 'lifecycle'
    ]
    ip_aliases = [
        'ip', 'ip address', 'ipaddr', 'address'
    ]
    port_aliases = [
        'port', 'ports', 'listening ports', 'exposed ports'
    ]
    subnet_aliases = [
        'subnet', 'vlan', 'cidr', 'network'
    ]
    region_aliases = [
        'region', 'location', 'datacenter', 'dc', 'zone', 'availability zone'
    ]
    team_aliases = [
        'team', 'owner', 'group', 'department', 'dept', 'squad'
    ]
    server_type_aliases = [
        'type', 'server type', 'role'
    ]
    connections_aliases = [
        'connects to', 'connections', 'peers', 'upstream', 'downstream', 'depends on', 'talks to', 'communicates with', 'calls', 'calls service', 'calls api'
    ]

    def pick_index(headers: List[str], aliases: List[str]) -> Optional[int]:
        for i, h in enumerate(headers):
            hl = h.strip().lower()
            for a in aliases:
                if a in hl:
                    return i
        return None

    # Known database technology names for inference when explicit DB column is missing
    known_db_tech = {
        'mysql', 'mariadb', 'postgres', 'postgresql', 'ms sql', 'mssql', 'sql server', 'oracle', 'oracle db',
        'mongodb', 'redis', 'elasticsearch', 'cassandra', 'dynamodb', 'cosmosdb', 'cosmos db'
    }

    entities_map: Dict[str, Any] = {}
    relationships: List[Any] = []

    for elem in table_elements:
        content = norm(elem.content)
        if not content:
            continue
        # Normalize newlines
        text = content.replace('\r\n', '\n').replace('\r', '\n')
        # Try to sniff delimiter; fall back through common ones
        sample = '\n'.join(text.split('\n')[:5])
        delim_candidates = [',', '\t', '|', ';']
        sniffed = None
        try:
            sniffed = csv.Sniffer().sniff(sample, delimiters=''.join(delim_candidates))
        except Exception:
            sniffed = None
        if sniffed is not None:
            delimiter = sniffed.delimiter
        else:
            # heuristic: pick the most frequent delimiter in header line
            header_line = text.split('\n', 1)[0]
            counts = {d: header_line.count(d) for d in delim_candidates}
            delimiter = max(counts, key=counts.get) if any(counts.values()) else ','

        reader = csv.reader(StringIO(text), delimiter=delimiter)
        rows: List[List[str]] = [r for r in reader if any(c.strip() for c in r)]
        # If we didn't get at least a header and one data row, try a regex-based fallback
        # Common in our JSONL: a gigantic single line like
        # "ServerName Type OS SoftwarePackages Purpose server0001 Proxy Ubuntu 20.04 Apache, MySQL, PHP Backup Storage ..."
        # In such case, split content into pseudo-rows at each serverXXXX token boundary and
        # detect technologies by keyword matching.
        if len(rows) < 2:
            try:
                # Build a list of known technologies to extract
                tech_keywords: Dict[str, str] = {
                    r"\bapache\b": "Apache",
                    r"\bnginx\b": "Nginx",
                    r"\biis\b": "IIS",
                    r"\bmysql\b": "MySQL",
                    r"\bpostgres(?:ql)?\b": "PostgreSQL",
                    r"\boracle\b": "Oracle",
                    r"\bmongo ?db\b": "MongoDB",
                    r"\bsql server\b": "SQL Server",
                    r"\bdocker\b": "Docker",
                    r"\bkubernetes\b": "Kubernetes",
                    r"\bhelm\b": "Helm",
                    r"\bredis\b": "Redis",
                    r"\brabbitmq\b": "RabbitMQ",
                    r"\btomcat\b": "Tomcat",
                    r"\bjboss\b": "JBoss",
                    r"\bglassfish\b": "GlassFish",
                    r"\bnode(?:\.js)?\b": "Node.js",
                    r"\bpython\b": "Python",
                    r"\bphp\b": "PHP",
                    r"\bjava\b": "Java",
                    r"\bgo(lang)?\b": "Golang",
                    r"\bruby\b": "Ruby",
                    r"\belastic ?search\b": "Elasticsearch",
                    r"\bkafka\b": "Kafka",
                    r"\bzoo ?keeper\b": "Zookeeper",
                    r"\bspark\b": "Spark",
                    r"\bhadoop\b": "Hadoop",
                }
                # Find server boundaries
                server_pattern = re.compile(r"\bserver\d{3,}\b", re.IGNORECASE)
                matches = list(server_pattern.finditer(text))
                if not matches:
                    # Nothing to do
                    continue
                # Slice into segments per server
                segments: List[str] = []
                for i, m in enumerate(matches):
                    start = m.start()
                    end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
                    seg = text[start:end]
                    # Join accidental newlines within a segment to simplify parsing
                    segments.append(seg.replace('\n', ' ').strip())
                for seg in segments[:100]:  # cap to avoid overload
                    # Extract server name
                    m = server_pattern.search(seg)
                    if not m:
                        continue
                    server_name = m.group(0)
                    sid = f"server:{server_name.lower()}"
                    if sid not in entities_map:
                        entities_map[sid] = Entity(id=sid, type="Server", name=server_name, properties={})
                    # Extract technologies present in the segment
                    lower_seg = seg.lower()
                    for pattern, canon in tech_keywords.items():
                        if re.search(pattern, lower_seg):
                            tid = f"technology:{canon.lower()}"
                            if tid not in entities_map:
                                entities_map[tid] = Entity(id=tid, type="Technology", name=canon, properties={})
                            relationships.append(
                                Relationship(
                                    source_id=sid,
                                    target_id=tid,
                                    type="USES",
                                    properties={}
                                )
                            )
                # Done with regex fallback for this element; go to next element
                continue
            except Exception:
                # If fallback also fails, skip element
                continue

        headers = [norm(h).lower() for h in rows[0]]
        idx_server = pick_index(headers, server_aliases)
        idx_app = pick_index(headers, app_aliases)
        idx_db = pick_index(headers, db_aliases)
        idx_tech = pick_index(headers, tech_aliases)
        idx_os = pick_index(headers, os_aliases)
        idx_env = pick_index(headers, env_aliases)
        idx_ip = pick_index(headers, ip_aliases)
        idx_ports = pick_index(headers, port_aliases)
        idx_subnet = pick_index(headers, subnet_aliases)
        idx_region = pick_index(headers, region_aliases)
        idx_team = pick_index(headers, team_aliases)
        idx_srvtype = pick_index(headers, server_type_aliases)
        idx_conns = pick_index(headers, connections_aliases)

        if all(v is None for v in [idx_server, idx_app, idx_db, idx_tech]):
            # No meaningful columns detected; fallback to regex segmentation within this element
            try:
                tech_keywords2: Dict[str, str] = {
                    r"\bapache\b": "Apache",
                    r"\bnginx\b": "Nginx",
                    r"\biis\b": "IIS",
                    r"\bmysql\b": "MySQL",
                    r"\bpostgres(?:ql)?\b": "PostgreSQL",
                    r"\boracle\b": "Oracle",
                    r"\bmongo ?db\b": "MongoDB",
                    r"\bsql server\b": "SQL Server",
                    r"\bdocker\b": "Docker",
                    r"\bkubernetes\b": "Kubernetes",
                    r"\bhelm\b": "Helm",
                    r"\bredis\b": "Redis",
                    r"\brabbitmq\b": "RabbitMQ",
                    r"\btomcat\b": "Tomcat",
                    r"\bjboss\b": "JBoss",
                    r"\bglassfish\b": "GlassFish",
                    r"\bnode(?:\.js)?\b": "Node.js",
                    r"\bpython\b": "Python",
                    r"\bphp\b": "PHP",
                    r"\bjava\b": "Java",
                    r"\bgo(lang)?\b": "Golang",
                    r"\bruby\b": "Ruby",
                    r"\belastic ?search\b": "Elasticsearch",
                    r"\bkafka\b": "Kafka",
                    r"\bzoo ?keeper\b": "Zookeeper",
                    r"\bspark\b": "Spark",
                    r"\bhadoop\b": "Hadoop",
                }
                server_pattern2 = re.compile(r"\bserver\d{3,}\b", re.IGNORECASE)
                joined = '\n'.join(' | '.join(r) for r in rows)
                segments2: List[str] = []
                matches2 = list(server_pattern2.finditer(joined))
                if not matches2:
                    continue
                for i, m2 in enumerate(matches2):
                    start = m2.start()
                    end = matches2[i + 1].start() if i + 1 < len(matches2) else len(joined)
                    segments2.append(joined[start:end])
                for seg in segments2[:100]:
                    mm = server_pattern2.search(seg)
                    if not mm:
                        continue
                    sname = mm.group(0)
                    sid = f"server:{sname.lower()}"
                    if sid not in entities_map:
                        entities_map[sid] = Entity(id=sid, type="Server", name=sname, properties={})
                    low = seg.lower()
                    for pattern, canon in tech_keywords2.items():
                        if re.search(pattern, low):
                            tid = f"technology:{canon.lower()}"
                            if tid not in entities_map:
                                entities_map[tid] = Entity(id=tid, type="Technology", name=canon, properties={})
                            relationships.append(Relationship(source_id=sid, target_id=tid, type="USES", properties={}))
            except Exception:
                pass
            continue

    for row in rows[1:101]:  # cap to first 100 data rows
            # Guard variable-length rows
            def get(i: Optional[int]) -> str:
                if i is None:
                    return ''
                try:
                    return norm(row[i]) if i < len(row) else ''
                except Exception:
                    return ''

            server = get(idx_server)
            app = get(idx_app)
            db = get(idx_db)
            tech = get(idx_tech)
            os_val = get(idx_os)
            env_val = get(idx_env)
            ip_val = get(idx_ip)
            ports_val = get(idx_ports)
            subnet_val = get(idx_subnet)
            region_val = get(idx_region)
            team_val = get(idx_team)
            srvtype_val = get(idx_srvtype)
            conns_val = get(idx_conns)

            # Create entities
            if server:
                sid = f"server:{server.lower()}"
                if sid not in entities_map:
                    entities_map[sid] = Entity(id=sid, type="Server", name=server, properties={})
                # enrich server properties
                if srvtype_val:
                    try:
                        entities_map[sid].properties.setdefault('role', srvtype_val)
                    except Exception:
                        pass
                if ip_val:
                    try:
                        entities_map[sid].properties.setdefault('ip_address', ip_val)
                    except Exception:
                        pass
                if ports_val:
                    try:
                        entities_map[sid].properties.setdefault('ports', ports_val)
                    except Exception:
                        pass
            if app:
                aid = f"application:{app.lower()}"
                if aid not in entities_map:
                    entities_map[aid] = Entity(id=aid, type="Application", name=app, properties={})
            if db:
                did = f"database:{db.lower()}"
                if did not in entities_map:
                    entities_map[did] = Entity(id=did, type="Database", name=db, properties={})
            if tech:
                tid = f"technology:{tech.lower()}"
                if tid not in entities_map:
                    entities_map[tid] = Entity(id=tid, type="Technology", name=tech, properties={})

            # If OS column absent, infer OS from concatenated row content heuristically
            if not os_val:
                try:
                    row_text = ' '.join([c for c in row if isinstance(c, str)]).lower()
                    if any(tok in row_text for tok in ['windows', 'win32', 'win64', 'iis']):
                        os_val = 'Windows'
                    elif 'ubuntu' in row_text:
                        os_val = 'Ubuntu'
                    elif 'centos' in row_text:
                        os_val = 'CentOS'
                    elif 'rhel' in row_text or 'red hat' in row_text or 'redhat' in row_text:
                        os_val = 'RHEL'
                    elif 'debian' in row_text:
                        os_val = 'Debian'
                    elif 'suse' in row_text or 'sles' in row_text:
                        os_val = 'SUSE'
                    elif 'amazon linux' in row_text:
                        os_val = 'Amazon Linux'
                    elif 'alpine' in row_text:
                        os_val = 'Alpine'
                except Exception:
                    pass

            # Additional entities: OS, Environment, Network/Subnet, Location, Team, Port(s), IP(s)
            # Promote OS as a first-class type for UI discoverability
            if os_val:
                oid = f"os:{os_val.lower()}"
                if oid not in entities_map:
                    # Use canonical type 'OS' instead of generic InfrastructureComponent
                    # Keep subtype for backwards-compat if other parts look for it
                    entities_map[oid] = Entity(
                        id=oid,
                        type="OS",
                        name=os_val,
                        properties={"subtype": "OS"}
                    )
            if env_val:
                evid = f"environment:{env_val.lower()}"
                if evid not in entities_map:
                    entities_map[evid] = Entity(id=evid, type="Environment", name=env_val, properties={})
            if subnet_val:
                nid = f"network:{subnet_val.lower()}"
                if nid not in entities_map:
                    entities_map[nid] = Entity(id=nid, type="Network", name=subnet_val, properties={})
            if region_val:
                lid = f"location:{region_val.lower()}"
                if lid not in entities_map:
                    entities_map[lid] = Entity(id=lid, type="Location", name=region_val, properties={})
            if team_val:
                tid2 = f"team:{team_val.lower()}"
                if tid2 not in entities_map:
                    entities_map[tid2] = Entity(id=tid2, type="Team", name=team_val, properties={})
            # IP(s): in addition to keeping server.ip_address property, create IP nodes + HAS_IP edges
            if server and ip_val:
                # Split on common separators; accept IPv4/IPv6 tokens and simple host IP-like values
                ip_tokens = [pp.strip() for pp in re.split(r"[,|;/\s]+", ip_val) if pp and pp.strip()]
                for ip in ip_tokens:
                    # Basic sanity check for IPv4 or IPv6-ish strings
                    if not re.match(r"^(?:\d{1,3}\.){3}\d{1,3}$", ip) and \
                       not re.match(r"^[0-9A-Fa-f:]{2,}$", ip):
                        # Skip obviously non-IP tokens
                        continue
                    ipid = f"ip:{ip.lower()}"
                    if ipid not in entities_map:
                        entities_map[ipid] = Entity(id=ipid, type="IP", name=ip, properties={})
                    relationships.append(
                        Relationship(
                            source_id=f"server:{server.lower()}",
                            target_id=ipid,
                            type="HAS_IP",
                            properties={}
                        )
                    )

            # Infer Database from technology when DB column is absent
            inferred_db_ids: List[str] = []
            if not db and tech:
                parts = [p.strip() for p in re.split(r"[,|;/]", tech) if p.strip()]
                for p in parts:
                    pl = p.lower()
                    if pl in known_db_tech:
                        did2 = f"database:{pl}"
                        if did2 not in entities_map:
                            entities_map[did2] = Entity(id=did2, type="Database", name=p, properties={"inferred": True})
                        inferred_db_ids.append(did2)

            # Relationships
            if server and app:
                relationships.append(Relationship(source_id=f"server:{server.lower()}", target_id=f"application:{app.lower()}", type="HOSTS", properties={}))
            if app and db:
                relationships.append(Relationship(source_id=f"application:{app.lower()}", target_id=f"database:{db.lower()}", type="CONNECTS_TO", properties={}))
            if app and tech:
                parts = [p.strip() for p in re.split(r"[,|;/]", tech) if p.strip()]
                for p in parts or [tech]:
                    relationships.append(Relationship(source_id=f"application:{app.lower()}", target_id=f"technology:{p.lower()}", type="USES", properties={}))

            # Connect to inferred databases (from technology cell)
            if app and inferred_db_ids:
                for did2 in inferred_db_ids:
                    relationships.append(Relationship(source_id=f"application:{app.lower()}", target_id=did2, type="CONNECTS_TO", properties={"inferred": True}))

            # RUNS_ON, BELONGS_TO, LOCATED_IN, IN_SUBNET
            if server and os_val:
                relationships.append(Relationship(source_id=f"server:{server.lower()}", target_id=f"os:{os_val.lower()}", type="RUNS_ON", properties={}))
            if server and env_val:
                relationships.append(Relationship(source_id=f"server:{server.lower()}", target_id=f"environment:{env_val.lower()}", type="BELONGS_TO", properties={}))
            if server and region_val:
                relationships.append(Relationship(source_id=f"server:{server.lower()}", target_id=f"location:{region_val.lower()}", type="LOCATED_IN", properties={}))
            if server and subnet_val:
                relationships.append(Relationship(source_id=f"server:{server.lower()}", target_id=f"network:{subnet_val.lower()}", type="IN_SUBNET", properties={}))

            # OWNS: Team relationships
            if team_val and server:
                relationships.append(Relationship(source_id=f"team:{team_val.lower()}", target_id=f"server:{server.lower()}", type="OWNS", properties={}))
            if team_val and app:
                relationships.append(Relationship(source_id=f"team:{team_val.lower()}", target_id=f"application:{app.lower()}", type="OWNS", properties={}))

            # EXPOSES_PORT: create Port nodes and edges (optional, when ports present)
            if server and ports_val:
                port_parts = [pp.strip() for pp in re.split(r"[,|;/\s]+", ports_val) if pp.strip()]
                for pp in port_parts:
                    pid = f"port:{pp.lower()}"
                    if pid not in entities_map:
                        entities_map[pid] = Entity(id=pid, type="Port", name=pp, properties={})
                    relationships.append(Relationship(source_id=f"server:{server.lower()}", target_id=pid, type="EXPOSES_PORT", properties={}))

            # CONNECTS_TO from connections column: Server->Server
            if server and conns_val:
                targets = [t.strip() for t in re.split(r"[,|;/]", conns_val) if t.strip()]
                for tgt in targets:
                    tid = f"server:{tgt.lower()}"
                    if tid not in entities_map:
                        entities_map[tid] = Entity(id=tid, type="Server", name=tgt, properties={"inferred": True})
                    relationships.append(Relationship(source_id=f"server:{server.lower()}", target_id=tid, type="CONNECTS_TO", properties={"source": "connections_column"}))

    # Deduplicate relationships
    rel_seen = set()
    dedup_relationships: List[Any] = []
    for r in relationships:
        key = (r.source_id, r.target_id, r.type)
        if key in rel_seen:
            continue
        rel_seen.add(key)
        dedup_relationships.append(r)

    return list(entities_map.values()), dedup_relationships

async def _extract_relationships_from_structured_elements(
    project_id: str,
    elements: List[StructuredDocumentElement],
    graph_processor
) -> tuple[int, Dict[str, int]]:
    """Extract relationships from structured elements using LLM-based analysis"""
    relationships_count = 0
    relationship_types = {}
    
    try:
        # Look for relationships in narrative text and lists
        narrative_elements = [
            elem for elem in elements 
            if elem.element_type in ['narrative_text', 'list_item']
            and len(elem.content.strip()) > 30
        ]
        
        logger.info(f"Processing {len(narrative_elements)} narrative elements for relationship extraction")
        
        if not narrative_elements:
            logger.warning("No suitable narrative elements found for relationship extraction")
            return 0, {}
        
        # The relationship extraction is already handled by the main entity extraction
        # in _extract_entities_from_structured_elements since the LLM call extracts both
        # entities and relationships. We'll get the relationship counts from there.
        
        # For now, return zero since relationships are extracted together with entities
        # in the combined LLM call to avoid duplication
        logger.info("Relationships are extracted together with entities in the main LLM call")
        
        return 0, {}
        
    except Exception as e:
        logger.error(f"Relationship extraction process failed: {e}")
        return 0, {}

# Entity extraction helper functions removed - now using real LLM calls

# Relationship extraction helper functions removed - now using real LLM calls

async def _create_entity_node(
    project_id: str, 
    entity_name: str, 
    entity_type: str, 
    source_element_id: str,
    graph_processor
):
    """Create an entity node in Neo4j"""
    try:
        # Prefer canonical_id-based upsert to avoid name collisions
        try:
            from app.core.id_utils import make_canonical_id as _make_canonical_id
        except Exception:
            _make_canonical_id = None  # type: ignore
        etype = (entity_type or "Entity").strip() or "Entity"
        ename = (entity_name or "").strip()
        if _make_canonical_id is not None:
            cid = _make_canonical_id(project_id, etype, ename, None)
        else:
            import hashlib as _hashlib
            cid = f"{project_id}:{etype.lower()}:{_hashlib.sha1((ename or '').encode('utf-8', errors='ignore')).hexdigest()[:12]}"
        async with graph_processor.neo4j_driver.session() as session:
            await session.run(
                """
                MERGE (p:Project {id: $project_id})
                MERGE (e:Entity {canonical_id: $cid})
                ON CREATE SET e.created_at = datetime(), e.project_id = $project_id, e.type = $entity_type, e.id = $cid, e.name = $entity_name
                SET e.source_element_id = $source_element_id,
                    e.updated_at = datetime()
                MERGE (p)-[:CONTAINS]->(e)
                """,
                project_id=project_id,
                cid=cid,
                entity_name=entity_name,
                entity_type=entity_type,
                source_element_id=source_element_id
            )
    except Exception as e:
        logger.error(f"Failed to create entity node: {e}")

async def _create_relationship(
    project_id: str,
    source_entity: str,
    target_entity: str,
    relationship_type: str,
    source_element_id: str,
    graph_processor
):
    """Create a relationship between entities in Neo4j"""
    try:
        try:
            from app.core.id_utils import make_canonical_id as _make_canonical_id
        except Exception:
            _make_canonical_id = None  # type: ignore
        sname = (source_entity or "").strip()
        tname = (target_entity or "").strip()
        rtype = (relationship_type or "RELATIONSHIP").strip() or "RELATIONSHIP"
        # Types are unknown in this helper; default to Entity to compute cid deterministically
        if _make_canonical_id is not None:
            sid = _make_canonical_id(project_id, "Entity", sname, None)
            tid = _make_canonical_id(project_id, "Entity", tname, None)
        else:
            import hashlib as _hashlib
            sid = f"{project_id}:entity:{_hashlib.sha1(sname.encode('utf-8', errors='ignore')).hexdigest()[:12]}"
            tid = f"{project_id}:entity:{_hashlib.sha1(tname.encode('utf-8', errors='ignore')).hexdigest()[:12]}"
        async with graph_processor.neo4j_driver.session() as session:
            await session.run(
                """
                MATCH (p:Project {id: $project_id})
                MERGE (s:Entity {canonical_id: $sid})
                ON CREATE SET s.created_at = datetime(), s.project_id = $project_id, s.type = 'Entity', s.id = $sid, s.name = $source_entity
                MERGE (t:Entity {canonical_id: $tid})
                ON CREATE SET t.created_at = datetime(), t.project_id = $project_id, t.type = 'Entity', t.id = $tid, t.name = $target_entity
                MERGE (p)-[:CONTAINS]->(s)
                MERGE (p)-[:CONTAINS]->(t)
                MERGE (s)-[r:RELATIONSHIP {type: $relationship_type}]->(t)
                SET r.source_element_id = $source_element_id,
                    r.created_at = datetime(),
                    r.updated_at = datetime()
                """,
                project_id=project_id,
                sid=sid,
                tid=tid,
                source_entity=source_entity,
                target_entity=target_entity,
                relationship_type=rtype,
                source_element_id=source_element_id
            )
    except Exception as e:
        logger.error(f"Failed to create relationship: {e}")

async def _create_document_node(
    project_id: str,
    document_id: str,
    filename: str,
    element_count: int,
    graph_processor
):
    """Create a document node in Neo4j"""
    try:
        async with graph_processor.neo4j_driver.session() as session:
            await session.run(
                """
                MERGE (p:Project {id: $project_id})
                MERGE (d:Document {id: $document_id, project_id: $project_id})
                MERGE (p)-[:CONTAINS]->(d)
                SET d.filename = $filename,
                    d.element_count = $element_count,
                    d.processing_type = 'structured',
                    d.created_at = datetime(),
                    d.updated_at = datetime()
                """,
                project_id=project_id,
                document_id=document_id,
                filename=filename,
                element_count=element_count
            )
    except Exception as e:
        logger.error(f"Failed to create document node: {e}")

@router.delete("/projects/{project_id}/documents/{filename}", summary="Delete document graph data")
async def delete_document_graph(
    project_id: str,
    filename: str,
    graph_processor=Depends(get_graph_processor)
):
    """Delete graph data for a specific document"""
    try:
        # Delete nodes and relationships where document_id matches the filename
        query = """
        MATCH (n {document_id: $filename})
        DETACH DELETE n
        """
        
        result = graph_processor.neo4j_driver.execute_query(
            query,
            filename=filename,
            database_=graph_processor.database
        )
        
        # Count deleted nodes (this is approximate since DETACH DELETE doesn't return exact count)
        nodes_deleted = len(result.records) if result.records else 0
        
        logger.info(f"Deleted graph data for document {filename} in project {project_id}")
        
        return {
            "message": f"Deleted graph data for document {filename}",
            "nodes_deleted": nodes_deleted,
            "relationships_deleted": "unknown",  # Neo4j DETACH DELETE doesn't provide exact relationship count
            "project_id": project_id,
            "document_id": filename
        }
        
    except Exception as e:
        logger.error(f"Failed to delete graph data for document {filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete document graph data: {str(e)}")

# =====================================================================================
# DISCOVERIES ENDPOINTS - Stage 1: Foundational Fact Extraction
# =====================================================================================

@router.get("/projects/{project_id}/discoveries", response_model=DiscoveryResponse)
async def get_project_discoveries(
    project_id: str,
    category: Optional[str] = Query(None, description="Filter by category (infrastructure, technology, business, security, performance, compliance)"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of discoveries to return"),
    graph_processor = Depends(get_graph_processor)
):
    """
    Get all discoveries (key facts) extracted from documents in a project

    Returns foundational facts that were automatically extracted during document processing.
    These provide the base knowledge layer for agents and users.
    """
    try:
        logger.info(f"DEBUG: Starting get_project_discoveries for project_id={project_id}, category={category}, limit={limit}")

        # Check Neo4j connection
        try:
            async with graph_processor.neo4j_driver.session() as session:
                logger.info("DEBUG: Neo4j session created successfully")

                # Build query with optional category filter
                query = """
                    MATCH (p:Project {id: $project_id})-[:CONTAINS]->(d:Document)-[:CONTAINS_DISCOVERY]->(discovery:Discovery)
                    """

                if category:
                    query += " WHERE discovery.category = $category"

                query += """
                    RETURN discovery.id as id,
                            discovery.text as text,
                            discovery.category as category,
                            discovery.confidence as confidence,
                            discovery.source_document as source_document,
                            discovery.extracted_at as extracted_at,
                            discovery.project_id as project_id
                    ORDER BY discovery.extracted_at DESC
                    LIMIT $limit
                    """

                logger.info(f"DEBUG: Executing main query: {query}")
                result = await session.run(query, project_id=project_id, category=category, limit=limit)
                logger.info("DEBUG: Main query executed successfully")

                discoveries = []
                record_count = 0
                async for record in result:
                    record_count += 1
                    try:
                        # Check for null values that might cause issues and serialize Neo4j objects
                        discovery_data = {
                            "id": record["id"],
                            "text": record["text"],
                            "category": record["category"],
                            "confidence": record["confidence"],
                            "source_document": record["source_document"],
                            "extracted_at": serialize_neo4j_value(record["extracted_at"]),
                            "project_id": record["project_id"]
                        }
                        discoveries.append(discovery_data)
                        logger.debug(f"DEBUG: Processed discovery {record_count}: id={record['id']}")
                    except Exception as record_error:
                        logger.error(f"DEBUG: Error processing record {record_count}: {record_error}")
                        logger.error(f"DEBUG: Record data: {dict(record) if record else 'None'}")
                        raise

                logger.info(f"DEBUG: Processed {record_count} discovery records")

                # Get category breakdown
                category_query = """
                    MATCH (p:Project {id: $project_id})-[:CONTAINS]->(d:Document)-[:CONTAINS_DISCOVERY]->(discovery:Discovery)
                    RETURN discovery.category as category, count(discovery) as count
                    ORDER BY count DESC
                    """

                logger.info("DEBUG: Executing category query")
                category_result = await session.run(category_query, project_id=project_id)
                categories = {}
                category_count = 0
                async for record in category_result:
                    category_count += 1
                    try:
                        categories[record["category"]] = record["count"]
                        logger.debug(f"DEBUG: Category {record['category']}: {record['count']} items")
                    except Exception as cat_error:
                        logger.error(f"DEBUG: Error processing category record {category_count}: {cat_error}")
                        raise

                logger.info(f"DEBUG: Processed {category_count} category records")

                response = DiscoveryResponse(
                    project_id=project_id,
                    discoveries=discoveries,
                    total_count=len(discoveries),
                    categories=categories,
                    timestamp=serialize_neo4j_value(datetime.utcnow())
                )

                logger.info(f"DEBUG: Successfully returning {len(discoveries)} discoveries for project {project_id}")
                return response

        except Exception as neo4j_error:
            logger.error(f"DEBUG: Neo4j operation failed: {neo4j_error}")
            logger.error(f"DEBUG: Neo4j error type: {type(neo4j_error)}")
            raise

    except Exception as e:
        logger.error(f"DEBUG: Failed to get discoveries for project {project_id}: {e}")
        logger.error(f"DEBUG: Error type: {type(e)}")
        logger.error(f"DEBUG: Error traceback: {e.__traceback__}")
        raise HTTPException(status_code=500, detail="Failed to retrieve project discoveries")

@router.get("/projects/{project_id}/discoveries/{discovery_id}")
async def get_discovery_details(
    project_id: str,
    discovery_id: str,
    graph_processor = Depends(get_graph_processor)
):
    """
    Get detailed information about a specific discovery including its relationships
    """
    try:
        async with graph_processor.neo4j_driver.session() as session:
            # Get discovery details
            discovery_query = """
                MATCH (p:Project {id: $project_id})-[:CONTAINS]->(d:Document)-[:CONTAINS_DISCOVERY]->(discovery:Discovery {id: $discovery_id})
                RETURN discovery.id as id,
                       discovery.text as text,
                       discovery.category as category,
                       discovery.confidence as confidence,
                       discovery.source_document as source_document,
                       discovery.extracted_at as extracted_at,
                       d.id as document_id,
                       d.filename as document_filename
                """

            result = await session.run(discovery_query, project_id=project_id, discovery_id=discovery_id)
            record = await result.single()

            if not record:
                raise HTTPException(status_code=404, detail="Discovery not found")

            # Get related entities (if any future relationships are established)
            related_query = """
                MATCH (discovery:Discovery {id: $discovery_id})-[r]-(n)
                WHERE NOT n:Document
                RETURN type(r) as relationship_type, n.id as node_id, n.name as node_name, labels(n) as node_labels
                LIMIT 20
                """

            related_result = await session.run(related_query, discovery_id=discovery_id)
            related_entities = []
            async for rel_record in related_result:
                related_entities.append({
                    "relationship_type": rel_record["relationship_type"],
                    "node_id": rel_record["node_id"],
                    "node_name": rel_record["node_name"],
                    "node_labels": rel_record["node_labels"]
                })

            return {
                "discovery": {
                    "id": record["id"],
                    "text": record["text"],
                    "category": record["category"],
                    "confidence": record["confidence"],
                    "source_document": record["source_document"],
                    "document_id": record["document_id"],
                    "document_filename": record["document_filename"],
                    "extracted_at": serialize_neo4j_value(record["extracted_at"]),
                    "project_id": project_id
                },
                "related_entities": related_entities,
                "timestamp": serialize_neo4j_value(datetime.utcnow())
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get discovery details for {discovery_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve discovery details")

@router.get("/projects/{project_id}/discoveries/search")
async def search_discoveries(
    project_id: str,
    q: str = Query(..., description="Search query for discovery text"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results"),
    graph_processor = Depends(get_graph_processor)
):
    """
    Search discoveries by text content within a project
    """
    try:
        if not q or not q.strip():
            raise HTTPException(status_code=400, detail="Search query cannot be empty")

        async with graph_processor.neo4j_driver.session() as session:
            query = """
                MATCH (p:Project {id: $project_id})-[:CONTAINS]->(d:Document)-[:CONTAINS_DISCOVERY]->(discovery:Discovery)
                WHERE toLower(discovery.text) CONTAINS toLower($query)
                """

            if category:
                query += " AND discovery.category = $category"

            query += """
                RETURN discovery.id as id,
                       discovery.text as text,
                       discovery.category as category,
                       discovery.confidence as confidence,
                       discovery.source_document as source_document,
                       discovery.extracted_at as extracted_at
                ORDER BY discovery.confidence DESC, discovery.extracted_at DESC
                LIMIT $limit
                """

            result = await session.run(query, project_id=project_id, query=q.strip(), category=category, limit=limit)

            discoveries = []
            async for record in result:
                discoveries.append({
                    "id": record["id"],
                    "text": record["text"],
                    "category": record["category"],
                    "confidence": record["confidence"],
                    "source_document": record["source_document"],
                    "extracted_at": serialize_neo4j_value(record["extracted_at"])
                })

            return {
                "project_id": project_id,
                "query": q,
                "category_filter": category,
                "results": discoveries,
                "total_found": len(discoveries),
                "timestamp": serialize_neo4j_value(datetime.utcnow())
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to search discoveries for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to search discoveries")

# =====================================================================================
# INSIGHTS ENDPOINTS - Stage 2: Layered Insights with Traceability
# =====================================================================================

@router.post("/projects/{project_id}/insights", response_model=Dict[str, Any])
async def create_insight(
    project_id: str,
    insight_data: Dict[str, Any],
    graph_processor = Depends(get_graph_processor)
):
    """
    Create and store an insight with full traceability

    This endpoint stores insights generated by agents with links to source facts
    and complete metadata for knowledge evolution tracking.
    """
    try:
        insight_id = insight_data.get("insight_id")
        if not insight_id:
            return {"error": "insight_id is required"}

        async with graph_processor.neo4j_driver.session() as session:
            # Create Insight node
            await session.run(
                """
                MATCH (p:Project {id: $project_id})
                MERGE (insight:Insight {id: $insight_id})
                ON CREATE SET
                    insight.text = $text,
                    insight.category = $category,
                    insight.confidence = $confidence,
                    insight.agent_name = $agent_name,
                    insight.tags = $tags,
                    insight.traceability = $traceability,
                    insight.created_at = datetime(),
                    insight.project_id = $project_id
                ON MATCH SET
                    insight.text = $text,
                    insight.category = $category,
                    insight.confidence = $confidence,
                    insight.agent_name = $agent_name,
                    insight.tags = $tags,
                    insight.traceability = $traceability
                MERGE (p)-[:CONTAINS]->(insight)
                """,
                project_id=project_id,
                insight_id=insight_id,
                text=insight_data.get("text", ""),
                category=insight_data.get("category", "general"),
                confidence=insight_data.get("confidence", 0.8),
                agent_name=insight_data.get("agent_name", "unknown"),
                tags=insight_data.get("tags", []),
                traceability=insight_data.get("traceability", {}),
            )

        return {
            "success": True,
            "insight_id": insight_id,
            "message": "Insight stored successfully",
            "project_id": project_id
        }

    except Exception as e:
        logger.error(f"Failed to create insight for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to create insight")

@router.post("/projects/{project_id}/insights/{insight_id}/link-fact")
async def link_insight_to_fact(
    project_id: str,
    insight_id: str,
    link_data: Dict[str, Any],
    graph_processor = Depends(get_graph_processor)
):
    """
    Link an insight to a source fact for traceability
    """
    try:
        fact_id = link_data.get("fact_id")
        if not fact_id:
            raise HTTPException(status_code=400, detail="fact_id is required")

        async with graph_processor.neo4j_driver.session() as session:
            # Create relationship between insight and fact
            await session.run(
                """
                MATCH (insight:Insight {id: $insight_id})
                MATCH (fact:Discovery {id: $fact_id})
                MERGE (insight)-[r:DERIVED_FROM]->(fact)
                ON CREATE SET r.created_at = datetime()
                """,
                insight_id=insight_id,
                fact_id=fact_id,
            )

        return {
            "success": True,
            "message": f"Linked insight {insight_id} to fact {fact_id}",
            "insight_id": insight_id,
            "fact_id": fact_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to link insight {insight_id} to fact: {e}")
        raise HTTPException(status_code=500, detail="Failed to link insight to fact")

@router.get("/projects/{project_id}/insights")
async def get_project_insights(
    project_id: str,
    category: Optional[str] = Query(None, description="Filter by category"),
    agent_name: Optional[str] = Query(None, description="Filter by agent name"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of insights to return"),
    graph_processor = Depends(get_graph_processor)
):
    """
    Get insights for a project with optional filtering
    """
    try:
        async with graph_processor.neo4j_driver.session() as session:
            query = """
                MATCH (p:Project {id: $project_id})-[:CONTAINS]->(insight:Insight)
                """

            params = {"project_id": project_id, "limit": limit}

            if category:
                query += " WHERE insight.category = $category"
                params["category"] = category

            if agent_name:
                if category:
                    query += " AND insight.agent_name = $agent_name"
                else:
                    query += " WHERE insight.agent_name = $agent_name"
                params["agent_name"] = agent_name

            query += """
                RETURN insight.id as id,
                       insight.text as text,
                       insight.category as category,
                       insight.confidence as confidence,
                       insight.agent_name as agent_name,
                       insight.tags as tags,
                       insight.traceability as traceability,
                       insight.created_at as created_at
                ORDER BY insight.created_at DESC
                LIMIT $limit
                """

            result = await session.run(query, params)

            insights = []
            async for record in result:
                insights.append({
                    "id": record["id"],
                    "text": record["text"],
                    "category": record["category"],
                    "confidence": record["confidence"],
                    "agent_name": record["agent_name"],
                    "tags": record["tags"],
                    "traceability": record["traceability"],
                    "created_at": record["created_at"],
                    "project_id": project_id
                })

            return {
                "insights": insights,
                "total_count": len(insights),
                "project_id": project_id,
                "filters": {
                    "category": category,
                    "agent_name": agent_name
                },
                "timestamp": serialize_neo4j_value(datetime.utcnow())
            }

    except Exception as e:
        logger.error(f"Failed to get insights for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve insights")

@router.get("/projects/{project_id}/insights/{insight_id}")
async def get_insight_details(
    project_id: str,
    insight_id: str,
    graph_processor = Depends(get_graph_processor)
):
    """
    Get detailed information about a specific insight including its source facts
    """
    try:
        async with graph_processor.neo4j_driver.session() as session:
            # Get insight details
            insight_query = """
                MATCH (p:Project {id: $project_id})-[:CONTAINS]->(insight:Insight {id: $insight_id})
                RETURN insight.id as id,
                       insight.text as text,
                       insight.category as category,
                       insight.confidence as confidence,
                       insight.agent_name as agent_name,
                       insight.tags as tags,
                       insight.traceability as traceability,
                       insight.created_at as created_at
                """

            result = await session.run(insight_query, project_id=project_id, insight_id=insight_id)
            record = await result.single()

            if not record:
                raise HTTPException(status_code=404, detail="Insight not found")

            # Get source facts
            facts_query = """
                MATCH (insight:Insight {id: $insight_id})-[r:DERIVED_FROM]->(fact:Discovery)
                RETURN fact.id as id,
                       fact.text as text,
                       fact.category as category,
                       fact.confidence as confidence,
                       fact.source_document as source_document,
                       fact.extracted_at as extracted_at
                ORDER BY fact.extracted_at DESC
                """

            facts_result = await session.run(facts_query, insight_id=insight_id)
            source_facts = []
            async for fact_record in facts_result:
                source_facts.append({
                    "id": fact_record["id"],
                    "text": fact_record["text"],
                    "category": fact_record["category"],
                    "confidence": fact_record["confidence"],
                    "source_document": fact_record["source_document"],
                    "extracted_at": serialize_neo4j_value(fact_record["extracted_at"])
                })

            return {
                "insight": {
                    "id": record["id"],
                    "text": record["text"],
                    "category": record["category"],
                    "confidence": record["confidence"],
                    "agent_name": record["agent_name"],
                    "tags": record["tags"],
                    "traceability": record["traceability"],
                    "created_at": record["created_at"],
                    "project_id": project_id
                },
                "source_facts": source_facts,
                "facts_count": len(source_facts),
                "timestamp": serialize_neo4j_value(datetime.utcnow())
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get insight details for {insight_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve insight details")

# ---------------- Commit Summary Endpoints -----------------
class CommitSummaryCreateRequest(BaseModel):
    proposal_id: str
    project_id: str
    summary: Dict[str, Any]

class CommitSummaryResponse(BaseModel):
    id: int
    proposal_id: str
    project_id: str
    created_at: str
    summary: Dict[str, Any]

class CanonicalEntityIndexEntry(BaseModel):
    slug: str
    name: Optional[str]
    type: Optional[str]
    occurrences: int
    degree_in: int
    degree_out: int
    total_degree: int
    relationship_type_counts: Dict[str, int]
    first_proposal_id: Optional[str]
    last_proposal_id: Optional[str]
    updated_at: Optional[str]

@router.post("/api/graphs/commit-summaries", response_model=CommitSummaryResponse)
async def create_commit_summary(payload: CommitSummaryCreateRequest):
    try:
        from ..pvc_repo.repository import PVCRepository
        repo = PVCRepository()
        rec = repo.add_commit_summary(payload.proposal_id, payload.project_id, payload.summary)
        return CommitSummaryResponse(**rec, summary=payload.summary)
    except Exception as e:
        logger.error(f"Create commit summary failed: {e}")
        raise HTTPException(status_code=500, detail="Commit summary creation failed")

@router.get("/api/graphs/projects/{project_id}/commit-summaries", response_model=List[CommitSummaryResponse])
async def list_commit_summaries(project_id: str, limit: int = Query(50, le=200)):
    try:
        from ..pvc_repo.repository import PVCRepository
        repo = PVCRepository()
        rows = repo.list_commit_summaries(project_id, limit=limit)
        return [CommitSummaryResponse(**r) for r in rows]
    except Exception as e:
        logger.error(f"List commit summaries failed: {e}")
        raise HTTPException(status_code=500, detail="List commit summaries failed")

@router.get("/api/graphs/commit-summaries/{proposal_id}", response_model=CommitSummaryResponse)
async def get_commit_summary(proposal_id: str):
    try:
        from ..pvc_repo.repository import PVCRepository
        repo = PVCRepository()
        rec = repo.get_commit_summary(proposal_id)
        if not rec:
            raise HTTPException(status_code=404, detail="Not found")
        return CommitSummaryResponse(**rec)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get commit summary failed: {e}")
        raise HTTPException(status_code=500, detail="Get commit summary failed")

@router.get("/api/graphs/projects/{project_id}/canonical-entities", response_model=List[CanonicalEntityIndexEntry])
async def list_canonical_entities(project_id: str, limit: int = Query(100, le=500)):
    """List canonical entity index entries ordered by total_degree desc."""
    try:
        from ..pvc_repo.repository import PVCRepository
        repo = PVCRepository()
        rows = repo.list_canonical_entities(project_id, limit=limit)
        return [CanonicalEntityIndexEntry(**r) for r in rows]
    except Exception as e:
        logger.error(f"List canonical entities failed: {e}")
        raise HTTPException(status_code=500, detail="List canonical entities failed")
