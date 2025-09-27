"""Extraction Analytics Scaffold (B3)

Provides a placeholder endpoint returning extraction-related metrics.
Future plan:
 - Integrate real timers around layout chunking in document-service (export via event or shared store)
 - Aggregate table merge counts and figure linkage counts from processing pipeline
 - Compute enrichment cache hit rate by querying llm-service health endpoint
 - Add avg_section_depth when section paths (A2 advanced) implemented
"""
from __future__ import annotations

import os
import httpx
from typing import Dict, Any, Optional, List
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["extraction-analytics"])

LLM_SERVICE_URL = os.getenv("LLM_SERVICE_URL", "http://localhost:8007")

class ProjectExtractionStats(BaseModel):
    project_id: Optional[str]
    sample_count: int
    avg_layout_chunk_time_ms: float
    tables_merged: int
    figures_linked: int
    multi_page_tables_merged: int
    avg_section_depth: float
    caption_coverage_ratio_avg: float
    mineru_table_count_avg: float
    mineru_header_count_avg: float
    last_ingested_ts: Optional[float]


class ExtractionStatsResponse(BaseModel):
    success: bool
    layout_chunk_time_ms: float
    tables_merged: int
    figures_linked: int
    avg_section_depth: float
    max_section_depth: int | float
    mineru_table_count_avg: float
    mineru_header_count_avg: float
    caption_coverage_ratio_avg: float
    section_depth_histogram: Dict[int, int] | Dict[str, int]
    captions_total: int
    captions_linked_total: int
    multi_page_tables_merged_total: int
    enrichment_cache_hit_rate: Optional[float]
    raw_enrichment_cache: Dict[str, Any]
    notes: str
    sample_count: int
    max_layout_chunk_time_ms: float
    min_layout_chunk_time_ms: float
    p50_layout_chunk_time_ms: float
    p95_layout_chunk_time_ms: float
    avg_chunk_tokens: float
    max_chunk_tokens: float
    over_budget_elements_total: int
    paragraphs_split_total: int
    trend_last_5_vs_prev_5_pct: Optional[float]
    project_rollup: List[ProjectExtractionStats]
    version: str = "c1"

async def _fetch_enrichment_cache_metrics() -> tuple[Optional[float], Dict[str, Any]]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{LLM_SERVICE_URL}/health")
            if r.status_code >= 400:
                return None, {"error": f"status {r.status_code}"}
            data = r.json()
            enrich = (data.get("cache_status", {}) or {}).get("enrichment", {})
            hits = float(enrich.get("hits", 0))
            misses = float(enrich.get("misses", 0))
            denom = hits + misses
            hit_rate = (hits / denom) if denom > 0 else None
            return hit_rate, enrich
    except Exception as e:  # pragma: no cover - network/connection issues
        return None, {"error": str(e)}

