# Nagarro's Ascent - Enterprise Architecture

**Version:** 3.0  
**Audience:** Enterprise & Solutions Architects  
**Status:** As-Built (Q3 2025)  
**Last Updated:** August 6, 2025  
**Platform Name:** Nagarro's Ascent (formerly AgentiMigrate)

---

## 1. Executive Summary

Nagarro's Ascent is an enterprise-grade AI-powered cloud migration assessment platform that transforms complex cloud transformation initiatives through specialized AI agents and advanced knowledge synthesis. The platform delivers C-level ready migration strategies, professional deliverables, and real-time intelligence to Fortune 500 organizations.

### Platform Capabilities
- **AI-Driven Assessment**: Multi-agent crews with 12+ years equivalent expertise in enterprise migrations
- **Professional Deliverables**: Executive-ready PDF/DOCX reports with embedded architecture diagrams  
- **Real-Time Intelligence**: Interactive dependency graphs and RAG-powered knowledge exploration
- **Zero-Trust Security**: Complete data isolation within client infrastructure boundaries
- **Enterprise Integration**: JWT-based authentication with comprehensive audit trails

### Key Differentiators
- **Cross-Modal Synthesis**: Combined graph and vector database intelligence for comprehensive analysis
- **Adversarial Validation**: Compliance-first approach with risk officer agent validation
- **Professional Command Center**: Modern React UI with real-time monitoring and service management
- **Polyglot Persistence**: Purpose-built data stores for structured, graph, vector, and object data

---

## 2. Architectural Principles & Design Tenets

### 2.1 Core Principles

**Zero-Trust, Client-Perimeter Deployment:**
- Entire platform runs within client's cloud environment (VPC/VNet) or on-premises
- Eliminates data exfiltration concerns and complex data residency requirements
- All inter-service communication encrypted with mTLS capability

**Domain-Driven, Composable Design:**
- Microservices decomposed by bounded contexts (Project Management, Assessment, Reporting)
- Independent scalability and technology flexibility per service
- Clear ownership boundaries with well-defined service interfaces

**Event-Driven & Real-Time Communication:**
- Synchronous REST APIs for direct commands and queries
- WebSocket connections for real-time agent monitoring and progress tracking
- Asynchronous processing for long-running AI workflows

**Polyglot Persistence:**
- PostgreSQL for relational data (projects, users, metadata)
- Weaviate for vector embeddings and semantic search
- Neo4j for graph relationships and dependency modeling
- MinIO for object storage and artifact management

**Glass Box AI & Full Auditability:**
- Complete transparency in agent decision-making processes
- Immutable audit trails for all agent actions and tool invocations
- Governance-ready logging for compliance and diagnostics

### 2.2 Quality Attributes

- **Security**: JWT-based authentication, RBAC authorization, encrypted API keys
- **Scalability**: Microservices architecture with independent scaling capabilities
- **Reliability**: Health checks, graceful degradation, comprehensive error handling  
- **Performance**: Optimized Docker builds, efficient data processing pipelines
- **Maintainability**: TypeScript frontend, comprehensive documentation, modular components

---

## 3. System Architecture & Components

### 3.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    NAGARRO'S ASCENT PLATFORM                       │
├─────────────────────────────────────────────────────────────────────┤
│  Command Center     │  AI Orchestrator    │  Knowledge Engine       │
│  (React/TS/Mantine) │  (FastAPI/Python)   │  (Weaviate + Neo4j)     │
│  - Dashboard        │  - CrewAI Framework │  - Vector Search        │
│  - Project Mgmt     │  - Multi-LLM        │  - Graph Analysis       │
│  - Real-time UI     │  - WebSocket        │  - Cross-Modal Sync     │
├─────────────────────────────────────────────────────────────────────┤
│  Project Service    │  Reporting Service  │  Object Storage         │
│  (FastAPI/SQL)      │  (FastAPI/Pandoc)   │  (MinIO S3)             │
│  - Authentication   │  - PDF/DOCX Gen     │  - Document Storage     │
│  - RBAC Security    │  - LaTeX Templates  │  - Report Artifacts     │
│  - Lifecycle Mgmt   │  - Enterprise Style │  - Diagram Storage      │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 Core Services

