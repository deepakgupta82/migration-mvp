"""Entity Resolution / Clustering utilities.

This module groups semantically similar entity card texts (already embedded
as generic DocumentChunk objects with source=="entity_cards") into clusters
to support canonical entity fusion in downstream graph + RAG workflows.

Design goals:
 - Pure async API using existing VectorProcessor for model + Weaviate access
 - Greedy similarity clustering (O(n^2) worst case, fine for few thousand)
 - Deterministic canonical selection (longest content then lexicographic)
 - No schema changes required (operates on existing collection)
 - Returns rich stats for governance / analytics

If future scale requires, replace with incremental / ANN pre-clustering.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import List, Dict, Any
import numpy as np  # type: ignore
from weaviate.classes.query import Filter  # type: ignore


@dataclass
class EntityCard:
    idx: int
    content: str
    filename: str | None
    chunk_index: int | None


async def _embed_texts(model, texts: List[str]) -> np.ndarray:
    """Run synchronous encode inside executor, return numpy matrix."""
    loop = asyncio.get_running_loop()
    embeddings = await loop.run_in_executor(None, lambda: model.encode(texts, convert_to_tensor=False))
    # Ensure ndarray shape (n, d)
    if not isinstance(embeddings, np.ndarray):  # sentence-transformers may return list
        embeddings = np.asarray(embeddings)
    return embeddings.astype("float32")


def _cosine_similarity_matrix(vecs: np.ndarray) -> np.ndarray:
    """Compute full cosine similarity matrix for normalized vectors."""
    # Normalize
    norms = np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-12
    v = vecs / norms
    return (v @ v.T).clip(-1.0, 1.0)


def _greedy_cluster(sim_matrix: np.ndarray, threshold: float) -> List[List[int]]:
    """Simple greedy clustering: pick first unassigned point, group all above threshold.

    This produces stable, order-dependent clusters but is adequate for
    governance preview + canonicalization bootstrap. Deterministic given input order.
    """
    n = sim_matrix.shape[0]
    assigned = np.zeros(n, dtype=bool)
    clusters: List[List[int]] = []
    for i in range(n):
        if assigned[i]:
            continue
        # Members whose similarity with seed >= threshold
        sims = sim_matrix[i]
        members = np.where(sims >= threshold)[0].tolist()
        # Mark members assigned
        for m in members:
            assigned[m] = True
        clusters.append(members)
    return clusters


def _canonical_for_cluster(cluster_indices: List[int], cards: List[EntityCard]) -> int:
    """Choose canonical representative: longest content (len stripped), tie -> lowest content lexicographically, tie -> lowest original idx."""
    best = None
    best_key = None
    for idx in cluster_indices:
        content = cards[idx].content.strip()
        key = (len(content), content.lower(), -cards[idx].idx * -1)  # length desc via later compare? Simpler: use minus? We'll just store negative length separately
        # Actually simpler: store ( -length, content.lower(), original index ) and pick min
    # Re-implement cleanly
    best_idx = cluster_indices[0]
    best_tuple = (-len(cards[best_idx].content.strip()), cards[best_idx].content.strip().lower(), cards[best_idx].idx)
    for idx in cluster_indices[1:]:
        t = (-len(cards[idx].content.strip()), cards[idx].content.strip().lower(), cards[idx].idx)
        if t < best_tuple:
            best_tuple = t
            best_idx = idx
    return best_idx


async def cluster_entity_cards(
    processor, project_id: str, similarity_threshold: float = 0.82, max_cards: int = 5000
) -> Dict[str, Any]:
    """Fetch entity card chunks for a project and cluster them by semantic similarity.

    Parameters
    ----------
    processor : VectorProcessor
        Existing processor instance (provides Weaviate client + embedding model).
    project_id : str
        Project identifier.
    similarity_threshold : float
        Cosine similarity threshold to join a cluster (default 0.82).
    max_cards : int
        Safety cap to avoid O(n^2) blow-up.
    """
    if similarity_threshold <= 0 or similarity_threshold > 1:
        raise ValueError("similarity_threshold must be in (0,1].")

    col = processor.wclient.collections.get("DocumentChunk")
    project_filter = Filter.by_property("project_id").equal(project_id)
    kind_filter = Filter.by_property("source").equal("entity_cards")
    combined = project_filter & kind_filter

    # Fetch objects (limit large but bounded)
    # Weaviate v4 fetch_objects returns objects list
    res = col.query.fetch_objects(limit=max_cards, filters=combined, return_properties=[
        "content", "filename", "chunk_index", "project_id", "source"
    ])
    objects = res.objects or []
    if not objects:
        return {
            "project_id": project_id,
            "clusters": [],
            "stats": {"entity_card_count": 0, "cluster_count": 0, "duplicates_removed": 0},
            "similarity_threshold": similarity_threshold,
            "status": "no_entity_cards"
        }

    cards: List[EntityCard] = []
    for i, obj in enumerate(objects):
        props = obj.properties or {}
        content = (props.get("content") or "").strip()
        if not content:
            continue
        cards.append(EntityCard(idx=i, content=content, filename=props.get("filename"), chunk_index=props.get("chunk_index")))

    if not cards:
        return {
            "project_id": project_id,
            "clusters": [],
            "stats": {"entity_card_count": 0, "cluster_count": 0, "duplicates_removed": 0},
            "similarity_threshold": similarity_threshold,
            "status": "empty_after_filter"
        }

    if len(cards) >= max_cards:
        # Soft warn (truncation)
        truncated = True
    else:
        truncated = False

    # Embed
    model = await processor._get_embedding_model_async()
    embeddings = await _embed_texts(model, [c.content for c in cards])

    # Compute similarity matrix
    sim_matrix = _cosine_similarity_matrix(embeddings)

    # Cluster
    clusters_indices = _greedy_cluster(sim_matrix, similarity_threshold)

    # Build response clusters
    response_clusters = []
    for cid, member_idxs in enumerate(clusters_indices):
        canonical_internal = _canonical_for_cluster(member_idxs, cards)
        canonical_card = cards[canonical_internal]
        members = []
        for mi in member_idxs:
            c = cards[mi]
            members.append({
                "index": mi,
                "filename": c.filename,
                "chunk_index": c.chunk_index,
                "content_preview": c.content[:160]
            })
        response_clusters.append({
            "cluster_id": cid,
            "canonical_index": canonical_internal,
            "canonical_content_preview": canonical_card.content[:240],
            "size": len(member_idxs),
            "members": members
        })

    cluster_count = len(response_clusters)
    duplicates_removed = len(cards) - cluster_count
    avg_cluster_size = float(len(cards)) / cluster_count if cluster_count else 0.0

    return {
        "project_id": project_id,
        "clusters": response_clusters,
        "stats": {
            "entity_card_count": len(cards),
            "cluster_count": cluster_count,
            "duplicates_removed": duplicates_removed,
            "avg_cluster_size": avg_cluster_size,
            "truncated": truncated,
        },
        "similarity_threshold": similarity_threshold,
        "status": "success"
    }
