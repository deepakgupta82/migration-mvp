#!/usr/bin/env python3
"""
Test Enhanced JSONL-Aware Chunking Integration

This script tests the enhanced chunking functionality that was implemented
to address the user's request for better JSONL format utilization.
"""

import asyncio
import sys
import os
import json
import logging
from pathlib import Path

# Add the document service to the path
sys.path.append(str(Path(__file__).parent / "services" / "document-service"))

try:
    from app.core.semantic_chunking import SemanticChunker, chunk_text
    from app.core.enhanced_processor import EnhancedDocumentProcessor
    from app.core.structured_processor import StructuredDocumentProcessor, DocumentElement, DocumentMetadata, ProcessingResult
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running this from the project root directory")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_sample_jsonl_data():
    """Create sample JSONL data for testing"""
    return [
        {
            "type": "title",
            "content": "Introduction to Cloud Migration",
            "metadata": {"font_size": 18, "bold": True},
            "page_number": 1,
            "element_id": "elem_001",
            "hierarchy_level": 1,
            "semantic_tags": ["title", "heading"],
            "confidence_score": 0.95
        },
        {
            "type": "narrative_text",
            "content": "Cloud migration has become a critical strategy for organizations looking to modernize their infrastructure. This comprehensive guide will walk you through the essential steps, best practices, and considerations for a successful cloud migration journey.",
            "metadata": {"paragraph_id": "p1"},
            "page_number": 1,
            "element_id": "elem_002",
            "hierarchy_level": 2,
            "semantic_tags": ["introduction", "long_text"],
            "confidence_score": 0.88
        },
        {
            "type": "title",
            "content": "Planning Your Migration Strategy",
            "metadata": {"font_size": 16, "bold": True},
            "page_number": 1,
            "element_id": "elem_003",
            "hierarchy_level": 1,
            "semantic_tags": ["title", "heading"],
            "confidence_score": 0.92
        },
        {
            "type": "list_item",
            "content": "Assess current infrastructure and workloads",
            "metadata": {"list_type": "bullet", "list_index": 1},
            "page_number": 1,
            "element_id": "elem_004",
            "hierarchy_level": 3,
            "semantic_tags": ["list_item", "action"],
            "confidence_score": 0.85
        },
        {
            "type": "list_item",
            "content": "Define migration goals and success criteria",
            "metadata": {"list_type": "bullet", "list_index": 2},
            "page_number": 1,
            "element_id": "elem_005",
            "hierarchy_level": 3,
            "semantic_tags": ["list_item", "action"],
            "confidence_score": 0.85
        },
        {
            "type": "narrative_text",
            "content": "Each migration strategy comes with its own set of advantages and challenges. The rehost approach, often called 'lift and shift,' provides the fastest migration path but may not fully leverage cloud-native benefits. Replatform strategies offer a middle ground, allowing for some optimization while maintaining familiar architectures.",
            "metadata": {"paragraph_id": "p2"},
            "page_number": 2,
            "element_id": "elem_006",
            "hierarchy_level": 2,
            "semantic_tags": ["detailed_explanation", "long_text"],
            "confidence_score": 0.90
        }
    ]

def test_basic_semantic_chunking():
    """Test basic semantic chunking functionality"""
    logger.info("Testing basic semantic chunking...")
    
    sample_text = """
    Introduction to Cloud Migration
    
    Cloud migration has become a critical strategy for organizations looking to modernize their infrastructure. This comprehensive guide will walk you through the essential steps, best practices, and considerations for a successful cloud migration journey.
    
    Planning Your Migration Strategy
    
    Before embarking on your cloud migration journey, it's essential to develop a comprehensive strategy that aligns with your business objectives.
    """
    
    try:
        chunks = chunk_text(sample_text, strategy="semantic")
        logger.info(f"✅ Basic semantic chunking successful: {len(chunks)} chunks generated")
        
        for i, chunk in enumerate(chunks):
            logger.info(f"   Chunk {i+1}: {len(chunk)} characters")
            logger.info(f"   Preview: {chunk[:100]}...")
        
        return True
    except Exception as e:
        logger.error(f"❌ Basic semantic chunking failed: {e}")
        return False

