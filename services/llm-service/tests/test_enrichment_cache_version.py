import os
from fastapi.testclient import TestClient
from app.main import app  # type: ignore

client = TestClient(app)

def test_enrichment_cache_version_keying(monkeypatch):
    os.environ.setdefault("ENRICH_CACHE_ENABLED", "true")
    os.environ.setdefault("ENRICH_SCHEMA_VERSION", "vTest1")
    payload = {
        "process_type": "rag_synthesis",
        "prompt": "Test prompt for version v1",
        "allow_global": True,
    }
    r1 = client.post("/api/llm/process", json=payload)
    assert r1.status_code == 200
    # Change version -> force miss
    os.environ["ENRICH_SCHEMA_VERSION"] = "vTest2"
    r2 = client.post("/api/llm/process", json=payload)
    assert r2.status_code == 200
    # Fetch health to inspect metrics
    h = client.get("/health")
    assert h.status_code == 200
    data = h.json()
    enrich = data.get("cache_status", {}).get("enrichment", {})
    assert enrich.get("version") == "vTest2"
    # At least 1 miss for new version
    assert enrich.get("misses", 0) >= 1
