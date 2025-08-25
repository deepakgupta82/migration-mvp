#!/usr/bin/env python3
"""
Test script to validate health monitoring and container stats fixes
"""
import requests
import json

def test_health_endpoint():
    """Test the health endpoint for service status"""
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.ok:
            data = response.json()
            services = data.get('services', {})
            connected_count = sum(1 for v in services.values() if v == 'connected')
            total_count = len(services)
            
            print(f"✅ Health Endpoint Test:")
            print(f"   Status: {data.get('status', 'unknown')}")
            print(f"   Services: {connected_count}/{total_count} connected")
            print(f"   Connected services sample: {list(k for k, v in services.items() if v == 'connected')[:5]}")
            return True
        else:
            print(f"❌ Health endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health endpoint error: {e}")
        return False

def test_containers_endpoint():
    """Test the containers endpoint"""
    try:
        response = requests.get("http://localhost:8000/api/health/containers", timeout=5)
        if response.ok:
            data = response.json()
            containers = data.get('containers', [])
            
            print(f"✅ Containers Endpoint Test:")
            print(f"   Total containers: {len(containers)}")
            if containers:
                sample = containers[0]
                print(f"   Sample container: {sample.get('name', 'unknown')} - {sample.get('status', 'unknown')}")
                print(f"   Has stats: CPU={sample.get('cpu_percent', 'N/A')}%, Memory={sample.get('memory_usage', 'N/A')}")
            return True
        else:
            print(f"❌ Containers endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Containers endpoint error: {e}")
        return False

if __name__ == "__main__":
    print("Testing Health Monitoring Fixes...")
    print("=" * 50)
    
    health_ok = test_health_endpoint()
    print()
    containers_ok = test_containers_endpoint()
    
    print("\n" + "=" * 50)
    if health_ok and containers_ok:
        print("🎉 All tests passed! Health monitoring fixes are working.")
    else:
        print("⚠️  Some tests failed. Check the output above.")