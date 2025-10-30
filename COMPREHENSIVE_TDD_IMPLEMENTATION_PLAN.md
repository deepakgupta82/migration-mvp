# COMPREHENSIVE TDD IMPLEMENTATION PLAN
## Agentic Cloud Modernization Platform - Full Roadmap

**Document Version:** 2.0  
**Date:** January 2025  
**Status:** Approved for Implementation  
**Estimated Duration:** 34-48 weeks  
**Estimated Budget:** $520K-700K  

---

## EXECUTIVE SUMMARY

### Current State Assessment
- **Platform Maturity:** 60-65% TDD coverage
- **Architecture Status:** Over-decomposed (19 microservices vs 4 TDD boundaries)
- **Frontend Status:** 208 TypeScript files with hardcoded service URLs
- **Deployment Model:** Local Kubernetes/Docker only
- **Critical Gap:** No Temporal workflow engine (0% implementation)
- **Agent Frameworks:** CrewAI ✅ Operational, AutoGen ✅ Operational
- **Missing Components:** Temporal (0%), RDL (10%), MCP Gateway (embedded only), GCP deployment (0%)

### Strategic Imperatives
1. **Service Consolidation:** 19 → 10 services aligned to TDD boundaries
2. **Decommission Backend API Gateway:** Replace with GCP API Gateway or Kubernetes Ingress
3. **Frontend Refactoring:** Remove hardcoded URLs, implement API abstraction
4. **Temporal Integration:** Implement workflow engine for orchestration
5. **GCP Deployment:** Migrate to Cloud Run/GKE for MVP/POC delivery
6. **Multi-Cloud Abstraction:** Support AWS/Azure/On-prem for client deployments

---

## PHASE 0: FOUNDATION & CONSOLIDATION (8-10 weeks)
**Timeline:** Weeks 1-10  
**Budget:** $96K-120K  
**Team:** 3 Backend Engineers, 2 Frontend Engineers, 1 DevOps Engineer

### 0.1 Backend Service Consolidation (6-8 weeks)

#### Services to DECOMMISSION
1. **Backend Service (Port 8000)** - API Gateway pattern
   - **Why:** Not in TDD architecture
   - **Replacement:** GCP API Gateway (cloud) or Kubernetes Ingress (on-prem)
   - **Action:** Extract routing logic, migrate to infrastructure layer
   
2. **Project Service (Port 8002)** - Project metadata management
   - **Why:** Merge into Discovery & Ingestion Service
   - **Action:** Migrate project CRUD operations to document-service
   
3. **Stats Service (Port 8004)** - Platform statistics
   - **Why:** Move to Learning & Optimization Service
   - **Action:** Migrate stats aggregation to analytics-service
   
4. **Vector Service (Port 8005)** - Embedding operations
   - **Why:** Merge into Discovery & Ingestion Service
   - **Action:** Integrate vector operations into document-service
   
5. **Parts of Graph Service (Port 8006)** - Entity extraction only
   - **Why:** Merge entity extraction into Discovery & Ingestion
   - **Action:** Keep graph querying, move entity extraction to document-service
   
6. **LLM Service (Port 8007)** - LLM abstraction
   - **Why:** Merge into cross-cutting concerns
   - **Action:** Integrate into ai-agent-service as LLM provider factory
   
7. **Storage Service (Port 8010)** - MinIO wrapper
   - **Why:** Merge into Discovery & Ingestion Service
   - **Action:** Integrate MinIO client into document-service
   
8. **Knowledge Service (Port 8017)** - Knowledge base
   - **Why:** Merge into Learning & Optimization Service
   - **Action:** Migrate knowledge APIs to analytics-service
   
9. **Cloud Orchestration Service (Port 8020)** - Wave planning
   - **Why:** Merge into Generation & Execution Service
   - **Action:** Move to iac-governance-service
   
10. **FinOps Service (Port 8022)** - Cost optimization
    - **Why:** Merge into Learning & Optimization Service
    - **Action:** Integrate into analytics-service

#### Services to CONSOLIDATE into TDD Boundaries

**TDD Boundary 1: Discovery & Ingestion Service**
- **Core Service:** Document Service (Port 8003)
- **Absorb:** Project Service (8002), Vector Service (8005), Storage Service (8010), Entity Extraction from Graph Service (8006)
- **Responsibilities:**
  - Document upload/download (MinIO integration)
  - Multi-format conversion (MarkItDown, Unstructured.io, OCR)
  - JSONL generation and storage
  - Vector embedding generation (ChromaDB/Weaviate)
  - Entity extraction (spaCy, LLM-based)
  - Project metadata management (PostgreSQL)
  - Storage quota tracking
- **New Port:** 8003 (unchanged)
- **Database:** PostgreSQL (projects, documents, processing_status), MinIO (raw files, JSONL), ChromaDB/Weaviate (embeddings)

**TDD Boundary 2: Reasoning & Proposal Service**
- **Core Service:** AI Agent Service (Port 8008)
- **Absorb:** LLM Service (8007), WebSocket Service (8009)
- **Responsibilities:**
  - CrewAI workflow orchestration (15+ workflows)
  - AutoGen conversational agents (session management)
  - LLM provider abstraction (OpenAI, Anthropic, Ollama, Azure OpenAI)
  - MCP server registry (PostgreSQL-backed)
  - Assessment proposal generation
  - Real-time agent communication (WebSocket)
  - Reasoning strategy selection (single-agent, multi-agent, debate)
- **New Port:** 8008 (unchanged)
- **Database:** PostgreSQL (agent_runs, agent_events, llm_calls, mcp_servers), Redis (session cache)

**TDD Boundary 3: Generation & Execution Service**
- **Core Service:** IaC Governance Service (Port 8021)
- **Absorb:** Cloud Orchestration Service (8020)
- **Responsibilities:**
  - Terraform generation (multi-cloud: AWS, Azure, GCP)
  - IaC policy scanning (Checkov, tfsec, Terrascan)
  - Deployment wave planning
  - Resource provisioning orchestration
  - Terraform state management
  - Cloud provider API abstraction
  - Execution monitoring and rollback
- **New Port:** 8021 (unchanged)
- **Database:** PostgreSQL (iac_templates, policies, scans, waves), Cloud provider state backends

