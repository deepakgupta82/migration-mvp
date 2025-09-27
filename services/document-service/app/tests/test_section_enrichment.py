import asyncio
import os
import sys
from typing import List

# Ensure parent app directory is on path when running tests directly
CURRENT_DIR = os.path.dirname(__file__)
APP_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..'))
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)

from core.enhanced_processor import EnhancedDocumentProcessor  # type: ignore
from core.structured_processor import ProcessingResult, DocumentElement, DocumentMetadata  # type: ignore


def build_processing_result(elements: List[DocumentElement]) -> ProcessingResult:
    meta = DocumentMetadata(filename="testdoc.pdf", project_id="proj123", correlation_id="corr1", file_size=123)
    return ProcessingResult(
        status="success",
        document_metadata=meta,
        elements=elements,
        errors=[],
        processing_stats={"processing_time_seconds": 0.1, "element_types": {}},
    )


def test_section_enrichment_basic():
    proc = EnhancedDocumentProcessor()
    # Build synthetic elements with headers
    elements = [
        DocumentElement(type="title", text="Overview", page_number=1, element_id="e1"),
        DocumentElement(type="paragraph", text="This is an intro.", page_number=1, element_id="e2"),
        DocumentElement(type="header", text="Details", page_number=2, element_id="e3"),
        DocumentElement(type="paragraph", text="More details here.", page_number=2, element_id="e4"),
    ]
    pr = build_processing_result(elements)

    async def run():
        return await proc._enrich_sections(
            project_id="proj123",
            processing_result=pr,
            structured_filename="testdoc_structured.jsonl",
            layout_filename=None,
            correlation_id="corr1",
        )
    result = asyncio.run(run())
    assert result["status"] == "success"
    assert result["summary"]["sections_count"] >= 2
    assert any(s.get("heading") == "Overview" for s in result["sections"])
