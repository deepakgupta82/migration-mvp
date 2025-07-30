#!/usr/bin/env python3
import requests
import json

print("=== SETTING REAL OPENAI API KEY ===")

# Update the OpenAI API key in settings
settings_url = "http://localhost:8000/platform-settings/openai_key"
key_data = {
    "id": "openai_key",
    "name": "OpenAI API Key",
    "value": "sk-proj-your-real-key-here",  # Replace with actual key
    "category": "llm",
    "type": "secret"
}

try:
    response = requests.put(settings_url, json=key_data)
    print(f"Key Update Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ OpenAI API Key Updated Successfully")
        print(f"  - Name: {result['name']}")
        print(f"  - Category: {result['category']}")
        print(f"  - Type: {result['type']}")
        
        # Test LLM functionality
        print(f"\n🤖 Testing LLM with real API key...")
        llm_test_url = "http://localhost:8000/api/test-llm"
        llm_data = {
            "provider": "openai",
            "model": "gpt-3.5-turbo",
            "apiKeyId": "openai_key"
        }
        
        llm_response = requests.post(llm_test_url, json=llm_data)
        print(f"LLM Test Status: {llm_response.status_code}")
        
        if llm_response.status_code == 200:
            llm_result = llm_response.json()
            print(f"✅ LLM Test Result: {llm_result['status']}")
            print(f"  - Message: {llm_result['message']}")
            if 'response' in llm_result:
                print(f"  - Response: {llm_result['response'][:100]}...")
        else:
            print(f"❌ LLM test failed: {llm_response.text}")
    else:
        print(f"❌ Key update failed: {response.text}")
        
except Exception as e:
    print(f"❌ Error: {e}")

print(f"\n📝 NOTE: Replace 'sk-proj-your-real-key-here' with your actual OpenAI API key")