#### **Frontend Command Center** (Port 3000)
**Technology Stack:** React 18, TypeScript, Mantine v7, React Router v6
- **Professional Dashboard**: Executive metrics, project statistics, success rates
- **Project Management**: Complete CRUD with real-time status tracking
- **Multi-Tab Workspace**: Overview, Files, Discovery, Reports, History tabs
- **Interactive Visualizations**: Force-directed dependency graphs with react-force-graph-2d
- **RAG-Powered Chat**: Natural language queries with conversation history
- **Real-Time Monitoring**: WebSocket-based progress tracking and agent logging
- **Service Management**: Health monitoring with start/stop/restart capabilities

#### **Backend AI Orchestrator** (Port 8000)
**Technology Stack:** FastAPI, Python 3.11, CrewAI, LangChain, WebSockets
- **Dual-Workflow Architecture**: 
  - Phase 1: Knowledge base creation (Upload → Parse → Embed → Store)
  - Phase 2A: Agent-driven assessment with CrewAI orchestration
  - Phase 2B: Interactive chat with lightweight RAG queries
- **Multi-Provider LLM Support**: OpenAI GPT-4, Google Gemini, Anthropic Claude
- **Real-Time Communication**: WebSocket streaming for agent actions and progress
- **Comprehensive Logging**: AgentLogStreamHandler with detailed audit trails
- **Advanced Tools**: Hybrid search, compliance frameworks, live data fetching

#### **Project Service** (Port 8002)  
**Technology Stack:** FastAPI, SQLAlchemy, PostgreSQL, JWT
- **Authentication & Authorization**: JWT-based with UUID service users
- **RBAC Security Model**: User and platform_admin roles with granular permissions
- **Project Lifecycle Management**: Status tracking, metadata, and file associations
- **LLM Configuration Management**: Multi-provider settings with encrypted API keys
- **Database Models**: Projects, Users, Files, Settings, Deliverables, Templates

#### **Reporting Service** (Port 8001)
**Technology Stack:** FastAPI, Pandoc, LaTeX, MinIO integration
- **Professional Document Generation**: High-quality PDF and DOCX reports
- **Template System**: Customizable templates with Nagarro branding
- **LaTeX Processing**: Executive-grade formatting with embedded diagrams
- **Object Storage Integration**: Seamless MinIO upload and retrieval
- **Download Management**: Proper MIME types and secure access URLs

#### **Supporting Services**
- **MegaParse Service** (Port 5001): Multi-format document parsing and text extraction
- **Weaviate** (Port 8080): Vector database with SentenceTransformer embeddings
- **Neo4j** (Port 7474/7687): Graph database with APOC procedures
- **PostgreSQL** (Port 5432): Primary relational database with full ACID compliance
- **MinIO** (Port 9000/9001): S3-compatible object storage with web console

---

## 4. Data Architecture & Flow

### 4.1 Data Stores

#### **PostgreSQL - Relational Store**
```sql
-- Core tables
projects (id, name, description, client_name, status, created_at, updated_at)
users (id, email, role, created_at)
project_files (id, project_id, filename, file_size, upload_date)
platform_settings (id, key, value, created_at)
llm_configurations (id, provider, model_id, api_key_encrypted)
```

#### **Weaviate - Vector Store**
- Document chunks as vector embeddings using SentenceTransformers
- Project-specific collections for data isolation
- Semantic search capabilities with similarity scoring
- Integration with hybrid search for cross-modal queries

#### **Neo4j - Graph Store**  
- IT infrastructure entities (Servers, Applications, Databases, Networks)
- Explicit relationships (HOSTS, CONNECTS_TO, DEPENDS_ON, COMMUNICATES_WITH)
- Dependency analysis for migration wave planning
- Digital twin representation of client landscapes

#### **MinIO - Object Store**
- **project-files bucket**: Original uploaded documents
- **reports bucket**: Generated PDF/DOCX deliverables  
- **diagrams bucket**: Architecture diagrams and visualizations
- **templates bucket**: Document templates and configurations

