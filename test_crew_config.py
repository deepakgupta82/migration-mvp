#!/usr/bin/env python3
"""
Test script for crew configuration API endpoints
"""
import requests
import json
import time

def test_crew_config_api():
    """Test the crew configuration API endpoints"""
    base_url = "http://localhost:8000"
    
    print("🧪 Testing Crew Configuration API")
    print("=" * 50)
    
    # Test 1: Get crew definitions
    print("\n1. Testing GET /api/crew-definitions")
    try:
        response = requests.get(f"{base_url}/api/crew-definitions")
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                config_data = data['data']
                stats = config_data.get('statistics', {})
                validation = config_data.get('validation', {})
                
                print(f"✅ Success!")
                print(f"   Agents: {stats.get('agents_count', 0)}")
                print(f"   Tasks: {stats.get('tasks_count', 0)}")
                print(f"   Crews: {stats.get('crews_count', 0)}")
                print(f"   Tools: {stats.get('tools_count', 0)}")
                
                if validation.get('errors'):
                    print(f"   ❌ Errors: {len(validation['errors'])}")
                    for error in validation['errors']:
                        print(f"      - {error}")
                
                if validation.get('warnings'):
                    print(f"   ⚠️  Warnings: {len(validation['warnings'])}")
                    for warning in validation['warnings']:
                        print(f"      - {warning}")
                
                return True
            else:
                print(f"❌ API returned success=false")
                return False
        else:
            print(f"❌ HTTP Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

def test_available_tools_api():
    """Test the available tools API endpoint"""
    base_url = "http://localhost:8000"
    
    print("\n2. Testing GET /api/available-tools")
    try:
        response = requests.get(f"{base_url}/api/available-tools")
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                tools = data['data']
                print(f"✅ Success! Found {len(tools)} tools:")
                for tool in tools:
                    print(f"   - {tool.get('name', 'Unknown')} ({tool.get('id', 'no-id')})")
                return True
            else:
                print(f"❌ API returned success=false")
                return False
        else:
            print(f"❌ HTTP Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

def test_statistics_api():
    """Test the statistics API endpoint"""
    base_url = "http://localhost:8000"
    
    print("\n3. Testing GET /api/crew-definitions/statistics")
    try:
        response = requests.get(f"{base_url}/api/crew-definitions/statistics")
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                stats_data = data['data']
                stats = stats_data.get('statistics', {})
                validation = stats_data.get('validation', {})
                
                print(f"✅ Success!")
                print(f"   Statistics: {stats}")
                print(f"   Validation errors: {len(validation.get('errors', []))}")
                print(f"   Validation warnings: {len(validation.get('warnings', []))}")
                return True
            else:
                print(f"❌ API returned success=false")
                return False
        else:
            print(f"❌ HTTP Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

def test_reload_api():
    """Test the reload API endpoint"""
    base_url = "http://localhost:8000"
    
    print("\n4. Testing POST /api/crew-definitions/reload")
    try:
        response = requests.post(f"{base_url}/api/crew-definitions/reload")
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print(f"✅ Success! {data.get('message', 'Reloaded')}")
                stats = data.get('statistics', {})
                print(f"   Post-reload stats: {stats}")
                return True
            else:
                print(f"❌ API returned success=false")
                return False
        else:
            print(f"❌ HTTP Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

def test_yaml_file_exists():
    """Test if the YAML file exists and is readable"""
    import os
    from pathlib import Path
    
    print("\n5. Testing YAML file accessibility")
    yaml_path = Path("backend/crew_definitions.yaml")
    
    if yaml_path.exists():
        print(f"✅ YAML file exists: {yaml_path}")
        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                content = f.read()
                print(f"   File size: {len(content)} characters")
                
                # Basic YAML structure check
                if 'agents:' in content and 'tasks:' in content and 'crews:' in content:
                    print("   ✅ Contains expected sections (agents, tasks, crews)")
                    return True
                else:
                    print("   ❌ Missing expected sections")
                    return False
        except Exception as e:
            print(f"   ❌ Error reading file: {e}")
            return False
    else:
        print(f"❌ YAML file not found: {yaml_path}")
        return False

def main():
    """Run all tests"""
    print("🔧 Testing Crew Configuration Implementation")
    print("=" * 60)
    
    tests = [
        ("YAML File Check", test_yaml_file_exists),
        ("Crew Definitions API", test_crew_config_api),
        ("Available Tools API", test_available_tools_api),
        ("Statistics API", test_statistics_api),
        ("Reload API", test_reload_api),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"Test {test_name} failed with exception: {e}")
            results[test_name] = False
    
    print("\n" + "=" * 60)
    print("🔍 Test Results Summary:")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name}: {status}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    if all_passed:
        print("🎉 All tests passed! Crew configuration API is working correctly.")
        print("\n📋 Next Steps:")
        print("1. Open http://localhost:3000/settings and go to AI Agents tab")
        print("2. Check that real data is displayed instead of static placeholders")
        print("3. Open http://localhost:3000/settings/agents for the crew editor")
        print("4. Verify WebSocket connection shows 'Live' status")
    else:
        print("⚠️  Some tests failed. Please check the issues above.")
        print("\n🔧 Troubleshooting:")
        print("1. Make sure the backend service is running on port 8000")
        print("2. Check that crew_definitions.yaml exists in backend directory")
        print("3. Verify PyYAML is installed: pip install pyyaml")
    
    return all_passed

if __name__ == "__main__":
    main()
