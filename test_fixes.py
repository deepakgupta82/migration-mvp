#!/usr/bin/env python3
"""
Test script to verify the platform fixes
"""
import requests
import json

def test_llm_configuration():
    """Test LLM configuration for the project"""
    project_id = '3b50a477-701f-427e-9f26-20b81d5ff00e'
    backend_url = 'http://localhost:8000'
    
    print("=== Testing LLM Configuration ===")
    print(f"Project ID: {project_id}")
    
    try:
        response = requests.post(f'{backend_url}/api/projects/{project_id}/test-llm', timeout=30)
        print(f"LLM Test Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"LLM Test Result: {result.get('status')} - {result.get('message')}")
            return True
        else:
            print(f"LLM Test Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"LLM Test Exception: {e}")
        return False

def test_reporting_service():
    """Test reporting service on port 8001"""
    print("\n=== Testing Reporting Service ===")
    
    try:
        response = requests.get('http://localhost:8001/health', timeout=10)
        print(f"Reporting Service Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Reporting Service Health: {result}")
            return True
        else:
            print(f"Reporting Service Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"Reporting Service Exception: {e}")
        return False

def test_graph_database():
    """Test Neo4j graph database connection"""
    print("\n=== Testing Graph Database ===")
    
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', 'password'))
        
        with driver.session() as session:
            result = session.run('RETURN 1 as test')
            record = result.single()
            if record and record['test'] == 1:
                print("Graph Database: Connected successfully")
                driver.close()
                return True
            else:
                print("Graph Database: Connection test failed")
                driver.close()
                return False
                
    except Exception as e:
        print(f"Graph Database Exception: {e}")
        return False

def test_project_service():
    """Test project service with authentication"""
    print("\n=== Testing Project Service ===")
    
    try:
        headers = {"Authorization": "Bearer service-backend-token"}
        response = requests.get('http://localhost:8002/llm-configurations', headers=headers, timeout=10)
        print(f"Project Service Status: {response.status_code}")
        
        if response.status_code == 200:
            configs = response.json()
            print(f"Found {len(configs)} LLM configurations")
            
            # Find Gemini config
            gemini_configs = [c for c in configs if c.get('provider') == 'gemini']
            if gemini_configs:
                print(f"Gemini configurations found: {len(gemini_configs)}")
                for config in gemini_configs:
                    print(f"  - {config.get('name')} ({config.get('id')})")
                return True
            else:
                print("No Gemini configurations found")
                return False
        else:
            print(f"Project Service Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"Project Service Exception: {e}")
        return False

def main():
    """Run all tests"""
    print("🔧 Testing Platform Fixes")
    print("=" * 50)
    
    tests = [
        ("Reporting Service", test_reporting_service),
        ("Graph Database", test_graph_database),
        ("Project Service", test_project_service),
        ("LLM Configuration", test_llm_configuration),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"Test {test_name} failed with exception: {e}")
            results[test_name] = False
    
    print("\n" + "=" * 50)
    print("🔍 Test Results Summary:")
    print("=" * 50)
    
    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name}: {status}")
        if not passed:
            all_passed = False
    
    print("=" * 50)
    if all_passed:
        print("🎉 All tests passed! Platform fixes are working correctly.")
    else:
        print("⚠️  Some tests failed. Please check the issues above.")
    
    return all_passed

if __name__ == "__main__":
    main()
