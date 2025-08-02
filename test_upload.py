import requests

# Test file upload
files = {'files': ('test_file.txt', open('test_file.txt', 'rb'), 'text/plain')}
response = requests.post('http://localhost:8000/upload/test-project-123', files=files)

print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")
