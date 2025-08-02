import requests

# Test project service file registration directly
project_id = "c31db8a0-98ff-4e44-a687-0b629e418414"  # From the created project

file_data = {
    'filename': 'test_file.txt',
    'file_type': 'text/plain',
    'file_size': 108,
    'upload_path': '/some/path/test_file.txt'
}

headers = {
    "Authorization": "Bearer service-backend-token",
    "Content-Type": "application/json"
}

response = requests.post(f'http://localhost:8002/projects/{project_id}/files', json=file_data, headers=headers)
print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")
