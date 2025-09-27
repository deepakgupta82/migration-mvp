"""Fusion & RAG Analytics Endpoints

Aggregates metrics previously ingested via /ingest events emitted by
vector-service (fusion search) and llm-service (advanced RAG).

Expected ingest record shapes (subset):
  {"source":"vector-service","project_id":"p1","metrics":{"fusion": {
        "candidate_counts": {"raw_chunks": 30, ...},
        "fused_candidates": 52,
        "returned": 12,
        "rrf_k": 60,
        "dedupe_ratio": 0.34,
        "latency_ms": 123.4 (optional)
  }}}

  {"source":"llm-service","project_id":"p1","metrics":{"rag": {
        "kinds": ["raw_chunks","entity_cards"],
        "fused_candidates": 40,
        "used": 8,
        "invalid_citations": 1,
        "validation_warnings": [..] (optional),
        "centrality_augmented": false,
        "answer_tokens": 480,
        "latency_ms": 1400.2
  }}}

These endpoints provide percentile & trend style rollups similar to existing
extraction-stats scaffold.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import math
import os
import time
from datetime import datetime
import json
import glob
import threading

from .ingest import get_history

router = APIRouter(tags=["fusion-rag-analytics"])

# ---------------- Snapshot Persistence (Phase C6 Persistence Upgrade) ----------------
_SNAP_ENABLED = os.getenv("FUSION_RAG_SNAPSHOT_ENABLED", "false").lower() in {"1","true","yes","on"}
_SNAP_DIR = os.getenv("FUSION_RAG_SNAPSHOT_DIR", "fusion_rag_snapshots")
_SNAP_RETENTION_MAX = int(os.getenv("FUSION_RAG_SNAPSHOT_RETENTION_MAX", "200") or 200)
_SNAP_MIN_SECONDS = int(os.getenv("FUSION_RAG_SNAPSHOT_MIN_SECONDS", "300") or 300)  # 5 min default
_last_snapshot_ts: float = 0.0
_snap_lock = threading.Lock()

def _ensure_snap_dir():  # pragma: no cover - trivial
    if not _SNAP_ENABLED:
        return False
    try:
        os.makedirs(_SNAP_DIR, exist_ok=True)
        return True
    except Exception:
        return False

def _snapshot_path(ts: float) -> str:
    iso = datetime.utcfromtimestamp(ts).strftime("%Y%m%dT%H%M%S")
    return os.path.join(_SNAP_DIR, f"snapshot_{iso}_{int(ts)}.json")

def _list_snapshots() -> List[str]:  # pragma: no cover - simple glob
    if not _SNAP_ENABLED:
        return []
    pattern = os.path.join(_SNAP_DIR, "snapshot_*.json")
    return sorted(glob.glob(pattern))

def _enforce_retention():  # pragma: no cover - small
    files = _list_snapshots()
    if len(files) <= _SNAP_RETENTION_MAX:
        return
    to_delete = files[0: len(files) - _SNAP_RETENTION_MAX]
    for f in to_delete:
        try:
            os.remove(f)
        except Exception:
            pass

def _write_snapshot(payload: Dict[str, Any]):  # pragma: no cover - IO
    if not _SNAP_ENABLED:
        return False
    if not _ensure_snap_dir():
        return False
    ts = payload.get("ts") or time.time()
    path = _snapshot_path(ts)
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        os.replace(tmp, path)
        _enforce_retention()
        return True
    except Exception:
        return False

def _maybe_snapshot(fusion: Dict[str, Any], rag: Dict[str, Any], extraction: Optional[Dict[str, Any]]):
    global _last_snapshot_ts
    if not _SNAP_ENABLED:
        return False
    now = time.time()
    # Throttle snapshot frequency
    if (now - _last_snapshot_ts) < _SNAP_MIN_SECONDS:
        return False
    with _snap_lock:
        # Double-check inside lock
        if (now - _last_snapshot_ts) < _SNAP_MIN_SECONDS:
            return False
        payload: Dict[str, Any] = {
            "ts": now,
            "iso_ts": datetime.utcfromtimestamp(now).isoformat() + "Z",
            "version": "c1",
            "fusion": fusion,
            "rag": rag,
            "extraction": extraction,
            "fusion_sample_count": fusion.get("sample_count") if isinstance(fusion, dict) else None,
            "rag_sample_count": rag.get("sample_count") if isinstance(rag, dict) else None,
        }
        ok = _write_snapshot(payload)
        if ok:
            _last_snapshot_ts = now
        return ok


@router.get("/dashboard/schema")
def dashboard_schema():
    """Return merged dashboard schema for frontend wiring (flag-guarded)."""
    if os.getenv("ANALYTICS_PERSIST_ENABLED", "false").lower() not in {"1","true","yes","on"}:
        raise HTTPException(status_code=404, detail="analytics dashboard disabled")
    return {
        "version": "c1",
        "sections": [
            {"name": "fusion", "keys": ["sample_count","kinds_coverage","avg_returned","p50_returned","p95_returned","avg_dedupe_ratio","max_dedupe_ratio","avg_fused_candidates","rrf_k_modes","latest_latency_ms"]},
            {"name": "rag", "keys": ["sample_count","avg_answer_tokens","invalid_citations","validation_warnings","centrality_augmented","latency_ms_p50","latency_ms_p95"]},
            {"name": "extraction", "keys": [
                "layout_chunk_time_ms_avg",
                "tables_merged_total",
                "figures_linked_total",
                "avg_chunk_tokens",
                "p50_layout_chunk_time_ms",
                "p95_layout_chunk_time_ms",
                "trend_last_5_vs_prev_5_pct",
                "avg_section_depth",
                "max_section_depth",
                "section_depth_histogram",
                "mineru_table_count_avg",
                "mineru_header_count_avg",
                "caption_coverage_ratio_avg"
            ]}
        ]
    }


class DashboardStats(BaseModel):
    success: bool
    fusion: Dict[str, Any]
    rag: Dict[str, Any]
    extraction: Optional[Dict[str, Any]] = None
    version: str = Field("c1", const=True)

def _safe_extract_stats(history_func) -> Dict[str, Any]:
    try:
        return history_func()
    except Exception as e:
        return {"success": False, "error": str(e)}


class FusionStats(BaseModel):
    success: bool
    sample_count: int
    kinds_coverage: Dict[str, int]
    avg_returned: float
    p50_returned: float
    p95_returned: float
    avg_dedupe_ratio: float
    max_dedupe_ratio: float
    avg_fused_candidates: float
    rrf_k_modes: Dict[int, int]
    latest_latency_ms: Optional[float]
    notes: Optional[str] = None
    version: str = Field("c1", const=True)


class RAGStats(BaseModel):
    success: bool
    sample_count: int
    kinds_usage_frequency: Dict[str, int]
    centrality_usage_count: int
    avg_fused_candidates: float
    avg_used: float
    p50_used: float
    p95_used: float
    invalid_citation_ratio: float
    avg_answer_tokens: float
    p95_answer_tokens: float
    latest_latency_ms: Optional[float]
    version: str = Field("c1", const=True)
    notes: Optional[str] = None


def _percentile(sorted_list: List[float], p: float) -> float:
    if not sorted_list:
        return 0.0
    k = (len(sorted_list) - 1) * p
    f = int(k)
    c = min(f + 1, len(sorted_list) - 1)
    if f == c:
        return float(sorted_list[f])
    d0 = sorted_list[f] * (c - k)
    d1 = sorted_list[c] * (k - f)
    return float(d0 + d1)


@router.get("/fusion-stats", response_model=FusionStats, summary="Aggregated fusion search analytics")
async def fusion_stats():
    history = get_history()
    fusion_entries = [h for h in history if isinstance(h, dict) and (h.get("metrics") or {}).get("fusion")]
    n = len(fusion_entries)
    if n == 0:
        return FusionStats(
            success=True,
            sample_count=0,
            kinds_coverage={},
            avg_returned=0.0,
            p50_returned=0.0,
            p95_returned=0.0,
            avg_dedupe_ratio=0.0,
            max_dedupe_ratio=0.0,
            avg_fused_candidates=0.0,
            rrf_k_modes={},
            latest_latency_ms=None,
            notes="No fusion metrics ingested yet"
        )
    kinds_coverage: Dict[str, int] = {}
    returned_list: List[float] = []
    dedupes: List[float] = []
    fused_candidates_list: List[float] = []
    rrf_k_modes: Dict[int, int] = {}
    latest_latency_ms: Optional[float] = None
    for entry in fusion_entries:
        fm = entry.get("metrics", {}).get("fusion", {}) or {}
        returned = int(fm.get("returned", 0))
        returned_list.append(returned)
        dedupes.append(float(fm.get("dedupe_ratio", 0.0)))
        fused_candidates_list.append(int(fm.get("fused_candidates", 0)))
        rrf_k = int(fm.get("rrf_k", 0))
        if rrf_k:
            rrf_k_modes[rrf_k] = rrf_k_modes.get(rrf_k, 0) + 1
        cc = fm.get("candidate_counts") or {}
        for k,v in cc.items():
            kinds_coverage[k] = kinds_coverage.get(k, 0) + int(v)
        if "latency_ms" in fm:
            latest_latency_ms = float(fm.get("latency_ms"))
    returned_sorted = sorted(returned_list)
    stats = FusionStats(
        success=True,
        sample_count=n,
        kinds_coverage=kinds_coverage,
        avg_returned=round(sum(returned_list)/n,2),
        p50_returned=round(_percentile(returned_sorted,0.50),2),
        p95_returned=round(_percentile(returned_sorted,0.95),2),
        avg_dedupe_ratio=round(sum(dedupes)/n,4),
        max_dedupe_ratio=round(max(dedupes),4),
        avg_fused_candidates=round(sum(fused_candidates_list)/n,2),
        rrf_k_modes=rrf_k_modes,
        latest_latency_ms=latest_latency_ms,
    )
    return stats


@router.get("/rag-metrics", response_model=RAGStats, summary="Aggregated advanced RAG analytics")
async def rag_metrics():
    history = get_history()
    rag_entries = [h for h in history if isinstance(h, dict) and (h.get("metrics") or {}).get("rag")]
    n = len(rag_entries)
    if n == 0:
        return RAGStats(
            success=True,
            sample_count=0,
            kinds_usage_frequency={},
            centrality_usage_count=0,
            avg_fused_candidates=0.0,
            avg_used=0.0,
            p50_used=0.0,
            p95_used=0.0,
            invalid_citation_ratio=0.0,
            avg_answer_tokens=0.0,
            p95_answer_tokens=0.0,
            latest_latency_ms=None,
            notes="No RAG analytics ingested yet"
        )
    kinds_usage: Dict[str,int] = {}
    centrality_usage = 0
    fused_list: List[float] = []
    used_list: List[float] = []
    invalid_list: List[int] = []
    answer_tokens: List[float] = []
    latest_latency_ms: Optional[float] = None
    for entry in rag_entries:
        rm = entry.get("metrics", {}).get("rag", {}) or {}
        for k in rm.get("kinds", []) or []:
            kinds_usage[k] = kinds_usage.get(k,0)+1
        if rm.get("centrality_augmented"):
            centrality_usage += 1
        fused_list.append(int(rm.get("fused_candidates",0)))
        used_list.append(int(rm.get("used",0)))
        invalid_list.append(int(rm.get("invalid_citations",0)))
        answer_tokens.append(float(rm.get("answer_tokens",0)))
        if "latency_ms" in rm:
            latest_latency_ms = float(rm.get("latency_ms"))
    sample_count = len(rag_entries)
    used_sorted = sorted(used_list)
    invalid_total = sum(invalid_list)
    total_used = sum(used_list)
    invalid_ratio = (invalid_total / total_used) if total_used > 0 else 0.0
    answer_sorted = sorted(answer_tokens)
    stats = RAGStats(
        success=True,
        sample_count=sample_count,
        kinds_usage_frequency=kinds_usage,
        centrality_usage_count=centrality_usage,
        avg_fused_candidates=round(sum(fused_list)/sample_count,2),
        avg_used=round(sum(used_list)/sample_count,2),
        p50_used=round(_percentile(used_sorted,0.50),2),
        p95_used=round(_percentile(used_sorted,0.95),2),
        invalid_citation_ratio=round(invalid_ratio,4),
        avg_answer_tokens=round(sum(answer_tokens)/sample_count,2),
        p95_answer_tokens=round(_percentile(answer_sorted,0.95),2),
        latest_latency_ms=latest_latency_ms,
    )
    return stats

@router.get("/dashboard", response_model=DashboardStats, summary="Unified dashboard of fusion, rag, extraction stats")
async def dashboard():
    # Reuse internal functions; call sequentially
    fusion = await fusion_stats()
    rag = await rag_metrics()
    # Attempt to import extraction stats endpoint logic dynamically to avoid circular import
    extraction_data: Optional[Dict[str, Any]] = None
    try:
        from .extraction_stats import extraction_stats as _extraction_stats
        extraction_data = await _extraction_stats()
        if hasattr(extraction_data, 'dict'):
            extraction_data = extraction_data.dict()
    except Exception:
        extraction_data = None
    fusion_dict = fusion.dict() if hasattr(fusion, 'dict') else fusion
    rag_dict = rag.dict() if hasattr(rag, 'dict') else rag
    # Attempt snapshot (non-blocking semantics are fine; currently synchronous but cheap)
    try:
        _maybe_snapshot(fusion_dict, rag_dict, extraction_data)
    except Exception:
        pass
    return DashboardStats(success=True, fusion=fusion_dict, rag=rag_dict, extraction=extraction_data)


@router.get("/fusion-rag/snapshots", summary="List available fusion/rag analytics snapshots")
async def list_fusion_rag_snapshots(limit: int = 50):
    if not _SNAP_ENABLED:
        return {"enabled": False, "snapshots": []}
    files = _list_snapshots()
    entries: List[Dict[str, Any]] = []
    for fpath in reversed(files[-limit:]):  # newest first
        try:
            st = os.stat(fpath)
            with open(fpath, "r", encoding="utf-8") as rf:
                # Peek minimal metadata without loading entire file again (they are small anyway)
                data = json.load(rf)
            entries.append({
                "file": os.path.basename(fpath),
                "ts": data.get("ts"),
                "iso_ts": data.get("iso_ts"),
                "size_bytes": st.st_size,
                "fusion_sample_count": data.get("fusion_sample_count"),
                "rag_sample_count": data.get("rag_sample_count"),
                "version": data.get("version"),
            })
        except Exception:
            continue
    return {"enabled": True, "count": len(entries), "snapshots": entries}


@router.get("/fusion-rag/snapshots/latest", summary="Fetch latest fusion/rag analytics snapshot")
async def latest_fusion_rag_snapshot():
    if not _SNAP_ENABLED:
        return {"enabled": False, "snapshot": None}
    files = _list_snapshots()
    if not files:
        raise HTTPException(status_code=404, detail="No snapshots available")
    latest = files[-1]
    try:
        with open(latest, "r", encoding="utf-8") as rf:
            data = json.load(rf)
        return {"enabled": True, "snapshot": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read snapshot: {e}")

__all__ = ["router"]