**TDD Boundary 4: Learning & Optimization Service**
- **Core Service:** Analytics Service (Port 8014)
- **Absorb:** Stats Service (8004), Knowledge Service (8017), FinOps Service (8022)
- **Responsibilities:**
  - Platform statistics aggregation
  - Cost analytics and optimization recommendations
  - Knowledge base management (lessons learned, patterns)
  - Performance metrics tracking
  - Usage analytics (LLM tokens, storage, compute)
  - Feedback collection and analysis
  - Continuous improvement suggestions
- **New Port:** 8014 (unchanged)
- **Database:** PostgreSQL (lessons, knowledge_articles, cost_data, metrics), InfluxDB/Prometheus (time-series metrics)

#### Services to KEEP (Cross-Cutting Concerns)
1. **Graph Service (Port 8006)** - Neo4j knowledge graph
   - **Scope:** Graph querying, relationship analysis, graph algorithms only
   - **Remove:** Entity extraction (move to document-service)
   
2. **Security Service (Port 8015)** - Authentication/Authorization
   - **Keep:** OAuth, RBAC, JWT, audit logging
   
3. **Collaboration Service (Port 8016)** - Notifications, real-time updates
   - **Keep:** User notifications, team collaboration features
   
4. **Service Registry (Port 8011)** - Service discovery
   - **Keep:** For on-prem Kubernetes deployments
   - **Note:** Not needed for GCP Cloud Run (uses Cloud Service Directory)

#### Consolidation Tasks
1. **Database Migration Scripts** (2 weeks)
   - Merge `project_service.projects` into `document_service.projects`
   - Merge `stats_service.metrics` into `analytics_service.platform_stats`
   - Migrate `cloud_orchestration.waves` into `iac_governance.deployment_waves`
   - Migrate `finops.cost_data` into `analytics.cost_analytics`
   - Create foreign key constraints across consolidated schemas

2. **Code Refactoring** (3-4 weeks)
   - Extract MinIO client from storage-service → document-service
   - Extract vector operations from vector-service → document-service
   - Extract entity extraction from graph-service → document-service
   - Extract LLM provider factory from llm-service → ai-agent-service
   - Extract WebSocket handlers from websocket-service → ai-agent-service
   - Extract wave planning from cloud-orchestration → iac-governance-service
   - Extract cost optimization from finops-service → analytics-service

3. **API Route Consolidation** (2 weeks)
   - Merge `/api/projects/*` from backend + project-service → document-service
   - Merge `/api/stats/*` from stats-service → analytics-service
   - Merge `/api/vectors/*` from vector-service → document-service
   - Merge `/api/llm/*` from llm-service → ai-agent-service
   - Merge `/api/cloud-orchestration/*` from cloud-orchestration → iac-governance-service
   - Merge `/api/finops/*` from finops-service → analytics-service

4. **Testing & Validation** (1 week)
   - Integration tests for consolidated services
   - API contract tests (ensure backward compatibility where needed)
   - Performance benchmarking (ensure no degradation)
   - Load testing (verify horizontal scalability)

### 0.2 Frontend API Abstraction Layer (6-8 weeks)

#### API Service Refactoring
1. **Centralized API Configuration** (1 week)
   ```typescript
   // frontend/src/config/api.config.ts
   export const API_CONFIG = {
     baseUrl: process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000',
     services: {
       discovery: '/api/discovery',      // Discovery & Ingestion (8003)
       reasoning: '/api/reasoning',      // Reasoning & Proposal (8008)
       generation: '/api/generation',    // Generation & Execution (8021)
       learning: '/api/learning',        // Learning & Optimization (8014)
       graph: '/api/graph',              // Knowledge Graph (8006)
       security: '/api/security',        // Security (8015)
       collaboration: '/api/collaboration', // Collaboration (8016)
     },
     timeout: 30000,
     retryConfig: { maxRetries: 3, backoff: 'exponential' },
   };
   ```

2. **Service Boundary Adapters** (2 weeks)
   - `DiscoveryService.ts` - Wraps document-service APIs
   - `ReasoningService.ts` - Wraps ai-agent-service APIs
   - `GenerationService.ts` - Wraps iac-governance-service APIs
   - `LearningService.ts` - Wraps analytics-service APIs
   - Each adapter handles:
     - Request/response transformation
     - Error handling and retries
     - Correlation ID injection
     - Response caching (where appropriate)

3. **Remove Hardcoded URLs** (2-3 weeks)
   - Scan all 208 .tsx files for `localhost:8000|8002|8003|...` patterns
   - Replace with centralized API service calls
   - Files to update:
     - `views/LessonsLearnedView.tsx` (4 hardcoded URLs)
     - `views/ProjectDetailView.tsx` (3 hardcoded URLs)
     - `views/ProjectExplorerView.tsx` (4 hardcoded URLs)
     - `views/SettingsView.tsx` (6+ hardcoded URLs)
     - `contexts/LLMConfigContext.tsx` (1 hardcoded URL)
     - `contexts/NotificationContext.tsx` (3 hardcoded URLs)
     - + ~40 more files

4. **Environment-Based Configuration** (1 week)
   ```bash
   # .env.development
   REACT_APP_API_BASE_URL=http://localhost:8000
   
   # .env.staging
   REACT_APP_API_BASE_URL=https://staging-api.agentic-cloud.com
   
   # .env.production
   REACT_APP_API_BASE_URL=https://api.agentic-cloud.com
   ```

5. **Testing & Validation** (1 week)
   - Component unit tests with mocked API services
   - Integration tests with test API endpoints
   - E2E tests for critical user workflows

### 0.3 Infrastructure Preparation (2 weeks)

1. **Docker Compose Restructuring**
   - Update `docker-compose.microservices.yml` to reflect 10 services (down from 19)
   - Remove decommissioned services
   - Add health checks for consolidated services
   - Configure inter-service networking

2. **Kubernetes Manifests (On-Prem)**
   - Create Helm charts for 10 services
   - Configure Ingress for API gateway pattern
   - Add HPA (Horizontal Pod Autoscaler) for scalability
   - Configure persistent volumes for PostgreSQL, Neo4j, MinIO

