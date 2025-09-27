import os
import asyncio
import json

from fastapi.testclient import TestClient

# Assuming main FastAPI app is exposed as `app` in services/llm-service/app/main.py
try:
    from app.main import app  # type: ignore
except Exception:  # pragma: no cover
    raise

client = TestClient(app)

def test_enrichment_cache_hit_miss(monkeypatch):
    os.environ.setdefault("ENRICH_CACHE_ENABLED", "true")
    os.environ.setdefault("ENRICH_CACHE_MAX_ENTRIES", "10")
    os.environ.setdefault("ENRICH_CACHE_TTL_SECONDS", "60")

    payload = {
        "project_id": "test-project",
        "text": "Acme Corp acquired Beta LLC in 2024 for $5M.",
        "mode": "facts_entities"
    }

    # First request -> miss
    r1 = client.post("/enrich", json=payload, headers={"Authorization": "Bearer service-backend-token"})
    assert r1.status_code == 200, r1.text
    data1 = r1.json()
    assert data1.get("success") is True
    assert data1.get("cache_enabled") in (True, False)
    cache_key = data1.get("cache_key")
    assert cache_key

    # Second request (same payload) -> should be hit if caching enabled
    r2 = client.post("/enrich", json=payload, headers={"Authorization": "Bearer service-backend-token"})
    assert r2.status_code == 200, r2.text
    data2 = r2.json()
    assert data2.get("success") is True
    assert data2.get("cache_key") == cache_key

    # Fetch health to inspect metrics
    h = client.get("/health")
    assert h.status_code == 200, h.text
    hdata = h.json()
    enrich_metrics = hdata.get("cache_status", {}).get("enrichment", {})
    # Basic presence assertions
    assert "hits" in enrich_metrics and "misses" in enrich_metrics
    # At least 1 miss (first) and 1 hit (second) if cache enabled
    if data2.get("cache_enabled"):
        assert enrich_metrics["hits"] >= 1
        assert enrich_metrics["misses"] >= 1


def test_enrichment_cache_force_refresh(monkeypatch):
    os.environ["FORCE_REFRESH_ENRICH"] = "true"
    payload = {
        "project_id": "test-project",
        "text": "Contoso divested Gamma Division in 2025.",
        "mode": "facts_entities"
    }
    r = client.post("/enrich", json=payload, headers={"Authorization": "Bearer service-backend-token"})
    assert r.status_code == 200
    d = r.json()
    assert d.get("cache_forced") is True
    # disable flag for rest of tests
    os.environ["FORCE_REFRESH_ENRICH"] = "false"