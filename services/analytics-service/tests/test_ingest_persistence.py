import os
import json
from fastapi.testclient import TestClient

from app.main import app  # type: ignore

client = TestClient(app)


def setup_module(module):
    # Enable persistence to a temp file
    os.environ["ANALYTICS_PERSIST_ENABLED"] = "true"
    os.environ["ANALYTICS_PERSIST_PATH"] = "test_analytics_history.jsonl"


def teardown_module(module):
    try:
        os.remove(os.environ.get("ANALYTICS_PERSIST_PATH", "test_analytics_history.jsonl"))
    except OSError:
        pass


def test_ingest_and_reload_persistence():
    payload = {"source": "test", "project_id": "pZ", "metrics": {"elapsed_ms": 12.3, "number_of_chunks": 3}}
    r = client.post("/ingest", json=payload)
    assert r.status_code == 200, r.text
    # Fetch history
    r2 = client.get("/ingest/history", params={"limit": 5})
    assert r2.status_code == 200
    hist = r2.json()
    assert hist["count"] >= 1
    # Force reload (will re-import module-level function)
    from app.routers import ingest as ingest_mod  # type: ignore
    ingest_mod.reload_persisted()  # should not raise
    r3 = client.get("/ingest/history", params={"limit": 5})
    assert r3.status_code == 200
