import json
from fastapi.testclient import TestClient

try:
    from services.document-service.app.main import app  # type: ignore
except ImportError:
    from app.main import app  # type: ignore

client = TestClient(app)

PROJECT_ID = "test-incremental-fusion"


def test_incremental_fusion_no_filters_feature_flag_disabled(monkeypatch):
    # Force feature disabled
    monkeypatch.setenv("FUSION_ENABLED", "false")
    resp = client.post(f"/fusion/projects/{PROJECT_ID}/run-incremental", json={})
    assert resp.status_code == 403


def test_incremental_fusion_no_matching(monkeypatch):
    # Enable fusion
    monkeypatch.setenv("FUSION_ENABLED", "true")

    # Mock orchestrator methods to control cluster/proposal data
    from services.document-service.app.core import fusion_orchestrator as fmod  # type: ignore

    async def mock_fetch_clusters(project_id, threshold, max_cards):
        return {"clusters": [
            {"cluster_id": "c1", "members": [{"entity_id": "e1", "content_preview": "Alpha"}]},
            {"cluster_id": "c2", "members": [{"entity_id": "e2", "content_preview": "Beta"}]},
        ]}

    async def mock_fetch_proposals(project_id):
        return []  # triggers no_entities_in_proposals path

    monkeypatch.setattr(fmod.FusionOrchestrator, "_fetch_clusters", mock_fetch_clusters, raising=True)
    monkeypatch.setattr(fmod.FusionOrchestrator, "_fetch_proposals", mock_fetch_proposals, raising=True)

    body = {"cluster_ids": ["nonexistent"], "similarity_threshold": 0.9}
    resp = client.post(f"/fusion/projects/{PROJECT_ID}/run-incremental", json=body)
    # Because filter excludes all clusters, expect no_matching_clusters OR earlier short-circuit of no_entities
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("no_matching_clusters", "no_entities_in_proposals")
