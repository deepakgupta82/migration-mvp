
# Nagarro's Ascent - Developer Onboarding Guide (2025-08-19)

Welcome! This guide covers architecture, setup, codebase, and contribution workflows for Nagarro's Ascent.

## 1. Introduction

Nagarro's Ascent is an enterprise-grade, agentic cloud migration assessment platform. It features:
- Multi-agent CrewAI orchestration (Discovery, Strategy, Design, Planning)
- RAG-powered chat and document synthesis
- Polyglot persistence: PostgreSQL, ChromaDB, Neo4j, MinIO
- Real-time logs, service health, and professional deliverables

## 2. Getting Started

### Prerequisites
- Docker Desktop (16GB RAM recommended)
- Python 3.11+
- Node.js 18+
- Git

### Startup Sequence
1. **Start Infrastructure:**
    - `docker-compose up -d postgres neo4j minio chromadb`
2. **Start Services (in order):**
    - Project Service: `cd project-service && python main.py`
    - Backend: `cd backend && python -m app.main`
    - Frontend: `cd frontend && npm start`
    - Reporting Service: `cd reporting-service && python main.py`
3. **Access Points:**
    - Frontend: http://localhost:3000
    - Backend API: http://localhost:8000
    - Project Service: http://localhost:8002
    - Reporting Service: http://localhost:8001

## 3. Codebase Structure

```
migration_platform_2/
├── backend/              # FastAPI app: agent orchestration, core APIs
├── frontend/             # React + TypeScript Command Center
├── project-service/      # FastAPI: state management, context fields
├── reporting-service/    # FastAPI: PDF/DOCX generation, MinIO
├── MegaParse/            # Document parsing service
├── k8s/                  # Kubernetes manifests
├── logs/                 # Platform, agent, and service logs
├── docker-compose.yml    # Local service orchestration
└── setup-platform.ps1    # Windows setup script
```

## 4. Key Services & Components

- **Project Service:** CRUD, file metadata, LLM config, rich context fields (overview, client summary, RFP, expectations, deliverables, timelines)
- **Backend:** CrewAI orchestration, RAGService (ChromaDB), GraphService (Neo4j), document generation, logs, chat
- **Reporting Service:** Markdown → PDF/DOCX, MinIO storage, download endpoints
- **Frontend:** Multi-tab UI, project CRUD, file upload, document generation, chat, logs, service health

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
