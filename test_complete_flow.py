#!/usr/bin/env python3
import requests
import json

print("=== TESTING COMPLETE FLOW ===")

# Step 1: Create a project
print("\n1. Creating project...")
project_url = "http://localhost:8002/projects"
project_data = {
    "name": "Test Upload Project",
    "description": "Testing file upload and registration",
    "client_name": "Test Client",
    "client_contact": "test@example.com"
}

try:
    response = requests.post(project_url, json=project_data)
    print(f"Project Creation Status: {response.status_code}")
    if response.status_code == 200:
        project = response.json()
        project_id = project['id']
        print(f"Project Created: {project_id}")
        
        # Step 2: Upload files to the project
        print(f"\n2. Uploading files to project {project_id}...")
        upload_url = f"http://localhost:8000/upload/{project_id}"
        files = {'files': ('test.txt', 'This is a test file content for upload', 'text/plain')}
        
        upload_response = requests.post(upload_url, files=files)
        print(f"Upload Status: {upload_response.status_code}")
        print(f"Upload Response: {upload_response.json()}")
        
        # Step 3: Check if files were registered
        print(f"\n3. Checking registered files...")
        files_url = f"http://localhost:8002/projects/{project_id}/files"
        files_response = requests.get(files_url)
        print(f"Files Status: {files_response.status_code}")
        if files_response.status_code == 200:
            files_list = files_response.json()
            print(f"Registered Files Count: {len(files_list)}")
            for file_info in files_list:
                print(f"  - {file_info['filename']} ({file_info['file_size']} bytes)")
        else:
            print(f"Error getting files: {files_response.text}")
            
        # Step 4: Get project stats
        print(f"\n4. Getting project statistics...")
        stats_url = f"http://localhost:8002/projects/{project_id}/stats"
        stats_response = requests.get(stats_url)
        print(f"Stats Status: {stats_response.status_code}")
        if stats_response.status_code == 200:
            stats = stats_response.json()
            print(f"Project Stats: {json.dumps(stats, indent=2)}")
        
    else:
        print(f"Project creation failed: {response.text}")
        
except Exception as e:
    print(f"Error: {e}")
