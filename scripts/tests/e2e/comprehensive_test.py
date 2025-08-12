# Add missing generate_document function
def generate_document(project_id):
    """Generate the specified document for the project using the template"""
    log_step(7, f"Generating Document: '{DOCUMENT_TEMPLATE}'")
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/projects/{project_id}/generate-document",
            json={
                "name": DOCUMENT_TEMPLATE,
                "description": "Comprehensive technical deep-dive based on uploaded assessment documents",
                "format": "markdown"
            },
            headers=AUTH_HEADERS
        )
        if response.status_code == 200:
            result = response.json()
            log_success("Document generated successfully")
            log_info(f"Document ID: {result.get('document_id', 'Unknown')}")
            log_info(f"Content length: {len(result.get('content', ''))} characters")
            return True
        else:
            log_error(f"Document generation failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        log_error(f"Error generating document: {e}")
        return False
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

AUTH_HEADERS = {"Authorization": "Bearer service-backend-token"}

# Configuration
BACKEND_URL = "http://localhost:8000"
PROJECT_SERVICE_URL = "http://localhost:8002"
# Use the specific document and project as per user request
DOCUMENTS_FOLDER = r"C:\Users\deepakgupta13\OneDrive - Nagarro\Cloud Practice\migration_platform_2\NBQ Assessment documents\NBQ- Documents Received"
TARGET_DOCUMENT = "D8_NESA Self Assessment Report.pdf"
PROJECT_NAME = "nbqtest"
LLM_CONFIG_NAME = "gemini 2.5 pro 1"
DOCUMENT_TEMPLATE = "Current-State Technical Deep-Dive"

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
        "Neo4j": "http://localhost:7474",
    }
    
    all_healthy = True
    for service, url in services.items():
        try:
            if "localhost:8000" in url:
                response = requests.get(url, timeout=5, headers=AUTH_HEADERS)
            else:
                response = requests.get(url, timeout=5)
            if response.status_code == 200:
                log_success(f"{service} is running")
            else:
                log_error(f"{service} returned status {response.status_code}")
                all_healthy = False
        except Exception as e:
            if service == "Weaviate":
                continue  # Ignore Weaviate errors
            log_error(f"{service} is not accessible: {e}")
            all_healthy = False
    
    return all_healthy

def get_llm_configurations():
    """Get available LLM configurations"""
    log_step(2, "Getting LLM Configurations")
    
    try:
        response = requests.get(f"{BACKEND_URL}/llm-configurations", headers=AUTH_HEADERS)
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
        response = requests.post(f"{BACKEND_URL}/projects", json=project_data, headers=AUTH_HEADERS)
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

def upload_document(project_id):
    """Upload the specified document only"""
    log_step(4, f"Uploading Document '{TARGET_DOCUMENT}' from '{DOCUMENTS_FOLDER}'")
    file_path = os.path.join(DOCUMENTS_FOLDER, TARGET_DOCUMENT)
    if not os.path.exists(file_path):
        log_error(f"Document not found: {file_path}")
        return False
    try:
        with open(file_path, 'rb') as f:
            files = {'files': (TARGET_DOCUMENT, f, 'application/pdf')}
            response = requests.post(f"{BACKEND_URL}/upload/{project_id}", files=files, headers=AUTH_HEADERS)
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'success':
                    log_success(f"Uploaded: {TARGET_DOCUMENT}")
                    return True
                else:
                    log_error(f"Upload failed: {result}")
            else:
                log_error(f"Upload failed: {response.status_code}")
    except Exception as e:
        log_error(f"Error uploading {TARGET_DOCUMENT}: {e}")
    return False

