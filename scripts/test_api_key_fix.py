#!/usr/bin/env python3
"""
Quick LLM API Key Test
Tests if the LLM service can now properly use the API key from the configuration
"""

import requests
import json

def test_llm_with_api_key():
    """Test LLM service with the project that was failing"""
    
    print("🧪 Testing LLM API Key Resolution...")
    
    test_payload = {
        "process_type": "entity_extraction",
        "prompt": "Extract entities from: Microsoft Azure SQL Server database running on Unix systems",
        "project_id": "7d1e347c-efdd-4bc5-a112-98ec17fdf31c"
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-Correlation-ID": "test-fix-verification"
    }
    
    try:
        print("Sending test request to LLM service...")
        print("(This may take 20-30 seconds - please wait)")
        
        response = requests.post(
            "http://localhost:8007/api/llm/process",
            json=test_payload,
            headers=headers,
            timeout=60
        )
        
        print(f"Response Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            success = result.get('success', False)
            
            print(f"Success: {success}")
            
            if success:
                print("✅ SUCCESS! API key resolution is now working!")
                print("🎉 Document processing should now work completely!")
                response_text = result.get('response', '')
                if response_text:
                    print(f"LLM Response preview: {response_text[:200]}...")
                return True
            else:
                error_msg = result.get('error', 'Unknown error')
                print(f"❌ FAILED: {error_msg}")
                
                if "No API key" in error_msg:
                    print("💡 API key is still not being found properly")
                    print("   The LLM service may need to be restarted to pick up code changes")
                
                return False
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            try:
                error_detail = response.json()
                print(f"Error details: {json.dumps(error_detail, indent=2)}")
            except:
                print(f"Raw response: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ Request timed out after 60 seconds")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("🔧 LLM API Key Fix Verification")
    print("=" * 60)
    
    success = test_llm_with_api_key()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ FIX SUCCESSFUL!")
        print("Your document processing pipeline should now work end-to-end!")
    else:
        print("❌ Fix needs more work or LLM service restart required")
        print("Try restarting the LLM service and run this test again")
    print("=" * 60)