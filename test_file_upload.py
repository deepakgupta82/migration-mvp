#!/usr/bin/env python3
import requests

# Test file upload with registration
url = "http://localhost:8000/upload/test-project-123"

# Create a test file
files = {'files': ('test.txt', 'This is a test file content', 'text/plain')}

try:
    response = requests.post(url, files=files)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    
    # Check if files were registered in project service
    project_files_url = "http://localhost:8002/projects/test-project-123/files"
    files_response = requests.get(project_files_url)
    print(f"\nProject Files Status: {files_response.status_code}")
    if files_response.status_code == 200:
        print(f"Registered Files: {files_response.json()}")
    else:
        print(f"Error getting files: {files_response.text}")
        
except Exception as e:
    print(f"Error: {e}")
