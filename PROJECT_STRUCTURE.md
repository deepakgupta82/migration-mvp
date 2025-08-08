# Migration Platform - Complete Project Structure

## Root Directory Structure

```
migration_platform_2/
├── README.md                           # Main project documentation
├── CHANGELOG.md                        # Version history and changes
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
├── health-check.bat                   # Service health check script
│
├── backend/                           # Main FastAPI backend service
│   ├── Dockerfile                     # Backend container definition
│   ├── requirements.txt               # Python dependencies
│   ├── start_backend.py               # Backend startup script
│   ├── crew_definitions.yaml          # AI agent crew configurations
│   └── app/
│       ├── main.py                    # FastAPI application entry point
│       ├── llm_configurations.json   # LLM provider configurations
│       ├── core/                      # Core business logic
│       │   ├── crew.py                # CrewAI orchestration
│       │   ├── crew_config_service.py # Crew configuration management
│       │   ├── crew_factory.py        # Crew instance factory
│       │   ├── crew_loader.py         # Crew definition loader
│       │   ├── crew_logger.py         # Crew interaction logging
│       │   ├── embedding_service.py   # Vector embedding service
│       │   ├── entity_extraction_agent.py # Entity extraction logic
│       │   ├── graph_service.py       # Neo4j graph database service
│       │   ├── platform_stats.py      # Platform-wide statistics
│       │   ├── project_service.py     # Project service client
│       │   └── rag_service.py         # RAG (Retrieval Augmented Generation)
│       ├── agents/                    # AI agent definitions
│       │   └── agent_definitions.py   # Agent roles and backstories
│       ├── tools/                     # AI agent tools
│       │   ├── cloud_catalog_tool.py  # Cloud service catalog tool
│       │   ├── compliance_tool.py     # Compliance checking tool
│       │   ├── enhanced_rag_tool.py   # Advanced RAG queries
│       │   ├── graph_query_tool.py    # Neo4j graph queries
│       │   ├── hybrid_search_tool.py  # Hybrid vector/keyword search
│       │   ├── infrastructure_analysis_tool.py # Infrastructure analysis
│       │   ├── lessons_learned_tool.py # Historical lessons tool
│       │   └── project_knowledge_base_tool.py # Project-specific KB
│       ├── models/                    # Data models
│       │   └── crew_interaction.py    # Crew interaction data model
│       └── utils/                     # Utility functions
│           ├── config_parsers.py      # Configuration parsing
│           ├── cypher_generator.py    # Neo4j Cypher query generation
│           └── semantic_chunker.py    # Document semantic chunking
│
├── frontend/                          # React TypeScript frontend
│   ├── Dockerfile                     # Frontend container definition
│   ├── package.json                   # Node.js dependencies
│   ├── tsconfig.json                  # TypeScript configuration
│   ├── nginx.conf                     # Nginx configuration for production
│   └── src/
│       ├── App.tsx                    # Main React application component
│       ├── index.tsx                  # React application entry point
│       ├── views/                     # Main application views/pages
│       │   ├── DashboardView.tsx      # Dashboard with platform metrics
│       │   ├── ProjectsView.tsx       # Projects list and creation
│       │   ├── ProjectDetailView.tsx  # Individual project details
│       │   ├── SettingsView.tsx       # Global settings and configuration
│       │   ├── LogsView.tsx           # Application logs viewer
│       │   ├── SystemLogsView.tsx     # System-level logs
│       │   └── CrewManagementView.tsx # AI crew management
│       ├── components/                # Reusable React components
│       │   ├── ServiceHealthBanner.tsx # Service status banner
│       │   ├── FileUpload.tsx         # File upload component
│       │   ├── LLMConfigSelector.tsx  # LLM configuration selector
│       │   ├── LLMConfigurationModal.tsx # LLM setup modal
│       │   ├── FloatingChatWidget.tsx # Chat interface widget
│       │   ├── ReportDisplay.tsx      # Document report display
│       │   ├── LiveConsole.tsx        # Real-time console output
│       │   ├── layout/
│       │   │   └── AppLayout.tsx      # Main application layout
│       │   ├── admin/
│       │   │   ├── SystemLogsViewer.tsx # System administration logs
│       │   │   └── ModernConsole.tsx  # Modern console interface
│       │   ├── project-detail/
│       │   │   ├── ChatInterface.tsx  # Project chat interface
│       │   │   ├── GraphVisualizer.tsx # Knowledge graph visualization
│       │   │   ├── DocumentTemplates.tsx # Document template management
│       │   │   ├── CrewInteractionViewer.tsx # AI crew interactions
│       │   │   ├── AgentActivityLog.tsx # Agent activity tracking
│       │   │   └── ProjectHistory.tsx # Project change history
│       │   ├── settings/
│       │   │   ├── AIAgentsPanel.tsx  # AI agent configuration
│       │   │   ├── ServiceStatusPanel.tsx # Service status management
│       │   │   ├── GlobalDocumentTemplates.tsx # Global templates
│       │   │   └── EnvironmentVariablesPanel.tsx # Environment config
│       │   └── notifications/
│       │       └── NotificationDropdown.tsx # Notification system
│       ├── services/
│       │   └── api.ts                 # API client service
│       ├── hooks/
│       │   └── useProjects.ts         # Projects data hook
│       └── contexts/
│           ├── AssessmentContext.tsx  # Assessment state context
│           ├── LLMConfigContext.tsx   # LLM configuration context
│           └── NotificationContext.tsx # Notification state context
│
├── project-service/                   # Project management microservice
│   ├── Dockerfile                     # Project service container
│   ├── requirements.txt               # Python dependencies
│   ├── main.py                        # FastAPI service entry point
│   ├── database.py                    # PostgreSQL database connection
│   ├── schemas.py                     # Pydantic data schemas
│   ├── auth.py                        # Authentication logic
│   └── start_service.py               # Service startup script
│
├── reporting-service/                 # Document generation microservice
│   ├── Dockerfile                     # Reporting service container
│   ├── requirements.txt               # Python dependencies
│   ├── main.py                        # FastAPI service for document generation
│   └── template_note.md               # Template documentation
│
├── MegaParse/                         # Document parsing service (submodule)
│   ├── Dockerfile                     # MegaParse container
│   ├── requirements.lock              # Python dependencies
│   └── [MegaParse source files]       # Document parsing implementation
│
├── common/                            # Shared libraries and utilities
│   ├── adapters/                      # External service adapters
│   ├── auth/                          # Authentication utilities
│   ├── config/                        # Configuration management
│   ├── cqrs/                          # CQRS pattern implementation
│   ├── exceptions/                    # Custom exception classes
│   ├── http/                          # HTTP utilities
│   ├── interfaces/                    # Interface definitions
│   ├── logging/                       # Logging utilities
│   ├── middleware/                    # Middleware components
│   ├── dependency_container.py        # Dependency injection container
│   └── project_context.py             # Project context management
│
├── config/                            # Configuration files
│   ├── base/                          # Base configuration templates
│   ├── environments/                  # Environment-specific configs
│   ├── config.local.json              # Local development config
│   ├── config.dev-aws.json            # AWS development config
│   └── client_profile.json            # Client profile configuration
│
├── scripts/                           # Initialization and utility scripts
│   ├── init-postgres.sql              # PostgreSQL initialization
│   ├── init-neo4j.cypher              # Neo4j initialization
│   ├── init-minio.py                  # MinIO initialization
│   ├── init-weaviate.py               # Weaviate initialization
│   └── requirements-init.txt          # Initialization script dependencies
│
├── k8s/                               # Kubernetes deployment manifests
│   ├── backend-deployment.yaml        # Backend Kubernetes deployment
│   ├── frontend-deployment.yaml       # Frontend Kubernetes deployment
│   ├── postgres-deployment.yaml       # PostgreSQL deployment
│   ├── neo4j-deployment.yaml          # Neo4j deployment
│   ├── weaviate-deployment.yaml       # Weaviate deployment
│   ├── minio-deployment.yaml          # MinIO deployment
│   ├── project-service-deployment.yaml # Project service deployment
│   ├── reporting-service-deployment.yaml # Reporting service deployment
│   ├── megaparse-deployment.yaml      # MegaParse deployment
│   └── secrets.yaml                   # Kubernetes secrets
│
├── terraform/                         # Infrastructure as Code
│   ├── aws/                           # AWS deployment configurations
│   └── azure/                         # Azure deployment configurations
│
├── database/                          # Database schemas and migrations
│   └── migrations/                    # Database migration scripts
│
└── logs/                              # Application logs directory
    ├── platform.log                   # Main platform logs
    ├── agents.log                     # AI agent logs
    ├── database.log                   # Database operation logs
    └── [timestamped build logs]       # Build and deployment logs
```