3. **CI/CD Pipeline Updates**
   - Update GitHub Actions workflows for new service structure
   - Create deployment pipelines for consolidated services
   - Add smoke tests post-deployment

---

## PHASE 1: TEMPORAL INTEGRATION (8-10 weeks)
**Timeline:** Weeks 11-20  
**Budget:** $128K-160K  
**Team:** 2 Backend Engineers, 1 Frontend Engineer, 1 DevOps Engineer

### 1.1 Temporal Workflow Engine Setup (2 weeks)

#### Infrastructure Setup
1. **Temporal Server Deployment**
   - **Development:** Docker Compose with Temporal Server + PostgreSQL
   - **GCP Production:** Temporal Cloud (managed) or self-hosted on GKE
   - Components: Frontend (UI), Server, Worker, Visibility (ElasticSearch)

2. **Temporal Client SDK Integration**
   - Install `temporalio` Python SDK in all workflow-enabled services
   - Configure Temporal client connection (namespace, server URL)
   - Set up worker processes for each service

3. **Namespace Design**
   ```
   namespaces:
     - dev.agentic-cloud
     - staging.agentic-cloud
     - prod.agentic-cloud
     - tenant-{tenant_id}.prod (for multi-tenancy)
   ```

### 1.2 Discovery & Ingestion Workflows (2 weeks)

**Workflow:** `DocumentIngestionWorkflow`
```python
# Workflow Steps:
1. upload_document_activity (MinIO)
2. detect_format_activity (file type detection)
3. convert_to_markdown_activity (MarkItDown/Unstructured.io)
4. extract_entities_activity (spaCy/LLM)
5. generate_embeddings_activity (ChromaDB/Weaviate)
6. store_jsonl_activity (MinIO)
7. update_processing_status_activity (PostgreSQL)

# Workflow Features:
- Retry policies: exponential backoff (max 5 retries)
- Timeouts: 5 minutes per activity, 30 minutes total workflow
- Human-in-the-loop: Manual approval for ambiguous formats
- Rollback: Delete partial artifacts on failure
```

**Workflow:** `BatchDocumentProcessingWorkflow`
- Parent workflow that spawns `DocumentIngestionWorkflow` for each document
- Parallel execution with concurrency limits (max 10 concurrent)
- Progress tracking and reporting

### 1.3 Reasoning & Proposal Workflows (2 weeks)

**Workflow:** `AssessmentWorkflow`
```python
# Workflow Steps:
1. load_project_context_activity (PostgreSQL + Graph + Vector)
2. select_reasoning_strategy_activity (single-agent, multi-agent, debate)
3. execute_crew_workflow_activity (CrewAI orchestration)
   - OR execute_autogen_conversation_activity (AutoGen multi-agent)
4. generate_proposal_activity (assessment report + recommendations)
5. store_proposal_activity (PostgreSQL)
6. notify_user_activity (Collaboration service)

# Workflow Features:
- LLM call tracking (all calls logged to PostgreSQL)
- Strategy selection based on project complexity
- Multi-agent debate for high-risk decisions
- Proposal versioning
```

**Workflow:** `ProposalApprovalWorkflow`
```python
# Workflow Steps:
1. wait_for_approval_signal (human-in-the-loop)
2. if_approved:
     - trigger_generation_workflow
   else:
     - request_revision_activity
     - loop back to AssessmentWorkflow
```

### 1.4 Generation & Execution Workflows (2 weeks)

**Workflow:** `IaCGenerationWorkflow`
```python
# Workflow Steps:
1. load_approved_proposal_activity
2. select_cloud_provider_activity (AWS/Azure/GCP)
3. generate_terraform_activity (LLM-based generation)
4. validate_terraform_activity (terraform validate)
5. scan_policies_activity (Checkov, tfsec, Terrascan)
6. store_terraform_activity (version control)
7. wait_for_execution_approval_signal

# Workflow Features:
- Multi-cloud support (AWS, Azure, GCP)
- Policy violations halt workflow
- Terraform code versioning
```

**Workflow:** `TerraformExecutionWorkflow`
```python
# Workflow Steps:
1. terraform_init_activity
2. terraform_plan_activity
3. wait_for_plan_approval_signal (human review)
4. terraform_apply_activity (with progress streaming)
5. monitor_deployment_activity (check resource health)
6. store_state_activity (Terraform state backend)
7. on_failure:
     - terraform_destroy_activity (rollback)

# Workflow Features:
- Real-time progress updates (WebSocket)
- Automatic rollback on failure
- State locking to prevent concurrent modifications
```

**Workflow:** `WaveExecutionWorkflow`
- Parent workflow for multi-wave migrations
- Executes `TerraformExecutionWorkflow` for each wave sequentially
- Wave dependencies (wave 2 waits for wave 1 completion)

### 1.5 Learning & Optimization Workflows (1 week)

**Workflow:** `LessonExtractionWorkflow`
```python
# Workflow Steps:
1. aggregate_project_data_activity (logs, metrics, outcomes)
2. extract_patterns_activity (LLM-based pattern detection)
3. generate_lesson_activity (structured lesson learned)
4. store_knowledge_activity (PostgreSQL knowledge_articles table)
5. update_recommendations_activity (improve future proposals)
```

**Workflow:** `CostOptimizationWorkflow`
```python
# Workflow Steps:
1. fetch_cloud_cost_data_activity (GCP Billing API)
2. analyze_utilization_activity (identify idle/oversized resources)
3. generate_recommendations_activity (LLM-based optimization suggestions)
4. create_optimization_proposal_activity
5. wait_for_approval_signal
6. execute_optimization_activity (resize/terminate resources)
```

### 1.6 Workflow Monitoring UI (1-2 weeks)

**Frontend Components:**
1. **WorkflowListView.tsx** - List all running/completed workflows
2. **WorkflowDetailView.tsx** - Workflow execution timeline, activity status
3. **WorkflowApprovalModal.tsx** - Approve/reject proposals
4. **WorkflowHistoryView.tsx** - Historical workflow runs with filters