### 4.2 Data Flow Patterns

#### **Project Creation Flow**
1. User creates project via Command Center UI
2. Frontend → Backend → Project Service (JWT validation)  
3. Project Service creates PostgreSQL record with LLM configuration
4. MinIO buckets initialized for project-specific storage
5. Response propagated back to UI for immediate feedback

#### **Document Processing Pipeline**
1. **File Upload**: Drag-and-drop interface with progress tracking
2. **Document Parsing**: MegaParse service extracts clean text
3. **Knowledge Extraction**: Text chunking and entity identification
4. **Vector Embedding**: SentenceTransformer processing for Weaviate storage
5. **Graph Population**: Relationship extraction for Neo4j entities
6. **Deduplication**: Prevention of duplicate processing with statistics tracking

#### **AI Assessment Workflow**  
1. **Crew Initialization**: CrewAI agents instantiated from YAML configurations
2. **Tool Integration**: Agents equipped with RAG, Graph, and specialized tools
3. **Sequential Execution**: Tasks executed with memory sharing between agents
4. **Real-Time Monitoring**: WebSocket streaming of agent activities to UI
5. **Report Generation**: Markdown-based comprehensive assessment
6. **Professional Publishing**: PDF/DOCX generation via Reporting Service

#### **Interactive Chat Flow**
1. **Natural Language Input**: User query via chat interface
2. **Vector Search**: Weaviate semantic similarity matching  
3. **Context Retrieval**: Relevant document chunks identification
4. **LLM Synthesis**: Provider-specific response generation
5. **Real-Time Response**: Answer delivery with source attribution

---

## 5. AI Agent Framework

### 5.1 Agent Architecture

#### **Specialized Agent Profiles**

**Senior Infrastructure Discovery Analyst**
- **Experience**: 12+ years in enterprise IT discovery and dependency mapping
- **Tools**: Hybrid Search Tool, Lessons Learned Tool, Context Tool
- **Methodology**: Cross-modal synthesis combining graph queries with semantic search
- **Output**: Comprehensive current state analysis with infrastructure inventory

**Principal Cloud Architect & Migration Strategist**  
- **Experience**: 50+ enterprise migrations across AWS, Azure, GCP
- **Tools**: Cloud Catalog Tool, Live Data Fetch Tool, Context Tool
- **Framework**: 6Rs migration patterns (Rehost, Replatform, Refactor, Retire, Retain, Relocate)
- **Output**: Target architecture design with cost optimization

**Risk & Compliance Officer**
- **Experience**: 10+ years in cybersecurity and regulatory compliance
- **Tools**: Compliance Framework Tool, RAG Tool, Context Tool  
- **Authority**: Architecture rejection capability for non-compliant designs
- **Output**: Compliance validation with go/no-go decisions

**Lead Migration Program Manager**
- **Experience**: 30+ cloud migrations with $10M+ budgets
- **Tools**: Project Planning Tool, RAG Tool, Context Tool
- **Specialization**: Wave planning, dependency analysis, risk mitigation
- **Output**: Executive-ready migration roadmap with timelines

### 5.2 Agent Orchestration

#### **CrewAI Integration**
- YAML-based crew definitions for reproducible configurations
- Sequential task execution with context passing between agents
- Memory-enabled collaboration for persistent knowledge sharing
- Real-time logging with WebSocket streaming to Command Center

#### **Tool Ecosystem**
- **RAG Query Tool**: Semantic search against project knowledge base
- **Graph Query Tool**: Neo4j relationship traversal and analysis
- **Hybrid Search Tool**: Combined vector and graph intelligence  
- **Context Tool**: Shared memory for inter-agent communication
- **Compliance Framework Tool**: Regulatory validation against standards
- **Cloud Catalog Tool**: Real-time cloud service and pricing data

### 5.3 Quality Assurance

#### **Adversarial Validation**
- Compliance Officer with architecture rejection authority
- Iterative design refinement until compliance achieved
- Zero-trust principles applied to security architecture
- Risk-first methodology with comprehensive gap identification

