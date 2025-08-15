#!/usr/bin/env python3
"""
Test MarkItDown conversion with debug file saving
This will process a real document and save the converted content for inspection
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

def test_markitdown_debug():
    """Test MarkItDown conversion and save debug files"""
    
    print("🔍 Testing MarkItDown Conversion with Debug File Saving")
    print("=" * 60)
    
    try:
        from app.core.rag_service import RAGService
        from langchain_google_genai import ChatGoogleGenerativeAI
        
        # Create working LLM
        api_key = os.environ.get('GOOGLE_API_KEY')
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=api_key,
            temperature=0.1
        )
        
        print("✅ Created Gemini LLM")
        
        # Create RAG service
        project_id = "151859dd-98a1-47f7-b980-31759e29c70f"
        rag_service = RAGService(project_id=project_id, llm=llm)
        
        print(f"✅ Created RAG service for project: {project_id}")
        
        # Use the specific test file you provided
        test_file = r"C:\Users\deepakgupta13\OneDrive - Nagarro\Cloud Practice\migration_platform_2\NBQ Assessment documents\NBQ- Documents Received\D11_IT - Organization Structure-2025-NRCApproved.pdf"
        
        if not os.path.exists(test_file):
            print(f"❌ Test file not found: {test_file}")
            print("Please check the file path and try again.")
            return
        
        file_size = os.path.getsize(test_file)
        print(f"✅ Found test file: {os.path.basename(test_file)} ({file_size} bytes)")
        
        print(f"\n📄 Processing file: {os.path.basename(test_file)}")
        
        # Check if markitdown_debug directory exists or will be created
        debug_dir = os.path.join(os.getcwd(), "markitdown_debug")
        print(f"📁 Debug files will be saved to: {debug_dir}")
        
        # Process the file through RAG service (this will trigger MarkItDown conversion)
        print("\n🔄 Processing file through RAG service...")
        print("🔍 This will trigger our enhanced MarkItDown debug saving...")
        
        try:
            # Use the add_file method to process the document
            result = rag_service.add_file(test_file, reprocess=True)
            
            print(f"✅ File processing completed!")
            print(f"📊 Result: {result}")
            
        except Exception as processing_error:
            print(f"❌ File processing failed: {processing_error}")
            import traceback
            traceback.print_exc()
        
        # Check if debug files were created
        print(f"\n🔍 Checking for debug files in {debug_dir}...")
        
        if os.path.exists(debug_dir):
            debug_files = os.listdir(debug_dir)
            if debug_files:
                print(f"✅ Found {len(debug_files)} debug files:")
                for file in debug_files:
                    file_path = os.path.join(debug_dir, file)
                    file_size = os.path.getsize(file_path)
                    print(f"  📄 {file} ({file_size} bytes)")
                
                # Show content of the first debug file
                if debug_files:
                    first_file = os.path.join(debug_dir, debug_files[0])
                    print(f"\n📖 Content of {debug_files[0]}:")
                    print("-" * 50)
                    try:
                        with open(first_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                            print(content[:1000] + ("..." if len(content) > 1000 else ""))
                    except Exception as read_error:
                        print(f"❌ Could not read file: {read_error}")
                    print("-" * 50)
            else:
                print("❌ Debug directory exists but no files found")
        else:
            print("❌ Debug directory not created - check for errors in processing")
        
        # Clean up test file if we created it (skip for our specific test file)
        # No cleanup needed for the PDF test file
        print(f"✅ Test completed with file: {os.path.basename(test_file)}")
            
    except Exception as e:
        print(f"❌ Error in MarkItDown debug test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🚀 MarkItDown Conversion Debug Test")
    print("🎯 Testing document conversion with debug file saving")
    print("=" * 60)
    
    if not os.environ.get('GOOGLE_API_KEY'):
        print("❌ GOOGLE_API_KEY not found")
        sys.exit(1)
        
    print("✅ Environment check passed")
    
    test_markitdown_debug()
    
    print(f"\n🎯 Next Steps:")
    print("1. Check the markitdown_debug/ folder for generated files")
    print("2. Inspect the converted content to see if it's empty/corrupted")
    print("3. Compare with the original document content")
    print("4. This will reveal if MarkItDown is the source of 0 entities issue!")
