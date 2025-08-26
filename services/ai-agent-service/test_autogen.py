#!/usr/bin/env python3
"""
Simple test script to validate AutoGen integration
"""

import asyncio
import json
import sys
import requests
from datetime import datetime

# Test endpoints
BASE_URL = "http://localhost:8008"

def test_service_health():
    """Test if the service is running"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=30)
        if response.status_code == 200:
            print("✅ Service is running")
            return True
        else:
            print(f"❌ Service health check failed: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Cannot connect to service: {e}")
        return False

def test_autogen_agents():
    """Test AutoGen agents endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/api/autogen/agents", timeout=30)
        if response.status_code == 200:
            agents = response.json()
            print(f"✅ AutoGen agents available: {len(agents)} agents")
            for agent, description in agents.items():
                print(f"   - {agent}: {description}")
            return True
        else:
            print(f"❌ AutoGen agents endpoint failed: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ AutoGen agents test failed: {e}")
        return False

def test_autogen_conversation():
    """Test a simple AutoGen conversation"""
    try:
        payload = {
            "message": "I need help planning a cloud migration for a simple web application. What are the key considerations?",
            "context": {
                "project_name": "Test Web App Migration",
                "current_infrastructure": "On-premises servers",
                "target_cloud": "AWS",
                "migration_goals": ["Cost reduction", "Improved scalability"]
            },
            "selected_agents": ["migration_architect", "security_expert"]
        }
        
        print(f"🧪 Testing AutoGen conversation...")
        response = requests.post(
            f"{BASE_URL}/api/autogen/conversations/start", 
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ AutoGen conversation completed")
            print(f"   - Session ID: {result.get('session_id', 'N/A')}")
            print(f"   - Status: {result.get('status', 'N/A')}")
            print(f"   - Mode: {result.get('conversation_mode', 'N/A')}")
            print(f"   - AutoGen Enabled: {result.get('autogen_enabled', 'N/A')}")
            print(f"   - Participating Agents: {result.get('participating_agents', [])}")
            print(f"   - Message Count: {result.get('message_count', 0)}")
            
            # Show first agent response if available
            if result.get('full_conversation'):
                first_msg = result['full_conversation'][0] if result['full_conversation'] else None
                if first_msg:
                    content = first_msg.get('content', '')[:200] + '...' if len(first_msg.get('content', '')) > 200 else first_msg.get('content', '')
                    print(f"   - First response from {first_msg.get('source', 'unknown')}: {content}")
            
            return True
        else:
            print(f"❌ AutoGen conversation failed: {response.status_code}")
            try:
                error_detail = response.json()
                print(f"   Error: {error_detail}")
            except:
                print(f"   Error: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ AutoGen conversation test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Testing AutoGen Co-pilot Implementation")
    print("=" * 50)
    
    tests = [
        ("Service Health", test_service_health),
        ("AutoGen Agents", test_autogen_agents),
        ("AutoGen Conversation", test_autogen_conversation)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}:")
        result = test_func()
        results.append((test_name, result))
    
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n🎯 Overall: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 All tests passed! AutoGen integration is working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Please check the service logs.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
