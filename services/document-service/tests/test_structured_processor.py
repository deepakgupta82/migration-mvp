import asyncio
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.structured_processor import StructuredDocumentProcessor
from app.core.enhanced_processor import EnhancedDocumentProcessor
# Import Element safely to handle cases where unstructured is not available
try:
    from unstructured.documents.elements import Element as UnstructuredElement
    Element = UnstructuredElement
except ImportError:
    # Fallback to the internal Element definition
    from app.core.structured_processor import Element

class FakeElement(Element):
    def __init__(self, text, category='Text', metadata=None):
        super().__init__(text=text, category=category, metadata=metadata)

@pytest.mark.asyncio
async def test_post_process_elements_basic():
    proc = StructuredDocumentProcessor()

    # Create fake unstructured elements
    elems = [
        FakeElement('Title: Example', category='Title', metadata={'category_depth': 1, 'page_number': 1}),
        FakeElement('This is a paragraph.', category='Text', metadata={'page_number': 1}),
        FakeElement('- list item 1', category='ListItem', metadata={'page_number': 2}),
    ]

    # _post_process_elements is synchronous
    processed = proc._post_process_elements(elems)

    assert isinstance(processed, list)
    assert len(processed) == 3
    # Check first element mapped type
    assert processed[0].type in ('title', 'header', 'title')
    assert 'Example' in processed[0].text
    # Ensure list item cleaned bullets
    assert processed[2].text.startswith('-') or processed[2].type == 'listitem'


@pytest.mark.asyncio
async def test_websocket_messaging_enhanced_processor():
    """Test that WebSocket messages are sent with proper format and analysis_id"""

    # Mock the WebSocket client
    mock_ws_client = AsyncMock()
    mock_ws_client.send_document_processing_update = AsyncMock()

    # Mock the service client
    mock_service_client = AsyncMock()

    with patch('app.core.enhanced_processor.get_websocket_client', return_value=mock_ws_client), \
         patch('app.core.enhanced_processor.get_service_client', return_value=mock_service_client), \
         patch('app.core.enhanced_processor.EnhancedDocumentProcessor._integrate_vector_service', return_value={"status": "success"}), \
         patch('app.core.enhanced_processor.EnhancedDocumentProcessor._integrate_graph_service', return_value={"status": "success"}), \
         patch('app.core.enhanced_processor.EnhancedDocumentProcessor._save_structured_output', return_value={"status": "success"}), \
         patch('app.core.enhanced_processor.EnhancedDocumentProcessor._notify_stats_service'), \
         patch('app.core.enhanced_processor.EnhancedDocumentProcessor._store_analysis_result'):

        # Create processor instance
        processor = EnhancedDocumentProcessor()

        # Mock processing result
        mock_processing_result = MagicMock()
        mock_processing_result.status = "success"
        mock_processing_result.elements = [MagicMock()]
        mock_processing_result.processing_stats = {"processing_time_seconds": 10.5}
        mock_processing_result.to_dict.return_value = {"test": "data"}

        # Mock structured processor
        processor.structured_processor.process_document = AsyncMock(return_value=mock_processing_result)

        # Test the completion message
        await processor._send_websocket_notification(
            "test-project-id",
            "test-correlation-id",
            "document_processing_completed",
            {
                "filename": "test.pdf",
                "structured_output": "test_structured.jsonl",
                "elements_extracted": 5,
                "vector_integration": {"status": "success"},
                "graph_integration": {"status": "success"},
                "processing_time": 10.5,
                "progress": 100,
                "message": "Document processing completed successfully for test.pdf",
                "details": "Extracted 5 elements, analysis ready for viewing",
                "analysis_status": "analysis_complete"
            }
        )

        # Verify WebSocket message was sent with correct parameters
        mock_ws_client.send_document_processing_update.assert_called_once()
        call_args = mock_ws_client.send_document_processing_update.call_args

        # Check that the call was made with the right parameters
        assert call_args[0][0] == "test-project-id"  # project_id
        assert call_args[0][1] == "test.pdf"  # document_id
        assert call_args[0][2] == "completed"  # status
        assert "analysis_id" in call_args[1]  # analysis_id should be in kwargs
        assert "analysis_status" in call_args[1]  # analysis_status should be in kwargs
        assert call_args[1]["analysis_status"] == "analysis_complete"
