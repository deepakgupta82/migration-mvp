#!/usr/bin/env python3
"""
Test the project creation fix specifically
"""

import requests
import json

def test_project_creation():
    """Test project creation with the fixed schema"""
    print("🧪 Testing Project Creation Fix")
    print("================================")
    
    # Test via API Gateway with the correct schema
    gateway_url = "http://localhost:8000/api/projects/"
    
    # Test with the corrected payload that includes client_name
    project_data = {
        "name": "test_schema_fix",
        "description": "Testing the fixed schema with client_name",
        "client_name": "Test Client Corp",
        "client_contact": "test@client.com"
    }
    
    print(f"Testing: POST {gateway_url}")
    print(f"Payload: {json.dumps(project_data, indent=2)}")
    
    try:
        response = requests.post(gateway_url, json=project_data, timeout=15)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 201:
            print("✅ SUCCESS: Project creation now works!")
            project_response = response.json()
            print(f"Created project: {project_response.get('name')} (ID: {project_response.get('id')})")
            return project_response.get('id')
        elif response.status_code == 422:
            print("❌ FAILED: Still getting schema validation error")
            print(f"Response: {response.text}")
            return None
        elif response.status_code == 401:
            print("⚠️  Authentication issue - need to authenticate first")
            print(f"Response: {response.text}")
            return None
        else:
            print(f"⚠️  Unexpected status: {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error testing project creation: {str(e)}")
        return None

def test_document_upload_with_project(project_id):
    """Test document upload if we have a project ID"""
    if not project_id:
        print("\n⏭️  Skipping document upload test - no project available")
        return
        
    print(f"\n🧪 Testing Document Upload Fix")
    print("===============================")
    
    upload_url = f"http://localhost:8000/api/projects/{project_id}/upload"
    print(f"Testing: POST {upload_url}")
    
    # Create a small test file
    files = {'files': ('test_fix.txt', 'This is a test file for upload testing', 'text/plain')}
    
    try:
        response = requests.post(upload_url, files=files, timeout=15)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ SUCCESS: Document upload now works!")
        elif "No module named 'httpx'" in response.text:
            print("❌ CONFIRMED: httpx dependency still missing")
        else:
            print(f"⚠️  Other issue detected")
            
    except Exception as e:
        print(f"❌ Error testing document upload: {str(e)}")

if __name__ == "__main__":
    print("🔧 Testing Migration Platform Fixes")
    print("====================================\n")
    
    # Test project creation fix
    project_id = test_project_creation()
    
    # Test document upload if project creation worked
    test_document_upload_with_project(project_id)
    
    print(f"\n🏁 Fix testing complete!")
