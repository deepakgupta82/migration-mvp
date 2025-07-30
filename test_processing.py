#!/usr/bin/env python3
import requests
import json
import time

print("=== TESTING DOCUMENT PROCESSING ===")

project_id = "851d350f-aee4-4645-9efb-9a1247820cee"

# Step 1: Start document processing
print(f"\n1. Starting document processing for project {project_id}...")
process_url = f"http://localhost:8000/api/projects/{project_id}/process-documents"

try:
    response = requests.post(process_url)
    print(f"Processing Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Processing Result:")
        print(f"  - Status: {result['status']}")
        print(f"  - Message: {result['message']}")
        print(f"  - Total Files: {result['total_files']}")
        print(f"  - Processed Count: {result['processed_count']}")
        
        print(f"\n📊 Processed Files Details:")
        for i, file_info in enumerate(result['processed_files'], 1):
            print(f"  {i}. {file_info['filename']}")
            print(f"     - Status: {file_info['status']}")
            print(f"     - Chunks: {file_info['chunks']}")
            print(f"     - Embeddings: {file_info['embeddings']}")
        
        # Step 2: Check updated project stats
        print(f"\n2. Checking updated project statistics...")
        stats_url = f"http://localhost:8002/projects/{project_id}/stats"
        stats_response = requests.get(stats_url)
        
        if stats_response.status_code == 200:
            stats = stats_response.json()
            print(f"📊 Updated Stats:")
            print(f"  - Total Files: {stats['total_files']}")
            print(f"  - Total Size: {stats['total_size']} bytes")
            print(f"  - File Types: {stats['file_types']}")
            
        # Step 3: Check project status
        print(f"\n3. Checking project status...")
        project_url = f"http://localhost:8002/projects/{project_id}"
        project_response = requests.get(project_url)
        
        if project_response.status_code == 200:
            project = project_response.json()
            print(f"📋 Project Status: {project['status']}")
            
        print(f"\n✅ DOCUMENT PROCESSING COMPLETE")
        print(f"Ready for RAG and chat testing...")
        
    else:
        print(f"❌ Processing failed: {response.text}")
        
except Exception as e:
    print(f"❌ Error: {e}")
