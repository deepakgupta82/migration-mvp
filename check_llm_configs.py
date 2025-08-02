import requests

response = requests.get('http://localhost:8000/llm-configurations')
print(f"Status Code: {response.status_code}")
print(f"LLM Configurations: {response.json()}")
