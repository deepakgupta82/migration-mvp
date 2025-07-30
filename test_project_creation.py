#!/usr/bin/env python3
import requests
import json

# Test project creation
url = "http://localhost:8002/projects"
data = {
    "name": "Test Project API",
    "description": "Testing project creation via API",
    "client_name": "Test Client",
    "client_contact": "test@example.com"
}

try:
    response = requests.post(url, json=data)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
except Exception as e:
    print(f"Error: {e}")