@router.get("/extraction-stats", response_model=ExtractionStatsResponse, summary="Extraction analytics metrics (aggregated)")
async def extraction_stats():
    from .ingest import get_history  # local import to avoid circular at module load
    hit_rate, enrich_raw = await _fetch_enrichment_cache_metrics()
    history = get_history()
    project_rollups: Dict[str, Dict[str, Any]] = {}

    def _get_project_bucket(project_id: Optional[str]) -> Dict[str, Any]:
        key = project_id or "__unknown__"
        bucket = project_rollups.get(key)
        if bucket is None:
            bucket = {
                "project_id": project_id,
                "sample_count": 0,
                "total_elapsed_ms": 0.0,
                "tables_merged": 0,
                "figures_linked": 0,
                "total_over_budget": 0,
                "total_paragraphs_split": 0,
                "avg_chunk_tokens_sum": 0.0,
                "max_chunk_tokens": 0,
                "layout_records": 0,
                "avg_section_depth_sum": 0.0,
                "mineru_table_count_sum": 0.0,
                "mineru_header_count_sum": 0.0,
                "caption_total": 0,
                "caption_linked": 0,
                "multi_page_tables": 0,
                "caption_ratio_sum": 0.0,
                "latest_ts": 0.0,
            }
            project_rollups[key] = bucket
        return bucket
    # Filter layout-aware metrics entries
    layout_entries = [h for h in history if isinstance(h, dict) and (h.get("metrics") or {}).get("number_of_chunks") is not None]
    sample_count = len(layout_entries)
    if sample_count == 0:
        return ExtractionStatsResponse(
            success=True,
            layout_chunk_time_ms=0.0,
            tables_merged=0,
            figures_linked=0,
            avg_section_depth=0.0,
            max_section_depth=0,
            mineru_table_count_avg=0.0,
            mineru_header_count_avg=0.0,
            caption_coverage_ratio_avg=0.0,
            section_depth_histogram={},
            captions_total=0,
            captions_linked_total=0,
            multi_page_tables_merged_total=0,
            enrichment_cache_hit_rate=hit_rate,
            raw_enrichment_cache=enrich_raw,
            notes=("No ingested layout metrics yet. "
                   "Percentiles and trend fields are zero by definition."),
            sample_count=0,
            max_layout_chunk_time_ms=0.0,
            min_layout_chunk_time_ms=0.0,
            p50_layout_chunk_time_ms=0.0,
            p95_layout_chunk_time_ms=0.0,
            avg_chunk_tokens=0.0,
            max_chunk_tokens=0.0,
            over_budget_elements_total=0,
            paragraphs_split_total=0,
            trend_last_5_vs_prev_5_pct=None,
            project_rollup=[],
        )
    # Aggregations
    total_time = 0.0
    max_time = 0.0
    min_time = None
    total_tables = 0
    total_figures = 0
    # New MinerU aggregation accumulators
    mineru_section_depth_sum = 0.0
    mineru_section_depth_max_seen = 0
    mineru_section_depth_count = 0
    mineru_table_count_sum = 0
    mineru_header_count_sum = 0
    caption_coverage_sum = 0.0
    histogram_agg: Dict[int, int] = {}
    total_over_budget = 0
    total_paragraphs_split = 0
    total_avg_chunk_tokens = 0.0
    max_chunk_tokens_seen = 0
    times: list[float] = []
    for entry in layout_entries:
        m = entry.get("metrics", {})
        t = float(m.get("elapsed_ms", 0.0))
        total_time += t
        if t > max_time:
            max_time = t
        if min_time is None or t < min_time:
            min_time = t
        times.append(t)
        total_tables += int(m.get("tables_merged", 0))
        total_figures += int(m.get("figures_bound", 0))
        total_over_budget += int(m.get("over_budget_elements", 0))
        total_paragraphs_split += int(m.get("paragraphs_split", 0))
        total_avg_chunk_tokens += float(m.get("avg_chunk_tokens", 0.0))
        max_chunk_tokens_seen = max(max_chunk_tokens_seen, int(m.get("max_chunk_tokens", 0)))
        bucket = _get_project_bucket(entry.get("project_id"))
        bucket["sample_count"] += 1
        bucket["total_elapsed_ms"] += t
        bucket["tables_merged"] += int(m.get("tables_merged", 0))
        bucket["figures_linked"] += int(m.get("figures_bound", 0))
        bucket["total_over_budget"] += int(m.get("over_budget_elements", 0))
        bucket["total_paragraphs_split"] += int(m.get("paragraphs_split", 0))
        bucket["avg_chunk_tokens_sum"] += float(m.get("avg_chunk_tokens", 0.0))
        bucket["max_chunk_tokens"] = max(bucket["max_chunk_tokens"], int(m.get("max_chunk_tokens", 0)))
        entry_ts = entry.get("ts")
        if entry_ts is not None:
            try:
                bucket["latest_ts"] = max(bucket["latest_ts"], float(entry_ts))
            except Exception:
                pass

    # Also scan history for document-service layout events containing MinerU metrics
    captions_total_sum = 0
    captions_linked_sum = 0
    multi_page_tables_sum = 0
    for entry in history:
        if not isinstance(entry, dict):
            continue
        metrics = entry.get("metrics") or {}
        layout = metrics.get("layout") or {}
        if not layout:
            continue
        bucket = _get_project_bucket(entry.get("project_id"))
        bucket["layout_records"] += 1
        # Sum/avg fields
        if "avg_section_depth" in layout:
            mineru_section_depth_sum += float(layout.get("avg_section_depth", 0.0))
            mineru_section_depth_count += 1
            bucket["avg_section_depth_sum"] += float(layout.get("avg_section_depth", 0.0))
        if "max_section_depth" in layout:
            try:
                mineru_section_depth_max_seen = max(mineru_section_depth_max_seen, int(layout.get("max_section_depth", 0)))
                bucket["max_section_depth"] = max(bucket.get("max_section_depth", 0), int(layout.get("max_section_depth", 0)))
            except Exception:
                pass
        mineru_table_count_sum += int(layout.get("mineru_table_count", 0))
        mineru_header_count_sum += int(layout.get("mineru_header_count", 0))
        bucket["mineru_table_count_sum"] += float(layout.get("mineru_table_count", 0.0))
        bucket["mineru_header_count_sum"] += float(layout.get("mineru_header_count", 0.0))
        caption_ratio = float(layout.get("caption_coverage_ratio", 0.0))
        caption_coverage_sum += caption_ratio
        # Merge histogram bins
        hist = layout.get("section_depth_histogram") or {}
        if isinstance(hist, dict):
            for k, v in hist.items():
                try:
                    ki = int(k)
                except Exception:
                    continue
                histogram_agg[ki] = histogram_agg.get(ki, 0) + int(v)
        captions_total = int(layout.get("captions_total", 0))
        captions_linked = int(layout.get("captions_linked", 0))
        multi_page_tables = int(layout.get("multi_page_tables_merged", 0))
        captions_total_sum += captions_total
        captions_linked_sum += captions_linked
        multi_page_tables_sum += multi_page_tables
        bucket["caption_total"] += captions_total
        bucket["caption_linked"] += captions_linked
        bucket["multi_page_tables"] += multi_page_tables
        bucket["caption_ratio_sum"] += caption_ratio
        entry_ts = entry.get("ts")
        if entry_ts is not None:
            try:
                bucket["latest_ts"] = max(bucket["latest_ts"], float(entry_ts))
            except Exception:
                pass
    avg_time = total_time / sample_count if sample_count else 0.0
    avg_avg_chunk_tokens = total_avg_chunk_tokens / sample_count if sample_count else 0.0

    # Percentiles
    times_sorted = sorted(times)
    def _percentile(sorted_list, p: float) -> float:
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
    p50 = _percentile(times_sorted, 0.50)
    p95 = _percentile(times_sorted, 0.95)

    # Trend: compare avg of last 5 vs previous 5 (if >=10 samples)
    trend_pct: Optional[float] = None
    if sample_count >= 10:
        last5 = times_sorted[-5:]
        prev5 = times_sorted[-10:-5]
        prev_avg = sum(prev5) / 5
        last_avg = sum(last5) / 5
        if prev_avg > 0:
            trend_pct = ((last_avg - prev_avg) / prev_avg) * 100.0

    project_rollup: List[ProjectExtractionStats] = []
    for key, bucket in project_rollups.items():
        project_id = bucket["project_id"] if key != "__unknown__" else None
        sample_ct = bucket["sample_count"]
        layout_records = bucket["layout_records"]
        avg_time_ms = (bucket["total_elapsed_ms"] / sample_ct) if sample_ct else 0.0
        avg_section_depth = (bucket["avg_section_depth_sum"] / layout_records) if layout_records else 0.0
        caption_ratio = (bucket["caption_linked"] / bucket["caption_total"]) if bucket["caption_total"] else 0.0
        mineru_table_avg = (bucket["mineru_table_count_sum"] / layout_records) if layout_records else 0.0
        mineru_header_avg = (bucket["mineru_header_count_sum"] / layout_records) if layout_records else 0.0
        project_rollup.append(ProjectExtractionStats(
            project_id=project_id,
            sample_count=sample_ct,
            avg_layout_chunk_time_ms=round(avg_time_ms, 2),
            tables_merged=bucket["tables_merged"],
            figures_linked=bucket["figures_linked"],
            multi_page_tables_merged=bucket["multi_page_tables"],
            avg_section_depth=round(avg_section_depth, 3),
            caption_coverage_ratio_avg=round(caption_ratio, 4),
            mineru_table_count_avg=round(mineru_table_avg, 2),
            mineru_header_count_avg=round(mineru_header_avg, 2),
            last_ingested_ts=(bucket["latest_ts"] or None),
        ))

    project_rollup_sorted = sorted(project_rollup, key=lambda item: (-item.sample_count, item.project_id or ""))
    project_rollup_limited = project_rollup_sorted[:10]

    return ExtractionStatsResponse(
        success=True,
        layout_chunk_time_ms=round(avg_time, 2),
        tables_merged=total_tables,
        figures_linked=total_figures,
        avg_section_depth=(round(mineru_section_depth_sum / mineru_section_depth_count, 3) if mineru_section_depth_count else 0.0),
        max_section_depth=mineru_section_depth_max_seen,
        mineru_table_count_avg=(round(mineru_table_count_sum / mineru_section_depth_count, 2) if mineru_section_depth_count else 0.0),
        mineru_header_count_avg=(round(mineru_header_count_sum / mineru_section_depth_count, 2) if mineru_section_depth_count else 0.0),
        caption_coverage_ratio_avg=(round(caption_coverage_sum / mineru_section_depth_count, 4) if mineru_section_depth_count else 0.0),
        section_depth_histogram=dict(sorted(histogram_agg.items(), key=lambda kv: kv[0])),
        captions_total=captions_total_sum,
        captions_linked_total=captions_linked_sum,
        multi_page_tables_merged_total=multi_page_tables_sum,
        enrichment_cache_hit_rate=hit_rate,
        raw_enrichment_cache=enrich_raw,
        notes="Aggregated over ingested layout metrics.",
        sample_count=sample_count,
        max_layout_chunk_time_ms=round(max_time, 2),
        min_layout_chunk_time_ms=round(min_time or 0.0, 2),
        p50_layout_chunk_time_ms=round(p50, 2),
        p95_layout_chunk_time_ms=round(p95, 2),
        avg_chunk_tokens=round(avg_avg_chunk_tokens, 2),
        max_chunk_tokens=max_chunk_tokens_seen,
        over_budget_elements_total=total_over_budget,
        paragraphs_split_total=total_paragraphs_split,
        trend_last_5_vs_prev_5_pct=(round(trend_pct, 2) if trend_pct is not None else None),
        project_rollup=project_rollup_limited,
    )
