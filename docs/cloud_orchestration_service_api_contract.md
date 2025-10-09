# Cloud Orchestration Service - API Contract

**Service Name**: cloud-orchestration-service  
**Port**: 8012  
**Version**: 1.0.0  
**Protocol**: HTTP/REST + WebSocket  
**Base URL**: `http://localhost:8012/api/cloud-orchestration`

---

## Overview

The Cloud Orchestration Service is a unified multi-cloud migration orchestrator that wraps AWS MCP, Azure MCP, and GCP MCP servers. It provides CSP-agnostic APIs for migration wave management, resource discovery, migration execution, and real-time progress tracking.

### Key Responsibilities
- Multi-cloud migration orchestration (AWS, Azure, GCP)
- Migration wave lifecycle management
- CSP-native service invocation via MCP adapters
- Real-time progress tracking via WebSocket
- Migration state management and rollback orchestration

---

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│       Cloud Orchestration Service (Port 8012)               │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ AWS MCP      │  │ Azure MCP    │  │ GCP MCP      │     │
│  │ Adapter      │  │ Adapter      │  │ Adapter      │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
│         │                  │                  │              │
│  ┌──────▼──────────────────▼──────────────────▼──────┐     │
│  │         Multi-Cloud Abstraction Layer             │     │
│  └──────────────────────────────────────────────────┘     │
│                                                              │
│  ┌──────────────────────────────────────────────────┐     │
│  │    Migration Wave Orchestrator                   │     │
│  │  - Pre-migration phase                            │     │
│  │  - Migration phase                                │     │
│  │  - Post-migration phase                           │     │
│  └──────────────────────────────────────────────────┘     │
│                                                              │
│  ┌──────────────────────────────────────────────────┐     │
│  │    State Manager (PostgreSQL)                     │     │
│  │  - Migration waves                                │     │
│  │  - Resource inventory                             │     │
│  │  - Migration tasks                                │     │
│  └──────────────────────────────────────────────────┘     │
│                                                              │
│  ┌──────────────────────────────────────────────────┐     │
│  │    WebSocket Event Publisher                      │     │
│  │  - Real-time progress updates                     │     │
│  │  - Task status changes                            │     │
│  │  - Error notifications                            │     │
│  └──────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

---

## Database Schema

### Migration Waves Table
```sql
CREATE TABLE migration_waves (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    phase VARCHAR(50) NOT NULL CHECK (phase IN ('pre-migration', 'migration', 'post-migration')),
    status VARCHAR(50) NOT NULL CHECK (status IN ('pending', 'in-progress', 'completed', 'failed', 'rolled-back')),
    target_csp VARCHAR(20) NOT NULL CHECK (target_csp IN ('aws', 'azure', 'gcp')),
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_migration_waves_project ON migration_waves(project_id);
CREATE INDEX idx_migration_waves_status ON migration_waves(status);
```

### Migration Resources Table
```sql
CREATE TABLE migration_resources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wave_id UUID NOT NULL REFERENCES migration_waves(id) ON DELETE CASCADE,
    resource_type VARCHAR(100) NOT NULL, -- 'vm', 'database', 'storage', 'network'
    source_identifier VARCHAR(500) NOT NULL, -- Source VM ID, DB instance name, etc.
    target_identifier VARCHAR(500), -- Target AWS instance ID, Azure VM ID, etc.
    source_metadata JSONB DEFAULT '{}',
    target_metadata JSONB DEFAULT '{}',
    migration_status VARCHAR(50) NOT NULL CHECK (migration_status IN ('pending', 'replicating', 'testing', 'cutover', 'completed', 'failed')),
    progress_percentage INTEGER DEFAULT 0 CHECK (progress_percentage BETWEEN 0 AND 100),
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_migration_resources_wave ON migration_resources(wave_id);
CREATE INDEX idx_migration_resources_status ON migration_resources(migration_status);
```

