#!/usr/bin/env python3
"""
Simple MarkItDown test with any file you specify
Just change the TEST_FILE_PATH below to test any document
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Add backend to Python path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

# 🎯 CHANGE THIS PATH TO TEST ANY FILE
TEST_FILE_PATH = r"C:\Users\deepakgupta13\OneDrive - Nagarro\Cloud Practice\migration_platform_2\test_document.txt"  # Change this to your file

def test_specific_file():
    """Test MarkItDown conversion on a specific file"""
    
    print("🔍 Testing Specific File with MarkItDown Debug")
    print("=" * 50)
    
    # Check if file exists
    if not os.path.exists(TEST_FILE_PATH):
        print(f"❌ File not found: {TEST_FILE_PATH}")
        print("\n💡 To test a file:")
        print("1. Edit this script and change TEST_FILE_PATH to your file")
        print("2. Or place a file in the project root and update the path")
        return
    
    file_size = os.path.getsize(TEST_FILE_PATH)
    print(f"📄 Testing file: {os.path.basename(TEST_FILE_PATH)}")
    print(f"📄 File size: {file_size} bytes")
    print(f"📄 File path: {TEST_FILE_PATH}")
    
    try:
        # Import MarkItDown directly
        from markitdown import MarkItDown
        
        print("\n🔄 Running MarkItDown conversion...")
        
        md = MarkItDown()
        result = md.convert(TEST_FILE_PATH)
        content = result.text_content
        
        print(f"✅ MarkItDown conversion completed")
        print(f"📊 Content length: {len(content or '')} characters")
        
        # Save debug file
        debug_dir = "markitdown_debug"
        os.makedirs(debug_dir, exist_ok=True)
        
        filename = os.path.basename(TEST_FILE_PATH)
        safe_filename = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
        debug_file = os.path.join(debug_dir, f"DIRECT_TEST_{safe_filename}.md")
        
        with open(debug_file, 'w', encoding='utf-8') as f:
            f.write(f"# DIRECT MARKITDOWN TEST: {filename}\n")
            f.write(f"Original file: {TEST_FILE_PATH}\n")
            f.write(f"File size: {file_size} bytes\n")
            f.write(f"Content length: {len(content or '')} characters\n")
            f.write("=" * 50 + "\n")
            if content:
                f.write(content)
            else:
                f.write("[EMPTY CONTENT - MARKITDOWN FAILED]")
        
        print(f"💾 Saved debug file: {debug_file}")
        
        # Show preview
        if content and content.strip():
            print(f"\n✅ SUCCESS! MarkItDown extracted content:")
            print("-" * 30)
            print(content[:500] + ("..." if len(content) > 500 else ""))
            print("-" * 30)
            print(f"✅ This should work with entity extraction!")
        else:
            print(f"\n❌ FAILURE! MarkItDown returned empty content")
            print("🔍 This explains the 0 entities issue!")
            print("💡 Possible causes:")
            print("  - File is corrupted or unreadable")
            print("  - Unsupported file format")
            print("  - MarkItDown installation issue")
            print("  - Missing dependencies (e.g., for PDFs)")
        
        # Test entity extraction if content exists
        if content and content.strip():
            print(f"\n🧠 Testing entity extraction on this content...")
            try:
                from app.core.entity_extraction_agent import EntityExtractionAgent
                from langchain_google_genai import ChatGoogleGenerativeAI
                
                api_key = os.environ.get('GOOGLE_API_KEY')
                llm = ChatGoogleGenerativeAI(
                    model="gemini-2.5-flash",
                    google_api_key=api_key,
                    temperature=0.1
                )
                
                agent = EntityExtractionAgent(llm=llm)
                
                # Use first 2000 chars to avoid token limits
                test_content = content[:2000]
                result = agent.extract_entities_and_relationships(test_content)
                
                entities = result.get('entities', [])
                relationships = result.get('relationships', [])
                
                print(f"📊 Entity extraction result:")
                print(f"  Entities: {len(entities)}")
                print(f"  Relationships: {len(relationships)}")
                
                if entities:
                    print(f"✅ Entity extraction WORKS with this content!")
                    for i, entity in enumerate(entities[:3], 1):
                        print(f"  {i}. {entity}")
                else:
                    print(f"❌ Entity extraction still returns 0 entities")
                    print(f"🔍 Issue is not in MarkItDown conversion")
                
            except Exception as entity_error:
                print(f"❌ Entity extraction test failed: {entity_error}")
        
    except Exception as e:
        print(f"❌ MarkItDown test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🚀 Direct File MarkItDown Test")
    print("🎯 Testing specific file conversion")
    print("=" * 50)
    
    test_specific_file()
    
    print(f"\n🎯 Results:")
    print("- Check markitdown_debug/ folder for the debug file")
    print("- If MarkItDown content is empty, that's your 0 entities issue!")
    print("- If MarkItDown content is good but entities = 0, dig deeper")