## Frontend UI Components and Panels Reference

### Main Views (Pages)
- **DashboardView.tsx** - Platform overview with metrics cards (Total Projects, Active Projects, Total Documents, Total Embeddings, Neo4j Nodes/Relationships)
- **ProjectsView.tsx** - Project list table, create new project modal with LLM configuration
- **ProjectDetailView.tsx** - Tabbed interface: Overview, Files, Knowledge Graph, Interactive Discovery, Document Generation, Crew Interactions
- **SettingsView.tsx** - Tabbed settings: AI Agents, Service Status, Global Templates, Environment Variables
- **LogsView.tsx** - Application-level log viewer with filtering
- **SystemLogsView.tsx** - System administration logs and service health
- **CrewManagementView.tsx** - AI crew configuration and management

### Layout Components
- **AppLayout.tsx** - Main application shell with sidebar navigation, header, and content area
- **ServiceHealthBanner.tsx** - Top banner showing service status with expandable details and refresh button

### Project Detail Tabs/Panels
- **ChatInterface.tsx** - Real-time chat with AI agents
- **GraphVisualizer.tsx** - Interactive Neo4j knowledge graph visualization
- **DocumentTemplates.tsx** - Document template selection and management
- **CrewInteractionViewer.tsx** - AI agent conversation history and logs
- **AgentActivityLog.tsx** - Individual agent activity tracking
- **ProjectHistory.tsx** - Project change and activity history

