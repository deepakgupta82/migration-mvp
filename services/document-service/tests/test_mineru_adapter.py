from typing import Any, Dict

import pytest

from app.core.mineru_adapter import MinerUAdapter


class _FakePipeline:
    def parse(self, file_path: str) -> Dict[str, Any]:  # pragma: no cover - simple helper
        assert file_path.endswith(".pdf")
        return {
            "blocks": [
                {
                    "id": "title-1",
                    "type": "Title",
                    "text": "Document Title",
                    "page_number": 1,
                    "bbox": [0, 0, 120, 40],
                    "confidence": 0.91,
                },
                {
                    "id": "tbl-1",
                    "type": "TABLE",
                    "text": "H1 H2\nR1C1 R1C2",
                    "page": {"number": 2},
                    "bbox": {"x0": 10, "y0": 20, "x1": 200, "y1": 260},
                    "order": "10",
                    "section_path": "1.2",
                    "table": {"rows": 2, "cols": 2},
                    "labels": ["analysis", "metric"],
                },
                {
                    "id": "cap-1",
                    "type": "Caption",
                    "text": "Table 1 caption",
                    "page_index": 1,
                    "target_id": "tbl-1",
                    "parent_id": "tbl-1",
                },
            ]
        }


class _FakeMinerUModule:
    class Pipeline:  # pragma: no cover - simple helper
        def __call__(self) -> _FakePipeline:
            return _FakePipeline()

        def parse(self, file_path: str) -> Dict[str, Any]:
            return _FakePipeline().parse(file_path)


@pytest.fixture
def mineru_adapter(monkeypatch):
    monkeypatch.setenv("MINERU_ENABLED", "true")
    monkeypatch.delenv("MINERU_FAKE_MODE", raising=False)
    adapter = MinerUAdapter()
    monkeypatch.setattr(MinerUAdapter, "_try_import", lambda self: _FakeMinerUModule(), raising=False)
    return adapter


def test_mineru_adapter_normalizes_pipeline_output(mineru_adapter, tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 test")

    elements = mineru_adapter.process_pdf_to_elements(str(pdf_path), pdf_path.name)

    assert elements is not None
    assert len(elements) == 3

    title = elements[0]
    assert title["type"] == "title"
    assert title["element_id"] == "title-1"
    assert title["page_number"] == 1
    assert title["confidence_score"] == pytest.approx(0.91)
    assert title["metadata"].get("raw_type") == "Title"

    table = next(el for el in elements if el["type"] == "table")
    assert table["element_id"] == "tbl-1"
    assert table["page_number"] == 2
    assert table["coordinates"] == {"x1": 10.0, "y1": 20.0, "x2": 200.0, "y2": 260.0}
    assert table["metadata"].get("table_rows") == 2
    assert table["metadata"].get("table_cols") == 2
    assert table["metadata"].get("section_path") == [1, 2]
    assert "table" in table["metadata"]  # sanitized table info retained
    assert "table" in table["semantic_tags"]

    caption = next(el for el in elements if el["type"] == "caption")
    assert caption["element_id"] == "cap-1"
    assert caption["page_number"] == 2
    assert caption["metadata"].get("caption_for") == "tbl-1"
    assert caption["parent_id"] == "tbl-1"