**API Endpoints (ai-agent-service):**
- `GET /api/workflows` - List workflows with filters
- `GET /api/workflows/{workflow_id}` - Workflow details
- `POST /api/workflows/{workflow_id}/signal` - Send signal (approve/reject)
- `GET /api/workflows/{workflow_id}/history` - Workflow execution history

---

## PHASE 2: MCP GATEWAY & RDL (6-8 weeks)
**Timeline:** Weeks 21-28  
**Budget:** $96K-128K  
**Team:** 2 Backend Engineers, 1 DevOps Engineer

### 2.1 Standalone MCP Gateway Service (3 weeks)

#### Extract MCP from AI Agent Service
1. **Create New Service: `mcp-gateway-service` (Port 8030)**
   - FastAPI application
   - MCP server registry (PostgreSQL)
   - MCP protocol implementation (SSE, stdio, HTTP)
   - Tool invocation router

2. **MCP Server Registry**
   ```python
   # Database Schema:
   mcp_servers:
     - id (UUID)
     - name (string)
     - url (string)
     - protocol (sse | stdio | http)
     - tools (JSONB) - list of available tools
     - status (active | inactive | error)
     - health_check_url (string)
     - last_health_check (timestamp)
     - created_at, updated_at
   
   mcp_tool_invocations:
     - id (UUID)
     - server_id (FK to mcp_servers)
     - tool_name (string)
     - input_params (JSONB)
     - output (JSONB)
     - status (success | failure)
     - duration_ms (integer)
     - correlation_id (string)
     - created_at
   ```

3. **MCP Server Connectors**
   - AWS MCP Server (EC2, S3, Lambda, RDS, IAM)
   - Azure MCP Server (VMs, Storage, Functions, SQL)
   - GCP MCP Server (Compute, Storage, Cloud Run, BigQuery)
   - Filesystem MCP Server (for local file operations)

4. **API Endpoints**
   - `GET /mcp/servers` - List registered MCP servers
   - `POST /mcp/servers` - Register new MCP server
   - `DELETE /mcp/servers/{server_id}` - Unregister server
   - `POST /mcp/servers/{server_id}/tools/{tool_name}/invoke` - Invoke tool
   - `GET /mcp/servers/{server_id}/health` - Health check

### 2.2 Resource Description Language (RDL) Implementation (3-4 weeks)

#### RDL Schema Design
```yaml
# Example RDL Schema for Cloud Resources
resource_types:
  - ec2_instance:
      properties:
        instance_type: { type: string, required: true }
        ami_id: { type: string, required: true }
        vpc_id: { type: string, required: false }
        subnet_id: { type: string, required: false }
        security_groups: { type: array, items: { type: string } }
        tags: { type: object }
      constraints:
        - instance_type must be in [t2.micro, t2.small, t2.medium, ...]
        - if vpc_id is set, subnet_id must be set
      cost_model:
        hourly_rate: 0.0116 (for t2.micro)
        
  - s3_bucket:
      properties:
        bucket_name: { type: string, required: true, unique: true }
        region: { type: string, required: true }
        versioning_enabled: { type: boolean, default: false }
        encryption: { type: string, enum: [AES256, aws:kms] }
      constraints:
        - bucket_name must match regex ^[a-z0-9\-]+$
        - bucket_name length 3-63 characters
      cost_model:
        storage_gb_month: 0.023
```

#### RDL Parser & Validator
1. **RDL Parser** - Parse RDL YAML files into internal representation
2. **RDL Validator** - Validate resource definitions against schema
3. **RDL Resolver** - Resolve resource dependencies and constraints
4. **RDL Cost Estimator** - Calculate estimated costs based on RDL definitions

#### RDL Integration with IaC Generation
```python
# Workflow: AssessmentWorkflow → RDL Generation → Terraform Generation

# Step 1: Generate RDL from assessment
rdl_document = generate_rdl_from_assessment(assessment_data)

# Step 2: Validate RDL
validation_result = validate_rdl(rdl_document)

# Step 3: Estimate costs
cost_estimate = estimate_costs(rdl_document)

# Step 4: Generate Terraform from RDL
terraform_code = generate_terraform_from_rdl(rdl_document, cloud_provider='aws')
```

#### RDL Storage & Versioning
- Store RDL documents in PostgreSQL (JSONB column)
- Version control using Git (commit RDL changes)
- Track RDL → Terraform → Deployed Resources lineage

### 2.3 Testing & Validation (1 week)
- MCP server integration tests (AWS, Azure, GCP)
- RDL parser unit tests
- RDL → Terraform generation tests
- End-to-end workflow tests (Assessment → RDL → Terraform → Deploy)

---

## PHASE 3: FRONTEND TDD ALIGNMENT (10-12 weeks)
**Timeline:** Weeks 29-40  
**Budget:** $128K-160K  
**Team:** 2 Frontend Engineers, 1 UX Designer

### 3.1 Core Workflow UI (4-5 weeks)

#### Assessment Wizard (2 weeks)
**Component:** `AssessmentWizardView.tsx`
- **Step 1:** Project selection & LLM configuration
- **Step 2:** Document upload & ingestion status
- **Step 3:** Reasoning strategy selection (single-agent, multi-agent, debate)
- **Step 4:** Agent configuration (select CrewAI workflow or AutoGen agents)
- **Step 5:** Launch assessment (trigger `AssessmentWorkflow`)
- **Real-time Progress:** WebSocket connection to show workflow progress

#### Proposal Review UI (2 weeks)
**Component:** `ProposalReviewView.tsx`
- **Proposal Viewer:** Markdown rendering with syntax highlighting
- **Diff Viewer:** Show changes from previous versions
- **Approval Workflow:** Approve/Reject buttons (send Temporal signal)
- **Comments:** Add feedback/comments to proposals
- **Revision History:** Track all proposal versions

#### Workflow Monitor (1 week)
**Component:** `WorkflowMonitorView.tsx`
- **Workflow List:** Table with filters (status, type, project)
- **Workflow Timeline:** Gantt chart showing activity execution
- **Activity Status:** Color-coded status indicators (running, completed, failed)
- **Workflow Actions:** Pause, resume, cancel, retry buttons
- **Integration:** Temporal Web UI iframe embed (optional)

### 3.2 Execution Dashboard (3-4 weeks)