### Migration Tasks Table
```sql
CREATE TABLE migration_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_id UUID NOT NULL REFERENCES migration_resources(id) ON DELETE CASCADE,
    task_type VARCHAR(100) NOT NULL, -- 'discovery', 'replication', 'validation', 'cutover', 'rollback'
    mcp_tool_name VARCHAR(200), -- e.g., 'aws_mgn_start_replication', 'azure_migrate_replicate_vm'
    input_parameters JSONB DEFAULT '{}',
    output_result JSONB DEFAULT '{}',
    status VARCHAR(50) NOT NULL CHECK (status IN ('pending', 'running', 'completed', 'failed', 'retrying')),
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_details TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_migration_tasks_resource ON migration_tasks(resource_id);
CREATE INDEX idx_migration_tasks_status ON migration_tasks(status);
```

---

## REST API Endpoints

### Wave Management

#### 1. Create Migration Wave
**POST** `/api/cloud-orchestration/projects/{project_id}/waves`

**Request Body**:
```json
{
  "name": "Wave 1 - Dev Environment",
  "description": "Migrate development workloads to AWS",
  "phase": "pre-migration",
  "target_csp": "aws",
  "metadata": {
    "target_region": "us-east-1",
    "migration_strategy": "lift-and-shift",
    "cutover_window": "2025-02-15T00:00:00Z"
  }
}
```

**Response**: `201 Created`
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "project_id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "Wave 1 - Dev Environment",
  "description": "Migrate development workloads to AWS",
  "phase": "pre-migration",
  "status": "pending",
  "target_csp": "aws",
  "metadata": {
    "target_region": "us-east-1",
    "migration_strategy": "lift-and-shift",
    "cutover_window": "2025-02-15T00:00:00Z"
  },
  "created_at": "2025-01-09T10:00:00Z",
  "updated_at": "2025-01-09T10:00:00Z"
}
```

#### 2. List Migration Waves
**GET** `/api/cloud-orchestration/projects/{project_id}/waves`

**Query Parameters**:
- `phase` (optional): Filter by phase (`pre-migration`, `migration`, `post-migration`)
- `status` (optional): Filter by status (`pending`, `in-progress`, `completed`, `failed`)
- `target_csp` (optional): Filter by CSP (`aws`, `azure`, `gcp`)

**Response**: `200 OK`
```json
{
  "waves": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Wave 1 - Dev Environment",
      "phase": "pre-migration",
      "status": "in-progress",
      "target_csp": "aws",
      "resource_count": 15,
      "progress_percentage": 45,
      "created_at": "2025-01-09T10:00:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

#### 3. Get Wave Details
**GET** `/api/cloud-orchestration/projects/{project_id}/waves/{wave_id}`

**Response**: `200 OK`
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "project_id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "Wave 1 - Dev Environment",
  "description": "Migrate development workloads to AWS",
  "phase": "migration",
  "status": "in-progress",
  "target_csp": "aws",
  "start_time": "2025-01-09T12:00:00Z",
  "metadata": {
    "target_region": "us-east-1",
    "migration_strategy": "lift-and-shift"
  },
  "resources": [
    {
      "id": "660e8400-e29b-41d4-a716-446655440001",
      "resource_type": "vm",
      "source_identifier": "vm-12345",
      "target_identifier": "i-0abc123def456789",
      "migration_status": "replicating",
      "progress_percentage": 65
    }
  ],
  "statistics": {
    "total_resources": 15,
    "pending": 5,
    "replicating": 8,
    "completed": 2,
    "failed": 0
  }
}
```

#### 4. Update Wave Status
**PATCH** `/api/cloud-orchestration/projects/{project_id}/waves/{wave_id}`

**Request Body**:
```json
{
  "status": "in-progress",
  "phase": "migration"
}
```

**Response**: `200 OK`
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "in-progress",
  "phase": "migration",
  "updated_at": "2025-01-09T14:00:00Z"
}
```

#### 5. Delete Wave
**DELETE** `/api/cloud-orchestration/projects/{project_id}/waves/{wave_id}`

