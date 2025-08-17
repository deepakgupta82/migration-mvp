#!/usr/bin/env python3
"""
Test automatic max token detection functionality
"""

import requests
import json

def test_max_tokens_detection():
    print("🔧 Testing Automatic Max Token Detection")
    print("=" * 50)
    
    # Test cases for different providers and models
    test_cases = [
        {"provider": "gemini", "model": "gemini-2.5-pro", "api_key": "AIzaSyDcP6test_key"},
        {"provider": "gemini", "model": "gemini-2.5-flash-lite", "api_key": "AIzaSyDcP6test_key"},
        {"provider": "openai", "model": "gpt-4o", "api_key": None},  # No API key for static lookup
        {"provider": "anthropic", "model": "claude-3.5-sonnet", "api_key": None},  # No API key for static lookup
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        provider = test_case["provider"]
        model = test_case["model"]
        api_key = test_case["api_key"]
        
        print(f"\n{i}. Testing {provider}/{model}")
        
        # Build URL
        url = f"http://localhost:8000/api/llm/models/{provider}/{model}/max-tokens"
        if api_key:
            url += f"?api_key={api_key}"
        
        try:
            response = requests.get(url, timeout=30)
            
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                result = response.json()
                print(f"   ✅ SUCCESS")
                print(f"   Provider: {result.get('provider', 'N/A')}")
                print(f"   Model: {result.get('model', 'N/A')}")
                print(f"   Max Tokens: {result.get('max_tokens', 'N/A')}")
                print(f"   Source: {result.get('source', 'N/A')}")
                print(f"   Validated: {result.get('validated', False)}")
                
                if result.get('validation_error'):
                    print(f"   Validation Error: {result['validation_error']}")
            else:
                print(f"   ❌ FAILED: {response.text}")
                
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
    
    # Test the static lookup function directly
    print(f"\n5. Testing static lookup function")
    try:
        # This should work even if the backend is down
        from backend.app.services.llm_service import get_model_max_tokens
        
        static_tests = [
            ("gemini", "gemini-2.5-pro"),
            ("openai", "gpt-4o"),
            ("anthropic", "claude-3.5-sonnet"),
        ]
        
        for provider, model in static_tests:
            max_tokens = get_model_max_tokens(provider, model)
            print(f"   {provider}/{model}: {max_tokens} tokens")
            
    except Exception as e:
        print(f"   ❌ Static lookup test failed: {e}")

if __name__ == "__main__":
    test_max_tokens_detection()
