#!/usr/bin/env python3
"""
Test direct LLM service functionality with project-specific configuration
"""
import asyncio
import httpx
import json

async def test_llm_service():
    """Test the LLM service with project-specific configuration"""
    
    project_id = "61502d23-4928-4377-92c8-81b9c4f0fffd"
    llm_service_url = "http://localhost:8007"
    
    print(f"Testing LLM service at {llm_service_url}")
    print(f"Project ID: {project_id}")
    print("-" * 50)
    
    # Test payload
    payload = {
        "process_type": "content_summarization",
        "project_id": project_id,
        "prompt": "Summarize this: The quick brown fox jumps over the lazy dog.",
        "input_text": "This is a test document to summarize."
    }
    
    async with httpx.AsyncClient() as client:
        try:
            print("Testing LLM process endpoint...")
            response = await client.post(
                f"{llm_service_url}/api/llm/process",
                json=payload,
                timeout=30.0
            )
            
            print(f"Status Code: {response.status_code}")
            print(f"Response Headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                result = response.json()
                print("\n✅ SUCCESS: LLM service call successful!")
                print(f"Response: {json.dumps(result, indent=2)}")
            else:
                print(f"\n❌ FAILED: {response.status_code}")
                print(f"Error Response: {response.text}")
                
        except Exception as e:
            print(f"\n💥 ERROR: Exception occurred: {e}")

if __name__ == "__main__":
    asyncio.run(test_llm_service())
