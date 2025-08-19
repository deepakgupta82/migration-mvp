# Migration Platform - Detailed Project Structure with Functions & Components

## Root Directory
```
migration_platform_2/
├── README.md                           # Project documentation
├── CHANGELOG.md                        # Version history
├── DEVELOPER_ONBOARDING.md            # Developer setup guide
├── ENTERPRISE_ARCHITECTURE.md         # Architecture documentation
├── QUICK_START.md                     # Quick setup instructions
├── WINDOWS_SETUP.md                   # Windows-specific setup
├── overview_and_mvp.md                # Project overview and MVP requirements
├── docker-compose.yml                 # Main Docker Compose configuration
├── docker-compose.dev.yml             # Development environment config
├── docker-compose.optimized.yml       # Optimized production config
├── setup-platform.ps1                 # Main platform setup script (Windows)
├── start-platform-dev.ps1             # Development startup script
├── build-all.ps1                      # Build all Docker images script
    │   │   ├── Progress tracking
    │   ├── LLMConfigurationModal.tsx  # LLM setup modal
    │   │       └── Content area

# Migration Platform - Detailed Project Structure (2025-08-19)

## Root Directory
```
migration_platform_2/
├── README.md                 # Project documentation
├── CHANGELOG.md              # Version history
├── DEVELOPER_ONBOARDING.md   # Developer setup guide
├── ENTERPRISE_ARCHITECTURE.md# Architecture documentation
├── overview_and_mvp.md       # Platform overview
├── docker-compose.yml        # Main Docker Compose config
├── setup-platform.ps1        # Windows setup script
├── logs/                     # Platform, agent, and service logs
├── k8s/                      # Kubernetes manifests
├── database/                 # Migration scripts
├── ...                       # Other scripts and configs
```

## Backend Service (FastAPI)
```
backend/
├── Dockerfile
├── requirements.txt
├── crew_definitions.yaml      # CrewAI agent configurations
└── app/
    ├── main.py               # FastAPI entry point
    ├── core/
    │   ├── crew.py           # CrewAI orchestration
    │   ├── rag_service.py    # ChromaDB vector search
    │   ├── graph_service.py  # Neo4j graph operations
    │   ├── project_service.py# Project service client
    │   └── ...
    ├── routers/
    │   ├── projects_router.py# Project endpoints
    │   ├── logs_router.py    # Logs endpoints
    │   └── ...
    └── tools/
        ├── project_knowledge_base_tool.py
        └── ...
```

## Frontend Service (React TypeScript)
```
frontend/
├── Dockerfile
├── package.json
├── tsconfig.json
└── src/
    ├── App.tsx
    ├── views/
    │   ├── DashboardView.tsx
    │   ├── ProjectsView.tsx
    │   ├── ProjectDetailView.tsx
    │   ├── SettingsView.tsx
    │   └── ...
    ├── components/
    │   ├── FileUpload.tsx
    │   ├── DocumentTemplates.tsx
    │   ├── ChatInterface.tsx
    │   ├── GraphVisualizer.tsx
    │   └── ...
    ├── services/api.ts
    ├── contexts/AssessmentContext.tsx
    └── hooks/useProjects.ts
```

## Microservices

### Project Service (FastAPI)
```
project-service/
├── Dockerfile
├── requirements.txt
├── main.py                # FastAPI entry point
├── database.py            # PostgreSQL connection, ProjectModel
├── schemas.py             # Pydantic schemas (ProjectCreate, Update, Response)
├── auth.py                # JWT authentication
└── ...
```

### Reporting Service (FastAPI)
```
reporting-service/
├── Dockerfile
├── requirements.txt
├── main.py                # FastAPI: Markdown → PDF/DOCX, MinIO
└── ...
```

### MegaParse Service
```
MegaParse/
├── Dockerfile
├── requirements.lock
├── main.py                # Document parsing API
└── ...
```

## Shared Libraries
```
common/
├── adapters/
├── auth/
├── config/
├── logging/
├── project_context.py      # Project context management
└── ...
```

## Configuration & Infrastructure
```
config/
├── base/
├── environments/
├── config.local.json
├── config.dev-aws.json
└── client_profile.json

    │   ├── settings/
