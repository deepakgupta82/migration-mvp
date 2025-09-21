#!/usr/bin/env python3
"""
Test script to verify the AutoGen discussion endpoint after the real fix
"""

import requests
import json
import time

def test_autogen_endpoint():
    """Test the AutoGen discussion endpoint with real project ID"""
    
    # Test endpoint URL
    url = 'http://localhost:8008/api/autogen/discussions/start'
    
    # Test payload with the real project ID that has LLM config
    payload = {
        'message': 'Do we have enough data to do migration?',
        'project_id': '1f69de03-0ce6-4c0b-8820-2883eaa3dd4f'  # Real project ID with Gemini config
    }
    
    print("Testing AutoGen discussion endpoint with REAL project...")
    print(f"URL: {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print("-" * 50)
    
    try:
        # Make the request
        response = requests.post(url, json=payload, timeout=60)  # Longer timeout for LLM calls
        
        print(f"Status Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        print("-" * 50)
        
        if response.status_code == 200:
            print("✅ SUCCESS: Request completed successfully!")
            result = response.json()
            print(f"Response keys: {list(result.keys())}")
            
            # Check for specific success indicators
            if result.get('status') == 'success':
                print("✅ AutoGen discussion completed successfully!")
                print(f"Session ID: {result.get('session_id', 'N/A')}")
                print(f"Participating Agents: {result.get('participating_agents', [])}")
                
                # Check for messages or result content
                if 'result' in result and 'messages' in result['result']:
                    messages = result['result']['messages']
                    print(f"Number of messages: {len(messages)}")
                    for i, msg in enumerate(messages[:3]):  # Show first 3 messages
                        print(f"  Message {i+1}: {msg.get('source', 'Unknown')} - {msg.get('content', '')[:100]}...")
                else:
                    print("Warning: No messages found in result")
                    
            else:
                print(f"❌ Request succeeded but AutoGen reported status: {result.get('status')}")
                if 'error' in result:
                    print(f"Error: {result['error']}")
                    
        elif response.status_code == 422:
            print("❌ VALIDATION ERROR: Request payload validation failed")
            try:
                error_detail = response.json()
                print(f"Error details: {json.dumps(error_detail, indent=2)}")
            except:
                print(f"Raw response: {response.text}")
                
        elif response.status_code == 500:
            print("❌ SERVER ERROR: Internal server error occurred")
            try:
                error_detail = response.json()
                print(f"Error details: {json.dumps(error_detail, indent=2)}")
                
                # Check if it's still the SimpleNamespace error
                if 'SimpleNamespace' in str(error_detail):
                    print("\n🔍 DIAGNOSIS: Still getting SimpleNamespace error")
                    print("This means the fix needs more work")
                elif 'LLM' in str(error_detail):
                    print("\n🔍 DIAGNOSIS: LLM-related error")
                    print("This means we're past the SimpleNamespace issue")
                else:
                    print("\n🔍 DIAGNOSIS: Unknown error type")
                    
            except:
                print(f"Raw response: {response.text}")
        else:
            print(f"❌ UNEXPECTED STATUS: {response.status_code}")
            print(f"Response: {response.text[:500]}...")
            
    except requests.exceptions.ConnectionError:
        print("❌ CONNECTION ERROR: Could not connect to the service")
        print("Make sure the AI Agent service is running on port 8008")
        
    except requests.exceptions.Timeout:
        print("❌ TIMEOUT ERROR: Request took too long to complete")
        print("The AutoGen discussion may be processing, but took longer than expected")
        
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {type(e).__name__}: {e}")

if __name__ == "__main__":
    test_autogen_endpoint()