#### Terraform Execution UI (2 weeks)
**Component:** `TerraformExecutionView.tsx`
- **Plan Viewer:** Display `terraform plan` output with syntax highlighting
- **Apply Progress:** Real-time `terraform apply` output streaming
- **Resource Status:** Table showing resource creation status
- **Approval Gate:** Approve/reject Terraform plan before apply
- **Rollback Controls:** Emergency rollback button

#### Deployment Wave UI (1-2 weeks)
**Component:** `DeploymentWaveView.tsx`
- **Wave Planner:** Drag-and-drop interface for wave grouping
- **Wave Dependencies:** Visual graph showing wave dependencies
- **Wave Execution:** Sequential execution with status indicators
- **Wave Rollback:** Rollback entire wave or individual resources

### 3.3 GCP Deployment UI (2-3 weeks)

#### Environment Selector (1 week)
**Component:** `EnvironmentSelector.tsx`
- Dropdown: Dev / Staging / Production
- Auto-switch API base URL based on environment
- Environment-specific feature flags

#### Multi-Tenant Workspace UI (1 week)
**Component:** `WorkspaceSwitcher.tsx`
- Workspace dropdown (for users with access to multiple workspaces)
- Workspace settings (GCP project ID, region, billing account)
- Tenant admin panel (create/delete workspaces, assign users)

#### Cloud Provider Configuration (1 week)
**Component:** `CloudProviderConfigView.tsx`
- **GCP Config:** Project ID, region, service account credentials
- **AWS Config:** Account ID, region, IAM role ARN
- **Azure Config:** Subscription ID, resource group, service principal
- **On-Prem Config:** Kubernetes cluster URL, kubeconfig

### 3.4 Missing Features (2-3 weeks)

#### Feedback Collection (1 week)
**Component:** `FeedbackModal.tsx`
- Star rating (1-5)
- Feedback categories (accuracy, performance, usability)
- Free-text feedback
- Submit feedback to `learning-service` (analytics-service)

#### Audit Log Viewer (1 week)
**Component:** `AuditLogView.tsx`
- Table showing all user actions (login, project creation, assessment, deployment)
- Filters: user, action type, date range
- Export to CSV

#### Enhanced Role Management (1 week)
**Component:** `RoleManagementView.tsx`
- RBAC roles: Admin, Engineer, Viewer
- Permission matrix (read, write, approve, deploy)
- Assign roles to users per workspace

---

## PHASE 4: GCP DEPLOYMENT & INFRA (6-8 weeks)
**Timeline:** Weeks 41-48  
**Budget:** $96K-128K  
**Team:** 2 DevOps Engineers, 1 Backend Engineer, 1 Frontend Engineer

### 4.1 GCP Infrastructure Setup (3 weeks)

#### GCP Services Selection
1. **Compute:**
   - **Cloud Run:** Stateless services (Discovery, Reasoning, Generation, Learning)
   - **GKE (Google Kubernetes Engine):** Stateful services (PostgreSQL, Neo4j, Redis, MinIO)
   - **Cloud Functions:** Serverless event handlers (document triggers)

2. **Data Storage:**
   - **Cloud SQL (PostgreSQL):** Primary relational database
   - **Cloud Storage:** Object storage (replace MinIO for production)
   - **Memorystore (Redis):** Session cache, rate limiting
   - **Neo4j Aura (Managed):** Knowledge graph (or self-hosted on GKE)

3. **Messaging & Events:**
   - **Pub/Sub:** Asynchronous message queue (document processing triggers)
   - **Cloud Tasks:** Task scheduling and queueing

4. **Observability:**
   - **Cloud Logging:** Centralized logging (replace ELK stack)
   - **Cloud Monitoring:** Metrics and alerting (replace Prometheus/Grafana)
   - **Cloud Trace:** Distributed tracing
   - **Cloud Profiler:** Performance profiling

5. **Networking:**
   - **Cloud Load Balancer:** HTTP(S) load balancing
   - **Cloud CDN:** Frontend asset caching
   - **VPC:** Private networking for services
   - **Cloud NAT:** Outbound internet for Cloud Run

6. **Security:**
   - **Secret Manager:** Store API keys, database credentials
   - **Identity-Aware Proxy (IAP):** OAuth-based access control
   - **Cloud Armor:** DDoS protection, WAF

#### Terraform for GCP Infrastructure
```hcl
# terraform/gcp/main.tf
module "vpc" {
  source = "./modules/vpc"
  project_id = var.project_id
  region = var.region
}

module "cloud_sql" {
  source = "./modules/cloud_sql"
  instance_name = "agentic-cloud-postgres"
  database_version = "POSTGRES_15"
  tier = "db-g1-small"  # Dev: db-g1-small, Prod: db-custom-4-16384
}

module "cloud_run_services" {
  source = "./modules/cloud_run"
  for_each = {
    discovery = { image = "gcr.io/${var.project_id}/discovery-service", port = 8003 }
    reasoning = { image = "gcr.io/${var.project_id}/reasoning-service", port = 8008 }
    generation = { image = "gcr.io/${var.project_id}/generation-service", port = 8021 }
    learning = { image = "gcr.io/${var.project_id}/learning-service", port = 8014 }
  }
  service_name = each.key
  image = each.value.image
  port = each.value.port
  vpc_connector = module.vpc.connector_id
  cloudsql_connection = module.cloud_sql.connection_name
}

module "gke_cluster" {
  source = "./modules/gke"
  cluster_name = "agentic-cloud-gke"
  node_count = 3
  machine_type = "e2-standard-4"
  # For stateful services: Neo4j, Redis, MinIO (dev only)
}

module "api_gateway" {
  source = "./modules/api_gateway"
  api_config_file = "./api_gateway_config.yaml"
  services = {
    discovery = module.cloud_run_services["discovery"].url
    reasoning = module.cloud_run_services["reasoning"].url
    generation = module.cloud_run_services["generation"].url
    learning = module.cloud_run_services["learning"].url
  }
}
```

### 4.2 CI/CD Pipeline for GCP (2 weeks)

