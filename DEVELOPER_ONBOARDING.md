
# Nagarro's Ascent - Developer Onboarding Guide

**Version:** 4.0 (Phase 2)  
**Last Updated:** August 24, 2025  
**Platform:** Microservices Architecture (12 Services)

Welcome! This guide covers the Phase 2 microservices architecture, setup, codebase, and contribution workflows for Nagarro's Ascent.

## 1. Introduction

Nagarro's Ascent is an enterprise-grade, agentic cloud migration assessment platform with a fully distributed microservices architecture. Phase 2 enhancements include:

### Core Capabilities
- **12-Service Microservices Architecture**: Distributed, scalable, independently deployable services
- **Service Discovery & Health Monitoring**: Centralized service registry with real-time health checks
- **Advanced Progress Tracking**: Real-time operation tracking with analytics and WebSocket broadcasting
- **Structured Document Processing**: Enhanced JSONL-based processing with unstructured.io
- **Native Cloud Integration**: Direct AWS, Azure, GCP integration for real-time assessments
- **Multi-Agent CrewAI Orchestration**: Enhanced with cloud assessment capabilities
- **Enhanced Real-Time Communication**: 9 WebSocket channels for different data streams
- **Polyglot Persistence**: PostgreSQL, Weaviate (upgraded), Neo4j, MinIO

### Phase 2 New Features
- **Service Registry** (8011): Distributed health monitoring, Docker integration
- **Cloud Tools Service** (8012): Native cloud provider integrations
- **Enhanced WebSocket Service**: Multi-channel progress tracking and analytics
- **Structured Document Processing**: JSONL output with semantic enrichment
- **Advanced Progress Tracking**: Operation lifecycle management with real-time updates

## 2. Getting Started (Phase 2 Architecture)

### Prerequisites
- Docker Desktop (24GB RAM recommended for 12 services)
- Python 3.11+ (3.10 for backend)
- Node.js 18+
- Git

### Quick Start (Recommended)
```bash
# Windows automated setup
.\setup-platform.ps1

# Health check all services
.\health-check.bat
```

### Manual Startup Sequence
1. **Start Infrastructure:**
   ```bash
   docker-compose up -d postgres neo4j minio weaviate
   ```

2. **Start Core Services (in order):**
   ```bash
   # Service Registry (must start first)
   cd services/service-registry && python main.py
   
   # Core services
   cd services/project-service && python main.py     # 8010
   cd backend && python -m app.main                  # 8000
   cd services/llm-service && python main.py         # 8001
   cd services/vector-service && python main.py      # 8002
   cd services/document-service && python main.py    # 8003
   cd services/storage-service && python main.py     # 8004
   cd services/graph-service && python main.py       # 8005
   cd services/ai-agent-service && python main.py    # 8006
   cd services/data-importer-service && python main.py # 8007
   cd services/reporting-service && python main.py   # 8008
   cd services/websocket-service && python main.py   # 8009
   cd services/cloud-tools-service && python main.py # 8012
   
   # Frontend (start last)
   cd frontend && npm start                           # 3000
   ```

### Access Points (Phase 2)
```
Frontend Command Center:    http://localhost:3000
Backend API:               http://localhost:8000
LLM Service:               http://localhost:8001
Vector Service (Weaviate): http://localhost:8002
Document Service:          http://localhost:8003
Storage Service (MinIO):   http://localhost:8004
Graph Service (Neo4j):     http://localhost:8005
AI Agent Service:          http://localhost:8006
Data Importer Service:     http://localhost:8007
Reporting Service:         http://localhost:8008
WebSocket Service:         http://localhost:8009
Project Service:           http://localhost:8010
Service Registry:          http://localhost:8011  # NEW
Cloud Tools Service:       http://localhost:8012  # NEW

# Monitoring endpoints
Service Health Dashboard:   http://localhost:8011/services
Progress Analytics:         http://localhost:8009/analytics/summary
```

## 3. Codebase Structure (Phase 2 Microservices)

