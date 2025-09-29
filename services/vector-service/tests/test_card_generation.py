import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.routers.vectors import (
    _build_entity_and_triple_cards,
    _cards_generation_signature,
    _card_pipeline_schema_version,
)
from app.core.vector_processor import VectorProcessor


def _find_entity_card(cards, entity_name: str):
    for card in cards:
        if card.get("entity") == entity_name:
            return card
    raise AssertionError(f"Entity card for {entity_name!r} not found")


def test_build_entity_cards_alignment_and_provenance():
    raw_chunks = [
        {
            "content": "Alpha is a Platform. Alpha integrates Beta solutions for enterprises.",
            "filename": "doc1.txt",
            "chunk_index": 0,
            "source": "raw_chunks",
        },
        {
            "content": "Beta collaborates with Alpha on modern architectures. Alpha delivers services.",
            "filename": "doc2.txt",
            "chunk_index": 1,
            "source": "raw_chunks",
        },
        {
            "content": "Gamma reference only for noise handling.",
            "filename": "doc3.txt",
            "chunk_index": 2,
            "source": "raw_chunks",
        },
    ]

    entity_cards, triple_cards, stats = _build_entity_and_triple_cards(
        raw_chunks,
        entity_min_occurrences=2,
        triple_pattern=r"([A-Z][A-Za-z0-9_]{2,})\s+is\s+([A-Z][A-Za-z0-9_]{2,})",
    )

    alpha_card = _find_entity_card(entity_cards, "Alpha")

    assert alpha_card["occurrences"] >= 3
    assert alpha_card["dispersion_chunks"] == 2
    assert alpha_card["alignment_density_total"] > 0.0
    assert alpha_card["alignment_avg_density"] > 0.0
    assert len(alpha_card["provenance"]) == 2
    assert all("snippet" in prov and prov["snippet"] for prov in alpha_card["provenance"])
    assert stats["entity_cards_retained"] >= 1
    assert stats["alignment_avg"] > 0.0
    assert stats["provenance_total"] >= len(alpha_card["provenance"])


def test_cards_generation_signature_includes_content_and_schema():
    base_schema = _card_pipeline_schema_version()
    args = ("project-1", 100, 2, r"([A-Z][A-Za-z0-9_]{2,})\s+is\s+([A-Z][A-Za-z0-9_]{2,})")

    sig_a = _cards_generation_signature(*args, regen_key=None, content_signature="content-a", schema_version=base_schema)
    sig_b = _cards_generation_signature(*args, regen_key=None, content_signature="content-b", schema_version=base_schema)
    assert sig_a != sig_b

    sig_c = _cards_generation_signature(*args, regen_key=None, content_signature="content-a", schema_version=f"{base_schema}-x")
    assert sig_c != sig_a


def test_extract_metadata_merges_json_payload():
    props = {
        "filename": "entity_card_Alpha.txt",
        "chunk_index": 0,
        "source": "entity_cards",
        "timestamp": "2025-09-26T12:00:00",
        "project_id": "project-123",
        "metadata_json": json.dumps({
            "schema_version": "v2",
            "card_kind": "entity",
            "entity": "Alpha",
            "weight": 12.34,
            "provenance_count": 2,
        }),
    }

    merged = VectorProcessor._extract_metadata(props)
    assert merged["schema_version"] == "v2"
    assert merged["entity"] == "Alpha"
    assert merged["filename"] == "entity_card_Alpha.txt"
    assert merged["provenance_count"] == 2
    assert "metadata_json_parse_error" not in merged
