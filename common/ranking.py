"""
Ranking helpers for fused search and centrality boosting.

These utilities are pure functions so they can be unit tested without
external dependencies.

Contracts:
- Items are dictionaries with at minimum keys: id (str), score (float), source (str)
- Per-kind results are lists of such items (already ranked best-first)

Functions:
- compute_rrf_fusion(per_kind_results, weights=None, rrf_k=60.0) -> List[Dict]
- apply_centrality_boost(items, degree_map, scale=0.05, normalized=True) -> None (in-place)
"""
from __future__ import annotations

from typing import Dict, List, Optional, Iterable, Any


def compute_rrf_fusion(
    per_kind_results: Iterable[Iterable[Dict[str, Any]]],
    *,
    weights: Optional[Dict[str, float]] = None,
    rrf_k: float = 60.0,
) -> List[Dict[str, Any]]:
    """Fuse multiple ranked lists using Reciprocal Rank Fusion (RRF).

    - per_kind_results: iterable of result lists; each result item should have
      keys: id, name?, text?, score, source.
    - weights: optional map of source -> weight multiplier (>= 0)
    - rrf_k: the RRF constant; larger reduces the impact of rank differences

    Returns a list of fused items, where each item has fields:
      id, name, text, sources: List[{source, rank, score}], fused_score
    """
    fused: Dict[str, Dict[str, Any]] = {}
    wmap = weights or {}
    # Ensure rrf_k positive to avoid div by zero
    k = float(rrf_k) if rrf_k and rrf_k > 0 else 60.0
    for results in per_kind_results:
        if not results:
            continue
        for rank, item in enumerate(results):
            _id = item.get("id")
            if not _id:
                continue
            rec = fused.setdefault(
                _id,
                {
                    "id": _id,
                    "name": item.get("name"),
                    "text": item.get("text"),
                    "sources": [],
                    "fused_score": 0.0,
                },
            )
            rec["sources"].append(
                {
                    "source": item.get("source"),
                    "rank": rank + 1,
                    "score": float(item.get("score", 0) or 0),
                }
            )
            w = float(wmap.get(item.get("source"), 1.0) or 0.0)
            # Clip negative weights to zero
            if w < 0:
                w = 0.0
            rec["fused_score"] += (1.0 / (k + (rank + 1))) * w
    out = list(fused.values())
    out.sort(key=lambda x: x.get("fused_score", 0.0), reverse=True)
    return out


def apply_centrality_boost(
    items: List[Dict[str, Any]],
    degree_map: Dict[str, float],
    *,
    scale: float = 0.05,
    normalized: bool = True,
) -> None:
    """Apply an additive boost to fused scores based on simple degree centrality.

    - items: list of fused items (each must have id and fused_score)
    - degree_map: node id -> degree (non-negative)
    - scale: multiplier applied after optional normalization
    - normalized: when True, divide by max degree to bring into [0,1]

    Mutates each item's fused_score in-place.
    """
    if not items or not degree_map:
        return
    try:
        max_deg = max(float(v or 0.0) for v in degree_map.values())
    except ValueError:
        max_deg = 0.0
    for rec in items:
        rid = rec.get("id")
        if rid is None:
            continue
        raw = float(degree_map.get(str(rid), 0.0) or 0.0)
        base = (raw / max_deg) if (normalized and max_deg > 0) else raw
        boost = float(base) * float(scale or 0.0)
        rec["fused_score"] = float(rec.get("fused_score", 0.0) or 0.0) + boost
