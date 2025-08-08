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
├── health-check.bat                   # Service health check script
```

## Backend Service (FastAPI)
```
backend/
├── Dockerfile                         # Backend container definition
├── requirements.txt                   # Python dependencies
├── start_backend.py                   # Backend startup script
├── crew_definitions.yaml              # AI agent crew configurations
└── app/
    ├── main.py                        # FastAPI application entry point
    │   ├── API Endpoints (49 total):
    │   │   ├── get_project_graph()           # GET /api/projects/{id}/graph
    │   │   ├── clear_project_data()          # POST /api/projects/{id}/clear-data
    │   │   ├── query_project_knowledge()     # POST /api/projects/{id}/query
    │   │   ├── list_llm_configurations()     # GET /llm-configurations
    │   │   ├── test_llm_connection()         # POST /api/test-llm
    │   │   ├── get_project_service_status()  # GET /api/projects/{id}/service-status
    │   │   ├── get_project_report()          # GET /api/projects/{id}/report
    │   │   ├── health_check()                # GET /health
    │   │   ├── llm_configurations_health()   # GET /health/llm-configurations
    │   │   ├── validate_configuration()      # GET /config/validate
    │   │   ├── create_project_endpoint()     # POST /projects
    │   │   ├── get_projects()                # GET /projects
    │   │   ├── get_projects_stats()          # GET /projects/stats
    │   │   ├── get_platform_settings()       # GET /platform-settings
    │   │   ├── platform_stats()              # GET /api/platform/stats
    │   │   ├── create_llm_configuration()    # POST /llm-configurations
    │   │   ├── update_llm_configuration()    # PUT /llm-configurations/{id}
    │   │   ├── delete_llm_configuration()    # DELETE /llm-configurations/{id}
    │   │   ├── debug_llm_configs()           # GET /debug/llm-configs
    │   │   ├── reload_llm_configs()          # POST /api/reload-llm-configs
    │   │   ├── test_project_llm()            # POST /api/projects/{id}/test-llm
    │   │   ├── test_llm_config()             # POST /api/test-llm-config
    │   │   ├── process_project_documents()   # POST /api/projects/{id}/process-documents
    │   │   ├── get_project()                 # GET /projects/{id}
    │   │   ├── update_project()              # PUT /projects/{id}
    │   │   ├── list_projects()               # GET /projects (duplicate)
    │   │   ├── delete_project()              # DELETE /projects/{id}
    │   │   ├── get_project_stats()           # GET /api/projects/{id}/stats
    │   │   ├── generate_infrastructure_report() # POST /api/projects/{id}/generate-report
    │   │   ├── get_project_files()           # GET /projects/{id}/files
    │   │   ├── get_project_deliverables()    # GET /projects/{id}/deliverables
    │   │   ├── get_project_template_usage()  # GET /projects/{id}/template-usage
    │   │   ├── get_project_generation_history() # GET /projects/{id}/generation-history
    │   │   ├── add_project_file()            # POST /projects/{id}/files
    │   │   ├── delete_project_file()         # DELETE /projects/{id}/files/{file_id}
    │   │   ├── download_project_file()       # GET /api/projects/{id}/files/{filename}/download
    │   │   ├── upload_files()                # POST /upload/{project_id}
    │   │   ├── get_available_models()        # GET /api/models/{provider}
    │   │   ├── get_crew_interactions()       # GET /api/projects/{id}/crew-interactions
    │   │   ├── get_crew_interaction_stats()  # GET /api/projects/{id}/crew-interactions/stats
    │   │   ├── generate_document()           # POST /api/projects/{id}/generate-document
    │   │   ├── download_project_file()       # GET /api/projects/{id}/download/{filename}
    │   │   ├── get_crew_definitions_endpoint() # GET /api/crew-definitions
    │   │   ├── update_crew_definitions_endpoint() # PUT /api/crew-definitions
    │   │   ├── get_crew_statistics()         # GET /api/crew-definitions/statistics
    │   │   ├── reload_crew_definitions()     # POST /api/crew-definitions/reload
    │   │   ├── get_available_tools()         # GET /api/available-tools
    │   │   └── get_system_services()         # GET /api/system/services
    │   └── WebSocket Endpoints:
    │       ├── websocket_endpoint()          # WS /ws/{project_id}
    │       ├── crew_websocket_endpoint()     # WS /ws/crew/{project_id}
    │       └── document_generation_websocket() # WS /ws/document-generation/{project_id}
    │
    ├── llm_configurations.json           # LLM provider configurations
    │
    ├── core/                              # Core business logic
    │   ├── crew.py                        # CrewAI orchestration
    │   │   ├── CrewLoggerCallback         # Custom callback handler
    │   │   ├── get_llm_class()            # Lazy load LLM classes
    │   │   ├── get_llm_and_model()        # Default LLM instance
    │   │   ├── AgentLogStreamHandler      # WebSocket streaming
    │   │   ├── LLMInitializationError     # Custom exception
    │   │   ├── test_llm_connection()      # Test LLM connectivity
    │   │   ├── _initialize_provider()     # Initialize LLM provider
    │   │   ├── get_project_llm()          # Project-specific LLM
    │   │   ├── get_project_crewai_llm()   # CrewAI-compatible LLM
    │   │   ├── log_token_usage()          # Token usage logging
    │   │   ├── create_assessment_crew()   # Assessment crew creation
    │   │   └── create_document_generation_crew() # Document generation crew
    │   │
    │   ├── crew_config_service.py         # Crew configuration management
    │   ├── crew_factory.py                # Crew instance factory
    │   ├── crew_loader.py                 # Crew definition loader
    │   ├── crew_logger.py                 # Crew interaction logging
    │   ├── embedding_service.py           # Vector embedding service
    │   ├── entity_extraction_agent.py     # Entity extraction logic
    │   ├── graph_service.py               # Neo4j graph database service
    │   ├── platform_stats.py              # Platform-wide statistics
    │   │   └── get_platform_stats()       # Aggregate platform metrics
    │   ├── project_service.py             # Project service client
    │   │   ├── ProjectCreate              # Project creation model
    │   │   ├── ProjectServiceClient       # HTTP client for project service
    │   │   └── get_project_service()      # Project service instance
    │   └── rag_service.py                 # RAG (Retrieval Augmented Generation)
    │
    ├── agents/                            # AI agent definitions
    │   └── agent_definitions.py           # Agent roles and backstories
    │
    ├── tools/                             # AI agent tools
    │   ├── cloud_catalog_tool.py          # Cloud service catalog tool
    │   ├── compliance_tool.py             # Compliance checking tool
    │   ├── enhanced_rag_tool.py           # Advanced RAG queries
    │   ├── graph_query_tool.py            # Neo4j graph queries
    │   ├── hybrid_search_tool.py          # Hybrid vector/keyword search
    │   ├── infrastructure_analysis_tool.py # Infrastructure analysis
    │   ├── lessons_learned_tool.py        # Historical lessons tool
    │   └── project_knowledge_base_tool.py # Project-specific KB
    │
    ├── models/                            # Data models
    │   └── crew_interaction.py            # Crew interaction data model
    │
    └── utils/                             # Utility functions
        ├── config_parsers.py              # Configuration parsing
        ├── cypher_generator.py            # Neo4j Cypher query generation
        └── semantic_chunker.py            # Document semantic chunking