### Settings Panels
- **AIAgentsPanel.tsx** - Configure AI agent roles, backstories, and capabilities
- **ServiceStatusPanel.tsx** - Monitor and manage service health status
- **GlobalDocumentTemplates.tsx** - Manage document templates across all projects
- **EnvironmentVariablesPanel.tsx** - Configure environment variables and API keys

### Utility Components
- **FileUpload.tsx** - Drag-and-drop file upload with progress tracking
- **LLMConfigSelector.tsx** - Dropdown selector for LLM configurations
- **LLMConfigurationModal.tsx** - Modal for creating/editing LLM configurations
- **FloatingChatWidget.tsx** - Floating chat interface widget
- **ReportDisplay.tsx** - Document report viewer with download capabilities
- **LiveConsole.tsx** - Real-time console output display
- **NotificationDropdown.tsx** - System notification dropdown menu

### Admin Components
- **SystemLogsViewer.tsx** - System logs with service health overview, database versions
- **ModernConsole.tsx** - Modern terminal-style console interface

## Backend API Endpoints Reference

### Project Management
- `GET /projects` - List all projects
- `POST /projects` - Create new project with LLM configuration
- `GET /projects/{id}` - Get project details
- `PUT /projects/{id}` - Update project
- `DELETE /projects/{id}` - Delete project

### Document Management
- `POST /projects/{id}/files` - Upload files to project
- `GET /projects/{id}/files` - List project files
- `DELETE /projects/{id}/files/{file_id}` - Delete project file
- `GET /api/projects/{id}/files/{filename}/download` - Download file

### Knowledge Graph
- `GET /api/projects/{id}/graph` - Get Neo4j graph data
- `POST /api/projects/{id}/process-documents` - Process documents for knowledge extraction

### AI Crew Management
- `GET /api/projects/{id}/crew-interactions` - Get crew interaction history
- `POST /api/projects/{id}/crew-interactions` - Start new crew interaction
- `GET /api/projects/{id}/crew-interactions/stats` - Get interaction statistics

### Document Generation
- `POST /api/projects/{id}/generate-report` - Generate project report
- `GET /api/projects/{id}/download/{filename}` - Download generated document

### System Management
- `GET /health` - Service health check with database versions
- `GET /api/platform/stats` - Platform-wide statistics
- `GET /llm-configurations` - List LLM configurations
- `POST /llm-configurations` - Create LLM configuration
## Service Architecture

### Core Services
1. **Backend (Port 8000)** - Main FastAPI application with AI orchestration
2. **Frontend (Port 3000)** - React TypeScript UI
3. **Project Service (Port 8002)** - Project and file management
4. **Reporting Service (Port 8003)** - Document generation
5. **MegaParse (Port 5001)** - Document parsing

### Data Stores
1. **PostgreSQL (Port 5432)** - Relational data (projects, files, configurations)
2. **Neo4j (Port 7474/7687)** - Knowledge graph storage
3. **Weaviate (Port 8080)** - Vector embeddings and semantic search
4. **MinIO (Port 9000/9001)** - Object storage for files and reports

### Key Features by Component
- **Dashboard**: Platform metrics, service health monitoring
- **Projects**: CRUD operations, LLM configuration, file management
- **Knowledge Graph**: Entity extraction, relationship mapping, graph visualization
- **Document Generation**: Template-based report generation with AI content
- **AI Crew**: Multi-agent conversations, task orchestration, interaction logging
- **Settings**: System configuration, agent management, template administration

## Quick Reference for Developers

### Finding Components
- **Service Health Issues**: `ServiceHealthBanner.tsx`, `backend/app/main.py` `/health` endpoint
- **Project LLM Configuration**: `LLMConfigSelector.tsx`, `LLMConfigurationModal.tsx`, `backend/app/core/project_service.py`
- **Dashboard Metrics**: `DashboardView.tsx`, `backend/app/core/platform_stats.py`
- **File Upload**: `FileUpload.tsx`, `backend/app/main.py` file upload endpoints
- **Knowledge Graph**: `GraphVisualizer.tsx`, `backend/app/core/graph_service.py`
- **AI Crew Interactions**: `CrewInteractionViewer.tsx`, `backend/app/core/crew.py`
- **Document Generation**: `ReportDisplay.tsx`, `reporting-service/main.py`
- **System Logs**: `SystemLogsViewer.tsx`, `backend/app/main.py` logging endpoints

### Common Development Tasks
- **Add new API endpoint**: Modify `backend/app/main.py`
- **Add new UI component**: Create in `frontend/src/components/`
- **Add new page/view**: Create in `frontend/src/views/`
- **Modify database schema**: Update `project-service/schemas.py` and create migration
- **Add new AI agent tool**: Create in `backend/app/tools/`
- **Configure new service**: Update `docker-compose.yml` and add health check
- **Add new environment config**: Update files in `config/` directory