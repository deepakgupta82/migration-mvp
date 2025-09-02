# Nagarro Ascent Platform - Complete API Endpoints Documentation

## Overview
This document provides a comprehensive list of all API endpoints across the Nagarro Ascent Platform, including both frontend-called endpoints and all service endpoints. Each service operates on its designated port with specific responsibilities. This document maps every frontend component to its corresponding backend API endpoints for complete system understanding.

**Last Updated:** August 30, 2025  
**Recent Updates:** Service health monitoring, port conflict resolution, integration status updates  
**Platform Architecture:** Microservices with API Gateway Pattern  
**Frontend Technology:** React 18 with TypeScript, Mantine UI  
**Backend Technology:** FastAPI Python microservices

---

## Table of Contents

### Frontend Structure
- [Frontend Application Structure](#frontend-application-structure) - Complete frontend file mapping
- [Detailed Frontend Component API Usage](#detailed-frontend-component-api-usage) - Component-to-API mapping

### Backend Services
- [Service Architecture & Ports](#service-architecture--ports) - All microservices overview
- [Backend Service (API Gateway) - Port 8000](#1-backend-service-api-gateway---port-8000) - Main API gateway
- [Project Service - Port 8002](#2-project-service---port-8002) - Project management
- [Document Service - Port 8004](#3-document-service---port-8004) - Document processing
- [Vector Service - Port 8005](#4-vector-service---port-8005) - Vector embeddings
- [Graph Service - Port 8006](#5-graph-service---port-8006) - Knowledge graphs
- [LLM Service - Port 8007](#6-llm-service---port-8007) - LLM processing
- [AI Agent Service - Port 8008](#7-ai-agent-service---port-8008) - AI agent workflows
- [WebSocket Service - Port 8009](#8-websocket-service---port-8009) - Real-time communication
- [Storage Service - Port 8010](#9-storage-service---port-8010) - File storage
- [Reporting Service - Port 8001](#10-reporting-service---port-8001) - Report generation
- [Service Registry - Port 8011](#11-service-registry---port-8011) - Service discovery
- [Additional Services](#12-cloud-tools-service---port-8012) - Ports 8012-8017

### Architecture & Integration
- [Complete Platform Architecture Overview](#complete-platform-architecture-overview) - System design
- [Complete Service Reference](#complete-service-reference) - Service discovery
- [Platform Usage Guide for AI Tools](#platform-usage-guide-for-ai-tools) - AI analysis reference

### Operations
- [Recommendations for Cleanup](#recommendations-for-cleanup) - Maintenance guidelines
- [Security & Authentication](#security--authentication) - Security patterns
- [Service Health Check Summary](#service-health-check-summary) - Monitoring

---

## Frontend Application Structure

### Core Frontend Files and Their API Usage

**Base Application:**
- `frontend/src/App.tsx` - Main application component with routing and Mantine providers
- `frontend/src/index.tsx` - Application entry point

**Services Layer:**
- `frontend/src/services/api.ts` - **Central API service** with all backend endpoint calls
- `frontend/src/services/notificationService.ts` - WebSocket notification handling

**Context Providers:**
- `frontend/src/contexts/AuthContext.tsx` - Authentication state management
- `frontend/src/contexts/LLMConfigContext.tsx` - LLM configuration context
- `frontend/src/contexts/NotificationContext.tsx` - Real-time notifications
- `frontend/src/contexts/AssessmentContext.tsx` - AI assessment workflow state

**Main Views (Pages):**
- `frontend/src/views/DashboardView.tsx` - Platform overview with stats
- `frontend/src/views/ProjectsView.tsx` - Project management interface
- `frontend/src/views/ProjectDetailView.tsx` - Individual project details
- `frontend/src/views/SettingsView.tsx` - Platform configuration
- `frontend/src/views/LogsView.tsx` - System logs and monitoring
- `frontend/src/views/SystemLogsView.tsx` - Detailed system diagnostics
- `frontend/src/views/CrewManagementView.tsx` - AI agent crew configuration

**Core Components:**
- `frontend/src/components/FileUpload.tsx` - Document upload interface
- `frontend/src/components/ServiceHealthBanner.tsx` - Service status monitoring
- `frontend/src/components/ModelManager.tsx` - LLM model management
- `frontend/src/components/ProcessingProgressView.tsx` - Real-time processing updates
- `frontend/src/components/FloatingChatWidget.tsx` - RAG knowledge chat
- `frontend/src/components/TestLLMModal.tsx` - LLM configuration testing

**Layout Components:**
- `frontend/src/components/layout/AppLayout.tsx` - Main application layout
- `frontend/src/components/layout/SettingsPageLayout.tsx` - Settings page layout

**Project Detail Components:**
- `frontend/src/components/project-detail/ChatInterface.tsx` - Project knowledge chat
- `frontend/src/components/project-detail/GraphVisualizer.tsx` - Knowledge graph visualization
- `frontend/src/components/project-detail/DocumentTemplates.tsx` - Template management
- `frontend/src/components/project-detail/AgentActivityLog.tsx` - AI agent activity tracking
- `frontend/src/components/project-detail/CrewInteractionViewer.tsx` - Crew workflow monitoring
- `frontend/src/components/project-detail/ProjectHistory.tsx` - Project activity history

**Settings Components:**
- `frontend/src/components/settings/LLMConfigurationPanel.tsx` - LLM settings management
- `frontend/src/components/settings/ServiceStatusPanel.tsx` - Service health monitoring
- `frontend/src/components/settings/EnvironmentVariablesPanel.tsx` - Environment configuration
- `frontend/src/components/settings/GlobalDocumentTemplates.tsx` - Template management
- `frontend/src/components/settings/AIAgentsPanel.tsx` - AI agent configuration

**Admin Components:**
- `frontend/src/components/admin/ModernConsole.tsx` - Administrative console
- `frontend/src/components/admin/SystemLogsViewer.tsx` - Advanced log viewer

**Utility Components:**
- `frontend/src/components/logs/` - Log viewing components
- `frontend/src/components/notifications/` - Notification components
- `frontend/src/hooks/` - Custom React hooks for API integration

### Frontend to Backend API Mapping

**Primary API Base URL:**
```typescript
const API_BASE_URL = process.env.REACT_APP_API_URL || 
  `${window.location.protocol}//${window.location.hostname}:8000`
```

**Key Frontend → Backend Connections:**

| Frontend Component | Primary API Endpoints | Purpose |
|-------------------|----------------------|----------|
| `DashboardView.tsx` | `GET /api/platform/stats-fast`<br>`GET /api/projects?include_stats=true` | Platform overview statistics |
| `ProjectsView.tsx` | `GET /api/projects`<br>`POST /api/projects`<br>`DELETE /api/projects/{id}` | Project CRUD operations |
| `ProjectDetailView.tsx` | `GET /api/projects/{id}`<br>`GET /api/projects/{id}/graph`<br>`POST /api/projects/{id}/query` | Project details and knowledge |
| `FileUpload.tsx` | `POST /api/projects/{id}/upload`<br>`GET /api/projects/{id}/uploaded-files` | File upload and management |
| `SettingsView.tsx` | `GET /api/llm/configurations`<br>`POST /api/llm/configurations`<br>`POST /api/test-llm-config` | Platform configuration |
| `LogsView.tsx` | `GET /api/logs/search`<br>`GET /api/logs/services` | System monitoring |
| `ServiceHealthBanner.tsx` | `GET /api/health`<br>`GET /api/services/health` | Service status monitoring |
| `ChatInterface.tsx` | `POST /api/projects/{id}/query` | RAG knowledge queries |
| `GraphVisualizer.tsx` | `GET /api/projects/{id}/graph` | Knowledge graph visualization |
| `CrewManagementView.tsx` | `GET /api/crew-config`<br>`PUT /api/crew-config` | AI agent configuration |
| `AgentActivityLog.tsx` | WebSocket `/ws/run_assessment/{id}` | Real-time agent activity |
| `ProcessingProgressView.tsx` | WebSocket `/ws/processing/{id}`<br>`GET /api/projects/{id}/processing-status/{job_id}` | Document processing progress |

---

## Detailed Frontend Component API Usage

### 1. Dashboard Components

**DashboardView.tsx** → Platform Overview
- `GET /api/platform/stats-fast` - Real-time platform statistics
- `GET /api/projects?include_stats=true` - Project list with embedded stats
- WebSocket connections to Stats Service for live updates
- **Features:** Service health cards, project activity, real-time metrics

**ServiceHealthBanner.tsx** → Service Status Monitoring
- `GET /api/health` - API gateway health with all service statuses
- `GET /api/services/health` - Detailed microservice health checks
- **Features:** Real-time service status indicators, error alerts

### 2. Project Management Components

**ProjectsView.tsx** → Project Listing & Management
- `GET /api/projects` - List all projects with pagination
- `POST /api/projects` - Create new project with LLM configuration
- `PUT /api/projects/{id}` - Update project details
- `DELETE /api/projects/{id}` - Delete project with cascade cleanup
- `GET /api/llm/configurations` - Load LLM configs for project creation
- `POST /api/test-llm-config` - Validate LLM configuration before saving
- **Features:** Search, filtering, status management, bulk operations

**ProjectDetailView.tsx** → Individual Project Interface
- `GET /api/projects/{id}` - Load project details and configuration
- `GET /api/projects/{id}/uploaded-files` - List project documents
- `POST /api/projects/{id}/upload` - Upload new documents
- `POST /api/projects/{id}/process-documents` - Start document processing
- `GET /api/projects/{id}/processing-status/{job_id}` - Monitor processing progress
- `POST /api/projects/{id}/query` - RAG knowledge queries
- `GET /api/projects/{id}/graph` - Knowledge graph data
- `POST /api/agents/workflows` - Start AI assessment workflows
- **Features:** Document management, knowledge chat, graph visualization, AI assessments

### 3. Document Processing Components

**FileUpload.tsx** → Document Upload Interface
- `POST /api/projects/{id}/upload` - Multipart file upload with progress tracking
- `GET /api/projects/{id}/uploaded-files` - List uploaded documents
- `DELETE /api/projects/{id}/files/{file_id}` - Delete documents with cleanup
- **Features:** Drag-and-drop, progress bars, file validation, error handling

**ProcessingProgressView.tsx** → Real-time Processing Updates
- WebSocket `/ws/processing/{project_id}` - Live processing updates
- `GET /api/projects/{id}/processing-status/{job_id}` - Processing job status
- **Features:** Real-time progress bars, error reporting, completion notifications

### 4. Knowledge & AI Components

**ChatInterface.tsx** → RAG Knowledge Chat
- `POST /api/projects/{id}/query` - Submit knowledge queries
- **Features:** Conversational interface, context-aware responses, source citations

**GraphVisualizer.tsx** → Knowledge Graph Visualization
- `GET /api/projects/{id}/graph` - Load graph nodes and relationships
- **Features:** Interactive graph visualization, node filtering, relationship exploration

**AgentActivityLog.tsx** → AI Agent Activity Monitoring
- WebSocket `/ws/run_assessment/{project_id}` - Real-time agent activity
- `GET /api/agents/workflows/{job_id}/status` - Workflow status checks
- **Features:** Live agent logs, task progress, error tracking

**CrewInteractionViewer.tsx** → AI Crew Workflow Monitoring
- WebSocket `/ws/run_assessment/{project_id}` - Crew execution updates
- `POST /api/agents/workflows/{job_id}/cancel` - Cancel running workflows
- **Features:** Multi-agent coordination display, task assignments, completion tracking

### 5. Configuration & Settings Components

**SettingsView.tsx** → Platform Configuration Hub
- `GET /api/llm/configurations` - List all LLM configurations
- `POST /api/llm/configurations` - Create new LLM configuration
- `PUT /api/llm/configurations/{id}` - Update LLM settings
- `DELETE /api/llm/configurations/{id}` - Remove LLM configuration
- `POST /api/test-llm-config` - Test LLM connectivity
- `GET /api/llm/models/{provider}` - Get available models for provider
- `GET /api/platform-settings` - Load platform settings
- **Features:** Multi-tab interface, configuration validation, provider management

**LLMConfigurationPanel.tsx** → LLM Settings Management
- `GET /api/llm/providers` - Available LLM providers (OpenAI, Gemini, Ollama, etc.)
- `GET /api/llm/models/{provider}` - Dynamic model loading per provider
- `POST /api/test-llm-config` - Configuration testing and validation
- **Features:** Provider-specific settings, model selection, API key management

**ModelManager.tsx** → Advanced LLM Model Management
- `GET /api/llm/configurations` - Load saved configurations
- `POST /api/llm/configurations` - Save new configurations
- `POST /api/test-llm-config` - Comprehensive model testing
- **Features:** Model comparison, performance testing, configuration templates

### 6. Administrative Components

**LogsView.tsx** → System Log Management
- `GET /api/logs/search` - Search logs with filters (service, level, time range)
- `GET /api/logs/services` - Get available log services
- `GET /api/logs` - List log services
- **Features:** Advanced filtering, real-time search, log level management

**CrewManagementView.tsx** → AI Agent Configuration
- `GET /api/crew-config` - Load crew definitions and statistics
- `PUT /api/crew-config` - Update crew configurations
- `POST /api/crew-config/reload` - Reload crew definitions from file
- **Features:** Agent creation, task assignment, crew orchestration

**SystemLogsViewer.tsx** → Advanced System Diagnostics
- `GET /api/correlation/trace` - Trace correlation IDs across services
- `GET /api/logs/search` - Advanced log correlation and analysis
- **Features:** Cross-service debugging, correlation tracking, performance analysis

### 7. Real-time Communication

**WebSocket Connections Used by Frontend:**

| Component | WebSocket Endpoint | Purpose |
|-----------|-------------------|----------|
| `AgentActivityLog.tsx` | `/ws/run_assessment/{project_id}` | AI agent execution logs |
| `ProcessingProgressView.tsx` | `/ws/processing/{project_id}` | Document processing updates |
| `DashboardView.tsx` | Stats Service WebSocket | Real-time platform metrics |
| `CrewInteractionViewer.tsx` | `/ws/run_assessment/{project_id}` | Multi-agent workflow coordination |
| `NotificationService.ts` | Collaboration Service WebSocket | User notifications and alerts |

### 8. Authentication & Security

**AuthContext.tsx** → Authentication Management
- `POST /token` - User login and JWT token generation
- `POST /users/register` - New user registration
- **Features:** JWT token management, role-based access control

### 9. Data Flow Architecture

**API Service Layer (`api.ts`):**
```typescript
class ApiService {
  // Centralized request handling with:
  // - Correlation ID generation
  // - Authentication headers
  // - Error handling and retry logic
  // - Request/response logging
}
```

**Key Features:**
- Correlation ID tracking for debugging
- Service token authentication
- Centralized error handling
- Request logging and monitoring
- Type-safe API calls with TypeScript

---

## Service Architecture & Ports

| Service | Port | Purpose | Deployment | Status |
|---------|------|---------|------------|--------|
| **Backend (API Gateway)** | 8000 | Main API gateway, routes to microservices | Native Python | ✅ Active |
| **Reporting Service** | 8001 | Report generation, PDF/DOCX conversion, MinIO storage | Native Python | ✅ Active |
| **Project Service** | 8002 | Project management, users, LLM configs | Native Python | ✅ Active |
| **Document Service** | 8003 | Document processing with Unstructured.io, conversion, chunking | Native Python | ✅ Active |
| **Stats Service** | 8004 | Platform statistics, analytics, event tracking | Native Python | ✅ Active |
| **Vector Service** | 8005 | Vector embeddings, semantic search | Native Python | ✅ Active |
| **Graph Service** | 8006 | Knowledge graph, entity extraction | Native Python | ✅ Active |
| **LLM Service** | 8007 | LLM processing, configurations | Native Python | ✅ Active |
| **AI Agent Service** | 8008 | AI agent orchestration, crew management | Native Python | ✅ Active |
| **WebSocket Service** | 8009 | Real-time notifications, progress tracking | Native Python | ✅ Active |
| **Storage Service** | 8010 | File storage, upload/download operations | Native Python | ✅ Active |
| **Service Registry** | 8011 | Service discovery, health monitoring | Native Python | ✅ Active |
| **Cloud Tools Service** | 8012 | Cloud provider integrations, assessments | Native Python | ✅ Active |
| **Analytics Service** | 8014 | Advanced analytics, ML insights, forecasting | Native Python | ✅ Active |
| **Security Service** | 8015 | Multi-tenant auth, RBAC, audit logging | Native Python | ✅ Active |
| **Collaboration Service** | 8016 | Team collaboration, notifications, workspaces | Native Python | ✅ Active |
| **Knowledge Service** | 8017 | Knowledge management, RAG, semantic search | Native Python | ✅ Active |
| **Weaviate** | 8080 | Vector database | Docker Container | ✅ Active |
| **PostgreSQL** | 5432 | Relational database | Docker Container | ✅ Active |
| **Neo4j** | 7474/7687 | Graph database | Docker Container | ✅ Active |
| **MinIO** | 9000/9001 | Object storage | Docker Container | ✅ Active |
| **Redis** | 6379 | Caching and message queuing | Docker Container | ✅ Active |
| **Loki** | - | Log aggregation | Docker Container | ✅ Active |
| **Promtail** | - | Log shipping | Docker Container | ✅ Active |

**Note**: The platform uses Unstructured.io as the primary document conversion engine for JSONL processing. MegaParse is NOT used in the current implementation.

---

## 1. Backend Service (API Gateway) - Port 8000

### **Frontend Base URL:** `http://localhost:8000`

### Health & Status Endpoints

| Method | Endpoint | Purpose | Frontend Usage |
|--------|----------|---------|----------------|
| `GET` | `/api/health` | API gateway health check with microservices status | ✅ ServiceHealthBanner |
| `GET` | `/api/services/health` | Check all microservices health | ✅ Admin dashboard |
| `GET` | `/api/services/{service}/health` | Check specific service health | ✅ Service monitoring |
| `GET` | `/api/gateway/debug` | Debug service client token for troubleshooting | ⚠️ Development only |

### Project Management (Proxied to Project Service)

| Method | Endpoint | Purpose | Frontend Usage |
|--------|----------|---------|----------------|
| `GET` | `/api/projects` | List all projects with optional stats | ✅ ProjectsView, Dashboard |
| `GET` | `/api/projects/` | List projects (with trailing slash) | ✅ Alternative URL |
| `GET` | `/api/projects/{project_id}` | Get specific project details | ✅ Project detail views |
| `POST` | `/api/projects` | Create new project | ✅ Create project modal |
| `POST` | `/api/projects/` | Create project (with trailing slash) | ✅ Alternative URL |
| `PUT` | `/api/projects/{project_id}` | Update existing project | ✅ Project edit forms |
| `DELETE` | `/api/projects/{project_id}` | Delete project and all data | ✅ Project management |

### Project Files & Data

| Method | Endpoint | Purpose | Frontend Usage |
|--------|----------|---------|----------------|
| `GET` | `/api/projects/{project_id}/uploaded-files` | List uploaded project files | ✅ File management |
| `POST` | `/api/projects/{project_id}/upload` | Upload documents to project | ✅ File upload |
| `POST` | `/api/projects/{project_id}/clear-data` | Clear project vectors and graph data | ✅ Project reset |

### Document Processing

| Method | Endpoint | Purpose | Frontend Usage |
|--------|----------|---------|----------------|
| `POST` | `/api/projects/{project_id}/process-documents` | Start document processing job | ✅ Document processing |
| `GET` | `/api/projects/{project_id}/processing-status/{job_id}` | Get processing job status | ✅ Progress tracking |

### Knowledge & Query

| Method | Endpoint | Purpose | Frontend Usage |
|--------|----------|---------|----------------|
| `POST` | `/api/projects/{project_id}/query` | RAG-powered knowledge queries | ✅ Chat interface |
| `GET` | `/api/projects/{project_id}/graph` | Get project knowledge graph | ✅ Graph visualization |

### LLM Configuration Management

| Method | Endpoint | Purpose | Frontend Usage |
|--------|----------|---------|----------------|
| `GET` | `/api/llm/providers` | Get available LLM providers | ✅ Settings form |
| `GET` | `/api/llm/configurations` | List all LLM configurations | ✅ Settings, project forms |
| `POST` | `/api/llm/configurations` | Create new LLM configuration | ✅ Settings save |
| `PUT` | `/api/llm/configurations/{config_id}` | Update LLM configuration | ✅ Settings edit |
| `DELETE` | `/api/llm/configurations/{config_id}` | Delete LLM configuration | ✅ Settings management |
| `GET` | `/api/llm/models/{provider}` | Get models for specific provider | ✅ Dynamic model loading |
| `POST` | `/api/test-llm-config` | Test LLM configuration | ✅ Configuration validation |

### User Management

| Method | Endpoint | Purpose | Frontend Usage |
|--------|----------|---------|----------------|
| `GET` | `/api/users/enhanced` | Get enhanced user information with pagination | ✅ User management |

### AI Agent & Workflows

| Method | Endpoint | Purpose | Frontend Usage |
|--------|----------|---------|----------------|
| `GET` | `/api/agents` | List available AI agents | ✅ Agent selection |
| `POST` | `/api/agents/workflows` | Start AI workflow/crew | ✅ Assessment trigger |
| `GET` | `/api/agents/workflows/{job_id}/status` | Get workflow status | ✅ Progress monitoring |
| `POST` | `/api/agents/workflows/{job_id}/cancel` | Cancel running workflow | ✅ Workflow control |

### Logging & Debugging

| Method | Endpoint | Purpose | Frontend Usage |
|--------|----------|---------|----------------|
| `GET` | `/api/logs` | List log services | ✅ LogsView service list |
| `GET` | `/api/logs/search` | Search logs with filters | ✅ LogsView search |
| `GET` | `/api/logs/services` | Get available log services | ✅ Service filter |
| `GET` | `/api/correlation/trace` | Trace correlation IDs across services | ⚠️ Debugging |

### Storage Operations

| Method | Endpoint | Purpose | Frontend Usage |
|--------|----------|---------|----------------|
| `GET` | `/api/storage/projects/{project_id}/files/{category}` | List project files by category | ✅ File browser |
| `GET` | `/api/storage/projects/{project_id}/stats` | Get project storage statistics | ✅ Storage monitoring |

### Crew Configuration

| Method | Endpoint | Purpose | Frontend Usage |
|--------|----------|---------|----------------|
| `GET` | `/api/crew-config` | Get crew definitions and statistics | ✅ Crew management |
| `PUT` | `/api/crew-config` | Update crew configurations | ✅ Crew editor |
| `POST` | `/api/crew-config/reload` | Reload crew definitions from file | ✅ Configuration refresh |

### Platform Settings

| Method | Endpoint | Purpose | Frontend Usage |
|--------|----------|---------|----------------|
| `GET` | `/api/platform-settings` | Get platform configuration settings | ✅ Settings view |

### Project Deliverables & Templates

| Method | Endpoint | Purpose | Frontend Usage |
|--------|----------|---------|----------------|
| `GET` | `/api/projects/{project_id}/deliverables` | Get project-specific templates | ✅ Template management |
| `POST` | `/api/projects/{project_id}/deliverables` | Create project deliverable template | ✅ Template creation |

### Statistics & Analytics

| Method | Endpoint | Purpose | Frontend Usage |
|--------|----------|---------|----------------|
| `GET` | `/api/projects/stats` | Get legacy project statistics | ⚠️ Deprecated |
| `GET` | `/api/platform/stats-fast` | Get fast platform statistics | ✅ Dashboard |
| `GET` | `/api/projects/{project_id}/stats-snapshot` | Get project stats snapshot | ✅ Project overview |

---

## 2. Project Service - Port 8002

**Direct Access:** Generally accessed through API Gateway, but has its own endpoints.

### Authentication

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/token` | User login and JWT token generation |
| `POST` | `/users/register` | Register new user (first user becomes admin) |

### Project Management (Native)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/projects` | List all projects with enhanced data |
| `POST` | `/projects` | Create new project with validation |
| `GET` | `/projects/{project_id}` | Get project by ID with full details |
| `PUT` | `/projects/{project_id}` | Update project with field validation |
| `DELETE` | `/projects/{project_id}` | Delete project and cascade cleanup |

### Project Files Management

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/projects/{project_id}/files` | Get all files for project |
| `POST` | `/projects/{project_id}/files` | Add file record to project |
| `GET` | `/projects/{project_id}/files/count` | Get lightweight file count |
| `DELETE` | `/projects/{project_id}/files/{file_id}` | Delete file from project |

### LLM Configuration Management (Native)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/llm-configurations` | List all LLM configurations |
| `POST` | `/llm-configurations` | Create new LLM configuration |
| `GET` | `/llm-configurations/{config_id}` | Get specific LLM configuration |
| `PUT` | `/llm-configurations/{config_id}` | Update LLM configuration |
| `DELETE` | `/llm-configurations/{config_id}` | Delete LLM configuration |

### User Management (Native)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/users/enhanced` | Get enhanced user list with pagination and search |

### Platform Settings (Native)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/settings` | List all platform settings (admin only) |
| `GET` | `/platform-settings` | Get platform settings (alternative endpoint) |

### Template Management

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/templates/global` | List global document templates |
| `POST` | `/templates/global` | Create global template |
| `DELETE` | `/templates/global/{template_id}` | Delete global template |
| `GET` | `/templates/all/{project_id}` | Get both global and project templates |

### Template Usage Tracking

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/template-usage` | Track template usage for statistics |
| `GET` | `/projects/{project_id}/template-usage` | Get project template usage stats |
| `GET` | `/template-usage/global` | Get global template usage stats (admin) |

### Generation History

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/projects/{project_id}/generation-history` | Get document generation history |
| `GET` | `/projects/{project_id}/generation-requests` | Get generation requests for project |
| `POST` | `/projects/{project_id}/generation-requests` | Create new generation request |
| `PUT` | `/projects/{project_id}/generation-requests/{request_id}` | Update generation request |

---

## 3. Document Service - Port 8003

**Technology Stack:**
- **Primary Converter**: Unstructured.io for JSONL processing
- **OCR Engine**: Tesseract OCR
- **Output Formats**: Markdown (.md) and Structured JSONL

### Document Upload & Processing

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/documents/{project_id}/upload` | Upload documents to Storage Service (port 8010) |
| `POST` | `/api/documents/{project_id}/process-all` | Process all uploaded documents |
| `POST` | `/api/documents/{project_id}/process-selected` | Process selected documents |
| `GET` | `/api/documents/{project_id}/status/{job_id}` | Get processing status for a job |

### Structured Document Processing

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/documents/{project_id}/structured-process/{filename}` | Process single document with structured JSONL output |
| `POST` | `/api/documents/{project_id}/structured-process-all` | Process all documents with structured output |
| `GET` | `/api/documents/{project_id}/structured-status/{job_id}` | Get status of structured processing job |

### Enhanced Document Processing

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/documents/{project_id}/generate-enhanced-chunks/{filename}` | Generate enhanced chunks from processed document using JSONL-aware chunking |
| `POST` | `/api/documents/{project_id}/process-structured` | Process structured document elements for entity extraction |

### Configuration & Status

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/documents/workflow-config` | Get current document processing workflow configuration |
| `GET` | `/health` | Document service health check with table model optimization status |

### JSONL Analysis Endpoints (PHASE 3 - Migration to JSONL-only)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/documents/{project_id}/analysis` | Create new analysis result in JSONL format |
| `GET` | `/api/documents/{project_id}/analysis/{analysis_id}` | Retrieve specific analysis result |
| `GET` | `/api/documents/{project_id}/analysis` | List analysis results for project with filtering |
| `PUT` | `/api/documents/{project_id}/analysis/{analysis_id}` | Update existing analysis result |
| `DELETE` | `/api/documents/{project_id}/analysis/{analysis_id}` | Delete analysis result |
| `POST` | `/api/documents/{project_id}/analysis/batch` | Create and start batch analysis operation |
| `GET` | `/api/documents/{project_id}/analysis/batch/{batch_id}` | Get batch analysis status and results |
| `GET` | `/api/documents/{project_id}/analysis/batches` | List analysis batches for project |
| `POST` | `/api/documents/{project_id}/analysis/{analysis_id}/version` | Create new version of analysis result |
| `GET` | `/api/documents/{project_id}/analysis/{analysis_id}/versions` | List all versions of analysis result |
| `GET` | `/api/documents/{project_id}/analysis/{analysis_id}/version/{version_number}` | Get specific version of analysis result |

### Legacy Endpoints (Maintained for Compatibility)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/{project_id}/upload` | Legacy upload endpoint |
| `POST` | `/{project_id}/process-all` | Legacy processing endpoint |
| `GET` | `/{project_id}/status/{job_id}` | Legacy status endpoint |

### Migration Notes (JSONL Transition)

**Removed Endpoints (Replaced with JSONL Analysis):**
- `POST /api/projects/{project_id}/generate-report` → Use `POST /api/documents/{project_id}/analysis/batch`
- `GET /api/projects/{project_id}/report` → Use `GET /api/documents/{project_id}/analysis`
- `GET /api/projects/{project_id}/download/{filename}` → Use `GET /api/documents/{project_id}/analysis/{analysis_id}`

**Migration Path:**
1. **Report Generation**: Use batch analysis endpoints for comprehensive JSONL analysis
2. **Report Retrieval**: Use analysis result endpoints with filtering capabilities
3. **Report Download**: Use analysis result retrieval with JSONL format
4. **Backward Compatibility**: Legacy endpoints removed - migrate to new JSONL endpoints

**Benefits of JSONL Migration:**
- Structured data format for better analysis
- Enhanced search and filtering capabilities
- Version control for analysis results
- Batch processing support
- Improved metadata management

---

## 4. Vector Service - Port 8005

### Vector Collection Management

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/vectors/projects/{project_id}/collection` | Create vector collection for project (no physical collection) |
| `GET` | `/api/vectors/projects/{project_id}/collection` | Get information about project's vector set in Weaviate |
| `DELETE` | `/api/vectors/projects/{project_id}/collection` | Delete project's vectors from Weaviate |

### Document Vector Operations

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/vectors/projects/{project_id}/documents` | Add documents to Weaviate with background embedding generation |
| `POST` | `/api/vectors/projects/{project_id}/documents/sync` | Add documents to Weaviate synchronously (for smaller batches) |
| `DELETE` | `/api/vectors/projects/{project_id}/documents/{filename}` | Delete vectors for specific document |

### Vector Search

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/vectors/projects/{project_id}/search` | Similarity search in project's vectors (Weaviate) |
| `POST` | `/api/vectors/projects/{project_id}/search/hybrid` | Hybrid search combining semantic and keyword matching |

### Collection Statistics

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/vectors/projects/{project_id}/stats` | Get detailed statistics about project's vector collection |
| `GET` | `/api/vectors/projects/{project_id}/search/cache` | Get search cache statistics for debugging |

### Structured Document Processing

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/vectors/projects/{project_id}/process-structured` | Process structured document elements with smart chunking and embedding |

### Utility & Maintenance

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/vectors/cleanup` | Cleanup database connections to prevent resource warnings |
| `POST` | `/api/vectors/warm-up` | Warm up AI models in background to reduce first request latency |
| `GET` | `/api/vectors/model-status` | Get current model loading status |
| `GET` | `/api/vectors/debug/collections` | Debug endpoint to list Weaviate classes |
| `GET` | `/api/vectors/debug/model-info` | Debug endpoint to get information about embedding model |

### Health & Status

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/vectors/health` | Check if vector service is healthy |
| `GET` | `/health` | Vector service health with Weaviate connection status |

---

## 5. Graph Service - Port 8006

### Graph Database Management

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/graph/projects/{project_id}/database` | Create Neo4j database for project |
| `DELETE` | `/api/graph/projects/{project_id}/database` | Delete project's Neo4j database |
| `GET` | `/api/graph/projects/{project_id}/database` | Get information about project's graph database |

### Node Operations

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/graph/projects/{project_id}/nodes` | Create nodes in project's graph database |
| `GET` | `/api/graph/projects/{project_id}/nodes/{node_id}` | Get specific node by ID |
| `PUT` | `/api/graph/projects/{project_id}/nodes/{node_id}` | Update node properties |
| `DELETE` | `/api/graph/projects/{project_id}/nodes/{node_id}` | Delete node from graph |

### Relationship Operations

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/graph/projects/{project_id}/relationships` | Create relationships between nodes |
| `GET` | `/api/graph/projects/{project_id}/relationships/{rel_id}` | Get specific relationship by ID |
| `PUT` | `/api/graph/projects/{project_id}/relationships/{rel_id}` | Update relationship properties |
| `DELETE` | `/api/graph/projects/{project_id}/relationships/{rel_id}` | Delete relationship from graph |

### Graph Query & Search

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/graph/projects/{project_id}/query` | Execute Cypher query on project's graph |
| `POST` | `/api/graph/projects/{project_id}/search` | Search nodes and relationships in graph |
| `GET` | `/api/graph/projects/{project_id}/nodes` | Get all nodes in project graph |
| `GET` | `/api/graph/projects/{project_id}/relationships` | Get all relationships in project graph |

### Document Graph Processing

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/graph/projects/{project_id}/process-document` | Process document and create graph representation |
| `POST` | `/api/graph/projects/{project_id}/process-structured` | Process structured document elements into graph |

### Graph Analytics

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/graph/projects/{project_id}/analytics/centrality` | Calculate node centrality measures |
| `GET` | `/api/graph/projects/{project_id}/analytics/clusters` | Find clusters/communities in graph |
| `GET` | `/api/graph/projects/{project_id}/analytics/paths` | Find shortest paths between nodes |

### Utility & Maintenance

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/graph/cleanup` | Cleanup database connections |
| `GET` | `/api/graph/projects/{project_id}/stats` | Get detailed graph database statistics |
| `GET` | `/api/graph/debug/constraints` | Debug endpoint to list Neo4j constraints |
| `GET` | `/api/graph/debug/indexes` | Debug endpoint to list Neo4j indexes |

### Health & Status

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/graph/health` | Check if graph service is healthy |
| `GET` | `/health` | Graph service health with Neo4j connection status |

---

## 6. LLM Service - Port 8007

### LLM Processing

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/llm/process` | Process LLM requests with project context |
| `GET` | `/api/llm/resolve` | Resolve LLM provider/model for process type |

### Configuration Management (Proxy)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/configurations` | List LLM configurations (proxy to project service) |
| `POST` | `/configurations` | Create LLM configuration |
| `GET` | `/configurations/{config_id}` | Get specific configuration |
| `PUT` | `/configurations/{config_id}` | Update configuration |
| `DELETE` | `/configurations/{config_id}` | Delete configuration |

### Provider & Model Management

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/providers` | Get available LLM providers |
| `GET` | `/models/{provider}` | Get models for specific provider |
| `POST` | `/test-config` | Test LLM configuration |

### Health & Status

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/health` | LLM service health check |

---

## 7. AI Agent Service - Port 8008

### Agent Management

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/agents` | List available AI agents |
| `GET` | `/api/agents/{agent_id}` | Get specific agent details |

### Workflow Management

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/agents/workflows` | Start crew workflow |
| `GET` | `/api/agents/workflows/{job_id}/status` | Get workflow execution status |
| `POST` | `/api/agents/workflows/{job_id}/cancel` | Cancel running workflow |

### Crew Configuration

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/crew-config` | Get crew definitions |
| `PUT` | `/api/crew-config` | Update crew configuration |
| `POST` | `/api/crew-config/reload` | Reload crew from file |

### Health & Status

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/health` | AI agent service health |

---

## 8. WebSocket Service - Port 8009

### Real-time Communication

| WebSocket | Endpoint | Purpose |
|-----------|----------|---------|
| `WS` | `/ws/processing/{project_id}` | Real-time processing updates |
| `WS` | `/ws/run_assessment/{project_id}` | Assessment execution updates |

### Broadcast & Notifications

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/websocket/broadcast` | Send broadcast message to clients |

### Progress Tracking

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/progress/operation/{event_id}` | Get specific operation status |
| `GET` | `/progress/project/{project_id}` | Get all operations for project |
| `GET` | `/progress/service/{service_name}` | Get operations for specific service |

### Health & Status

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/health` | WebSocket service health |

---

## 9. Storage Service - Port 8010

### File Upload & Download

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/storage/projects/{project_id}/upload/{category}` | Upload files to specific category |
| `GET` | `/api/storage/projects/{project_id}/download/{category}/{filename}` | Download specific file |

### File Management

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/storage/projects/{project_id}/files/{category}` | List files in category |
| `DELETE` | `/api/storage/projects/{project_id}/files/{category}/{filename}` | Delete specific file |

### Storage Statistics

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/storage/projects/{project_id}/stats` | Get project storage statistics |

### Health & Status

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/health` | Storage service health |

---

## 10. Reporting Service - Port 8001

### Report Generation

| Method | Endpoint | Purpose |
|--------|----------|----------|
| `POST` | `/generate_report` | Generate professional reports in DOCX/PDF format from markdown |
| `POST` | `/convert/pdf` | Convert markdown content to PDF format |
| `POST` | `/convert/docx` | Convert markdown content to DOCX format |
| `GET` | `/reports/{project_id}` | Get report URL for specific project |

### Health & Status

| Method | Endpoint | Purpose |
|--------|----------|----------|
| `GET` | `/health` | Report service health with database and MinIO status |

---

## 11. Service Registry - Port 8011

### Service Management

| Method | Endpoint | Purpose |
|--------|----------|----------|
| `POST` | `/services/register` | Register new service for discovery |
| `DELETE` | `/services/{service_name}` | Unregister service from registry |
| `GET` | `/services` | Get status of all registered services |
| `GET` | `/services/{service_name}` | Get status of specific service |
| `GET` | `/health/summary` | Get health summary of all services |

### Real-time Monitoring

| WebSocket | Endpoint | Purpose |
|-----------|----------|----------|
| `WS` | `/ws` | Real-time service health updates |

### Health & Status

| Method | Endpoint | Purpose |
|--------|----------|----------|
| `GET` | `/health` | Service registry health check |

---

## 12. Cloud Tools Service - Port 8012

### Cloud Credentials Management

| Method | Endpoint | Purpose |
|--------|----------|----------|
| `POST` | `/projects/{project_id}/credentials` | Add cloud provider credentials for project |

### Assessment Management

| Method | Endpoint | Purpose |
|--------|----------|----------|
| `POST` | `/projects/{project_id}/assessments` | Start cloud environment assessment |
| `GET` | `/projects/{project_id}/assessments` | Get all assessments for project |
| `GET` | `/assessments/{assessment_id}` | Get specific assessment details |

### Resource Discovery

| Method | Endpoint | Purpose |
|--------|----------|----------|
| `GET` | `/projects/{project_id}/resources` | Get all discovered cloud resources |
| `GET` | `/projects/{project_id}/resources/summary` | Get resource summary by type and provider |

### Health & Status

| Method | Endpoint | Purpose |
|--------|----------|----------|
| `GET` | `/health` | Cloud tools service health check |

---

## 13. Analytics Service - Port 8014

### Analytics Generation

| Method | Endpoint | Purpose |
|--------|----------|----------|
| `POST` | `/analytics/migration-complexity` | Generate migration complexity analysis |
| `POST` | `/analytics/cost-optimization` | Generate cost optimization analysis |
| `POST` | `/analytics/agent-efficiency` | Generate AI agent efficiency analysis |

### Health & Status

| Method | Endpoint | Purpose |
|--------|----------|----------|
| `GET` | `/health` | Analytics service health check |

---

## 14. Security Service - Port 8015

### Authentication

| Method | Endpoint | Purpose |
|--------|----------|----------|
| `POST` | `/auth/login` | User authentication and JWT token generation |
| `POST` | `/auth/logout` | User logout and token invalidation |
| `POST` | `/auth/refresh` | Refresh JWT access token |

### User Management

| Method | Endpoint | Purpose |
|--------|----------|----------|
| `POST` | `/users` | Create new user account |
| `GET` | `/users/{user_id}` | Get user information |
| `PUT` | `/users/{user_id}` | Update user information |
| `DELETE` | `/users/{user_id}` | Delete user account |

### Multi-Tenant Management

| Method | Endpoint | Purpose |
|--------|----------|----------|
| `POST` | `/tenants` | Create new tenant |
| `GET` | `/tenants/{tenant_id}` | Get tenant information |
| `GET` | `/tenants/{tenant_id}/users` | Get all users for tenant |

### Audit & Compliance

| Method | Endpoint | Purpose |
|--------|----------|----------|
| `GET` | `/audit/logs` | Get audit logs with filtering |
| `POST` | `/audit/log` | Create audit log entry |

### Health & Status

| Method | Endpoint | Purpose |
|--------|----------|----------|
| `GET` | `/health` | Security service health check |

---

## 15. Collaboration Service - Port 8016

### Workspace Management

| Method | Endpoint | Purpose |
|--------|----------|----------|
| `POST` | `/workspaces` | Create new team workspace |
| `GET` | `/workspaces/{workspace_id}` | Get workspace details |

### Activity Management

| Method | Endpoint | Purpose |
|--------|----------|----------|
| `POST` | `/workspaces/{workspace_id}/activities` | Add activity to workspace |
| `GET` | `/workspaces/{workspace_id}/activities` | Get workspace activities |

### Notification Management

| Method | Endpoint | Purpose |
|--------|----------|----------|
| `POST` | `/workspaces/{workspace_id}/notifications` | Create notification |
| `GET` | `/users/{user_id}/notifications` | Get user notifications |

### Real-time Communication

| WebSocket | Endpoint | Purpose |
|-----------|----------|----------|
| `WS` | `/ws/{user_id}` | Real-time collaboration updates |

### Statistics

| Method | Endpoint | Purpose |
|--------|----------|----------|
| `GET` | `/stats` | Get collaboration statistics |

### Health & Status

| Method | Endpoint | Purpose |
|--------|----------|----------|
| `GET` | `/health` | Collaboration service health check |

---

## 16. Knowledge Service - Port 8017

### Document Management

| Method | Endpoint | Purpose |
|--------|----------|----------|
| `POST` | `/documents` | Add new knowledge document |
| `GET` | `/documents/{doc_id}` | Get specific document |
| `GET` | `/documents` | List all documents with filtering |
| `PUT` | `/documents/{doc_id}` | Update document |
| `DELETE` | `/documents/{doc_id}` | Delete document |

### Knowledge Search

| Method | Endpoint | Purpose |
|--------|----------|----------|
| `POST` | `/search` | Search documents with semantic/keyword/hybrid search |
| `POST` | `/questions` | Ask questions using RAG (Retrieval-Augmented Generation) |
| `GET` | `/questions/{qa_id}` | Get Q&A pair by ID |

### Knowledge Graphs

| Method | Endpoint | Purpose |
|--------|----------|----------|
| `POST` | `/knowledge-graphs` | Create knowledge graph from documents |
| `GET` | `/knowledge-graphs/{graph_id}` | Get knowledge graph |

### Health & Status

| Method | Endpoint | Purpose |
|--------|----------|----------|
| `GET` | `/health` | Knowledge service health check |

---

## 17. Stats Service - Port 8004

### Platform Statistics

| Method | Endpoint | Purpose |
|--------|----------|----------|
| `GET` | `/api/stats/platform` | Get platform-wide statistics |
| `GET` | `/api/stats/projects` | Get project statistics summary |
| `GET` | `/api/stats/platform/fast` | Get fast platform statistics (cached) |

### Event Tracking

| Method | Endpoint | Purpose |
|--------|----------|----------|
| `POST` | `/api/stats/events` | Record platform events for analytics |
| `GET` | `/api/stats/events/{event_type}` | Get events by type |

### Real-time Updates

| WebSocket | Endpoint | Purpose |
|-----------|----------|----------|
| `WS` | `/ws/stats` | Real-time statistics updates |

### Health & Status

| Method | Endpoint | Purpose |
|--------|----------|----------|
| `GET` | `/health` | Stats service health check |

**Note**: Stats Service focuses on real-time platform metrics and event tracking, while Analytics Service (8014) handles ML insights and forecasting. No active conflict with Document Service in Docker mode.

---

## Frontend API Usage Patterns

### Primary Frontend Endpoints (Most Frequently Used)

1. **`GET /api/projects`** - ProjectsView, Dashboard (project listing)
2. **`GET /api/health`** - ServiceHealthBanner (service status)
3. **`POST /api/projects/{project_id}/upload`** - File upload functionality
4. **`GET /api/llm/configurations`** - Settings, project forms
5. **`POST /api/test-llm-config`** - LLM configuration validation
6. **`GET /api/logs/search`** - LogsView search functionality
7. **`POST /api/projects/{project_id}/query`** - RAG chat interface
8. **`GET /api/projects/{project_id}/graph`** - Graph visualization

### Base URL Configuration

```typescript
// Frontend API base URL resolution
const API_BASE_URL = process.env.REACT_APP_API_URL || 
  `${window.location.protocol}//${window.location.hostname}:8000`
```

---

## Deprecated & Orphaned Endpoints

### ⚠️ **Potential Orphaned Endpoints**

1. **`/api/projects/stats`** - Legacy project stats (replaced by stats service on port 8004)
2. **Direct service calls** - Frontend should use gateway endpoints only
3. **`/api/crew-definitions`** - Old crew management (replaced by `/api/crew-config`)
4. **Duplicate LLM endpoints** - Both project service and LLM service have overlapping functionality
5. **Multiple file upload paths** - Document service and storage service overlap

### 🔄 **Endpoints Needing Review**

1. **Multiple LLM config endpoints** - Both project service (8002) and LLM service (8007) have overlapping functionality
2. **Template management** - Split between project service and reporting service
3. **File operations** - Document service (8003) and storage service (8010) have overlapping upload endpoints
4. **Authentication endpoints** - Security service (8015) vs legacy auth in project service
5. **Stats collection** - Stats service (8004) vs analytics service (8014) overlapping functionality
6. **Knowledge management** - Vector service (8005), graph service (8006), and knowledge service (8017) potential overlap

### 📊 **Service Integration Issues**

1. **Port Conflicts** - Document service (8003 native/8004 Docker) and Stats service (8004) - resolved with clear separation
2. **Service Discovery** - Service Registry (8011) is active and most services register with it
3. **Security Integration** - Security service (8015) has JWT authentication implemented; RBAC integration is partial but progressing
4. **Analytics Pipeline** - Analytics service (8014) focuses on ML insights, Stats service (8004) handles platform metrics
5. **Real-time Updates** - WebSocket Service (8009) coordinates real-time updates across services

---

## Security & Authentication

### Service Authentication
- **Service-to-Service:** Bearer token (`SERVICE_AUTH_TOKEN`)
- **User Authentication:** JWT tokens via `/token` endpoint
- **CORS Configuration:** Configured for `localhost:3000` (frontend)

### Common Headers
```
Authorization: Bearer service-backend-token
X-Correlation-ID: <unique-request-id>
Content-Type: application/json
```

---

## Complete Platform Architecture Overview

### Frontend Architecture

**Technology Stack:**
- React 18.2+ with TypeScript
- Mantine UI 7.x component library
- React Router 6.x for routing
- Custom hooks for state management
- WebSocket integration for real-time features

**Directory Structure:**
```
frontend/src/
├── components/           # Reusable UI components
│   ├── layout/          # Layout components (AppLayout, SettingsPageLayout)
│   ├── project-detail/  # Project-specific components
│   ├── settings/        # Settings page components
│   ├── admin/          # Administrative components
│   ├── logs/           # Log viewing components
│   └── notifications/  # Notification components
├── views/              # Main page components
├── contexts/           # React context providers
├── hooks/              # Custom React hooks
├── services/           # API service layer
├── pages/              # Settings sub-pages
└── App.tsx            # Main application component
```

### Backend Architecture

**Microservices Pattern:**
- API Gateway (Backend Service) - Port 8000
- 16 specialized microservices (Ports 8001-8017)
- Service discovery and health monitoring
- Event-driven communication
- Containerized deployment with Docker

**Data Storage:**
- PostgreSQL (Relational data)
- Neo4j (Knowledge graphs)
- Weaviate (Vector embeddings)
- MinIO (Object storage)
- Redis (Caching and sessions)

### Communication Patterns

**Frontend → Backend:**
1. All frontend requests go through API Gateway (Port 8000)
2. Gateway routes requests to appropriate microservices
3. WebSocket connections for real-time updates
4. REST API for CRUD operations
5. Multipart uploads for file handling

**Backend → Backend:**
1. Service-to-service HTTP communication
2. Event-driven messaging
3. Service discovery via environment variables
4. Health check monitoring
5. Correlation ID tracking across services

### Key Design Patterns

**Frontend Patterns:**
- Component composition
- Custom hooks for API integration
- Context providers for state management
- Real-time WebSocket integration
- Error boundary implementation

**Backend Patterns:**
- API Gateway pattern
- Microservices architecture
- CQRS (Command Query Responsibility Segregation)
- Event sourcing
- Circuit breaker pattern
- Bulkhead pattern for service isolation

---

## Complete Service Reference

### Service Discovery and Health Monitoring

**Service Registry (Port 8011)** - Centralized service discovery
- Tracks all active services
- Health check aggregation
- Service status broadcasting
- Automatic service registration/deregistration

**Health Check Endpoints by Service:**
```
Backend Gateway:   GET :8000/api/health
Reporting Service: GET :8001/health
Project Service:   GET :8002/health
Document Service:  GET :8003/health
Stats Service:     GET :8004/health
Vector Service:    GET :8005/health
Graph Service:     GET :8006/health
LLM Service:       GET :8007/health
AI Agent Service:  GET :8008/health
WebSocket Service: GET :8009/health
Storage Service:   GET :8010/health
Service Registry:  GET :8011/health
Cloud Tools:       GET :8012/health
Analytics Service: GET :8014/health
Security Service:  GET :8015/health
Collaboration:     GET :8016/health
Knowledge Service: GET :8017/health
```

### Deployment Architecture

**Docker Containerized Services (Infrastructure Only):**
- **Weaviate** (Port 8080) - Vector database
- **PostgreSQL** (Port 5432) - Relational database
- **Neo4j** (Port 7474/7687) - Graph database
- **MinIO** (Port 9000/9001) - Object storage
- **Redis** (Port 6379) - Caching and message queuing
- **Loki** - Log aggregation
- **Promtail** - Log shipping

**Native Python Services (All Application Services):**
- **Backend (API Gateway)** (Port 8000) - Main API gateway
- **Project Service** (Port 8002) - Project management
- **Reporting Service** (Port 8001) - Report generation
- **Document Service** (Port 8003) - Document processing with Unstructured.io
- **Vector Service** (Port 8005) - Vector embeddings
- **Graph Service** (Port 8006) - Knowledge graphs
- **LLM Service** (Port 8007) - LLM processing
- **AI Agent Service** (Port 8008) - AI agent workflows
- **WebSocket Service** (Port 8009) - Real-time communication
- **Storage Service** (Port 8010) - File storage
- **Service Registry** (Port 8011) - Service discovery
- **Cloud Tools Service** (Port 8012) - Cloud integrations
- **Analytics Service** (Port 8014) - Analytics and insights
- **Security Service** (Port 8015) - Authentication and security
- **Collaboration Service** (Port 8016) - Team collaboration
- **Knowledge Service** (Port 8017) - Knowledge management
- **Stats Service** (Port 8004) - Platform statistics

**Document Processing Technology:**
- **Primary**: Unstructured.io for JSONL processing and document conversion
- **OCR Support**: Tesseract OCR for scanned documents
- **Output Format**: Markdown with JSONL structured data

**Note**: MegaParse is NOT used in the current implementation. The platform uses Unstructured.io as the primary document conversion engine.

**Document Processing Pipeline:**
1. Frontend uploads via `FileUpload.tsx` → Storage Service
2. Document Service processes files → Unstructured.io for JSONL conversion
3. Vector Service creates embeddings → Weaviate
4. Graph Service extracts entities → Neo4j
5. Real-time updates via WebSocket Service

**Knowledge Query Pipeline:**
1. Frontend query via `ChatInterface.tsx` → API Gateway
2. Gateway routes to Vector Service for similarity search
3. Graph Service provides context enrichment
4. LLM Service generates response
5. Response returned to frontend with sources

**AI Assessment Pipeline:**
1. Frontend triggers via `ProjectDetailView.tsx` → AI Agent Service
2. Agent Service coordinates crew workflow
3. Real-time updates via WebSocket Service
4. Results stored via Storage Service
5. Reports generated via Reporting Service

---

## Recommendations for Cleanup

### 🧹 **Immediate Actions Needed**

1. **Consolidate LLM Configuration Management**
   - Choose single source of truth (project service recommended)
   - Remove duplicate endpoints from LLM service

2. **Standardize File Upload**
   - Document service uploads should route through storage service
   - Remove direct upload endpoints from document service

3. **Remove Orphaned Endpoints**
   - Clean up legacy stats endpoints
   - Remove unused crew definition endpoints

4. **Service Port Conflicts**
   - Document service (8003) and Stats service (8004) - ensure no conflicts
   - Verify all services are using assigned ports correctly

5. **API Versioning**
   - Add `/api/v1/` prefix for public endpoints
   - Maintain backward compatibility during migration

6. **Security Integration**
   - Integrate Security service (8015) with all other services
   - Implement consistent JWT token validation across services

7. **Service Registry Integration**
   - Ensure all services register with Service Registry (8011)
   - Use service discovery instead of hardcoded URLs

### 📝 **Documentation Updates Needed**

1. **OpenAPI/Swagger Documentation** - Generate for each service
2. **Frontend Integration Guide** - Document expected usage patterns
3. **Service Communication Diagrams** - Show inter-service dependencies

---

## Service Health and Monitoring

### Health Check Endpoints

**Centralized Health Monitoring:**
- **API Gateway**: `GET :8000/api/health` - Aggregates all service statuses
- **Service Registry**: `GET :8011/health/summary` - Centralized service discovery and health
- **Stats Service**: `GET :8004/api/stats/platform` - Platform-wide health metrics

**Individual Service Health Checks:**
- All services have dedicated `/health` endpoints
- Service Registry tracks 16 registered services
- Real-time health updates via WebSocket connections

### Monitoring Integration

**Logging Stack:**
- **Loki** (docker-compose.yml) - Log aggregation
- **Promtail** (docker-compose.yml) - Log shipping from services
- **Analytics Service** (8014) - ML-driven insights and anomaly detection
- **Security Service** (8015) - Security monitoring and threat detection

**Real-time Monitoring:**
- **WebSocket Service** (8009) - Coordinates real-time updates across platform
- **Stats Service** (8004) - Real-time platform metrics and event tracking
- **Service Registry** (8011) - Service discovery and health broadcasting

### Current Status

**Active Services:** ✅ All 17 services running and healthy
**Service Registry:** ✅ 16 services registered, 1 native service (Backend)
**Docker Deployment:** ✅ 7 infrastructure services containerized
**Native Deployment:** ✅ 17 application services running locally
**Integration Status:** ✅ Service Registry active, Security partial, Analytics operational

---

## Service Health Check Summary

| Service | Port | Health Endpoint | Status | Deployment |
|---------|------|----------------|--------|------------|
| Backend (API Gateway) | 8000 | `GET /api/health` | ✅ Active | Native |
| Reporting Service | 8001 | `GET /health` | ✅ Active | Native |
| Project Service | 8002 | `GET /health` | ✅ Active | Native |
| Document Service | 8003 | `GET /health` | ✅ Active | Native |
| Stats Service | 8004 | `GET /health` | ✅ Active | Native |
| Vector Service | 8005 | `GET /health` | ✅ Active | Native |
| Graph Service | 8006 | `GET /health` | ✅ Active | Native |
| LLM Service | 8007 | `GET /health` | ✅ Active | Native |
| AI Agent Service | 8008 | `GET /health` | ✅ Active | Native |
| WebSocket Service | 8009 | `GET /health` | ✅ Active | Native |
| Storage Service | 8010 | `GET /health` | ✅ Active | Native |
| Service Registry | 8011 | `GET /health` | ✅ Active | Native |
| Cloud Tools Service | 8012 | `GET /health` | ✅ Active | Native |
| Analytics Service | 8014 | `GET /health` | ✅ Active | Native |
| Security Service | 8015 | `GET /health` | ✅ Active | Native |
| Collaboration Service | 8016 | `GET /health` | ✅ Active | Native |
| Knowledge Service | 8017 | `GET /health` | ✅ Active | Native |
| Weaviate | 8080 | - | ✅ Active | Docker |
| PostgreSQL | 5432 | - | ✅ Active | Docker |
| Neo4j | 7474/7687 | - | ✅ Active | Docker |
| MinIO | 9000/9001 | - | ✅ Active | Docker |
| Redis | 6379 | - | ✅ Active | Docker |
| Loki | - | - | ✅ Active | Docker |
| Promtail | - | - | ✅ Active | Docker |

**Status Legend:**
- ✅ **Active**: Service running and responding to health checks
- ⚠️ **Partial**: Service running but with integration issues
- ❌ **Inactive**: Service not responding or not deployed

---

## Platform Usage Guide for AI Tools

### Quick Reference for AI Analysis

**Frontend Entry Points:**
- Main Application: `frontend/src/App.tsx`
- API Service Layer: `frontend/src/services/api.ts` (Central API hub)
- View Components: `frontend/src/views/` (Main user interfaces)
- Component Library: `frontend/src/components/` (Reusable UI elements)

**Backend Entry Points:**
- API Gateway: `backend/app/main.py` (Port 8000)
- Service Discovery: `services/service-registry/` (Port 8011)
- Microservices: `services/*/` (Ports 8001-8017)

**Key Configuration Files:**
- Docker Compose: `docker-compose.yml` (infrastructure services only)
- Frontend Package: `frontend/package.json`
- Service Dependencies: `*/requirements.txt` files

### Frontend Component Dependencies

**Core Dependencies Map:**
```
App.tsx
├── AppLayout.tsx
│   ├── ServiceHealthBanner.tsx → GET /api/health
│   └── Navigation routing
├── DashboardView.tsx → GET /api/platform/stats-fast
├── ProjectsView.tsx → GET /api/projects
├── ProjectDetailView.tsx
│   ├── FileUpload.tsx → POST /api/projects/{id}/upload
│   ├── ChatInterface.tsx → POST /api/projects/{id}/query
│   ├── GraphVisualizer.tsx → GET /api/projects/{id}/graph
│   └── AgentActivityLog.tsx → WebSocket /ws/run_assessment/{id}
├── SettingsView.tsx
│   ├── LLMConfigurationPanel.tsx → GET /api/llm/configurations
│   ├── ServiceStatusPanel.tsx → GET /api/services/health
│   └── ModelManager.tsx → POST /api/test-llm-config
└── LogsView.tsx → GET /api/logs/search
```

### API Flow Patterns

**1. Project Creation Flow:**
```
ProjectsView.tsx → POST /api/projects → Project Service (8002) → PostgreSQL
```

**2. Document Upload Flow:**
```
FileUpload.tsx → POST /api/projects/{id}/upload → Storage Service (8010) → MinIO
```

**3. Document Processing Flow:**
```
ProjectDetailView.tsx → POST /api/projects/{id}/process-documents → Document Service (8003)
→ Vector Service (8005) → Weaviate
→ Graph Service (8006) → Neo4j
→ WebSocket updates to ProcessingProgressView.tsx
```

**4. Knowledge Query Flow:**
```
ChatInterface.tsx → POST /api/projects/{id}/query → Vector Service (8005) → Weaviate
→ Graph Service (8006) → Neo4j
→ LLM Service (8007) → OpenAI/Gemini/Ollama
```

**5. AI Assessment Flow:**
```
ProjectDetailView.tsx → POST /api/agents/workflows → AI Agent Service (8008)
→ CrewAI Framework → LLM Service (8007)
→ WebSocket updates to AgentActivityLog.tsx
```

### Critical Integration Points

**Authentication:**
- Service Token: `service-backend-token` (Frontend → Backend)
- JWT Tokens: User authentication via Project Service
- Correlation IDs: Request tracking across services

**Error Handling:**
- Frontend: Try-catch blocks in api.ts
- Backend: Centralized error handling in API Gateway
- Logging: Correlation ID tracking across all services

**Real-time Features:**
- WebSocket Service (Port 8009) coordinates all real-time updates
- Multiple WebSocket connections for different data types
- Frontend components automatically reconnect on connection loss

### Development Guidelines

**Frontend Development:**
1. All API calls must go through `api.ts` service layer
2. Use React hooks from `hooks/` directory for state management
3. WebSocket connections handled by service layer
4. Error handling with user-friendly notifications

**Backend Development:**
1. All frontend requests route through API Gateway (Port 8000)
2. Microservices communicate via HTTP with correlation IDs
3. Health checks required for all services
4. Service registration with Service Registry recommended

**Testing Guidelines:**
1. Frontend: Component testing with React Testing Library
2. Backend: FastAPI automatic testing endpoints
3. Integration: End-to-end testing with Docker Compose
4. Performance: Load testing on API Gateway endpoints

---

**End of Documentation**  
**Total Endpoints Documented:** 250+  
**Services Covered:** 17 Active Services  
**Frontend Components Mapped:** 40+ Components  
**Complete Architecture Coverage:** Frontend + Backend + Data Flow  
**AI Tool Reference:** Complete platform understanding guide  

---

## Recent Documentation Updates (August 30, 2025)

### ✅ **Completed Updates**

1. **Deployment Architecture Update** - Corrected Docker vs Native service deployment
2. **Document Processing Technology** - Updated to reflect Unstructured.io usage instead of MarkItDown
3. **Service Architecture Table** - Updated deployment modes for all services
4. **Infrastructure Services** - Clarified that only infrastructure services run in Docker
5. **Removed References** - Eliminated mentions of docker-microservices.yml and MegaParse
6. **Service Health and Monitoring Section** - Added comprehensive monitoring overview
7. **Port Conflict Resolution** - Clarified Document service (8003 native) vs Stats service (8004)
8. **Service Integration Status** - Updated Service Registry, Security, and Analytics integration details
9. **Health Check Summary** - Enhanced table with ports, status, and deployment modes
10. **Complete API Endpoint Documentation** - Updated all 17 services with detailed endpoints from OpenAPI specifications

### 📊 **Current Platform Status**

- **All 17 Application Services:** ✅ Running locally (Native Python)
- **7 Infrastructure Services:** ✅ Running in Docker containers
- **Service Registry:** ✅ 16 services registered
- **Security Integration:** ⚠️ JWT implemented, RBAC partial
- **Analytics Pipeline:** ✅ Operational with ML insights
- **Document Processing:** ✅ Using Unstructured.io for JSONL conversion
- **Real-time Updates:** ✅ WebSocket coordination active
- **API Documentation:** ✅ Complete with 250+ endpoints documented

### 🔄 **Next Steps**

1. Complete Security service RBAC integration
2. Implement comprehensive service-to-service authentication
3. Add OpenAPI/Swagger documentation for all services
4. Create service communication architecture diagrams
5. Generate automated API documentation from OpenAPI specs