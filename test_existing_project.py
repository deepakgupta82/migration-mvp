import requests

# Test with existing project
project_id = "3b50a477-701f-427e-9f26-20b81d5ff00e"  # nbq4 project

# Test file upload with existing project
files = {'files': ('test_file.txt', open('test_file.txt', 'rb'), 'text/plain')}
upload_response = requests.post(f'http://localhost:8000/upload/{project_id}', files=files)

print(f"Upload Status Code: {upload_response.status_code}")
print(f"Upload Response: {upload_response.text}")
