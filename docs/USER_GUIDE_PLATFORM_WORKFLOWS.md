# Cloud Migration Platform - Complete User Guide

**Document Version:** 1.0  
**Last Updated:** January 8, 2025  
**Platform Version:** Phase 1 (Cloud Migration & IAC Governance)

---

## Table of Contents

1. [Introduction](#introduction)
2. [Platform Overview](#platform-overview)
3. [Getting Started](#getting-started)
4. [Phase 1: Assessment & Discovery](#phase-1-assessment--discovery)
5. [Phase 2: Analysis & Planning](#phase-2-analysis--planning)
6. [Phase 3: Migration Execution](#phase-3-migration-execution)
7. [Phase 4: IAC Governance & Compliance](#phase-4-iac-governance--compliance)
8. [Phase 5: Cost Optimization (FinOps)](#phase-5-cost-optimization-finops)
9. [Advanced Features](#advanced-features)
10. [Troubleshooting](#troubleshooting)
11. [Best Practices](#best-practices)

---

## Introduction

The Cloud Migration Platform is an AI-powered enterprise solution designed to streamline and automate the complete cloud migration lifecycle. This guide provides step-by-step instructions for using the platform's core workflows.

### Key Capabilities

- **Automated Discovery**: AI-powered assessment of existing infrastructure
- **Intelligent Planning**: Migration wave planning and dependency analysis
- **Orchestrated Execution**: Automated migration with real-time monitoring
- **Policy Governance**: Infrastructure-as-Code compliance and security scanning
- **Cost Optimization**: FinOps insights and optimization recommendations

### Platform Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend UI (React)                      │
│  Dashboard | Projects | Cloud Migration | IAC | FinOps      │
└─────────────────────────────────────────────────────────────┘
                             │
┌─────────────────────────────────────────────────────────────┐
│                   Backend Gateway (FastAPI)                  │
│         Routing | Authentication | Correlation IDs          │
└─────────────────────────────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
┌───────────────┐   ┌────────────────┐   ┌──────────────┐
│ Cloud Orch    │   │ IAC Governance │   │ FinOps Opt   │
│ Service       │   │ Service        │   │ Service      │
│ (Port 8020)   │   │ (Port 8021)    │   │ (Port 8022)  │
└───────────────┘   └────────────────┘   └──────────────┘
        │                    │                    │
┌───────────────┐   ┌────────────────┐   ┌──────────────┐
│ AWS MCP       │   │ Terraform MCP  │   │ Cost APIs    │
│ Adapters      │   │ OPA Engine     │   │ Analytics    │
└───────────────┘   └────────────────┘   └──────────────┘
```

---

## Platform Overview

### Core Services

1. **Backend Gateway** (Port 8000)
   - Central API gateway for all requests
   - Authentication and authorization
   - Request routing and correlation tracking

2. **Cloud Orchestration Service** (Port 8020)
   - Migration wave management
   - Resource inventory and dependency mapping
   - Migration execution orchestration

3. **IAC Governance Service** (Port 8021)
   - Policy template management
   - Infrastructure code scanning
   - Compliance violation tracking
   - Remediation workflows

4. **FinOps Optimization Service** (Port 8022)
   - Cost analysis and forecasting
   - Resource optimization recommendations
   - Budget tracking and alerts

### Supporting Services

- **Project Service** (Port 8002): Project lifecycle management
- **Document Service** (Port 8003): Document processing and extraction
- **Vector Service** (Port 8005): Semantic search and embeddings
- **Graph Service** (Port 8006): Knowledge graph construction
- **LLM Service** (Port 8007): AI model orchestration
- **AI Agent Service** (Port 8008): Autonomous agent workflows
- **WebSocket Service** (Port 8009): Real-time updates
- **Storage Service** (Port 8010): File and artifact storage
- **Service Registry** (Port 8011): Service discovery and health monitoring

---

## Getting Started

### Prerequisites

- Active user account with appropriate permissions
- Web browser (Chrome, Firefox, Edge - latest versions)
- Network access to platform URL
- (Optional) API access token for programmatic usage

### First-Time Login

1. **Access the Platform**
   ```
   https://your-platform-url.com
   ```

2. **Authenticate**
   - Click "Sign In"
   - Enter credentials or use OAuth provider
   - Complete MFA if enabled

3. **Verify Dashboard Access**
   - Upon successful login, you'll see the Dashboard
   - Review platform statistics and recent projects
   - Verify service health indicators (green badges)

### Navigation Overview

**Main Navigation (Left Sidebar)**

- 🏠 **Dashboard**: Platform overview and statistics
- 📁 **Projects**: Project management and listing
- ☁️ **Cloud Migration**: Migration wave orchestration
- 🛡️ **IAC Governance**: Policy and compliance management
- 💰 **FinOps**: Cost optimization and analysis
- 🖥️ **System**: Platform logs and monitoring
- ⚙️ **Settings**: Configuration and preferences

---

## Phase 1: Assessment & Discovery

**Objective**: Understand your current infrastructure and create a comprehensive inventory.

### Step 1: Create a New Project

1. **Navigate to Projects**
   - Click **Projects** in the left sidebar
   - Click **+ New Project** button

2. **Fill Project Details**
   ```yaml
   Project Name: "Production Migration to AWS"
   Description: "Migration of production workloads from on-premise to AWS"
   Migration Type: Cloud Migration
   Source Environment: On-Premise
   Target Cloud: AWS
   ```

3. **Configure Project Settings**
   - Set project owner and team members
   - Define project timeline and milestones
   - Configure notification preferences

4. **Save Project**
   - Click **Create Project**
   - Note the Project ID for future reference

### Step 2: Upload Infrastructure Documentation

1. **Access Project Detail Page**
   - Click on your newly created project
   - Navigate to the **Documents** tab

2. **Upload Assessment Documents**
   - Click **Upload Documents**
   - Supported formats: Excel (.xlsx, .xls), PDF, Word (.docx), CSV
   - Example documents:
     - Server inventory spreadsheets
     - Network diagrams (PDF)
     - Application dependency maps
     - Database schemas
     - Configuration exports

3. **Configure Document Processing**
   ```json
   {
     "extract_tables": true,
     "extract_images": true,
     "include_coordinates": true,
     "ocr_enabled": true
   }
   ```

4. **Monitor Processing Status**
   - Wait for document processing to complete
   - Check **Processing Status** column
   - Review extracted data in **Document Viewer**

### Step 3: AI-Powered Data Extraction

The platform automatically extracts structured data from uploaded documents:

1. **Table Extraction**
   - Server lists from Excel/CSV
   - Application inventories
   - Network configurations
   - Database catalogs

2. **Entity Recognition**
   - IP addresses and hostnames
   - Application names and versions
   - Database instances and sizes
   - Network dependencies

3. **Knowledge Graph Construction**
   - Automatic relationship mapping
   - Dependency visualization
   - Impact analysis readiness

### Step 4: Review Extracted Inventory

1. **Navigate to Knowledge Graph**
   - Click **Knowledge Graph** tab
   - View interactive visualization of discovered assets

2. **Verify Discovered Assets**
   - **Servers**: Count, OS types, locations
   - **Applications**: Installed software, versions
   - **Databases**: Instances, sizes, technologies
   - **Networks**: VLANs, subnets, connectivity

3. **Manual Corrections** (if needed)
   - Click on any node to edit properties
   - Add missing relationships
   - Tag critical vs. non-critical assets

### Step 5: Generate Assessment Report

1. **Navigate to Reports**
   - Click **Reports** tab
   - Select **Assessment Report**

2. **Configure Report Parameters**
   ```yaml
   Report Type: Comprehensive Assessment
   Include Sections:
     - Infrastructure Inventory
     - Dependency Analysis
     - Complexity Score
     - Risk Assessment
     - Recommended Migration Strategy
   Format: PDF + Excel
   ```

3. **Generate Report**
   - Click **Generate Report**
   - Download when ready (typically 2-5 minutes)

**Expected Outputs:**
- Complete infrastructure inventory (Excel)
- Dependency map visualization (PDF)
- Migration readiness score (0-100)
- Recommended migration approach

---

## Phase 2: Analysis & Planning

**Objective**: Analyze dependencies, group resources into migration waves, and create execution plan.

### Step 1: Analyze Dependencies

1. **Access Dependency Analysis**
   - Project Detail → **Analysis** tab
   - Click **Run Dependency Analysis**

2. **Review Dependency Map**
   - Visualize inter-application dependencies
   - Identify critical path resources
   - Spot circular dependencies (requires resolution)

3. **Dependency Metrics**
   - **Inbound Dependencies**: Resources depending on this asset
   - **Outbound Dependencies**: Assets this resource depends on
   - **Criticality Score**: Impact rating (1-10)
   - **Complexity Score**: Migration difficulty (1-10)

### Step 2: Create Migration Waves

Migration waves group related resources for phased migration.

1. **Navigate to Cloud Migration**
   - Click **Cloud Migration** in sidebar
   - Ensure project is selected (URL: `/cloud-migration?project=YOUR_PROJECT_ID`)

2. **Create First Wave**
   - Click **+ Create Wave**
   - Fill wave details:
     ```yaml
     Wave Name: "Wave 1 - Non-Critical Web Servers"
     Description: "Low-risk web servers with minimal dependencies"
     Target Cloud: AWS
     Priority: P3 (Medium)
     ```
   - Click **Create Wave**

3. **Add Resources to Wave**
   - Click wave name to open details
   - Click **+ Add Resource**
   - Fill resource details:
     ```yaml
     Resource Type: EC2 Instance
     Source Identifier: "web-server-01.example.com"
     Target Configuration:
       {
         "instance_type": "t3.medium",
         "region": "us-east-1",
         "availability_zone": "us-east-1a",
         "ami": "ami-0c55b159cbfafe1f0"
       }
     ```
   - Repeat for all resources in wave

### Step 3: Define Migration Strategy Per Wave

For each wave, select the appropriate migration strategy:

**Available Strategies:**

1. **Rehost (Lift & Shift)**
   - Move as-is to cloud
   - Minimal changes
   - Fastest migration
   - Example: Physical servers → EC2 instances

2. **Replatform**
   - Minor optimizations during migration
   - Use managed services where beneficial
   - Example: MySQL on-prem → RDS MySQL

3. **Refactor/Re-architect**
   - Significant code changes
   - Cloud-native patterns
   - Example: Monolith → Microservices

4. **Repurchase**
   - Replace with SaaS
   - Example: Exchange Server → Microsoft 365

5. **Retire**
   - Decommission unused resources
   - No migration needed

6. **Retain**
   - Keep on-premise
   - Example: Mainframe systems

### Step 4: Validate Migration Waves

1. **Run Wave Validation**
   - Select wave from list
   - Click **Actions** → **Validate Wave**

2. **Review Validation Results**
   - ✅ **Passed Checks**:
     - No circular dependencies
     - All dependencies in earlier waves
     - Sufficient target capacity
     - Network connectivity confirmed
   
   - ❌ **Failed Checks**:
     - Missing dependencies
     - Insufficient quota
     - Network isolation issues
   
3. **Resolve Validation Issues**
   - Reorder resources between waves
   - Add missing dependencies
   - Request quota increases

### Step 5: Create Migration Timeline

1. **Navigate to Project Timeline**
   - Project Detail → **Timeline** tab
   - Click **Generate Timeline**

2. **Configure Timeline Parameters**
   ```yaml
   Start Date: 2025-02-01
   Wave Duration: 2 weeks per wave
   Buffer Between Waves: 1 week
   Include Testing Phase: Yes (1 week per wave)
   Include Rollback Windows: Yes
   ```

3. **Review Generated Timeline**
   - Gantt chart visualization
   - Wave start/end dates
   - Testing and validation periods
   - Go-live dates per wave

**Sample Timeline Output:**
```
Wave 1: 2025-02-01 to 2025-02-14 (Migration)
        2025-02-15 to 2025-02-21 (Testing)
        2025-02-22 (Go-Live)

Wave 2: 2025-02-29 to 2025-03-14 (Migration)
        2025-03-15 to 2025-03-21 (Testing)
        2025-03-22 (Go-Live)
```

---

## Phase 3: Migration Execution

**Objective**: Execute planned migrations with automated orchestration and monitoring.

### Step 1: Pre-Migration Checklist

Before executing a migration wave, verify:

- [ ] All resources in wave are properly configured
- [ ] Dependencies from previous waves are migrated and operational
- [ ] Target cloud accounts and credentials are configured
- [ ] Network connectivity is established (VPN/Direct Connect)
- [ ] Backup of source systems completed
- [ ] Rollback plan documented
- [ ] Stakeholders notified of migration window
- [ ] Change control approvals obtained

### Step 2: Execute Migration Wave

1. **Navigate to Cloud Migration**
   - Select the wave ready for execution
   - Verify wave status is "Ready"

2. **Review Pre-Migration Checklist**
   - Click **Pre-Flight Check**
   - Verify all checks pass
   - Resolve any issues before proceeding

3. **Start Migration**
   - Click **Execute Wave** button
   - Confirm migration start
   - Monitor progress in real-time

### Step 3: Monitor Migration Progress

**Real-Time Monitoring Dashboard**

1. **Wave Progress Overview**
   ```
   Overall Progress: 45% (12/27 resources completed)
   Current Task: Migrating database db-prod-01
   ETA: 2 hours 15 minutes
   Status: In Progress
   ```

2. **Per-Resource Status**
   - ✅ **Completed**: Successfully migrated
   - 🔄 **In Progress**: Currently migrating
   - ⏳ **Pending**: Waiting for dependencies
   - ❌ **Failed**: Migration failed (requires attention)

3. **Live Logs**
   - Real-time streaming logs via WebSocket
   - Filter by resource or severity
   - Download logs for offline analysis

### Step 4: Handle Migration Issues

**Common Issues and Resolutions:**

1. **Network Connectivity Failure**
   ```
   Error: Unable to reach source server 10.0.1.50
   
   Resolution:
   - Verify VPN/Direct Connect status
   - Check firewall rules
   - Validate security groups
   - Click "Retry" after resolving
   ```

2. **Insufficient Permissions**
   ```
   Error: AccessDenied when creating EC2 instance
   
   Resolution:
   - Verify IAM role permissions
   - Add required policies
   - Refresh credentials
   - Click "Retry"
   ```

3. **Data Sync Failure**
   ```
   Error: Data replication fell behind (lag: 2 hours)
   
   Resolution:
   - Check network bandwidth
   - Pause non-critical transfers
   - Extend cutover window
   - Resume replication
   ```

### Step 5: Post-Migration Validation

After wave execution completes:

1. **Automated Tests**
   - Connectivity tests (ping, port checks)
   - Application health checks
   - Database integrity verification
   - Performance baseline comparison

2. **Manual Validation**
   - Application functional testing
   - User acceptance testing (UAT)
   - Performance testing
   - Security scanning

3. **Update Migration Status**
   - Mark resources as "Validated" or "Failed"
   - Document any issues or deviations
   - Update knowledge graph with new cloud resource IDs

### Step 6: Cutover and Go-Live

1. **Prepare for Cutover**
   - Schedule final data sync
   - Coordinate with stakeholders
   - Prepare DNS/load balancer changes

2. **Execute Cutover**
   - Stop source applications
   - Perform final data sync
   - Update DNS records
   - Start cloud applications
   - Verify end-to-end functionality

3. **Post-Cutover Monitoring**
   - Monitor for 24-48 hours
   - Watch for performance issues
   - Track error rates
   - Keep rollback plan ready

### Step 7: Decommission Source Resources

After successful validation (typically 30 days):

1. **Mark for Decommission**
   - Project → Resources → Select migrated resources
   - Click **Mark for Decommission**

2. **Execute Decommission**
   - Final backups
   - Power off source systems
   - Release IP addresses
   - Update documentation

---

## Phase 4: IAC Governance & Compliance

**Objective**: Ensure infrastructure code follows security, compliance, and best practice policies.

### Step 1: Set Up Policy Templates

1. **Navigate to IAC Governance**
   - Click **IAC Governance** in sidebar
   - Click **Policy Templates** tab

2. **Create Security Policy**
   - Click **+ Create Policy**
   - Fill policy details:
     ```yaml
     Policy Name: "Enforce S3 Bucket Encryption"
     Description: "All S3 buckets must have encryption enabled"
     Policy Type: Security
     Severity: Critical
     ```

3. **Write Rego Policy**
   ```rego
   package terraform.s3_encryption
   
   deny[msg] {
     resource := input.resource_changes[_]
     resource.type == "aws_s3_bucket"
     not resource.change.after.server_side_encryption_configuration
     
     msg := sprintf(
       "S3 bucket '%s' does not have encryption enabled",
       [resource.address]
     )
   }
   ```

4. **Save Policy Template**
   - Add tags: `aws`, `s3`, `encryption`
   - Enable policy
   - Click **Create Policy**

### Step 2: Import or Create More Policies

**Recommended Policy Categories:**

1. **Security Policies**
   - Encryption at rest and in transit
   - Public access restrictions
   - Security group rules
   - IAM least privilege

2. **Compliance Policies**
   - PCI-DSS requirements
   - HIPAA compliance
   - GDPR data residency
   - SOC 2 controls

3. **Cost Optimization Policies**
   - Instance type restrictions
   - Reserved instance usage
   - Unused resource detection
   - Tagging requirements

4. **Best Practices**
   - Multi-AZ deployments
   - Backup configuration
   - Monitoring and logging
   - Disaster recovery

### Step 3: Scan Infrastructure Code

1. **Prepare IAC Repository**
   - Ensure Terraform/CloudFormation code is accessible
   - Organize code in logical modules
   - Commit latest changes to version control

2. **Initiate Policy Scan**
   - IAC Governance → **Policy Scans** tab
   - Click **+ Start Scan**
   - Configure scan:
     ```yaml
     Scan Type: Terraform
     Target Path: /terraform/modules/infrastructure
     Policy Selection: All Enabled Policies
     ```
   - Click **Start Scan**

3. **Monitor Scan Progress**
   - Status updates in real-time
   - Estimated completion time displayed
   - Notification on completion

### Step 4: Review Violations

1. **Access Scan Results**
   - Click on completed scan
   - View violations summary:
     ```
     Total Violations: 23
     Critical: 3
     High: 7
     Medium: 10
     Low: 3
     ```

2. **Analyze Critical Violations**
   ```
   Violation ID: V-001
   Severity: Critical
   Policy: Enforce S3 Bucket Encryption
   Resource: module.storage.aws_s3_bucket.data_lake
   Message: S3 bucket 'data-lake-prod' does not have encryption enabled
   File: modules/storage/main.tf
   Line: 45
   ```

3. **Export Violations Report**
   - Click **Download Report**
   - Format: Excel or PDF
   - Share with development team

### Step 5: Remediate Violations

**Automated Remediation (where available)**

1. **Select Violations for Auto-Fix**
   - Filter violations by "Auto-Remediable"
   - Select violations
   - Click **Auto-Remediate**

2. **Review Proposed Changes**
   - Platform shows Terraform diff
   - Verify changes are correct
   - Click **Apply Remediation**

**Manual Remediation**

1. **Access Violation Details**
   - Click on violation
   - View suggested fix

2. **Update Infrastructure Code**
   ```hcl
   # Before
   resource "aws_s3_bucket" "data_lake" {
     bucket = "data-lake-prod"
     # Missing encryption
   }
   
   # After
   resource "aws_s3_bucket" "data_lake" {
     bucket = "data-lake-prod"
     
     server_side_encryption_configuration {
       rule {
         apply_server_side_encryption_by_default {
           sse_algorithm = "AES256"
         }
       }
     }
   }
   ```

3. **Re-scan to Verify**
   - Commit changes
   - Run scan again
   - Verify violation is resolved

### Step 6: Set Up Continuous Compliance

1. **Enable Automated Scanning**
   - Settings → IAC Governance → Automation
   - Enable "Scan on Code Commit"
   - Configure scan frequency (e.g., daily)

2. **Configure Notifications**
   ```yaml
   Notification Rules:
     - Trigger: New Critical Violations
       Channel: Email + Slack
       Recipients: security-team@example.com
     
     - Trigger: Compliance Score < 90%
       Channel: Email
       Recipients: devops-leads@example.com
   ```

3. **Integrate with CI/CD**
   - Add policy scan step to CI/CD pipeline
   - Block deployments if critical violations found
   - Example GitHub Actions workflow:
     ```yaml
     - name: Run Policy Scan
       run: |
         curl -X POST \
           -H "Authorization: Bearer ${{ secrets.PLATFORM_TOKEN }}" \
           -d '{"scan_type":"terraform","target_path":"./terraform"}' \
           https://platform.example.com/api/iac-governance/api/scans
     ```

---

## Phase 5: Cost Optimization (FinOps)

**Objective**: Optimize cloud spend and implement FinOps best practices.

### Step 1: Connect Cost Data Sources

1. **Navigate to FinOps**
   - Click **FinOps** in sidebar
   - Ensure project is selected

2. **Configure Cloud Accounts**
   - Click **Settings** → **Cloud Accounts**
   - Add AWS account:
     ```yaml
     Account Name: Production AWS
     Account ID: 123456789012
     Cost & Usage Report: s3://bucket/path/to/cur
     Billing Alerts: Enabled
     ```

3. **Enable Cost Collection**
   - Platform fetches cost data from AWS Cost Explorer API
   - Historical data imported (up to 12 months)
   - Daily updates scheduled

### Step 2: Analyze Cost Trends

1. **View Cost Dashboard**
   - Current month spending
   - Projected annual cost
   - Cost trend (increasing/decreasing/stable)

2. **Cost Breakdown by Service**
   ```
   EC2:        $2,134.45 (46.7%)
   RDS:        $1,234.56 (27.0%)
   S3:         $  678.90 (14.9%)
   Lambda:     $  345.67 (7.6%)
   Others:     $  174.31 (3.8%)
   Total:      $4,567.89/month
   ```

3. **Identify Cost Anomalies**
   - Sudden spikes in spending
   - Unexpected service usage
   - Idle resource detection

### Step 3: Review Optimization Recommendations

The platform automatically generates optimization recommendations:

1. **Underutilized EC2 Instances**
   ```
   Finding: 5 instances running at <20% CPU utilization
   
   Recommendations:
   - Downsize to smaller instance types
   - Consider Graviton instances for cost savings
   - Implement auto-scaling
   
   Potential Savings: $456.78/month (19.5%)
   
   Action: Click "Review" to see instance details
   ```

2. **Reserved Instance Opportunities**
   ```
   Finding: 3 instances eligible for RI discounts
   
   Recommendations:
   - Purchase 1-year Standard RIs
   - Estimated savings: 40% vs On-Demand
   
   Potential Savings: $287.45/month
   
   Action: Click "Review" to see RI purchase options
   ```

3. **S3 Lifecycle Policies**
   ```
   Finding: 450 GB of data older than 90 days in Standard storage
   
   Recommendations:
   - Transition to S3 Intelligent-Tiering
   - Archive to Glacier for infrequent access data
   
   Potential Savings: $148.22/month
   
   Action: Click "Review" to implement lifecycle rules
   ```

### Step 4: Implement Cost Optimizations

1. **Resize Instances**
   - Click on recommendation
   - Review instance utilization metrics
   - Select new instance type
   - Schedule resize window
   - Execute resize
   - Monitor performance post-resize

2. **Purchase Reserved Instances**
   - Review RI recommendations
   - Validate instance stability (no planned changes)
   - Purchase RIs via AWS Console
   - Update cost model in platform

3. **Configure S3 Lifecycle Policies**
   - Click "Implement" on S3 recommendation
   - Review proposed lifecycle rules:
     ```json
     {
       "Rules": [
         {
           "Id": "Archive old data",
           "Status": "Enabled",
           "Transitions": [
             {
               "Days": 90,
               "StorageClass": "GLACIER"
             }
           ]
         }
       ]
     }
     ```
   - Apply lifecycle policy
   - Monitor cost impact over 30 days

### Step 5: Set Up Budget Alerts

1. **Create Budget**
   - FinOps → **Budgets** tab
   - Click **+ Create Budget**
   - Configure budget:
     ```yaml
     Budget Name: "Production Monthly Budget"
     Amount: $5,000/month
     Alert Thresholds:
       - 80% ($4,000): Notification
       - 90% ($4,500): Warning
       - 100% ($5,000): Critical Alert
     ```

2. **Configure Alert Actions**
   ```yaml
   80% Threshold:
     - Send email to: finance@example.com
     - Notification: Informational
   
   90% Threshold:
     - Send email to: finance@example.com, cto@example.com
     - Slack notification: #cost-alerts
     - Notification: Warning
   
   100% Threshold:
     - Send email to: finance@example.com, cto@example.com
     - Slack notification: @channel in #cost-alerts
     - Create incident ticket
     - Notification: Critical
   ```

### Step 6: Generate Cost Reports

1. **Monthly Cost Report**
   - FinOps → **Reports**
   - Select **Monthly Cost Report**
   - Date Range: Last 30 days
   - Click **Generate**

2. **Report Contents**
   - Executive summary
   - Cost by service
   - Cost by team/project
   - Optimization opportunities
   - Budget vs. actual comparison
   - Month-over-month trends

3. **Schedule Recurring Reports**
   - Configure report to auto-generate monthly
   - Email to stakeholders
   - Archive in document repository

---

## Advanced Features

### 1. AI Agent Workflows

**Autonomous Migration Planning**

1. **Enable AI Agent**
   - Project → **AI Agents** tab
   - Click **+ Create Agent Workflow**
   - Select template: "Migration Wave Planner"

2. **Configure Agent**
   ```yaml
   Agent Name: "Auto Wave Planner"
   Objective: "Create optimal migration waves based on dependencies"
   Constraints:
     - Max 50 resources per wave
     - No circular dependencies
     - Prioritize by criticality score
   Schedule: Run daily at 2 AM UTC
   ```

3. **Review Agent Output**
   - Agent automatically generates wave proposals
   - Human review and approval required
   - Iterative refinement based on feedback

### 2. Knowledge Graph Queries

**Complex Dependency Queries**

1. **Access Graph Query Interface**
   - Project → **Knowledge Graph** → **Query**

2. **Example Queries**
   ```cypher
   # Find all databases dependent on app-server-01
   MATCH (db:Database)-[:DEPENDS_ON*]->(server:Server {name: 'app-server-01'})
   RETURN db.name, db.size, db.technology
   
   # Identify circular dependencies
   MATCH (a)-[:DEPENDS_ON*]->(b), (b)-[:DEPENDS_ON*]->(a)
   WHERE id(a) < id(b)
   RETURN a.name, b.name
   
   # Calculate migration complexity score
   MATCH (resource)
   RETURN resource.name, 
          size((resource)-[:DEPENDS_ON]->()) as dependencies,
          size((resource)<-[:DEPENDS_ON]-()) as dependents,
          (dependencies + dependents * 2) as complexity_score
   ORDER BY complexity_score DESC
   ```

### 3. Custom Rego Policies

**Advanced Policy Authoring**

1. **Multi-Resource Policies**
   ```rego
   package terraform.network_segmentation
   
   # Ensure database and web tiers are in separate subnets
   deny[msg] {
     db := input.resource_changes[_]
     db.type == "aws_db_instance"
     db_subnet := db.change.after.subnet_id
     
     web := input.resource_changes[_]
     web.type == "aws_instance"
     web.change.after.tags.Tier == "web"
     web_subnet := web.change.after.subnet_id
     
     db_subnet == web_subnet
     
     msg := sprintf(
       "Database %s and web server %s are in the same subnet - violates segmentation policy",
       [db.address, web.address]
     )
   }
   ```

2. **Policies with External Data**
   ```rego
   package terraform.approved_amis
   
   import data.approved_ami_list
   
   deny[msg] {
     resource := input.resource_changes[_]
     resource.type == "aws_instance"
     ami := resource.change.after.ami
     
     not ami_is_approved(ami)
     
     msg := sprintf(
       "Instance %s uses non-approved AMI %s",
       [resource.address, ami]
     )
   }
   
   ami_is_approved(ami) {
     approved_ami_list[_] == ami
   }
   ```

### 4. API Automation

**Programmatic Access**

1. **Generate API Token**
   - Settings → **API Tokens**
   - Click **Create Token**
   - Set expiration and scope
   - Copy token (shown once)

2. **Example API Calls**
   ```bash
   # List all migration waves
   curl -X GET \
     -H "Authorization: Bearer YOUR_TOKEN" \
     https://platform.example.com/api/cloud-orchestration/api/waves?project_id=PROJECT_ID
   
   # Create new wave
   curl -X POST \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "project_id": "PROJECT_ID",
       "name": "Wave 5 - Analytics Cluster",
       "target_cloud": "aws",
       "priority": 2
     }' \
     https://platform.example.com/api/cloud-orchestration/api/waves
   
   # Start policy scan
   curl -X POST \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "project_id": "PROJECT_ID",
       "scan_type": "terraform",
       "target_path": "/terraform/production"
     }' \
     https://platform.example.com/api/iac-governance/api/scans
   ```

---

## Troubleshooting

### Common Issues

#### Issue: Document Upload Fails

**Symptoms:**
- Upload progress stuck at 0%
- Error message: "Upload failed"

**Resolution:**
1. Check file size (max 500 MB per file)
2. Verify file format is supported
3. Check network connectivity
4. Clear browser cache and retry
5. Try different browser

#### Issue: Migration Wave Validation Fails

**Symptoms:**
- Wave status: "Validation Failed"
- Error: "Circular dependency detected"

**Resolution:**
1. Review dependency map
2. Identify circular references
3. Reorder resources between waves
4. Add intermediate migration steps
5. Re-run validation

#### Issue: Policy Scan Returns No Results

**Symptoms:**
- Scan completes successfully
- 0 violations found (unexpected)

**Resolution:**
1. Verify target path is correct
2. Check policy templates are enabled
3. Ensure Terraform files are in standard format
4. Review scan logs for parsing errors
5. Test policy with sample Terraform code

#### Issue: Cost Data Not Updating

**Symptoms:**
- Cost dashboard shows outdated data
- Last update >24 hours ago

**Resolution:**
1. Verify cloud account credentials
2. Check Cost & Usage Report configuration
3. Ensure IAM permissions include `ce:GetCostAndUsage`
4. Manually trigger data sync: Settings → **Sync Cost Data**
5. Contact support if issue persists

### Getting Help

**Support Channels:**

1. **In-App Help**
   - Click **?** icon in top-right corner
   - Search knowledge base
   - View video tutorials

2. **Submit Support Ticket**
   - Settings → **Support**
   - Click **Create Ticket**
   - Provide: Project ID, Error Message, Screenshots

3. **Community Forum**
   - https://community.platform.example.com
   - Search existing questions
   - Post new questions with tag

4. **Email Support**
   - support@platform.example.com
   - Response SLA: 4 hours (Critical), 24 hours (Normal)

---

## Best Practices

### Project Organization

1. **Naming Conventions**
   - Use descriptive project names
   - Include environment: `ProjectName-Production`
   - Version control: `ProjectName-v2`

2. **Documentation**
   - Upload all relevant documents upfront
   - Keep inventory spreadsheets up-to-date
   - Document custom configurations
   - Maintain migration journal

3. **Team Collaboration**
   - Assign clear roles and responsibilities
   - Use comments and annotations
   - Schedule regular review meetings
   - Share reports with stakeholders

### Migration Planning

1. **Wave Design**
   - Start with low-risk, non-critical systems
   - Group functionally related resources
   - Keep wave size manageable (20-50 resources)
   - Allow buffer time between waves

2. **Dependency Management**
   - Validate dependencies before migration
   - Plan for cross-wave dependencies
   - Test connectivity post-migration
   - Maintain dependency documentation

3. **Risk Mitigation**
   - Always have rollback plan
   - Test in non-production first
   - Schedule migrations during low-traffic windows
   - Keep source systems running for 30+ days

### IAC Governance

1. **Policy Management**
   - Start with security and compliance policies
   - Gradually add cost and best practice policies
   - Review policies quarterly
   - Version control policy changes

2. **Remediation Workflow**
   - Prioritize critical violations first
   - Set SLAs for remediation (e.g., Critical: 24h, High: 7 days)
   - Track remediation progress
   - Re-scan after fixes

3. **Continuous Compliance**
   - Integrate scans into CI/CD pipelines
   - Block deployments with critical violations
   - Automate policy testing
   - Generate compliance reports monthly

### Cost Optimization

1. **Regular Reviews**
   - Weekly cost trend analysis
   - Monthly optimization reviews
   - Quarterly RI/Savings Plan assessment
   - Annual budget planning

2. **Tagging Strategy**
   - Tag all resources with: Environment, Project, Owner, CostCenter
   - Enforce tagging via IAC policies
   - Use tags for cost allocation
   - Audit tags monthly

3. **Optimization Discipline**
   - Implement recommendations within 30 days
   - Measure actual vs. projected savings
   - Document optimization decisions
   - Share savings with stakeholders

---

## Appendix

### Glossary

- **Migration Wave**: A group of related resources migrated together in a single execution
- **Dependency**: A relationship where one resource requires another to function
- **IAC**: Infrastructure as Code - managing infrastructure using code files
- **Rego**: Policy language used by Open Policy Agent (OPA)
- **FinOps**: Financial Operations - cloud cost management discipline
- **Reserved Instance (RI)**: Discounted cloud resources purchased with commitment

### API Reference

Full API documentation: https://platform.example.com/api/docs

### Keyboard Shortcuts

- `Ctrl+K` or `Cmd+K`: Search
- `G then D`: Go to Dashboard
- `G then P`: Go to Projects
- `G then M`: Go to Cloud Migration
- `G then I`: Go to IAC Governance
- `G then F`: Go to FinOps
- `/`: Focus search
- `Esc`: Close modal

### Version History

- **v1.0** (January 8, 2025): Initial release
  - Phase 1 features: Cloud Migration, IAC Governance, FinOps
  - Complete user workflows documented

---

**End of User Guide**

For the latest updates and feature announcements, visit the platform documentation portal or subscribe to the changelog.
