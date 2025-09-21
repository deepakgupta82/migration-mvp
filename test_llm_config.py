#!/usr/bin/env python3
"""Test LLM configuration retrieval endpoint"""

import requests
import json

def test_llm_config():
    headers = {
        'Authorization': 'Bearer service-backend-token',
        'Content-Type': 'application/json'
    }
    
    project_id = "61502d23-4928-4377-92c8-81b9c4f0fffd"
    config_id = "29auggemin1_1756425518"
    
    print("=== Testing LLM Configuration Retrieval ===")
    print(f"Project ID: {project_id}")
    print(f"Config ID: {config_id}")
    print()
    
    # Test 1: Get project details
    print("1. Testing project retrieval...")
    try:
        resp = requests.get(f"http://localhost:8002/projects/{project_id}", headers=headers, timeout=10)
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   LLM Config ID: {data.get('llm_configuration_id')}")
            print(f"   ✅ Project retrieval working")
        else:
            print(f"   ❌ Error: {resp.text}")
    except Exception as e:
        print(f"   ❌ Exception: {e}")
    
    print()
    
    # Test 2: Get LLM configuration by ID
    print("2. Testing LLM config retrieval...")
    try:
        resp = requests.get(f"http://localhost:8002/llm-configurations/{config_id}", headers=headers, timeout=10)
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   ✅ LLM config retrieval working")
            print(f"   Config Name: {data.get('name')}")
            print(f"   Provider: {data.get('provider')}")
            print(f"   Model: {data.get('model')}")
            print(f"   API Key ID: {data.get('api_key_id')}")
            print(f"   API Key (masked): {data.get('api_key', 'Not present')[:10]}...")
        else:
            print(f"   ❌ Error: {resp.text}")
    except Exception as e:
        print(f"   ❌ Exception: {e}")
    
    print()
    
    # Test 3: List all configurations (to see available endpoints)
    print("3. Testing list all configurations...")
    try:
        resp = requests.get("http://localhost:8002/llm-configurations", headers=headers, timeout=10)
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   ✅ Found {len(data)} configurations")
            for config in data:
                print(f"     - {config.get('id')}: {config.get('name')} ({config.get('provider')})")
        else:
            print(f"   ❌ Error: {resp.text}")
    except Exception as e:
        print(f"   ❌ Exception: {e}")
    
    print()
    
    # Test 4: Check LLM service health
    print("4. Testing LLM service...")
    try:
        resp = requests.get("http://localhost:8007/health", timeout=10)
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            print(f"   ✅ LLM service is healthy")
        else:
            print(f"   ❌ LLM service error: {resp.text}")
    except Exception as e:
        print(f"   ❌ LLM service exception: {e}")

if __name__ == "__main__":
    test_llm_config()
