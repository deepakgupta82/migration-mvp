# Migration Platform Architecture

## Overview

The Nagarro Ascent Migration Platform is a comprehensive cloud migration and AI-powered knowledge management system built on a microservices architecture. The platform provides end-to-end support for cloud migration projects, including document processing, AI agent orchestration, knowledge management, and real-time collaboration.

## High-Level Architecture

The platform follows a microservices architecture with the following key components:

- **Frontend**: React/TypeScript single-page application
- **Backend**: FastAPI-based API gateway and core services
- **Services Layer**: Specialized microservices for different domains
- **Data Layer**: Multiple databases for different data types
- **Infrastructure**: Kubernetes-based deployment with cloud provider support

### Architecture Diagram

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │     Backend     │    │   Services      │
│   (React/TS)    │◄──►│   (FastAPI)     │◄──►│   (Microservices)│
│                 │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
          │                       │                       │
          ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   WebSocket     │    │   PostgreSQL    │    │   Vector DB     │
│   Services      │    │   (Relational)  │    │   (Weaviate)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                          │
┌─────────────────┐    ┌─────────────────┐               │
│   Redis         │    │   Neo4j         │◄──────────────┘
│   (Cache)       │    │   (Graph)       │
└─────────────────┘    └─────────────────┘
```

## Tech Stack

### Backend & Services
- **Language**: Python 3.9+
- **Framework**: FastAPI with Uvicorn ASGI server
- **API Documentation**: OpenAPI/Swagger
- **Authentication**: JWT tokens, service-to-service auth
- **Logging**: Structured JSON logging with Loki integration
- **Health Monitoring**: Kubernetes probes, service registry

### Frontend
- **Language**: TypeScript
- **Framework**: React 18 with React Router
- **UI Library**: Mantine UI components
- **State Management**: React Context, custom hooks
- **HTTP Client**: Axios
- **Build Tool**: Create React App

### Data Storage
- **Primary Database**: PostgreSQL (relational data, user management, projects)
- **Cache**: Redis (session storage, temporary data)
- **Vector Database**: Weaviate (embeddings for RAG)
- **Graph Database**: Neo4j (knowledge graphs, relationships)
- **Object Storage**: MinIO (document storage)
- **Search/Indexing**: Weaviate (semantic search)

### AI/ML Stack
- **LLM Providers**: OpenAI, Anthropic, Google Vertex AI, Google Generative AI
- **Embeddings**: LangChain ecosystem
- **Agent Framework**: CrewAI, AutoGen
- **Document Processing**: Custom parsers, OCR (Tesseract)

### Infrastructure
- **Containerization**: Docker
- **Orchestration**: Kubernetes
- **Service Discovery**: Custom service registry
- **Load Balancing**: NGINX ingress
- **Monitoring**: Prometheus metrics
- **Logging**: Loki with Grafana
- **CI/CD**: GitHub Actions (inferred from .github directory)

## Services Overview

The platform consists of 19 specialized microservices organized into three tiers:

**Core Services** (Infrastructure & Gateway):
- Service Registry (8011) - Service discovery and health monitoring
- Backend Gateway (8000) - API gateway and request routing
- Project Service (8002) - Project lifecycle management

**Domain Services** (Business Logic):
- LLM Service (8007) - Language model orchestration
- Graph Service (8006) - Knowledge graph management
- Knowledge Service (8017) - RAG and semantic search
- AI Agent Service (8008) - Multi-agent orchestration with MCP
- Document Service (8003) - Document processing
- Vector Service (8005) - Embeddings and similarity search
- Analytics Service (8014) - Data analytics and reporting
- Stats Service (8004) - Platform statistics

**Cloud Migration & FinOps Services**:
- Cloud Tools Service (8012) - Native cloud integrations and discovery
- Cloud Orchestration Service (8020) - Migration wave management
- IAC Governance Service (8021) - IaC compliance and security
- FinOps Optimization Service (8022) - Cost optimization and anomaly detection

**Supporting Services** (Infrastructure Support):
- Storage Service (8010) - File storage and management
- WebSocket Service (8009) - Real-time communication
- Security Service (8015) - Multi-tenant auth and RBAC
- Collaboration Service (8016) - Team collaboration and notifications

### Core Services

#### Service Registry (Port 8011)
- **Purpose**: Service discovery and health monitoring
- **Responsibilities**:
  - Register/unregister services
  - Health checks and status monitoring
  - Real-time health notifications via WebSocket
  - Docker container monitoring
- **Dependencies**: Docker API, PostgreSQL, Redis

#### Backend Gateway (Port 8000)
- **Purpose**: API gateway and core business logic
- **Responsibilities**:
  - Request routing and authentication
  - Project management coordination
  - Document processing orchestration
  - CrewAI agent management
- **Dependencies**: PostgreSQL, Redis, all microservices

#### Project Service (Port 8002)
- **Purpose**: Project lifecycle management
- **Responsibilities**:
  - Project CRUD operations
  - Deliverable management
  - Template handling
  - Generation request processing
- **Dependencies**: PostgreSQL, Alembic migrations

#### LLM Service (Port 8007)
- **Purpose**: Large Language Model orchestration
- **Responsibilities**:
  - LLM provider management and configuration
  - Rate limiting and usage tracking
  - Model testing and validation
  - Caching and optimization
- **Dependencies**: Redis, PostgreSQL, external LLM APIs

#### Graph Service (Port 8006)
- **Purpose**: Knowledge graph management and multi-viewpoint visualization
- **Responsibilities**:
  - Neo4j database operations
  - Entity extraction from documents with metadata tracking
  - Relationship mapping and graph construction
  - Infrastructure topology visualization
  - Multi-viewpoint graph visualization:
    - **Platform-Centric View**: Hierarchical 4-layer visualization (Platform → Application → Server → Details)
    - **Document Source View**: Filter graph by originating document for traceability
    - **Environment View**: Group entities by environment (Dev/Test/Prod) with cross-environment dependency analysis
  - Canonical entity identification and merging
  - Graph query optimization with caching
- **Key Features**:
  - Metadata tracking: `environment`, `layer_type`, `hierarchy_level`, `document_id`, `document_filename` on all entities
  - Concentric layout positioning for hierarchical visualization
  - Cross-environment connection detection for migration risk analysis
  - Document-to-graph traceability for audit and compliance
- **Dependencies**: Neo4j, Redis

#### Knowledge Service (Port 8017)
- **Purpose**: Advanced RAG and knowledge management
- **Responsibilities**:
  - Semantic search and retrieval
  - Knowledge graph construction
  - Context-aware question answering
  - Document indexing and curation
- **Dependencies**: Vector service, LLM service, storage service

#### AI Agent Service (Port 8008)
- **Purpose**: AI agent orchestration with Level 3 agentic capabilities and MCP integration
- **Responsibilities**:
  - CrewAI workflow management
  - AutoGen copilot integration with persistent conversation storage
  - Multi-agent task orchestration
  - Real-time agent communication via WebSocket
  - **Dynamic query routing** (SupervisorAgent)
  - **Iterative quality refinement** (Reflection Loop)
  - MCP (Model Context Protocol) server integration and registry
  - Project-scoped LLM configuration management
- **Key Features**:
  - WebSocket-based real-time conversations (`/ws/autogen/{session_id}`)
  - Persistent conversation storage with PostgreSQL
  - Project-scoped API key management (no default keys)
  - Admin prompt management for AI agents
  - MCP server registry with AWS MCP servers (IAM, CloudWatch, Cost Explorer, API, Pricing)
  - Correlation ID propagation for distributed tracing
  - JSON-structured logging for Loki integration
- **Dependencies**: LLM service, project service, WebSocket service, PostgreSQL, Redis

**Level 3 Enhancements** (implemented October 2025):

The AI Agent Service has been enhanced from Level 2 "Strategic Problem-Solver" to Level 3 "Collaborative Multi-Agent System" with the following capabilities:

1. **Supervisor Agent (Dynamic Routing)**:
   - Intelligent query classification (simple_fact | focused_analysis | comprehensive_assessment)
   - Domain expert selection (6 expertise types)
   - Cost-optimized execution paths (60-70% cost reduction on simple queries)
   - LLM-based + heuristic fallback classification
   - File: `app/core/supervisor_agent.py`

2. **Reflection Loop (Producer-Critic Pattern)**:
   - Iterative document refinement (max 3 iterations)
   - Quality assessment with 5 criteria (accuracy, completeness, clarity, professionalism, actionability)
   - LLM-based review with heuristic fallback
   - Learning system tracking refinement patterns
   - Quality threshold: 0.9 (auto-accept)
   - File: `app/core/reflection_loop.py`

3. **Dual Agent Frameworks**:
   - **CrewAI**: Document generation and assessment crews
   - **AutoGen**: Conversational agents with session memory and PostgreSQL persistence

4. **MCP Integration**:
   - Unified registry for Model Context Protocol servers
   - Pre-configured AWS MCP servers for cloud operations
   - Dynamic server management (enable/disable, upsert configuration)
   - STDIO transport with environment variable support

**Routing Decision Matrix**:
```
Simple Fact Query (e.g., "What OS is server-01?")
  → Direct Service Call (5 seconds, $0.001)

