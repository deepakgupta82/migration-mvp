import requests

headers = {
    "Authorization": "Bearer service-backend-token",
    "Content-Type": "application/json"
}

# List all projects
response = requests.get('http://localhost:8002/projects', headers=headers)
print(f"List Projects Status Code: {response.status_code}")
print(f"List Projects Response: {response.text}")

# Check specific project
project_id = "c31db8a0-98ff-4e44-a687-0b629e418414"
response = requests.get(f'http://localhost:8002/projects/{project_id}', headers=headers)
print(f"\nGet Project Status Code: {response.status_code}")
print(f"Get Project Response: {response.text}")
