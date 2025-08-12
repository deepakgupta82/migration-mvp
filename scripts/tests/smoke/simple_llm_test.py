#!/usr/bin/env python3
import requests
import json

print("=== SIMPLE LLM TEST ===")

url = "http://localhost:8000/api/test-llm"
data = {
    "provider": "openai",
    "model": "gpt-3.5-turbo",
    "apiKeyId": "OPENAI_API_KEY"
}

try:
    print("Sending LLM test request...")
    response = requests.post(url, json=data, timeout=10)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
except Exception as e:
    print(f"Error: {e}")