Focused Analysis (e.g., "Analyze security risks for database tier")
  → Mini-Crew (5 minutes, $0.10)

Comprehensive Assessment (e.g., "Generate migration strategy")
  → Full Assessment Crew + Reflection Loop (2 hours, $2.00)
```

For detailed architecture and implementation guide, see: [AGENT_ENHANCEMENTS.md](./AGENT_ENHANCEMENTS.md)

### Supporting Services

#### Document Service (Port 8003)
- **Purpose**: Document processing and analysis
- **Responsibilities**:
  - Document upload and parsing
  - Text extraction and OCR
  - Document classification
  - Metadata extraction

#### Vector Service (Port 8005)
- **Purpose**: Vector embeddings and similarity search
- **Responsibilities**:
  - Embedding generation
  - Vector storage and retrieval
  - Similarity search operations
- **Dependencies**: Weaviate, embedding models

#### Storage Service (Port 8010)
- **Purpose**: File storage and management
- **Responsibilities**:
  - File upload/download
  - Metadata management
  - Storage optimization
- **Dependencies**: MinIO

#### WebSocket Service (Port 8009)
- **Purpose**: Real-time communication
- **Responsibilities**:
  - WebSocket connections
  - Real-time notifications
  - Live updates and streaming
- **Dependencies**: Redis pub/sub

#### Analytics Service (Port 8014)
- **Purpose**: Data analytics and reporting
- **Responsibilities**:
  - Usage analytics
  - Performance metrics
  - Report generation
- **Dependencies**: PostgreSQL, Redis

#### Stats Service (Port 8004)
- **Purpose**: Platform statistics
- **Responsibilities**:
  - Real-time metrics collection
  - Dashboard data provision
  - Performance monitoring
- **Dependencies**: PostgreSQL, WebSocket

#### Security Service (Port 8015)
- **Purpose**: Enterprise multi-tenant security, authentication, and RBAC
- **Responsibilities**:
  - Multi-tenant authentication and authorization
  - JWT token management and validation
  - Role-based access control (RBAC) with granular permissions
  - Security policy management
  - Audit logging and compliance tracking
  - User and tenant lifecycle management
  - Session management and token invalidation
  - Permission checking and enforcement
- **Key Features**:
  - **Multi-Tenancy**: Complete tenant isolation with subscription plans (Basic, Standard, Premium, Enterprise)
  - **User Roles**: Super Admin, Tenant Admin, Project Manager, Migration Specialist, Analyst, Viewer
  - **Permissions**: 14 granular permissions covering projects, users, analytics, security, agents, audit
  - **JWT Authentication**: 24-hour token expiry with automatic session management
  - **Audit Logging**: Comprehensive audit trail for all security events (authentication, logout, access attempts)
  - **Subscription Plans**: Feature gating based on subscription level
  - **Password Security**: SHA-256 hashed passwords (production should use bcrypt/scrypt)
- **User Roles and Permissions**:
  - Super Admin: Full system access including tenant management
  - Tenant Admin: Tenant-level administration, user management, project management
  - Project Manager: Project CRUD, user view, analytics
  - Migration Specialist: Project read/update, analytics view
  - Analyst: Project and analytics read access
  - Viewer: Read-only access to projects and analytics
- **Tenant Features by Plan**:
  - Basic: 10 users, 5 projects, basic migration
  - Standard: 50 users, 25 projects, document processing, cloud tools
  - Premium: 200 users, 100 projects, advanced analytics, agent orchestration
  - Enterprise: 1000 users, 500 projects, full RBAC, audit logging
- **API Endpoints**:
  - `/auth/login`, `/auth/logout`, `/auth/me`
  - `/tenants` (create, get), `/tenants/{id}/users` (manage users)
  - `/tenants/{id}/audit-logs` (compliance and audit)
  - `/permissions/check/{permission}` (permission validation)
- **Dependencies**: None (standalone security service)

#### Cloud Tools Service (Port 8012)
- **Purpose**: Native cloud provider integrations and infrastructure discovery
- **Responsibilities**:
  - Cloud credential management (AWS, Azure, GCP)
  - Automated cloud resource discovery and inventory
  - Cloud environment assessment and analysis
  - Cost estimation and analysis per resource
  - Migration complexity scoring
  - Migration recommendations generation
  - Real-time assessment progress tracking
- **Key Features**:
  - **Multi-Cloud Support**: AWS, Azure, GCP, and hybrid environments
  - **Resource Types**: Compute, storage, database, network, security, serverless, container
  - **Assessment Engine**: Background task execution with WebSocket notifications
  - **Resource Discovery**: Automated inventory with metadata extraction
  - **Cost Analysis**: Monthly cost estimation per resource and aggregated totals
  - **Complexity Scoring**: 0-100 score based on migration complexity (low/medium/high)
  - **Recommendations**: Intelligent migration pathway suggestions
  - **Assessment States**: Pending → In Progress → Completed/Failed
- **Cloud Provider Integration**:
  - AWS: EC2, EBS, RDS, and other core services
  - Azure: Virtual Machines, Storage Accounts, databases
  - GCP: Compute Engine, Cloud Storage, Cloud SQL
  - Extensible for additional providers
- **Assessment Report Contents**:
  - Total resources discovered by type and provider
  - Total monthly cost estimation
  - Migration complexity score (0-100)
  - Detailed recommendations list
  - Resource-level metadata and tags
- **API Endpoints**:
  - `/projects/{id}/credentials` (add cloud credentials)
  - `/projects/{id}/assessments` (start/list assessments)
  - `/assessments/{id}` (get assessment details)
  - `/projects/{id}/resources` (list discovered resources)
  - `/projects/{id}/resources/summary` (aggregated statistics)
- **Dependencies**: WebSocket service (notifications), storage service (reports)

#### Cloud Orchestration Service (Port 8020)
- **Purpose**: Multi-cloud migration orchestration and wave management
- **Responsibilities**:
  - Migration wave planning and execution
  - Multi-cloud migration workflow orchestration
  - MCP-based migration task execution
  - Wave dependency management
  - Migration timeline tracking
  - Rollback and disaster recovery coordination
  - Migration status monitoring and reporting
- **Key Features**:
  - **Wave Management**: Create, schedule, and execute migration waves
  - **Multi-Cloud Orchestration**: Coordinate migrations across AWS, Azure, GCP
  - **MCP Integration**: Leverage Model Context Protocol for migration automation
  - **Dependency Tracking**: Manage inter-wave and inter-resource dependencies
  - **Status Monitoring**: Real-time tracking of migration progress
  - **Rollback Support**: Automated rollback mechanisms for failed migrations
  - **Timeline Management**: Schedule waves with start/end times and dependencies
- **Wave Lifecycle**:
  - Planning → Scheduled → In Progress → Completed/Failed/Rolled Back
- **Database Schema**:
  - Migration waves table with project association
  - Wave status and timeline tracking
  - Dependency relationships
  - Migration logs and audit trail
- **API Endpoints** (via router):
  - Wave CRUD operations
  - Wave execution and monitoring
  - Dependency management
  - Status reporting
- **Dependencies**: Project service, cloud tools service, service registry, PostgreSQL
- **Deployment**: Alembic database migrations for schema management

#### IAC Governance Service (Port 8021)
- **Purpose**: Infrastructure-as-Code compliance, policy enforcement, and security scanning
- **Responsibilities**:
  - Terraform code analysis and validation
  - Policy-as-Code enforcement (OPA/Rego)
  - Security vulnerability scanning
  - Compliance checking (CIS, PCI-DSS, HIPAA, SOC2)
  - Cost estimation from IaC templates
  - Automated remediation suggestions
  - Violation tracking and reporting
  - IaC best practices enforcement
- **Key Features**:
  - **Terraform Support**: Parse, validate, and analyze Terraform configurations
  - **Policy Engine**: Define and enforce organizational policies
  - **Security Scanning**: Identify security risks in IaC templates
  - **Compliance Frameworks**: Built-in support for major compliance standards
  - **Cost Estimation**: Calculate infrastructure costs from Terraform plans
  - **Remediation Engine**: Generate automated fix suggestions
  - **Violation Management**: Track, prioritize, and resolve policy violations
  - **Multi-Severity**: Critical, High, Medium, Low, Info severity levels
- **Scan Types**:
  - Security vulnerabilities (exposed secrets, insecure configurations)
  - Compliance violations (regulatory requirements)
  - Cost optimization opportunities
  - Best practices deviations
- **Policy Management**:
  - Create custom policies with Rego language
  - Enable/disable policies per project or globally
  - Policy versioning and audit trail
  - Policy testing and validation
- **Remediation Support**:
  - Automated fix generation for common issues
  - Manual remediation guidance
  - Remediation tracking and verification
- **API Endpoints** (via routers):
  - `/terraform/*` - Terraform operations
  - `/policies/*` - Policy management
  - `/scans/*` - Security and compliance scanning
  - `/remediations/*` - Remediation workflow
  - `/violations/*` - Violation tracking
  - `/costs/*` - Cost estimation
  - `/security/*` - Security operations
- **Dependencies**: PostgreSQL (schema management), service registry
- **Deployment**: Alembic migrations, .env configuration

#### FinOps Optimization Service (Port 8022)
- **Purpose**: Cost optimization, anomaly detection, and FinOps intelligence for multi-cloud
- **Responsibilities**:
  - Multi-cloud cost tracking and analysis
  - Cost anomaly detection and alerting
  - Budget management and forecasting
  - Optimization recommendations generation
  - FinOps best practices enforcement
  - Cost allocation and chargeback
  - Reserved instance and savings plan optimization
  - Real-time cost monitoring
- **Key Features**:
  - **Multi-Cloud Cost Visibility**: Unified view across AWS, Azure, GCP
  - **Cost Granularity**: Daily, weekly, monthly cost breakdowns
  - **Anomaly Detection**: ML-based spike and trend detection
  - **Budget Management**: Set budgets, track spend, get alerts
  - **Recommendations**: Right-sizing, reserved instances, unused resource cleanup
  - **Cost Allocation**: Tag-based cost allocation and reporting
  - **Forecasting**: Trend-based cost prediction
  - **Alert Management**: Configurable thresholds and notification channels
- **Cost Visibility Features**:
  - Cost by cloud service provider (CSP)
  - Cost by project/application
  - Cost by environment (dev/test/prod)
  - Cost trends and variance analysis
  - Top cost drivers identification
- **Optimization Recommendations**:
  - Right-sizing (over-provisioned resources)
  - Reserved instance/savings plan opportunities
  - Unused resource identification
  - Storage tier optimization
  - Network cost reduction
- **Anomaly Types**:
  - Cost spikes (sudden increases)
  - Usage anomalies (unexpected patterns)
  - Budget breaches
  - Waste detection (idle resources)
- **Budget Management**:
  - Project-level and organization-level budgets
  - Monthly, quarterly, annual budget periods
  - Alert thresholds (50%, 80%, 100%)
  - Budget vs. actual spend tracking
- **API Endpoints**:
  - `/api/finops/projects/{id}/costs/summary` - Cost summaries
  - `/api/finops/projects/{id}/budgets` - Budget management
  - `/api/finops/projects/{id}/recommendations` - Optimization recommendations
  - `/api/finops/projects/{id}/anomalies` - Anomaly alerts
- **Dependencies**: PostgreSQL (cost data), analytics service (reporting)
- **Deployment**: Production-ready FastAPI service with correlation ID middleware

#### Collaboration Service (Port 8016)
- **Purpose**: Real-time team collaboration and notification management
- **Responsibilities**:
  - Team workspace management with member tracking
  - Task/todo management with assignment and status tracking
  - Meeting scheduling and management (invitation, agenda, recording)
  - File sharing within workspaces
  - Comment system with mentions and reactions
  - Real-time notifications with multi-channel support (in-app, email, webhook, Slack, Teams)
  - Activity feeds and timeline tracking
  - WebSocket-based real-time updates
  - Workspace statistics and analytics
- **Key Features**:
  - **Task Management**: Full lifecycle (TODO → IN_PROGRESS → REVIEW → COMPLETED/CANCELLED)
  - **Priority Levels**: Low, Medium, High, Urgent
  - **Meeting Management**: Schedule, track attendance, record notes
  - **File Sharing**: Document, image, video, archive support with preview URLs
  - **Notification Types**: Info, warning, error, success, urgent, mention, task assignment
  - **Correlation ID Tracking**: Links notifications to user actions for audit trails
  - **Activity Tracking**: Project created/updated, migration started/completed, document uploaded, etc.
  - **Real-time Broadcasting**: WebSocket connections for workspace and user-level updates
  - **Team Member Status**: Online/offline tracking, last seen timestamps
- **Data Models**:
  - TeamMember, Workspace, Task, Meeting, SharedFile, Comment, Notification, Activity
  - WorkspaceStats for analytics
- **Dependencies**: WebSocket service, storage service, project service
- **WebSocket Endpoints**: `/ws/{user_id}` for real-time collaboration

## Data Flow

### Document Processing Flow
1. **Upload**: Documents uploaded via frontend to storage service
2. **Processing**: Document service extracts text and metadata
3. **Indexing**: Vector service generates embeddings and stores in Weaviate
4. **Graph Building**: Graph service creates knowledge graph in Neo4j
5. **Search Ready**: Knowledge service enables semantic search

### AI Agent Workflow
1. **Request**: User initiates agent workflow via frontend
2. **Orchestration**: AI agent service coordinates CrewAI agents
3. **LLM Processing**: LLM service provides model access and caching
4. **Knowledge Retrieval**: Knowledge service provides context via RAG
5. **Real-time Updates**: WebSocket service streams progress to frontend

### Project Management Flow
1. **Creation**: Projects created via project service
2. **Document Association**: Documents linked to projects
3. **Agent Processing**: AI agents analyze project documents
4. **Knowledge Building**: Insights stored in knowledge graph
5. **Reporting**: Analytics service generates project reports

## Service Interactions

Services communicate through:
- **HTTP REST APIs**: Primary communication method
- **WebSocket**: Real-time updates and streaming
- **Shared Databases**: PostgreSQL for relational data, Redis for cache
- **Message Queues**: Redis pub/sub for async communication
- **Service Registry**: Dynamic service discovery

### Key Integration Points

#### Service Client
- Centralized HTTP client for service-to-service communication
- Automatic authentication headers
- Correlation ID propagation
- Timeout and retry handling

#### Shared Libraries
- Common utilities in `common/` directory
- Shared data models and DTOs
- Configuration management
- Logging and monitoring utilities

## Deployment

### Kubernetes Deployment
- **Orchestration**: Kubernetes clusters
- **Services**: Deployed as individual pods
- **Databases**: StatefulSets with persistent volumes
- **Ingress**: NGINX ingress controller
- **ConfigMaps/Secrets**: Environment-specific configuration

### Cloud Providers
- **AWS**: ECS, Lambda, RDS, S3 via Terraform modules
- **Azure**: Azure services integration
- **Multi-cloud**: Hybrid deployments supported

### Development Environment
- **Local Development**: Docker Compose for local services
- **Hot Reload**: Services support development mode with auto-reload
- **Service Registry**: Local service discovery and health monitoring

## Security

### Authentication & Authorization
- **Multi-tenant Security**: Comprehensive RBAC via Security Service (Port 8015)
- **JWT-based Authentication**: 24-hour tokens with automatic session management
- **Service-to-service Tokens**: Internal service authentication
- **Role-based Access Control**: 6 user roles with 14 granular permissions
- **Tenant Isolation**: Complete data and resource isolation per tenant
- **API Key Management**: Secure management for external services (LLM providers, cloud APIs)
- **Audit Logging**: Full audit trail for compliance and security events

### Data Protection
- Encrypted data at rest and in transit
- Secure API communication with TLS
- Input validation and sanitization
- Rate limiting and abuse prevention
- Password hashing (SHA-256, recommend bcrypt/scrypt for production)
- Sensitive data masking in logs

## Monitoring & Observability

### Health Checks
- Kubernetes readiness/liveness probes
- Service-level health endpoints
- Dependency health monitoring
- Circuit breaker patterns

### Logging
- Structured JSON logging
- Correlation ID tracking
- Loki aggregation
- Grafana dashboards

### Metrics
- Prometheus metrics collection
- Custom business metrics
- Performance monitoring
- Error tracking

## Scalability Considerations

### Horizontal Scaling
- Stateless services can scale horizontally
- Database read replicas for read-heavy workloads
- Load balancing across service instances

### Data Partitioning
- Project-based data isolation
- Sharding strategies for large datasets
- Cache optimization for frequently accessed data

### Performance Optimization
- Async processing for heavy operations
- Caching layers (Redis, application-level)
- Optimized database queries
- CDN integration for static assets

## Development & Deployment Workflow

### Local Development
1. Services run in development mode with hot reload
2. Docker Compose for external dependencies
3. Local databases and caches
4. Service registry for local discovery

### CI/CD Pipeline
1. Code committed to repository
2. Automated testing and linting
3. Docker image building
4. Kubernetes deployment
5. Health checks and rollbacks

### Environment Management
- Multiple environments (dev, staging, prod)
- Environment-specific configurations
- Secret management
- Blue-green deployments

This architecture provides a robust, scalable foundation for AI-powered cloud migration and knowledge management, with clear separation of concerns and comprehensive monitoring capabilities.