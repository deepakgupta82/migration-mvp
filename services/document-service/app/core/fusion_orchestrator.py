"""Fusion Orchestrator

Consolidates duplicate / overlapping entities & relationships into canonical
forms using:
  - Entity resolution clusters (vector-service)
  - Validated proposals (graph-service PVC repository)
  - Existing entity + triple card vectors (via document-service generation)

Feature Flags (env):
  FUSION_ENABLED=true|false (default false)
  FUSION_COMMIT_MODE=proposal|direct (default proposal)
  FUSION_CANONICAL_VECTOR_UPSERT=true|false (default true)
  FUSION_EXCLUDE_ENTITY_TYPES=CommaSeparatedTypeNames  (optional)

This module does not persist directly to databases; it orchestrates calls to
graph-service and vector-service, returning a structured result for the API.
"""

from __future__ import annotations

import os
import uuid
import logging
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import httpx

logger = logging.getLogger("document-service.fusion")

# ---------------- Data Structures -----------------

@dataclass
class CanonicalEntity:
    id: str
    name: str
    types: List[str]
    properties: Dict[str, Any]
    provenance: List[Dict[str, Any]]
    member_entity_ids: List[str]

@dataclass
class CanonicalRelationship:
    id: str
    type: str
    from_id: str
    to_id: str
    properties: Dict[str, Any]
    provenance: List[Dict[str, Any]]


