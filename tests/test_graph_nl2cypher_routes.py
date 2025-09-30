import os
import sys
from typing import Any, Dict, List

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Ensure the graph-service package root is on sys.path so we can import app.routers.graphs
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
GRAPH_SERVICE_ROOT = os.path.join(ROOT, 'services', 'graph-service')
# Add repo root first so 'common' resolves as top-level package
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if GRAPH_SERVICE_ROOT not in sys.path:
    sys.path.insert(0, GRAPH_SERVICE_ROOT)

from app.routers import graphs  # type: ignore


class FakeRedis:
    def __init__(self):
        self.store: Dict[str, str] = {}

    async def incr(self, key: str):
        self.store[key] = str(int(self.store.get(key, "0")) + 1)

    async def get(self, key: str):
        v = self.store.get(key)
        # Mimic aioredis returning bytes sometimes
        return v.encode() if isinstance(v, str) else v

    async def set(self, key: str, value: str):
        self.store[key] = value

    async def lrange(self, key: str, start: int, end: int):
        return []


class FakeResult:
    def __init__(self, keys: List[str], rows: List[Dict[str, Any]]):
        self._keys = keys
        self._rows = rows

    def keys(self):
        return self._keys

    def __aiter__(self):
        async def gen():
            for r in self._rows:
                yield r
        return gen()

    async def single(self):
        # For tests that call .single(); return first-like
        if self._rows:
            class Rec(dict):
                def get(self, k, d=None):
                    return super().get(k, d)
            return Rec(self._rows[0])
        return None


class FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def run(self, cypher: str, **params):
        # Accept EXPLAIN validation silently
        if cypher.strip().upper().startswith("EXPLAIN "):
            return FakeResult([], [])
        # Return trivial result for execution
        if "RETURN 1 as a" in cypher:
            return FakeResult(["a"], [{"a": 1}])
        # Generic empty
        return FakeResult([], [])


class FakeNeo4jDriver:
    def session(self):
        return FakeSession()


class FakeHTTP:
    # not used in these route tests
    async def post(self, url: str, json: Dict[str, Any], headers: Dict[str, str]):
        class Resp:
            status_code = 200
            def json(self):
                return {"items": []}
        return Resp()


class FakeGraphProcessor:
    def __init__(self):
        self.neo4j_driver = FakeNeo4jDriver()
        self.redis_client = FakeRedis()
        self.http = FakeHTTP()


def make_test_app():
    app = FastAPI()

    # Inject fake graph processor via middleware to satisfy Depends(get_graph_processor)
    gp = FakeGraphProcessor()

    @app.middleware("http")
    async def add_gp(request, call_next):
        request.state.graph_processor = gp
        return await call_next(request)

    # Include router without prefix to use direct paths e.g. /projects/{id}/...
    app.include_router(graphs.router)
    return app


@pytest.fixture(scope="module")
def client():
    app = make_test_app()
    with TestClient(app) as c:
        yield c


def test_nl2cypher_build_success(client: TestClient):
    body = {"nl": "list servers connecting to databases", "limit": 10}
    r = client.post("/projects/test-proj/query/nl2cypher", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["project_id"] == "test-proj"
    cy = data.get("cypher", "")
    assert "Project {id:$pid}" in cy
    assert "LIMIT $lim" in cy


def test_nl2cypher_run_rejects_write(client: TestClient):
    # SET should be blocked by sanitizer
    r = client.post("/projects/test-proj/query/run", json={"cypher": "MATCH (n) SET n.x=1", "limit": 5})
    assert r.status_code == 400
    assert "Forbidden" in r.text or "forbidden" in r.text.lower()


def test_nl2cypher_run_executes_safe_query(client: TestClient):
    r = client.post("/projects/test-proj/query/run", json={"cypher": "MATCH (p:Project {id:$pid}) RETURN 1 as a", "limit": 5})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["project_id"] == "test-proj"
    assert data["columns"] == ["a"]
    assert data["rows"] == [{"a": 1}]
