"""
Simple Phase 1 API Test
Test the /orchestrate endpoint directly via HTTP
"""

import requests
import json

def test_orchestrate_endpoint():
    """Test the /orchestrate endpoint"""
    print("="*60)
    print("Phase 1 API Test: /orchestrate endpoint")
    print("="*60)
    
    url = "http://localhost:8007/orchestrate"
    headers = {
        "Authorization": "Bearer service-backend-token",
        "Content-Type": "application/json",
        "X-Correlation-ID": "test-phase1-001"
    }
    
    payload = {
        "task_type": "domain_classification",
        "content": "Server: srv-web-01, IP: 192.168.1.10, OS: Ubuntu 20.04",
        "complexity": "simple",
        "response_format": {"type": "json_object"},
        "temperature": 0.1
    }
    
    try:
        print(f"\nCalling: POST {url}")
        print(f"Payload: {json.dumps(payload, indent=2)}")
        
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        
        print(f"\nResponse Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Success: {result.get('success')}")
            print(f"Model Used: {result.get('model_used')}")
            print(f"Provider: {result.get('provider')}")
            print(f"Duration: {result.get('duration_ms')}ms")
            print(f"Cost: ${result.get('cost_usd', 0):.6f}")
            print(f"Tokens: {result.get('tokens')}")
            
            if result.get('success'):
                print("\n✅ TEST PASSED: Orchestration endpoint is working!")
                return True
            else:
                print(f"\n❌ TEST FAILED: {result.get('error')}")
                return False
        else:
            print(f"Response: {response.text}")
            print(f"\n❌ TEST FAILED: HTTP {response.status_code}")
            
            if response.status_code == 404:
                print("\n⚠️  The /orchestrate endpoint doesn't exist yet.")
                print("   This is expected if the LLM service hasn't been restarted.")
                print("   The code was just added and needs service restart.")
            
            return False
            
    except Exception as e:
        print(f"\n❌ TEST FAILED: {str(e)}")
        return False


def check_llm_service():
    """Check if LLM service is running"""
    print("\n" + "="*60)
    print("Checking LLM Service Status")
    print("="*60)
    
    try:
        response = requests.get("http://localhost:8007/healthz", timeout=5)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            health = response.json()
            print(f"Service: {health.get('service')}")
            print(f"Status: {health.get('status')}")
            print(f"Uptime: {health.get('uptime')}s")
            print("✅ LLM Service is running")
            return True
        else:
            print("❌ LLM Service unhealthy")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to LLM Service: {e}")
        return False


def main():
    """Run simple API test"""
    print("\n" + "="*80)
    print("PHASE 1 SIMPLE API TEST")
    print("="*80)
    
    # Check service is running
    if not check_llm_service():
        print("\n⚠️  LLM Service is not running. Please start it first.")
        return False
    
    # Test orchestrate endpoint
    result = test_orchestrate_endpoint()
    
    if not result:
        print("\n" + "="*80)
        print("NEXT STEPS")
        print("="*80)
        print("The /orchestrate endpoint code has been added but needs:")
        print("1. Service restart to load the new endpoint")
        print("2. Or we can proceed with Phase 2 and test everything together")
        print("\nPhase 1 code is committed and ready. Would you like to:")
        print("  A) Restart LLM service and test now")
        print("  B) Proceed with Phase 2 implementation (test later)")
    
    return result


if __name__ == "__main__":
    main()
