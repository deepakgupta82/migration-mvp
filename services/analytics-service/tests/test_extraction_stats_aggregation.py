from fastapi.testclient import TestClient
from app.main import app  # type: ignore

client = TestClient(app)

def test_extraction_stats_empty():
    r = client.get("/extraction-stats")
    assert r.status_code == 200
    data = r.json()
    assert data["sample_count"] == 0


def test_extraction_stats_with_ingest():
    # Ingest two fake layout metric records
    rec1 = {
        "source": "document-service",
        "project_id": "p1",
        "filename": "a.pdf",
        "metrics": {"elapsed_ms": 12.5, "tables_merged": 1, "figures_bound": 0, "paragraphs_split": 1, "over_budget_elements": 0, "avg_chunk_tokens": 120.0, "max_chunk_tokens": 400, "number_of_chunks": 10}
    }
    rec2 = {
        "source": "document-service",
        "project_id": "p1",
        "filename": "b.pdf",
        "metrics": {"elapsed_ms": 37.0, "tables_merged": 0, "figures_bound": 2, "paragraphs_split": 0, "over_budget_elements": 2, "avg_chunk_tokens": 90.0, "max_chunk_tokens": 500, "number_of_chunks": 8}
    }
    ir1 = client.post("/ingest", json=rec1)
    assert ir1.status_code == 200
    ir2 = client.post("/ingest", json=rec2)
    assert ir2.status_code == 200
    r = client.get("/extraction-stats")
    assert r.status_code == 200
    data = r.json()
    assert data["sample_count"] >= 2
    assert data["tables_merged"] >= 1
    assert data["figures_linked"] >= 2
    assert data["over_budget_elements_total"] >= 2
    assert data["paragraphs_split_total"] >= 1
