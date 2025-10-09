# Phase 1 Implementation Plan - CSP MCP Integration

**Phase**: Phase 1 - CSP MCP Integration  
**Duration**: Weeks 3-6 (4 weeks)  
**Target Start**: October 9, 2025 (ACTUAL START)  
**Target Completion**: November 6, 2025  
**Status**: 🟡 IN PROGRESS

---

## Overview

Phase 1 focuses on implementing the three new domain-driven services with full MCP adapter integration, database migrations, and core business logic. This phase builds upon the API contracts defined in Phase 0.

---

## Analysis of Existing MCP Implementation

### Current State (AI Agent Service)

The `ai-agent-service` already has a functional MCP infrastructure:

**Location**: `services/ai-agent-service/`

**Key Components**:
1. **MCP Models** (`app/core/mcp_models.py`):
   - `MCPServerConfig`: Server configuration with connection, auth, rate limiting
   - `UnifiedToolSchema`: Tool metadata
   - `ExecuteToolRequest/Response`: Tool execution contracts
   - Support for STDIO, WebSocket, SSE transports
   - Provider support: AWS, Azure, GCP, custom

2. **MCP Registry** (`app/repository/mcp_registry.py`):
   - In-memory registry with JSON persistence
   - Thread-safe operations with RLock
   - Tool caching with TTL
   - Health status tracking
   - Circuit breaker configuration

3. **MCP Initialization Scripts**:
   - `scripts/init_aws_pricing_mcp.py`: AWS Pricing MCP setup
   - Docker and NPX execution modes

**Decision**: ✅ REUSE existing MCP infrastructure  
**Rationale**: The ai-agent-service MCP implementation is production-ready, well-structured, and supports all required features (multi-provider, auth, rate limiting, circuit breakers). We will:
1. Keep MCP models in ai-agent-service as the **MCP control plane**
2. New services will act as MCP **data plane** - consuming MCP tools via HTTP API
3. Promote MCP models to shared library for reuse

---

## Architecture Decision

### Service Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   AI Agent Service (Port 8008)                  │
│                    [MCP Control Plane]                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  MCP Registry                                            │  │
│  │  - AWS MCP Servers (MGN, DMS, DataSync, Cost Explorer)  │  │
│  │  - Azure MCP Servers (Migrate, ASR, DMS, Cost Mgmt)     │  │
│  │  - GCP MCP Servers (Migrate, Billing API)               │  │
│  │  - Terraform MCP Server                                  │  │
│  │  - AWS Pricing MCP Server                                │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  REST API: /api/ai-agent/mcp/...                               │
│  - GET /servers (list MCP servers)                             │
│  - POST /execute (execute MCP tool)                            │
│  - GET /tools/{server_id} (list server tools)                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP API
                              ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                                                             │
    │  cloud-orchestration-service  iac-governance-service       │
    │  finops-optimization-service                                │
    │                                                             │
    │  [MCP Data Plane - MCP Tool Consumers]                     │
    └─────────────────────────────────────────────────────────────┘
```

### Shared MCP Client Library

Create `common/mcp_client.py` that new services will use:

```python
class MCPClient:
    """Client for invoking MCP tools via AI Agent Service."""
    
    async def execute_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict
    ) -> dict:
        """Execute MCP tool via AI Agent Service MCP proxy."""
        pass
