#!/usr/bin/env python3
"""
Simple test to check AutoGen endpoints
"""

import requests
import json

BASE_URL = "http://localhost:8008"

def test_health():
    print("Testing health endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        print(f"Health status: {response.status_code}")
        if response.status_code == 200:
            print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Health test failed: {e}")
        return False

def test_agents():
    print("\nTesting agents endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/api/autogen/agents", timeout=10)
        print(f"Agents status: {response.status_code}")
        if response.status_code == 200:
            agents = response.json()
            print(f"Agents: {list(agents.keys())}")
        else:
            print(f"Error response: {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"Agents test failed: {e}")
        return False

def test_conversation():
    print("\nTesting conversation endpoint...")
    try:
        payload = {
            "message": "Help me with cloud migration",
            "context": {
                "project_type": "simple"
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/autogen/conversations/start", 
            json=payload,
            timeout=45
        )
        print(f"Conversation status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"Success! Session: {result.get('session_id', 'N/A')}")
        else:
            print(f"Error response: {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"Conversation test failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Simple AutoGen Test")
    print("=" * 30)
    
    health_ok = test_health()
    agents_ok = test_agents()
    conv_ok = test_conversation()
    
    print(f"\n📊 Results:")
    print(f"Health: {'✅' if health_ok else '❌'}")
    print(f"Agents: {'✅' if agents_ok else '❌'}")
    print(f"Conversation: {'✅' if conv_ok else '❌'}")
