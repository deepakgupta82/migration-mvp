#!/usr/bin/env python3
"""
Debug upload issue by testing the upload endpoint directly
"""

import requests
import json

def test_upload_debug():
    gateway_url = "http://localhost:8000"
    project_id = "eff73256-7c15-4323-88f4-b72d74276d93"  # From the test
    
    # Test 1: Check if project exists
    print("🔹 Testing project existence...")
    try:
        response = requests.get(
            f"{gateway_url}/api/projects/{project_id}",
            headers={"Authorization": "Bearer service-backend-token"},
            timeout=10
        )
        print(f"   Project check: {response.status_code}")
        if response.status_code == 200:
            project_data = response.json()
            print(f"   Project name: {project_data.get('name', 'Unknown')}")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Exception: {e}")
    
    # Test 2: Try upload with detailed error handling
    print("\n🔹 Testing upload with debug...")
    try:
        test_content = "This is a debug test file for upload testing."
        files = {
            'files': ('debug-test.txt', test_content, 'text/plain')
        }
        
        headers = {
            "Authorization": "Bearer service-backend-token"
        }
        
        response = requests.post(
            f"{gateway_url}/api/projects/{project_id}/upload",
            headers=headers,
            files=files,
            timeout=30
        )
        
        print(f"   Upload status: {response.status_code}")
        print(f"   Response: {response.text}")
        
        if response.status_code != 200:
            print(f"   Headers sent: {headers}")
            print(f"   Files sent: {list(files.keys())}")
            
    except Exception as e:
        print(f"   Upload exception: {e}")
    
    # Test 3: Check document service directly
    print("\n🔹 Testing document service directly...")
    try:
        response = requests.get(
            "http://localhost:8004/health",
            timeout=10
        )
        print(f"   Document service health: {response.status_code}")
        print(f"   Response: {response.text}")
    except Exception as e:
        print(f"   Document service exception: {e}")
    
    # Test 4: Check storage service directly
    print("\n🔹 Testing storage service directly...")
    try:
        response = requests.get(
            "http://localhost:8010/health",
            timeout=10
        )
        print(f"   Storage service health: {response.status_code}")
        print(f"   Response: {response.text}")
    except Exception as e:
        print(f"   Storage service exception: {e}")

if __name__ == "__main__":
    test_upload_debug()