#### GitHub Actions Workflow
```yaml
# .github/workflows/deploy-gcp.yml
name: Deploy to GCP

on:
  push:
    branches: [main, staging, develop]

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Authenticate to Google Cloud
        uses: google-github-actions/auth@v1
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}
      
      - name: Set up Cloud SDK
        uses: google-github-actions/setup-gcloud@v1
      
      - name: Build Docker Images
        run: |
          docker build -t gcr.io/${{ secrets.GCP_PROJECT_ID }}/discovery-service:${{ github.sha }} ./services/document-service
          docker build -t gcr.io/${{ secrets.GCP_PROJECT_ID }}/reasoning-service:${{ github.sha }} ./services/ai-agent-service
          docker build -t gcr.io/${{ secrets.GCP_PROJECT_ID }}/generation-service:${{ github.sha }} ./services/iac-governance-service
          docker build -t gcr.io/${{ secrets.GCP_PROJECT_ID }}/learning-service:${{ github.sha }} ./services/analytics-service
      
      - name: Push to Container Registry
        run: |
          docker push gcr.io/${{ secrets.GCP_PROJECT_ID }}/discovery-service:${{ github.sha }}
          docker push gcr.io/${{ secrets.GCP_PROJECT_ID }}/reasoning-service:${{ github.sha }}
          docker push gcr.io/${{ secrets.GCP_PROJECT_ID }}/generation-service:${{ github.sha }}
          docker push gcr.io/${{ secrets.GCP_PROJECT_ID }}/learning-service:${{ github.sha }}
      
      - name: Deploy to Cloud Run
        run: |
          gcloud run deploy discovery-service --image gcr.io/${{ secrets.GCP_PROJECT_ID }}/discovery-service:${{ github.sha }} --region us-central1
          gcloud run deploy reasoning-service --image gcr.io/${{ secrets.GCP_PROJECT_ID }}/reasoning-service:${{ github.sha }} --region us-central1
          gcloud run deploy generation-service --image gcr.io/${{ secrets.GCP_PROJECT_ID }}/generation-service:${{ github.sha }} --region us-central1
          gcloud run deploy learning-service --image gcr.io/${{ secrets.GCP_PROJECT_ID }}/learning-service:${{ github.sha }} --region us-central1
      
      - name: Run Smoke Tests
        run: |
          curl -f https://discovery-service-xyz-uc.a.run.app/health || exit 1
          curl -f https://reasoning-service-xyz-uc.a.run.app/health || exit 1
```

### 4.3 Multi-Cloud Abstraction Layer (2 weeks)

#### Cloud Provider Adapter Pattern
```python
# services/iac-governance-service/app/cloud_adapters/base.py
from abc import ABC, abstractmethod

class CloudProviderAdapter(ABC):
    @abstractmethod
    def create_vm_instance(self, specs: dict) -> dict:
        pass
    
    @abstractmethod
    def create_storage_bucket(self, name: str, region: str) -> dict:
        pass
    
    @abstractmethod
    def get_cost_data(self, start_date: str, end_date: str) -> dict:
        pass

# services/iac-governance-service/app/cloud_adapters/gcp_adapter.py
class GCPAdapter(CloudProviderAdapter):
    def __init__(self, project_id: str, credentials_path: str):
        self.compute = googleapiclient.discovery.build('compute', 'v1')
        self.storage = google.cloud.storage.Client()
        self.billing = googleapiclient.discovery.build('cloudbilling', 'v1')
    
    def create_vm_instance(self, specs: dict) -> dict:
        operation = self.compute.instances().insert(
            project=self.project_id,
            zone=specs['zone'],
            body={
                'name': specs['name'],
                'machineType': f"zones/{specs['zone']}/machineTypes/{specs['machine_type']}",
                ...
            }
        ).execute()
        return {'instance_id': operation['targetId'], 'status': 'creating'}
    
    def create_storage_bucket(self, name: str, region: str) -> dict:
        bucket = self.storage.bucket(name)
        bucket.location = region
        bucket.create()
        return {'bucket_name': name, 'url': f'gs://{name}'}
    
    def get_cost_data(self, start_date: str, end_date: str) -> dict:
        # Use BigQuery billing export or Cloud Billing API
        pass

# Similar adapters for AWS, Azure, On-Prem
```

#### Adapter Factory
```python
# services/iac-governance-service/app/cloud_adapters/factory.py
class CloudAdapterFactory:
    @staticmethod
    def get_adapter(provider: str, config: dict) -> CloudProviderAdapter:
        if provider == 'gcp':
            return GCPAdapter(config['project_id'], config['credentials_path'])
        elif provider == 'aws':
            return AWSAdapter(config['access_key_id'], config['secret_access_key'], config['region'])
        elif provider == 'azure':
            return AzureAdapter(config['subscription_id'], config['client_id'], config['client_secret'])
        elif provider == 'onprem':
            return OnPremAdapter(config['kubernetes_url'], config['kubeconfig_path'])
        else:
            raise ValueError(f"Unsupported cloud provider: {provider}")
```

### 4.4 Testing & Launch (1-2 weeks)

1. **Staging Deployment**
   - Deploy all services to GCP staging environment
   - Run integration tests
   - Load testing (simulate 100 concurrent users)
   - Security scanning (OWASP ZAP, container scanning)

2. **Production Deployment**
   - Blue-green deployment for zero-downtime
   - Canary deployment (10% → 50% → 100% traffic)
   - Monitor error rates, latency, resource utilization
   - Rollback plan if issues detected

3. **Launch Checklist**
   - [ ] All services healthy in production
   - [ ] Frontend deployed to Cloud CDN
   - [ ] DNS configured (api.agentic-cloud.com, app.agentic-cloud.com)
   - [ ] SSL certificates configured (Cloud Load Balancer)
   - [ ] Monitoring dashboards configured (Cloud Monitoring)
   - [ ] Alerting rules configured (PagerDuty/Slack integration)
   - [ ] Documentation updated (deployment guide, troubleshooting)
   - [ ] User training materials ready

---

## PHASE 5: ADVANCED FEATURES (OPTIONAL) (8-10 weeks)
**Timeline:** Weeks 49-58  
**Budget:** $64K-80K  
**Team:** 1 Backend Engineer, 1 Frontend Engineer

