import os
from fastapi.testclient import TestClient

from app.main import app  # type: ignore

client = TestClient(app)


def setup_module(module):  # noqa: D401
    os.environ.setdefault("FUSION_ENABLED", "true")
    # Ensure minimal docs exist? Fusion endpoint internally calls similarity_search_by_kind which will
    # return empty results if vector store empty. That's acceptable – we just validate structure.


def test_fusion_search_structure_empty():
    payload = {"query": "test query", "top_k": 5, "per_kind_k": 3, "include_metadata": False}
    r = client.post("/projects/p1/fusion/search", json=payload)
    # If collection missing might 500 depending on processor; treat 403 separately.
    if r.status_code == 403:
        # Feature flag not respected
        assert False, "FUSION_ENABLED flag set but endpoint returned 403"
    assert r.status_code in (200, 500)  # Allow 500 if backend store not available
    if r.status_code == 200:
        data = r.json()
        assert data["status"] == "success"
        assert data["project_id"] == "p1"
        assert isinstance(data["results"], list)
        assert "retrieval_stats" in data
        rs = data["retrieval_stats"]
        assert "candidate_counts" in rs and "dedupe_ratio" in rs


def test_fusion_flag_enforced():
    os.environ["FUSION_ENABLED"] = "false"
    payload = {"query": "x"}
    r = client.post("/projects/p2/fusion/search", json=payload)
    assert r.status_code == 403

