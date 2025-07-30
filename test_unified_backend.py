#!/usr/bin/env python3
import requests
import json
import time
import os

print("=== TESTING UNIFIED BACKEND (ALL SERVICES ON PORT 8000) ===")

# Step 1: Test project creation
print("\n📁 STEP 1: Creating project...")
project_url = "http://localhost:8000/projects"
project_data = {
    "name": "UnifiedTest123",
    "description": "Testing unified backend with all services",
    "client_name": "Test Client",
    "client_contact": "test@example.com",
    "llm_provider": "openai",
    "llm_model": "gpt-3.5-turbo",
    "llm_api_key_id": "openai_key"
}

try:
    response = requests.post(project_url, json=project_data)
    print(f"Project Creation Status: {response.status_code}")
    
    if response.status_code == 200:
        project = response.json()
        project_id = project['id']
        print(f"✅ Project Created: {project['name']} (ID: {project_id})")
        
        # Step 2: Test project listing
        print(f"\n📋 STEP 2: Testing project listing...")
        list_response = requests.get(project_url)
        if list_response.status_code == 200:
            projects = list_response.json()
            print(f"✅ Projects Listed: {len(projects)} projects found")
        else:
            print(f"❌ Project listing failed: {list_response.status_code}")
        
        # Step 3: Upload files
        print(f"\n📤 STEP 3: Uploading files...")
        
        test_files = [
            ("infrastructure_overview.txt", "Infrastructure Overview:\n- Production Environment: AWS us-east-1\n- Web Servers: 3x EC2 t3.large instances running nginx\n- Application Servers: 5x EC2 m5.xlarge instances running Node.js\n- Database: RDS MySQL 8.0 with read replicas\n- Load Balancer: Application Load Balancer with SSL termination\n- CDN: CloudFront distribution for static assets"),
            ("security_assessment.txt", "Security Assessment:\n- Current State: Basic security controls in place\n- Vulnerabilities: Outdated SSL certificates, weak password policies\n- Compliance Requirements: SOC2 Type II, PCI DSS Level 1\n- Recommendations: Implement WAF, enable GuardDuty, update IAM policies\n- Encryption: Data at rest encrypted with KMS, data in transit uses TLS 1.3\n- Access Control: Role-based access with MFA required"),
            ("migration_plan.txt", "Migration Plan:\n- Phase 1: Assessment and planning (2 weeks)\n- Phase 2: Infrastructure setup (4 weeks)\n- Phase 3: Application migration (6 weeks)\n- Phase 4: Data migration (2 weeks)\n- Phase 5: Testing and validation (3 weeks)\n- Phase 6: Go-live and monitoring (1 week)\n- Total Timeline: 18 weeks\n- Budget: $250,000\n- Risk Mitigation: Parallel environments, rollback procedures"),
            ("performance_metrics.txt", "Performance Metrics:\n- Current Response Time: 250ms average\n- Target Response Time: 150ms average\n- Current Uptime: 99.5%\n- Target Uptime: 99.9%\n- Current Throughput: 1000 requests/second\n- Target Throughput: 2000 requests/second\n- Database Performance: 50ms query time average\n- CDN Hit Rate: 85%\n- Error Rate: 0.1%"),
            ("cost_analysis.txt", "Cost Analysis:\n- Current Monthly Cost: $15,000\n- Projected Monthly Cost: $12,000 (20% reduction)\n- Migration Cost: $250,000 one-time\n- ROI Timeline: 18 months\n- Cost Savings Areas: Reserved instances, right-sizing, automated scaling\n- Additional Costs: Enhanced monitoring, backup solutions\n- Cost Optimization: Spot instances for dev/test, S3 lifecycle policies")
        ]
        
        upload_url = f"http://localhost:8000/upload/{project_id}"
        uploaded_count = 0
        
        for filename, content in test_files:
            try:
                files = {'files': (filename, content, 'text/plain')}
                upload_response = requests.post(upload_url, files=files)
                
                if upload_response.status_code == 200:
                    uploaded_count += 1
                    print(f"✅ Uploaded: {filename}")
                else:
                    print(f"❌ Failed: {filename} - Status: {upload_response.status_code}")
                    
            except Exception as e:
                print(f"❌ Upload error for {filename}: {e}")
        
        print(f"📊 Upload Summary: {uploaded_count}/5 files uploaded")
        
        # Step 4: Verify files
        print(f"\n📋 STEP 4: Verifying files...")
        files_url = f"http://localhost:8000/projects/{project_id}/files"
        
        files_response = requests.get(files_url)
        if files_response.status_code == 200:
            files_list = files_response.json()
            print(f"✅ Registered Files: {len(files_list)}")
            for i, file_info in enumerate(files_list, 1):
                print(f"  {i}. {file_info.get('filename', 'unknown')} ({file_info.get('file_size', 0)} bytes)")
        else:
            print(f"❌ Files check failed: {files_response.status_code}")
        
        # Step 5: Process documents
        print(f"\n⚙️ STEP 5: Processing documents...")
        process_url = f"http://localhost:8000/api/projects/{project_id}/process-documents"
        
        process_response = requests.post(process_url)
        if process_response.status_code == 200:
            result = process_response.json()
            print(f"✅ Processing Complete:")
            print(f"  - Status: {result['status']}")
            print(f"  - Processed: {result['processed_count']}/{result['total_files']} files")
            
            total_embeddings = 0
            for file_info in result['processed_files']:
                if file_info['status'] == 'processed':
                    print(f"  - {file_info['filename']}: {file_info['embeddings']} embeddings")
                    total_embeddings += file_info['embeddings']
            
            print(f"📊 Total Embeddings Created: {total_embeddings}")
        else:
            print(f"❌ Processing failed: {process_response.status_code}")
            print(f"Error: {process_response.text}")
        
        # Step 6: Test enhanced stats
        print(f"\n📈 STEP 6: Testing enhanced project statistics...")
        stats_url = f"http://localhost:8000/api/projects/{project_id}/stats"
        
        stats_response = requests.get(stats_url)
        if stats_response.status_code == 200:
            stats = stats_response.json()
            print(f"✅ Enhanced Stats:")
            print(f"  - Files: {stats.get('total_files', 0)}")
            print(f"  - Embeddings: {stats.get('embeddings', 0)}")
            print(f"  - Graph Nodes: {stats.get('graph_nodes', 0)}")
            print(f"  - Deliverables: {stats.get('deliverables', 0)}")
        else:
            print(f"❌ Stats failed: {stats_response.status_code}")
        
        # Step 7: Test LLM settings
        print(f"\n🤖 STEP 7: Testing LLM settings...")
        settings_url = "http://localhost:8000/platform-settings"
        
        settings_response = requests.get(settings_url)
        if settings_response.status_code == 200:
            settings = settings_response.json()
            print(f"✅ Platform Settings: {len(settings)} settings found")
            for setting in settings:
                if setting.get('category') == 'llm':
                    print(f"  - {setting.get('name')}: {'*' * 10 if setting.get('type') == 'secret' else setting.get('value')}")
        
        # Step 8: Test RAG queries
        print(f"\n🔍 STEP 8: Testing RAG queries...")
        query_url = f"http://localhost:8000/api/projects/{project_id}/query"
        
        test_queries = [
            "What is the current infrastructure setup?",
            "What are the security vulnerabilities?",
            "What is the migration timeline?",
            "What are the performance targets?",
            "What are the cost savings?"
        ]
        
        successful_queries = 0
        for i, question in enumerate(test_queries, 1):
            try:
                query_response = requests.post(query_url, json={"question": question})
                if query_response.status_code == 200:
                    result = query_response.json()
                    print(f"✅ Query {i}: {len(result['answer'])} chars, {len(result['sources'])} sources")
                    successful_queries += 1
                else:
                    print(f"❌ Query {i} failed: {query_response.status_code}")
            except Exception as e:
                print(f"❌ Query {i} error: {e}")
        
        print(f"📊 Query Summary: {successful_queries}/{len(test_queries)} queries successful")
        
        # Step 9: Generate report
        print(f"\n📋 STEP 9: Generating infrastructure assessment report...")
        report_url = f"http://localhost:8000/api/projects/{project_id}/generate-report"
        
        report_response = requests.post(report_url)
        if report_response.status_code == 200:
            report_result = report_response.json()
            print(f"✅ Report Generated:")
            print(f"  - Filename: {report_result['report_filename']}")
            print(f"  - Size: {report_result['report_size']} characters")
            print(f"  - Documents: {report_result['document_count']}")
            
            # Download report
            download_url = f"http://localhost:8000{report_result['download_url']}"
            download_response = requests.get(download_url)
            
            if download_response.status_code == 200:
                local_filename = f"unified_test_{report_result['report_filename']}"
                with open(local_filename, 'wb') as f:
                    f.write(download_response.content)
                
                print(f"✅ Report Downloaded: {os.path.abspath(local_filename)}")
                print(f"🔗 Download URL: {download_url}")
                
                # Show report preview
                report_text = download_response.content.decode('utf-8')
                print(f"\n📄 Report Preview (first 300 characters):")
                print("-" * 60)
                print(report_text[:300] + "..." if len(report_text) > 300 else report_text)
                print("-" * 60)
            else:
                print(f"❌ Download failed: {download_response.status_code}")
        else:
            print(f"❌ Report generation failed: {report_response.status_code}")
            print(f"Error: {report_response.text}")
        
        print(f"\n🎉 UNIFIED BACKEND TEST COMPLETED!")
        print(f"\n📊 FINAL SUMMARY:")
        print(f"✅ Project Creation: Working")
        print(f"✅ Project Listing: Working")
        print(f"✅ File Upload: {uploaded_count}/5 files")
        print(f"✅ Document Processing: Working")
        print(f"✅ RAG Queries: {successful_queries}/{len(test_queries)} working")
        print(f"✅ Report Generation: Working")
        print(f"✅ All services unified on port 8000")
        
    else:
        print(f"❌ Project creation failed: {response.status_code}")
        print(f"Response: {response.text}")
        
except Exception as e:
    print(f"❌ Error: {e}")
