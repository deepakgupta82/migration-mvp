#!/usr/bin/env python3
"""
Test JSONL Chunking Fix
Verifies that the chunking now works with the JSONL structure produced by Excel processing
"""

import sys
import os
from pathlib import Path

# Add document service to path
sys.path.append(str(Path(__file__).parent.parent / "services" / "document-service"))

def test_chunking_fix():
    """Test the chunking fix with sample Excel-like JSONL data"""
    
    # Import after path setup
    try:
        from app.core.semantic_chunking import SemanticChunker
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure the document service is available")
        return False
    
    print("🧪 Testing JSONL Chunking Fix")
    print("=" * 50)
    
    # Simulate the JSONL data structure that comes from Excel processing
    # Based on the logs: "2 elements extracted"
    sample_jsonl_data = [
        {
            "type": "table",
            "content": "Asset ID | System Name | Operating System | Location\nSYS001 | WebServer01 | Unix | DataCenter-A\nSYS002 | DBServer01 | Unix | DataCenter-B",
            "metadata": {
                "page_number": 1,
                "table_rows": 3,
                "table_columns": 4
            },
            "element_id": "table_001"
        },
        {
            "type": "text", 
            "content": "This asset list contains all Unix systems currently deployed in the production environment. Each system has been categorized by function and location for migration planning purposes.",
            "metadata": {
                "page_number": 1,
                "font_size": 12
            },
            "element_id": "text_001"
        }
    ]
    
    # Test sample text
    sample_text = "\n\n".join([item["content"] for item in sample_jsonl_data])
    
    print(f"📋 Test Data:")
    print(f"   - JSONL Elements: {len(sample_jsonl_data)}")
    print(f"   - Combined Text Length: {len(sample_text)} chars")
    print(f"   - Sample Content Preview: {sample_text[:100]}...")
    
    try:
        # Test the chunking
        chunker = SemanticChunker(max_len=2000, overlap=200)
        chunks = chunker.chunk(sample_text, strategy="jsonl_aware", jsonl_data=sample_jsonl_data)
        
        print(f"\n✅ Chunking Result:")
        print(f"   - Chunks Created: {len(chunks)}")
        
        if len(chunks) > 0:
            print(f"   - SUCCESS: Chunking is now working!")
            
            for i, chunk in enumerate(chunks):
                print(f"\n   Chunk {i+1}:")
                print(f"     - Length: {len(chunk.content)} chars")
                print(f"     - Type: {chunk.kind}")
                print(f"     - Metadata: {chunk.metadata}")
                print(f"     - Preview: {chunk.content[:150]}...")
            
            return True
        else:
            print(f"   - ❌ STILL NO CHUNKS: The fix didn't work")
            return False
            
    except Exception as e:
        print(f"❌ Chunking failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_with_original_structure():
    """Test with the original problematic structure"""
    
    try:
        from app.core.semantic_chunking import SemanticChunker
    except ImportError:
        return False
        
    print(f"\n🔍 Testing Original Structure (with 'text' field)")
    
    # Test with the old structure that was failing
    old_structure = [
        {
            "type": "table",
            "text": "Asset data from Excel spreadsheet",  # OLD: using 'text' field
            "metadata": {"page_number": 1},
            "element_id": "elem_1"
        },
        {
            "type": "text",
            "text": "Description of Unix systems",  # OLD: using 'text' field  
            "metadata": {"page_number": 1},
            "element_id": "elem_2"
        }
    ]
    
    sample_text = "\n\n".join([item["text"] for item in old_structure])
    
    try:
        chunker = SemanticChunker()
        chunks = chunker.chunk(sample_text, strategy="jsonl_aware", jsonl_data=old_structure)
        
        print(f"   - Old Structure Result: {len(chunks)} chunks")
        if len(chunks) > 0:
            print(f"   - ✅ Backward compatibility maintained")
        else:
            print(f"   - ❌ Old structure still broken")
            
        return len(chunks) > 0
        
    except Exception as e:
        print(f"   - ❌ Error with old structure: {e}")
        return False

if __name__ == "__main__":
    print("🔧 JSONL Chunking Fix Verification")
    print("=" * 60)
    
    # Test both scenarios
    new_works = test_chunking_fix()
    old_works = test_with_original_structure()
    
    print("\n" + "=" * 60)
    print("📊 SUMMARY:")
    
    if new_works and old_works:
        print("✅ SUCCESS: Chunking fix works for both content structures!")
        print("📋 The document processing should now create chunks for entity extraction")
    elif new_works:
        print("✅ PARTIAL: New structure works, old structure may need attention")
    else:
        print("❌ FAILED: Chunking still not working correctly")
        
    print("=" * 60)