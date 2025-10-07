"""
Minimal Token Test for Graph Entity Extraction

Tests Phase 3B-4 entity extraction with exactly 3 server elements to:
1. Validate [EXTRACT] logging shows LLM prompts and responses
2. Verify entities are correctly extracted without cache collision
3. Minimize LLM tokens used (<100 tokens expected)

Expected Outcome:
- 3 Server entities extracted (LION, TIGER, WHALE)
- Logs show actual prompt and raw LLM response
- Total tokens < 100
"""

import asyncio
import httpx
import json
import uuid
from datetime import datetime

# Test configuration
PROJECT_ID = "d1d78934-bc20-4f0d-b3bf-45d8497642e5"
CORRELATION_ID = str(uuid.uuid4())
GRAPH_SERVICE_URL = "http://localhost:8006"

# Minimal test data: 3 servers with LION, TIGER, WHALE
# This should extract exactly 3 Server entities
MINIMAL_ELEMENTS = [
    {
        "element_id": "elem_1",
        "content": "Server Name: LION | IP: 10.0.0.1 | OS: RHEL 8 | Owner: TeamAlpha",
        "element_type": "NarrativeText",
        "page_number": 1
    },
    {
        "element_id": "elem_2",
        "content": "Server Name: TIGER | IP: 10.0.0.2 | OS: Ubuntu 22 | Owner: TeamBeta",
        "element_type": "NarrativeText",
        "page_number": 1
    },
    {
        "element_id": "elem_3",
        "content": "Server Name: WHALE | IP: 10.0.0.3 | OS: Windows Server 2019 | Owner: TeamGamma",
        "element_type": "NarrativeText",
        "page_number": 1
    }
]

async def test_minimal_extraction():
    """
    Run minimal entity extraction test directly against graph service
    """
    print("=" * 80)
    print("MINIMAL TOKEN TEST - Graph Entity Extraction")
    print("=" * 80)
    print(f"Project ID: {PROJECT_ID}")
    print(f"Correlation ID: {CORRELATION_ID}")
    print(f"Test Elements: {len(MINIMAL_ELEMENTS)}")
    print(f"Expected Entities: 3 Servers (LION, TIGER, WHALE)")
    print("=" * 80)
    print()
    
    # Build request payload
    payload = {
        "document_id": f"minimal_test_{CORRELATION_ID[:8]}.txt",
        "structured_elements": MINIMAL_ELEMENTS,
        "filename": "minimal_test.txt"
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-Correlation-ID": CORRELATION_ID,
        "Authorization": "Bearer service-backend-token"
    }
    
    endpoint = f"{GRAPH_SERVICE_URL}/api/graphs/projects/{PROJECT_ID}/process-structured"
    
    print(f"⏳ Calling graph service: {endpoint}")
    print(f"   Payload size: {len(json.dumps(payload))} bytes")
    print()
    
    start_time = datetime.now()
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                endpoint,
                json=payload,
                headers=headers
            )
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            print(f"✅ Response received in {duration:.2f}s")
            print(f"   Status Code: {response.status_code}")
            print()
            
            if response.status_code == 200:
                result = response.json()
                
                print("📊 RESULTS:")
                print(f"   Entities Extracted: {result.get('entities', 0)}")
                print(f"   Relationships: {result.get('relationships', 0)}")
                print(f"   Discovery Nodes: {result.get('discovery_nodes', 0)}")
                print(f"   Processing Time: {result.get('processing_time', 0):.2f}s")
                print()
                
                # Validate expected results
                entities = result.get('entities', 0)
                if entities == 3:
                    print("✅ SUCCESS: Extracted exactly 3 entities as expected!")
                elif entities == 0:
                    print("❌ FAILURE: 0 entities extracted (cache collision or extraction failure)")
                else:
                    print(f"⚠️  WARNING: Extracted {entities} entities (expected 3)")
                
                print()
                print("🔍 Check graph-service logs for [EXTRACT] entries:")
                print("   - Prompt preview (first 1000 chars)")
                print("   - Raw LLM response (first 2000 chars)")
                print("   - Parsed entity count")
                
            else:
                print(f"❌ ERROR: {response.status_code}")
                print(f"   Response: {response.text[:500]}")
                
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 80)
    print(f"🔎 NEXT STEPS:")
    print(f"   1. Search graph-service logs for: [{CORRELATION_ID}]")
    print(f"   2. Look for [EXTRACT] log entries showing prompts and responses")
    print(f"   3. Verify no cache collision occurred")
    print(f"   4. Check why entities were/weren't extracted correctly")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_minimal_extraction())
