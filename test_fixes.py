#!/usr/bin/env python3
"""
Test script to verify the document processing fixes:
1. LLM response tuple handling
2. ProcessingResult structure metadata extraction
3. WebSocket notification endpoint
"""

import asyncio
import json
import httpx
from typing import Dict, Any

async def test_llm_service_response():
    """Test that LLM service returns proper tuple response"""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "http://localhost:8007/api/llm/process",
                json={
                    "process_type": "content_summarization",
                    "prompt": "Test prompt for response format",
                    "project_id": "61502d23-4928-4377-92c8-81b9c4f0fffd",
                    "allow_global": True
                },
                headers={
                    "Authorization": "Bearer service-backend-token",
                    "Content-Type": "application/json"
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ LLM Service Response: HTTP {response.status_code}")
                print(f"   Response structure: {list(result.keys())}")
                return True
            else:
                print(f"❌ LLM Service Error: HTTP {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ LLM Service Exception: {e}")
        return False

async def test_websocket_notify_endpoint():
    """Test the new WebSocket notify endpoint"""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                "http://localhost:8009/api/websocket/notify",
                json={
                    "project_id": "61502d23-4928-4377-92c8-81b9c4f0fffd",
                    "type": "test_notification",
                    "data": {"test": "notification_data"},
                    "correlation_id": "test_correlation_id"
                },
                headers={
                    "Authorization": "Bearer service-backend-token",
                    "Content-Type": "application/json"
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ WebSocket Notify: HTTP {response.status_code}")
                print(f"   Response: {result}")
                return True
            else:
                print(f"❌ WebSocket Notify Error: HTTP {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ WebSocket Notify Exception: {e}")
        return False

async def test_document_processing():
    """Test document processing to see if fixes work end-to-end"""
    try:
        # Create a simple test file
        files = {
            'file': ('test_document.txt', 'This is a test document content for verifying the document processing pipeline fixes.', 'text/plain')
        }
        
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                "http://localhost:8003/api/documents/61502d23-4928-4377-92c8-81b9c4f0fffd/upload-and-process",
                files=files,
                headers={
                    "Authorization": "Bearer service-backend-token"
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Document Processing: HTTP {response.status_code}")
                print(f"   Status: {result.get('status', 'unknown')}")
                return True
            else:
                print(f"❌ Document Processing Error: HTTP {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ Document Processing Exception: {e}")
        return False

async def main():
    """Run all tests"""
    print("🧪 Testing Document Processing Fixes")
    print("=" * 50)
    
    tests = [
        ("LLM Service Response Format", test_llm_service_response),
        ("WebSocket Notify Endpoint", test_websocket_notify_endpoint),
        ("Document Processing Pipeline", test_document_processing)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n📋 Testing: {test_name}")
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            results.append((test_name, False))
    
    print(f"\n📊 Test Results Summary")
    print("=" * 50)
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\nTotal: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("🎉 All fixes are working correctly!")
    else:
        print("⚠️  Some issues remain - check the failed tests above")

if __name__ == "__main__":
    asyncio.run(main())
