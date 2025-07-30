#!/usr/bin/env python3
import requests
import json

# Test real LLM functionality
url = "http://localhost:8000/api/test-llm"
data = {
    "provider": "openai",
    "model": "gpt-3.5-turbo",
    "apiKeyId": "OPENAI_API_KEY"
}

try:
    response = requests.post(url, json=data)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
except Exception as e:
    print(f"Error: {e}")
