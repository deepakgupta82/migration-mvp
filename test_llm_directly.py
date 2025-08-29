import requests
import json

# Test the gemini444 configuration
payload = {
    "config_id": "gemini444_1756352388",
    "provider": "gemini", 
    "model": "gemini-2.5-flash",
    "query": "Please respond with just 'Test successful' to confirm connectivity"
}

try:
    response = requests.post(
        "http://localhost:8000/api/llm/test-llm-config",
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=30
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.ok:
        data = response.json()
        print("\n✅ Success Response:")
        print(json.dumps(data, indent=2))
    else:
        print(f"\n❌ Error Response: {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"❌ Request failed: {e}")