**Response**: `204 No Content`

---

### Resource Management

#### 6. Add Resource to Wave
**POST** `/api/cloud-orchestration/projects/{project_id}/waves/{wave_id}/resources`

**Request Body**:
```json
{
  "resource_type": "vm",
  "source_identifier": "vm-production-web-01",
  "source_metadata": {
    "hostname": "web01.example.com",
    "ip_address": "10.0.1.50",
    "os": "Ubuntu 20.04",
    "cpu": 4,
    "memory_gb": 16,
    "disk_gb": 100
  },
  "target_metadata": {
    "target_instance_type": "t3.xlarge",
    "target_region": "us-east-1",
    "target_vpc": "vpc-12345"
  }
}
```

**Response**: `201 Created`
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440001",
  "wave_id": "550e8400-e29b-41d4-a716-446655440000",
  "resource_type": "vm",
  "source_identifier": "vm-production-web-01",
  "migration_status": "pending",
  "progress_percentage": 0,
  "created_at": "2025-01-09T10:30:00Z"
}
```

#### 7. List Wave Resources
**GET** `/api/cloud-orchestration/projects/{project_id}/waves/{wave_id}/resources`

**Query Parameters**:
- `resource_type` (optional): Filter by type (`vm`, `database`, `storage`)
- `migration_status` (optional): Filter by status (`pending`, `replicating`, `completed`)

**Response**: `200 OK`
```json
{
  "resources": [
    {
      "id": "660e8400-e29b-41d4-a716-446655440001",
      "resource_type": "vm",
      "source_identifier": "vm-production-web-01",
      "target_identifier": "i-0abc123def456789",
      "migration_status": "replicating",
      "progress_percentage": 65,
      "created_at": "2025-01-09T10:30:00Z"
    }
  ],
  "total": 1
}
```

#### 8. Get Resource Details
**GET** `/api/cloud-orchestration/projects/{project_id}/waves/{wave_id}/resources/{resource_id}`

**Response**: `200 OK`
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440001",
  "wave_id": "550e8400-e29b-41d4-a716-446655440000",
  "resource_type": "vm",
  "source_identifier": "vm-production-web-01",
  "target_identifier": "i-0abc123def456789",
  "source_metadata": {
    "hostname": "web01.example.com",
    "ip_address": "10.0.1.50",
    "os": "Ubuntu 20.04",
    "cpu": 4,
    "memory_gb": 16,
    "disk_gb": 100
  },
  "target_metadata": {
    "instance_id": "i-0abc123def456789",
    "instance_type": "t3.xlarge",
    "region": "us-east-1",
    "public_ip": "54.123.45.67"
  },
  "migration_status": "replicating",
  "progress_percentage": 65,
  "tasks": [
    {
      "id": "770e8400-e29b-41d4-a716-446655440002",
      "task_type": "replication",
      "status": "running",
      "started_at": "2025-01-09T12:00:00Z"
    }
  ]
}
```

---

### Migration Execution (MCP Integration)

#### 9. Start Migration Wave
**POST** `/api/cloud-orchestration/projects/{project_id}/waves/{wave_id}/start`

**Request Body**:
```json
{
  "dry_run": false,
  "auto_cutover": false,
  "cutover_window": "2025-02-15T00:00:00Z"
}
```

**Response**: `202 Accepted`
```json
{
  "wave_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "in-progress",
  "tasks_created": 15,
  "message": "Migration wave started successfully"
}
```

**Internal Logic**:
1. Validate wave status (must be `pending`)
2. For each resource in wave:
   - Create migration task based on `target_csp`
   - Invoke appropriate MCP tool:
     - AWS: `aws_mgn_start_replication`
     - Azure: `azure_migrate_replicate_vm`
     - GCP: `gcp_migrate_start_replication`
3. Update wave status to `in-progress`
4. Publish WebSocket event: `wave.started`