### 5.1 Semantic Kernel Integration (3 weeks)
- Replace some LLM calls with Semantic Kernel for better prompt engineering
- Integrate SK planners for complex reasoning tasks
- SK plugins for tool invocations (alternative to MCP)

### 5.2 Advanced Graph Analytics (2 weeks)
- Implement graph algorithms (PageRank, community detection, shortest path)
- Add graph-based recommendations (similar projects, common patterns)
- Enhanced entity relationship visualization

### 5.3 Multi-Language Support (2 weeks)
- Internationalization (i18n) for frontend (English, Spanish, German, Japanese)
- LLM prompts in multiple languages
- Document processing for non-English documents

### 5.4 Advanced Cost Optimization (1-2 weeks)
- FinOps recommendations powered by LLM
- Automated resource rightsizing
- Reserved instance/committed use discount recommendations

---

## IMPLEMENTATION TIMELINE SUMMARY

| Phase | Duration | Start Week | End Week | Budget | Team Size |
|-------|----------|------------|----------|--------|-----------|
| **Phase 0:** Foundation & Consolidation | 8-10 weeks | 1 | 10 | $96K-120K | 6 engineers |
| **Phase 1:** Temporal Integration | 8-10 weeks | 11 | 20 | $128K-160K | 4 engineers |
| **Phase 2:** MCP Gateway & RDL | 6-8 weeks | 21 | 28 | $96K-128K | 3 engineers |
| **Phase 3:** Frontend TDD Alignment | 10-12 weeks | 29 | 40 | $128K-160K | 3 engineers |
| **Phase 4:** GCP Deployment & Infra | 6-8 weeks | 41 | 48 | $96K-128K | 4 engineers |
| **Phase 5 (Optional):** Advanced Features | 8-10 weeks | 49 | 58 | $64K-80K | 2 engineers |
| **TOTAL (Core)** | **38-48 weeks** | **1** | **48** | **$544K-696K** | **4-6 avg** |
| **TOTAL (with Phase 5)** | **46-58 weeks** | **1** | **58** | **$608K-776K** | **4-6 avg** |

---

## BUDGET BREAKDOWN

### Development Costs (Core Phases 0-4)
| Role | Avg Rate | Weeks | Total Cost |
|------|----------|-------|------------|
| Senior Backend Engineer | $4,000/week | 30-38 weeks | $120K-152K |
| Mid-Level Backend Engineer | $3,000/week | 30-38 weeks | $90K-114K |
| Senior Frontend Engineer | $3,500/week | 20-26 weeks | $70K-91K |
| Mid-Level Frontend Engineer | $2,500/week | 20-26 weeks | $50K-65K |
| DevOps Engineer | $3,500/week | 18-24 weeks | $63K-84K |
| UX Designer (Part-time) | $2,000/week | 10-12 weeks | $20K-24K |
| **Subtotal** | | | **$413K-530K** |

### Infrastructure Costs (GCP - Annual)
| Service | Estimated Monthly | Annual |
|---------|-------------------|--------|
| Cloud Run (4 services) | $200 | $2,400 |
| GKE (3-node cluster) | $500 | $6,000 |
| Cloud SQL (PostgreSQL) | $300 | $3,600 |
| Cloud Storage | $100 | $1,200 |
| Memorystore (Redis) | $150 | $1,800 |
| Neo4j Aura | $400 | $4,800 |
| Load Balancer + CDN | $100 | $1,200 |
| Cloud Logging + Monitoring | $150 | $1,800 |
| Temporal Cloud | $500 | $6,000 |
| **Subtotal** | **$2,400** | **$28,800** |

### Third-Party Licenses (Annual)
| Service | Estimated Annual |
|---------|------------------|
| LLM API Credits (OpenAI, Anthropic) | $12,000 |
| GitHub Enterprise | $2,100 |
| JetBrains IDEs | $1,500 |
| **Subtotal** | **$15,600** |

### TOTAL PROJECT COST
- **Development:** $413K-530K
- **Infrastructure (Year 1):** $28,800
- **Licenses (Year 1):** $15,600
- **Contingency (10%):** $45K-57K
- **GRAND TOTAL:** **$502K-631K** (Core Phases 0-4)
- **With Optional Phase 5:** **$566K-711K**

---

## RISK ASSESSMENT & MITIGATION

### High-Risk Items
1. **Temporal Learning Curve**
   - **Risk:** Team unfamiliar with Temporal
   - **Mitigation:** 2-week Temporal training bootcamp, hire Temporal consultant
   - **Probability:** Medium | **Impact:** High

2. **Service Consolidation Complexity**
   - **Risk:** Data migration errors, service downtime during consolidation
   - **Mitigation:** Comprehensive testing, gradual rollout, rollback plan
   - **Probability:** Medium | **Impact:** High

3. **GCP Cost Overruns**
   - **Risk:** Actual GCP costs exceed estimates
   - **Mitigation:** Monthly cost reviews, resource quotas, auto-scaling limits
   - **Probability:** Medium | **Impact:** Medium

4. **Multi-Cloud Abstraction Complexity**
   - **Risk:** AWS/Azure adapters don't cover all edge cases
   - **Mitigation:** Start with GCP, add AWS/Azure incrementally
   - **Probability:** Low | **Impact:** Medium

### Medium-Risk Items
1. **Frontend Refactoring Scope Creep**
   - **Risk:** 208 files take longer than estimated
   - **Mitigation:** Automated refactoring tools, parallel work streams
   - **Probability:** Medium | **Impact:** Low

2. **LLM API Rate Limits**
   - **Risk:** Exceed LLM provider rate limits during peak usage
   - **Mitigation:** Request quota increases, implement request queuing, use local models (Ollama) as fallback
   - **Probability:** Low | **Impact:** Medium

---

## SUCCESS METRICS

### Technical KPIs
- **Service Consolidation:** 19 → 10 services (50% reduction) ✅
- **API Response Time:** P95 < 500ms (vs current ~1200ms)
- **Workflow Automation:** 80%+ operations automated via Temporal
- **Frontend Load Time:** < 2 seconds (vs current ~4 seconds)
- **GCP Cost per User:** < $10/month (target for SaaS pricing)

