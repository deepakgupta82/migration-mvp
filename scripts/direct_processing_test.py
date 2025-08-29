#!/usr/bin/env python3
"""
Direct Document Processing Test
Triggers processing of the specific document and monitors results
"""

import requests
import json
import time
from datetime import datetime

# Configuration
PROJECT_ID = "7d1e347c-efdd-4bc5-a112-98ec17fdf31c"
DOCUMENT_NAME = "D4_Windows server inventory_V38.xlsx"
CORRELATION_ID = f"direct_test_{int(time.time())}"

# Service URLs
DOCUMENT_SERVICE = "http://localhost:8003"
VECTOR_SERVICE = "http://localhost:8005"
GRAPH_SERVICE = "http://localhost:8006"
STORAGE_SERVICE = "http://localhost:8010"

def trigger_document_processing():
    """Trigger document processing"""
    print(f"🚀 Starting document processing for {DOCUMENT_NAME}")
    print(f"Project ID: {PROJECT_ID}")
    print(f"Correlation ID: {CORRELATION_ID}")
    
    payload = {
        "file_names": [DOCUMENT_NAME]
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-Correlation-ID": CORRELATION_ID
    }
    
    try:
        response = requests.post(
            f"{DOCUMENT_SERVICE}/api/documents/{PROJECT_ID}/process-selected",
            json=payload,
            headers=headers,
            timeout=30
        )
        
        print(f"📋 Response Status: {response.status_code}")
        print(f"📋 Response: {response.text}")
        
        if response.status_code in [200, 201]:
            result = response.json()
            job_id = result.get("job_id")
            print(f"✅ Processing started with Job ID: {job_id}")
            return job_id
        else:
            print(f"❌ Failed to start processing: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error starting processing: {str(e)}")
        return None

def monitor_processing_status(job_id, max_wait_minutes=10):
    """Monitor processing status"""
    print(f"🔍 Monitoring processing status for job {job_id}")
    
    start_time = time.time()
    max_wait_seconds = max_wait_minutes * 60
    
    while time.time() - start_time < max_wait_seconds:
        try:
            response = requests.get(
                f"{DOCUMENT_SERVICE}/api/documents/{PROJECT_ID}/status/{job_id}",
                timeout=10
            )
            
            if response.status_code == 200:
                status_data = response.json()
                status = status_data.get("status", "unknown")
                progress = status_data.get("progress", 0)
                
                print(f"📊 Status: {status}, Progress: {progress}%")
                
                if status == "completed":
                    print(f"✅ Processing completed in {int(time.time() - start_time)}s")
                    return True
                elif status == "failed":
                    error_msg = status_data.get("error", "Unknown error")
                    print(f"❌ Processing failed: {error_msg}")
                    print(f"Full response: {json.dumps(status_data, indent=2)}")
                    return False
                else:
                    time.sleep(10)
            else:
                print(f"⚠️ Status check failed: HTTP {response.status_code}")
                time.sleep(5)
                
        except Exception as e:
            print(f"❌ Error checking status: {str(e)}")
            time.sleep(5)
    
    print(f"⏰ Processing timeout after {max_wait_minutes} minutes")
    return False

def check_vector_results():
    """Check if vectors were created"""
    print(f"🔍 Checking vector storage...")
    
    try:
        response = requests.get(
            f"{VECTOR_SERVICE}/api/vectors/projects/{PROJECT_ID}/stats",
            timeout=10
        )
        
        if response.status_code == 200:
            stats = response.json()
            print(f"📊 Vector Stats: {json.dumps(stats, indent=2)}")
            return stats.get("vector_count", 0) > 0
        else:
            print(f"❌ Vector check failed: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error checking vectors: {str(e)}")
        return False

def check_graph_results():
    """Check if graph entities were created"""
    print(f"🔍 Checking graph storage...")
    
    try:
        response = requests.get(
            f"{GRAPH_SERVICE}/api/graphs/projects/{PROJECT_ID}/stats",
            timeout=10
        )
        
        if response.status_code == 200:
            stats = response.json()
            print(f"📊 Graph Stats: {json.dumps(stats, indent=2)}")
            return stats.get("node_count", 0) > 0
        else:
            print(f"❌ Graph check failed: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error checking graph: {str(e)}")
        return False

def test_search_functionality():
    """Test search functionality"""
    print(f"🔍 Testing search functionality...")
    
    search_queries = [
        "windows server",
        "inventory",
        "system",
        "server"
    ]
    
    for query in search_queries:
        try:
            search_payload = {
                "query": query,
                "limit": 3
            }
            
            response = requests.post(
                f"{VECTOR_SERVICE}/api/vectors/projects/{PROJECT_ID}/search",
                json=search_payload,
                timeout=15
            )
            
            if response.status_code == 200:
                results = response.json()
                result_count = len(results.get("results", []))
                print(f"✅ Search '{query}': {result_count} results")
                
                if result_count > 0:
                    print(f"   Sample result: {results['results'][0].get('content', '')[:100]}...")
            else:
                print(f"❌ Search '{query}' failed: HTTP {response.status_code}")
                
        except Exception as e:
            print(f"❌ Search error for '{query}': {str(e)}")

def run_direct_test():
    """Run direct document processing test"""
    print("="*80)
    print("🧪 DIRECT DOCUMENT PROCESSING TEST")
    print("="*80)
    
    # Step 1: Trigger processing
    job_id = trigger_document_processing()
    
    if not job_id:
        print("❌ Could not start processing")
        return False
    
    # Step 2: Monitor processing
    processing_success = monitor_processing_status(job_id)
    
    # Step 3: Check results
    print("\n" + "="*40)
    print("📊 CHECKING RESULTS")
    print("="*40)
    
    vector_success = check_vector_results()
    graph_success = check_graph_results()
    
    # Step 4: Test search
    if vector_success:
        print("\n" + "="*40)
        print("🔍 TESTING SEARCH")
        print("="*40)
        test_search_functionality()
    
    # Summary
    print("\n" + "="*80)
    print("📋 SUMMARY")
    print("="*80)
    print(f"Processing: {'✅ SUCCESS' if processing_success else '❌ FAILED'}")
    print(f"Vectors: {'✅ SUCCESS' if vector_success else '❌ FAILED'}")
    print(f"Graph: {'✅ SUCCESS' if graph_success else '❌ FAILED'}")
    
    overall_success = processing_success and vector_success
    print(f"Overall: {'✅ SUCCESS' if overall_success else '❌ FAILED'}")
    
    return overall_success

if __name__ == "__main__":
    success = run_direct_test()