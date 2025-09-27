import os
import pytest
from fastapi.testclient import TestClient
from app.main import app

# Ensure multimodal + fake mode so LLM call does not invoke external providers
os.environ.setdefault("MULTIMODAL_ENABLED", "true")
os.environ.setdefault("LLM_FAKE_RESPONSES", "true")
# Keep OCR disabled for speed
os.environ.setdefault("OCR_ENABLED", "false")

client = TestClient(app)

@pytest.mark.parametrize("endpoint", ["/api/llm/multimodal/tables", "/api/llm/multimodal/diagrams"])
def test_vision_cache_reuse(monkeypatch, endpoint):
    """Exercise image caching by calling same URL twice and inspecting metrics delta.

    We rely on health endpoint's vision metrics to verify a hit on the second call.
    """
    test_url = "https://example.com/image1.png"

    # Monkeypatch httpx to avoid real network call
    import httpx

    class DummyResponse:
        def __init__(self):
            self.status_code = 200
            self.headers = {"content-type": "image/png"}
            self.content = b"fake-image-bytes"  # deterministic bytes

    async def dummy_get(self, url):  # type: ignore
        return DummyResponse()

    monkeypatch.setattr(httpx.AsyncClient, "get", dummy_get, raising=True)

    # First call -> miss
    first = client.post(endpoint, json={"project_id": "p1", "image_urls": [test_url]})
    assert first.status_code == 200
    # Second call -> should hit cache
    second = client.post(endpoint, json={"project_id": "p1", "image_urls": [test_url]})
    assert second.status_code == 200

    # Inspect health metrics
    health = client.get("/api/llm/health").json()
    vision = health.get("cache_status", {}).get("vision", {})
    assert vision.get("vision_cache_hits", 0) >= 1, f"Expected at least one cache hit, metrics={vision}"
    assert vision.get("vision_cache_misses", 0) >= 1, f"Expected at least one cache miss, metrics={vision}"
