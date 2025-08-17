#!/usr/bin/env python3
"""
Debug upload through API Gateway
"""

import requests
import json

def test_upload():
    project_id = "151859dd-98a1-47f7-b980-31759e29c70f"
    gateway_url = "http://localhost:8000"
    
    print("🔍 Testing Upload Through API Gateway")
    print("=" * 50)
    
    # Test 1: Check if project exists
    print("\n1. Check Project Exists")
    try:
        response = requests.get(
            f"{gateway_url}/api/projects/{project_id}",
            headers={"Authorization": "Bearer service-backend-token"},
            timeout=10
        )
        print(f"   Project Status: {response.status_code}")
        if response.status_code == 200:
            project = response.json()
            print(f"   Project Name: {project.get('name', 'Unknown')}")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   ❌ Project check failed: {e}")
        return
    
    # Test 2: Test upload with detailed debugging
    print("\n2. Test Upload")
    try:
        # Create test file content
        test_content = "This is a test file for debugging upload issues."
        
        # Prepare files for upload
        files = {
            'files': ('debug-test.txt', test_content, 'text/plain')
        }
        
        headers = {
            "Authorization": "Bearer service-backend-token"
        }
        
        print(f"   Uploading to: {gateway_url}/api/projects/{project_id}/upload")
        print(f"   Headers: {list(headers.keys())}")
        print(f"   Files: {list(files.keys())}")
        
        response = requests.post(
            f"{gateway_url}/api/projects/{project_id}/upload",
            headers=headers,
            files=files,
            timeout=30
        )
        
        print(f"   Upload Status: {response.status_code}")
        print(f"   Response Headers: {dict(response.headers)}")
        print(f"   Response: {response.text}")
        
        if response.status_code == 422:
            print("   ❌ 422 Unprocessable Content - likely files parameter issue")
        elif response.status_code == 200:
            print("   ✅ Upload successful!")
        else:
            print(f"   ❌ Unexpected status: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Upload failed: {e}")
    
    # Test 3: Test direct document service
    print("\n3. Test Direct Document Service")
    try:
        files = {
            'files': ('debug-test-direct.txt', test_content, 'text/plain')
        }
        
        response = requests.post(
            f"http://localhost:8004/api/documents/{project_id}/upload",
            files=files,
            timeout=15
        )
        
        print(f"   Direct Upload Status: {response.status_code}")
        print(f"   Direct Response: {response.text}")
        
    except Exception as e:
        print(f"   ❌ Direct upload failed: {e}")

if __name__ == "__main__":
    test_upload()
