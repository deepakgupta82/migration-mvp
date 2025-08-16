#!/usr/bin/env python3
"""
Service Health Check Script
Tests all microservices systematically with detailed error reporting
"""

import requests
import json
import time

# Service endpoints
services = {
    "backend": "http://localhost:8000",
    "project": "http://localhost:8002", 
    "reporting": "http://localhost:8003",
    "document": "http://localhost:8004",
    "vector": "http://localhost:8005",
    "graph": "http://localhost:8006",
    "llm": "http://localhost:8007",
    "ai_agent": "http://localhost:8008",
    "websocket": "http://localhost:8009",
    "storage": "http://localhost:8010"
}

def test_service_health(name, base_url):
    """Test service health with detailed error reporting"""
    print(f"\n=== Testing {name.upper()} Service ({base_url}) ===")
    
    try:
        # Test health endpoint
        health_url = f"{base_url}/health"
        print(f"Testing: {health_url}")
        
        response = requests.get(health_url, timeout=15)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            try:
                health_data = response.json()
                print(f"Health Response: {json.dumps(health_data, indent=2)}")
                return True, "Healthy"
            except:
                print(f"Health Response (text): {response.text}")
                return True, "Healthy (non-JSON)"
        else:
            print(f"Error Response: {response.text}")
            return False, f"HTTP {response.status_code}"
            
    except requests.exceptions.ConnectRefused:
        return False, "Connection Refused - Service Not Running"
    except requests.exceptions.Timeout:
        return False, "Timeout - Service Not Responding"
    except Exception as e:
        return False, f"Error: {str(e)}"

def test_project_creation():
    """Test the specific project creation issue"""
    print(f"\n=== Testing Project Creation Issue ===")
    
    # Test via API Gateway
    gateway_url = "http://localhost:8000/api/projects/"
    project_data = {
        "name": "test_project_fix",
        "description": "Testing schema fix"
    }
    
    print(f"Testing: POST {gateway_url}")
    print(f"Payload: {json.dumps(project_data, indent=2)}")
    
    try:
        response = requests.post(gateway_url, json=project_data, timeout=15)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 422:
            print("❌ CONFIRMED: Schema mismatch issue - missing client_name field")
        elif response.status_code == 201:
            print("✅ Project creation works!")
        else:
            print(f"⚠️  Unexpected status: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error testing project creation: {str(e)}")

def test_document_upload():
    """Test document upload to check httpx dependency"""
    print(f"\n=== Testing Document Upload Issue ===")
    
    # First, we need a project ID - let's try to get the list of projects
    try:
        projects_response = requests.get("http://localhost:8000/api/projects/", timeout=15)
        if projects_response.status_code == 200:
            projects = projects_response.json()
            if projects:
                project_id = projects[0]["id"]
                print(f"Using existing project: {project_id}")
                
                # Test upload endpoint
                upload_url = f"http://localhost:8000/api/projects/{project_id}/upload"
                print(f"Testing: POST {upload_url}")
                
                # Create a dummy file for testing
                files = {'files': ('test.txt', 'Test content', 'text/plain')}
                
                response = requests.post(upload_url, files=files, timeout=15)
                print(f"Status Code: {response.status_code}")
                print(f"Response: {response.text}")
                
                if "No module named 'httpx'" in response.text:
                    print("❌ CONFIRMED: httpx dependency missing in document service")
                elif response.status_code == 200:
                    print("✅ Document upload works!")
                else:
                    print(f"⚠️  Other issue: {response.text}")
                    
            else:
                print("No projects available for testing upload")
        else:
            print(f"Cannot get projects list: {projects_response.status_code}")
            
    except Exception as e:
        print(f"❌ Error testing document upload: {str(e)}")

if __name__ == "__main__":
    print("🔍 Migration Platform Service Health Check")
    print("==========================================")
    
    # Test all services
    results = {}
    for name, base_url in services.items():
        is_healthy, status = test_service_health(name, base_url)
        results[name] = {"healthy": is_healthy, "status": status, "url": base_url}
        time.sleep(1)  # Brief pause between tests
    
    # Summary
    print(f"\n📊 HEALTH CHECK SUMMARY")
    print("=======================")
    healthy_count = 0
    for name, result in results.items():
        status_icon = "✅" if result["healthy"] else "❌"
        print(f"{status_icon} {name.upper()}: {result['status']}")
        if result["healthy"]:
            healthy_count += 1
    
    print(f"\nServices Running: {healthy_count}/{len(services)}")
    
    # Test specific issues
    test_project_creation()
    test_document_upload()
    
    print(f"\n🏁 Health check complete!")