```
migration_platform_2/
├── services/                    # Phase 2 Microservices
│   ├── service-registry/        # Service discovery & health monitoring (8011)
│   ├── ai-agent-service/        # CrewAI agent execution (8006)
│   ├── data-importer-service/   # Bulk data ingestion (8007)
│   ├── document-service/        # Enhanced document processing (8003)
│   ├── graph-service/           # Neo4j graph operations (8005)
│   ├── llm-service/             # Language model management (8001)
│   ├── reporting-service/       # PDF/DOCX generation (8008)
│   ├── storage-service/         # MinIO object storage (8004)
│   ├── vector-service/          # Weaviate embeddings (8002)
│   ├── websocket-service/       # Enhanced real-time communication (8009)
│   ├── project-service/         # Moved to services/ (8010)
│   └── cloud-tools-service/     # Cloud integrations (8012)
├── backend/                     # API Gateway & orchestration (8000)
├── frontend/                    # React Command Center (3000)
├── common/                      # Shared utilities and models
├── config/                      # Configuration management
├── k8s/                         # Kubernetes manifests (updated)
├── scripts/                     # Utility scripts and tools
├── logs/                        # Distributed logging
├── docker-compose.microservices.yml  # 12-service orchestration
└── setup-platform.ps1          # Enhanced setup script
```

## 4. Key Services & Components (Phase 2)

### Core Infrastructure Services
- **Service Registry (8011)**: Service discovery, health monitoring, Docker integration
- **WebSocket Service (8009)**: 9-channel real-time communication, progress tracking
- **Project Service (8010)**: State management, context fields, PostgreSQL
- **Storage Service (8004)**: MinIO object storage, file management

### AI & Processing Services  
- **Backend (8000)**: API Gateway, CrewAI orchestration, request routing
- **AI Agent Service (8006)**: CrewAI agent execution, workflow management
- **LLM Service (8001)**: Language model management, inference
- **Document Service (8003)**: Enhanced processing with unstructured.io, JSONL output
- **Vector Service (8002)**: Weaviate embeddings, semantic search
- **Graph Service (8005)**: Neo4j operations, relationship management

### Specialized Services
- **Cloud Tools Service (8012)**: Native AWS/Azure/GCP integration, assessments
- **Data Importer Service (8007)**: Bulk data ingestion, ETL operations
- **Reporting Service (8008)**: PDF/DOCX generation, professional deliverables

### Frontend
- **Command Center (3000)**: Enhanced multi-tab UI with service monitoring, progress dashboards

## 5. Data Flow Walkthroughs

### Project Creation & Context
1. User creates project in UI
2. Frontend calls backend → project-service
3. ProjectService stores project, context fields, LLM config in PostgreSQL
4. Context fields indexed to ChromaDB and Neo4j
5. UI updates with new project

### Document Processing & Generation
1. User uploads files in UI
2. Files stored in MinIO, parsed to Markdown
3. Backend indexes content to ChromaDB and Neo4j
4. CrewAI agents generate Markdown report
5. Reporting Service converts to PDF/DOCX, stores in MinIO
6. UI provides download links

### Logs & Observability
1. UI global log pane fetches logs via REST/WebSocket
2. Logs filterable by service, correlation ID, project, time, level
3. Service health/status shown in UI

### Agentic Assessment & Chat
1. CrewAI agents use context fields, indexed docs, and graph for synthesis
2. Chat interface uses RAGService for context-aware answers
3. All agent actions logged for auditability

## 6. How to Contribute

### Add a New Project Field (e.g., "priority")
1. **Database:** Add column to `ProjectModel` in `project-service/database.py`
2. **API Schema:** Add field to Pydantic models in `project-service/schemas.py`
3. **API Logic:** Update endpoint in `project-service/main.py` if needed
4. **Frontend UI:** Add input in project creation/edit modal
5. **Frontend State:** Update API call in `useProjects.ts`
6. **Display:** Add column to projects table

### Add a New Agent Tool
1. **Tool Logic:** Create Python class/function (e.g., `get_stock_price`)
2. **CrewAI Tool:** Import and instantiate in `backend/app/core/crew.py`
3. **Assign Tool:** Add to agent's tool list in crew definition
4. **Update Agent Goal/Task:** Mention tool in agent's goal/task description

## 7. Recent Enhancements (2025-08-19)

- Project context fields: overview, client summary, RFP, expectations, deliverables, timelines
- End-to-end context indexing: ChromaDB, Neo4j, agent/crew workflows
- Document generation: Markdown → PDF/DOCX, MinIO storage, download endpoints
- Enhanced logs: REST + WebSocket, multi-service filtering
- UI: Exported Documents tab, service health panel, global log pane, context editing
- Maximizable for detailed log analysis

**Service Management:**
- Platform services status panel in Settings
- Real-time health monitoring for all services
- Start/Stop/Restart capabilities for local services
- Live logs for service operations
- Service dependency tracking

**Project History:**
- Complete activity timeline for all project actions
- Detailed metadata for each activity
- Expandable details with JSON data
- Filtering by activity type
- Timestamp tracking for audit purposes

**Enhanced UI Components:**
- Improved navigation and user experience
- Better error handling and loading states
- Responsive design improvements
- Consistent styling across components

