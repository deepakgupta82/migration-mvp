#!/usr/bin/env python3
"""
Service Diagnostic Script
Quick health checks and issue identification
"""

import requests
import json
from datetime import datetime

# Configuration
PROJECT_ID = "7d1e347c-efdd-4bc5-a112-98ec17fdf31c"
DOCUMENT_NAME = "D4_Windows server inventory_V38.xlsx"

# Service URLs
SERVICES = {
    "backend": "http://localhost:8000",
    "project": "http://localhost:8002", 
    "document": "http://localhost:8003",
    "vector": "http://localhost:8005",
    "graph": "http://localhost:8006",
    "llm": "http://localhost:8007",
    "storage": "http://localhost:8010"
}

def check_service_health():
    """Check health of all services"""
    print("🏥 SERVICE HEALTH CHECK")
    print("="*50)
    
    for service, url in SERVICES.items():
        try:
            response = requests.get(f"{url}/health", timeout=5)
            if response.status_code == 200:
                health_data = response.json()
                status = health_data.get('status', 'unknown')
                print(f"✅ {service}: {status}")
            else:
                print(f"❌ {service}: HTTP {response.status_code}")
        except Exception as e:
            print(f"❌ {service}: {str(e)}")

def check_llm_config():
    """Check LLM configuration"""
    print("\n🤖 LLM CONFIGURATION CHECK")
    print("="*50)
    
    try:
        response = requests.get(f"{SERVICES['backend']}/api/llm/configurations", timeout=10)
        if response.status_code == 200:
            configs = response.json()
            gemini_config = None
            
            for config in configs:
                if config.get('name') == 'gemini444':
                    gemini_config = config
                    break
            
            if gemini_config:
                api_key = gemini_config.get('api_key', '')
                if api_key and api_key.strip():
                    print(f"✅ LLM Config 'gemini444' found with API key")
                    print(f"   Provider: {gemini_config.get('provider')}")
                    print(f"   Model: {gemini_config.get('model')}")
                else:
                    print(f"❌ LLM Config 'gemini444' has empty API key")
            else:
                print(f"❌ LLM Config 'gemini444' not found")
                available = [c.get('name') for c in configs]
                print(f"   Available configs: {available}")
        else:
            print(f"❌ Failed to get LLM configs: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ Error checking LLM config: {str(e)}")

def check_document_availability():
    """Check if document is available"""
    print("\n📄 DOCUMENT AVAILABILITY CHECK")
    print("="*50)
    
    try:
        response = requests.get(f"{SERVICES['storage']}/api/storage/projects/{PROJECT_ID}/files/uploads_raw", timeout=10)
        if response.status_code == 200:
            files_data = response.json()
            files = files_data.get('files', [])
            
            found = False
            for file_info in files:
                if file_info.get('filename') == DOCUMENT_NAME:
                    print(f"✅ Document found: {DOCUMENT_NAME}")
                    print(f"   Size: {file_info.get('size', 'unknown')} bytes")
                    print(f"   Modified: {file_info.get('last_modified', 'unknown')}")
                    found = True
                    break
            
            if not found:
                print(f"❌ Document not found: {DOCUMENT_NAME}")
                available = [f.get('filename') for f in files]
                print(f"   Available files: {available}")
        else:
            print(f"❌ Failed to check files: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ Error checking document: {str(e)}")

def check_vector_endpoint():
    """Check vector service endpoint"""
    print("\n🔢 VECTOR SERVICE ENDPOINT CHECK")
    print("="*50)
    
    try:
        # Test the endpoint with empty payload (should get 422 or 401, not 404)
        test_url = f"{SERVICES['vector']}/api/vectors/projects/{PROJECT_ID}/documents"
        response = requests.post(test_url, json={}, timeout=10)
        
        if response.status_code == 404:
            print(f"❌ Vector endpoint not found: {test_url}")
        elif response.status_code in [401, 422, 400]:
            print(f"✅ Vector endpoint exists: {test_url}")
            print(f"   Response: HTTP {response.status_code} (expected)")
        else:
            print(f"⚠️ Vector endpoint: HTTP {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error checking vector endpoint: {str(e)}")

def test_simple_processing():
    """Test simple document processing"""
    print("\n🔄 SIMPLE PROCESSING TEST")
    print("="*50)
    
    payload = {
        "file_names": [DOCUMENT_NAME]
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-Correlation-ID": f"diagnostic_{int(datetime.now().timestamp())}"
    }
    
    try:
        response = requests.post(
            f"{SERVICES['document']}/api/documents/{PROJECT_ID}/process-selected",
            json=payload,
            headers=headers,
            timeout=30
        )
        
        print(f"📋 Processing request status: HTTP {response.status_code}")
        print(f"📋 Response: {response.text}")
        
        if response.status_code in [200, 201]:
            result = response.json()
            job_id = result.get("job_id")
            if job_id:
                print(f"✅ Processing started with Job ID: {job_id}")
                return job_id
            else:
                print(f"⚠️ No job ID returned")
        else:
            print(f"❌ Processing failed to start")
            
    except Exception as e:
        print(f"❌ Error starting processing: {str(e)}")
    
    return None

def check_existing_vectors():
    """Check if there are any existing vectors"""
    print("\n🔢 EXISTING VECTOR CHECK")
    print("="*50)
    
    try:
        response = requests.get(f"{SERVICES['vector']}/api/vectors/projects/{PROJECT_ID}/stats", timeout=10)
        if response.status_code == 200:
            stats = response.json()
            print(f"📊 Vector stats: {json.dumps(stats, indent=2)}")
        else:
            print(f"❌ Vector stats failed: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ Error checking vectors: {str(e)}")

def check_existing_graph():
    """Check if there are any existing graph nodes"""
    print("\n📊 EXISTING GRAPH CHECK")
    print("="*50)
    
    try:
        response = requests.get(f"{SERVICES['graph']}/api/graphs/projects/{PROJECT_ID}/stats", timeout=10)
        if response.status_code == 200:
            stats = response.json()
            print(f"📊 Graph stats: {json.dumps(stats, indent=2)}")
        else:
            print(f"❌ Graph stats failed: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ Error checking graph: {str(e)}")

def run_diagnostics():
    """Run all diagnostic checks"""
    print("🔍 COMPREHENSIVE SERVICE DIAGNOSTICS")
    print("="*80)
    print(f"Project ID: {PROJECT_ID}")
    print(f"Document: {DOCUMENT_NAME}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Run all checks
    check_service_health()
    check_llm_config()
    check_document_availability()
    check_vector_endpoint()
    check_existing_vectors()
    check_existing_graph()
    
    # Try processing
    job_id = test_simple_processing()
    
    print("\n" + "="*80)
    print("📋 DIAGNOSTIC COMPLETE")
    print("="*80)
    
    if job_id:
        print(f"✅ Successfully started processing with Job ID: {job_id}")
        print("📋 Monitor the job status manually or wait for completion")
    else:
        print("❌ Failed to start document processing")
        print("📋 Check the issues identified above")

if __name__ == "__main__":
    run_diagnostics()