├── backend-deployment.yaml
├── frontend-deployment.yaml
├── postgres-deployment.yaml
├── neo4j-deployment.yaml
├── minio-deployment.yaml
├── project-service-deployment.yaml
├── reporting-service-deployment.yaml
└── secrets.yaml

    │   │   ├── AIAgentsPanel.tsx      # Configure AI agent roles and capabilities
└── migrations/
```

## Logs
```
logs/
├── platform.log
├── agents.log
├── database.log
└── ...
```

## Key Endpoints & Components

### Backend Endpoints (main.py, routers/*)
- **Projects:** CRUD, context fields, file metadata, LLM config
- **Document Processing:** Upload, parse, index, generate report
- **Knowledge Graph:** Neo4j graph, context nodes, relationships
- **CrewAI:** Agent orchestration, document generation, chat
- **Logs:** REST + WebSocket, multi-service filtering
- **Service Health:** Status endpoints

### Frontend Components
- **Main Views:** DashboardView, ProjectsView, ProjectDetailView, SettingsView
- **Project Detail:** ChatInterface, GraphVisualizer, DocumentTemplates, CrewInteractionViewer
- **Settings:** ServiceStatusPanel, GlobalDocumentTemplates
- **Utilities:** FileUpload, LLMConfigSelector, ServiceHealthBanner, ReportDisplay
- **Layout:** AppLayout, SystemLogsViewer, NotificationDropdown

### Core Services
- **AI Orchestration:** crew.py (CrewAI management, agent coordination)
- **Data Services:** rag_service.py (ChromaDB), graph_service.py (Neo4j)
- **Project Management:** project_service.py (CRUD, context fields)
- **Reporting:** Markdown → PDF/DOCX, MinIO storage
- **Logs:** REST/WebSocket, filtering, audit trail

---
    │   │   │   ├── AIAgentsPanel()    # Main agents panel
    │   │   │   ├── Agent configuration
    │   │   │   ├── Backstory editing
    │   │   │   └── Tool assignment
    │   │   │
    │   │   ├── ServiceStatusPanel.tsx # Monitor and manage service health
    │   │   │   ├── ServiceStatusPanel() # Service monitoring
    │   │   │   ├── Health indicators
    │   │   │   └── Service controls
    │   │   │
    │   │   ├── GlobalDocumentTemplates.tsx # Manage document templates
    │   │   └── EnvironmentVariablesPanel.tsx # Configure environment variables
    │   │
    │   └── notifications/
    │       └── NotificationDropdown.tsx # System notification dropdown
    │
    ├── services/
    │   └── api.ts                     # API client service
    │       ├── ApiClient class        # Main API client
    │       ├── Project Management APIs:
    │       │   ├── getProjects()      # Fetch all projects
    │       │   ├── getProject()       # Fetch single project
    │       │   ├── createProject()    # Create new project
    │       │   ├── updateProject()    # Update project
    │       │   └── deleteProject()    # Delete project
    │       ├── File Management APIs:
    │       │   ├── uploadFiles()      # Upload project files
    │       │   ├── getProjectFiles()  # List project files
    │       │   └── deleteProjectFile() # Delete project file
    │       ├── LLM Configuration APIs:
    │       │   ├── getLLMConfigurations() # List LLM configs
    │       │   ├── createLLMConfiguration() # Create LLM config
    │       │   ├── updateLLMConfiguration() # Update LLM config
    │       │   └── deleteLLMConfiguration() # Delete LLM config
    │       └── System APIs:
    │           ├── getServiceHealth() # Service health check
    │           ├── getPlatformStats() # Platform statistics
    │           └── testLLMConnection() # Test LLM connectivity
    │
    ├── hooks/
    │   └── useProjects.ts             # Projects data hook
    │       ├── useProjects()          # Projects state management
    │       ├── useProjectStats()      # Project statistics
    │       └── Data fetching logic
    │
    └── contexts/
        ├── AssessmentContext.tsx      # Assessment state context
        ├── LLMConfigContext.tsx       # LLM configuration context
        └── NotificationContext.tsx    # Notification state context
```
## Microservices

