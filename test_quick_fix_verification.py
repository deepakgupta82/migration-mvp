#!/usr/bin/env python3
"""
Quick test to verify the uploaded files fix is working
"""

import requests
import json

# Test with both project IDs from the logs
PROJECT_IDS = [
    "e3a71711-1856-443e-8730-c52a3359a1f7",  # New upload from logs
    "8a7feed2-85d5-47f5-a6a4-e4c5c82f9de5"   # Original test project
]
GATEWAY_URL = "http://localhost:8000"



def main():
    """Run the verification tests"""
    print("🧪 Quick Fix Verification Test")
    print("=" * 50)

    results = {}

    for project_id in PROJECT_IDS:
        print(f"\n🔍 Testing Project: {project_id}")
        print("-" * 60)

        # Test 1: Check if project exists
        project_exists = test_project_exists_for_id(project_id)

        # Test 2: Check uploaded files endpoint
        files_working = test_uploaded_files_endpoint_for_id(project_id)

        results[project_id] = {
            "exists": project_exists,
            "files_working": files_working
        }

    print("\n" + "=" * 50)
    print("📊 OVERALL RESULTS")
    print("=" * 50)

    working_projects = 0
    for project_id, result in results.items():
        status = "✅ WORKING" if result["exists"] and result["files_working"] else "❌ ISSUES"
        print(f"{status} {project_id[:8]}...")
        if result["exists"] and result["files_working"]:
            working_projects += 1

    if working_projects > 0:
        print(f"\n🎉 {working_projects}/{len(PROJECT_IDS)} projects working correctly!")
        print("   The uploaded files should now appear in the frontend.")
    else:
        print("\n⚠️ No projects working correctly - check service connectivity")

def test_project_exists_for_id(project_id):
    """Test if a specific project exists"""
    try:
        response = requests.get(f"{GATEWAY_URL}/api/projects/{project_id}", timeout=10)
        if response.status_code == 200:
            project = response.json()
            print(f"   ✅ Project exists: {project.get('name', 'Unknown')}")
            return True
        else:
            print(f"   ❌ Project not found: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return False

def test_uploaded_files_endpoint_for_id(project_id):
    """Test uploaded files endpoint for a specific project"""
    try:
        response = requests.get(f"{GATEWAY_URL}/api/projects/{project_id}/uploaded-files", timeout=10)

        if response.status_code == 200:
            data = response.json()
            if 'files' in data and 'count' in data:
                count = data['count']
                print(f"   ✅ Files endpoint working: {count} files found")
                return True
            else:
                print(f"   ❌ Wrong response format")
                return False
        else:
            print(f"   ❌ Endpoint error: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return False

if __name__ == "__main__":
    main()
