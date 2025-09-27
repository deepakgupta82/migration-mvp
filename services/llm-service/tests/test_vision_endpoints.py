import os
import pytest
from fastapi.testclient import TestClient

# Ensure fake mode & multimodal enabled for deterministic tests
os.environ.setdefault("LLM_FAKE_RESPONSES", "true")
os.environ.setdefault("MULTIMODAL_ENABLED", "true")

from main import app  # noqa: E402

client = TestClient(app)

@pytest.mark.parametrize("endpoint,payload_key", [
    ("/api/llm/multimodal/tables", "tables"),
    ("/api/llm/multimodal/diagrams", "entities"),
])
def test_multimodal_fake_mode(endpoint, payload_key):
    resp = client.post(endpoint, json={"project_id": "test-proj", "image_urls": []})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    assert payload_key in data["data"], data

def test_multimodal_disabled():
    os.environ["MULTIMODAL_ENABLED"] = "false"
    resp = client.post("/api/llm/multimodal/tables", json={"project_id": "p1", "image_urls": []})
    # Recreate client to pick up env change not strictly necessary but done for isolation
    # fast path: endpoint returns success False with error
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert "disabled" in body.get("error",""), body
    os.environ["MULTIMODAL_ENABLED"] = "true"  # reset
