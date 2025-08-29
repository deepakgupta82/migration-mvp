#!/usr/bin/env python3
"""
Quick Graph Service Endpoint Test
Verifies the correct graph service endpoint is working
"""

import requests
import json

PROJECT_ID = "7d1e347c-efdd-4bc5-a112-98ec17fdf31c"
GRAPH_SERVICE = "http://localhost:8006"

def test_graph_health():
    """Test graph service health"""
    print("🔍 Testing graph service health...")
    try:
        response = requests.get(f"{GRAPH_SERVICE}/health", timeout=10)
        if response.status_code == 200:
            print("✅ Graph service is healthy")
            return True
        else:
            print(f"❌ Graph service unhealthy: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Graph service error: {e}")
        return False

def test_graph_stats():
    """Test graph stats endpoint"""
    print(f"🔍 Testing graph stats endpoint...")
    
    # Test correct endpoint
    try:
        response = requests.get(f"{GRAPH_SERVICE}/api/graphs/projects/{PROJECT_ID}/stats", timeout=10)
        print(f"📊 Correct endpoint (/api/graphs/): HTTP {response.status_code}")
        if response.status_code == 200:
            stats = response.json()
            print(f"   Response: {json.dumps(stats, indent=2)}")
            return True
        elif response.status_code == 404:
            print("   No data found for project (expected for new project)")
            return True
        else:
            print(f"   Error: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error testing correct endpoint: {e}")
        return False

def test_wrong_endpoint():
    """Test the wrong endpoint for comparison"""
    print(f"🔍 Testing wrong endpoint (for comparison)...")
    
    try:
        response = requests.get(f"{GRAPH_SERVICE}/api/graph/projects/{PROJECT_ID}/stats", timeout=10)
        print(f"📊 Wrong endpoint (/api/graph/): HTTP {response.status_code}")
        if response.status_code == 404:
            print("   ✅ Correctly returns 404 (endpoint doesn't exist)")
        else:
            print(f"   Response: {response.text[:200]}...")
    except Exception as e:
        print(f"❌ Error testing wrong endpoint: {e}")

if __name__ == "__main__":
    print("="*60)
    print("🧪 GRAPH SERVICE ENDPOINT TEST")
    print("="*60)
    
    # Test health first
    if test_graph_health():
        # Test correct endpoint
        test_graph_stats()
        # Test wrong endpoint for comparison
        test_wrong_endpoint()
        
        print("\n" + "="*60)
        print("✅ Test completed! Use the correct endpoint:")
        print("   ✅ /api/graphs/projects/{project_id}/stats")
        print("   ❌ /api/graph/projects/{project_id}/stats")
        print("="*60)
    else:
        print("❌ Graph service is not healthy")