#### 10. Execute Cutover
**POST** `/api/cloud-orchestration/projects/{project_id}/waves/{wave_id}/cutover`

**Request Body**:
```json
{
  "resources": [
    "660e8400-e29b-41d4-a716-446655440001",
    "660e8400-e29b-41d4-a716-446655440002"
  ],
  "shutdown_source": true
}
```

**Response**: `202 Accepted`
```json
{
  "wave_id": "550e8400-e29b-41d4-a716-446655440000",
  "cutover_tasks": 2,
  "message": "Cutover initiated for 2 resources"
}
```

**Internal Logic**:
1. For each resource:
   - Invoke MCP cutover tool:
     - AWS: `aws_mgn_start_cutover`
     - Azure: `azure_migrate_cutover`
     - GCP: `gcp_migrate_cutover`
   - If `shutdown_source=true`, shutdown source VM after cutover
2. Update resource status to `cutover`
3. Publish WebSocket event: `resource.cutover_started`

#### 11. Rollback Migration
**POST** `/api/cloud-orchestration/projects/{project_id}/waves/{wave_id}/rollback`

**Request Body**:
```json
{
  "reason": "Validation failed - network connectivity issues",
  "rollback_scope": "full" // or "partial"
}
```

**Response**: `202 Accepted`
```json
{
  "wave_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "rolling-back",
  "message": "Rollback initiated"
}
```

**Internal Logic**:
1. Stop all in-progress replication tasks
2. Delete target resources (AWS instances, Azure VMs, GCP instances)
3. Restore source resources to operational state
4. Update wave status to `rolled-back`
5. Publish WebSocket event: `wave.rolled_back`

---

### CSP-Specific Operations

#### 12. AWS - List MGN Source Servers
**GET** `/api/cloud-orchestration/aws/mgn/source-servers`

**Query Parameters**:
- `region` (required): AWS region (e.g., `us-east-1`)

**Response**: `200 OK`
```json
{
  "source_servers": [
    {
      "source_server_id": "s-1234567890abcdef0",
      "hostname": "web-server-01",
      "replication_status": "CONTINUOUS",
      "last_seen_at": "2025-01-09T14:00:00Z"
    }
  ]
}
```

**MCP Tool Invoked**: `aws_mgn_list_source_servers`

#### 13. Azure - Get Migration Job Status
**GET** `/api/cloud-orchestration/azure/migrate/jobs/{job_id}`

**Response**: `200 OK`
```json
{
  "job_id": "job-12345",
  "status": "InProgress",
  "progress_percentage": 75,
  "started_at": "2025-01-09T12:00:00Z"
}
```

**MCP Tool Invoked**: `azure_migrate_get_job`

#### 14. GCP - List Migrate for Compute Engine Tasks
**GET** `/api/cloud-orchestration/gcp/migrate/tasks`

**Query Parameters**:
- `project_id` (required): GCP project ID

**Response**: `200 OK`
```json
{
  "tasks": [
    {
      "task_id": "task-abc123",
      "vm_name": "production-db-01",
      "status": "RUNNING",
      "progress_percentage": 60
    }
  ]
}
```

**MCP Tool Invoked**: `gcp_migrate_list_tasks`

---

## WebSocket Events

### Connection
**URL**: `ws://localhost:8012/ws/cloud-orchestration/projects/{project_id}/waves/{wave_id}`

**Authentication**: JWT token in query parameter `?token=<jwt_token>`

### Event Types

#### 1. Wave Status Changed
```json
{
  "event_type": "wave.status_changed",
  "timestamp": "2025-01-09T14:00:00Z",
  "data": {
    "wave_id": "550e8400-e29b-41d4-a716-446655440000",
    "old_status": "pending",
    "new_status": "in-progress"
  }
}
```

#### 2. Resource Progress Updated
```json
{
  "event_type": "resource.progress_updated",
  "timestamp": "2025-01-09T14:05:00Z",
  "data": {
    "resource_id": "660e8400-e29b-41d4-a716-446655440001",
    "migration_status": "replicating",
    "progress_percentage": 75,
    "estimated_completion": "2025-01-09T16:00:00Z"
  }
}
```

