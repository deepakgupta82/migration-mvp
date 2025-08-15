#!/usr/bin/env python3
"""
Direct entity extraction test script for debugging Gemini LLM issues
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

# Test content - IT infrastructure document sample
TEST_CONTENT = """
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

- **Application Server**: IBM WebSphere Application Server 9.0
  - IP Address: 192.168.1.30
  - CPU: 12 cores, 48GB RAM
  - Storage: 1TB SSD
  - Role: Business logic processing

### Network Infrastructure
- **Core Switch**: Cisco Catalyst 6500 Series
  - Management IP: 192.168.1.1
  - Ports: 48x 1Gb Ethernet, 4x 10Gb Uplinks
  - VLAN Configuration: Production (VLAN 100), Development (VLAN 200)

- **Firewall**: Palo Alto Networks PA-850
  - Management IP: 192.168.1.2
  - Throughput: 1.9 Gbps
  - Security Features: IPS, URL Filtering, Malware Protection

### Applications
- **CRM System**: Salesforce Enterprise
  - Version: Summer '23 Release
  - Users: 500 active licenses
  - Integration: REST APIs with internal systems

- **ERP System**: SAP S/4HANA On-Premise
  - Version: 2022 FPS01
  - Modules: Finance, HR, Supply Chain
  - Database: Oracle 19c backend

## Dependencies
- Web Server depends on Database Server for data retrieval
- Application Server connects to Database Server via JDBC
- CRM System integrates with ERP System through middleware
- All servers connect through Core Switch
- External access controlled by Firewall

## Compliance Requirements
- SOX compliance for financial data
- GDPR compliance for customer data
- PCI DSS for payment processing
"""

async def test_entity_extraction():
    """Test entity extraction with direct LLM configuration"""
    
    print("🔍 Starting Entity Extraction Debug Test")
    print("=" * 50)
    
    print(f"📄 Using test content: {len(TEST_CONTENT)} characters")
    print(f"📄 Content preview (first 300 chars):\n{TEST_CONTENT[:300]}...")
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
        print(f"✅ LLM model: {getattr(llm, 'model', 'unknown')}")
        
        # Create entity extraction agent (this will trigger our enhanced debugging)
        print("\n🧠 Creating EntityExtractionAgent with enhanced debugging...")
        agent = EntityExtractionAgent(llm=llm)
        
        print("\n🔥 Starting entity extraction from content...")
        print("🔍 This will show:")
        print("  1. Full prompt logging")  
        print("  2. Direct Gemini API test")
        print("  3. LangChain response analysis")
        print("  4. API key validation")
        print()
        
        # Extract entities (this will show all our debugging output)
        result = await agent.extract_entities_from_content(TEST_CONTENT, max_entities=15, chunk_size=3000)
        
        print("\n" + "=" * 50)
        print("📊 FINAL EXTRACTION RESULTS:")
        print("=" * 50)
        print(f"✨ Entities found: {len(result.get('entities', []))}")
        print(f"🔗 Relationships found: {len(result.get('relationships', []))}")
        
        if result.get('entities'):
            print("\n📋 Entities (first 10):")
            for i, entity in enumerate(result['entities'][:10], 1):
                print(f"  {i}. {entity}")
        
        if result.get('relationships'):
            print("\n🔗 Relationships (first 5):")
            for i, rel in enumerate(result['relationships'][:5], 1):
                print(f"  {i}. {rel}")
        
        if result.get('metadata'):
            print(f"\n📈 Extraction Metadata:")
            for key, value in result['metadata'].items():
                print(f"  {key}: {value}")
        
        print("\n" + "=" * 50)
        print("🏁 Test completed!")
        
        # Analysis
        if len(result.get('entities', [])) == 0:
            print("\n❌ ANALYSIS: No entities extracted!")
            print("   Check the debugging output above for:")
            print("   - Are prompts empty or malformed?")
            print("   - Does direct Gemini API work vs LangChain?")
            print("   - Are there LLM response errors?")
        else:
            print(f"\n✅ ANALYSIS: Successfully extracted {len(result.get('entities', []))} entities")
        
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()

def check_environment():
    """Check if required environment variables are set"""
    print("🔧 Environment Check:")
    print("-" * 25)
    
    api_key = os.environ.get('GOOGLE_API_KEY')
    if api_key:
        print(f"✅ GOOGLE_API_KEY: {api_key[:10]}...")
    else:
        print("❌ GOOGLE_API_KEY: Not set")
        return False
    
    # Check for alternative key names
    gemini_key = os.environ.get('GEMINI_API_KEY')
    if gemini_key:
        print(f"✅ GEMINI_API_KEY: {gemini_key[:10]}...")
    
    return True

if __name__ == "__main__":
    print("🚀 Entity Extraction Debug Test Script")
    print("🎯 Testing Gemini LLM Entity Extraction")
    print("=" * 50)
    
    if not check_environment():
        print("❌ Environment check failed. Please check API keys.")
        sys.exit(1)
    
    # Run the test
    asyncio.run(test_entity_extraction())
