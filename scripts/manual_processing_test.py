#!/usr/bin/env python3
"""
Manual Document Processing Test
Step-by-step manual test to isolate the exact failure point
"""

import requests
import json
import time
from datetime import datetime

# Configuration
PROJECT_ID = "7d1e347c-efdd-4bc5-a112-98ec17fdf31c"
DOCUMENT_NAME = "D4_Windows server inventory_V38.xlsx"
CORRELATION_ID = f"manual_{int(time.time())}"

def test_step_by_step():
    print("🔧 MANUAL DOCUMENT PROCESSING TEST")
    print("="*60)
    print(f"Project: {PROJECT_ID}")
    print(f"Document: {DOCUMENT_NAME}")
    print(f"Correlation: {CORRELATION_ID}")
    
    # Step 1: Check document exists
    print("\\n1️⃣ Checking document exists in storage...")
    try:
        response = requests.get(
            f"http://localhost:8010/api/storage/projects/{PROJECT_ID}/files/uploads_raw",
            timeout=10
        )
        if response.status_code == 200:
            files_data = response.json()
            files = files_data.get('files', [])
            document_found = any(f.get('filename') == DOCUMENT_NAME for f in files)
            
            if document_found:
                print("✅ Document found in storage")
                doc_info = next(f for f in files if f.get('filename') == DOCUMENT_NAME)
                print(f"   Size: {doc_info.get('size')} bytes")
                print(f"   Modified: {doc_info.get('last_modified')}")
            else:
                print("❌ Document not found!")
                return False
        else:
            print(f"❌ Storage check failed: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error checking storage: {e}")
        return False
    
    # Step 2: Test document download
    print("\\n2️⃣ Testing document download...")
    try:
        download_url = f"http://localhost:8010/api/storage/projects/{PROJECT_ID}/download/uploads_raw/{DOCUMENT_NAME}"
        response = requests.get(
            download_url,
            headers={"Authorization": "Bearer service-backend-token"},
            timeout=30
        )
        if response.status_code == 200:
            print(f"✅ Document download successful: {len(response.content)} bytes")
        else:
            print(f"❌ Download failed: HTTP {response.status_code}")
            print(f"   Error: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Download error: {e}")
        return False
    
    # Step 3: Test LLM service health
    print("\\n3️⃣ Testing LLM service...")
    try:
        response = requests.get("http://localhost:8007/health", timeout=10)
        if response.status_code == 200:
            print("✅ LLM service healthy")
        else:
            print(f"❌ LLM service unhealthy: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ LLM service error: {e}")
    
    # Step 4: Test Vector service health
    print("\\n4️⃣ Testing Vector service...")
    try:
        response = requests.get("http://localhost:8005/health", timeout=10)
        if response.status_code == 200:
            print("✅ Vector service healthy")
        else:
            print(f"❌ Vector service unhealthy: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ Vector service error: {e}")
    
    # Step 5: Test Graph service health
    print("\\n5️⃣ Testing Graph service...")
    try:
        response = requests.get("http://localhost:8006/health", timeout=10)
        if response.status_code == 200:
            print("✅ Graph service healthy")
        else:
            print(f"❌ Graph service unhealthy: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ Graph service error: {e}")
    
    # Step 6: Start processing
    print("\\n6️⃣ Starting document processing...")
    try:
        payload = {"file_names": [DOCUMENT_NAME]}
        headers = {
            "Content-Type": "application/json",
            "X-Correlation-ID": CORRELATION_ID
        }
        
        response = requests.post(
            f"http://localhost:8003/api/documents/{PROJECT_ID}/process-selected",
            json=payload,
            headers=headers,
            timeout=30
        )
        
        print(f"Response Status: {response.status_code}")
        print(f"Response Body: {response.text}")
        
        if response.status_code in [200, 201]:
            result = response.json()
            job_id = result.get("job_id")
            
            if job_id:
                print(f"✅ Processing started successfully!")
                print(f"   Job ID: {job_id}")
                return monitor_job_simple(job_id)
            else:
                print("❌ No job ID returned")
                return False
        else:
            print(f"❌ Processing failed to start")
            return False
            
    except Exception as e:
        print(f"❌ Processing start error: {e}")
        return False

def monitor_job_simple(job_id, max_wait=600):  # 10 minutes
    print(f"\\n7️⃣ Monitoring job {job_id}...")
    
    start_time = time.time()
    last_status = None
    
    while time.time() - start_time < max_wait:
        try:
            response = requests.get(
                f"http://localhost:8003/api/documents/{PROJECT_ID}/status/{job_id}",
                timeout=10
            )
            
            if response.status_code == 200:
                status_data = response.json()
                status = status_data.get("status", "unknown")
                progress = status_data.get("progress", 0)
                
                if status != last_status:
                    print(f"📊 Status: {status} ({progress}%)")
                    if status_data.get("current_file"):
                        print(f"   Processing: {status_data['current_file']}")
                    last_status = status
                
                if status == "completed":
                    elapsed = int(time.time() - start_time)
                    print(f"✅ Processing completed in {elapsed}s!")
                    
                    # Check results
                    print("\\n8️⃣ Checking results...")
                    check_processing_results()
                    return True
                    
                elif status == "failed":
                    print(f"❌ Processing failed!")
                    print(f"Error details: {json.dumps(status_data, indent=2)}")
                    return False
                    
            else:
                print(f"⚠️ Status check error: HTTP {response.status_code}")
            
            time.sleep(10)
            
        except Exception as e:
            print(f"❌ Monitoring error: {e}")
            time.sleep(5)
    
    print(f"⏰ Timeout after {max_wait} seconds")
    return False

def check_processing_results():
    """Check if processing actually created results"""
    
    # Check vectors
    try:
        response = requests.get(f"http://localhost:8005/api/vectors/projects/{PROJECT_ID}/stats", timeout=10)
        if response.status_code == 200:
            stats = response.json()
            vector_count = stats.get("vector_count", 0)
            print(f"📊 Vectors: {vector_count} embeddings")
        else:
            print(f"❌ Vector check failed: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ Vector check error: {e}")
    
    # Check graph
    try:
        response = requests.get(f"http://localhost:8006/api/graphs/projects/{PROJECT_ID}/stats", timeout=10)
        if response.status_code == 200:
            stats = response.json()
            node_count = stats.get("node_count", 0)
            relationship_count = stats.get("relationship_count", 0)
            print(f"📊 Graph: {node_count} nodes, {relationship_count} relationships")
        else:
            print(f"❌ Graph check failed: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ Graph check error: {e}")
    
    # Test search
    try:
        search_payload = {"query": "windows server", "limit": 3}
        response = requests.post(
            f"http://localhost:8005/api/vectors/projects/{PROJECT_ID}/search",
            json=search_payload,
            timeout=15
        )
        if response.status_code == 200:
            results = response.json()
            result_count = len(results.get("results", []))
            print(f"📊 Search: {result_count} results found")
            if result_count > 0:
                print(f"   Sample: {results['results'][0].get('content', '')[:100]}...")
        else:
            print(f"❌ Search test failed: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ Search test error: {e}")

if __name__ == "__main__":
    success = test_step_by_step()
    print("\\n" + "="*60)
    if success:
        print("🎉 DOCUMENT PROCESSING SUCCESSFUL!")
    else:
        print("❌ DOCUMENT PROCESSING FAILED!")
    print("="*60)