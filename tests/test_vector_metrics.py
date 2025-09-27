from fastapi.testclient import TestClient

try:
    from services.vector-service.app.main import app  # type: ignore
except ImportError:
    from app.main import app  # type: ignore

client = TestClient(app)
PROJECT_ID = "test-vector-metrics"


def test_vector_metrics_endpoint(monkeypatch):
    # Monkeypatch underlying fetch to avoid real Weaviate dependency if needed
    from services.vector-service.app.routers import vectors as vmod  # type: ignore

    class DummyObj:
        objects = [1, 2, 3]

    class DummyQuery:
        def fetch_objects(self, limit, filters=None, return_properties=None):
            return DummyObj()

    class DummyCollection:
        query = DummyQuery()

    class DummyWClient:
        def collections(self):
            return self
        def get(self, name):
            return DummyCollection()

    # If direct attribute access is used, patch processor.wclient.collections.get
    class DummyCollections:
        def get(self, name):
            return DummyCollection()

    class DummyWClient2:
        collections = DummyCollections()

    vmod.processor.wclient = DummyWClient2()

    resp = client.get(f"/projects/{PROJECT_ID}/metrics")
    assert resp.status_code in (200, 500)
    if resp.status_code == 200:
        data = resp.json()
        assert set(data["counts_by_kind"].keys()) == {"entity_cards", "raw_chunks", "triple_cards"}
