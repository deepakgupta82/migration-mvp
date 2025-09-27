"""Evidence normalization & deduplication utilities.

Purpose:
  Provide lightweight, deterministic hashing of evidence snippets so that
  duplicate or near-duplicate evidences (often produced when multiple
  chunkers overlap or the same sentence appears in entity + fact contexts)
  can be collapsed before summarization. This reduces prompt token usage
  and amplifies weighting for genuinely corroborated facts.

Design:
  - normalize_text(): strips noise, collapses whitespace, lowercases.
  - evidence_hash(): sha1 of normalized text (fast, good enough; not for security).
  - dedupe_evidences(): accepts list of CardEvidence-like dicts with keys
        {"content", "source_id"?, "filename"?, "weight"?}
     Returns a tuple (deduped_list, groups_meta) where:
        deduped_list = list of merged evidence dicts (weights summed, sources aggregated)
        groups_meta = list of group descriptors useful for stats/debug.

Future extensions:
  - Fuzzy similarity (Levenshtein/Jaccard) grouping for near duplicates.
  - Min-hash / simhash for large scale corpora.

Safe to import anywhere (no heavy deps). 100% pure Python.
"""
from __future__ import annotations

from typing import List, Dict, Tuple, Any
import hashlib
import re

_ws_re = re.compile(r"\s+")
_punct_re = re.compile(r"[\u200b\ufeff]")  # zero-width & BOM chars


def normalize_text(text: str) -> str:
    if not text:
        return ""
    t = text.strip()
    # Remove zero-width punctuation
    t = _punct_re.sub("", t)
    # Collapse whitespace
    t = _ws_re.sub(" ", t)
    # Lowercase
    t = t.lower()
    return t


def evidence_hash(text: str) -> str:
    norm = normalize_text(text)
    # Short sha1 (first 16 hex chars) sufficient for grouping
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:16]


def dedupe_evidences(evidences: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Group identical evidence snippets by normalized hash.

    Each output evidence contains aggregated 'weight' (sum) and a
    'sources' array capturing distinct (source_id, filename) combos.
    """
    groups: Dict[str, Dict[str, Any]] = {}
    groups_meta: List[Dict[str, Any]] = []
    for ev in evidences:
        content = (ev.get("content") or "")[:1000]
        h = evidence_hash(content)
        g = groups.get(h)
        if not g:
            g = {
                "hash": h,
                "content": content,
                "weight": float(ev.get("weight") or 1.0),
                "source_id": ev.get("source_id"),  # primary (first)
                "filename": ev.get("filename"),
                "sources": set(),
                "count": 0,
            }
            groups[h] = g
        # Aggregate
        g["weight"] += float(ev.get("weight") or 1.0) if g["count"] > 0 else 0.0  # already seeded
        g["count"] += 1
        sid = (ev.get("source_id"), ev.get("filename"))
        g["sources"].add(sid)
    deduped: List[Dict[str, Any]] = []
    for h, g in groups.items():
        deduped.append({
            "content": g["content"],
            "source_id": g.get("source_id"),
            "filename": g.get("filename"),
            "weight": round(g["weight"], 4),
            "hash": h,
            "dup_count": g["count"],
            "unique_sources": len(g["sources"]),
        })
        groups_meta.append({
            "hash": h,
            "dup_count": g["count"],
            "unique_sources": len(g["sources"]),
        })
    # Sort stable by weight desc then content length asc
    deduped.sort(key=lambda x: (-x["weight"], len(x["content"])) )
    groups_meta.sort(key=lambda x: -x["dup_count"])
    return deduped, groups_meta

__all__ = [
    "normalize_text",
    "evidence_hash",
    "dedupe_evidences",
]