#### **Multi-Agent Review**
- Peer validation and cross-checking between agents
- Quality gates at each phase of the assessment
- Executive presentation standards for all deliverables
- C-level readiness validation for strategic recommendations

---

## 6. Security Architecture

### 6.1 Authentication & Authorization

#### **JWT-Based Authentication**
- Project Service acts as identity provider and token issuer
- Service-to-service authentication with UUID-based users
- Token expiration and refresh mechanisms
- Secure token storage and transmission

#### **Role-Based Access Control (RBAC)**
```
Roles:
- user: Project creation, own project management, assessment execution
- platform_admin: All user permissions + user management, system settings, global access
```

#### **API Security**
- All endpoints protected with JWT validation
- Input validation with Pydantic models
- Comprehensive error handling without information leakage
- Rate limiting and request size restrictions

### 6.2 Data Protection

#### **Encryption**
- API keys encrypted at rest in PostgreSQL
- TLS/HTTPS for all client communications  
- mTLS capability for service-to-service communication
- Encrypted MinIO object storage with access controls

#### **Data Isolation**
- Project-specific data segregation in all stores
- Vector database collections scoped by project
- Graph database namespacing for multi-tenancy
- Object storage with project-based bucket structures

### 6.3 Audit & Compliance

#### **Comprehensive Logging**
- All agent actions and tool invocations logged immutably
- Complete request/response audit trails
- User action tracking with timestamps
- Platform health and performance metrics

#### **Regulatory Compliance**
- GDPR compliance with data residency controls
- SOX compliance with financial data protections  
- HIPAA readiness for healthcare environments
- PCI-DSS considerations for payment processing

---

## 7. Deployment & Operations

### 7.1 Local Development

#### **Docker Compose Orchestration**
- Optimized multi-stage builds with BuildKit caching
- 60-80% faster subsequent builds with persistent caches
- Health checks for all services with dependency management
- Automated setup scripts for cross-platform deployment

#### **Development Workflow**
```bash
# Windows setup
.\setup-platform.ps1

# Service management
.\start-platform-dev.ps1
.\health-check.bat

# Individual service access
http://localhost:3000    # Command Center
http://localhost:8000    # Backend API
http://localhost:8002    # Project Service
http://localhost:8001    # Reporting Service
```

### 7.2 Production Deployment

#### **Kubernetes Architecture**
- Complete K8s manifests for all services
- Persistent Volume Claims for data persistence
- ConfigMaps for environment-specific settings
- Secrets management for sensitive configuration

#### **Cloud Provider Support**
- **AWS**: EKS clusters with RDS, ElastiCache, S3 integration
- **Azure**: AKS clusters with Azure Database, Storage integration  
- **GCP**: GKE clusters with Cloud SQL, Cloud Storage integration
- **On-Premises**: Self-managed Kubernetes with local storage

### 7.3 Monitoring & Observability

#### **Health Monitoring**
- Service-level health checks with startup/readiness/liveness probes
- Database connection monitoring with automatic failover
- Real-time service status in Command Center UI
- Automated alerting for service degradation

#### **Performance Monitoring**
- Application performance monitoring (APM) integration ready
- Prometheus metrics collection capability
- Grafana dashboard integration for visualization
- Log aggregation with ELK stack compatibility

#### **Scaling Strategies**
- Horizontal Pod Autoscaling (HPA) based on CPU/memory metrics
- Vertical Pod Autoscaling (VPA) for resource optimization  
- Database read replicas for improved query performance
- CDN integration for static asset delivery

---

## 8. Integration & Extensibility

### 8.1 API Design

#### **RESTful Architecture**
- Consistent HTTP methods and status codes
- JSON request/response format with comprehensive schemas
- Pagination for large result sets
- Filtering, sorting, and search capabilities

#### **Real-Time Communications**
- WebSocket connections for agent monitoring
- Server-Sent Events (SSE) for progress updates
- Real-time log streaming with filtering capabilities
- Live service health status updates

### 8.2 Third-Party Integrations

