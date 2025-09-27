import asyncio
import os
import sys
from typing import List
import uuid

CURRENT_DIR = os.path.dirname(__file__)
APP_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..'))
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)

from core.enhanced_processor import EnhancedDocumentProcessor  # type: ignore
from core.structured_processor import ProcessingResult, DocumentElement, DocumentMetadata  # type: ignore


def build_processing_result(elements: List[DocumentElement]) -> ProcessingResult:
    meta = DocumentMetadata(filename="assembly.pdf", project_id="projX", correlation_id="corrZ", file_size=321)
    return ProcessingResult(
        status="success",
        document_metadata=meta,
        elements=elements,
        errors=[],
        processing_stats={"processing_time_seconds": 0.2, "element_types": {}},
    )


def test_proposal_assembly_prepared():
    proc = EnhancedDocumentProcessor()
    # Fake section enrichment structure
    section_enrichment = {
        "status": "success",
        "sections": [
            {"section_id": "sec_0", "heading": "Intro", "text_length": 120, "page_spread": [1], "elements_count": 2},
            {"section_id": "sec_1", "heading": "Body", "text_length": 560, "page_spread": [2,3], "elements_count": 5},
        ],
        "summary": {"sections_count": 2, "total_elements": 7, "approx_total_chars": 680},
    }
    # Call with auto_post disabled to avoid external dependency in unit test
    result = asyncio.run(proc.assemble_and_post_proposal(
        project_id="projX",
        correlation_id=str(uuid.uuid4()),
        section_enrichment=section_enrichment,
        auto_post=False,
    ))
    assert result["status"] == "prepared"
    proposal = result["proposal"]
    assert proposal["payload_facts"]
    assert proposal["entities"] == []
    assert proposal["relationships"] == []
