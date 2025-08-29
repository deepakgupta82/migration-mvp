#!/usr/bin/env python3
"""
Test Vector Service Endpoint Fix
Verifies that the document service can now successfully call the correct vector service endpoint
"""

import requests
import json
import time

def test_vector_service_endpoint():
    """Test if the vector service endpoint is accessible"""
    
    print("🧪 Testing Vector Service Endpoint Accessibility...")
    
    # Test vector service health
    try:
        response = requests.get("http://localhost:8005/health", timeout=5)
        print(f"Vector service health: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Vector service is running")
        else:
            print("❌ Vector service health check failed")
            return False
    except Exception as e:
        print(f"❌ Vector service not accessible: {e}")
        return False
    
    # Test the specific endpoint that was failing
    project_id = "7d1e347c-efdd-4bc5-a112-98ec17fdf31c"
    
    # Test endpoint existence (we expect authentication error, not 404)
    test_payload = {
        "documents": [
            {
                "chunk_id": "test-chunk-1", 
                "content": "This is a test document chunk",
                "chunk_index": 0,
                "total_chunks": 1,
                "metadata": {
                    "filename": "test.txt",
                    "start_position": 0,
                    "end_position": 100,
                    "chunking_strategy": "test"
                }
            }
        ],
        "processing_type": "enhanced_chunks",
        "chunking_strategy": "jsonl_aware",
        "source": "endpoint_test"
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer service-backend-token"
    }
    
    try:
        print(f"Testing endpoint: POST /api/vectors/projects/{project_id}/documents")
        response = requests.post(
            f"http://localhost:8005/api/vectors/projects/{project_id}/documents",
            json=test_payload,
            headers=headers,
            timeout=10
        )
        
        print(f"Response Status: {response.status_code}")
        
        if response.status_code == 404:
            print("❌ STILL GETTING 404 - Endpoint doesn't exist")
            return False
        elif response.status_code in [200, 401, 422]:  # 200=success, 401=auth error, 422=validation error
            print("✅ Endpoint exists and is accessible!")
            print(f"Response: {response.text[:200]}")
            return True
        else:
            print(f"⚠️  Unexpected status: {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return True  # Endpoint exists, just other error
            
    except Exception as e:
        print(f"❌ Error testing endpoint: {e}")
        return False

def trigger_document_processing():
    """Trigger a small document processing to test the fix end-to-end"""
    
    print("\n🔄 Testing End-to-End Document Processing...")
    
    project_id = "7d1e347c-efdd-4bc5-a112-98ec17fdf31c"
    
    # Get list of files to process
    try:
        response = requests.get(f"http://localhost:8010/api/storage/projects/{project_id}/files/uploads_raw")
        if response.status_code == 200:
            files = response.json()
            if files:
                # Take the first file for testing
                test_file = files[0]
                print(f"Found test file: {test_file}")
                
                # Trigger processing
                process_payload = {
                    "file_names": [test_file]
                }
                
                headers = {
                    "Content-Type": "application/json",
                    "X-Correlation-ID": "endpoint-fix-test"
                }
                
                response = requests.post(
                    f"http://localhost:8003/api/documents/{project_id}/process-selected",
                    json=process_payload,
                    headers=headers,
                    timeout=10
                )
                
                print(f"Document processing triggered: {response.status_code}")
                if response.status_code == 200:
                    result = response.json()
                    job_id = result.get("job_id")
                    print(f"✅ Processing started with job ID: {job_id}")
                    print("📋 Monitor the logs to see if vector service gets called successfully!")
                    print("🔍 Look for 'Enhanced vector integration successful' in document service logs")
                    return True
                else:
                    print(f"❌ Failed to start processing: {response.text}")
                    return False
            else:
                print("⚠️  No files found to process")
                return False
        else:
            print(f"❌ Failed to get file list: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error in document processing test: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("🔧 Vector Service Endpoint Fix Verification")
    print("=" * 60)
    
    # Test 1: Endpoint accessibility
    endpoint_ok = test_vector_service_endpoint()
    
    if endpoint_ok:
        print("\n" + "=" * 60)
        # Test 2: End-to-end processing
        processing_ok = trigger_document_processing()
        
        print("\n" + "=" * 60)
        if endpoint_ok and processing_ok:
            print("✅ ENDPOINT FIX SUCCESSFUL!")
            print("The vector service endpoint is now accessible.")
            print("Document processing should now complete the full pipeline!")
        else:
            print("⚠️  Partial success - endpoint fixed but processing needs checking")
    else:
        print("\n❌ Endpoint still has issues")
    
    print("=" * 60)