#### 3. Task Completed
```json
{
  "event_type": "task.completed",
  "timestamp": "2025-01-09T14:10:00Z",
  "data": {
    "task_id": "770e8400-e29b-41d4-a716-446655440002",
    "resource_id": "660e8400-e29b-41d4-a716-446655440001",
    "task_type": "replication",
    "status": "completed",
    "duration_seconds": 3600
  }
}
```

#### 4. Error Occurred
```json
{
  "event_type": "error.occurred",
  "timestamp": "2025-01-09T14:15:00Z",
  "data": {
    "resource_id": "660e8400-e29b-41d4-a716-446655440001",
    "error_code": "REPLICATION_FAILED",
    "error_message": "Network connectivity lost to source server",
    "retry_attempt": 1,
    "max_retries": 3
  }
}
```

---

## MCP Adapter Interfaces

### AWS MCP Adapter

```python
class AWSMCPAdapter:
    """Adapter for AWS MCP Server integration."""
    
    def __init__(self, mcp_server_url: str, aws_credentials: dict):
        self.mcp_server_url = mcp_server_url
        self.credentials = aws_credentials
    
    async def start_replication(
        self,
        source_server_id: str,
        region: str,
        replication_settings: dict
    ) -> dict:
        """
        Start AWS MGN replication for a source server.
        
        MCP Tool: aws_mgn_start_replication
        """
        pass
    
    async def start_cutover(
        self,
        source_server_id: str,
        region: str
    ) -> dict:
        """
        Start AWS MGN cutover.
        
        MCP Tool: aws_mgn_start_cutover
        """
        pass
    
    async def get_replication_status(
        self,
        source_server_id: str,
        region: str
    ) -> dict:
        """
        Get AWS MGN replication status.
        
        MCP Tool: aws_mgn_describe_source_servers
        """
        pass
```

### Azure MCP Adapter

```python
class AzureMCPAdapter:
    """Adapter for Azure MCP Server integration."""
    
    def __init__(self, mcp_server_url: str, azure_credentials: dict):
        self.mcp_server_url = mcp_server_url
        self.credentials = azure_credentials
    
    async def replicate_vm(
        self,
        vm_id: str,
        target_resource_group: str,
        target_region: str
    ) -> dict:
        """
        Start Azure Migrate VM replication.
        
        MCP Tool: azure_migrate_replicate_vm
        """
        pass
    
    async def get_job_status(
        self,
        job_id: str
    ) -> dict:
        """
        Get Azure Migrate job status.
        
        MCP Tool: azure_migrate_get_job
        """
        pass
```

### GCP MCP Adapter

```python
class GCPMCPAdapter:
    """Adapter for GCP MCP Toolbox integration."""
    
    def __init__(self, mcp_server_url: str, gcp_credentials: dict):
        self.mcp_server_url = mcp_server_url
        self.credentials = gcp_credentials
    
    async def start_migration(
        self,
        vm_name: str,
        target_project: str,
        target_zone: str
    ) -> dict:
        """
        Start GCP Migrate for Compute Engine migration.
        
        MCP Tool: gcp_migrate_start_replication
        """
        pass
```

---

## Error Handling

### Error Response Format
```json
{
  "error": {
    "code": "MIGRATION_FAILED",
    "message": "Failed to start replication for resource vm-production-web-01",
    "details": {
      "resource_id": "660e8400-e29b-41d4-a716-446655440001",
      "mcp_error": "AWS MGN API error: InvalidSourceServerID"
    },
    "timestamp": "2025-01-09T14:20:00Z"
  }
}
```