### Business KPIs
- **Time to Assessment:** Reduce from 4 hours → 30 minutes
- **Deployment Success Rate:** 95%+ (Terraform apply success)
- **User Adoption:** 50+ pilot users in first 3 months
- **Cost Savings for Clients:** Average 40% cloud cost reduction
- **Platform Uptime:** 99.5% SLA

### User Experience KPIs
- **User Satisfaction Score:** 4.5+ / 5.0
- **Net Promoter Score (NPS):** 50+
- **Feature Adoption Rate:** 70%+ users use workflow features
- **Support Ticket Volume:** < 5 tickets/week

---

## NEXT STEPS

1. **Approve This Plan** - Review and sign off on roadmap, timeline, budget
2. **Form Core Team** - Hire/assign 6 engineers (3 backend, 2 frontend, 1 DevOps)
3. **Kickoff Phase 0** - Begin service consolidation (Week 1)
4. **Set Up GCP Account** - Create GCP project, set up billing, IAM roles
5. **Weekly Standups** - Establish agile cadence (daily standups, weekly sprint planning)
6. **Milestone Reviews** - Bi-weekly demos to stakeholders

---

## APPENDIX A: SERVICE CONSOLIDATION MAPPING

### Discovery & Ingestion Service (Port 8003)
**Absorbs:**
- Project Service (8002) → Project CRUD, metadata
- Vector Service (8005) → Embedding generation, ChromaDB/Weaviate
- Storage Service (8010) → MinIO client, file upload/download
- Graph Service (8006) → Entity extraction only

**Final Responsibilities:**
- Document upload (MinIO)
- Multi-format conversion (MarkItDown, Unstructured.io, OCR)
- Entity extraction (spaCy, LLM)
- Embedding generation (ChromaDB/Weaviate)
- JSONL generation
- Project metadata management

### Reasoning & Proposal Service (Port 8008)
**Absorbs:**
- LLM Service (8007) → LLM provider factory
- WebSocket Service (8009) → Real-time agent communication

**Final Responsibilities:**
- CrewAI workflow orchestration
- AutoGen conversational agents
- LLM provider abstraction
- Assessment proposal generation
- MCP tool invocation (via MCP Gateway)
- Real-time progress updates (WebSocket)

### Generation & Execution Service (Port 8021)
**Absorbs:**
- Cloud Orchestration Service (8020) → Wave planning

**Final Responsibilities:**
- Terraform/IaC generation
- Policy scanning (Checkov, tfsec, Terrascan)
- Deployment wave planning
- Terraform execution
- Cloud provider API abstraction
- Rollback/retry logic

### Learning & Optimization Service (Port 8014)
**Absorbs:**
- Stats Service (8004) → Platform statistics
- Knowledge Service (8017) → Knowledge base
- FinOps Service (8022) → Cost optimization

**Final Responsibilities:**
- Platform statistics aggregation
- Cost analytics
- Knowledge base management
- Lessons learned extraction
- Performance metrics
- Usage analytics

---

## APPENDIX B: FRONTEND FILE AUDIT

**Files Requiring URL Refactoring:** 42 files
- `views/LessonsLearnedView.tsx` - 4 hardcoded URLs
- `views/ProjectDetailView.tsx` - 3 hardcoded URLs
- `views/ProjectExplorerView.tsx` - 4 hardcoded URLs
- `views/ProjectOverviewPage.tsx` - 5 hardcoded URLs
- `views/SettingsView.tsx` - 6 hardcoded URLs
- `views/CloudMigrationView.tsx` - 5 hardcoded URLs
- `views/IACGovernanceView.tsx` - 4 hardcoded URLs
- `contexts/LLMConfigContext.tsx` - 1 hardcoded URL
- `contexts/NotificationContext.tsx` - 3 hardcoded URLs
- `contexts/AuthContext.tsx` - 2 hardcoded URLs
- + 32 more files (see full audit in separate document)

**Estimated Refactoring Effort:** 2-3 weeks for 2 frontend engineers

---

## APPENDIX C: TEMPORAL WORKFLOW EXAMPLES

### Example: DocumentIngestionWorkflow
```python
@workflow.defn
class DocumentIngestionWorkflow:
    @workflow.run
    async def run(self, project_id: str, file_key: str) -> dict:
        # Step 1: Upload to MinIO
        upload_result = await workflow.execute_activity(
            upload_document_activity,
            args=[project_id, file_key],
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                backoff_coefficient=2.0,
            )
        )
        
        # Step 2: Detect file format
        format_result = await workflow.execute_activity(
            detect_format_activity,
            args=[upload_result['object_key']],
            start_to_close_timeout=timedelta(minutes=1),
        )
        
        # Step 3: Convert to Markdown
        conversion_result = await workflow.execute_activity(
            convert_to_markdown_activity,
            args=[upload_result['object_key'], format_result['format']],
            start_to_close_timeout=timedelta(minutes=10),
        )
        
        # Step 4: Extract entities
        entity_result = await workflow.execute_activity(
            extract_entities_activity,
            args=[conversion_result['markdown_text']],
            start_to_close_timeout=timedelta(minutes=15),
        )
        
        # Step 5: Generate embeddings
        embedding_result = await workflow.execute_activity(
            generate_embeddings_activity,
            args=[conversion_result['markdown_text']],
            start_to_close_timeout=timedelta(minutes=5),
        )
        
        # Step 6: Store JSONL
        jsonl_result = await workflow.execute_activity(
            store_jsonl_activity,
            args=[project_id, entity_result['entities'], embedding_result['embeddings']],
            start_to_close_timeout=timedelta(minutes=2),
        )
        
        # Step 7: Update processing status
        await workflow.execute_activity(
            update_processing_status_activity,
            args=[project_id, file_key, 'completed'],
            start_to_close_timeout=timedelta(minutes=1),
        )
        
        return {
            'status': 'completed',
            'project_id': project_id,
            'file_key': file_key,
            'entities_count': len(entity_result['entities']),
            'embeddings_count': len(embedding_result['embeddings']),
        }
```

---

**END OF COMPREHENSIVE TDD IMPLEMENTATION PLAN**

*This plan is a living document and will be updated as the project progresses. All stakeholders should review and approve before implementation begins.*
