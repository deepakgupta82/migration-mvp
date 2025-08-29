#!/usr/bin/env python3
"""
LLM Configuration and API Key Diagnostic Script
This script helps diagnose issues with LLM configurations and API keys
"""

import requests
import json
import sys

def check_project_llm_config(project_id):
    """Check the LLM configuration for a specific project"""
    try:
        print(f"🔍 Checking LLM configuration for project: {project_id}")
        
        # Get project details
        response = requests.get(f"http://localhost:8002/projects/{project_id}")
        if response.status_code == 200:
            project = response.json()
            print(f"✓ Project found: {project.get('name', 'Unknown')}")
            print(f"  - LLM Provider: {project.get('llm_provider', 'Not set')}")
            print(f"  - LLM Model: {project.get('llm_model', 'Not set')}")
            print(f"  - LLM API Key ID: {project.get('llm_api_key_id', 'Not set')}")
            
            # Check the specific LLM configuration
            llm_api_key_id = project.get('llm_api_key_id')
            if llm_api_key_id:
                print(f"\n🔍 Checking LLM configuration: {llm_api_key_id}")
                config_response = requests.get(f"http://localhost:8002/llm-configurations/{llm_api_key_id}")
                if config_response.status_code == 200:
                    config = config_response.json()
                    print(f"✓ Configuration found:")
                    print(f"  - ID: {config.get('id')}")
                    print(f"  - Name: {config.get('name')}")
                    print(f"  - Provider: {config.get('provider')}")
                    print(f"  - Model: {config.get('model')}")
                    
                    # Check if API key is present (don't show the actual key for security)
                    api_key = config.get('api_key')
                    if api_key:
                        print(f"  - API Key: {'*' * 20} (present, {len(api_key)} chars)")
                    else:
                        print(f"  - API Key: ❌ NOT PRESENT")
                        return False
                else:
                    print(f"❌ Failed to fetch LLM configuration: {config_response.status_code}")
                    return False
            else:
                print(f"❌ No LLM API Key ID assigned to project")
                return False
        else:
            print(f"❌ Failed to fetch project: {response.status_code}")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def list_all_llm_configs():
    """List all available LLM configurations"""
    try:
        print(f"\n📋 Listing all LLM configurations:")
        response = requests.get("http://localhost:8002/llm-configurations")
        if response.status_code == 200:
            configs = response.json()
            if configs:
                for config in configs:
                    api_key = config.get('api_key')
                    api_key_status = f"{'*' * 10} (present)" if api_key else "❌ NOT PRESENT"
                    print(f"  - {config.get('id')}: {config.get('name')} ({config.get('provider')}/{config.get('model')}) - API Key: {api_key_status}")
            else:
                print(f"  No LLM configurations found")
        else:
            print(f"❌ Failed to fetch LLM configurations: {response.status_code}")
    except Exception as e:
        print(f"❌ Error listing configurations: {e}")

def test_llm_service():
    """Test LLM service connectivity"""
    try:
        print(f"\n🔧 Testing LLM service connectivity:")
        response = requests.get("http://localhost:8007/health")
        if response.status_code == 200:
            print(f"✓ LLM service is running")
        else:
            print(f"❌ LLM service health check failed: {response.status_code}")
    except Exception as e:
        print(f"❌ LLM service not accessible: {e}")

def main():
    if len(sys.argv) != 2:
        print("Usage: python check_llm_api_keys.py <project_id>")
        print("Example: python check_llm_api_keys.py 7d1e347c-efdd-4bc5-a112-98ec17fdf31c")
        sys.exit(1)
    
    project_id = sys.argv[1]
    
    print("=" * 60)
    print("🔍 LLM Configuration Diagnostic Script")
    print("=" * 60)
    
    # Test services
    test_llm_service()
    
    # List all configurations
    list_all_llm_configs()
    
    # Check specific project
    success = check_project_llm_config(project_id)
    
    print("\n" + "=" * 60)
    if success:
        print("✅ LLM configuration appears to be properly set up")
        print("If you're still experiencing issues, check the LLM service logs for more details")
    else:
        print("❌ LLM configuration has issues that need to be resolved")
        print("\n💡 Suggested fixes:")
        print("1. Ensure the LLM configuration has a valid API key")
        print("2. Verify the project is assigned the correct LLM configuration")
        print("3. Check that the LLM service can access the project service")
    print("=" * 60)

if __name__ == "__main__":
    main()