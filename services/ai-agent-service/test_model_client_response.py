"""Test the ModelClientWrapper response structure"""
import asyncio
import json
from app.core.autogen_copilot import AutoGenCopilot

async def test_model_client_response():
    """Test what the model client create() method returns"""
    config = {
        'model': 'gemini-2.5-pro',
        'provider': 'gemini',
        'api_key': 'test-key',
        'project_id': 'test'
    }
    
    copilot = AutoGenCopilot(config)
    client = copilot._create_model_client()
    
    test_messages = [
        {'role': 'user', 'content': 'Say OK'}
    ]
    
    try:
        print("Testing ModelClientWrapper.create()...")
        response = await client.create(messages=test_messages)
        
        print(f"\n✅ Response type: {type(response)}")
        
        if isinstance(response, dict):
            print(f"✅ Response keys: {list(response.keys())}")
            print("\n✅ Response structure:")
            print(json.dumps(response, indent=2))
            
            # Check if it has the expected OpenAI structure
            if "choices" in response:
                print("\n✅ Has 'choices' key")
                if response["choices"] and "message" in response["choices"][0]:
                    print("✅ Has 'choices[0].message' key")
                    if "content" in response["choices"][0]["message"]:
                        print("✅ Has 'choices[0].message.content' key")
                        print(f"\n Content: {response['choices'][0]['message']['content'][:200]}")
        else:
            print(f"\n❌ Response is not a dict: {str(response)[:200]}")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_model_client_response())