class FusionOrchestrator:
    def __init__(self):
        self.vector_url = os.getenv("VECTOR_SERVICE_URL", "http://localhost:8005")
        self.graph_url = os.getenv("GRAPH_SERVICE_URL", "http://localhost:8006")
        self.service_token = os.getenv("SERVICE_AUTH_TOKEN", "service-backend-token")
        self.session_timeout = float(os.getenv("FUSION_HTTP_TIMEOUT_SEC", "25"))

    # -------- Public API --------
    async def run_fusion(self, project_id: str, threshold: float, max_cards: int, include_singletons: bool = True) -> Dict[str, Any]:
        if os.getenv("FUSION_ENABLED", "false").lower() not in {"1", "true", "yes"}:
            return {"status": "disabled", "project_id": project_id}

        fusion_run_id = str(uuid.uuid4())
        start = datetime.utcnow()
        logger.info(f"Starting fusion run {fusion_run_id} for project={project_id} threshold={threshold}")

        # 1. Fetch clusters from vector-service
        clusters = await self._fetch_clusters(project_id, threshold, max_cards)
        if clusters.get("status") in {"no_entity_cards", "empty_after_filter"}:
            return {"status": "no_clusters", "project_id": project_id, "fusion_run_id": fusion_run_id, "clusters": []}

        cluster_list = clusters.get("clusters", [])

        # 2. Fetch validated proposals (simplified: fetch all proposals and filter if field present)
        proposals = await self._fetch_proposals(project_id)
        entity_index, relationship_list, proposal_map = self._index_proposals(proposals)
        if not entity_index:
            return {"status": "no_entities_in_proposals", "project_id": project_id, "fusion_run_id": fusion_run_id}

        # 3. Resolve clusters to canonical entities
        excluded_types = {t.strip() for t in os.getenv("FUSION_EXCLUDE_ENTITY_TYPES", "").split(',') if t.strip()}
        canonical_entities: List[CanonicalEntity] = []
        entity_mapping: Dict[str, str] = {}  # original_entity_id -> canonical_id
        unmatched_clusters = 0

        for c in cluster_list:
            members = c.get("members", [])
            # Extract candidate entity IDs by fuzzy matching name presence in entity content (simple heuristic)
            matched_entity_ids = self._match_entities_from_cluster(members, entity_index)
            if not matched_entity_ids:
                unmatched_clusters += 1
                continue
            # Filter by excluded types
            filtered_ids = [eid for eid in matched_entity_ids if not (entity_index[eid].get("type") in excluded_types)]
            if not filtered_ids:
                unmatched_clusters += 1
                continue
            # Build canonical entity
            canonical_id = str(uuid.uuid4())
            canonical_entity = self._build_canonical_entity(canonical_id, filtered_ids, entity_index)
            canonical_entities.append(canonical_entity)
            for eid in filtered_ids:
                entity_mapping[eid] = canonical_id

        # Optionally include singleton entities not in any cluster
        if include_singletons:
            for eid, e in entity_index.items():
                if eid not in entity_mapping:
                    canonical_id = str(uuid.uuid4())
                    ce = CanonicalEntity(
                        id=canonical_id,
                        name=e.get("name") or e.get("label") or eid,
                        types=[e.get("type") or "Unknown"],
                        properties=e.get("properties", {}).copy(),
                        provenance=[{"source_entity_id": eid, "proposal_id": e.get("proposal_id")}],
                        member_entity_ids=[eid],
                    )
                    canonical_entities.append(ce)
                    entity_mapping[eid] = canonical_id

        # 4. Remap relationships
        canonical_relationships, rel_mapping, dropped_relationships = self._remap_relationships(relationship_list, entity_mapping)

        # 5. Deduplicate relationships
        canonical_relationships = self._dedupe_relationships(canonical_relationships)

        # 6. Build stats
        stats = self._build_stats(
            clusters=cluster_list,
            canonical_entities=canonical_entities,
            original_entity_count=len(entity_index),
            original_relationship_count=len(relationship_list),
            dropped_relationships=dropped_relationships,
            unmatched_clusters=unmatched_clusters,
        )

        # 7. Optional persistence (proposal vs direct)
        persistence = await self._persist_results(project_id, canonical_entities, canonical_relationships, entity_mapping, rel_mapping, stats)

        # 8. Optional vector upsert for canonical entity cards
        vector_upsert = None
        if os.getenv("FUSION_CANONICAL_VECTOR_UPSERT", "true").lower() in {"1", "true", "yes"}:
            try:
                vector_upsert = await self._upsert_canonical_vectors(project_id, canonical_entities)
            except Exception as e:
                logger.warning(f"Vector upsert failed: {e}")

        duration = (datetime.utcnow() - start).total_seconds()
        logger.info(f"Fusion run completed in {duration:.2f}s entities={len(canonical_entities)} rels={len(canonical_relationships)}")

        return {
            "status": "success",
            "fusion_run_id": fusion_run_id,
            "project_id": project_id,
            "canonical_entities": [ce.__dict__ for ce in canonical_entities[:100]],  # limit preview
            "canonical_relationships": [cr.__dict__ for cr in canonical_relationships[:200]],
            "entity_mapping_preview": dict(list(entity_mapping.items())[:50]),
            "relationship_mapping_preview": dict(list(rel_mapping.items())[:50]),
            "stats": stats,
            "persistence": persistence,
            "vector_upsert": vector_upsert,
            "duration_seconds": duration,
        }

    # -------- Internal helpers --------
    async def _fetch_clusters(self, project_id: str, threshold: float, max_cards: int) -> Dict[str, Any]:
        url = f"{self.vector_url}/projects/{project_id}/entity-resolution/cluster"
        async with httpx.AsyncClient(timeout=self.session_timeout) as client:
            r = await client.post(url, json={"similarity_threshold": threshold, "max_cards": max_cards}, headers=self._auth_headers())
            if r.status_code == 403:
                logger.warning("Entity resolution endpoint disabled upstream; returning empty clusters")
                return {"clusters": [], "status": "disabled"}
            r.raise_for_status()
            return r.json()

    async def _fetch_proposals(self, project_id: str) -> List[Dict[str, Any]]:
        # Simplified assumption: graph-service exposes /api/graphs/projects/{project_id}/proposals
        url = f"{self.graph_url}/api/graphs/projects/{project_id}/proposals"
        try:
            async with httpx.AsyncClient(timeout=self.session_timeout) as client:
                r = await client.get(url, headers=self._auth_headers())
                if r.status_code >= 400:
                    logger.warning(f"Failed to fetch proposals: {r.status_code}")
                    return []
                data = r.json()
                if isinstance(data, dict) and "proposals" in data:
                    return data["proposals"]
                if isinstance(data, list):
                    return data
                return []
        except Exception as e:
            logger.warning(f"Proposal fetch error: {e}")
            return []

    def _index_proposals(self, proposals: List[Dict[str, Any]]) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
        entity_index: Dict[str, Dict[str, Any]] = {}
        relationships: List[Dict[str, Any]] = []
        proposal_map: Dict[str, Dict[str, Any]] = {}
        for p in proposals:
            pid = p.get("id") or p.get("proposal_id") or str(uuid.uuid4())
            proposal_map[pid] = p
            # Consider only validated proposals if status present
            status = p.get("status")
            if status and status not in {"validated", "approved", "committed"}:
                continue
            for e in p.get("entities", []) or []:
                eid = e.get("id") or e.get("entity_id") or str(uuid.uuid4())
                entity_index[eid] = {**e, "proposal_id": pid}
            for r in p.get("relationships", []) or []:
                rid = r.get("id") or r.get("relationship_id") or str(uuid.uuid4())
                relationships.append({**r, "proposal_id": pid, "internal_id": rid})
        return entity_index, relationships, proposal_map

    def _match_entities_from_cluster(self, cluster_members: List[Dict[str, Any]], entity_index: Dict[str, Dict[str, Any]]) -> List[str]:
        # Very naive fuzzy matching: check if entity name appears in any member preview
        previews = "\n".join(m.get("content_preview", "").lower() for m in cluster_members)
        matched = []
        for eid, e in entity_index.items():
            name = (e.get("name") or e.get("label") or "").lower().strip()
            if name and name in previews:
                matched.append(eid)
        return matched

    def _build_canonical_entity(self, canonical_id: str, member_ids: List[str], entity_index: Dict[str, Dict[str, Any]]) -> CanonicalEntity:
        # Choose representative with most properties; tie by earliest proposal_id lexical
        best_id = member_ids[0]
        best_score = -1
        for mid in member_ids:
            props = entity_index[mid].get("properties", {}) or {}
            score = len([k for k, v in props.items() if v])
            if score > best_score or (score == best_score and entity_index[mid].get("proposal_id", "zzz") < entity_index[best_id].get("proposal_id", "zzz")):
                best_score = score
                best_id = mid
        rep = entity_index[best_id]
        name = rep.get("name") or rep.get("label") or best_id
        # Merge types and properties
        types = []
        for mid in member_ids:
            t = entity_index[mid].get("type") or entity_index[mid].get("entity_type")
            if t and t not in types:
                types.append(t)
        merged_props: Dict[str, Any] = {}
        for mid in member_ids:
            props = entity_index[mid].get("properties", {}) or {}
            for k, v in props.items():
                if v and (k not in merged_props or merged_props[k] in (None, "")):
                    merged_props[k] = v
        provenance = [{"source_entity_id": mid, "proposal_id": entity_index[mid].get("proposal_id")} for mid in member_ids]
        return CanonicalEntity(
            id=canonical_id,
            name=name,
            types=types or [rep.get("type") or "Unknown"],
            properties=merged_props,
            provenance=provenance,
            member_entity_ids=member_ids,
        )

    def _remap_relationships(self, relationships: List[Dict[str, Any]], mapping: Dict[str, str]) -> Tuple[List[CanonicalRelationship], Dict[str, str], int]:
        out: List[CanonicalRelationship] = []
        rel_mapping: Dict[str, str] = {}
        dropped = 0
        for r in relationships:
            src = r.get("from") or r.get("from_id") or r.get("source_entity_id")
            dst = r.get("to") or r.get("to_id") or r.get("target_entity_id")
            if not src or not dst:
                dropped += 1
                continue
            if src not in mapping or dst not in mapping:
                dropped += 1
                continue
            can_src = mapping[src]
            can_dst = mapping[dst]
            rel_type = r.get("type") or r.get("relationship_type") or "RELATED".upper()
            properties = r.get("properties", {}) or {}
            rid = str(uuid.uuid4())
            out.append(
                CanonicalRelationship(
                    id=rid,
                    type=rel_type,
                    from_id=can_src,
                    to_id=can_dst,
                    properties=properties,
                    provenance=[{"source_relationship_id": r.get("internal_id"), "proposal_id": r.get("proposal_id")}],
                )
            )
            if r.get("internal_id"):
                rel_mapping[r["internal_id"]] = rid
        return out, rel_mapping, dropped

    def _dedupe_relationships(self, rels: List[CanonicalRelationship]) -> List[CanonicalRelationship]:
        deduped: Dict[str, CanonicalRelationship] = {}
        for r in rels:
            key = f"{r.type}|{r.from_id}|{r.to_id}|{sorted(r.properties.items())}"
            if key not in deduped:
                deduped[key] = r
            else:
                # merge provenance
                deduped[key].provenance.extend(r.provenance)
        return list(deduped.values())

    def _build_stats(self, *, clusters, canonical_entities, original_entity_count, original_relationship_count, dropped_relationships, unmatched_clusters) -> Dict[str, Any]:
        after_entities = len(canonical_entities)
        dedupe_ratio = (original_entity_count - after_entities) / original_entity_count if original_entity_count else 0.0
        return {
            "entity_before": original_entity_count,
            "entity_after": after_entities,
            "dedupe_ratio": dedupe_ratio,
            "relationship_before": original_relationship_count,
            "dropped_relationships": dropped_relationships,
            "clusters": len(clusters),
            "unmatched_clusters": unmatched_clusters,
            "avg_cluster_size": (sum(c.get("size", 0) for c in clusters) / len(clusters)) if clusters else 0.0,
        }

    async def _persist_results(self, project_id: str, entities: List[CanonicalEntity], relationships: List[CanonicalRelationship], entity_mapping: Dict[str, str], rel_mapping: Dict[str, str], stats: Dict[str, Any]) -> Dict[str, Any]:
        mode = os.getenv("FUSION_COMMIT_MODE", "proposal").lower()
        payload = {
            "project_id": project_id,
            "canonical_entities": [e.__dict__ for e in entities],
            "canonical_relationships": [r.__dict__ for r in relationships],
            "entity_mapping": entity_mapping,
            "relationship_mapping": rel_mapping,
            "stats": stats,
        }
        # Proposal persistence attempt
        if mode == "proposal":
            url = f"{self.graph_url}/api/graphs/projects/{project_id}/fusion/proposals"
        else:
            url = f"{self.graph_url}/api/graphs/projects/{project_id}/fusion/commit"
        try:
            async with httpx.AsyncClient(timeout=self.session_timeout) as client:
                r = await client.post(url, json=payload, headers=self._auth_headers())
                if r.status_code >= 400:
                    logger.warning(f"Fusion persistence request failed: {r.status_code}")
                    return {"status": "persistence_failed", "mode": mode, "code": r.status_code}
                return {"status": "ok", "mode": mode}
        except Exception as e:
            logger.warning(f"Persistence error: {e}")
            return {"status": "persistence_error", "mode": mode, "error": str(e)}

    async def _upsert_canonical_vectors(self, project_id: str, entities: List[CanonicalEntity]):
        if not entities:
            return {"status": "no_entities"}
        url = f"{self.vector_url}/projects/{project_id}/collections/entity_cards/documents/sync"
        docs = []
        for i, e in enumerate(entities):
            # Build canonical card text
            provenance_lines = [f"- {p['source_entity_id']} (proposal {p['proposal_id']})" for p in e.provenance][:15]
            text = f"Canonical Entity: {e.name}\nTypes: {', '.join(e.types)}\nProperties:\n" + "\n".join(
                f"  {k}: {v}" for k, v in sorted(e.properties.items())
            ) + "\nProvenance:\n" + "\n".join(provenance_lines)
            docs.append({
                "content": text,
                "filename": f"canonical_entity_{e.id}.txt",
                "source": "entity_cards",  # per-kind logic will ensure correct filtering
                "chunk_index": i,
            })
        async with httpx.AsyncClient(timeout=self.session_timeout) as client:
            r = await client.post(url, json={"documents": docs}, headers=self._auth_headers())
            if r.status_code >= 400:
                return {"status": "failed", "code": r.status_code}
            return {"status": "ok", "added": len(docs)}

    def _auth_headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.service_token}"}


# Singleton accessor
_FUSION_ORCHESTRATOR_SINGLETON: Optional[FusionOrchestrator] = None

def get_fusion_orchestrator() -> FusionOrchestrator:
    global _FUSION_ORCHESTRATOR_SINGLETON
    if _FUSION_ORCHESTRATOR_SINGLETON is None:
        _FUSION_ORCHESTRATOR_SINGLETON = FusionOrchestrator()
    return _FUSION_ORCHESTRATOR_SINGLETON
