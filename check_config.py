#!/usr/bin/env python3
"""Check project and LLM configuration details"""

import requests
import json

def check_config():
    headers = {
        'Authorization': 'Bearer service-backend-token',
        'Content-Type': 'application/json'
    }
    
    project_id = "61502d23-4928-4377-92c8-81b9c4f0fffd"
    
    print(f"Checking project: {project_id}")
    
    # Get project details
    try:
        project_resp = requests.get(f"http://localhost:8002/projects/{project_id}", headers=headers)
        print(f"Project response: {project_resp.status_code}")
        if project_resp.status_code == 200:
            project_data = project_resp.json()
            print(f"Project data: {json.dumps(project_data, indent=2)}")
            
            llm_config_id = project_data.get('llm_configuration_id')
            print(f"LLM Config ID: {llm_config_id}")
            
            if llm_config_id:
                # Get LLM configuration
                llm_resp = requests.get(f"http://localhost:8002/llm-configurations/{llm_config_id}", headers=headers)
                print(f"LLM config response: {llm_resp.status_code}")
                if llm_resp.status_code == 200:
                    llm_data = llm_resp.json()
                    print(f"LLM Config: {json.dumps(llm_data, indent=2)}")
                else:
                    print(f"LLM config error: {llm_resp.text}")
        else:
            print(f"Project error: {project_resp.text}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_config()
