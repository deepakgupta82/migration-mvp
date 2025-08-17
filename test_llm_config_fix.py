#!/usr/bin/env python3
"""
Test LLM Configuration creation with numeric values
"""

import requests
import json

def test_llm_config_creation():
    print("🔧 Testing LLM Configuration Creation Fix")
    print("=" * 50)
    
    # Test data with numeric values (as sent by frontend)
    llm_config_data = {
        "name": "Test_Gemini_Fix",
        "provider": "gemini",
        "model": "gemini-2.5-pro",
        "api_key": "AIzaSyDcP6test_key_for_validation",
        "temperature": 0.7,  # Number, not string
        "max_tokens": 32000,  # Number, not string
        "description": "Test config to verify schema fix"
    }
    
    print(f"📤 Sending LLM config with numeric values:")
    print(f"   temperature: {llm_config_data['temperature']} (type: {type(llm_config_data['temperature'])})")
    print(f"   max_tokens: {llm_config_data['max_tokens']} (type: {type(llm_config_data['max_tokens'])})")
    
    # Test 1: Direct project service call
    print(f"\n1. Testing Direct Project Service")
    try:
        response = requests.post(
            "http://localhost:8002/llm-configurations",
            headers={
                "Authorization": "Bearer service-backend-token",
                "Content-Type": "application/json"
            },
            json=llm_config_data,
            timeout=15
        )
        
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   ✅ Direct service: SUCCESS")
            result = response.json()
            print(f"   Created config ID: {result.get('id', 'Unknown')}")
        else:
            print(f"   ❌ Direct service failed: {response.text}")
            
    except Exception as e:
        print(f"   ❌ Direct service error: {e}")
    
    # Test 2: API Gateway call
    print(f"\n2. Testing API Gateway")
    try:
        response = requests.post(
            "http://localhost:8000/api/llm/configurations",
            headers={
                "Authorization": "Bearer service-backend-token",
                "Content-Type": "application/json"
            },
            json=llm_config_data,
            timeout=15
        )
        
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   ✅ API Gateway: SUCCESS")
            result = response.json()
            print(f"   Created config ID: {result.get('id', 'Unknown')}")
        else:
            print(f"   ❌ API Gateway failed: {response.text}")
            
    except Exception as e:
        print(f"   ❌ API Gateway error: {e}")
    
    # Test 3: Verify configurations list
    print(f"\n3. Verifying LLM Configurations List")
    try:
        response = requests.get(
            "http://localhost:8000/api/llm/configurations",
            headers={"Authorization": "Bearer service-backend-token"},
            timeout=10
        )
        
        if response.status_code == 200:
            configs = response.json()
            print(f"   ✅ Found {len(configs)} total configurations")
            
            # Look for our test config
            test_configs = [c for c in configs if c.get('name', '').startswith('Test_Gemini_Fix')]
            if test_configs:
                print(f"   ✅ Test config found: {test_configs[0]['name']}")
                print(f"   Temperature: {test_configs[0].get('temperature', 'N/A')}")
                print(f"   Max tokens: {test_configs[0].get('max_tokens', 'N/A')}")
            else:
                print(f"   ⚠️  Test config not found in list")
        else:
            print(f"   ❌ Failed to list configs: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ List configs error: {e}")

if __name__ == "__main__":
    test_llm_config_creation()
