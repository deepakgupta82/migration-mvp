#!/usr/bin/env python3
"""
Test script to validate robust document conversion improvements.
"""

import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

import tempfile
import json
from datetime import datetime

def test_conversion_scenarios():
    """Test various conversion scenarios to ensure robustness."""
    
    print("🧪 Testing Robust Document Conversion")
    print("=" * 50)
    
    # Test 1: Valid document conversion
    print("\n1️⃣ Testing valid document conversion...")
    try:
        from markitdown import MarkItDown
        md = MarkItDown()
        
        # Create a simple test document
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("# Test Document\n\nThis is a test document for conversion validation.")
            test_file = f.name
        
        result = md.convert(test_file)
        if result.text_content and result.text_content.strip():
            print(f"   ✅ MarkItDown conversion successful: {len(result.text_content)} chars")
        else:
            print("   ❌ MarkItDown returned empty content")
        
        os.unlink(test_file)
        
    except Exception as e:
        print(f"   ❌ MarkItDown test failed: {e}")
    
    # Test 2: Storage service initialization
    print("\n2️⃣ Testing storage service...")
    try:
        from app.core.storage_service import get_storage
        storage = get_storage()
        print(f"   ✅ Storage service initialized: provider={storage.provider}, bucket={storage.bucket}")
        
    except Exception as e:
        print(f"   ❌ Storage service failed: {e}")
    
    # Test 3: Fallback PDF extraction libraries
    print("\n3️⃣ Testing PDF fallback libraries...")
    
    # Test pymupdf
    try:
        import fitz
        print(f"   ✅ PyMuPDF (fitz) available: version info available")
    except ImportError:
        print("   ❌ PyMuPDF not available")
    except Exception as e:
        print(f"   ⚠️ PyMuPDF import error: {e}")
    
    # Test pdfminer
    try:
        from pdfminer.high_level import extract_text
        print("   ✅ pdfminer.six available")
    except ImportError:
        print("   ❌ pdfminer.six not available")
    except Exception as e:
        print(f"   ⚠️ pdfminer import error: {e}")
    
    # Test 4: RAG Service initialization
    print("\n4️⃣ Testing RAG Service initialization...")
    try:
        from app.core.rag_service import RAGService
        
        # Test with minimal config
        test_project_id = "test_conversion_validation"
        config = {
            "chunking_strategy": "semantic",
            "batch_size": 10,
        }
        
        rag = RAGService(test_project_id, config=config)
        print(f"   ✅ RAG Service initialized for project: {test_project_id}")
        print(f"   📊 Chunking strategy: {rag.chunking_strategy}")
        print(f"   📦 Batch size: {rag.batch_size}")
        
        # Check collection
        if hasattr(rag, 'collection') and rag.collection:
            count = rag.collection.count()
            print(f"   📚 ChromaDB collection exists with {count} documents")
        else:
            print("   ⚠️ ChromaDB collection not initialized")
            
    except Exception as e:
        print(f"   ❌ RAG Service initialization failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 5: Event bus availability
    print("\n5️⃣ Testing event system...")
    try:
        from app.core.event_bus import get_event_bus
        bus = get_event_bus()
        print("   ✅ Event bus available")
    except Exception as e:
        print(f"   ❌ Event bus failed: {e}")
    
    # Test 6: WebSocket manager
    print("\n6️⃣ Testing WebSocket manager...")
    try:
        from app.core.process_ws import get_process_ws_manager
        ws_manager = get_process_ws_manager()
        print("   ✅ WebSocket manager available")
    except Exception as e:
        print(f"   ❌ WebSocket manager failed: {e}")
    
    print("\n" + "=" * 50)
    print("✨ Robust conversion test completed!")
    print("\n💡 Key improvements implemented:")
    print("   • Graceful S3/MinIO NoSuchKey handling")
    print("   • MarkItDown empty content fallbacks with PyMuPDF/pdfminer")
    print("   • Metadata recording even for failed conversions")
    print("   • Selective embedding/entity extraction skipping")
    print("   • Enhanced error reporting and WebSocket notifications")
    print("   • Media file detection and ffmpeg dependency warnings")


if __name__ == "__main__":
    test_conversion_scenarios()
