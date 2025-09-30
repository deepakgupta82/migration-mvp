import os
import pytest

import json
import urllib.request


@pytest.mark.skipif(os.getenv("RUN_GRAPH_IT", "0") != "1", reason="Integration test disabled")
def test_materialize_refers_to_smoke():
    host = os.getenv("GRAPH_HOST", "http://localhost:8006")
    project = os.getenv("GRAPH_TEST_PROJECT", "")
    if not project:
        pytest.skip("GRAPH_TEST_PROJECT not set")
    token = os.getenv("AUTH_TOKEN", "service-backend-token")
    url = f"{host}/api/graphs/projects/{project}/maintenance/materialize-refers-to?min_score=0.55&max_candidates=3&preferred_kind=entity_cards&use_hybrid=true"
    req = urllib.request.Request(url=url, method='POST', headers={'Authorization': f'Bearer {token}'})
    with urllib.request.urlopen(req, timeout=60) as resp:
        assert resp.status == 200
        data = json.loads(resp.read())
        assert 'project_id' in data
        assert 'created_relationships' in data