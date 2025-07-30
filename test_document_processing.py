#!/usr/bin/env python3
import requests
import json

# Test document processing
project_id = "069d48ff-c314-4c66-ad95-e2e39282af27"  # Use the project we just created
url = f"http://localhost:8000/api/projects/{project_id}/process-documents"

try:
    response = requests.post(url)
    print(f"Document Processing Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"Processing Result: {json.dumps(result, indent=2)}")
    else:
        print(f"Error: {response.text}")
except Exception as e:
    print(f"Error: {e}")
