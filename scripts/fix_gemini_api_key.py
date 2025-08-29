#!/usr/bin/env python3
"""
Fix LLM API Key Configuration
Adds the actual API key to the existing Gemini configuration
"""

import requests
import json
import sys

def update_gemini_config():
    """Update the Gemini configuration with an actual API key"""
    
    config_id = "gemini444_1756352388"
    
    print("🔧 Fixing Gemini LLM Configuration...")
    print(f"Configuration ID: {config_id}")
    
    # You need to replace this with your actual Google API key
    api_key = input("Enter your Google API key: ").strip()
    
    if not api_key:
        print("❌ No API key provided. Exiting.")
        return False
    
    # Prepare the update payload
    update_payload = {
        "api_key": api_key
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer service-backend-token"
    }
    
    try:
        print("📡 Updating LLM configuration...")
        response = requests.put(
            f"http://localhost:8002/llm-configurations/{config_id}",
            json=update_payload,
            headers=headers
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ LLM configuration updated successfully!")
            print(f"  - Configuration: {result.get('name')}")
            print(f"  - Provider: {result.get('provider')}")
            print(f"  - Model: {result.get('model')}")
            print(f"  - API Key: {'*' * 20} (set)")
            return True
        else:
            print(f"❌ Failed to update configuration: {response.status_code}")
            try:
                error = response.json()
                print(f"Error: {error}")
            except:
                print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error updating configuration: {e}")
        return False

def test_configuration():
    """Test that the configuration now works"""
    print("\n🧪 Testing LLM configuration...")
    
    test_payload = {
        "process_type": "entity_extraction",
        "prompt": "Test: Microsoft Azure cloud platform",
        "project_id": "7d1e347c-efdd-4bc5-a112-98ec17fdf31c"
    }
    
    try:
        response = requests.post(
            "http://localhost:8007/api/llm/process",
            json=test_payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print("✅ LLM configuration test PASSED!")
                print("🎉 Document processing should now work correctly!")
                return True
            else:
                print(f"❌ LLM test failed: {result.get('error')}")
                return False
        else:
            print(f"❌ LLM service error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing LLM: {e}")
        return False

def main():
    print("=" * 60)
    print("🔧 LLM API Key Configuration Fix")
    print("=" * 60)
    
    print("\n📋 Current Issue:")
    print("- The Gemini LLM configuration exists but has no API key")
    print("- This causes document processing to fail during entity extraction")
    print("- We need to add your Google API key to the configuration")
    
    print("\n🔑 Google API Key Information:")
    print("- Get your key from: https://console.cloud.google.com/")
    print("- Go to APIs & Services > Credentials")
    print("- Create or use existing API key for Gemini API")
    
    # Update configuration
    if update_gemini_config():
        # Test the fix
        test_configuration()
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()