```

## Frontend Service (React TypeScript)
```
frontend/
├── Dockerfile                         # Frontend container definition
├── package.json                       # Node.js dependencies
├── tsconfig.json                      # TypeScript configuration
├── nginx.conf                         # Nginx configuration for production
└── src/
    ├── App.tsx                        # Main React application component
    ├── index.tsx                      # React application entry point
    │
    ├── views/                         # Main application views/pages
    │   ├── DashboardView.tsx          # Dashboard with platform metrics
    │   │   ├── DashboardView()        # Main dashboard component
    │   │   ├── loadPlatformStats()    # Fetch platform statistics
    │   │   └── Platform Metrics Cards:
    │   │       ├── Total Projects Card
    │   │       ├── Active Projects Card
    │   │       ├── Total Documents Card
    │   │       ├── Total Embeddings Card
    │   │       ├── Neo4j Nodes Card
    │   │       └── Neo4j Relationships Card
    │   │
    │   ├── ProjectsView.tsx           # Projects list and creation
    │   │   ├── ProjectsView()         # Main projects view
    │   │   ├── Project List Table
    │   │   ├── Create Project Modal
    │   │   └── LLM Configuration Selection
    │   │
    │   ├── ProjectDetailView.tsx      # Individual project details
    │   │   ├── ProjectDetailView()    # Main project detail component
    │   │   └── Tabbed Interface:
    │   │       ├── Overview Tab
    │   │       ├── Files Tab
    │   │       ├── Knowledge Graph Tab
    │   │       ├── Interactive Discovery Tab
    │   │       ├── Document Generation Tab
    │   │       └── Crew Interactions Tab
    │   │
    │   ├── SettingsView.tsx           # Global settings and configuration
    │   │   ├── SettingsView()         # Main settings component
    │   │   └── Tabbed Settings:
    │   │       ├── AI Agents Panel
    │   │       ├── Service Status Panel
    │   │       ├── Global Templates Panel
    │   │       └── Environment Variables Panel
    │   │
    │   ├── LogsView.tsx               # Application logs viewer
    │   ├── SystemLogsView.tsx         # System-level logs
    │   └── CrewManagementView.tsx     # AI crew management
    │
    ├── components/                    # Reusable React components
    │   ├── ServiceHealthBanner.tsx    # Service status banner
    │   │   ├── ServiceHealthBanner()  # Main banner component
    │   │   ├── checkServiceHealth()   # Health check function
    │   │   ├── ServiceDetails()       # Expandable service details
    │   │   └── Refresh Button
    │   │
    │   ├── FileUpload.tsx             # File upload component
    │   │   ├── FileUpload()           # Drag-and-drop file upload
    │   │   ├── Progress tracking
    │   │   └── Multi-file support
    │   │
    │   ├── LLMConfigSelector.tsx      # LLM configuration selector
    │   │   ├── LLMConfigSelector()    # Dropdown selector
    │   │   └── Configuration validation
    │   │
    │   ├── LLMConfigurationModal.tsx  # LLM setup modal
    │   │   ├── LLMConfigurationModal() # Modal component
    │   │   ├── Provider selection
    │   │   ├── Model selection
    │   │   ├── API key configuration
    │   │   └── Test connection
    │   │
    │   ├── FloatingChatWidget.tsx     # Chat interface widget
    │   ├── ReportDisplay.tsx          # Document report display
    │   ├── LiveConsole.tsx            # Real-time console output
    │   │
    │   ├── layout/
    │   │   └── AppLayout.tsx          # Main application layout
    │   │       ├── AppLayout()        # Shell with sidebar navigation
    │   │       ├── Header component
    │   │       ├── Sidebar navigation
    │   │       └── Content area
    │   │
    │   ├── admin/
    │   │   ├── SystemLogsViewer.tsx   # System administration logs
    │   │   │   ├── SystemLogsViewer() # Main logs viewer
    │   │   │   ├── Service health overview
    │   │   │   ├── Database versions display
    │   │   │   └── Log filtering
    │   │   └── ModernConsole.tsx      # Modern console interface
    │   │
    │   ├── project-detail/
    │   │   ├── ChatInterface.tsx      # Real-time chat with AI agents
    │   │   │   ├── ChatInterface()    # Main chat component
    │   │   │   ├── Message history
    │   │   │   ├── WebSocket connection
    │   │   │   └── Agent response handling
    │   │   │
    │   │   ├── GraphVisualizer.tsx    # Interactive Neo4j knowledge graph
    │   │   │   ├── GraphVisualizer()  # Graph visualization component
    │   │   │   ├── Node/edge rendering
    │   │   │   ├── Interactive controls
    │   │   │   └── Graph data fetching
    │   │   │
    │   │   ├── DocumentTemplates.tsx  # Document template management
    │   │   │   ├── DocumentTemplates() # Template selection
    │   │   │   ├── Template preview
    │   │   │   └── Generation controls
    │   │   │
    │   │   ├── CrewInteractionViewer.tsx # AI agent conversation history
    │   │   │   ├── CrewInteractionViewer() # Interaction viewer
    │   │   │   ├── Conversation threads
    │   │   │   ├── Agent activity timeline
    │   │   │   └── Interaction filtering
    │   │   │
    │   │   ├── AgentActivityLog.tsx   # Individual agent activity tracking
    │   │   └── ProjectHistory.tsx     # Project change and activity history
    │   │
    │   ├── settings/
    │   │   ├── AIAgentsPanel.tsx      # Configure AI agent roles and capabilities
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

### Backend Functions (main.py - 49 endpoints)
- **Health & Status**: `health_check()`, `llm_configurations_health()`, `get_system_services()`
- **Projects**: `create_project_endpoint()`, `get_projects()`, `get_project()`, `update_project()`, `delete_project()`
- **LLM Management**: `list_llm_configurations()`, `create_llm_configuration()`, `test_llm_connection()`
- **Document Processing**: `process_project_documents()`, `upload_files()`, `generate_infrastructure_report()`
- **Knowledge Graph**: `get_project_graph()`, `query_project_knowledge()`, `clear_project_data()`
- **AI Crew**: `get_crew_interactions()`, `get_crew_definitions_endpoint()`, `generate_document()`
- **Platform Stats**: `platform_stats()`, `get_project_stats()`, `get_projects_stats()`

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