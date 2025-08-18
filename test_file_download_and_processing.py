#!/usr/bin/env python3
"""
Test script to verify file download and document processing functionality
"""

import requests
import json
import time
import sys
import os
from urllib.parse import quote

# Configuration
PROJECT_ID = "3c84076a-39c7-48c2-b261-4c80f56a3d61"
TEST_FILE = "D1_NBQ Strategy and Budget Plan 2025-2027 vF - Approved - Extract for IT.pdf"
GATEWAY_URL = "http://localhost:8000"
STORAGE_URL = "http://localhost:8010"
DOCUMENT_URL = "http://localhost:8004"

def test_service_health():
    """Test if all required services are running"""
    print("🔍 Testing service health...")
    
    services = [
        ("Gateway", f"{GATEWAY_URL}/health"),
        ("Storage", f"{STORAGE_URL}/health"),
        ("Document", f"{DOCUMENT_URL}/health")
    ]
    
    for name, url in services:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print(f"✅ {name} service is running")
            else:
                print(f"❌ {name} service returned {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ {name} service is not accessible: {e}")
            return False
    
    return True

def test_file_listing():
    """Test if uploaded files are listed correctly"""
    print(f"\n📋 Testing file listing for project {PROJECT_ID}...")
    
    try:
        response = requests.get(f"{GATEWAY_URL}/api/projects/{PROJECT_ID}/uploaded-files")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ File listing successful")
            print(f"📁 Found {data.get('count', 0)} files")
            
            files = data.get('files', [])
            if TEST_FILE in files:
                print(f"✅ Test file '{TEST_FILE}' found in uploads")
                return True
            else:
                print(f"❌ Test file '{TEST_FILE}' not found in uploads")
                print(f"Available files: {files}")
                return False
        else:
            print(f"❌ File listing failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ File listing error: {e}")
        return False

def test_file_download():
    """Test file download functionality"""
    print(f"\n⬇️ Testing file download for '{TEST_FILE}'...")
    
    try:
        # URL encode the filename
        encoded_filename = quote(TEST_FILE, safe='')
        download_url = f"{GATEWAY_URL}/api/projects/{PROJECT_ID}/download/{encoded_filename}"
        
        print(f"Download URL: {download_url}")
        
        response = requests.get(download_url, timeout=30)
        
        if response.status_code == 200:
            print(f"✅ File download successful")
            print(f"📄 Content-Type: {response.headers.get('Content-Type')}")
            print(f"📏 Content-Length: {len(response.content)} bytes")
            
            # Save to temp file for verification
            temp_file = f"downloaded_{TEST_FILE}"
            with open(temp_file, 'wb') as f:
                f.write(response.content)
            
            print(f"💾 File saved as '{temp_file}' for verification")
            return True
        else:
            print(f"❌ File download failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ File download error: {e}")
        return False

def test_document_processing():
    """Test document processing functionality"""
    print(f"\n⚙️ Testing document processing for project {PROJECT_ID}...")
    
    try:
        # Test processing selected files
        request_data = {
            "use_project_llm": True,
            "files": [
                {
                    "filename": TEST_FILE,
                    "file_type": "application/pdf"
                }
            ]
        }
        
        response = requests.post(
            f"{GATEWAY_URL}/api/projects/{PROJECT_ID}/process-documents",
            json=request_data,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Document processing initiated successfully")
            print(f"🆔 Job ID: {data.get('job_id')}")
            print(f"📊 Status: {data.get('status')}")
            print(f"📁 Files to process: {data.get('files_to_process')}")
            return True
        else:
            print(f"❌ Document processing failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Document processing error: {e}")
        return False

def test_storage_service_direct():
    """Test storage service directly"""
    print(f"\n🗄️ Testing storage service directly...")
    
    try:
        # Test listing files in uploads_raw
        headers = {"Authorization": "Bearer service-backend-token"}
        response = requests.get(
            f"{STORAGE_URL}/api/storage/projects/{PROJECT_ID}/files/uploads_raw",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Storage service listing successful")
            files = data.get('files', [])
            print(f"📁 Found {len(files)} files in uploads_raw")
            
            # Check if our test file exists
            file_found = False
            for file_info in files:
                if isinstance(file_info, dict):
                    filename = file_info.get('filename')
                    if filename == TEST_FILE:
                        file_found = True
                        print(f"✅ Test file found: {filename}")
                        print(f"📏 Size: {file_info.get('size')} bytes")
                        print(f"📅 Last modified: {file_info.get('last_modified')}")
                        break
                elif isinstance(file_info, str) and file_info == TEST_FILE:
                    file_found = True
                    print(f"✅ Test file found: {file_info}")
                    break
            
            if not file_found:
                print(f"❌ Test file '{TEST_FILE}' not found in storage")
                print(f"Available files: {[f.get('filename') if isinstance(f, dict) else f for f in files]}")
            
            return file_found
        else:
            print(f"❌ Storage service listing failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Storage service error: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Starting File Download and Processing Tests")
    print("=" * 60)
    
    tests = [
        ("Service Health", test_service_health),
        ("Storage Service Direct", test_storage_service_direct),
        ("File Listing", test_file_listing),
        ("File Download", test_file_download),
        ("Document Processing", test_document_processing)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results[test_name] = False
        
        time.sleep(1)  # Brief pause between tests
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! File download and processing are working correctly.")
        return 0
    else:
        print("⚠️ Some tests failed. Check the output above for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
