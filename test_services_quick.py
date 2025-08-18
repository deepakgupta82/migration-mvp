#!/usr/bin/env python3
"""
Quick test to verify services are running
"""

import requests
import sys

def test_services():
    """Test if all services are running"""
    services = [
        ("Gateway", "http://localhost:8000/health"),
        ("Document", "http://localhost:8004/health"),
        ("Vector", "http://localhost:8005/health"),
        ("Graph", "http://localhost:8006/health"),
        ("Storage", "http://localhost:8010/health")
    ]
    
    print("🔍 Testing service availability...")
    
    all_healthy = True
    for name, url in services:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print(f"✅ {name} service is running")
            else:
                print(f"❌ {name} service returned {response.status_code}")
                all_healthy = False
        except Exception as e:
            print(f"❌ {name} service is not accessible: {e}")
            all_healthy = False
    
    return all_healthy

def test_project_files():
    """Test if project has uploaded files"""
    project_id = "8a7feed2-85d5-47f5-a6a4-e4c5c82f9de5"
    
    try:
        response = requests.get(f"http://localhost:8000/api/projects/{project_id}/uploaded-files", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            file_count = data.get('count', 0)
            print(f"✅ Project has {file_count} uploaded files")
            if file_count > 0:
                files = data.get('files', [])
                print(f"   First few files: {files[:3]}")
            return file_count > 0
        else:
            print(f"❌ Failed to get project files: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error getting project files: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Quick Service and Project Test")
    print("=" * 50)
    
    services_ok = test_services()
    print()
    files_ok = test_project_files()
    
    print("\n" + "=" * 50)
    if services_ok and files_ok:
        print("✅ Ready for comprehensive testing!")
        sys.exit(0)
    else:
        print("❌ Issues detected - fix before running full tests")
        sys.exit(1)
