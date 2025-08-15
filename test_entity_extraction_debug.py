#!/usr/bin/env python3
"""
Direct entity extraction test script for debugging Gemini LLM issues
Project: 151859dd-98a1-47f7-b980-31759e29c70f
"""

import sys
import os
import asyncio
from pathlib import Path

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Add backend to Python path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

async def test_entity_extraction():
    """Test entity extraction with direct LLM configuration"""
    
    print("🔍 Starting Entity Extraction Debug Test")
    print("=" * 50)
    
    # Test file path
    test_file = r"C:\Users\deepakgupta13\OneDrive - Nagarro\Cloud Practice\migration_platform_2\minio_data\agentimigrate\projects\151859dd-98a1-47f7-b980-31759e29c70f\uploads\parsed\D21_Middleware_Integration_Diagram.md"
    
    if not os.path.exists(test_file):
        print(f"❌ Test file not found: {test_file}")
        return
    
    # Read the content
    with open(test_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print(f"📄 Loaded test content: {len(content)} characters")
    print(f"📄 Content preview (first 200 chars):\n{content[:200]}...")
    print()
    
    try:
        # Import backend modules
        from app.core.llm_factory import LLMFactory
        from app.core.entity_extraction_agent import EntityExtractionAgent
        
        print("✅ Backend modules imported successfully")
        
        # Get LLM factory
        llm_factory = LLMFactory()
        
        # Create a mock project object (simulating database project)
        class MockProject:
            def __init__(self):
                self.id = "151859dd-98a1-47f7-b980-31759e29c70f"
                self.llm_provider = "gemini"
                self.llm_model = "gemini-2.5-flash"
                self.llm_api_key_id = None  # Will use environment GOOGLE_API_KEY
        
        project = MockProject()
        
        print(f"🤖 Getting LLM for project: {project.id}")
        print(f"🤖 LLM Configuration: provider={project.llm_provider}, model={project.llm_model}")
        
        # Get LLM instance
        llm = llm_factory.get_process_llm(
            project=project,
            process_type="entity_extraction",
            fallback_to_project_default=True
        )
        
        if not llm:
            print("❌ Failed to get LLM instance")
            return
        
        print(f"✅ LLM instance created: {type(llm).__name__}")
        
        # Create entity extraction agent (this will trigger our enhanced debugging)
        print("\n🧠 Creating EntityExtractionAgent with enhanced debugging...")
        agent = EntityExtractionAgent(llm=llm)
        
        print("\n🔥 Starting entity extraction from content...")
        
        # Extract entities (this will show all our debugging output)
        result = await agent.extract_entities_from_content(content, max_entities=10, chunk_size=2000)
        
        print("\n📊 EXTRACTION RESULTS:")
        print("=" * 30)
        print(f"Entities found: {len(result.get('entities', []))}")
        print(f"Relationships found: {len(result.get('relationships', []))}")
        
        if result.get('entities'):
            print("\n📋 Entities:")
            for i, entity in enumerate(result['entities'][:5], 1):
                print(f"  {i}. {entity}")
        
        if result.get('relationships'):
            print("\n🔗 Relationships:")
            for i, rel in enumerate(result['relationships'][:3], 1):
                print(f"  {i}. {rel}")
        
        if result.get('metadata'):
            print(f"\n📈 Metadata: {result['metadata']}")
        
        print("\n" + "=" * 50)
        print("🏁 Test completed!")
        
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()

def check_environment():
    """Check if required environment variables are set"""
    print("🔧 Checking Environment:")
    print("-" * 25)
    
    api_key = os.environ.get('GOOGLE_API_KEY')
    if api_key:
        print(f"✅ GOOGLE_API_KEY: {api_key[:10]}...")
    else:
        print("❌ GOOGLE_API_KEY: Not set")
        print("   Please set: export GOOGLE_API_KEY='your-key-here'")
        return False
    
    return True

if __name__ == "__main__":
    print("🚀 Entity Extraction Debug Test Script")
    print("=" * 50)
    
    if not check_environment():
        print("❌ Environment check failed. Please set required API keys.")
        sys.exit(1)
    
    # Run the test
    asyncio.run(test_entity_extraction())
