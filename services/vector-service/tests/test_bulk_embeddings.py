import os
from fastapi.testclient import TestClient

from app.main import app  # type: ignore

client = TestClient(app)

def test_bulk_embeddings_basic():
    os.environ.setdefault("EMBED_BATCH_MAX", "8")
    os.environ.setdefault("EMBED_CACHE_ENABLED", "true")
    payload = {"texts": ["alpha", "beta", "gamma"], "project_id": "p1"}
    r1 = client.post("/bulk-embeddings", json=payload)
    assert r1.status_code == 200, r1.text
    d1 = r1.json()
    assert d1["success"] is True
    assert d1["generated"] == 3
    assert d1["cached"] == 0
    # Second call should hit cache
    r2 = client.post("/bulk-embeddings", json=payload)
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["cached"] >= 3  # all three reused
    assert d2["generated"] == 0


def test_bulk_embeddings_cap_enforced():
    os.environ["EMBED_BATCH_MAX"] = "2"
    payload = {"texts": ["a","b","c"], "project_id": "p1"}
    r = client.post("/bulk-embeddings", json=payload)
    assert r.status_code == 400
    assert "exceeds" in r.json().get("detail","")
