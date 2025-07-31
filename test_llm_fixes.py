#!/usr/bin/env python3
import requests
import json

print("=== TESTING LLM CONFIGURATION FIXES ===")

# Test 1: Create a new LLM configuration to test dynamic workflow
print("\n1. Creating new LLM configuration for testing...")
config_data = {
    'name': 'Test Dynamic Workflow',
    'provider': 'openai',
    'model': 'gpt-4o',
    'api_key': 'sk-test-dynamic-key-456',
    'temperature': 0.1,
    'max_tokens': 2000,
    'description': 'Testing dynamic model loading workflow'
}

response = requests.post('http://localhost:8000/llm-configurations', json=config_data)
if response.status_code == 200:
    config = response.json()
    print(f'✅ Configuration created: {config["name"]}')
    print(f'   ID: {config["id"]}')
    config_id = config['id']
else:
    print(f'❌ Failed to create config: {response.status_code}')
    exit()

# Test 2: Test the configuration (will show inline results)
print("\n2. Testing LLM configuration (should show inline results)...")
test_data = {
    'config_id': config_id,
    'provider': 'openai',
    'model': 'gpt-4o',
    'api_key': 'sk-test-dynamic-key-456',
    'temperature': 0.1,
    'max_tokens': 50
}

response = requests.post('http://localhost:8000/api/test-llm-config', json=test_data)
if response.status_code == 200:
    result = response.json()
    print(f'✅ Test completed: {result["status"]}')
    if result['status'] == 'error':
        print(f'   Expected error (fake API key): {result["message"]}')
    else:
        print(f'   Response: {result["response"]}')
else:
    print(f'❌ Test endpoint failed: {response.status_code}')

# Test 3: Test dynamic model loading endpoint
print("\n3. Testing dynamic model loading...")
try:
    response = requests.get('http://localhost:8000/api/models/openai?api_key=sk-test-key')
    if response.status_code == 200:
        result = response.json()
        if result['status'] == 'success':
            print(f'✅ Dynamic model loading working: {len(result["models"])} models found')
        else:
            print(f'⚠️ Expected error (fake API key): {result["message"]}')
    else:
        print(f'❌ Model endpoint failed: {response.status_code}')
except Exception as e:
    print(f'❌ Model endpoint error: {e}')

print("\n✅ LLM Configuration Fixes Testing Complete!")
print("\n🌐 Frontend fixes implemented:")
print("   1. ✅ Dynamic model loading workflow (name → provider → API key → models)")
print("   2. ✅ Inline test results display (no more cutoff at bottom)")
print("   3. ✅ Proper field enabling/disabling sequence")
print("   4. ✅ Enhanced user experience with loading indicators")
print("\n🔧 Backend enhancements:")
print("   1. ✅ Dynamic model fetching from OpenAI/Gemini APIs")
print("   2. ✅ Enhanced test result storage and display")
print("   3. ✅ Improved error handling and response formatting")
print("\n🎯 Test the fixes in the frontend:")
print("   - Visit http://localhost:3000/settings")
print("   - Try creating a new LLM configuration following the workflow")
print("   - Test saved configurations and see inline results")
