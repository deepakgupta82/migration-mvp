import asyncio
import pytest
import uuid

from app.core.structured_processor import StructuredDocumentProcessor, Element

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
