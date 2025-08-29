#!/usr/bin/env python3
"""
Test LLM Configuration Saving
Tests that saving a new Gemini LLM configuration works without internal server errors
"""

import requests
import json
import time
from datetime import datetime

# Test configuration
BASE_URL = "http://localhost:8000"
TEST_CONFIG = {
    "name": f"Test Gemini Config {int(time.time())}",
    "provider": "gemini",
    "model": "gemini-2.5-pro",
    "api_key": "AIzaSyBRa5wujJXXvIDniza9eRs6rLFUVL9hW0I",  # Your test API key
    "temperature": "0.1",
    "max_tokens": "8192",
    "description": "Test configuration for Gemini 2.5 Pro"
}

def test_save_llm_config():
    """Test saving a new LLM configuration"""
    print("🧪 Testing LLM Configuration Saving...")
    print("="*50)
    
    try:
        # Test 1: Create new configuration
        print(f"📝 Creating new LLM configuration: {TEST_CONFIG['name']}")
        
        response = requests.post(
            f"{BASE_URL}/api/llm/configurations",
            json=TEST_CONFIG,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer service-backend-token"
            },
            timeout=30
        )
        
        print(f"📊 Response Status: {response.status_code}")
        
        if response.status_code == 201:
            result = response.json()
            config_id = result.get('id')
            print(f"✅ Configuration created successfully!")
            print(f"   - Config ID: {config_id}")
            print(f"   - Name: {result.get('name')}")
            print(f"   - Provider: {result.get('provider')}")
            print(f"   - Model: {result.get('model')}")
            print(f"   - Max Tokens: {result.get('max_tokens')}")
            
            # Test 2: Verify it appears in the list
            print("\n📋 Verifying configuration appears in list...")
            list_response = requests.get(
                f"{BASE_URL}/api/llm/configurations",
                headers={"Authorization": "Bearer service-backend-token"}
            )
            
            if list_response.status_code == 200:
                configs = list_response.json()
                found_config = None
                for config in configs:
                    if config.get('id') == config_id:
                        found_config = config
                        break
                
                if found_config:
                    print(f"✅ Configuration found in list!")
                    print(f"   - Status: {found_config.get('status')}")
                else:
                    print("❌ Configuration not found in list")
            
            # Test 3: Clean up (delete the test configuration)
            print(f"\n🗑️ Cleaning up test configuration...")
            delete_response = requests.delete(
                f"{BASE_URL}/api/llm/configurations/{config_id}",
                headers={"Authorization": "Bearer service-backend-token"}
            )
            
            if delete_response.status_code == 200:
                print("✅ Test configuration cleaned up successfully")
            else:
                print(f"⚠️ Failed to clean up test configuration: {delete_response.status_code}")
            
            return True
            
        else:
            print(f"❌ Failed to create configuration!")
            print(f"   - Status: {response.status_code}")
            print(f"   - Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error during test: {e}")
        return False

def test_max_tokens_endpoint():
    """Test the max tokens endpoint - REMOVED (max tokens now manual entry)"""
    print("\n🔍 Testing Max Tokens Endpoint...")
    print("="*50)
    print("⚠️  Max tokens endpoint has been removed - users now enter max tokens manually")
    print("✅ Max tokens test skipped (feature intentionally removed)")
    return True

def main():
    """Run all tests"""
    print("🚀 LLM Configuration Save Test Suite")
    print("="*60)
    print(f"⏰ Started at: {datetime.now().isoformat()}")
    print(f"🎯 Target: {BASE_URL}")
    print()
    
    # Test 1: Save LLM Configuration
    save_success = test_save_llm_config()
    
    # Test 2: Max Tokens Endpoint
    max_tokens_success = test_max_tokens_endpoint()
    
    # Summary
    print("\n📋 Test Results Summary")
    print("="*30)
    print(f"✅ LLM Config Save: {'PASS' if save_success else 'FAIL'}")
    print(f"✅ Max Tokens API: SKIPPED (endpoint removed - manual entry now)")
    
    if save_success:
        print("\n🎉 LLM configuration saving is working correctly.")
        print("📝 Note: Max tokens is now manually entered by users (endpoint removed)")
        return True
    else:
        print("\n❌ LLM config save test failed. Check the logs above for details.")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)