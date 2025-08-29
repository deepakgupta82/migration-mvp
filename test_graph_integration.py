#!/usr/bin/env python3
"""
Test Graph Service Integration
Tests if the graph service is properly integrated with document processing
"""

import asyncio
import httpx
import json
import uuid
from datetime import datetime

async def test_graph_service_health():
    """Test if graph service is healthy"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("http://localhost:8006/health")
            if response.status_code == 200:
                health_data = response.json()
                print(f"✅ Graph Service Health: {health_data}")
                return True
            else:
                print(f"❌ Graph Service Health Check Failed: {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ Graph Service Connection Failed: {e}")
        return False

async def test_graph_service_process_structured():
    """Test the process-structured endpoint"""
    try:
        # Sample structured elements
        test_elements = [
            {
                "element_id": "test_001",
                "content": "Windows Server 2019 running SQL Server 2017 Enterprise with 32GB RAM and 8 CPU cores",
                "element_type": "narrative_text",
                "page_number": 1,
                "hierarchy_level": 1,
                "metadata": {"source": "test_document"}
            },
            {
                "element_id": "test_002", 
                "content": "Application Server: WebApp1 connecting to Database DB-PROD-01 on port 1433",
                "element_type": "narrative_text",
                "page_number": 1,
                "hierarchy_level": 1,
                "metadata": {"source": "test_document"}
            }
        ]
        
        payload = {
            "document_id": str(uuid.uuid4()),
            "filename": "test_integration.txt",
            "structured_elements": test_elements,
            "processing_type": "structured_extraction",
            "extract_entities": True,
            "extract_relationships": True
        }
        
        print(f"🧪 Testing Graph Service Process-Structured Endpoint...")
        print(f"   Payload: {len(test_elements)} elements")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "http://localhost:8006/api/graphs/projects/test-project-123/process-structured",
                json=payload,
                headers={
                    "Authorization": "Bearer service-backend-token",
                    "X-Correlation-ID": str(uuid.uuid4())
                }
            )
            
            print(f"   Response Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Graph Processing Successful:")
                print(f"   - Elements Analyzed: {result.get('elements_analyzed', 0)}")
                print(f"   - Entities Extracted: {result.get('entities_extracted', 0)}")
                print(f"   - Relationships Found: {result.get('relationships_found', 0)}")
                print(f"   - Processing Time: {result.get('processing_time_seconds', 0):.2f}s")
                return True
            else:
                print(f"❌ Graph Processing Failed: {response.status_code}")
                print(f"   Error: {response.text[:500]}")
                return False
                
    except Exception as e:
        print(f"❌ Graph Service Process-Structured Test Failed: {e}")
        return False

async def test_document_service_health():
    """Test if document service is healthy"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("http://localhost:8003/health")
            if response.status_code == 200:
                health_data = response.json()
                print(f"✅ Document Service Health: {health_data}")
                return True
            else:
                print(f"❌ Document Service Health Check Failed: {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ Document Service Connection Failed: {e}")
        return False

async def test_enhanced_processor_config():
    """Test enhanced processor configuration"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("http://localhost:8003/workflow-config")
            if response.status_code == 200:
                config = response.json()
                print(f"✅ Enhanced Processor Configuration:")
                print(f"   - Use Enhanced Workflow: {config.get('use_enhanced', False)}")
                print(f"   - Vector Integration: {config.get('vector_integration', False)}")
                print(f"   - Graph Integration: {config.get('graph_integration', False)}")
                print(f"   - WebSocket Notifications: {config.get('websocket_notifications', False)}")
                print(f"   - Parallel Processing: {config.get('parallel_processing', False)}")
                
                if not config.get('graph_integration', False):
                    print(f"⚠️  WARNING: Graph integration is DISABLED!")
                    return False
                return True
            else:
                print(f"❌ Enhanced Processor Config Check Failed: {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ Enhanced Processor Config Test Failed: {e}")
        return False

async def main():
    """Main test function"""
    print("=" * 80)
    print("🔍 GRAPH SERVICE INTEGRATION DIAGNOSTIC TEST")
    print("=" * 80)
    print(f"Started at: {datetime.now().isoformat()}")
    print()
    
    # Test 1: Graph Service Health
    print("📋 Test 1: Graph Service Health Check")
    graph_healthy = await test_graph_service_health()
    print()
    
    # Test 2: Document Service Health 
    print("📋 Test 2: Document Service Health Check")
    doc_healthy = await test_document_service_health()
    print()
    
    # Test 3: Enhanced Processor Configuration
    print("📋 Test 3: Enhanced Processor Configuration")
    config_ok = await test_enhanced_processor_config()
    print()
    
    # Test 4: Graph Service Process-Structured Endpoint
    print("📋 Test 4: Graph Service Process-Structured Endpoint")
    if graph_healthy:
        process_ok = await test_graph_service_process_structured()
    else:
        print("⏭️  Skipping due to graph service health check failure")
        process_ok = False
    print()
    
    # Summary
    print("=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)
    print(f"Graph Service Health: {'✅ PASS' if graph_healthy else '❌ FAIL'}")
    print(f"Document Service Health: {'✅ PASS' if doc_healthy else '❌ FAIL'}")
    print(f"Enhanced Processor Config: {'✅ PASS' if config_ok else '❌ FAIL'}")
    print(f"Graph Processing Endpoint: {'✅ PASS' if process_ok else '❌ FAIL'}")
    print()
    
    if all([graph_healthy, doc_healthy, config_ok, process_ok]):
        print("🎉 ALL TESTS PASSED! Graph service integration should work.")
    else:
        print("⚠️  SOME TESTS FAILED! Graph service integration issues detected.")
    
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())