### Project Service (FastAPI)
```
project-service/
├── Dockerfile                         # Project service container
├── requirements.txt                   # Python dependencies
├── main.py                            # FastAPI service entry point
│   ├── API Endpoints:
│   │   ├── health()                   # GET /health - Service health check
│   │   ├── db_version()               # GET /db/version - PostgreSQL version
│   │   ├── create_project()           # POST /projects - Create project
│   │   ├── get_projects()             # GET /projects - List projects
│   │   ├── get_project()              # GET /projects/{id} - Get project
│   │   ├── update_project()           # PUT /projects/{id} - Update project
│   │   ├── delete_project()           # DELETE /projects/{id} - Delete project
│   │   ├── create_llm_configuration() # POST /llm-configurations - Create LLM config
│   │   ├── get_llm_configurations()   # GET /llm-configurations - List LLM configs
│   │   ├── update_llm_configuration() # PUT /llm-configurations/{id} - Update LLM config
│   │   ├── delete_llm_configuration() # DELETE /llm-configurations/{id} - Delete LLM config
│   │   ├── add_project_file()         # POST /projects/{id}/files - Add file
│   │   ├── get_project_files()        # GET /projects/{id}/files - List files
│   │   └── delete_project_file()      # DELETE /projects/{id}/files/{file_id} - Delete file
│   └── Database Operations:
│       ├── PostgreSQL connection management
│       ├── Project CRUD operations
│       ├── File metadata management
│       └── LLM configuration storage
├── database.py                        # PostgreSQL database connection
├── schemas.py                         # Pydantic data schemas
│   ├── ProjectCreate                  # Project creation schema
│   ├── ProjectUpdate                  # Project update schema
│   ├── ProjectResponse                # Project response schema
│   ├── LLMConfigurationCreate         # LLM config creation schema
│   ├── LLMConfigurationResponse       # LLM config response schema
│   └── FileCreate                     # File creation schema
├── auth.py                            # Authentication logic
└── start_service.py                   # Service startup script
```

### Reporting Service (FastAPI)
```
reporting-service/
├── Dockerfile                         # Reporting service container
├── requirements.txt                   # Python dependencies
├── main.py                            # FastAPI service for document generation
│   ├── API Endpoints:
│   │   ├── health()                   # GET /health - Service health check
│   │   ├── generate_report()          # POST /generate-report - Generate document
│   │   ├── get_report_status()        # GET /reports/{id}/status - Report status
│   │   └── download_report()          # GET /reports/{id}/download - Download report
│   └── Document Generation:
│       ├── Template processing
│       ├── PDF generation (LaTeX)
│       ├── DOCX generation (pypandoc)
│       ├── MinIO storage integration
│       └── Progress tracking
└── template_note.md                   # Template documentation
```

### MegaParse Service (Document Parsing)
```
MegaParse/
├── Dockerfile                         # MegaParse container
├── requirements.lock                  # Python dependencies
├── API Endpoints:
│   ├── parse_document()               # POST /parse - Parse document
│   ├── get_supported_formats()        # GET /formats - Supported formats
│   └── health_check()                 # GET /health - Service health
└── Document Processing:
    ├── PDF parsing
    ├── DOCX parsing
    ├── Text extraction
    ├── Metadata extraction
    └── Structured output generation
```

