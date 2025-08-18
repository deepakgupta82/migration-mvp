#!/usr/bin/env python3
"""
Detailed test script to verify document processing is working
"""

import requests
import json
import time
import sys

# Configuration
PROJECT_ID = "cbe6893e-ddd5-42d3-9319-5dce925bfd36"
TEST_FILE = "D1_NBQ Strategy and Budget Plan 2025-2027 vF - Approved - Extract for IT.pdf"
GATEWAY_URL = "http://localhost:8000"
DOCUMENT_URL = "http://localhost:8004"
STORAGE_URL = "http://localhost:8010"

def test_document_service_health():
    """Test document service health"""
    print("🔍 Testing document service health...")
    
    try:
        response = requests.get(f"{DOCUMENT_URL}/health", timeout=5)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            print(f"✅ Document service is healthy")
            return True
        else:
            print(f"❌ Document service health check failed")
            return False
    except Exception as e:
        print(f"❌ Document service not accessible: {e}")
        return False

def test_storage_files():
    """Test storage service file listing"""
    print(f"\n📁 Testing storage service file listing...")
    
    try:
        headers = {"Authorization": "Bearer service-backend-token"}
        response = requests.get(
            f"{STORAGE_URL}/api/storage/projects/{PROJECT_ID}/files/uploads_raw",
            headers=headers,
            timeout=10
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            files = data.get('files', [])
            print(f"✅ Found {len(files)} files in uploads_raw")
            
            # Check if our test file exists
            file_found = False
            for file_info in files:
                filename = file_info.get('filename') if isinstance(file_info, dict) else file_info
                if filename == TEST_FILE:
                    file_found = True
                    print(f"✅ Test file found: {filename}")
                    break
            
            if not file_found:
                print(f"❌ Test file '{TEST_FILE}' not found")
                print(f"Available files: {[f.get('filename') if isinstance(f, dict) else f for f in files]}")
            
            return file_found
        else:
            print(f"❌ Storage listing failed: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Storage service error: {e}")
        return False

def test_document_processing_direct():
    """Test document service directly"""
    print(f"\n⚙️ Testing document service directly...")
    
    try:
        headers = {"Authorization": "Bearer service-backend-token"}
        request_data = {
            "file_names": [TEST_FILE],
            "reprocess": False
        }
        
        response = requests.post(
            f"{DOCUMENT_URL}/api/documents/{PROJECT_ID}/process-selected",
            json=request_data,
            headers=headers,
            timeout=30
        )
        
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            job_id = data.get('job_id')
            print(f"✅ Document processing started")
            print(f"Job ID: {job_id}")
            print(f"Status: {data.get('status')}")
            print(f"Files to process: {data.get('files_to_process')}")
            
            # Wait a bit and check status
            if job_id:
                time.sleep(5)
                return test_processing_status(job_id)
            
            return True
        else:
            print(f"❌ Document processing failed: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Document processing error: {e}")
        return False

def test_processing_status(job_id):
    """Test processing status endpoint"""
    print(f"\n📊 Testing processing status for job {job_id}...")
    
    try:
        headers = {"Authorization": "Bearer service-backend-token"}
        response = requests.get(
            f"{DOCUMENT_URL}/api/documents/{PROJECT_ID}/status/{job_id}",
            headers=headers,
            timeout=10
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Status retrieved successfully")
            print(f"Job Status: {data.get('status')}")
            print(f"Processed Files: {data.get('processed_files', 0)}")
            print(f"Failed Files: {data.get('failed_files', 0)}")
            print(f"Current File: {data.get('current_file', 'None')}")
            
            # Check if processing is complete
            if data.get('status') in ['completed', 'completed_with_errors']:
                print(f"✅ Processing completed")
                return True
            elif data.get('status') == 'processing':
                print(f"⏳ Processing in progress...")
                return True
            else:
                print(f"⚠️ Processing status: {data.get('status')}")
                return True
        else:
            print(f"❌ Status check failed: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Status check error: {e}")
        return False

def test_parsed_files():
    """Test if parsed files were created"""
    print(f"\n📄 Testing for parsed files...")
    
    try:
        headers = {"Authorization": "Bearer service-backend-token"}
        response = requests.get(
            f"{STORAGE_URL}/api/storage/projects/{PROJECT_ID}/files/uploads_parsed",
            headers=headers,
            timeout=10
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            files = data.get('files', [])
            print(f"✅ Found {len(files)} files in uploads_parsed")
            
            # Look for markdown version of our test file
            expected_md_file = TEST_FILE.replace('.pdf', '.md')
            md_file_found = False
            
            for file_info in files:
                filename = file_info.get('filename') if isinstance(file_info, dict) else file_info
                if filename == expected_md_file:
                    md_file_found = True
                    print(f"✅ Parsed file found: {filename}")
                    if isinstance(file_info, dict):
                        print(f"   Size: {file_info.get('size')} bytes")
                    break
            
            if not md_file_found:
                print(f"❌ Parsed file '{expected_md_file}' not found")
                print(f"Available parsed files: {[f.get('filename') if isinstance(f, dict) else f for f in files]}")
            
            return md_file_found
        else:
            print(f"❌ Parsed files listing failed: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Parsed files check error: {e}")
        return False

def main():
    """Run detailed document processing tests"""
    print("🧪 Detailed Document Processing Tests")
    print("=" * 60)
    
    tests = [
        ("Document Service Health", test_document_service_health),
        ("Storage Files Check", test_storage_files),
        ("Document Processing Direct", test_document_processing_direct),
        ("Parsed Files Check", test_parsed_files)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results[test_name] = False
        
        time.sleep(2)  # Pause between tests
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 DETAILED TEST RESULTS")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed >= 3:  # Allow for some tolerance
        print("🎉 Document processing appears to be working!")
        return 0
    else:
        print("⚠️ Document processing may have issues.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
