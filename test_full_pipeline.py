#!/usr/bin/env python3
"""
Document Processing Pipeline Test
Tests the complete document processing workflow including graph service integration
"""

import asyncio
import httpx
import json
import uuid
import tempfile
import os
from datetime import datetime

async def test_document_processing_pipeline():
    """Test the complete document processing pipeline"""
    print("=" * 80)
    print("🧪 DOCUMENT PROCESSING PIPELINE TEST")
    print("=" * 80)
    print(f"Started at: {datetime.now().isoformat()}")
    print()
    
    # Test configuration
    project_id = "test-project-123"
    correlation_id = str(uuid.uuid4())
    
    # Create a test Excel file for processing
    test_content = """Project,Environment,Server Name,IP Address,OS,CPU Cores,RAM GB,Application
TechCorp,Production,WEB-PROD-01,192.168.1.10,Windows Server 2019,8,32,IIS Web Server
TechCorp,Production,DB-PROD-01,192.168.1.11,Windows Server 2019,16,64,SQL Server 2019
TechCorp,Production,APP-PROD-01,192.168.1.12,Windows Server 2019,8,32,Application Server"""
    
    # Test 1: Check Service Health
    print("📋 Test 1: Service Health Checks")
    services = {
        "Document Service": "http://localhost:8003/health",
        "Vector Service": "http://localhost:8005/health", 
        "Graph Service": "http://localhost:8006/health",
        "Storage Service": "http://localhost:8010/health"
    }
    
    healthy_services = {}
    for service_name, health_url in services.items():
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(health_url)
                if response.status_code == 200:
                    print(f"   ✅ {service_name}: Healthy")
                    healthy_services[service_name] = True
                else:
                    print(f"   ❌ {service_name}: Unhealthy ({response.status_code})")
                    healthy_services[service_name] = False
        except Exception as e:
            print(f"   ❌ {service_name}: Connection failed - {e}")
            healthy_services[service_name] = False
    
    print()
    
    if not all(healthy_services.values()):
        print("⚠️  Some services are unhealthy. Testing will continue but may fail.")
        print()
    
    # Test 2: Upload Test Document
    print("📋 Test 2: Document Upload Test")
    
    # Create a temporary CSV file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as temp_file:
        temp_file.write(test_content)
        temp_file_path = temp_file.name
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Upload file
            with open(temp_file_path, 'rb') as f:
                files = {'files': ('test_infrastructure.csv', f, 'text/csv')}
                data = {'correlation_id': correlation_id}
                
                print(f"   📤 Uploading test document...")
                upload_response = await client.post(
                    f"http://localhost:8010/api/storage/projects/{project_id}/upload/uploads_raw",
                    files=files,
                    data=data,
                    headers={"Authorization": "Bearer service-backend-token"}
                )
                
                if upload_response.status_code == 200:
                    print(f"   ✅ Document uploaded successfully")
                    upload_result = upload_response.json()
                    print(f"   📁 File: {upload_result.get('files', [{}])[0].get('filename', 'unknown')}")
                else:
                    print(f"   ❌ Upload failed: {upload_response.status_code}")
                    print(f"   Error: {upload_response.text[:200]}")
                    return False
    except Exception as e:
        print(f"   ❌ Upload test failed: {e}")
        return False
    finally:
        # Clean up temp file
        try:
            os.unlink(temp_file_path)
        except:
            pass
    
    print()
    
    # Test 3: Process Document with Enhanced Workflow
    print("📋 Test 3: Document Processing with Enhanced Workflow")
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            # Get list of files to process
            files_response = await client.get(
                f"http://localhost:8010/api/storage/projects/{project_id}/files/uploads_raw",
                headers={"Authorization": "Bearer service-backend-token"}
            )
            
            if files_response.status_code != 200:
                print(f"   ❌ Failed to get file list: {files_response.status_code}")
                return False
            
            files_data = files_response.json()
            if not files_data.get('files'):
                print(f"   ❌ No files found for processing")
                return False
            
            # Select files for processing
            files_to_process = [f['filename'] for f in files_data['files'][:1]]  # Process first file
            
            print(f"   📋 Processing files: {files_to_process}")
            
            # Start processing
            process_payload = {
                "files": files_to_process,
                "correlation_id": correlation_id
            }
            
            process_response = await client.post(
                f"http://localhost:8003/api/documents/{project_id}/process-selected",
                json=process_payload,
                headers={
                    "Authorization": "Bearer service-backend-token",
                    "X-Correlation-ID": correlation_id
                }
            )
            
            if process_response.status_code == 200:
                result = process_response.json()
                print(f"   ✅ Processing started successfully")
                print(f"   🔄 Job ID: {result.get('job_id')}")
                print(f"   📄 Files: {result.get('files_count', 0)}")
                
                # Wait a bit for processing to complete
                print(f"   ⏳ Waiting for processing to complete...")
                await asyncio.sleep(30)  # Wait 30 seconds
                
                return True
            else:
                print(f"   ❌ Processing failed: {process_response.status_code}")
                print(f"   Error: {process_response.text[:300]}")
                return False
                
    except Exception as e:
        print(f"   ❌ Document processing test failed: {e}")
        return False
    
    print()

