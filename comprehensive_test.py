#!/usr/bin/env python3
import requests
import json
import time
import os

print("=== COMPREHENSIVE PLATFORM TEST ===")

# Step 1: Create project test123
print("\n1. Creating project test123...")
project_url = "http://localhost:8002/projects"
project_data = {
    "name": "test123",
    "description": "Comprehensive test project for full workflow",
    "client_name": "Test Client",
    "client_contact": "test@example.com"
}

try:
    response = requests.post(project_url, json=project_data)
    print(f"Project Creation Status: {response.status_code}")
    if response.status_code == 200:
        project = response.json()
        project_id = project['id']
        print(f"✅ Project Created: {project_id}")
        print(f"Project Name: {project['name']}")
        
        # Step 2: Create and upload 5 test files
        print(f"\n2. Creating and uploading 5 test files...")
        
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
            try:
                files = {'files': (filename, content, 'text/plain')}
                upload_response = requests.post(upload_url, files=files)
                
                if upload_response.status_code == 200:
                    uploaded_count += 1
                    print(f"✅ Uploaded: {filename}")
                else:
                    print(f"❌ Failed to upload: {filename} - Status: {upload_response.status_code}")
                    
            except Exception as e:
                print(f"❌ Error uploading {filename}: {e}")
        
        print(f"\n📊 Upload Summary: {uploaded_count}/5 files uploaded successfully")
        
        # Step 3: Verify files are registered
        print(f"\n3. Verifying files are registered...")
        files_url = f"http://localhost:8002/projects/{project_id}/files"
        files_response = requests.get(files_url)
        
        if files_response.status_code == 200:
            files_list = files_response.json()
            print(f"✅ Registered Files Count: {len(files_list)}")
            for i, file_info in enumerate(files_list, 1):
                print(f"  {i}. {file_info['filename']} ({file_info['file_size']} bytes)")
        else:
            print(f"❌ Error getting files: {files_response.status_code}")
            
        # Step 4: Get project stats
        print(f"\n4. Getting initial project statistics...")
        stats_url = f"http://localhost:8002/projects/{project_id}/stats"
        stats_response = requests.get(stats_url)
        
        if stats_response.status_code == 200:
            stats = stats_response.json()
            print(f"📊 Initial Stats:")
            print(f"  - Total Files: {stats['total_files']}")
            print(f"  - Total Size: {stats['total_size']} bytes")
            print(f"  - File Types: {stats['file_types']}")
        
        print(f"\n✅ PROJECT SETUP COMPLETE")
        print(f"Project ID: {project_id}")
        print(f"Ready for document processing test...")
        
    else:
        print(f"❌ Project creation failed: {response.text}")
        
except Exception as e:
    print(f"❌ Error: {e}")
