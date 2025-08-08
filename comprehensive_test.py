#!/usr/bin/env python3
"""
Comprehensive test script to verify the complete knowledge graph pipeline.
Tests: Project creation, file upload, processing, graph visualization, and document generation.
"""

import requests
import json
import os
import time
import glob
from pathlib import Path

# Configuration
BACKEND_URL = "http://localhost:8000"
PROJECT_SERVICE_URL = "http://localhost:8002"
DOCUMENTS_FOLDER = r"C:\Users\deepakgupta13\Downloads\NBQ Assessment documents"
PROJECT_NAME = "ABC"
LLM_CONFIG_NAME = "gemini 2.5 pro 1"
DOCUMENT_TEMPLATE = "Standard Migration Playbook"

def log_step(step, message):
    """Log test steps with formatting"""
    print(f"\n{'='*60}")
    print(f"STEP {step}: {message}")
    print(f"{'='*60}")

def log_info(message):
    """Log info messages"""
    print(f"ℹ️  {message}")

def log_success(message):
    """Log success messages"""
    print(f"✅ {message}")

def log_error(message):
    """Log error messages"""
    print(f"❌ {message}")

def log_warning(message):
    """Log warning messages"""
    print(f"⚠️  {message}")

def check_services():
    """Check if all required services are running"""
    log_step(1, "Checking Services")
    
    services = {
        "Backend": f"{BACKEND_URL}/health",
        "Project Service": f"{PROJECT_SERVICE_URL}/health",
        "Weaviate": "http://localhost:8080/v1/.well-known/ready",
        "Neo4j": "http://localhost:7474",
    }
    
    all_healthy = True
    for service, url in services.items():
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                log_success(f"{service} is running")
            else:
                log_error(f"{service} returned status {response.status_code}")
                all_healthy = False
        except Exception as e:
            log_error(f"{service} is not accessible: {e}")
            all_healthy = False
    
    return all_healthy

def get_llm_configurations():
    """Get available LLM configurations"""
    log_step(2, "Getting LLM Configurations")
    
    try:
        response = requests.get(f"{BACKEND_URL}/llm-configurations")
        if response.status_code == 200:
            configs = response.json()
            log_success(f"Found {len(configs)} LLM configurations")
            
            # Find the target LLM config
            target_config = None
            for config in configs:
                if LLM_CONFIG_NAME.lower() in config.get('name', '').lower():
                    target_config = config
                    break
            
            if target_config:
                log_success(f"Found target LLM config: {target_config['name']} (ID: {target_config['id']})")
                return target_config['id']
            else:
                log_error(f"Could not find LLM config with name containing '{LLM_CONFIG_NAME}'")
                log_info("Available configurations:")
                for config in configs:
                    print(f"  - {config.get('name', 'Unknown')} (ID: {config['id']})")
                return None
        else:
            log_error(f"Failed to get LLM configurations: {response.status_code}")
            return None
    except Exception as e:
        log_error(f"Error getting LLM configurations: {e}")
        return None

