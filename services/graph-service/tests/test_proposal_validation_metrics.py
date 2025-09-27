import os
import pytest
from httpx import AsyncClient
from fastapi import FastAPI

# Assuming the FastAPI app is created in main.py within graph-service
# and includes the router under / (adjust import if different)

pytestmark = pytest.mark.asyncio

# Minimal app import / construction
try:
    from app.main import app  # type: ignore
except Exception:
    # Fallback: create dummy app if direct import path differs
    from fastapi import FastAPI
    app = FastAPI()

REQUIRED_KEYS = {
    "entity_count",
    "relationship_count",
    "duplicate_entity_names",
    "duplicate_entity_ratio",
    "avg_entity_name_length",
    "p95_entity_name_length",
    "entity_type_counts",
    "relationship_type_counts",
    "generated_at",
}

@pytest.mark.asyncio
async def test_validation_metrics_flow(monkeypatch):
    # Force redis store to simplify (avoid needing a real Postgres); set PVC_STORE to redis
    monkeypatch.setenv("PVC_STORE", "redis")

    project_id = "test-project-metrics"

    # Create a proposal
    proposal_payload = {
        "project_id": project_id,
        "entities": [
            {"name": "ServerA", "type": "Server"},
            {"name": "ServerA", "type": "Server"},  # duplicate name
            {"name": "App1", "type": "Application"},
            {"name": "", "type": "Application"},  # empty name for empty_name_entities
        ],
        "relationships": [
            {"type": "HOSTS", "source": "ServerA", "target": "App1"},
            {"type": "CONNECTS_TO", "source": "App1", "target": "DbX"},
            {"type": "USES", "source": "App1", "target": "Redis"},
            {"type": "BROKEN", "source": "App1"},  # missing target
        ],
        "facts": [],
        "source_documents": []
    }

    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.post(f"/projects/{project_id}/proposals", json=proposal_payload)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        proposal_id = data.get("proposal_id") or data.get("id")
        assert proposal_id

        # Validate
        vresp = await client.post(f"/proposals/{proposal_id}/validate")
        assert vresp.status_code == 200, vresp.text
        vdata = vresp.json()
        metrics = vdata.get("validation_metrics") or {}
        missing = REQUIRED_KEYS - set(metrics.keys())
        assert not missing, f"Missing expected keys: {missing} in metrics {metrics}" 
        assert metrics["entity_count"] == 4
        assert metrics["relationship_count"] == 4
        assert metrics["duplicate_entity_names"] >= 1
        assert metrics["duplicate_entity_ratio"] > 0.0
        assert metrics["relationships_missing_endpoints"] >= 1

        # Summary endpoint
        sresp = await client.get(f"/projects/{project_id}/proposals/validation-summary")
        assert sresp.status_code == 200, sresp.text
        sdata = sresp.json()
        assert sdata.get("proposal_count") >= 1
        agg = sdata.get("aggregated_metrics") or {}
        assert "entity_count" in agg
        assert agg.get("proposal_count") is None  # proposal_count should be top-level, not inside aggregated

