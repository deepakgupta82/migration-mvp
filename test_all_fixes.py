#!/usr/bin/env python3
"""
Test script to verify all the fixes are working
"""

import requests
import json
import sys

def test_project_creation():
    """Test project creation with LLM configuration"""
    print("🧪 Testing project creation with LLM configuration...")
    
    # First, get available LLM configurations
    try:
        response = requests.get("http://localhost:8000/llm-configurations")
        if response.status_code == 200:
            llm_configs = response.json()
            if llm_configs:
                config_id = llm_configs[0]['id']
                print(f"✅ Found LLM configuration: {config_id}")
                
                # Create test project
                project_data = {
                    "name": "Test Project - Fix Verification",
                    "description": "Testing LLM configuration assignment",
                    "client_name": "Test Client",
                    "client_contact": "test@example.com",
                    "default_llm_config_id": config_id
                }
                
                response = requests.post(
                    "http://localhost:8000/projects",
                    json=project_data,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    project = response.json()
                    print(f"✅ Project created: {project['id']}")
                    print(f"✅ LLM Provider: {project.get('llm_provider', 'NOT SET')}")
                    print(f"✅ LLM Model: {project.get('llm_model', 'NOT SET')}")
                    print(f"✅ LLM API Key ID: {project.get('llm_api_key_id', 'NOT SET')}")
                    
                    if project.get('llm_provider') and project.get('llm_model'):
                        print("✅ LLM configuration properly assigned!")
                        return project['id']
                    else:
                        print("❌ LLM configuration NOT assigned!")
                        return None
                else:
                    print(f"❌ Project creation failed: {response.status_code} - {response.text}")
                    return None
            else:
                print("❌ No LLM configurations found")
                return None
        else:
            print(f"❌ Failed to get LLM configurations: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error testing project creation: {e}")
        return None

def test_weaviate_connection():
    """Test Weaviate connection"""
    print("🧪 Testing Weaviate connection...")
    
    try:
        response = requests.get("http://localhost:8080/v1/meta")
        if response.status_code == 200:
            print("✅ Weaviate is accessible")
            return True
        else:
            print(f"❌ Weaviate not accessible: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Weaviate connection error: {e}")
        return False

def test_graph_api(project_id):
    """Test graph API endpoint"""
    print(f"🧪 Testing graph API for project {project_id}...")
    
    try:
        response = requests.get(f"http://localhost:8000/api/projects/{project_id}/graph")
        if response.status_code == 200:
            graph_data = response.json()
            node_count = len(graph_data.get('nodes', []))
            edge_count = len(graph_data.get('edges', []))
            print(f"✅ Graph API working: {node_count} nodes, {edge_count} edges")
            return True
        else:
            print(f"❌ Graph API failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Graph API error: {e}")
        return False

def test_service_health():
    """Test all service health endpoints"""
    print("🧪 Testing service health...")
    
    services = {
        'Backend': 'http://localhost:8000/health',
        'Project Service': 'http://localhost:8002/health',
        'Reporting Service': 'http://localhost:8003/health'
    }
    
    all_healthy = True
    for service_name, url in services.items():
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print(f"✅ {service_name}: Healthy")
            else:
                print(f"⚠️  {service_name}: Unhealthy (HTTP {response.status_code})")
                all_healthy = False
        except requests.exceptions.RequestException:
            print(f"❌ {service_name}: Connection failed")
            all_healthy = False
    
    return all_healthy

def main():
    """Run all tests"""
    print("🔄 Starting comprehensive fix verification...")
    print("=" * 60)
    
    results = {}
    test_project_id = None
    
    # Test 1: Service Health
    results['service_health'] = test_service_health()
    print()
    
    # Test 2: Weaviate Connection
    results['weaviate'] = test_weaviate_connection()
    print()
    
    # Test 3: Project Creation with LLM
    test_project_id = test_project_creation()
    results['project_creation'] = test_project_id is not None
    print()
    
    # Test 4: Graph API (if project was created)
    if test_project_id:
        results['graph_api'] = test_graph_api(test_project_id)
    else:
        results['graph_api'] = False
        print("⏭️  Skipping graph API test (no test project)")
    print()
    
    # Summary
    print("=" * 60)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name.replace('_', ' ').title()}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL FIXES VERIFIED SUCCESSFULLY!")
        success = True
    else:
        print("⚠️  SOME ISSUES STILL NEED ATTENTION")
        success = False
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
