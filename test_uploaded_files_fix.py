#!/usr/bin/env python3
"""
Test script to verify uploaded files endpoint is working correctly
"""

import requests
import json

# Test configuration
PROJECT_ID = "e3a71711-1856-443e-8730-c52a3359a1f7"  # The project from the logs
GATEWAY_URL = "http://localhost:8000"
DOCUMENT_URL = "http://localhost:8004"
STORAGE_URL = "http://localhost:8010"

def test_storage_service_direct():
    """Test storage service directly"""
    print("🔍 Testing Storage Service directly...")
    
    try:
        headers = {"Authorization": "Bearer service-backend-token"}
        response = requests.get(
            f"{STORAGE_URL}/api/storage/projects/{PROJECT_ID}/files/uploads_raw",
            headers=headers,
            timeout=10
        )
        
        print(f"Storage Service Response: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            files = data.get('files', [])
            print(f"✅ Storage service found {len(files)} files")
            for i, file_info in enumerate(files[:3]):
                if isinstance(file_info, dict):
                    print(f"   {i+1}. {file_info.get('filename', 'Unknown')} ({file_info.get('size', 0)} bytes)")
                else:
                    print(f"   {i+1}. {file_info}")
            return True
        else:
            print(f"❌ Storage service error: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Storage service exception: {e}")
        return False

def test_document_service_direct():
    """Test document service directly"""
    print("\n🔍 Testing Document Service directly...")
    
    try:
        headers = {"Authorization": "Bearer service-backend-token"}
        response = requests.get(
            f"{DOCUMENT_URL}/api/documents/{PROJECT_ID}/files",
            headers=headers,
            timeout=10
        )
        
        print(f"Document Service Response: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            uploaded_files = data.get('uploaded_files', [])
            processed_files = data.get('processed_files', [])
            pending_files = data.get('pending_files', [])
            
            print(f"✅ Document service response:")
            print(f"   Uploaded files: {len(uploaded_files)}")
            print(f"   Processed files: {len(processed_files)}")
            print(f"   Pending files: {len(pending_files)}")
            
            if uploaded_files:
                print(f"   First few uploaded files: {uploaded_files[:3]}")
            
            return True
        else:
            print(f"❌ Document service error: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Document service exception: {e}")
        return False

def test_gateway_uploaded_files():
    """Test gateway uploaded files endpoint"""
    print("\n🔍 Testing Gateway uploaded-files endpoint...")
    
    try:
        response = requests.get(
            f"{GATEWAY_URL}/api/projects/{PROJECT_ID}/uploaded-files",
            timeout=10
        )
        
        print(f"Gateway Response: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Gateway response structure:")
            print(f"   Keys: {list(data.keys())}")
            
            if 'uploaded_files' in data:
                files = data['uploaded_files']
                print(f"   Found {len(files)} uploaded files")
                if files:
                    print(f"   First few files: {files[:3]}")
            elif 'files' in data:
                files = data['files']
                print(f"   Found {len(files)} files")
                if files:
                    print(f"   First few files: {files[:3]}")
            else:
                print(f"   Response data: {data}")
            
            return True
        else:
            print(f"❌ Gateway error: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Gateway exception: {e}")
        return False

def test_gateway_legacy_uploads():
    """Test legacy uploads endpoint"""
    print("\n🔍 Testing Gateway legacy uploads endpoint...")
    
    try:
        response = requests.get(
            f"{GATEWAY_URL}/api/projects/{PROJECT_ID}/uploads",
            timeout=10
        )
        
        print(f"Legacy Gateway Response: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Legacy gateway response structure:")
            print(f"   Keys: {list(data.keys())}")
            print(f"   Response: {data}")
            return True
        else:
            print(f"❌ Legacy gateway error: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Legacy gateway exception: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Testing Uploaded Files Endpoints")
    print("=" * 60)
    
    tests = [
        ("Storage Service Direct", test_storage_service_direct),
        ("Document Service Direct", test_document_service_direct),
        ("Gateway uploaded-files", test_gateway_uploaded_files),
        ("Gateway legacy uploads", test_gateway_legacy_uploads)
    ]
    
    results = {}
    for test_name, test_func in tests:
        results[test_name] = test_func()
    
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS")
    print("=" * 60)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All endpoints working correctly!")
    else:
        print("⚠️ Some endpoints have issues - check output above")

if __name__ == "__main__":
    main()