async def check_processing_results(project_id: str, correlation_id: str):
    """Check the results of document processing"""
    print("📋 Test 4: Processing Results Check")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Check vector service results
            print("   🔍 Checking vector service results...")
            vector_response = await client.get(
                f"http://localhost:8005/api/vectors/projects/{project_id}/stats",
                headers={"Authorization": "Bearer service-backend-token"}
            )
            
            if vector_response.status_code == 200:
                vector_stats = vector_response.json()
                embeddings_count = vector_stats.get('total_embeddings', 0)
                print(f"   ✅ Vector Service: {embeddings_count} embeddings created")
            else:
                print(f"   ⚠️  Vector Service: Status {vector_response.status_code}")
            
            # Check graph service results
            print("   🔍 Checking graph service results...")
            graph_response = await client.get(
                f"http://localhost:8006/api/graphs/projects/{project_id}/stats",
                headers={"Authorization": "Bearer service-backend-token"}
            )
            
            if graph_response.status_code == 200:
                graph_stats = graph_response.json()
                nodes_count = graph_stats.get('total_nodes', 0)
                relationships_count = graph_stats.get('total_relationships', 0)
                print(f"   ✅ Graph Service: {nodes_count} nodes, {relationships_count} relationships")
                
                if nodes_count == 0 and relationships_count == 0:
                    print(f"   ⚠️  WARNING: No entities or relationships found!")
                    print(f"   🔍 This suggests graph service integration may not be working")
                    return False
                else:
                    return True
            else:
                print(f"   ❌ Graph Service: Status {graph_response.status_code}")
                return False
                
    except Exception as e:
        print(f"   ❌ Results check failed: {e}")
        return False

async def main():
    """Main test function"""
    success = await test_document_processing_pipeline()
    
    if success:
        # Wait a bit more and check results
        print("⏳ Waiting additional time for all processing to complete...")
        await asyncio.sleep(30)
        
        project_id = "test-project-123"
        correlation_id = str(uuid.uuid4())
        
        results_ok = await check_processing_results(project_id, correlation_id)
        
        print()
        print("=" * 80)
        print("📊 FINAL TEST RESULTS")
        print("=" * 80)
        
        if results_ok:
            print("🎉 SUCCESS: Document processing pipeline with graph service integration is working!")
            print("✅ Both vector embeddings and graph entities/relationships were created")
        else:
            print("⚠️  ISSUE DETECTED: Graph service integration may not be working properly")
            print("📋 Recommendations:")
            print("   1. Check document service logs for graph integration calls")
            print("   2. Verify graph service process-structured endpoint is accessible")
            print("   3. Ensure enhanced workflow is enabled in document service")
            print("   4. Check environment variables for graph service integration")
    else:
        print()
        print("❌ Test failed during document processing setup")
    
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())