def test_jsonl_aware_chunking():
    """Test JSONL-aware chunking functionality"""
    logger.info("Testing JSONL-aware chunking...")
    
    # Create sample text from JSONL data
    jsonl_data = create_sample_jsonl_data()
    sample_text = "\n\n".join([item["content"] for item in jsonl_data])
    
    try:
        # Test JSONL-aware chunking
        chunks = chunk_text(sample_text, strategy="jsonl_aware", jsonl_data=jsonl_data)
        logger.info(f"✅ JSONL-aware chunking successful: {len(chunks)} chunks generated")
        
        for i, chunk in enumerate(chunks):
            logger.info(f"   Chunk {i+1}: {len(chunk)} characters")
            logger.info(f"   Preview: {chunk[:100]}...")
        
        # Test with SemanticChunker directly
        chunker = SemanticChunker()
        enhanced_chunks = chunker.chunk(sample_text, strategy="jsonl_aware", jsonl_data=jsonl_data)
        logger.info(f"✅ Direct SemanticChunker JSONL-aware: {len(enhanced_chunks)} chunks with metadata")
        
        for i, chunk in enumerate(enhanced_chunks):
            logger.info(f"   Enhanced Chunk {i+1}: {len(chunk.content)} chars, metadata: {chunk.metadata}")
        
        return True
    except Exception as e:
        logger.error(f"❌ JSONL-aware chunking failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def test_enhanced_processor_integration():
    """Test enhanced processor integration with chunking"""
    logger.info("Testing enhanced processor integration...")
    
    try:
        processor = EnhancedDocumentProcessor()
        
        # Create mock processing result
        from datetime import datetime
        
        # Create sample elements
        jsonl_data = create_sample_jsonl_data()
        elements = []
        
        for item in jsonl_data:
            element = DocumentElement(
                element_id=item["element_id"],
                type=item["type"],
                text=item["content"],
                page_number=item["page_number"],
                coordinates=None,
                parent_id=None,
                metadata=item["metadata"],
                hierarchy_level=item["hierarchy_level"],
                semantic_tags=item["semantic_tags"],
                confidence_score=item["confidence_score"]
            )
            elements.append(element)
        
        # Create mock document metadata
        doc_metadata = DocumentMetadata(
            filename="test_document.pdf",
            file_path="/tmp/test_document.pdf",
            file_size=1024,
            file_type=".pdf",
            mime_type="application/pdf",
            processing_timestamp=datetime.now(),
            project_id="test-project-123",
            correlation_id="test-correlation-456"
        )
        
        # Create processing result
        processing_result = ProcessingResult(
            document_metadata=doc_metadata,
            elements=elements,
            processing_stats={
                "processing_time_seconds": 2.5,
                "total_elements": len(elements),
                "element_types": {"title": 2, "narrative_text": 2, "list_item": 2}
            },
            status="success",
            errors=[],
            warnings=[]
        )
        
        # Test enhanced chunking generation
        enhanced_chunks = await processor.generate_enhanced_chunks(
            processing_result, 
            chunking_strategy="jsonl_aware"
        )
        
        logger.info(f"✅ Enhanced processor integration successful: {len(enhanced_chunks)} enhanced chunks")
        
        for i, chunk in enumerate(enhanced_chunks):
            logger.info(f"   Enhanced Chunk {i+1}:")
            logger.info(f"     ID: {chunk['chunk_id']}")
            logger.info(f"     Content length: {chunk['chunk_length']}")
            logger.info(f"     Strategy: {chunk['metadata']['chunking_strategy']}")
            logger.info(f"     Elements used: {chunk['metadata']['structured_elements_used']}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Enhanced processor integration failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def main():
    """Run all tests"""
    logger.info("🚀 Starting Enhanced JSONL-Aware Chunking Integration Tests")
    logger.info("=" * 70)
    
    tests = [
        ("Basic Semantic Chunking", test_basic_semantic_chunking()),
        ("JSONL-Aware Chunking", test_jsonl_aware_chunking()),
        ("Enhanced Processor Integration", test_enhanced_processor_integration())
    ]
    
    results = []
    for test_name, test_func in tests:
        logger.info(f"\n📝 Running: {test_name}")
        logger.info("-" * 50)
        
        if asyncio.iscoroutine(test_func):
            result = await test_func
        else:
            result = test_func
        
        results.append((test_name, result))
        
        if result:
            logger.info(f"✅ {test_name}: PASSED")
        else:
            logger.error(f"❌ {test_name}: FAILED")
    
    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("📊 TEST SUMMARY")
    logger.info("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"{test_name}: {status}")
    
    logger.info(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed! Enhanced JSONL-aware chunking is working correctly.")
        return True
    else:
        logger.error(f"⚠️  {total - passed} test(s) failed. Please check the implementation.")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
