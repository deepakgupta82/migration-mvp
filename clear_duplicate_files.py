#!/usr/bin/env python3
import requests

# Clear duplicate files for nbq1 project
project_id = "bdc9bfe3-65a4-4b48-8f5a-12434bc40872"

# Get current files
files_url = f"http://localhost:8002/projects/{project_id}/files"
response = requests.get(files_url)

if response.status_code == 200:
    files = response.json()
    print(f"Current files count: {len(files)}")
    
    # Show file details
    for i, file_info in enumerate(files):
        print(f"{i+1}. {file_info['filename']} - Size: {file_info['file_size']} - Date: {file_info.get('upload_timestamp', 'N/A')}")
else:
    print(f"Error getting files: {response.status_code}")