### Development Improvements

**Local Development:**
- Comprehensive `localdevstart.md` guide
- Step-by-step service startup instructions
- Troubleshooting section for common issues
- Rancher Desktop specific instructions

**Documentation:**
- `chatlog.md` for conversation history
- Updated architecture documentation
- Enhanced developer guides
- Code organization improvements

### How to Use New Features

**Accessing Logs:**
1. Click the collapsible arrow on the right side of any page
2. Select the log type (Platform/Agents/Assessment)
3. Use filters and controls to customize the view
4. Download logs for offline analysis

**Managing Services:**
1. Go to Settings → Platform Services tab
2. View real-time status of all services
3. Use action buttons to start/stop/restart services
4. Click logs button to view service-specific logs

**Viewing Project History:**
1. Open any project
2. Navigate to the History tab
3. Filter activities by type
4. Expand entries to see detailed information

---

**Happy Coding!**

This guide should provide a solid foundation for understanding and contributing to the **Nagarro's Ascent** platform. For any further questions, please refer to the `README.md`, `localdevstart.md`, or the source code itself.

---

## 8. Technology Stack Summary

### Frontend Technologies
- **React 18** with TypeScript for type safety and modern development
- **Mantine v7** for professional UI components and consistent design
- **React Router v6** for client-side routing and navigation
- **React Force Graph 2D** for interactive dependency visualizations
- **Axios** for HTTP client with comprehensive error handling
- **WebSockets** for real-time communication with backend services

### Backend Technologies  
- **FastAPI** with Python 3.11 for high-performance APIs
- **CrewAI Framework** for multi-agent AI orchestration
- **LangChain** for LLM integration and tool management
- **SQLAlchemy** for database ORM and relationship management
- **Pydantic** for data validation and serialization
- **JWT** for secure authentication and authorization

### AI & Machine Learning
- **OpenAI GPT-4** (primary LLM provider)
- **Google Gemini** and **Anthropic Claude** (secondary providers)
- **SentenceTransformers** for document embeddings
- **Weaviate** for vector similarity search
- **Neo4j** for graph-based dependency analysis

### Infrastructure & DevOps
- **Docker & Docker Compose** for containerized development
- **PostgreSQL 15** for relational data storage
- **MinIO** for S3-compatible object storage
- **Kubernetes** manifests for production deployment
- **Health Checks** and **Monitoring** for operational excellence

---

## 9. Development Best Practices

### Code Organization
- Follow **Domain-Driven Design** principles with clear service boundaries
- Use **TypeScript** for frontend type safety and better developer experience
- Implement **Pydantic models** for backend data validation
- Maintain **comprehensive error handling** across all services
- Write **self-documenting code** with clear variable and function names

### Testing Strategy
- **Unit Tests** for individual components and functions
- **Integration Tests** for service-to-service communication
- **End-to-End Tests** for complete user workflows
- **API Testing** with automated endpoint validation
- **Performance Testing** for document processing pipelines

### Security Considerations
- **JWT Authentication** with proper token expiration
- **Input Validation** using Pydantic schemas
- **API Key Encryption** for LLM provider credentials
- **RBAC Authorization** with user and admin roles
- **Audit Logging** for all user actions and agent activities

### Performance Optimization
- **Lazy Loading** of components and data
- **Connection Pooling** for database connections
- **Caching Strategies** for frequently accessed data
- **Asynchronous Processing** for long-running tasks
- **WebSocket Communication** for real-time updates

---

**Platform Version:** Nagarro's Ascent v2.0  
**Last Updated:** August 6, 2025  
**Documentation Status:** Current

---

# Developer Onboarding

**Revision:** 2.4  
**Last Updated:** Aug 11 2025

## Quick Delta (What's New Since 2.3)
- Stats subsystem now uses cached snapshots. Prefer `GET /api/platform/stats-fast` & project list `GET /api/projects?include_stats=true` for UI initial loads.
- Added per-project `GET /api/projects/{id}/stats-snapshot` for lightweight refresh.
- Event Bus introduced (in-process). Publish helpers already wired for: `project_created`, `project_deleted`, `document_uploaded`. Embedding & delete events coming soon.
- Crew Config now fully manageable via REST: `GET/PUT /api/crew-config`, `POST /api/crew-config/reload` plus WebSocket for live pushes.
- Logs tail available via `GET /api/logs?lines=200` (also WS stream if enabled).
- Instrumentation timings included in stats responses under `timings` key for performance profiling.

## Getting Started (unchanged core steps)
<!-- existing onboarding content remains below -->
