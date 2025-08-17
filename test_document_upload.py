#!/usr/bin/env python3
"""
Test document upload functionality for specific project
"""

import requests
import os

def test_document_upload():
    print("🔧 Testing Document Upload Functionality")
    print("=" * 50)
    
    project_id = "465bef05-3edd-41a2-8451-80d19855ffb4"
    print(f"Testing with project ID: {project_id}")
    
    # Create a test file
    test_file_content = "This is a test document for upload testing.\nIt contains some sample content to verify the upload process."
    test_file_path = "test_upload_document.txt"
    
    with open(test_file_path, 'w') as f:
        f.write(test_file_content)
    
    print(f"Created test file: {test_file_path}")
    
    # Test 1: Check document service health
    print(f"\n1. Checking document service health...")
    try:
        response = requests.get("http://localhost:8004/health", timeout=10)
        if response.status_code == 200:
            print(f"   ✅ Document service is healthy")
        else:
            print(f"   ❌ Document service health check failed: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Document service health check error: {e}")
    
    # Test 2: Direct document service upload
    print(f"\n2. Testing direct document service upload...")
    try:
        with open(test_file_path, 'rb') as f:
            files = {'files': (test_file_path, f, 'text/plain')}  # Changed from 'file' to 'files'
            response = requests.post(
                f"http://localhost:8004/api/documents/{project_id}/upload",
                files=files,
                timeout=30
            )
        
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   ✅ Direct upload: SUCCESS")
            result = response.json()
            print(f"   Response: {result}")
        else:
            print(f"   ❌ Direct upload failed: {response.text}")
            
    except Exception as e:
        print(f"   ❌ Direct upload error: {e}")
    
    # Test 3: API Gateway upload
    print(f"\n3. Testing API Gateway upload...")
    try:
        with open(test_file_path, 'rb') as f:
            files = {'files': (f"gateway_{test_file_path}", f, 'text/plain')}  # Changed from 'file' to 'files'
            response = requests.post(
                f"http://localhost:8000/api/projects/{project_id}/upload",
                headers={"Authorization": "Bearer service-backend-token"},
                files=files,
                timeout=30
            )
        
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   ✅ API Gateway upload: SUCCESS")
            result = response.json()
            print(f"   Response: {result}")
        else:
            print(f"   ❌ API Gateway upload failed: {response.text}")
            
    except Exception as e:
        print(f"   ❌ API Gateway upload error: {e}")
    
    # Test 4: Check uploaded files
    print(f"\n4. Checking uploaded files...")
    try:
        response = requests.get(
            f"http://localhost:8004/api/documents/{project_id}/files",
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            total_files = data.get('counts', {}).get('total_uploaded', 0)
            print(f"   ✅ Found {total_files} uploaded files")
            
            uploaded_files = data.get('uploaded_files', [])
            for file_info in uploaded_files:
                print(f"      - {file_info.get('filename', 'Unknown')} ({file_info.get('size', 0)} bytes)")
        else:
            print(f"   ❌ Failed to check files: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Check files error: {e}")
    
    # Cleanup
    try:
        os.remove(test_file_path)
        print(f"\nCleaned up test file: {test_file_path}")
    except:
        pass

if __name__ == "__main__":
    test_document_upload()
