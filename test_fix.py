import requests
import json

# Test the fix by trying to get a non-existent project
try:
    response = requests.get('http://localhost:8000/api/projects/non-existent-project-id')
    print(f'Status Code: {response.status_code}')
    print(f'Response: {response.text}')
except Exception as e:
    print(f'Error: {e}')
