import requests

# Create a test project first
project_data = {
    "name": "Test Project",
    "description": "Test project for file upload",
    "client_name": "Test Client",
    "client_contact": "test@example.com"
}

headers = {
    "Authorization": "Bearer service-backend-token",
    "Content-Type": "application/json"
}

response = requests.post('http://localhost:8002/projects', json=project_data, headers=headers)
print(f"Create Project Status Code: {response.status_code}")
print(f"Create Project Response: {response.text}")

if response.status_code == 200:
    project_id = response.json().get('id')
    print(f"Created project with ID: {project_id}")
    
    # Now test file upload with the actual project ID
    files = {'files': ('test_file.txt', open('test_file.txt', 'rb'), 'text/plain')}
    upload_response = requests.post(f'http://localhost:8000/upload/{project_id}', files=files)
    
    print(f"Upload Status Code: {upload_response.status_code}")
    print(f"Upload Response: {upload_response.text}")
