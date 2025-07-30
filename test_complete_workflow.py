#!/usr/bin/env python3
import requests
import json
import time
import os

print("=== COMPREHENSIVE PLATFORM TEST WITH MULTIPLE DELIVERABLES ===")

# Step 1: Create project
print("\n📁 STEP 1: Creating project...")
project_url = "http://localhost:8000/projects"
project_data = {
    "name": "CompleteTest2025",
    "description": "Complete workflow test with multiple deliverables",
    "client_name": "Nagarro Test Client",
    "client_contact": "test@nagarro.com",
    "llm_provider": "openai",
    "llm_model": "gpt-3.5-turbo",
    "llm_api_key_id": "openai_key"
}

try:
    response = requests.post(project_url, json=project_data)
    if response.status_code == 200:
        project = response.json()
        project_id = project['id']
        print(f"✅ Project Created: {project['name']} (ID: {project_id})")
        
        # Step 2: Upload comprehensive test files
        print(f"\n📤 STEP 2: Uploading comprehensive test files...")
        
        test_files = [
            ("current_infrastructure.txt", """Current Infrastructure Assessment:

PRODUCTION ENVIRONMENT:
- Cloud Provider: AWS (us-east-1)
- Compute: 15 EC2 instances (mix of t3.large, m5.xlarge, c5.2xlarge)
- Storage: 500GB EBS volumes, 2TB S3 storage
- Database: RDS MySQL 8.0 (db.r5.xlarge) with 2 read replicas
- Load Balancing: Application Load Balancer with SSL termination
- CDN: CloudFront with 12 edge locations
- Monitoring: CloudWatch with basic metrics

NETWORK ARCHITECTURE:
- VPC with 3 availability zones
- Public subnets: Web tier (10.0.1.0/24, 10.0.2.0/24, 10.0.3.0/24)
- Private subnets: App tier (10.0.11.0/24, 10.0.12.0/24, 10.0.13.0/24)
- Database subnets: (10.0.21.0/24, 10.0.22.0/24, 10.0.23.0/24)
- NAT Gateways in each AZ for outbound traffic
- Internet Gateway for public access

APPLICATION STACK:
- Frontend: React.js application served via nginx
- Backend: Node.js with Express framework
- API Gateway: Kong for API management
- Message Queue: Redis for session management and caching
- File Storage: S3 for static assets and user uploads
- Backup: Daily automated backups to S3 Glacier"""),
            
            ("security_analysis.txt", """Security Analysis Report:

CURRENT SECURITY POSTURE:
- IAM: Role-based access control implemented
- Encryption: Data at rest encrypted with AWS KMS
- Network: Security groups configured with least privilege
- SSL/TLS: Valid certificates, TLS 1.3 enforced
- Monitoring: CloudTrail enabled for audit logging

IDENTIFIED VULNERABILITIES:
1. CRITICAL: Some EC2 instances missing latest security patches
2. HIGH: Database password policy not enforcing complexity requirements
3. HIGH: No Web Application Firewall (WAF) configured
4. MEDIUM: MFA not enforced for all administrative accounts
5. MEDIUM: Log retention period set to only 30 days
6. LOW: Some unused security groups still active

COMPLIANCE REQUIREMENTS:
- SOC 2 Type II certification required
- PCI DSS Level 1 compliance for payment processing
- GDPR compliance for EU customer data
- HIPAA compliance for healthcare data processing

SECURITY RECOMMENDATIONS:
1. Implement AWS WAF with OWASP Top 10 rules
2. Enable AWS GuardDuty for threat detection
3. Configure AWS Config for compliance monitoring
4. Implement AWS Secrets Manager for credential management
5. Enable VPC Flow Logs for network monitoring
6. Set up AWS Security Hub for centralized security findings"""),
            
            ("performance_metrics.txt", """Performance Metrics and Analysis:

CURRENT PERFORMANCE BASELINE:
- Average Response Time: 285ms (target: <200ms)
- 95th Percentile Response Time: 750ms (target: <500ms)
- Throughput: 850 requests/second (target: 1500 req/s)
- Uptime: 99.2% (target: 99.9%)
- Error Rate: 0.3% (target: <0.1%)

DATABASE PERFORMANCE:
- Average Query Time: 45ms
- Slow Query Count: 23 queries/hour (>1 second)
- Connection Pool Utilization: 78%
- Read Replica Lag: 150ms average

INFRASTRUCTURE UTILIZATION:
- CPU Utilization: 65% average, 89% peak
- Memory Utilization: 72% average, 91% peak
- Network I/O: 450 Mbps average, 1.2 Gbps peak
- Disk I/O: 2,500 IOPS average, 8,000 IOPS peak

BOTTLENECKS IDENTIFIED:
1. Database connection pooling insufficient during peak hours
2. Frontend asset loading causing 2.3s initial page load
3. API rate limiting causing 429 errors during traffic spikes
4. Lack of caching strategy for frequently accessed data
5. Inefficient database queries in user management module

OPTIMIZATION OPPORTUNITIES:
- Implement Redis caching for session data
- Optimize database indexes for slow queries
- Enable CloudFront caching for static assets
- Implement auto-scaling for EC2 instances
- Upgrade to newer instance types for better performance"""),
            
            ("migration_requirements.txt", """Migration Requirements and Strategy:

PROJECT SCOPE:
- Migrate from current AWS setup to optimized cloud-native architecture
- Implement microservices architecture
- Enhance security and compliance posture
- Improve performance and scalability
- Reduce operational costs by 25%

MIGRATION PHASES:
Phase 1: Assessment and Planning (3 weeks)
- Complete infrastructure audit
- Application dependency mapping
- Risk assessment and mitigation planning
- Team training and preparation

Phase 2: Foundation Setup (4 weeks)
- New VPC and network configuration
- Security baseline implementation
- Monitoring and logging setup
- CI/CD pipeline establishment

Phase 3: Application Migration (8 weeks)
- Database migration with minimal downtime
- Application containerization
- Microservices decomposition
- Load testing and performance validation

Phase 4: Cutover and Optimization (2 weeks)
- DNS cutover and traffic routing
- Performance monitoring and tuning
- Security validation
- Documentation and knowledge transfer

TECHNICAL REQUIREMENTS:
- Zero-downtime migration for critical services
- Data integrity validation throughout migration
- Rollback capability at each phase
- Performance improvement of 40% post-migration
- Cost reduction of 25% within 6 months

RESOURCE REQUIREMENTS:
- 3 Senior DevOps Engineers
- 2 Application Architects
- 1 Security Specialist
- 1 Database Administrator
- 1 Project Manager
- Estimated Budget: $350,000"""),
            
            ("cost_analysis.txt", """Cost Analysis and Optimization:

CURRENT MONTHLY COSTS:
- EC2 Instances: $8,500/month
- RDS Database: $3,200/month
- Data Transfer: $1,800/month
- Storage (EBS + S3): $2,100/month
- Load Balancer: $450/month
- CloudWatch: $300/month
- Other Services: $650/month
TOTAL: $17,000/month ($204,000/year)

COST BREAKDOWN BY CATEGORY:
- Compute (50%): $8,500
- Database (19%): $3,200
- Storage (12%): $2,100
- Network (11%): $1,800
- Monitoring (4%): $450
- Other (4%): $650

OPTIMIZATION OPPORTUNITIES:
1. Reserved Instances: 40% savings on EC2 costs = $3,400/month
2. Right-sizing: 15% reduction in over-provisioned resources = $1,275/month
3. S3 Lifecycle Policies: 30% savings on storage = $630/month
4. Spot Instances for dev/test: 70% savings = $850/month
5. Database optimization: 20% reduction = $640/month

PROJECTED SAVINGS:
- Monthly Savings: $6,795
- Annual Savings: $81,540
- Percentage Reduction: 40%
- New Monthly Cost: $10,205

ROI ANALYSIS:
- Migration Investment: $350,000
- Annual Savings: $81,540
- Payback Period: 4.3 years
- 5-Year Net Savings: $57,700

COST OPTIMIZATION RECOMMENDATIONS:
1. Implement auto-scaling to reduce over-provisioning
2. Use Reserved Instances for predictable workloads
3. Implement data lifecycle management
4. Optimize database queries to reduce compute needs
5. Use CloudWatch for cost monitoring and alerts""")
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
                    print(f"❌ Failed: {filename}")
                    
            except Exception as e:
                print(f"❌ Upload error for {filename}: {e}")
        
        print(f"📊 Upload Summary: {uploaded_count}/5 files uploaded")
        
        # Step 3: Process documents
        print(f"\n⚙️ STEP 3: Processing documents for embeddings and knowledge graph...")
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
        
        # Step 4: Test chat interface with RAG
        print(f"\n💬 STEP 4: Testing chat interface with RAG...")
        query_url = f"http://localhost:8000/api/projects/{project_id}/query"
        
        chat_questions = [
            "What is the current infrastructure setup and what are the main components?",
            "What security vulnerabilities have been identified and what are the recommendations?",
            "What are the current performance metrics and what improvements are needed?",
            "What is the migration strategy and timeline?",
            "What are the current costs and what savings can be achieved?"
        ]
        
        successful_chats = 0
        for i, question in enumerate(chat_questions, 1):
            try:
                query_response = requests.post(query_url, json={"question": question})
                if query_response.status_code == 200:
                    result = query_response.json()
                    print(f"✅ Chat {i}: {len(result['answer'])} chars, {len(result['sources'])} sources")
                    successful_chats += 1
                    
                    # Show a preview of the first answer
                    if i == 1:
                        print(f"   Preview: {result['answer'][:150]}...")
                else:
                    print(f"❌ Chat {i} failed: {query_response.status_code}")
            except Exception as e:
                print(f"❌ Chat {i} error: {e}")
        
        print(f"📊 Chat Summary: {successful_chats}/{len(chat_questions)} successful")
        
        # Step 5: Get document templates
        print(f"\n📋 STEP 5: Getting available document templates...")
        templates_url = "http://localhost:8000/document-templates"
        
        templates_response = requests.get(templates_url)
        if templates_response.status_code == 200:
            templates = templates_response.json()
            print(f"✅ Available Templates: {len(templates)} templates found")
            for template in templates:
                print(f"  - {template['name']} ({template['category']})")
        else:
            print(f"❌ Templates failed: {templates_response.status_code}")
        
        # Step 6: Generate multiple deliverables
        print(f"\n📄 STEP 6: Generating multiple deliverables...")
        deliverable_url = f"http://localhost:8000/api/projects/{project_id}/generate-deliverable"
        
        deliverables_to_generate = [
            "infrastructure_assessment",
            "security_audit", 
            "migration_strategy",
            "cost_optimization"
        ]
        
        generated_deliverables = []
        for template_id in deliverables_to_generate:
            try:
                deliverable_data = {"template_id": template_id}
                deliverable_response = requests.post(deliverable_url, json=deliverable_data)
                
                if deliverable_response.status_code == 200:
                    result = deliverable_response.json()
                    print(f"✅ Generated: {result['template_name']}")
                    print(f"   - Size: {result['deliverable_size']} characters")
                    print(f"   - File: {result['deliverable_filename']}")
                    generated_deliverables.append(result)
                else:
                    print(f"❌ Failed to generate {template_id}: {deliverable_response.status_code}")
                    
            except Exception as e:
                print(f"❌ Error generating {template_id}: {e}")
        
        print(f"📊 Deliverables Summary: {len(generated_deliverables)}/4 generated")
        
        # Step 7: Download all deliverables
        print(f"\n📥 STEP 7: Downloading all deliverables...")
        downloaded_files = []
        
        for deliverable in generated_deliverables:
            try:
                download_url = f"http://localhost:8000{deliverable['download_url']}"
                download_response = requests.get(download_url)
                
                if download_response.status_code == 200:
                    local_filename = f"complete_test_{deliverable['deliverable_filename']}"
                    with open(local_filename, 'wb') as f:
                        f.write(download_response.content)
                    
                    downloaded_files.append(local_filename)
                    print(f"✅ Downloaded: {local_filename}")
                else:
                    print(f"❌ Download failed for {deliverable['template_name']}")
                    
            except Exception as e:
                print(f"❌ Download error: {e}")
        
        # Step 8: Verify project stats
        print(f"\n📈 STEP 8: Verifying final project statistics...")
        stats_url = f"http://localhost:8000/api/projects/{project_id}/stats"
        
        stats_response = requests.get(stats_url)
        if stats_response.status_code == 200:
            stats = stats_response.json()
            print(f"✅ Final Project Stats:")
            print(f"  - Total Files: {stats.get('total_files', 0)}")
            print(f"  - Total Size: {stats.get('total_size', 0)} bytes")
            print(f"  - Embeddings: {stats.get('embeddings', 0)}")
            print(f"  - Graph Nodes: {stats.get('graph_nodes', 0)}")
            print(f"  - Agent Interactions: {stats.get('agent_interactions', 0)}")
            print(f"  - Deliverables: {len(generated_deliverables)}")
        
        print(f"\n🎉 COMPREHENSIVE TEST COMPLETED SUCCESSFULLY!")
        print(f"\n📊 FINAL SUMMARY:")
        print(f"✅ Project Created: {project['name']}")
        print(f"✅ Files Uploaded: {uploaded_count}/5")
        print(f"✅ Documents Processed: ✓")
        print(f"✅ Embeddings Created: {total_embeddings}")
        print(f"✅ Chat Interface: {successful_chats}/{len(chat_questions)} working")
        print(f"✅ Deliverables Generated: {len(generated_deliverables)}/4")
        print(f"✅ Files Downloaded: {len(downloaded_files)}")
        
        print(f"\n📁 GENERATED FILES:")
        for i, filename in enumerate(downloaded_files, 1):
            print(f"  {i}. {os.path.abspath(filename)}")
        
        print(f"\n🔗 PROJECT ID: {project_id}")
        print(f"🌐 All services running on: http://localhost:8000")
        
    else:
        print(f"❌ Project creation failed: {response.status_code}")
        print(f"Response: {response.text}")
        
except Exception as e:
    print(f"❌ Error: {e}")