def process_documents_and_check_md(project_id):
    """Process the uploaded document and check for .md file creation and chunking/embedding usage"""
    log_step(5, "Processing Document and Checking .md File, Chunking, Embedding")
    start_time = time.time()
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/projects/{project_id}/process-documents",
            json={"use_project_llm": True}
        )
        elapsed = time.time() - start_time
        if response.status_code == 200:
            result = response.json()
            log_success("Document processing completed")
            log_info(f"Processing time: {elapsed:.2f} seconds")
            log_info(f"Embeddings created: {result.get('embeddings', 0)}")
            log_info(f"Graph nodes created: {result.get('graph_nodes', 0)}")
            log_info(f"Files processed: {result.get('files_processed', 0)}")
            # Check for .md file in likely output locations
            md_found = False
            md_path = None
            # Try common output locations
            possible_dirs = [
                os.path.join("data", "projects", str(project_id), "documents"),
                os.path.join(DOCUMENTS_FOLDER),
                os.path.join("uploads", f"project_{project_id}"),
                os.path.join("."),
            ]
            for d in possible_dirs:
                if os.path.exists(d):
                    for f in os.listdir(d):
                        if f.endswith(".md") and TARGET_DOCUMENT.split(".")[0].replace(" ", "_") in f.replace(" ", "_"):
                            md_found = True
                            md_path = os.path.join(d, f)
                            break
                if md_found:
                    break
            if md_found:
                log_success(f"Markdown (.md) file created: {md_path}")
            else:
                log_error("No .md file found for the uploaded document!")
            # Check logs for chunking/embedding and correlation ID
            check_logs_for_chunking_and_correlation(project_id)
            return True
        else:
            log_error(f"Document processing failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        log_error(f"Error processing documents: {e}")
        return False

def check_logs_for_chunking_and_correlation(project_id):
    """Check logs for chunking, embedding, and correlation ID usage"""
    log_step("LOG", "Checking logs for chunking, embedding, and correlation ID")
    log_dir = os.path.join("logs")
    log_files = [
        "platform.log", "agents.log", "database.log", "project-service.log", "megaparse-service.log"
    ]
    found_chunking = False
    found_embedding = False
    found_correlation = False
    correlation_id = None
    for lf in log_files:
        lf_path = os.path.join(log_dir, lf)
        if os.path.exists(lf_path):
            with open(lf_path, encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if "chunk" in line.lower():
                        found_chunking = True
                    if "embedding" in line.lower():
                        found_embedding = True
                    if "correlation" in line.lower() or "correlation_id" in line.lower():
                        found_correlation = True
                        # Try to extract a correlation id
                        parts = line.split()
                        for p in parts:
                            if len(p) > 10 and ("-" in p or p.isalnum()):
                                correlation_id = p
                                break
    if found_chunking:
        log_success("Chunking activity found in logs")
    else:
        log_error("No chunking activity found in logs")
    if found_embedding:
        log_success("Embedding activity found in logs")
    else:
        log_error("No embedding activity found in logs")
    if found_correlation:
        log_info(f"Correlation ID found in logs: {correlation_id}")
    else:
        log_warning("No correlation ID found in logs")

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

def main():
    """Run the comprehensive test for the specified document and project"""
    print("🚀 Starting Comprehensive Knowledge Graph Pipeline Test (Custom)")
    print(f"Target Project: {PROJECT_NAME}")
    print(f"Target LLM: {LLM_CONFIG_NAME}")
    print(f"Document: {TARGET_DOCUMENT}")
    print(f"Document Template: {DOCUMENT_TEMPLATE}")
    summary = []
    # Step 1: Check services
    if not check_services():
        log_error("Some services are not running. Please start all services first.")
        summary.append("❌ Some services are not running.")
        return False
    # Step 2: Get LLM configurations
    llm_config_id = get_llm_configurations()
    if not llm_config_id:
        log_error("Could not find the required LLM configuration.")
        summary.append("❌ LLM configuration not found.")
        return False
    # Step 3: Create project
    project_id = create_test_project(llm_config_id)
    if not project_id:
        log_error("Failed to create test project.")
        summary.append("❌ Project creation failed.")
        return False
    # Step 4: Upload document
    if not upload_document(project_id):
        log_error("Failed to upload document.")
        summary.append("❌ Document upload failed.")
        return False
    # Step 5: Process document and check .md, chunking, embedding, correlation
    if not process_documents_and_check_md(project_id):
        log_error("Failed to process document or .md/chunking/embedding/correlation check failed.")
        summary.append("❌ Document processing or .md/chunking/embedding/correlation check failed.")
        return False
    # Step 6: Check graph data
    if not check_graph_data(project_id):
        log_error("No graph data was created.")
        summary.append("❌ No graph data created.")
        return False
    # Step 7: Generate document with specified template
    if not generate_document(project_id):
        log_error("Failed to generate document.")
        summary.append("❌ Document generation failed.")
        return False
    log_step("FINAL", "Test Completed! Review the above logs for details.")
    log_success("All main pipeline components executed. See above for any errors or warnings.")
    log_info(f"Project ID for further testing: {project_id}")
    # Final summary
    print("\n===== SUMMARY =====")
    for s in summary:
        print(s)
    print("===================\n")
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