## Shared Libraries
```
common/
├── adapters/                          # External service adapters
├── auth/                              # Authentication utilities
├── config/                            # Configuration management
├── cqrs/                              # CQRS pattern implementation
├── exceptions/                        # Custom exception classes
├── http/                              # HTTP utilities
├── interfaces/                        # Interface definitions
├── logging/                           # Logging utilities
├── middleware/                        # Middleware components
├── dependency_container.py            # Dependency injection container
└── project_context.py                 # Project context management
```

## Configuration & Infrastructure
```
config/
├── base/                              # Base configuration templates
├── environments/                      # Environment-specific configs
├── config.local.json                 # Local development config
├── config.dev-aws.json               # AWS development config
└── client_profile.json               # Client profile configuration

scripts/
├── init-postgres.sql                 # PostgreSQL initialization
├── init-neo4j.cypher                 # Neo4j initialization
├── init-minio.py                     # MinIO initialization
├── init-weaviate.py                  # Weaviate initialization
└── requirements-init.txt             # Initialization script dependencies

k8s/
├── backend-deployment.yaml           # Backend Kubernetes deployment
├── frontend-deployment.yaml          # Frontend Kubernetes deployment
├── postgres-deployment.yaml          # PostgreSQL deployment
├── neo4j-deployment.yaml             # Neo4j deployment
├── weaviate-deployment.yaml          # Weaviate deployment
├── minio-deployment.yaml             # MinIO deployment
├── project-service-deployment.yaml   # Project service deployment
├── reporting-service-deployment.yaml # Reporting service deployment
├── megaparse-deployment.yaml         # MegaParse deployment
└── secrets.yaml                      # Kubernetes secrets

terraform/
├── aws/                              # AWS deployment configurations
└── azure/                            # Azure deployment configurations

database/
└── migrations/                       # Database migration scripts

logs/
├── platform.log                     # Main platform logs
├── agents.log                        # AI agent logs
├── database.log                      # Database operation logs
└── [timestamped build logs]          # Build and deployment logs
```

## Quick Function/Component Finder

### Backend Functions (main.py - 54 endpoints)
- **Health & Status**: `health_check()`, `llm_configurations_health()`, `get_system_services()`
- **Projects**: `create_project_endpoint()`, `get_projects()`, `get_project()`, `update_project()`, `delete_project()`
- **LLM Management**: `list_llm_configurations()`, `create_llm_configuration()`, `test_llm_connection()`
- **Document Processing**: `process_project_documents()`, `upload_files()`, `generate_infrastructure_report()`
- **Knowledge Graph**: `get_project_graph()`, `query_project_knowledge()`, `clear_project_data()`
- **AI Crew**: `get_crew_interactions()`, `get_crew_definitions_endpoint()`, `generate_document()`
- **Platform Stats**: `platform_stats()`, `get_project_stats()`, `get_projects_stats()`
- **Fast Stats**: `get_platform_stats_fast()`, `get_project_stats_snapshot()`
- **Logs**: `get_logs()`

### Frontend Components
- **Main Views**: `DashboardView`, `ProjectsView`, `ProjectDetailView`, `SettingsView`
- **Project Detail**: `ChatInterface`, `GraphVisualizer`, `DocumentTemplates`, `CrewInteractionViewer`
- **Settings**: `AIAgentsPanel`, `ServiceStatusPanel`, `GlobalDocumentTemplates`
- **Utilities**: `FileUpload`, `LLMConfigSelector`, `ServiceHealthBanner`, `ReportDisplay`
- **Layout**: `AppLayout`, `SystemLogsViewer`, `NotificationDropdown`

### Core Services
- **AI Orchestration**: `crew.py` - CrewAI management, LLM initialization, agent coordination
- **Data Services**: `rag_service.py` - Vector search, `graph_service.py` - Neo4j operations
- **Project Management**: `project_service.py` - Project service client, CRUD operations
- **Statistics**: `platform_stats.py` - Platform-wide metrics aggregation
- **Event Bus**: `event_bus.py` - Inter-service communication via events