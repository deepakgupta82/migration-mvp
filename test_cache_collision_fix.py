"""
Test Cache Collision Fix - Parallel Batch Processing

Validates that each batch gets a unique document_id to prevent cache collisions.
This test creates 6 batches (like the production run) to verify the fix.

Expected Behavior:
- Each batch should have unique document_id: filename_batch_1, filename_batch_2, etc.
- No "Returning cached result" warnings in graph-service logs
- All 6 batches should process independently (not return cached results)
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

# Create 6 small batches (2 servers each = 12 total servers)
# Each batch should process independently
def create_test_batches():
    """Create 6 batches with 2 servers each"""
    server_names = [
        ("ALPHA", "10.1.0.1", "RHEL 8"),
        ("BRAVO", "10.1.0.2", "Ubuntu 22"),
        ("CHARLIE", "10.1.0.3", "Windows Server 2019"),
        ("DELTA", "10.1.0.4", "RHEL 9"),
        ("ECHO", "10.1.0.5", "Ubuntu 20"),
        ("FOXTROT", "10.1.0.6", "Windows Server 2022"),
        ("GOLF", "10.1.0.7", "RHEL 8"),
        ("HOTEL", "10.1.0.8", "Ubuntu 22"),
        ("INDIA", "10.1.0.9", "Windows Server 2019"),
        ("JULIET", "10.1.0.10", "RHEL 9"),
        ("KILO", "10.1.0.11", "Ubuntu 20"),
        ("LIMA", "10.1.0.12", "Windows Server 2022"),
    ]
    
    batches = []
    for i in range(0, 12, 2):  # 6 batches of 2 servers each
        batch = []
        for j in range(2):
            idx = i + j
            name, ip, os = server_names[idx]
            batch.append({
                "element_id": f"elem_{idx+1}",
                "content": f"Server Name: {name} | IP: {ip} | OS: {os} | Owner: TestTeam",
                "element_type": "NarrativeText",
                "page_number": 1
            })
        batches.append(batch)
    
    return batches

async def test_batch(batch_num, batch_elements, base_filename):
    """
    Test a single batch with unique document_id
    """
    # Create unique document_id for this batch (simulating what enhanced_processor does)
    batch_document_id = f"{base_filename}_batch_{batch_num}"
    
    payload = {
        "document_id": batch_document_id,
        "structured_elements": batch_elements,
        "filename": f"{base_filename}.txt"
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-Correlation-ID": CORRELATION_ID,
        "Authorization": "Bearer service-backend-token"
    }
    
    endpoint = f"{GRAPH_SERVICE_URL}/api/graphs/projects/{PROJECT_ID}/process-structured"
    
    print(f"  📤 Batch {batch_num}: document_id={batch_document_id}, elements={len(batch_elements)}")
    
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
            
            if response.status_code == 200:
                result = response.json()
                entities = result.get('entities_extracted', 0)
                rels = result.get('relationships_found', 0)
                
                print(f"  ✅ Batch {batch_num}: {entities} entities, {rels} relationships ({duration:.1f}s)")
                return {
                    "batch": batch_num,
                    "status": "success",
                    "entities": entities,
                    "relationships": rels,
                    "duration": duration
                }
            else:
                print(f"  ❌ Batch {batch_num}: Error {response.status_code}")
                return {
                    "batch": batch_num,
                    "status": "error",
                    "error": response.status_code
                }
                
    except Exception as e:
        print(f"  ❌ Batch {batch_num}: Exception {e}")
        return {
            "batch": batch_num,
            "status": "exception",
            "error": str(e)
        }

async def test_parallel_batches():
    """
    Test parallel batch processing with unique document IDs
    """
    print("=" * 80)
    print("CACHE COLLISION FIX TEST - Parallel Batch Processing")
    print("=" * 80)
    print(f"Project ID: {PROJECT_ID}")
    print(f"Correlation ID: {CORRELATION_ID}")
    print("=" * 80)
    print()
    
    batches = create_test_batches()
    base_filename = f"cache_test_{CORRELATION_ID[:8]}"
    
    print(f"📊 Test Configuration:")
    print(f"   Total Batches: {len(batches)}")
    print(f"   Elements per Batch: 2 servers")
    print(f"   Total Servers: 12")
    print(f"   Base Filename: {base_filename}")
    print()
    
    print(f"🚀 Starting parallel batch processing...")
    print()
    
    start_time = datetime.now()
    
    # Process all batches in parallel (simulating ENABLE_PARALLEL_GRAPH_BATCHES=true)
    tasks = [
        test_batch(i+1, batch, base_filename)
        for i, batch in enumerate(batches)
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    end_time = datetime.now()
    total_duration = (end_time - start_time).total_seconds()
    
    print()
    print("=" * 80)
    print("📊 RESULTS:")
    print("=" * 80)
    
    successful = sum(1 for r in results if isinstance(r, dict) and r.get('status') == 'success')
    failed = len(results) - successful
    total_entities = sum(r.get('entities', 0) for r in results if isinstance(r, dict))
    total_rels = sum(r.get('relationships', 0) for r in results if isinstance(r, dict))
    
    print(f"   Successful Batches: {successful}/{len(batches)}")
    print(f"   Failed Batches: {failed}")
    print(f"   Total Entities: {total_entities} (expected: 12+ servers)")
    print(f"   Total Relationships: {total_rels}")
    print(f"   Total Duration: {total_duration:.1f}s")
    print()
    
    # Validate results
    print("=" * 80)
    print("🔍 VALIDATION:")
    print("=" * 80)
    
    if successful == len(batches):
        print("✅ All batches processed successfully")
    else:
        print(f"❌ {failed} batches failed")
    
    if total_entities >= 12:
        print(f"✅ Correct entity count: {total_entities} servers extracted")
    else:
        print(f"❌ Low entity count: {total_entities} (expected 12+)")
    
    print()
    print("=" * 80)
    print("🔎 NEXT STEPS:")
    print("=" * 80)
    print(f"   1. Search graph-service logs for: [{CORRELATION_ID}]")
    print(f"   2. Look for [CACHE] entries showing unique cache keys:")
    print(f"      - cache_key={CORRELATION_ID}:{base_filename}_batch_1")
    print(f"      - cache_key={CORRELATION_ID}:{base_filename}_batch_2")
    print(f"      - ... (should be 6 unique cache keys)")
    print(f"   3. Verify NO \"Returning cached result\" warnings")
    print(f"   4. Each batch should show \"Starting new processing\"")
    print("=" * 80)
    
    # Detailed batch results
    if any(r.get('status') != 'success' for r in results if isinstance(r, dict)):
        print()
        print("⚠️  FAILED BATCHES:")
        for r in results:
            if isinstance(r, dict) and r.get('status') != 'success':
                print(f"   Batch {r['batch']}: {r.get('error', 'unknown error')}")

if __name__ == "__main__":
    asyncio.run(test_parallel_batches())