### Error Codes
- `WAVE_NOT_FOUND`: Migration wave does not exist
- `RESOURCE_NOT_FOUND`: Migration resource does not exist
- `INVALID_WAVE_STATUS`: Wave status does not allow this operation
- `MIGRATION_FAILED`: MCP tool invocation failed
- `REPLICATION_FAILED`: Replication process failed
- `CUTOVER_FAILED`: Cutover process failed
- `ROLLBACK_FAILED`: Rollback process failed
- `MCP_ADAPTER_ERROR`: MCP adapter communication error
- `AUTHENTICATION_FAILED`: CSP authentication failed

---

## Configuration

### Environment Variables
```bash
# Service Configuration
CLOUD_ORCHESTRATION_PORT=8012
DATABASE_URL=postgresql://user:password@localhost:5432/ascent_db

# AWS MCP Server
AWS_MCP_SERVER_URL=http://localhost:5100
AWS_ACCESS_KEY_ID=<aws_access_key>
AWS_SECRET_ACCESS_KEY=<aws_secret_key>
AWS_DEFAULT_REGION=us-east-1

# Azure MCP Server
AZURE_MCP_SERVER_URL=http://localhost:5101
AZURE_TENANT_ID=<tenant_id>
AZURE_CLIENT_ID=<client_id>
AZURE_CLIENT_SECRET=<client_secret>

# GCP MCP Server
GCP_MCP_SERVER_URL=http://localhost:5102
GCP_SERVICE_ACCOUNT_KEY=<base64_encoded_key>
GCP_PROJECT_ID=<project_id>

# WebSocket
WEBSOCKET_SERVICE_URL=http://localhost:8009

# Retry Configuration
MAX_RETRIES=3
RETRY_BACKOFF_SECONDS=5
```

---

## Testing Plan

### Unit Tests
- MCP adapter connection tests
- Wave lifecycle state machine tests
- Resource status transition tests
- Error handling and retry logic tests

### Integration Tests
- End-to-end wave creation to cutover flow
- Multi-cloud migration (AWS + Azure + GCP)
- WebSocket event publishing tests
- Database transaction rollback tests

### Performance Tests
- Concurrent wave execution (10+ waves)
- Large-scale resource migration (1000+ VMs)
- WebSocket connection stress test (100+ concurrent clients)

---

## Deployment

### Docker Compose (Development)
```yaml
services:
  cloud-orchestration:
    build: ./services/cloud-orchestration-service
    ports:
      - "8012:8012"
    environment:
      - DATABASE_URL=postgresql://postgres:password@postgres:5432/ascent_db
      - AWS_MCP_SERVER_URL=http://aws-mcp:5100
      - AZURE_MCP_SERVER_URL=http://azure-mcp:5101
      - GCP_MCP_SERVER_URL=http://gcp-mcp:5102
    depends_on:
      - postgres
      - aws-mcp
      - azure-mcp
      - gcp-mcp
```

### Kubernetes Helm Chart
```yaml
# values.yaml
cloudOrchestration:
  replicaCount: 3
  image:
    repository: ascent/cloud-orchestration-service
    tag: "1.0.0"
  service:
    port: 8012
  env:
    AWS_MCP_SERVER_URL: "http://aws-mcp:5100"
    AZURE_MCP_SERVER_URL: "http://azure-mcp:5101"
    GCP_MCP_SERVER_URL: "http://gcp-mcp:5102"
```

---

## Metrics & Monitoring

### Prometheus Metrics
- `cloud_orchestration_waves_total{status}`: Total migration waves by status
- `cloud_orchestration_resources_total{migration_status}`: Total resources by migration status
- `cloud_orchestration_tasks_duration_seconds`: Task execution duration
- `cloud_orchestration_mcp_calls_total{adapter, tool}`: MCP tool invocation count
- `cloud_orchestration_errors_total{error_code}`: Error count by code

### Logging
- Structured JSON logs (INFO, WARNING, ERROR levels)
- Correlation ID tracking for distributed tracing
- MCP request/response logging
- Database query performance logging

---

**Document Version**: 1.0  
**Last Updated**: January 9, 2025  
**Author**: Cloud Orchestration Team