#### **LLM Provider Flexibility**
- Configurable providers: OpenAI, Google Gemini, Anthropic Claude
- Failover mechanisms with provider prioritization
- Cost optimization through model selection
- Custom prompt engineering per provider

#### **Cloud Provider APIs**
- Future integration points for AWS MGN, Azure ASR, GCP Migrate
- Real-time pricing APIs for cost optimization
- Service catalog integration for architecture recommendations
- Billing and usage monitoring capabilities

### 8.3 Extension Points

#### **Custom Agents**
- YAML-based agent definitions for easy customization
- Plugin architecture for domain-specific tools
- Custom compliance frameworks and validation rules
- Industry-specific assessment templates

#### **Document Templates**
- Customizable DOCX templates with company branding
- LaTeX templates for professional PDF generation
- Multi-language support for global deployments
- Custom report sections and formatting

---

## 9. Performance & Scalability

### 9.1 Performance Characteristics

#### **Response Times**
- API responses: < 200ms for typical operations
- Document processing: 1-5 minutes per MB of content
- Agent assessments: 10-30 minutes for comprehensive analysis
- Report generation: 2-5 minutes for professional documents

#### **Throughput Capacity**
- Concurrent projects: 50+ simultaneous assessments
- Document upload: 100MB+ files with progress tracking
- Real-time connections: 1000+ concurrent WebSocket clients
- Database operations: 10,000+ TPS with proper indexing

### 9.2 Scalability Patterns

#### **Microservices Scaling**
- Independent scaling per service based on demand
- Stateless service design for horizontal scaling
- Database read replicas for query performance
- Caching layers for frequently accessed data

#### **Data Tier Scaling**
- PostgreSQL connection pooling and read replicas
- Weaviate clustering for vector search performance
- Neo4j clustering for high-availability graph operations
- MinIO distributed mode for object storage scaling

### 9.3 Resource Optimization

#### **Memory Management**
- Efficient vector embedding storage and retrieval
- Graph database query optimization with indexes
- Connection pooling for database resources  
- Garbage collection tuning for Python services

#### **Storage Optimization**
- Document compression for archive storage
- Intelligent caching for frequently accessed data
- Tiered storage for cost optimization
- Automated cleanup of temporary processing files

---

## 10. Future Architecture Evolution

### 10.1 Planned Enhancements

#### **Message Bus Integration**
- NATS or RabbitMQ for asynchronous service communication
- Event-driven architecture for better decoupling
- Scalable task queuing for background processing
- Event sourcing for complete audit trails

#### **Advanced Analytics**
- Machine learning for assessment quality improvement  
- Predictive analytics for migration risk assessment
- Business intelligence dashboards for portfolio insights
- Automated recommendation engines

### 10.2 Technology Roadmap

#### **Q4 2025: Enhanced Automation**
- Automated cloud provider integrations
- Self-healing infrastructure monitoring  
- Advanced compliance automation
- Intelligent document classification

#### **Q1 2026: Enterprise Scale**
- Multi-tenant architecture for service providers
- Advanced RBAC with organizational hierarchies
- Enterprise SSO integration (SAML, OIDC)
- Advanced backup and disaster recovery

#### **Q2 2026: AI Evolution**
- Custom LLM fine-tuning for domain expertise
- Advanced reasoning with graph neural networks
- Automated code analysis and modernization recommendations
- Predictive migration outcome modeling

---

## 11. Conclusion

Nagarro's Ascent represents a significant advancement in enterprise cloud migration assessment platforms, combining cutting-edge AI technology with enterprise-grade architecture and security. The platform's microservices design, polyglot persistence, and specialized AI agents deliver unprecedented intelligence and automation for complex cloud transformation initiatives.

The architecture supports both current operational requirements and future scalability needs, with clear extension points for additional capabilities and integrations. The comprehensive security model, professional deliverables, and real-time monitoring capabilities position the platform as a market leader in the cloud migration assessment space.

Through its zero-trust deployment model and complete data isolation, Nagarro's Ascent addresses the critical security and compliance concerns of Fortune 500 organizations while delivering the deep technical insights and strategic recommendations necessary for successful cloud transformation initiatives.
