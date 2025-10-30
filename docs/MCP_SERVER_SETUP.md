# MCP Server Setup Guide
**Platform:** Migration Platform v2.0  
**Updated:** January 9, 2025

## Overview

This guide provides step-by-step instructions for installing and configuring Model Context Protocol (MCP) servers for Azure and GCP cloud migration operations.

MCP servers enable the Migration Platform's Cloud Orchestration service to perform automated migration tasks including:
- **Azure**: Azure Migrate assessments, Azure Site Recovery failovers, Azure Database Migration Service
- **GCP**: Compute Engine migrations, Database Migration Service, Storage Transfer Service

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Azure MCP Server Setup](#azure-mcp-server-setup)
3. [GCP MCP Server Setup](#gcp-mcp-server-setup)
4. [Registering MCP Servers via UI](#registering-mcp-servers-via-ui)
5. [Testing and Validation](#testing-and-validation)
6. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### General Requirements
- Node.js 18+ or Python 3.10+ (depending on MCP server implementation)
- Access to the Migration Platform UI (Settings → MCP Servers)
- Network connectivity to Azure/GCP APIs

### Azure Prerequisites
- Azure subscription with Owner or Contributor role
- Azure AD Service Principal with permissions:
  - `Microsoft.Migrate/*` - Azure Migrate operations
  - `Microsoft.RecoveryServices/*` - Azure Site Recovery
  - `Microsoft.DataMigration/*` - Database Migration Service
- Azure CLI installed (optional, for credential verification)

### GCP Prerequisites
- GCP project with billing enabled
- Service Account with roles:
  - `Compute Admin` - For VM migration
  - `Cloud SQL Admin` - For database migration
  - `Storage Transfer Admin` - For data migration
- Service Account JSON key file downloaded

---

## Azure MCP Server Setup

### Step 1: Create Azure Service Principal

Using Azure CLI:
```bash
# Login to Azure
az login

# Create Service Principal
az ad sp create-for-rbac \
  --name "migration-platform-mcp" \
  --role Contributor \
  --scopes /subscriptions/{subscription-id}

# Output will include:
# {
#   "appId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",        # CLIENT_ID
#   "password": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",      # CLIENT_SECRET
#   "tenant": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"        # TENANT_ID
# }
```

Save these credentials - you'll need them for MCP server configuration.

### Step 2: Grant Additional Permissions

```bash
# Grant Azure Migrate permissions
az role assignment create \
  --assignee {appId} \
  --role "Azure Migrate Contributor" \
  --scope /subscriptions/{subscription-id}

# Grant Site Recovery permissions
az role assignment create \
  --assignee {appId} \
  --role "Site Recovery Contributor" \
  --scope /subscriptions/{subscription-id}
```

### Step 3: Install Azure MCP Server

**Option A: Using NPM (if official package exists)**
```powershell
# Global installation
npm install -g @azure/mcp-server

# Verify installation
npx @azure/mcp-server --version
```

**Option B: Using Docker (recommended for production)**
```powershell
# Pull Azure MCP server image
docker pull azure/mcp-server:latest

# Run as service
docker run -d \
  --name azure-mcp-server \
  -e AZURE_CLIENT_ID={your-client-id} \
  -e AZURE_CLIENT_SECRET={your-client-secret} \
  -e AZURE_TENANT_ID={your-tenant-id} \
  -p 8080:8080 \
  azure/mcp-server:latest
```

**Option C: Build Custom MCP Server**

If no official Azure MCP server exists, you can build a custom one using the MCP protocol specification. See [Custom MCP Server Development](#custom-mcp-server-development) below.

### Step 4: Test Azure Credentials

```powershell
# Test Service Principal login
az login --service-principal \
  -u {CLIENT_ID} \
  -p {CLIENT_SECRET} \
  --tenant {TENANT_ID}

# List subscriptions to verify access
az account list

# Test Azure Migrate access
az migrate project list
```

---

## GCP MCP Server Setup

### Step 1: Create GCP Service Account

Using Google Cloud Console:
1. Navigate to **IAM & Admin → Service Accounts**
2. Click **Create Service Account**
3. Name: `migration-platform-mcp`
4. Description: "MCP server for cloud migration operations"
5. Click **Create and Continue**

### Step 2: Grant Roles

Add the following roles to the service account:
- `Compute Admin` (roles/compute.admin)
- `Cloud SQL Admin` (roles/cloudsql.admin)
- `Storage Transfer Admin` (roles/storagetransfer.admin)
- `Service Usage Consumer` (roles/serviceusage.serviceUsageConsumer)

Using gcloud CLI:
```bash
PROJECT_ID="your-project-id"
SA_EMAIL="migration-platform-mcp@${PROJECT_ID}.iam.gserviceaccount.com"

# Grant roles
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/compute.admin"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/cloudsql.admin"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/storagetransfer.admin"
```

### Step 3: Create and Download Service Account Key

Using Google Cloud Console:
1. Click on the service account you created
2. Go to **Keys** tab
3. Click **Add Key → Create New Key**
4. Select **JSON** format
5. Click **Create** (downloads `your-project-id-xxxxx.json`)

**Important:** Store the JSON key file securely. It provides full access to your GCP project.

Save to a secure location:
```powershell
# Example location
C:\secure\gcp-migration-key.json
```

### Step 4: Install GCP MCP Server

**Option A: Using NPM**
```powershell
npm install -g @google-cloud/mcp-server

# Verify installation
npx @google-cloud/mcp-server --version
```

**Option B: Using Docker**
```powershell
# Pull GCP MCP server image
docker pull gcr.io/google-cloud/mcp-server:latest

# Run as service
docker run -d \
  --name gcp-mcp-server \
  -v C:\secure\gcp-migration-key.json:/key.json:ro \
  -e GOOGLE_APPLICATION_CREDENTIALS=/key.json \
  -p 8081:8080 \
  gcr.io/google-cloud/mcp-server:latest
```

### Step 5: Test GCP Credentials

```powershell
# Set credentials environment variable
$env:GOOGLE_APPLICATION_CREDENTIALS="C:\secure\gcp-migration-key.json"

# Test authentication
gcloud auth activate-service-account --key-file=$env:GOOGLE_APPLICATION_CREDENTIALS

# List projects to verify access
gcloud projects list

# Test Compute Engine access
gcloud compute instances list --project={project-id}
```

---

## AWS MCP Server Setup

### Step 1: Create AWS IAM User for MCP

Using AWS Console:
1. Navigate to **IAM → Users**
2. Click **Create user**
3. User name: `migration-platform-mcp`
4. Select **Access key - Programmatic access**
5. Click **Next: Permissions**

Using AWS CLI:
```bash
# Create IAM user
aws iam create-user --user-name migration-platform-mcp

# Create access key
aws iam create-access-key --user-name migration-platform-mcp

# Output will include:
# {
#   "AccessKey": {
#     "AccessKeyId": "AKIAIOSFODNN7EXAMPLE",          # AWS_ACCESS_KEY_ID
#     "SecretAccessKey": "wJalrXUtnFEMI/K7MDENG/..."  # AWS_SECRET_ACCESS_KEY
#   }
# }
```

**Important:** Save the Access Key ID and Secret Access Key - you'll need them for MCP server configuration.

### Step 2: Attach IAM Policies

The IAM user needs permissions for:
- **AWS Application Migration Service (MGN)**: Server migration
- **AWS Database Migration Service (DMS)**: Database migration
- **AWS DataSync**: Data transfer operations

**Recommended Policies:**

**Option A: Use Managed Policies (Quick Setup)**
```bash
# Attach Application Migration Service full access
aws iam attach-user-policy \
  --user-name migration-platform-mcp \
  --policy-arn arn:aws:iam::aws:policy/AWSApplicationMigrationFullAccess

# Attach Database Migration Service full access
aws iam attach-user-policy \
  --user-name migration-platform-mcp \
  --policy-arn arn:aws:iam::aws:policy/AmazonDMSFullAccess

# Attach DataSync full access
aws iam attach-user-policy \
  --user-name migration-platform-mcp \
  --policy-arn arn:aws:iam::aws:policy/AWSDataSyncFullAccess

# Attach EC2 read access (for source server discovery)
aws iam attach-user-policy \
  --user-name migration-platform-mcp \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2ReadOnlyAccess
```

**Option B: Create Custom Policy (Least Privilege)**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "mgn:*",
        "dms:*",
        "datasync:*",
        "ec2:Describe*",
        "ec2:CreateTags"
      ],
      "Resource": "*"
    }
  ]
}
```

Save as `migration-mcp-policy.json` and attach:
```bash
# Create custom policy
aws iam create-policy \
  --policy-name MigrationMCPPolicy \
  --policy-document file://migration-mcp-policy.json

# Attach to user
aws iam attach-user-policy \
  --user-name migration-platform-mcp \
  --policy-arn arn:aws:iam::{account-id}:policy/MigrationMCPPolicy
```

### Step 3: Configure AWS Default Region

Choose your primary migration target region:
```bash
# Set default region for the IAM user
aws configure set region us-east-1 --profile migration-mcp
```

Common AWS regions:
- **us-east-1** - US East (N. Virginia)
- **us-west-2** - US West (Oregon)
- **eu-west-1** - Europe (Ireland)
- **ap-southeast-1** - Asia Pacific (Singapore)

### Step 4: Install AWS MCP Server

**Option A: Using NPM (if official package exists)**
```powershell
# Global installation
npm install -g @aws/mcp-server

# Verify installation
npx @aws/mcp-server --version
```

**Option B: Using Docker (recommended for production)**
```powershell
# Pull AWS MCP server image
docker pull public.ecr.aws/aws/mcp-server:latest

# Run as service
docker run -d \
  --name aws-mcp-server \
  -e AWS_ACCESS_KEY_ID={your-access-key-id} \
  -e AWS_SECRET_ACCESS_KEY={your-secret-access-key} \
  -e AWS_DEFAULT_REGION=us-east-1 \
  -p 8082:8080 \
  public.ecr.aws/aws/mcp-server:latest
```

**Option C: Using AWS Lambda (serverless)**

For serverless MCP server deployment:
```bash
# Package MCP server
zip -r aws-mcp-server.zip mcp_server.py requirements.txt

# Create Lambda function
aws lambda create-function \
  --function-name aws-mcp-server \
  --runtime python3.11 \
  --handler mcp_server.handler \
  --role arn:aws:iam::{account-id}:role/lambda-mcp-role \
  --zip-file fileb://aws-mcp-server.zip \
  --environment Variables={AWS_DEFAULT_REGION=us-east-1}
```

### Step 5: Test AWS Credentials

```powershell
# Configure AWS CLI with credentials
aws configure --profile migration-mcp
# AWS Access Key ID: {your-access-key-id}
# AWS Secret Access Key: {your-secret-access-key}
# Default region: us-east-1
# Default output format: json

# Test credentials
aws sts get-caller-identity --profile migration-mcp

# Test MGN access
aws mgn initialize-service --region us-east-1 --profile migration-mcp

# Test DMS access
aws dms describe-replication-instances --region us-east-1 --profile migration-mcp

# Test DataSync access
aws datasync list-tasks --region us-east-1 --profile migration-mcp
```

**Expected Output:**
```json
{
  "UserId": "AIDAI...",
  "Account": "123456789012",
  "Arn": "arn:aws:iam::123456789012:user/migration-platform-mcp"
}
```

---

## Registering MCP Servers via UI

### Azure MCP Server Registration

1. **Navigate to Settings**
   - Open Migration Platform UI
   - Click **Settings** in the left sidebar
   - Select **MCP Servers** tab

2. **Add New Server**
   - Click **Add Server** button
   - Fill in the form:

   | Field | Value |
   |-------|-------|
   | **Name** | Azure Migration Server |
   | **Provider** | Azure |
   | **Transport** | STDIO (for local) or WebSocket (for Docker) |
   | **Command** (STDIO) | `npx -y @azure/mcp-server` |
   | **URL** (WebSocket) | `ws://localhost:8080` |
   | **Azure Client ID** | `{your-app-id}` |
   | **Azure Client Secret** | `{your-password}` |
   | **Azure Tenant ID** | `{your-tenant-id}` |
   | **Rate Limit (RPM)** | 60 |
   | **Max Concurrency** | 4 |
   | **Cache TTL** | 900 seconds |
   | **Description** | Azure Migrate, ASR, and DMS operations |

3. **Optional: Additional Environment Variables**
   - Expand **Additional Environment Variables** accordion
   - Add any custom variables:
     ```
     AZURE_SUBSCRIPTION_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
     AZURE_LOCATION=eastus
     ```

4. **Save Configuration**
   - Click **Create Server**
   - Server appears in the table with "unknown" health status

5. **Discover Tools**
   - Click **Discover** button next to the server
   - Wait for tool discovery to complete
   - Health status changes to "healthy" ✅
   - View discovered tools by clicking **View**

6. **Verify Health**
   - Click **Health** button
   - Check last discovery timestamp
   - Status should show "healthy"

### GCP MCP Server Registration

1. **Add New Server**
   - Click **Add Server** button
   - Fill in the form:

   | Field | Value |
   |-------|-------|
   | **Name** | GCP Migration Server |
   | **Provider** | GCP |
   | **Transport** | STDIO or WebSocket |
   | **Command** (STDIO) | `npx -y @google-cloud/mcp-server` |
   | **URL** (WebSocket) | `ws://localhost:8081` |
   | **Service Account Key Path** | `C:\secure\gcp-migration-key.json` |
   | **Rate Limit (RPM)** | 60 |
   | **Max Concurrency** | 4 |
   | **Cache TTL** | 900 seconds |
   | **Description** | GCP Compute Engine, DMS, and Storage Transfer operations |

2. **Optional: Additional Environment Variables**
   ```
   GCP_PROJECT_ID=your-project-id
   GCP_REGION=us-central1
   ```

3. **Save and Discover**
   - Click **Create Server**
   - Click **Discover** to retrieve available tools
   - Verify health status shows "healthy" ✅

### AWS MCP Server Registration

1. **Add New Server**
   - Click **Add Server** button
   - Fill in the form:

   | Field | Value |
   |-------|-------|
   | **Name** | AWS Migration Server |
   | **Provider** | AWS |
   | **Transport** | STDIO or WebSocket or Lambda (HTTP) |
   | **Command** (STDIO) | `npx -y @aws/mcp-server` |
   | **URL** (WebSocket) | `ws://localhost:8082` |
   | **URL** (Lambda) | `https://{lambda-function-url}` |
   | **AWS Access Key ID** | `AKIAIOSFODNN7EXAMPLE` |
   | **AWS Secret Access Key** | `wJalrXUtnFEMI/K7MDENG/...` |
   | **AWS Default Region** | `us-east-1` |
   | **Rate Limit (RPM)** | 60 |
   | **Max Concurrency** | 4 |
   | **Cache TTL** | 900 seconds |
   | **Description** | AWS MGN, DMS, and DataSync operations |

2. **Optional: Additional Environment Variables**
   ```
   AWS_SESSION_TOKEN=<optional-for-temporary-credentials>
   AWS_PROFILE=migration-mcp
   ```

3. **Save and Discover**
   - Click **Create Server**
   - Click **Discover** to retrieve available tools
   - Health status should show "healthy" ✅
   - View discovered tools (should include MGN, DMS, DataSync operations)

---

## Testing and Validation

### Test Azure MCP Server

Using Cloud Orchestration Service API:

```powershell
# Check Azure adapter can find MCP server
curl -X GET http://localhost:8020/api/cloud-orchestration/azure/server-status

# Expected response:
# {
#   "status": "available",
#   "servers": [{
#     "id": "azure-1",
#     "name": "Azure Migration Server",
#     "provider": "azure",
#     "health_status": "healthy"
#   }]
# }
```

### Test GCP MCP Server

```powershell
# Check GCP adapter can find MCP server
curl -X GET http://localhost:8020/api/cloud-orchestration/gcp/server-status

# Expected response:
# {
#   "status": "available",
#   "servers": [{
#     "id": "gcp-1",
#     "name": "GCP Migration Server",
#     "provider": "gcp",
#     "health_status": "healthy"
#   }]
# }
```

### Test Tool Execution

#### Azure Example
```powershell
# Test Azure Migrate assessment
curl -X POST http://localhost:8020/api/cloud-orchestration/waves/{wave-id}/migrate \
  -H "Content-Type: application/json" \
  -d '{
    "target_platform": "azure",
    "operation": "assess"
  }'
```

#### GCP Example
```powershell
# Test GCP Compute Engine migration
curl -X POST http://localhost:8020/api/cloud-orchestration/waves/{wave-id}/migrate \
  -H "Content-Type: application/json" \
  -d '{
    "target_platform": "gcp",
    "operation": "create_migration"
  }'
```

#### AWS Example
```powershell
# Test AWS Application Migration Service (MGN)
curl -X POST http://localhost:8020/api/cloud-orchestration/waves/{wave-id}/migrate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {token}" \
  -d '{
    "target_platform": "aws",
    "operation": "mgn_initialize"
  }'

# Test AWS DMS database migration
curl -X POST http://localhost:8012/api/cloud-tools/http \
  -H "Content-Type: application/json" \
  -d '{
    "method": "POST",
    "url": "http://localhost:8007/tools/aws-dms-create-replication-instance",
    "json": {
      "instance_id": "test-dms-instance",
      "instance_class": "dms.t3.micro",
      "allocated_storage": 50,
      "vpc_security_group_ids": ["sg-12345"],
      "replication_subnet_group_id": "default",
      "engine_version": "3.4.7"
    }
  }'

# Test AWS DataSync file transfer
curl -X POST http://localhost:8012/api/cloud-tools/http \
  -H "Content-Type: application/json" \
  -d '{
    "method": "POST",
    "url": "http://localhost:8007/tools/aws-datasync-create-task",
    "json": {
      "source_location_arn": "arn:aws:datasync:us-east-1:123456789012:location/loc-source",
      "destination_location_arn": "arn:aws:datasync:us-east-1:123456789012:location/loc-dest",
      "cloud_watch_log_group_arn": "arn:aws:logs:us-east-1:123456789012:log-group:/aws/datasync"
    }
  }'
```

---

## Troubleshooting

### Issue: "No enabled Azure MCP server found in registry"

**Cause:** Azure MCP server not registered or disabled.

**Solution:**
1. Go to Settings → MCP Servers
2. Verify Azure server exists in the table
3. Check "Enabled" toggle is ON
4. Click "Health" to verify connectivity
5. If health is "unhealthy", check credentials and transport configuration

### Issue: "Failed to retrieve Azure MCP server" (network error)

**Cause:** MCP server process not running or unreachable.

**Solution:**

**For STDIO transport:**
```powershell
# Verify command exists
npx @azure/mcp-server --version

# If not found, install
npm install -g @azure/mcp-server
```

**For WebSocket transport:**
```powershell
# Check if server is running
netstat -an | findstr "8080"

# If not running, start Docker container
docker start azure-mcp-server

# View logs
docker logs azure-mcp-server
```

### Issue: "Missing required Azure credentials"

**Cause:** Environment variables not set correctly.

**Solution:**
1. Edit MCP server in UI
2. Verify all three Azure credentials are filled:
   - AZURE_CLIENT_ID
   - AZURE_CLIENT_SECRET
   - AZURE_TENANT_ID
3. Test credentials manually:
   ```powershell
   az login --service-principal -u {CLIENT_ID} -p {CLIENT_SECRET} --tenant {TENANT_ID}
   ```

### Issue: GCP "GOOGLE_APPLICATION_CREDENTIALS file not found"

**Cause:** File path incorrect or file doesn't exist.

**Solution:**
1. Verify file exists:
   ```powershell
   Test-Path "C:\secure\gcp-migration-key.json"
   ```
2. Use absolute path (not relative)
3. Check file permissions (readable by MCP server process)
4. For Docker, ensure volume mount is correct:
   ```powershell
   docker inspect gcp-mcp-server | grep -A 5 "Mounts"
   ```

### Issue: "Tool discovery failed" or "Cache TTL expired"

**Cause:** MCP server took too long to respond or crashed.

**Solution:**
1. Increase cache TTL in server configuration (e.g., 1800 seconds)
2. Reduce max concurrency to avoid overwhelming server
3. Check MCP server logs for errors
4. Verify network connectivity to cloud APIs (Azure/GCP)
5. Try manual tool discovery:
   ```powershell
   curl -X POST http://localhost:8008/api/mcp/servers/{server-id}/discover
   ```

### Issue: Rate limit exceeded

**Cause:** Too many API calls to MCP server.

**Solution:**
1. Edit server configuration
2. Adjust rate limits:
   - **Rate Limit (RPM):** 30-60 (default: 60)
   - **Max Concurrency:** 2-4 (default: 4)
3. Increase cache TTL to reduce discovery frequency
4. Check cloud provider API quotas (Azure/GCP/AWS)

### Issue: "No enabled AWS MCP server found in registry"

**Cause:** AWS MCP server not registered or disabled.

**Solution:**
1. Go to Settings → MCP Servers
2. Verify AWS server exists in the table
3. Check "Enabled" toggle is ON
4. Click "Health" to verify connectivity
5. If health is "unhealthy", check:
   - AWS_ACCESS_KEY_ID is set correctly
   - AWS_SECRET_ACCESS_KEY is valid
   - AWS_DEFAULT_REGION matches your target region

### Issue: AWS "InvalidClientTokenId" or "SignatureDoesNotMatch"

**Cause:** Invalid AWS credentials or incorrect secret key.

**Solution:**
1. Verify credentials using AWS CLI:
   ```bash
   aws sts get-caller-identity --profile migration-mcp
   ```
2. If error persists, regenerate access key:
   ```bash
   aws iam create-access-key --user-name migration-platform-mcp
   aws iam delete-access-key --user-name migration-platform-mcp --access-key-id OLD_KEY_ID
   ```
3. Update MCP server configuration with new credentials
4. Click "Health" to verify

### Issue: AWS "AccessDenied" when calling MGN/DMS/DataSync

**Cause:** IAM user lacks required permissions.

**Solution:**
1. Verify attached policies:
   ```bash
   aws iam list-attached-user-policies --user-name migration-platform-mcp
   ```
2. Required policies:
   - `AWSApplicationMigrationFullAccess` (for MGN)
   - `AmazonDMSFullAccess` (for DMS)
   - `AWSDataSyncFullAccess` (for DataSync)
   - `AmazonEC2ReadOnlyAccess` (for server discovery)
3. Attach missing policies:
   ```bash
   aws iam attach-user-policy --user-name migration-platform-mcp \
     --policy-arn arn:aws:iam::aws:policy/AWSApplicationMigrationFullAccess
   ```
4. For custom policies, verify JSON has correct permissions

### Issue: AWS MGN "Service not initialized in this region"

**Cause:** AWS MGN not initialized in target region.

**Solution:**
1. Initialize MGN service:
   ```bash
   aws mgn initialize-service --region us-east-1
   ```
2. Wait 2-3 minutes for initialization
3. Verify initialization:
   ```bash
   aws mgn describe-replication-configuration-templates --region us-east-1
   ```
4. Retry migration operation

### Issue: AWS "Region not specified" or "InvalidRegion"

**Cause:** AWS_DEFAULT_REGION not set or invalid.

**Solution:**
1. Edit AWS MCP server configuration
2. Set **AWS Default Region** to valid region (e.g., `us-east-1`, `us-west-2`, `eu-west-1`)
3. For Docker deployment, ensure `-e AWS_DEFAULT_REGION=us-east-1` is set
4. Verify region availability for your AWS service:
   ```bash
   aws ec2 describe-regions --all-regions
   ```

---

## Custom MCP Server Development

If official MCP servers are not available, you can build custom implementations:

### Azure MCP Server (Python Example)

```python
# azure_mcp_server.py
from mcp import MCPServer, Tool, ToolParameter
from azure.identity import ClientSecretCredential
from azure.mgmt.migrate import AzureMigrateV2

class AzureMCPServer(MCPServer):
    def __init__(self):
        super().__init__(name="azure-migrate-mcp")
        self.credential = ClientSecretCredential(
            tenant_id=os.getenv("AZURE_TENANT_ID"),
            client_id=os.getenv("AZURE_CLIENT_ID"),
            client_secret=os.getenv("AZURE_CLIENT_SECRET")
        )
        self.migrate_client = AzureMigrateV2(self.credential)
        
        self.register_tool(
            name="azure_migrate_assess_machine",
            description="Assess a machine for Azure migration",
            parameters=[
                ToolParameter("subscriptionId", "string", required=True),
                ToolParameter("resourceGroupName", "string", required=True),
                ToolParameter("projectName", "string", required=True),
                ToolParameter("machineId", "string", required=True)
            ],
            handler=self.assess_machine
        )
    
    async def assess_machine(self, **kwargs):
        # Implementation using Azure SDK
        result = self.migrate_client.machines.get_assessment(...)
        return result.as_dict()

if __name__ == "__main__":
    server = AzureMCPServer()
    server.run(transport="stdio")  # or "websocket" on port 8080
```

Run the server:
```powershell
python azure_mcp_server.py
```

### GCP MCP Server (Python Example)

```python
# gcp_mcp_server.py
from mcp import MCPServer, Tool
from google.cloud import compute_v1
from google.auth import default

class GCPMCPServer(MCPServer):
    def __init__(self):
        super().__init__(name="gcp-migrate-mcp")
        self.credentials, self.project = default()
        self.compute_client = compute_v1.InstancesClient(credentials=self.credentials)
        
        self.register_tool(
            name="gcp_compute_create_migration",
            description="Create a VM migration using Migrate for Compute Engine",
            parameters=[...],
            handler=self.create_migration
        )
    
    async def create_migration(self, **kwargs):
        # Implementation using GCP SDK
        operation = self.compute_client.insert(...)
        return {"operation_id": operation.name}

if __name__ == "__main__":
    server = GCPMCPServer()
    server.run(transport="stdio")
```

### AWS MCP Server (Python Example)

```python
# aws_mcp_server.py
from mcp import MCPServer, Tool, ToolParameter
import boto3
import os

class AWSMCPServer(MCPServer):
    def __init__(self):
        super().__init__(name="aws-migrate-mcp")
        self.mgn_client = boto3.client(
            'mgn',
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        )
        self.dms_client = boto3.client('dms')
        self.datasync_client = boto3.client('datasync')
        
        # Register MGN tools
        self.register_tool(
            name="aws_mgn_initialize_service",
            description="Initialize AWS Application Migration Service in a region",
            parameters=[
                ToolParameter("aws_region", "string", required=True)
            ],
            handler=self.mgn_initialize_service
        )
        
        self.register_tool(
            name="aws_mgn_create_replication_configuration",
            description="Create replication configuration for source server",
            parameters=[
                ToolParameter("source_server_id", "string", required=True),
                ToolParameter("replication_configuration_template_id", "string", required=True),
                ToolParameter("staging_area_subnet_id", "string", required=True),
                ToolParameter("replication_server_instance_type", "string", required=False)
            ],
            handler=self.mgn_create_replication
        )
        
        # Register DMS tools
        self.register_tool(
            name="aws_dms_create_replication_instance",
            description="Create DMS replication instance",
            parameters=[
                ToolParameter("instance_id", "string", required=True),
                ToolParameter("instance_class", "string", required=True),
                ToolParameter("allocated_storage", "integer", required=True)
            ],
            handler=self.dms_create_instance
        )
        
        # Register DataSync tools
        self.register_tool(
            name="aws_datasync_create_task",
            description="Create DataSync task for data transfer",
            parameters=[
                ToolParameter("source_location_arn", "string", required=True),
                ToolParameter("destination_location_arn", "string", required=True)
            ],
            handler=self.datasync_create_task
        )
    
    async def mgn_initialize_service(self, aws_region: str):
        """Initialize MGN service in specified region"""
        response = self.mgn_client.initialize_service()
        return {
            "status": "initialized",
            "region": aws_region,
            "service_id": response.get('serviceId')
        }
    
    async def mgn_create_replication(self, **kwargs):
        """Create replication configuration for source server"""
        response = self.mgn_client.create_replication_configuration_template(
            sourceServerID=kwargs['source_server_id'],
            stagingAreaSubnetId=kwargs['staging_area_subnet_id'],
            replicationServerInstanceType=kwargs.get('replication_server_instance_type', 't3.small')
        )
        return {
            "replication_config_id": response['replicationConfigurationTemplateID'],
            "status": response['arn']
        }
    
    async def dms_create_instance(self, **kwargs):
        """Create DMS replication instance"""
        response = self.dms_client.create_replication_instance(
            ReplicationInstanceIdentifier=kwargs['instance_id'],
            ReplicationInstanceClass=kwargs['instance_class'],
            AllocatedStorage=kwargs['allocated_storage']
        )
        return {
            "instance_arn": response['ReplicationInstance']['ReplicationInstanceArn'],
            "status": response['ReplicationInstance']['ReplicationInstanceStatus']
        }
    
    async def datasync_create_task(self, **kwargs):
        """Create DataSync task"""
        response = self.datasync_client.create_task(
            SourceLocationArn=kwargs['source_location_arn'],
            DestinationLocationArn=kwargs['destination_location_arn']
        )
        return {
            "task_arn": response['TaskArn']
        }

if __name__ == "__main__":
    server = AWSMCPServer()
    server.run(transport="stdio")  # or "websocket" on port 8082
```

Run the server:
```powershell
# Set AWS credentials
$env:AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"
$env:AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
$env:AWS_DEFAULT_REGION = "us-east-1"

# Run server
python aws_mcp_server.py
```

---

## Security Best Practices

### Credential Storage
- ✅ **DO:** Use environment variables or secure vaults (Azure Key Vault, GCP Secret Manager)
- ✅ **DO:** Rotate Service Principal/Service Account keys regularly (90 days)
- ✅ **DO:** Use least-privilege permissions (only required roles)
- ❌ **DON'T:** Hardcode credentials in code or configuration files
- ❌ **DON'T:** Commit service account keys to version control

### Network Security
- ✅ **DO:** Use HTTPS/WSS (WebSocket Secure) for remote MCP servers
- ✅ **DO:** Restrict MCP server network access (firewall rules)
- ✅ **DO:** Use VPN or private networks for production MCP servers
- ❌ **DON'T:** Expose MCP servers to public internet without authentication

### Monitoring
- ✅ **DO:** Monitor MCP server health status regularly
- ✅ **DO:** Set up alerts for failed tool discoveries
- ✅ **DO:** Log all MCP tool executions for audit trail
- ✅ **DO:** Review cloud provider audit logs (Azure Activity Log, GCP Cloud Audit Logs)

---

## Next Steps

1. ✅ Register Azure MCP server in Settings → MCP Servers
2. ✅ Register GCP MCP server in Settings → MCP Servers
3. ✅ Test tool discovery for both providers
4. ✅ Verify health status shows "healthy"
5. 📖 Read [Cloud Orchestration Service Documentation](./CLOUD_ORCHESTRATION_SERVICE.md)
6. 🚀 Create your first migration wave using Cloud Orchestration

---

## Additional Resources

- [MCP Protocol Specification](https://modelcontextprotocol.io)
- [Azure Migrate Documentation](https://docs.microsoft.com/azure/migrate/)
- [GCP Migrate for Compute Engine](https://cloud.google.com/migrate/compute-engine/docs)
- [Cloud Orchestration Service API](./API_CLOUD_ORCHESTRATION.md)
- [Platform User Guide](./USER_GUIDE_PLATFORM_WORKFLOWS.md)

---

**Questions or Issues?**
- Check [Troubleshooting](#troubleshooting) section
- Review MCP server logs
- Contact platform support team
