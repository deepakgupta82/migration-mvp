import os
from fastapi.testclient import TestClient
from app.main import app  # type: ignore

client = TestClient(app)

def test_bulk_embeddings_lru_eviction():
    os.environ.setdefault("EMBED_BATCH_MAX", "4")
    os.environ.setdefault("EMBED_CACHE_ENABLED", "true")
    os.environ.setdefault("EMBED_CACHE_MAX_ENTRIES", "3")
    os.environ.setdefault("EMBED_CACHE_TTL_SECONDS", "3600")
    # First batch
    texts1 = ["t1","t2","t3"]
    r1 = client.post("/bulk-embeddings", json={"texts": texts1})
    assert r1.status_code == 200
    # Second batch introduces new key causing eviction
    r2 = client.post("/bulk-embeddings", json={"texts": ["t4"]})
    assert r2.status_code == 200
    # Third call referencing one old (t1) may be a miss if evicted
    r3 = client.post("/bulk-embeddings", json={"texts": ["t1"]})
    assert r3.status_code == 200
    metrics = r3.json().get("metrics", {})
    # At least one eviction should have occurred
    assert metrics.get("evictions", 0) >= 1
