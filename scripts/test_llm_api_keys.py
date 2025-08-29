#!/usr/bin/env python3
"""
LLM API Key Test for Document Processing
Tests if LLM service can properly fetch API keys from configurations during document processing
"""

import requests
import json
import time
import sys

def test_services_connectivity():
    """Test connectivity to all required services"""
    services = {
        "Project Service": "http://localhost:8002/health",
        "LLM Service": "http://localhost:8007/health", 
        "Document Service": "http://localhost:8003/health",
        "Graph Service": "http://localhost:8004/health",
        "Vector Service": "http://localhost:8005/health"
    }
    
    print("🔍 Testing service connectivity...")
    all_healthy = True
    
    for service_name, health_url in services.items():
        try:
            response = requests.get(health_url, timeout=5)
            if response.status_code == 200:
                print(f"✓ {service_name}: Running")
            else:
                print(f"❌ {service_name}: Unhealthy (Status: {response.status_code})")
                all_healthy = False
        except Exception as e:
            print(f"❌ {service_name}: Not accessible ({str(e)})")
            all_healthy = False
    
    return all_healthy

def test_llm_config_for_project(project_id):
    """Test LLM configuration for a specific project"""
    print(f"\n🔍 Testing LLM configuration for project: {project_id}")
    
    try:
        # Get project details (no auth header needed for health endpoints)
        response = requests.get(f"http://localhost:8002/projects/{project_id}")
        if response.status_code == 401:
            print("❌ Authentication required - trying with service token...")
            headers = {"Authorization": "Bearer service-backend-token"}
            response = requests.get(f"http://localhost:8002/projects/{project_id}", headers=headers)
        
        if response.status_code == 200:
            project = response.json()
            print(f"✓ Project found: {project.get('name', 'Unknown')}")
            print(f"  - LLM Provider: {project.get('llm_provider', 'Not set')}")
            print(f"  - LLM Model: {project.get('llm_model', 'Not set')}")
            print(f"  - LLM API Key ID: {project.get('llm_api_key_id', 'Not set')}")
            
            llm_api_key_id = project.get('llm_api_key_id')
            if llm_api_key_id:
                return test_llm_configuration(llm_api_key_id, headers if 'headers' in locals() else None)
            else:
                print("❌ No LLM configuration assigned to project")
                return False
        else:
            print(f"❌ Failed to fetch project: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error checking project LLM config: {e}")
        return False

def test_llm_configuration(config_id, headers=None):
    """Test a specific LLM configuration"""
    print(f"\n🔍 Testing LLM configuration: {config_id}")
    
    try:
        response = requests.get(f"http://localhost:8002/llm-configurations/{config_id}", headers=headers)
        if response.status_code == 200:
            config = response.json()
            print(f"✓ Configuration found:")
            print(f"  - ID: {config.get('id')}")
            print(f"  - Name: {config.get('name')}")
            print(f"  - Provider: {config.get('provider')}")
            print(f"  - Model: {config.get('model')}")
            
            # Check if API key is present
            api_key = config.get('api_key')
            if api_key and len(api_key.strip()) > 0:
                print(f"  - API Key: {'*' * 20} (present, {len(api_key)} chars)")
                return True
            else:
                print(f"  - API Key: ❌ NOT PRESENT OR EMPTY")
                return False
        else:
            print(f"❌ Failed to fetch LLM configuration: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error fetching LLM configuration: {e}")
        return False

def test_llm_service_entity_extraction(project_id):
    """Test LLM service entity extraction with the project configuration"""
    print(f"\n🔍 Testing LLM service entity extraction for project: {project_id}")
    
    test_payload = {
        "process_type": "entity_extraction",
        "prompt": "Extract entities from this text: Microsoft Azure cloud platform with SQL Server database.",
        "project_id": project_id
    }
    
    try:
        print("Sending test request to LLM service... (this may take 20+ seconds)")
        start_time = time.time()
        
        response = requests.post(
            "http://localhost:8007/api/llm/process",
            json=test_payload,
            timeout=60  # 60 second timeout
        )
        
        elapsed_time = time.time() - start_time
        print(f"Response received after {elapsed_time:.1f} seconds")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ LLM service responded successfully")
            print(f"  - Success: {result.get('success', 'Unknown')}")
            print(f"  - Process Type: {result.get('process_type', 'Unknown')}")
            
            if result.get('success'):
                print(f"  - Response preview: {str(result.get('response', ''))[:200]}...")
                return True
            else:
                print(f"  - Error: {result.get('error', 'Unknown error')}")
                return False
        else:
            print(f"❌ LLM service error: {response.status_code}")
            try:
                error_detail = response.json()
                print(f"  - Error details: {error_detail}")
            except:
                print(f"  - Raw response: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"❌ LLM service request timed out after 60 seconds")
        return False
    except Exception as e:
        print(f"❌ Error testing LLM service: {e}")
        return False

def simulate_document_processing_test(project_id):
    """Simulate the document processing flow that was failing"""
    print(f"\n🔍 Simulating document processing flow for project: {project_id}")
    
    # Simulate what happens during entity extraction in graph service
    print("Simulating graph service calling LLM service for entity extraction...")
    
    # This simulates the same call that was failing in the logs
    test_payload = {
        "process_type": "entity_extraction", 
        "prompt": "Test entity extraction: Excel file with Unix systems data including servers, applications, and dependencies.",
        "project_id": project_id
    }
    
    try:
        headers = {"X-Correlation-ID": "test-correlation-id"}
        print("Making LLM service call... (waiting up to 30 seconds)")
        
        start_time = time.time()
        response = requests.post(
            "http://localhost:8007/api/llm/process",
            json=test_payload,
            headers=headers,
            timeout=30
        )
        elapsed_time = time.time() - start_time
        
        print(f"Response received after {elapsed_time:.1f} seconds")
        
        if response.status_code == 200:
            result = response.json()
            success = result.get('success', False)
            
            if success:
                print(f"✅ Entity extraction test PASSED")
                print(f"  - LLM successfully processed the request")
                print(f"  - This indicates API keys are working correctly")
                return True
            else:
                print(f"❌ Entity extraction test FAILED")
                print(f"  - Error: {result.get('error', 'Unknown')}")
                print(f"  - This suggests API key issues")
                return False
        else:
            print(f"❌ LLM service returned error: {response.status_code}")
            print(f"  - Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error in document processing simulation: {e}")
        return False

def main():
    project_id = "7d1e347c-efdd-4bc5-a112-98ec17fdf31c"  # The project from the error logs
    
    print("=" * 70)
    print("🧪 LLM API Key Test for Document Processing")
    print("=" * 70)
    
    # Test 1: Service connectivity
    if not test_services_connectivity():
        print("\n❌ Some services are not running. Please start all required services.")
        return
    
    # Test 2: Project LLM configuration
    config_ok = test_llm_config_for_project(project_id)
    
    # Test 3: LLM service functionality
    if config_ok:
        llm_ok = test_llm_service_entity_extraction(project_id)
        
        # Test 4: Simulate actual document processing
        if llm_ok:
            processing_ok = simulate_document_processing_test(project_id)
            
            print("\n" + "=" * 70)
            if processing_ok:
                print("✅ ALL TESTS PASSED")
                print("🎉 LLM API keys are properly configured and working!")
                print("📋 The document processing should now work correctly.")
            else:
                print("❌ TESTS FAILED")
                print("🔧 API key configuration needs to be fixed.")
        else:
            print("\n❌ LLM service is not working properly")
    else:
        print("\n❌ LLM configuration has issues")
    
    print("=" * 70)

if __name__ == "__main__":
    main()