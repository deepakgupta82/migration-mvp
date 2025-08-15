#!/usr/bin/env python3
"""
Test the complete RAG service entity extraction workflow
to find where 0 entities are coming from in real processing
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

# Sample document content (similar to what you processed)
SAMPLE_CONTENT = """
# IT Infrastructure Assessment

## Current Environment

### Servers
- **Web Server**: Apache HTTP Server 2.4 running on RHEL 8
  - IP Address: 192.168.1.10
  - CPU: 8 cores, 32GB RAM
  - Storage: 500GB SSD
  - Role: Frontend web application hosting

- **Database Server**: Oracle Database 19c Enterprise Edition
  - IP Address: 192.168.1.20  
  - CPU: 16 cores, 64GB RAM
  - Storage: 2TB NVMe SSD
  - Role: Primary database for business applications

### Network Infrastructure
- **Core Switch**: Cisco Catalyst 6500 Series
  - Management IP: 192.168.1.1
  - Ports: 48x 1Gb Ethernet, 4x 10Gb Uplinks
  - VLAN Configuration: Production (VLAN 100), Development (VLAN 200)

- **Firewall**: Palo Alto Networks PA-850
  - Management IP: 192.168.1.2
  - Throughput: 1.9 Gbps
  - Security Features: IPS, URL Filtering, Malware Protection
"""

def test_rag_service_entity_extraction():
    """Test the RAG service entity extraction workflow exactly as used in production"""
    
    print("🔍 Testing RAG Service Entity Extraction Workflow")
    print("=" * 60)
    
    try:
        # Import RAG service and related classes
        from app.core.rag_service import RAGService
        from langchain_google_genai import ChatGoogleGenerativeAI
        
        # Create Gemini LLM (matching project configuration)
        api_key = os.environ.get('GOOGLE_API_KEY')
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=api_key,
            temperature=0.1
        )
        
        print("✅ Created Gemini LLM")
        
        # Create RAG service for the test project
        project_id = "151859dd-98a1-47f7-b980-31759e29c70f"
        rag_service = RAGService(project_id=project_id, llm=llm)
        
        print(f"✅ Created RAG service for project: {project_id}")
        
        print(f"\n📄 Test content ({len(SAMPLE_CONTENT)} chars):")
        print(SAMPLE_CONTENT[:300] + "...")
        
        print("\n🔍 Running entity extraction via RAG service...")
        print("🔍 This will show the exact same workflow as real processing")
        
        # Call the exact method used in production
        try:
            # First, let's see if there's a specific entity extraction method
            if hasattr(rag_service, 'extract_entities'):
                print("📍 Using RAG service extract_entities method")
                result = rag_service.extract_entities(SAMPLE_CONTENT)
            else:
                print("📍 RAG service doesn't have extract_entities method")
                print("📍 Let's check what methods it has:")
                methods = [method for method in dir(rag_service) if not method.startswith('_') and callable(getattr(rag_service, method))]
                print(f"📍 Available methods: {methods}")
                
                # Let's try to create the entity extraction agent manually like RAG service does
                from app.core.entity_extraction_agent import EntityExtractionAgent
                
                agent = EntityExtractionAgent(llm=llm)
                print("✅ Created EntityExtractionAgent via RAG service workflow")
                
                # Extract entities the same way RAG service does
                result = agent.extract_entities_and_relationships(SAMPLE_CONTENT)
                print("✅ Called extract_entities_and_relationships")
                
        except Exception as extraction_error:
            print(f"❌ Entity extraction failed: {extraction_error}")
            import traceback
            traceback.print_exc()
            return
        
        print("\n" + "=" * 60)
        print("📊 RAG SERVICE EXTRACTION RESULTS:")
        print("=" * 60)
        
        entities = result.get('entities', [])
        relationships = result.get('relationships', [])
        metadata = result.get('metadata', {})
        
        print(f"📊 Entities: {len(entities)}")
        print(f"📊 Relationships: {len(relationships)}")
        
        if entities:
            print(f"\n✅ SUCCESS! Found {len(entities)} entities:")
            for i, entity in enumerate(entities[:10], 1):  # Show first 10
                print(f"  {i}. {entity}")
        else:
            print(f"\n❌ FAILURE! 0 entities found - this matches your production issue!")
            print("🔍 This means the issue is in the EntityExtractionAgent implementation")
            print("🔍 But our direct test showed it working... investigating...")
        
        if relationships:
            print(f"\n🔗 Relationships (first 5):")
            for i, rel in enumerate(relationships[:5], 1):
                print(f"  {i}. {rel}")
        
        print(f"\n📈 Metadata: {metadata}")
        
        # Analysis
        if len(entities) == 0:
            print(f"\n🔍 DEBUGGING THE 0 ENTITIES ISSUE:")
            print("1. Direct Gemini API: ✅ Works")
            print("2. LangChain Gemini: ✅ Works")
            print("3. EntityExtractionAgent direct test: ✅ Works")
            print("4. RAG service workflow: ❌ Returns 0 entities")
            print("")
            print("💡 The issue must be in:")
            print("   - Content preprocessing in RAG service")
            print("   - Different LLM configuration")
            print("   - Different prompts being used")
            print("   - Exception handling hiding the real error")
        
        return result
        
    except Exception as e:
        print(f"❌ Error in RAG service test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🚀 RAG Service Entity Extraction Debug Test")
    print("🎯 Reproducing the exact production workflow")
    print("=" * 60)
    
    if not os.environ.get('GOOGLE_API_KEY'):
        print("❌ GOOGLE_API_KEY not found")
        sys.exit(1)
        
    print("✅ Environment check passed")
    
    result = test_rag_service_entity_extraction()
    
    if result and len(result.get('entities', [])) > 0:
        print("\n🎉 RAG service workflow is working!")
    else:
        print("\n🔍 RAG service workflow issue confirmed - need to investigate further")
