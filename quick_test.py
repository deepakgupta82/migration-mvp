#!/usr/bin/env python3
"""
Quick test of key microservices workflows
"""

import requests
import json
from datetime import datetime

def quick_test():
    gateway_url = "http://localhost:8000"
    
    print("🚀 Quick Microservices Test")
    print("=" * 50)
    
    # Test 1: Health Check
    print("\n1. Health Check")
    try:
        response = requests.get(f"{gateway_url}/health", timeout=10)
        print(f"   ✅ Health: {response.status_code}")
        if response.status_code == 200:
            health_data = response.json()
            for service, status in health_data.get("services", {}).items():
                print(f"   - {service}: {status}")
    except Exception as e:
        print(f"   ❌ Health failed: {e}")
        return
    
    # Test 2: Create Project
    print("\n2. Create Project")
    project_data = {
        "name": f"Quick_Test_{datetime.now().strftime('%H%M%S')}",
        "description": "Quick test project",
        "client_name": "Test Client"
    }
    
    try:
        response = requests.post(
            f"{gateway_url}/api/projects",
            headers={"Authorization": "Bearer service-backend-token"},
            json=project_data,
            timeout=15
        )
        print(f"   ✅ Create Project: {response.status_code}")
        if response.status_code == 200:
            project = response.json()
            project_id = project["id"]
            print(f"   Project ID: {project_id}")
        else:
            print(f"   Response: {response.text}")
            return
    except Exception as e:
        print(f"   ❌ Create Project failed: {e}")
        return
    
    # Test 3: LLM Configurations
    print("\n3. LLM Configurations")
    try:
        response = requests.get(
            f"{gateway_url}/api/llm/configurations",
            headers={"Authorization": "Bearer service-backend-token"},
            timeout=10
        )
        print(f"   ✅ List LLM Configs: {response.status_code}")
        if response.status_code == 200:
            configs = response.json()
            print(f"   Found {len(configs)} configurations")
    except Exception as e:
        print(f"   ❌ LLM Configs failed: {e}")
    
    # Test 4: LLM Test
    print("\n4. LLM Test")
    try:
        response = requests.get(
            f"{gateway_url}/api/llm/test-llm-config",
            headers={"Authorization": "Bearer service-backend-token"},
            timeout=10
        )
        print(f"   ✅ LLM Test: {response.status_code}")
    except Exception as e:
        print(f"   ❌ LLM Test failed: {e}")
    
    # Test 5: LLM Models
    print("\n5. LLM Models")
    try:
        response = requests.get(
            f"{gateway_url}/api/llm/models/gemini",
            headers={"Authorization": "Bearer service-backend-token"},
            timeout=10
        )
        print(f"   ✅ LLM Models: {response.status_code}")
    except Exception as e:
        print(f"   ❌ LLM Models failed: {e}")
    
    # Test 6: File Upload
    print("\n6. File Upload")
    try:
        test_content = "This is a quick test file for upload testing."
        files = {'files': ('quick-test.txt', test_content, 'text/plain')}
        
        response = requests.post(
            f"{gateway_url}/api/projects/{project_id}/upload",
            headers={"Authorization": "Bearer service-backend-token"},
            files=files,
            timeout=15
        )
        print(f"   ✅ File Upload: {response.status_code}")
        if response.status_code != 200:
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"   ❌ File Upload failed: {e}")
    
    # Test 7: List Files
    print("\n7. List Files")
    try:
        response = requests.get(
            f"{gateway_url}/api/projects/{project_id}/uploaded-files",
            headers={"Authorization": "Bearer service-backend-token"},
            timeout=10
        )
        print(f"   ✅ List Files: {response.status_code}")
        if response.status_code == 200:
            files_data = response.json()
            print(f"   Found {len(files_data.get('files', []))} files")
    except Exception as e:
        print(f"   ❌ List Files failed: {e}")
    
    # Test 8: Update Project
    print("\n8. Update Project")
    try:
        update_data = {"description": "Updated description"}
        response = requests.put(
            f"{gateway_url}/api/projects/{project_id}",
            headers={"Authorization": "Bearer service-backend-token"},
            json=update_data,
            timeout=10
        )
        print(f"   ✅ Update Project: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Update Project failed: {e}")
    
    print("\n🏁 Quick Test Complete!")

if __name__ == "__main__":
    quick_test()
