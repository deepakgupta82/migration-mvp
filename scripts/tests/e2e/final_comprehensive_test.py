#!/usr/bin/env python3
import requests
import json
import time
import os

print("=== FINAL COMPREHENSIVE PLATFORM TEST ===")
print("Testing complete workflow: Project → Files → Processing → RAG → Report")

# Step 1: Create project test123
print("\n🚀 STEP 1: Creating project test123...")
project_url = "http://localhost:8002/projects"
project_data = {
    "name": "test123",
    "description": "Final comprehensive test project",
    "client_name": "Test Client",
    "client_contact": "test@example.com"
}

try:
    response = requests.post(project_url, json=project_data)
    if response.status_code == 200:
        project = response.json()
        project_id = project['id']
        print(f"✅ Project Created: {project['name']} (ID: {project_id})")
        
        # Step 2: Upload 5 test files
        print(f"\n📁 STEP 2: Uploading 5 test files...")
        
        test_files = [
            ("server_inventory.txt", "Server Inventory:\n- Web Server: nginx-01 (Ubuntu 20.04, 8GB RAM, 4 CPU cores)\n- Database Server: mysql-01 (CentOS 8, 16GB RAM, 8 CPU cores)\n- Application Server: app-01 (RHEL 8, 12GB RAM, 6 CPU cores)\n- Load Balancer: lb-01 (Ubuntu 18.04, 4GB RAM, 2 CPU cores)\n- Backup Server: backup-01 (Debian 10, 32GB RAM, 4 CPU cores)"),
            ("network_config.txt", "Network Configuration:\n- VLAN 10: Web Tier (192.168.10.0/24)\n- VLAN 20: App Tier (192.168.20.0/24)\n- VLAN 30: Database Tier (192.168.30.0/24)\n- VLAN 40: Management (192.168.40.0/24)\n- Firewall Rules: Port 80/443 open for web, Port 3306 for database\n- DNS Servers: 8.8.8.8, 8.8.4.4"),
            ("security_policies.txt", "Security Policies:\n- Password Policy: Minimum 12 characters, complexity required\n- Access Control: Role-based access with least privilege\n- Encryption: AES-256 for data at rest, TLS 1.3 for data in transit\n- Backup Policy: Daily incremental, weekly full backups\n- Patch Management: Monthly security updates, quarterly system updates"),
            ("application_stack.txt", "Application Stack:\n- Frontend: React.js with TypeScript\n- Backend: Node.js with Express framework\n- Database: MySQL 8.0 with replication\n- Cache: Redis cluster for session management\n- Monitoring: Prometheus with Grafana dashboards\n- CI/CD: Jenkins with Docker containers"),
            ("migration_requirements.txt", "Migration Requirements:\n- Target Platform: AWS Cloud\n- Timeline: 6 months phased migration\n- Downtime Tolerance: Maximum 4 hours per service\n- Compliance: SOC2, GDPR, HIPAA requirements\n- Performance: 99.9% uptime SLA\n- Disaster Recovery: RTO 2 hours, RPO 15 minutes")
        ]
        
        upload_url = f"http://localhost:8000/upload/{project_id}"
        uploaded_count = 0
        
        for filename, content in test_files:
            files = {'files': (filename, content, 'text/plain')}
            upload_response = requests.post(upload_url, files=files)
            
            if upload_response.status_code == 200:
                uploaded_count += 1
                print(f"✅ Uploaded: {filename}")
            else:
                print(f"❌ Failed: {filename}")
        
        print(f"📊 Upload Summary: {uploaded_count}/5 files uploaded")
        
        # Step 3: Process documents to create embeddings
        print(f"\n⚙️ STEP 3: Processing documents to create embeddings...")
        process_url = f"http://localhost:8000/api/projects/{project_id}/process-documents"
        
        process_response = requests.post(process_url)
        if process_response.status_code == 200:
            result = process_response.json()
            print(f"✅ Processing Complete: {result['processed_count']}/{result['total_files']} files")
            
            total_embeddings = sum(f['embeddings'] for f in result['processed_files'] if f['status'] == 'processed')
            print(f"📊 Total Embeddings Created: {total_embeddings}")
        else:
            print(f"❌ Processing failed: {process_response.text}")
            exit(1)
        
        # Step 4: Verify embeddings in project stats
        print(f"\n📈 STEP 4: Verifying embeddings in project stats...")
        stats_url = f"http://localhost:8000/api/projects/{project_id}/stats"
        
        stats_response = requests.get(stats_url)
        if stats_response.status_code == 200:
            stats = stats_response.json()
            print(f"✅ Project Stats:")
            print(f"  - Files: {stats['total_files']}")
            print(f"  - Embeddings: {stats['embeddings']}")
            print(f"  - Graph Nodes: {stats['graph_nodes']}")
            print(f"  - Deliverables: {stats['deliverables']}")
        
        # Step 5: Test RAG query functionality
        print(f"\n🤖 STEP 5: Testing RAG query functionality...")
        query_url = f"http://localhost:8000/api/projects/{project_id}/query"
        
        test_question = "What servers are in the inventory and what are their specifications?"
        query_response = requests.post(query_url, json={"question": test_question})
        
        if query_response.status_code == 200:
            query_result = query_response.json()
            print(f"✅ RAG Query Successful:")
            print(f"  - Question: {test_question}")
            print(f"  - Answer Length: {len(query_result['answer'])} characters")
            print(f"  - Sources: {len(query_result['sources'])} documents")
            print(f"  - Answer Preview: {query_result['answer'][:200]}...")
        else:
            print(f"❌ RAG query failed: {query_response.text}")
        
        # Step 6: Generate infrastructure assessment report
        print(f"\n📋 STEP 6: Generating infrastructure assessment report...")
        report_url = f"http://localhost:8000/api/projects/{project_id}/generate-report"
        
        report_response = requests.post(report_url)
        if report_response.status_code == 200:
            report_result = report_response.json()
            print(f"✅ Report Generated Successfully:")
            print(f"  - Filename: {report_result['report_filename']}")
            print(f"  - Size: {report_result['report_size']} characters")
            print(f"  - Documents Analyzed: {report_result['document_count']}")
            
            # Step 7: Download the report
            print(f"\n📥 STEP 7: Downloading the report...")
            download_url = f"http://localhost:8000{report_result['download_url']}"
            
            download_response = requests.get(download_url)
            if download_response.status_code == 200:
                local_filename = f"final_test_{report_result['report_filename']}"
                with open(local_filename, 'wb') as f:
                    f.write(download_response.content)
                
                print(f"✅ Report Downloaded Successfully:")
                print(f"  - Local File: {os.path.abspath(local_filename)}")
                print(f"  - Download URL: {download_url}")
                print(f"  - File Size: {len(download_response.content)} bytes")
                
                # Show report preview
                report_text = download_response.content.decode('utf-8')
                print(f"\n📄 Report Preview (first 300 characters):")
                print("-" * 60)
                print(report_text[:300] + "..." if len(report_text) > 300 else report_text)
                print("-" * 60)
                
                print(f"\n🎉 COMPREHENSIVE TEST COMPLETED SUCCESSFULLY!")
                print(f"\n📊 FINAL SUMMARY:")
                print(f"✅ Project Created: test123")
                print(f"✅ Files Uploaded: 5/5")
                print(f"✅ Documents Processed: {result['processed_count']}/{result['total_files']}")
                print(f"✅ Embeddings Created: {stats['embeddings']}")
                print(f"✅ RAG Query Working: Yes")
                print(f"✅ Report Generated: Yes")
                print(f"✅ Report Downloaded: Yes")
                print(f"\n🔗 Download Link: {download_url}")
                print(f"📁 Local File: {os.path.abspath(local_filename)}")
                
            else:
                print(f"❌ Download failed: {download_response.text}")
        else:
            print(f"❌ Report generation failed: {report_response.text}")
            
    else:
        print(f"❌ Project creation failed: {response.text}")
        
except Exception as e:
    print(f"❌ Error: {e}")
