#!/usr/bin/env python3
"""
Test the actual EntityExtractionAgent to find where the issue occurs
Since basic Gemini works, the problem is in our agent implementation
"""

import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Add backend to Python path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

# Test content
TEST_CONTENT = """
Web Server: Apache HTTP Server 2.4 on RHEL 8 at 192.168.1.10
Database Server: Oracle 19c at 192.168.1.20
Network Switch: Cisco Catalyst 6500 at 192.168.1.1
Firewall: Palo Alto PA-850 at 192.168.1.2
Application: Salesforce CRM with 500 users
ERP System: SAP S/4HANA with Finance and HR modules
"""

def test_entity_agent():
    """Test our actual EntityExtractionAgent with working LLM"""
    
    print("🧪 Testing EntityExtractionAgent Implementation")
    print("=" * 50)
    
    try:
        # Create working LangChain Gemini LLM (we know this works)
        from langchain_google_genai import ChatGoogleGenerativeAI
        
        api_key = os.environ.get('GOOGLE_API_KEY')
        
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=api_key,
            temperature=0.1
        )
        
        print("✅ Created working LangChain Gemini LLM")
        
        # Import and create our entity extraction agent
        from app.core.entity_extraction_agent import EntityExtractionAgent
        
        print("🧠 Creating EntityExtractionAgent...")
        print("📍 Watch for our enhanced debugging output below:")
        print("-" * 40)
        
        # This should trigger our enhanced debugging in __init__
        agent = EntityExtractionAgent(llm=llm)
        
        print("-" * 40)
        print("✅ EntityExtractionAgent created successfully")
        
        print(f"\n📝 Test content ({len(TEST_CONTENT)} chars):")
        print(TEST_CONTENT)
        
        print("\n🔍 Starting entity extraction with full debugging...")
        print("🔍 This will show our enhanced logs:")
        print("  - Full prompt logging")
        print("  - Direct API test comparison")
        print("  - Detailed response analysis")
        print("\n" + "=" * 50)
        
        # Call extract_entities_and_relationships with our test content
        result = agent.extract_entities_and_relationships(TEST_CONTENT)
        
        print("=" * 50)
        print("🎯 ENTITY EXTRACTION RESULTS:")
        print("=" * 50)
        
        entities = result.get('entities', [])
        relationships = result.get('relationships', [])
        metadata = result.get('metadata', {})
        
        print(f"📊 Entities found: {len(entities)}")
        print(f"📊 Relationships found: {len(relationships)}")
        
        if entities:
            print(f"\n✅ SUCCESS! Found {len(entities)} entities:")
            for i, entity in enumerate(entities, 1):
                print(f"  {i}. {entity}")
        else:
            print(f"\n❌ FAILURE! No entities found")
            print("📋 This confirms the issue is in our EntityExtractionAgent")
            
        if relationships:
            print(f"\n🔗 Relationships:")
            for i, rel in enumerate(relationships, 1):
                print(f"  {i}. {rel}")
                
        print(f"\n📈 Metadata: {metadata}")
        
        # Analysis
        print(f"\n🔍 ANALYSIS:")
        if len(entities) == 0:
            print("❌ EntityExtractionAgent failed despite working LLM")
            print("💡 Check the debugging logs above to see:")
            print("   - Did our prompts get constructed properly?")
            print("   - Did the direct API test in agent work?")
            print("   - Where exactly did the LangChain call fail?")
        else:
            print("✅ EntityExtractionAgent working correctly!")
            
    except Exception as e:
        print(f"❌ Error testing EntityExtractionAgent: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🔧 EntityExtractionAgent Debug Test")
    print("🎯 Testing our agent implementation with working LLM")
    print("=" * 50)
    
    # Check environment
    if not os.environ.get('GOOGLE_API_KEY'):
        print("❌ GOOGLE_API_KEY not found")
        sys.exit(1)
        
    print("✅ Environment check passed")
    
    # Run the test
    test_entity_agent()
