#!/usr/bin/env python3
"""
Test the fixed LLM service integration
"""

import requests
import json
import time

def test_llm_endpoints():
    """Test the LLM service endpoints"""
    
    base_url = 'http://localhost:8007'
    
    print("Testing LLM Service Integration...")
    print("=" * 50)
    
    # Test 1: Health check
    try:
        response = requests.get(f'{base_url}/health', timeout=10)
        print(f"✅ Health check: {response.status_code}")
        if response.status_code == 200:
            health_data = response.json()
            print(f"   Service: {health_data.get('service', 'unknown')}")
            print(f"   Status: {health_data.get('status', 'unknown')}")
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return
    
    # Test 2: Process endpoint (for document summarization)
    print("\n📝 Testing /process endpoint (document service usage)...")
    try:
        payload = {
            "process_type": "content_summarization",
            "prompt": "Summarize this test content: This is a sample document for migration assessment.",
            "project_id": "1f69de03-0ce6-4c0b-8820-2883eaa3dd4f",
            "allow_global": True
        }
        
        response = requests.post(f'{base_url}/api/llm/process', json=payload, timeout=30)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"   Success: {result.get('success', False)}")
            if result.get('success'):
                print(f"   Response length: {len(result.get('response', ''))}")
                print(f"   Sample response: {result.get('response', '')[:100]}...")
            else:
                print(f"   Error: {result.get('error', 'Unknown error')}")
        else:
            print(f"   Error: {response.text}")
            
    except Exception as e:
        print(f"❌ Process endpoint failed: {e}")
    
    # Test 3: Chat completions endpoint (for AutoGen)
    print("\n💬 Testing /chat/completions endpoint (AutoGen usage)...")
    try:
        payload = {
            "messages": [
                {"role": "system", "content": "You are a helpful migration assessment assistant."},
                {"role": "user", "content": "Do we have enough data to do migration planning?"}
            ],
            "model": "gemini-1.5-pro",
            "temperature": 0.7,
            "max_tokens": 512,
            "project_id": "1f69de03-0ce6-4c0b-8820-2883eaa3dd4f"
        }
        
        response = requests.post(f'{base_url}/api/llm/chat/completions', json=payload, timeout=30)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"   Choices: {len(result.get('choices', []))}")
            if result.get('choices'):
                choice = result['choices'][0]
                message = choice.get('message', {})
                print(f"   Role: {message.get('role', 'unknown')}")
                print(f"   Content length: {len(message.get('content', ''))}")
                print(f"   Sample content: {message.get('content', '')[:100]}...")
            
            usage = result.get('usage', {})
            if usage:
                print(f"   Token usage: {usage}")
        else:
            print(f"   Error: {response.text}")
            
    except Exception as e:
        print(f"❌ Chat completions endpoint failed: {e}")
    
    print("\n" + "=" * 50)
    print("LLM Service test completed!")

if __name__ == "__main__":
    # Wait a bit for services to start
    time.sleep(5)
    test_llm_endpoints()
