#!/usr/bin/env python3
"""
Simple test to create project ABC with gemini 2.5 pro 1
"""

import requests
import json

# Create project ABC
project_data = {
    "name": "ABC",
    "description": "Test project for comprehensive knowledge graph pipeline testing",
    "client_name": "Test Client",
    "client_contact": "test@example.com",
    "default_llm_config_id": "gemini_2.5_pro_1_1754123560"  # From the LLM configs
}

print("Creating project ABC...")
response = requests.post("http://localhost:8000/projects", json=project_data)
print(f"Status: {response.status_code}")
print(f"Response: {response.text}")

if response.status_code in [200, 201]:
    project = response.json()
    project_id = project.get('id') or project.get('project_id')
    print(f"✅ Created project with ID: {project_id}")
    
    # Save project ID for next steps
    with open("test_project_id.txt", "w") as f:
        f.write(project_id)
    
    print(f"Project ID saved to test_project_id.txt")
else:
    print("❌ Failed to create project")
