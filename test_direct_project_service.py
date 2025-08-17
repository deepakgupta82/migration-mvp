#!/usr/bin/env python3
"""
Direct test of Project Service to isolate the 422 error
"""

import requests
import json

def test_direct_project_service():
    url = "http://localhost:8002/projects"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer service-backend-token"
    }
    
    # Test 1: Minimal payload with required fields
    payload1 = {
        "name": "direct_test_1",
        "description": "Testing direct service",
        "client_name": "Test Client Corp"
    }
    
    print("🧪 Testing Direct Project Service")
    print("=" * 40)
    print(f"URL: {url}")
    print(f"Headers: {headers}")
    print(f"Payload: {json.dumps(payload1, indent=2)}")
    
    try:
        response = requests.post(url, headers=headers, json=payload1, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 201:
            print("✅ Direct project creation successful!")
            return response.json()
        else:
            print(f"❌ Direct project creation failed: {response.status_code}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return None

def test_project_service_health():
    url = "http://localhost:8002/health"
    try:
        response = requests.get(url, timeout=5)
        print(f"Health check: {response.status_code} - {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Direct Project Service Test")
    print("=" * 40)
    
    # First check health
    if test_project_service_health():
        print("✅ Project Service is healthy")
        # Then test project creation
        test_direct_project_service()
    else:
        print("❌ Project Service is not responding")