def create_test_project(llm_config_id):
    """Create the test project"""
    log_step(3, f"Creating Project '{PROJECT_NAME}'")
    
    project_data = {
        "name": PROJECT_NAME,
        "description": "Test project for comprehensive knowledge graph pipeline testing",
        "client_name": "Test Client",
        "client_contact": "test@example.com",
        "default_llm_config_id": llm_config_id
    }
    
    try:
        response = requests.post(f"{BACKEND_URL}/projects", json=project_data)
        if response.status_code in [200, 201]:
            project = response.json()
            project_id = project.get('id') or project.get('project_id')
            log_success(f"Created project '{PROJECT_NAME}' with ID: {project_id}")
            log_info(f"LLM Config: {project.get('llm_provider', 'Unknown')}/{project.get('llm_model', 'Unknown')}")
            return project_id
        else:
            log_error(f"Failed to create project: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        log_error(f"Error creating project: {e}")
        return None

def upload_documents(project_id):
    """Upload all documents from the specified folder"""
    log_step(4, f"Uploading Documents from '{DOCUMENTS_FOLDER}'")
    
    if not os.path.exists(DOCUMENTS_FOLDER):
        log_error(f"Documents folder not found: {DOCUMENTS_FOLDER}")
        return False
    
    # Get all files from the folder
    files_to_upload = []
    for ext in ['*.txt', '*.pdf', '*.docx', '*.doc', '*.md']:
        files_to_upload.extend(glob.glob(os.path.join(DOCUMENTS_FOLDER, ext)))
    
    if not files_to_upload:
        log_error(f"No documents found in {DOCUMENTS_FOLDER}")
        return False
    
    log_info(f"Found {len(files_to_upload)} files to upload")
    
    uploaded_count = 0
    for file_path in files_to_upload:
        try:
            filename = os.path.basename(file_path)
            log_info(f"Uploading: {filename}")
            
            with open(file_path, 'rb') as f:
                files = {'files': (filename, f, 'application/octet-stream')}
                response = requests.post(f"{BACKEND_URL}/upload/{project_id}", files=files)
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('status') == 'success':
                        uploaded_count += 1
                        log_success(f"Uploaded: {filename}")
                    else:
                        log_error(f"Upload failed for {filename}: {result}")
                else:
                    log_error(f"Upload failed for {filename}: {response.status_code}")
                    
        except Exception as e:
            log_error(f"Error uploading {filename}: {e}")
    
    log_success(f"Successfully uploaded {uploaded_count}/{len(files_to_upload)} files")
    return uploaded_count > 0

def process_documents(project_id):
    """Process the uploaded documents"""
    log_step(5, "Processing Documents")
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/projects/{project_id}/process-documents",
            json={"use_project_llm": True}
        )
        
        if response.status_code == 200:
            result = response.json()
            log_success("Document processing completed")
            log_info(f"Embeddings created: {result.get('embeddings', 0)}")
            log_info(f"Graph nodes created: {result.get('graph_nodes', 0)}")
            log_info(f"Files processed: {result.get('files_processed', 0)}")
            return True
        else:
            log_error(f"Document processing failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        log_error(f"Error processing documents: {e}")
        return False

def check_graph_data(project_id):
    """Check if graph data was created"""
    log_step(6, "Checking Graph Data")
    
    try:
        response = requests.get(f"{BACKEND_URL}/api/projects/{project_id}/graph")
        if response.status_code == 200:
            graph_data = response.json()
            nodes = graph_data.get('nodes', [])
            edges = graph_data.get('edges', [])
            
            log_success(f"Graph data retrieved: {len(nodes)} nodes, {len(edges)} edges")
            
            if nodes:
                log_info("Sample nodes:")
                for i, node in enumerate(nodes[:3]):
                    print(f"  - {node.get('label', 'Unknown')}: {node.get('name', 'Unknown')}")
            
            return len(nodes) > 0
        else:
            log_error(f"Failed to get graph data: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        log_error(f"Error checking graph data: {e}")
        return False

def generate_document(project_id):
    """Generate the Standard Migration Playbook document"""
    log_step(7, f"Generating Document: '{DOCUMENT_TEMPLATE}'")
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/projects/{project_id}/generate-document",
            json={
                "name": DOCUMENT_TEMPLATE,
                "description": "Comprehensive migration playbook based on uploaded assessment documents",
                "format": "markdown"
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            log_success(f"Document generated successfully")
            log_info(f"Document ID: {result.get('document_id', 'Unknown')}")
            log_info(f"Content length: {len(result.get('content', ''))} characters")
            return True
        else:
            log_error(f"Document generation failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        log_error(f"Error generating document: {e}")
        return False

def main():
    """Run the comprehensive test"""
    print("🚀 Starting Comprehensive Knowledge Graph Pipeline Test")
    print(f"Target Project: {PROJECT_NAME}")
    print(f"Target LLM: {LLM_CONFIG_NAME}")
    print(f"Documents Folder: {DOCUMENTS_FOLDER}")
    print(f"Document Template: {DOCUMENT_TEMPLATE}")
    
    # Step 1: Check services
    if not check_services():
        log_error("Some services are not running. Please start all services first.")
        return False
    
    # Step 2: Get LLM configurations
    llm_config_id = get_llm_configurations()
    if not llm_config_id:
        log_error("Could not find the required LLM configuration.")
        return False
    
    # Step 3: Create project
    project_id = create_test_project(llm_config_id)
    if not project_id:
        log_error("Failed to create test project.")
        return False
    
    # Step 4: Upload documents
    if not upload_documents(project_id):
        log_error("Failed to upload documents.")
        return False
    
    # Step 5: Process documents
    if not process_documents(project_id):
        log_error("Failed to process documents.")
        return False
    
    # Step 6: Check graph data
    if not check_graph_data(project_id):
        log_error("No graph data was created.")
        return False
    
    # Step 7: Generate document
    if not generate_document(project_id):
        log_error("Failed to generate document.")
        return False
    
    log_step("FINAL", "Test Completed Successfully! 🎉")
    log_success("All pipeline components are working correctly")
    log_info(f"Project ID for further testing: {project_id}")
    
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
