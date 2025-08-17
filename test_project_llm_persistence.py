#!/usr/bin/env python3
"""
Test LLM Configuration persistence during project creation
"""

import requests
import json

def test_project_llm_persistence():
    print("🔧 Testing LLM Configuration Persistence During Project Creation")
    print("=" * 70)
    
    # First, get available LLM configurations
    print("1. Getting available LLM configurations...")
    try:
        response = requests.get(
            "http://localhost:8000/api/llm/configurations",
            headers={"Authorization": "Bearer service-backend-token"},
            timeout=10
        )
        
        if response.status_code == 200:
            configs = response.json()
            print(f"   ✅ Found {len(configs)} LLM configurations")
            
            if configs:
                # Use the first available config
                test_config = configs[0]
                print(f"   Using config: {test_config['name']} ({test_config['id']})")
                print(f"   Provider: {test_config['provider']}")
                print(f"   Model: {test_config['model']}")
                
                # Test project creation with LLM config
                project_data = {
                    "name": "LLM_Persistence_Test",
                    "description": "Testing LLM config persistence during creation",
                    "client_name": "Test Client",
                    "client_contact": "test@example.com",
                    "llm_provider": test_config['provider'],
                    "llm_model": test_config['model'],
                    "llm_api_key_id": test_config['id'],
                    "llm_temperature": test_config['temperature'],
                    "llm_max_tokens": test_config['max_tokens']
                }
                
                print(f"\n2. Creating project with LLM configuration...")
                print(f"   LLM Provider: {project_data['llm_provider']}")
                print(f"   LLM Model: {project_data['llm_model']}")
                print(f"   LLM API Key ID: {project_data['llm_api_key_id']}")
                print(f"   Temperature: {project_data['llm_temperature']}")
                print(f"   Max Tokens: {project_data['llm_max_tokens']}")
                
                # Create project via API Gateway
                response = requests.post(
                    "http://localhost:8000/api/projects",
                    headers={
                        "Authorization": "Bearer service-backend-token",
                        "Content-Type": "application/json"
                    },
                    json=project_data,
                    timeout=15
                )
                
                if response.status_code in [200, 201]:
                    project = response.json()
                    project_id = project['id']
                    print(f"   ✅ Project created successfully: {project_id}")
                    
                    # Check if LLM config was saved
                    print(f"\n3. Verifying LLM configuration persistence...")
                    print(f"   Created project LLM provider: {project.get('llm_provider', 'None')}")
                    print(f"   Created project LLM model: {project.get('llm_model', 'None')}")
                    print(f"   Created project LLM API key ID: {project.get('llm_api_key_id', 'None')}")
                    print(f"   Created project temperature: {project.get('llm_temperature', 'None')}")
                    print(f"   Created project max tokens: {project.get('llm_max_tokens', 'None')}")
                    
                    # Fetch the project again to verify persistence
                    print(f"\n4. Re-fetching project to verify persistence...")
                    response = requests.get(
                        f"http://localhost:8000/api/projects/{project_id}",
                        headers={"Authorization": "Bearer service-backend-token"},
                        timeout=10
                    )
                    
                    if response.status_code == 200:
                        fetched_project = response.json()
                        print(f"   ✅ Project re-fetched successfully")
                        print(f"   Re-fetched LLM provider: {fetched_project.get('llm_provider', 'None')}")
                        print(f"   Re-fetched LLM model: {fetched_project.get('llm_model', 'None')}")
                        print(f"   Re-fetched LLM API key ID: {fetched_project.get('llm_api_key_id', 'None')}")
                        print(f"   Re-fetched temperature: {fetched_project.get('llm_temperature', 'None')}")
                        print(f"   Re-fetched max tokens: {fetched_project.get('llm_max_tokens', 'None')}")
                        
                        # Compare values
                        if (fetched_project.get('llm_provider') == project_data['llm_provider'] and
                            fetched_project.get('llm_model') == project_data['llm_model'] and
                            fetched_project.get('llm_api_key_id') == project_data['llm_api_key_id']):
                            print(f"\n   ✅ SUCCESS: LLM configuration persisted correctly!")
                        else:
                            print(f"\n   ❌ FAILURE: LLM configuration was not persisted correctly")
                            print(f"   Expected provider: {project_data['llm_provider']}")
                            print(f"   Actual provider: {fetched_project.get('llm_provider', 'None')}")
                            
                        return project_id
                    else:
                        print(f"   ❌ Failed to re-fetch project: {response.status_code}")
                        print(f"   Response: {response.text}")
                else:
                    print(f"   ❌ Failed to create project: {response.status_code}")
                    print(f"   Response: {response.text}")
            else:
                print(f"   ❌ No LLM configurations available for testing")
        else:
            print(f"   ❌ Failed to get LLM configurations: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        
    return None

if __name__ == "__main__":
    test_project_llm_persistence()
