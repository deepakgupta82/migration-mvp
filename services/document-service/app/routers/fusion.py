"""Fusion API Router

Runs the fusion orchestrator to consolidate entities & relationships.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import os
import uuid
import time
import logging

from ..core.fusion_orchestrator import get_fusion_orchestrator

logger = logging.getLogger("document-service.router.fusion")

router = APIRouter(prefix="/fusion", tags=["fusion"])


class FusionRunRequest(BaseModel):
    similarity_threshold: float = Field(0.82, ge=0.5, le=0.99)
    max_cards: int = Field(3000, ge=50, le=20000)
    include_singletons: bool = True


class FusionRunResponse(BaseModel):
    status: str
    fusion_run_id: Optional[str] = None
    project_id: Optional[str] = None
    stats: Optional[Dict[str, Any]] = None
    persistence: Optional[Dict[str, Any]] = None
    vector_upsert: Optional[Dict[str, Any]] = None
    duration_seconds: Optional[float] = None
    # Previews
    canonical_entities: Optional[list] = None
    canonical_relationships: Optional[list] = None
    entity_mapping_preview: Optional[Dict[str, str]] = None
    relationship_mapping_preview: Optional[Dict[str, str]] = None
    canonical_triple_cards: Optional[list] = None


class IncrementalFusionRequest(BaseModel):
    """Request model for incremental fusion.

    Allows caller to request recomputation limited to specific clusters or entity IDs.
    If both provided, intersection is applied. Falls back to full run if neither provided.
    """
    similarity_threshold: Optional[float] = Field(None, ge=0.5, le=0.99)
    max_cards: Optional[int] = Field(None, ge=50, le=20000)
    include_singletons: Optional[bool] = None
    cluster_ids: Optional[list[str]] = Field(None, description="Limit recomputation to these cluster IDs")
    entity_ids: Optional[list[str]] = Field(None, description="Limit recomputation to these original entity IDs")

class IncrementalFusionResponse(FusionRunResponse):
    incremental: bool = True
    filtered_clusters: Optional[int] = None
    original_clusters: Optional[int] = None


@router.post("/projects/{project_id}/run", response_model=FusionRunResponse)
async def run_fusion(project_id: str, request: FusionRunRequest):
    if os.getenv("FUSION_ENABLED", "false").lower() not in {"1", "true", "yes"}:
        raise HTTPException(status_code=403, detail="Fusion feature disabled. Set FUSION_ENABLED=true to enable.")
    try:
        orchestrator = get_fusion_orchestrator()
        result = await orchestrator.run_fusion(
            project_id=project_id,
            threshold=request.similarity_threshold,
            max_cards=request.max_cards,
            include_singletons=request.include_singletons,
        )
        return FusionRunResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fusion run failed for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Fusion run failed: {str(e)}")


@router.post("/projects/{project_id}/run-incremental", response_model=IncrementalFusionResponse, summary="Run incremental fusion for subset of clusters/entities")
async def run_incremental_fusion(project_id: str, request: IncrementalFusionRequest):
    start_time = time.time()
    if os.getenv("FUSION_ENABLED", "false").lower() not in {"1", "true", "yes"}:
        raise HTTPException(status_code=403, detail="Fusion feature disabled. Set FUSION_ENABLED=true to enable.")
    try:
        orchestrator = get_fusion_orchestrator()
        # Use base threshold/max_cards or overrides
        threshold = request.similarity_threshold or 0.82
        max_cards = request.max_cards or 3000
        include_singletons = True if request.include_singletons is None else request.include_singletons

        # First run full cluster fetch but we'll filter prior to building canonical entities
        clusters = await orchestrator._fetch_clusters(project_id, threshold, max_cards)  # type: ignore (internal use)
        cluster_list = clusters.get("clusters", []) if isinstance(clusters, dict) else []
        original_clusters = len(cluster_list)

        if request.cluster_ids:
            cluster_list = [c for c in cluster_list if str(c.get("cluster_id") or c.get("id")) in set(request.cluster_ids or [])]
        # If entity_ids provided, retain clusters having any of those entity ids
        if request.entity_ids:
            ent_set = set(request.entity_ids)
            filtered = []
            for c in cluster_list:
                members = c.get("members", []) or []
                for m in members:
                    mid = m.get("entity_id") or m.get("source_entity_id") or m.get("id")
                    if mid in ent_set:
                        filtered.append(c)
                        break
            cluster_list = filtered

        # Monkey patch a shallow orchestrator call by temporarily replacing _fetch_clusters result
        # We replicate key logic from run_fusion but inject filtered clusters.
        if not cluster_list:
            return IncrementalFusionResponse(status="no_matching_clusters", project_id=project_id, original_clusters=original_clusters, filtered_clusters=0)

        # Build mapping original_entity_id -> cluster_id
        entity_cluster_map: Dict[str, str] = {}
        for idx, c in enumerate(cluster_list):
            cid = c.get("cluster_id") or c.get("id") or f"cluster_{idx}"
            for m in c.get("members", []) or []:
                src_eid = m.get("entity_id") or m.get("source_entity_id") or m.get("id")
                if src_eid:
                    entity_cluster_map[src_eid] = cid

        proposals = await orchestrator._fetch_proposals(project_id)  # type: ignore
        entity_index, relationship_list, proposal_map = orchestrator._index_proposals(proposals)  # type: ignore
        if not entity_index:
            return IncrementalFusionResponse(status="no_entities_in_proposals", project_id=project_id)

        excluded_types = {t.strip() for t in os.getenv("FUSION_EXCLUDE_ENTITY_TYPES", "").split(',') if t.strip()}
        canonical_entities = []
        entity_mapping: Dict[str, str] = {}
        unmatched_clusters = 0

        for c in cluster_list:
            members = c.get("members", [])
            matched_entity_ids = orchestrator._match_entities_from_cluster(members, entity_index)  # type: ignore
            if not matched_entity_ids:
                unmatched_clusters += 1
                continue
            filtered_ids = [eid for eid in matched_entity_ids if not (entity_index[eid].get("type") in excluded_types)]
            if not filtered_ids:
                unmatched_clusters += 1
                continue
            canonical_id = str(uuid.uuid4())
            ce = orchestrator._build_canonical_entity(canonical_id, filtered_ids, entity_index)  # type: ignore
            canonical_entities.append(ce)
            for eid in filtered_ids:
                entity_mapping[eid] = canonical_id

        if include_singletons:
            for eid, e in entity_index.items():
                if eid not in entity_mapping:
                    canonical_id = str(uuid.uuid4())
                    from ..core.fusion_orchestrator import CanonicalEntity as _CE
                    ce = _CE(
                        id=canonical_id,
                        name=e.get("name") or e.get("label") or eid,
                        types=[e.get("type") or "Unknown"],
                        properties=e.get("properties", {}).copy(),
                        provenance=[{"source_entity_id": eid, "proposal_id": e.get("proposal_id")}],
                        member_entity_ids=[eid],
                    )
                    canonical_entities.append(ce)
                    entity_mapping[eid] = canonical_id

        canonical_relationships, rel_mapping, dropped_relationships = orchestrator._remap_relationships(relationship_list, entity_mapping)  # type: ignore
        canonical_relationships = orchestrator._dedupe_relationships(canonical_relationships)  # type: ignore

        # Provenance enrichment (reuse logic)
        for ce in canonical_entities:
            try:
                cluster_ids = sorted({entity_cluster_map.get(src_id, "singleton") for src_id in ce.member_entity_ids})
                ce.properties.setdefault("source_entity_ids", ce.member_entity_ids)
                ce.properties.setdefault("cluster_ids", cluster_ids)
                ce.properties.setdefault("provenance", ce.provenance[:200])
            except Exception:
                pass
        for cr in canonical_relationships:
            try:
                src_rel_ids = [p.get("source_relationship_id") for p in cr.provenance if p.get("source_relationship_id")]
                cr.properties.setdefault("source_relationship_ids", src_rel_ids)
                cr.properties.setdefault("provenance", cr.provenance[:200])
            except Exception:
                pass

        stats = orchestrator._build_stats(  # type: ignore
            clusters=cluster_list,
            canonical_entities=canonical_entities,
            original_entity_count=len(entity_index),
            original_relationship_count=len(relationship_list),
            dropped_relationships=dropped_relationships,
            unmatched_clusters=unmatched_clusters,
        )

        triple_cards = orchestrator._build_canonical_triple_cards(canonical_relationships, {ce.id: ce for ce in canonical_entities})  # type: ignore

        persistence = await orchestrator._persist_results(project_id, canonical_entities, canonical_relationships, entity_mapping, rel_mapping, stats)  # type: ignore

        vector_upsert = None
        if os.getenv("FUSION_CANONICAL_VECTOR_UPSERT", "true").lower() in {"1", "true", "yes"}:
            try:
                vector_upsert = await orchestrator._upsert_canonical_vectors(project_id, canonical_entities)  # type: ignore
                triple_upsert = await orchestrator._upsert_canonical_triple_vectors(project_id, triple_cards)  # type: ignore
                if vector_upsert:
                    vector_upsert["triple_upsert"] = triple_upsert
            except Exception as e:
                logger.warning(f"Vector upsert (incremental) failed: {e}")

        # Duration not tracked separately for incremental to keep simple
        resp = IncrementalFusionResponse(
            status="success",
            project_id=project_id,
            canonical_entities=[ce.__dict__ for ce in canonical_entities[:100]],
            canonical_relationships=[cr.__dict__ for cr in canonical_relationships[:200]],
            canonical_triple_cards=[tc.__dict__ for tc in triple_cards[:300]],
            entity_mapping_preview=dict(list(entity_mapping.items())[:50]),
            relationship_mapping_preview=dict(list(rel_mapping.items())[:50]),
            stats=stats,
            persistence=persistence,
            vector_upsert=vector_upsert,
            original_clusters=original_clusters,
            filtered_clusters=len(cluster_list),
        )
        duration = time.time() - start_time
        logger.info(f"incremental_fusion_completed project={project_id} clusters_filtered={len(cluster_list)} duration_sec={duration:.3f}")
        return resp
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Incremental fusion failed for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Incremental fusion failed: {str(e)}")
