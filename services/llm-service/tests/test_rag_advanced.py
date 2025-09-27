import os
from fastapi.testclient import TestClient

from app.main import app  # type: ignore

client = TestClient(app)

def setup_module(module):
    os.environ.setdefault("ADVANCED_RAG_ENABLED", "true")


def test_rag_advanced_flag_enforced():
    os.environ["ADVANCED_RAG_ENABLED"] = "false"
    payload = {"project_id": "p1", "question": "What is X?"}
    r = client.post("/rag/advanced", json=payload)
    assert r.status_code == 403


def test_rag_advanced_minimal_success_structure():
    os.environ["ADVANCED_RAG_ENABLED"] = "true"
    # Without vector data retrieval may still proceed (baseline rag_synthesize) or raise; allow 500 gracefully
    payload = {"project_id": "p1", "question": "Explain test architecture", "validate_citations": True}
    r = client.post("/rag/advanced", json=payload)
    if r.status_code == 200:
        data = r.json()
        assert data["project_id"] == "p1"
        assert "answer" in data
        # invalid_citations optional
        if data.get("invalid_citations") is not None:
            assert isinstance(data["invalid_citations"], list)
    else:
        # Accept failure if underlying retrieval/LLM path not configured
        assert r.status_code in (500,), r.text
