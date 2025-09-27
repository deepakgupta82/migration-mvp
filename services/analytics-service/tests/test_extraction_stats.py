from pathlib import Path
import importlib.util
import sys

SERVICE_ROOT = Path(__file__).resolve().parents[1]

def _load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module {module_name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    sys.path.pop(0)
    return module

main_module = _load_module("analytics_service_main", SERVICE_ROOT / "main.py")
ingest_module = _load_module("analytics_service_ingest", SERVICE_ROOT / "app" / "routers" / "ingest.py")

from fastapi.testclient import TestClient

app = main_module.app  # type: ignore[attr-defined]
reload_persisted = ingest_module.reload_persisted  # type: ignore[attr-defined]

client = TestClient(app)

def test_extraction_stats_structure():
    r = client.get("/extraction-stats")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["success"] is True
    # Ensure keys present
    for k in [
        "layout_chunk_time_ms",
        "tables_merged",
        "figures_linked",
        "avg_section_depth",
        "raw_enrichment_cache",
        "captions_total",
        "project_rollup",
    ]:
        assert k in data
    # Types / ranges
    assert isinstance(data["layout_chunk_time_ms"], (int, float))
    assert isinstance(data["tables_merged"], int)
    assert isinstance(data["figures_linked"], int)
    assert isinstance(data["avg_section_depth"], (int, float))
    # enrichment hit rate optional
    if data.get("enrichment_cache_hit_rate") is not None:
        assert 0.0 <= data["enrichment_cache_hit_rate"] <= 1.0


def test_extraction_stats_with_history():
    reload_persisted()
    # Ingest layout chunk metrics for two projects
    payloads = [
        {
            "source": "document-service",
            "project_id": "projA",
            "filename": "doc1.pdf",
            "metrics": {
                "number_of_chunks": 5,
                "elapsed_ms": 100.0,
                "tables_merged": 1,
                "figures_bound": 2,
                "over_budget_elements": 1,
                "paragraphs_split": 2,
                "avg_chunk_tokens": 120.0,
                "max_chunk_tokens": 300,
            },
            "ts": 1_700_000_000.0,
        },
        {
            "source": "document-service",
            "project_id": "projB",
            "filename": "doc2.pdf",
            "metrics": {
                "number_of_chunks": 4,
                "elapsed_ms": 200.0,
                "tables_merged": 0,
                "figures_bound": 1,
                "over_budget_elements": 0,
                "paragraphs_split": 1,
                "avg_chunk_tokens": 80.0,
                "max_chunk_tokens": 220,
            },
            "ts": 1_700_000_500.0,
        },
        {
            "source": "document-service",
            "project_id": "projA",
            "filename": "doc1.pdf",
            "metrics": {
                "layout": {
                    "avg_section_depth": 2.5,
                    "max_section_depth": 5,
                    "mineru_table_count": 4,
                    "mineru_header_count": 8,
                    "caption_coverage_ratio": 0.5,
                    "captions_total": 4,
                    "captions_linked": 2,
                    "multi_page_tables_merged": 1,
                    "section_depth_histogram": {"1": 2, "2": 3},
                }
            },
            "ts": 1_700_000_100.0,
        },
        {
            "source": "document-service",
            "project_id": "projB",
            "filename": "doc2.pdf",
            "metrics": {
                "layout": {
                    "avg_section_depth": 3.0,
                    "max_section_depth": 6,
                    "mineru_table_count": 5,
                    "mineru_header_count": 5,
                    "caption_coverage_ratio": 1.0,
                    "captions_total": 3,
                    "captions_linked": 3,
                    "multi_page_tables_merged": 2,
                    "section_depth_histogram": {"1": 1, "3": 2},
                }
            },
            "ts": 1_700_000_600.0,
        },
    ]
    for payload in payloads:
        resp = client.post("/ingest", json=payload)
        assert resp.status_code == 200, resp.text

    r = client.get("/extraction-stats")
    assert r.status_code == 200, r.text
    data = r.json()

    assert data["sample_count"] == 2
    assert data["tables_merged"] == 1
    assert data["figures_linked"] == 3
    assert data["multi_page_tables_merged_total"] == 3
    assert data["captions_total"] == 7
    assert data["captions_linked_total"] == 5
    assert data["avg_section_depth"] == 2.75
    assert data["caption_coverage_ratio_avg"] == 0.75

    rollups = {entry["project_id"]: entry for entry in data["project_rollup"]}
    proj_a = rollups["projA"]
    proj_b = rollups["projB"]

    assert proj_a["sample_count"] == 1
    assert proj_a["multi_page_tables_merged"] == 1
    assert proj_a["caption_coverage_ratio_avg"] == 0.5
    assert proj_a["avg_section_depth"] == 2.5

    assert proj_b["sample_count"] == 1
    assert proj_b["multi_page_tables_merged"] == 2
    assert proj_b["caption_coverage_ratio_avg"] == 1.0
    assert proj_b["avg_section_depth"] == 3.0
