import math
from common.ranking import compute_rrf_fusion, apply_centrality_boost


def test_rrf_basic_ordering():
    # Two sources with different ranks for the same ids
    s1 = [
        {"id": "A", "score": 0.9, "source": "entity_cards"},
        {"id": "B", "score": 0.8, "source": "entity_cards"},
    ]
    s2 = [
        {"id": "B", "score": 0.95, "source": "raw_chunks"},
        {"id": "A", "score": 0.6, "source": "raw_chunks"},
    ]
    fused = compute_rrf_fusion([s1, s2])
    ids = [r["id"] for r in fused]
    assert ids[:2] == ["A", "B"] or ids[:2] == ["B", "A"]
    # With higher weight on raw_chunks, expect B (rank1 in s2) to lead
    fused_w = compute_rrf_fusion([s1, s2], weights={"raw_chunks": 2.0, "entity_cards": 1.0})
    ids_w = [r["id"] for r in fused_w]
    assert ids_w[0] == "B"


def test_rrf_ignores_negative_weights():
    s1 = [
        {"id": "X", "score": 0.9, "source": "entity_cards"},
        {"id": "Y", "score": 0.8, "source": "entity_cards"},
    ]
    s2 = [
        {"id": "Y", "score": 0.95, "source": "raw_chunks"},
    ]
    fused = compute_rrf_fusion([s1, s2], weights={"raw_chunks": -5.0})
    # Negative weight is clipped to zero; only entity_cards contributes
    ids = [r["id"] for r in fused]
    assert ids[0] == "X"


def test_centrality_boost_normalized_and_scale():
    items = [
        {"id": "A", "fused_score": 1.0},
        {"id": "B", "fused_score": 1.0},
    ]
    deg = {"A": 10.0, "B": 5.0}
    # normalized: A gets boost 1.0 * (10/10)*0.1 = 0.1; B gets 1.0 * (5/10)*0.1 = 0.05
    apply_centrality_boost(items, deg, scale=0.1, normalized=True)
    a = next(i for i in items if i["id"] == "A")
    b = next(i for i in items if i["id"] == "B")
    assert math.isclose(a["fused_score"], 1.1, rel_tol=1e-6)
    assert math.isclose(b["fused_score"], 1.05, rel_tol=1e-6)
    # Non-normalized scale=0.01 should add raw*0.01
    items2 = [
        {"id": "A", "fused_score": 0.0},
        {"id": "B", "fused_score": 0.0},
    ]
    apply_centrality_boost(items2, deg, scale=0.01, normalized=False)
    a2 = next(i for i in items2 if i["id"] == "A")
    b2 = next(i for i in items2 if i["id"] == "B")
    assert math.isclose(a2["fused_score"], 0.1, rel_tol=1e-6)
    assert math.isclose(b2["fused_score"], 0.05, rel_tol=1e-6)