```

---

## Implementation Tasks

### Task 1: Promote MCP Models to Shared Library (Day 1)

**Objective**: Make MCP models reusable across services

**Steps**:
1. Create `common/mcp/` directory
2. Copy `mcp_models.py` from ai-agent-service to `common/mcp/models.py`
3. Create `common/mcp/client.py` for HTTP-based MCP tool execution
4. Update ai-agent-service to use shared models
5. Create MCP client utility functions

**Deliverables**:
- `common/mcp/models.py` (MCPServerConfig, UnifiedToolSchema, etc.)
- `common/mcp/client.py` (MCPClient class)
- `common/mcp/__init__.py` (exports)

**Acceptance Criteria**:
- ai-agent-service uses shared MCP models
- New services can import from `common.mcp`
- No breaking changes to existing MCP functionality

---

### Task 2: Cloud Orchestration Service - Database Setup (Day 2)

**Objective**: Create PostgreSQL database schema with Alembic migrations

**Database Tables** (from API contract):
1. `migration_waves`
2. `migration_resources`
3. `migration_tasks`

**Steps**:
1. Create service directory: `services/cloud-orchestration-service/`
2. Set up FastAPI project structure
3. Configure Alembic for database migrations
4. Create initial migration: `001_create_cloud_orchestration_tables.py`
5. Define SQLAlchemy models

**Directory Structure**:
```
services/cloud-orchestration-service/
├── alembic/
│   ├── versions/
│   │   └── 001_create_cloud_orchestration_tables.py
│   └── env.py
├── alembic.ini
├── app/
│   ├── main.py
│   ├── config.py
│   ├── models/
│   │   ├── migration_wave.py
│   │   ├── migration_resource.py
│   │   └── migration_task.py
│   ├── schemas/
│   │   └── wave_schemas.py
│   ├── routers/
│   │   └── wave_router.py
│   ├── services/
│   │   └── wave_service.py
│   └── adapters/
│       ├── aws_mcp_adapter.py
│       ├── azure_mcp_adapter.py
│       └── gcp_mcp_adapter.py
├── requirements.txt
└── Dockerfile
```

**Alembic Migration Example**:
```python
# alembic/versions/001_create_cloud_orchestration_tables.py
def upgrade():
    op.create_table(
        'migration_waves',
        sa.Column('id', postgresql.UUID(), primary_key=True),
        sa.Column('project_id', postgresql.UUID(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('phase', sa.String(50), nullable=False),
        # ... (rest of schema from API contract)
    )
```

**Deliverables**:
- Alembic configuration
- Initial database migration
- SQLAlchemy models for all 3 tables
- Database connection setup

---

### Task 3: Cloud Orchestration Service - MCP Adapters (Days 3-4)

**Objective**: Implement AWS, Azure, GCP MCP adapters

**AWS MCP Adapter**:
```python
# app/adapters/aws_mcp_adapter.py
from common.mcp.client import MCPClient

class AWSMCPAdapter:
    def __init__(self, mcp_client: MCPClient):
        self.mcp_client = mcp_client
        self.server_name = "AWS Migration MCP"
    
    async def start_replication(
        self, 
        source_server_id: str,
        region: str
    ) -> dict:
        return await self.mcp_client.execute_tool(
            server_name=self.server_name,
            tool_name="aws_mgn_start_replication",
            arguments={
                "source_server_id": source_server_id,
                "region": region
            }
        )
    
    async def start_cutover(
        self, 
        source_server_id: str,
        region: str
    ) -> dict:
        return await self.mcp_client.execute_tool(
            server_name=self.server_name,
            tool_name="aws_mgn_start_cutover",
            arguments={
                "source_server_id": source_server_id,
                "region": region
            }
        )
```

**Similar implementations for**:
- `AzureMCPAdapter` (Azure Migrate tools)
- `GCPMCPAdapter` (GCP Migrate tools)

**Deliverables**:
- AWS MCP Adapter (MGN, DMS, DataSync)
- Azure MCP Adapter (Migrate, ASR, DMS)
- GCP MCP Adapter (Migrate for Compute Engine)
- Adapter unit tests

---

### Task 4: Cloud Orchestration Service - Wave Management API (Day 5)

**Objective**: Implement wave CRUD operations

**Endpoints** (from API contract):
1. POST `/api/cloud-orchestration/projects/{project_id}/waves`
2. GET `/api/cloud-orchestration/projects/{project_id}/waves`
3. GET `/api/cloud-orchestration/projects/{project_id}/waves/{wave_id}`
4. PATCH `/api/cloud-orchestration/projects/{project_id}/waves/{wave_id}`
5. DELETE `/api/cloud-orchestration/projects/{project_id}/waves/{wave_id}`

**Implementation**:
```python
# app/routers/wave_router.py
from fastapi import APIRouter, Depends
from app.services.wave_service import WaveService

router = APIRouter()

@router.post("/projects/{project_id}/waves")
async def create_wave(
    project_id: str,
    wave_data: CreateWaveRequest,
    service: WaveService = Depends()
):
    return await service.create_wave(project_id, wave_data)
```

**Deliverables**:
- Wave router with all endpoints
- Wave service layer with business logic
- Pydantic schemas for requests/responses
- Integration tests

---

### Task 5: Cloud Orchestration Service - Migration Execution (Days 6-7)

**Objective**: Implement migration execution workflows

**Key Workflows**:
1. Start Migration Wave → Create tasks → Invoke MCP tools
2. Execute Cutover → Invoke cutover MCP tools
3. Rollback Migration → Cleanup resources

**Implementation**:
```python
# app/services/wave_service.py
class WaveService:
    async def start_wave(
        self, 
        wave_id: str,
        options: StartWaveOptions
    ):
        # 1. Load wave and resources
        wave = await self.get_wave(wave_id)
        resources = await self.get_wave_resources(wave_id)
        
        # 2. Create migration tasks
        for resource in resources:
            task = await self.create_migration_task(
                resource_id=resource.id,
                task_type="replication"
            )
            
            # 3. Invoke appropriate MCP adapter
            if wave.target_csp == "aws":
                await self.aws_adapter.start_replication(
                    source_server_id=resource.source_identifier,
                    region=wave.metadata["target_region"]
                )
            elif wave.target_csp == "azure":
                await self.azure_adapter.replicate_vm(
                    vm_id=resource.source_identifier,
                    target_resource_group=wave.metadata["target_rg"]
                )
```

**Deliverables**:
- Wave execution service
- Task orchestration logic
- Error handling and retry logic
- WebSocket event publishing

---

### Task 6: IaC Governance Service - Database Setup (Day 8)

**Objective**: Create database schema for IaC templates, policies, validations

**Database Tables**:
1. `iac_templates`
2. `policy_definitions`
3. `validation_results`
4. `cost_estimates`

**Steps**:
1. Create service directory structure
2. Configure Alembic
3. Create migration: `001_create_iac_governance_tables.py`
4. Define SQLAlchemy models

**Deliverables**:
- Alembic configuration
- Database migration
- SQLAlchemy models for all 4 tables

---

### Task 7: IaC Governance Service - Terraform MCP Integration (Days 9-10)

**Objective**: Integrate Terraform MCP for template generation and validation

**Terraform MCP Adapter**:
```python
# app/adapters/terraform_mcp_adapter.py
class TerraformMCPAdapter:
    async def generate_module(
        self,
        resources: list[dict],
        provider: str
    ) -> str:
        return await self.mcp_client.execute_tool(
            server_name="Terraform MCP",
            tool_name="terraform_generate_module",
            arguments={
                "resources": resources,
                "provider": provider
            }
        )
    
    async def validate(self, template_content: str) -> dict:
        return await self.mcp_client.execute_tool(
            server_name="Terraform MCP",
            tool_name="terraform_validate",
            arguments={"template": template_content}
        )
```

**Deliverables**:
- Terraform MCP adapter
- Template generation service
- Validation service
- Unit tests

---

### Task 8: IaC Governance Service - OPA Policy Engine (Days 11-12)

**Objective**: Integrate Open Policy Agent for policy enforcement

**OPA Integration**:
```python
# app/services/opa_service.py
class OPAService:
    def __init__(self, opa_url: str = "http://localhost:8181"):
        self.opa_url = opa_url
    
    async def evaluate_policies(
        self,
        template_content: str,
        policy_ids: list[str]
    ) -> dict:
        # Load policies from database
        policies = await self.get_policies(policy_ids)
        
        # Evaluate via OPA
        result = await self._evaluate_opa(
            input_data={"template": template_content},
            policies=[p.opa_rego_code for p in policies]
        )
        
        return result
```

**Default Policies**:
1. CIS Benchmark - Encryption at Rest
2. CIS Benchmark - Network Security
3. Tagging Policy
4. Cost Policy (budget constraints)

**Deliverables**:
- OPA service integration
- Default policy definitions
- Policy evaluation logic
- Policy management API

---

### Task 9: IaC Governance Service - Cost Estimation (Days 13-14)

**Objective**: Implement multi-cloud cost estimation

**Cost Estimation Service**:
```python
# app/services/cost_estimation_service.py
class CostEstimationService:
    async def estimate_cost(
        self,
        template: IaCTemplate,
        region: str
    ) -> CostEstimate:
        # Parse IaC template
        resources = await self.parse_template(template)
        
        # Estimate cost per resource
        cost_breakdown = {}
        for resource in resources:
            if template.target_csp == "aws":
                cost = await self.aws_pricing_mcp.get_price(
                    service=resource.service,
                    instance_type=resource.type,
                    region=region
                )
            elif template.target_csp == "azure":
                cost = await self.azure_pricing_mcp.get_price(...)
            
            cost_breakdown[resource.id] = cost
        
        return CostEstimate(
            monthly_cost=sum(cost_breakdown.values()),
            breakdown=cost_breakdown
        )
```

**Deliverables**:
- Cost estimation service
- AWS Pricing MCP integration
- Azure Pricing API integration
- GCP Pricing API integration

---

### Task 10: FinOps Optimization Service - Database Setup (Day 15)

**Objective**: Create TimescaleDB hypertable and cost optimization tables

**Database Tables**:
1. `cost_data` (TimescaleDB hypertable)
2. `budgets`
3. `optimization_recommendations`
4. `anomaly_alerts`
5. `cost_allocation_rules`

**TimescaleDB Extension**:
```sql
-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Create cost_data table
CREATE TABLE cost_data (
    timestamp TIMESTAMP NOT NULL,
    project_id UUID NOT NULL,
    csp VARCHAR(20) NOT NULL,
    service_name VARCHAR(255) NOT NULL,
    cost DECIMAL(12, 4) NOT NULL,
    tags JSONB DEFAULT '{}'
);

-- Convert to hypertable
SELECT create_hypertable('cost_data', 'timestamp');

-- Create indexes
CREATE INDEX idx_cost_data_project ON cost_data(project_id, timestamp DESC);
CREATE INDEX idx_cost_data_tags ON cost_data USING GIN(tags);
```

**Deliverables**:
- Alembic migration with TimescaleDB setup
- SQLAlchemy models
- Hypertable configuration

---

### Task 11: FinOps Optimization Service - Cost Data Ingestion (Days 16-17)

**Objective**: Implement cost data collection from AWS, Azure, GCP

**AWS Cost Explorer MCP Integration**:
```python
# app/adapters/aws_cost_mcp_adapter.py
class AWSCostExplorerAdapter:
    async def get_cost_and_usage(
        self,
        start_date: str,
        end_date: str,
        granularity: str = "DAILY"
    ) -> dict:
        return await self.mcp_client.execute_tool(
            server_name="AWS Cost Explorer MCP",
            tool_name="get_cost_and_usage",
            arguments={
                "start_date": start_date,
                "end_date": end_date,
                "granularity": granularity,
                "metrics": ["UnblendedCost"],
                "group_by": [
                    {"Type": "DIMENSION", "Key": "SERVICE"},
                    {"Type": "TAG", "Key": "ProjectId"}
                ]
            }
        )
```

**Cost Data Ingestion Service**:
```python
# app/services/cost_ingestion_service.py
class CostIngestionService:
    async def ingest_costs(self, project_id: str):
        # Get costs from all CSPs
        aws_costs = await self.aws_adapter.get_cost_and_usage(...)
        azure_costs = await self.azure_adapter.get_costs(...)
        gcp_costs = await self.gcp_adapter.get_costs(...)
        
        # Normalize and store
        for cost_record in aws_costs + azure_costs + gcp_costs:
            await self.store_cost_record(project_id, cost_record)
```

**Deliverables**:
- AWS Cost Explorer MCP adapter
- Azure Cost Management MCP adapter
- GCP Billing API integration
- Cost data ingestion service
- Scheduled cost collection (daily)

---

### Task 12: FinOps Optimization Service - Anomaly Detection (Days 18-19)

**Objective**: Implement ML-based anomaly detection using Prophet

**Anomaly Detection Engine**:
```python
# app/services/anomaly_detection_service.py
from prophet import Prophet
import pandas as pd

class AnomalyDetectionService:
    async def detect_anomalies(
        self,
        project_id: str,
        lookback_days: int = 30
    ) -> list[AnomalyAlert]:
        # Fetch historical cost data
        cost_data = await self.get_cost_timeseries(
            project_id,
            lookback_days
        )
        
        # Prepare data for Prophet
        df = pd.DataFrame({
            'ds': [record.timestamp for record in cost_data],
            'y': [record.cost for record in cost_data]
        })
        
        # Train Prophet model
        model = Prophet(
            interval_width=0.95,
            changepoint_prior_scale=0.05
        )
        model.fit(df)
        
        # Generate forecast
        future = model.make_future_dataframe(periods=7)
        forecast = model.predict(future)
        
        # Detect anomalies (actual vs predicted)
        anomalies = []
        for idx, row in df.iterrows():
            predicted = forecast.loc[idx, 'yhat']
            actual = row['y']
            deviation = abs(actual - predicted) / predicted
            
            if deviation > 0.5:  # 50% deviation threshold
                anomalies.append(
                    AnomalyAlert(
                        project_id=project_id,
                        alert_type="spike",
                        detected_at=row['ds'],
                        baseline_cost=predicted,
                        actual_cost=actual,
                        deviation_percentage=deviation * 100
                    )
                )
        
        return anomalies
```

**Deliverables**:
- Prophet-based anomaly detection
- Anomaly alert creation
- Scheduled anomaly detection (daily)

---

### Task 13: FinOps Optimization Service - Right-Sizing Recommendations (Days 20-21)

**Objective**: Generate right-sizing recommendations

**Right-Sizing Engine**:
```python
# app/services/right_sizing_service.py
class RightSizingService:
    async def generate_recommendations(
        self,
        project_id: str
    ) -> list[OptimizationRecommendation]:
        # Get all running resources
        resources = await self.get_project_resources(project_id)
        
        recommendations = []
        for resource in resources:
            # Get utilization metrics (from CloudWatch, Azure Monitor, GCP Monitoring)
            metrics = await self.get_resource_metrics(resource)
            
            # Check if over-provisioned
            if metrics.cpu_avg < 20 and metrics.memory_avg < 30:
                # Find smaller instance type
                recommended = await self.find_smaller_instance(resource)
                
                savings = resource.monthly_cost - recommended.monthly_cost
                
                recommendations.append(
                    OptimizationRecommendation(
                        resource_id=resource.id,
                        recommendation_type="right-sizing",
                        current_configuration=resource.config,
                        recommended_configuration=recommended.config,
                        monthly_savings=savings,
                        confidence_score=0.9
                    )
                )
        
        return recommendations
```

**Deliverables**:
- Right-sizing recommendation engine
- Utilization metrics integration
- Instance type comparison logic

---

## Testing Strategy

### Unit Tests
- MCP adapters (mock MCP client responses)
- Service layer business logic
- Database models and queries
- Cost estimation algorithms
- Anomaly detection logic

### Integration Tests
- End-to-end wave creation → MCP tool execution
- IaC template generation → validation → cost estimation
- Cost data ingestion → anomaly detection → alert generation
- Database migrations

### Performance Tests
- Concurrent MCP tool executions (100+ concurrent)
- Large-scale cost data ingestion (1M+ records)
- Anomaly detection on 90-day datasets

---

## Database Migration Strategy

### Alembic Workflow

1. **Create Migration**:
```bash
cd services/cloud-orchestration-service
alembic revision -m "create migration waves tables"
```

2. **Edit Migration File**:
```python
# alembic/versions/xxx_create_migration_waves_tables.py
def upgrade():
    # Create tables
    op.create_table(...)

def downgrade():
    # Drop tables
    op.drop_table(...)
```

3. **Run Migration**:
```bash
alembic upgrade head
```

4. **Rollback (if needed)**:
```bash
alembic downgrade -1
```

### Migration Best Practices
- ✅ Always include `downgrade()` function
- ✅ Use `op.batch_alter_table()` for schema changes
- ✅ Test migrations on copy of production data
- ✅ Version control all migrations
- ✅ Never edit applied migrations

---

## Environment Setup

### Prerequisites
- Python 3.11+
- PostgreSQL 14+ with TimescaleDB extension
- Docker (for MCP servers)
- Node.js 18+ (for NPX MCP servers)

### MCP Server Installation

**AWS MCP Servers**:
```bash
# AWS Migration MCP (placeholder - need official server)
npx @awslabs/aws-migration-mcp

# AWS Cost Explorer MCP
npx @awslabs/aws-cost-explorer-mcp
```

**Terraform MCP**:
```bash
npx @hashicorp/terraform-mcp-server
```

**Azure MCP**:
```bash
npx @azure/azure-mcp-server
```

---

## Deliverables & Milestones

### Week 1 (Days 1-5)
- ✅ MCP models promoted to shared library
- ✅ Cloud Orchestration Service database setup
- ✅ Cloud Orchestration Service MCP adapters
- ✅ Wave management API

### Week 2 (Days 6-10)
- ⏳ Migration execution workflows
- ⏳ IaC Governance Service database setup
- ⏳ Terraform MCP integration
- ⏳ OPA policy engine integration

### Week 3 (Days 11-15)
- ⏳ Cost estimation service
- ⏳ FinOps Service database setup (TimescaleDB)
- ⏳ Cost data ingestion

### Week 4 (Days 16-21)
- ⏳ Anomaly detection
- ⏳ Right-sizing recommendations
- ⏳ Integration testing
- ⏳ Documentation updates

---

## Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| MCP servers not available for all CSPs | High | Use mock adapters for missing servers, implement later |
| TimescaleDB setup complexity | Medium | Use Docker Compose for local dev, detailed docs |
| Prophet model performance | Medium | Pre-compute forecasts, cache results |
| Alembic migration conflicts | Low | Use feature branches, coordinate migrations |

---

## Next Steps (Today - October 9, 2025)

1. ✅ Create this implementation plan
2. ⏳ Create shared MCP library (`common/mcp/`)
3. ⏳ Set up cloud-orchestration-service directory structure
4. ⏳ Configure Alembic for first service
5. ⏳ Create first database migration

---

**Document Version**: 1.0  
**Last Updated**: October 9, 2025  
**Author**: Platform Engineering Team
