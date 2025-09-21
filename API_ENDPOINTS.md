# Migration Platform API Endpoints Reference

This document provides a comprehensive reference of all API endpoints across all services in the migration platform. Each endpoint includes a brief description of its functionality.

## Table of Contents
- [Backend (Port 8000)](#backend-port-8000)
- [Reporting Service (Port 8001)](#reporting-service-port-8001)
- [Document Service (Port 8003)](#document-service-port-8003)
- [Project Service (Port 8002)](#project-service-port-8002)
- [Storage Service (Port 8010)](#storage-service-port-8010)
- [Vector Service (Port 8005)](#vector-service-port-8005)
- [Graph Service (Port 8006)](#graph-service-port-8006)
- [Analytics Service (Port 8014)](#analytics-service-port-8014)
- [Stats Service (Port 8004)](#stats-service-port-8004)
- [LLM Service (Port 8007)](#llm-service-port-8007)
- [AI Agent Service (Port 8008)](#ai-agent-service-port-8008)
- [WebSocket Service (Port 8009)](#websocket-service-port-8009)
- [Service Registry (Port 8011)](#service-registry-port-8011)
- [Cloud Tools Service (Port 8012)](#cloud-tools-service-port-8012)
- [Security Service (Port 8015)](#security-service-port-8015)
- [Collaboration Service (Port 8016)](#collaboration-service-port-8016)
- [Knowledge Service (Port 8017)](#knowledge-service-port-8017)

---

## Backend (Port 8000)

### System Statistics
- `GET /api/system/websocket-stats` - Get WebSocket connection statistics
- `GET /api/platform/stats` - Get current platform statistics (snapshot)
- `GET /api/platform/stats-fast` - Get fast cached platform statistics snapshot

### Real-time Communication
- `WebSocket /ws/logs/{service}` - WebSocket endpoint for streaming real-time logs
- `WebSocket /ws/console/{service}` - WebSocket endpoint for streaming raw container console output
- `WebSocket /ws/project-stats/{project_id}` - WebSocket endpoint for real-time project statistics
- `WebSocket /ws/platform-stats` - WebSocket endpoint for real-time platform statistics
- `WebSocket /ws/crew-interactions/{project_id}` - Real-time crew interactions across all tasks for a project
- `WebSocket /ws/document-processing/{project_id}` - WebSocket endpoint for document processing updates

---

## Reporting Service (Port 8001)

### Document Conversion
- `POST /convert/pdf` - Convert markdown content to PDF format
- `POST /convert/docx` - Convert markdown content to DOCX format

### Report Generation
- `POST /generate_report` - Generate professional report in DOCX or PDF format

### Report Management
- `GET /reports/{project_id}` - Get the report URL for a specific project

### Health
- `GET /health` - Health check endpoint

---

## Document Service (Port 8003)

### Document Upload
- `POST /{project_id}/upload` - Upload documents to storage service
- `POST /{project_id}/process-all` - Start processing all uploaded documents
- `POST /{project_id}/process-selected` - Start processing selected documents

### Document Processing Status
- `GET /{project_id}/status/{job_id}` - Get processing status for a job
- `GET /{project_id}/structured-status/{job_id}` - Get structured processing status

### Document Content
- `GET /{project_id}/content/{filename}` - Get document content details
- `POST /{project_id}/analyze/{filename}` - Analyze document content
- `GET /{project_id}/insights` - Get project content insights
- `POST /{project_id}/analyze-batch` - Batch analyze multiple documents
- `GET /{project_id}/content-analysis/{analysis_id}` - Get batch analysis status

### Structured Processing
- `POST /{project_id}/structured-process/{filename}` - Process document with structured output
- `POST /{project_id}/structured-process-all` - Process all documents with structured output

### Enhanced Features
- `POST /{project_id}/generate-enhanced-chunks/{filename}` - Generate enhanced chunks with JSONL-aware chunking
- `POST /{project_id}/extract-content-batch` - Extract content from multiple documents

### Search
- `POST /{project_id}/search` - Search within document content, summaries, categories

### Analysis Management
- `POST /{project_id}/analysis` - Create analysis result
- `GET /{project_id}/analysis/{analysis_id}` - Get analysis result
- `GET /{project_id}/analysis` - List project analysis results
- `PUT /{project_id}/analysis/{analysis_id}` - Update analysis result
- `DELETE /{project_id}/analysis/{analysis_id}` - Delete analysis result

### Batch Operations
- `POST /{project_id}/analysis/batch` - Create analysis batch
- `GET /{project_id}/analysis/batch/{batch_id}` - Get analysis batch
- `GET /{project_id}/analysis/batches` - List project analysis batches

### Versioning
- `POST /{project_id}/analysis/{analysis_id}/version` - Create analysis version
- `GET /{project_id}/analysis/{analysis_id}/versions` - List analysis versions
- `GET /{project_id}/analysis/{analysis_id}/version/{version_number}` - Get analysis version

### LLM Analysis
- `POST /{project_id}/llm-analyze/{filename}` - LLM-enhanced document analysis
- `POST /{project_id}/llm-analyze-batch` - Batch LLM analysis
- `GET /{project_id}/llm-analysis-status/{analysis_id}` - Get LLM batch analysis status
- `GET /llm-analysis-health` - Get LLM analysis health status
- `POST /llm-analysis-cache/clear` - Clear LLM analysis cache

### Configuration
- `GET /workflow-config` - Get workflow configuration
- `GET /health` - Health check endpoint

---

## Project Service (Port 8002)

### Project Management
- `GET /api/projects` - List all projects
- `POST /api/projects` - Create new project
- `GET /api/projects/{project_id}` - Get project details
- `PUT /api/projects/{project_id}` - Update project
- `DELETE /api/projects/{project_id}` - Delete project

### Project Files
- `GET /api/projects/{project_id}/files` - List project files
- `POST /api/projects/{project_id}/files` - Add file to project
- `GET /api/projects/{project_id}/files/{file_id}` - Get file details
- `DELETE /api/projects/{project_id}/files/{file_id}` - Remove file from project

### Project Metadata
- `GET /api/projects/{project_id}/metadata` - Get project metadata
- `PUT /api/projects/{project_id}/metadata` - Update project metadata

---

## Storage Service (Port 8010)

### File Upload
- `POST /api/storage/projects/{project_id}/upload/uploads_raw` - Upload raw files
- `POST /api/storage/projects/{project_id}/upload/uploads_parsed` - Upload parsed files
- `POST /api/storage/projects/{project_id}/upload/metadata` - Upload metadata files
- `POST /api/storage/projects/{project_id}/upload/structured` - Upload structured files

### File Download
- `GET /api/storage/projects/{project_id}/download/uploads_raw/{filename}` - Download raw file
- `GET /api/storage/projects/{project_id}/download/uploads_parsed/{filename}` - Download parsed file
- `GET /api/storage/projects/{project_id}/download/metadata/{filename}` - Download metadata file
- `GET /api/storage/projects/{project_id}/download/structured/{filename}` - Download structured file

### File Management
- `GET /api/storage/projects/{project_id}/files/uploads_raw` - List raw files
- `GET /api/storage/projects/{project_id}/files/uploads_parsed` - List parsed files
- `GET /api/storage/projects/{project_id}/files/metadata` - List metadata files
- `GET /api/storage/projects/{project_id}/files/structured` - List structured files
- `DELETE /api/storage/projects/{project_id}/files/{filename}` - Delete file

---

## Vector Service (Port 8005)

### Collection Management
- `POST /api/vectors/projects/{project_id}/collection` - Create vector collection
- `DELETE /api/vectors/projects/{project_id}/collection` - Delete vector collection
- `GET /api/vectors/projects/{project_id}/collection/status` - Get collection status

### Document Operations
- `POST /api/vectors/projects/{project_id}/documents/sync` - Sync documents to vectors
- `POST /api/vectors/projects/{project_id}/documents/batch` - Batch document operations
- `DELETE /api/vectors/projects/{project_id}/documents/{document_id}` - Delete document vectors

### Search
- `POST /api/vectors/projects/{project_id}/search` - Semantic search
- `POST /api/vectors/projects/{project_id}/search/hybrid` - Hybrid search (semantic + keyword)

---

## Graph Service (Port 8006)

### Entity Extraction
- `POST /api/graphs/projects/{project_id}/extract` - Extract entities from document
- `POST /api/graphs/projects/{project_id}/extract/batch` - Batch entity extraction

### Graph Operations
- `GET /api/graphs/projects/{project_id}/entities` - Get project entities
- `GET /api/graphs/projects/{project_id}/relationships` - Get entity relationships
- `POST /api/graphs/projects/{project_id}/query` - Query graph data

---

## Analytics Service (Port 8014)

### Analysis Results
- `POST /api/analysis` - Create analysis result
- `GET /api/analysis/{analysis_id}` - Get analysis result
- `PUT /api/analysis/{analysis_id}` - Update analysis result
- `DELETE /api/analysis/{analysis_id}` - Delete analysis result

### Batch Operations
- `POST /api/analysis/batch` - Create analysis batch
- `GET /api/analysis/batch/{batch_id}` - Get analysis batch
- `GET /api/analysis/batch/{batch_id}/results` - Get batch results

### Version Management
- `POST /api/analysis/version` - Create analysis version
- `GET /api/analysis/version/{version_number}` - Get version by number
- `GET /api/analysis/version/{version_id}/batches` - Get batches by version

### Health
- `GET /health` - Service health check

---

## Stats Service (Port 8004)

### Event Tracking
- `POST /api/stats/projects/{project_id}/events/document-processed` - Track document processing
- `POST /api/stats/projects/{project_id}/events/document-uploaded` - Track document upload
- `POST /api/stats/projects/{project_id}/events/embeddings-updated` - Track embeddings update
- `POST /api/stats/projects/{project_id}/events/graph-updated` - Track graph update

### Statistics
- `GET /api/stats/projects/{project_id}/summary` - Get project statistics
- `GET /api/stats/projects/{project_id}/activity` - Get project activity

---

## LLM Service (Port 8007)

### Text Analysis
- `POST /api/llm/analyze` - Analyze text content
- `POST /api/llm/summarize` - Summarize text
- `POST /api/llm/categorize` - Categorize content

### Batch Operations
- `POST /api/llm/analyze/batch` - Batch text analysis
- `POST /api/llm/summarize/batch` - Batch summarization

### Model Management
- `GET /api/llm/models` - List available models
- `POST /api/llm/models/{model_id}/load` - Load specific model

---

## AI Agent Service (Port 8008)

### Health Checks
- `GET /livez` - Liveness probe - checks if service is running
- `GET /healthz` - Readiness probe - checks if service is ready to accept traffic
- `GET /health` - Health check endpoint

### Real-time Communication
- `WebSocket /ws/autogen/{session_id}` - WebSocket endpoint for real-time AutoGen conversations
- `WebSocket /ws/autogen/{session_id}/` - WebSocket endpoint for real-time AutoGen conversations (trailing slash)
- `WebSocket /ws/autogen/discussions/{session_id}` - WebSocket endpoint for Discussions UI (maps to core autogen handler)

---

## WebSocket Service (Port 8009)

### Health
- `GET /health` - Health check endpoint

---

## Service Registry (Port 8011)

### Health Checks
- `GET /livez` - Liveness probe - checks if service is running
- `GET /healthz` - Readiness probe - checks if service is ready to accept traffic
- `GET /health` - Health check endpoint

### Service Management
- `POST /services/register` - Register a new service
- `DELETE /services/{service_name}` - Unregister a service
- `GET /services` - Get status of all services
- `GET /services/{service_name}` - Get status of a specific service

### Monitoring
- `GET /health/summary` - Get health summary of all services

### Real-time Updates
- `WebSocket /ws` - WebSocket endpoint for real-time health updates

---

## Cloud Tools Service (Port 8012)

### Cloud Credentials
- `POST /projects/{project_id}/credentials` - Add cloud credentials for a project

### Cloud Assessment
- `POST /projects/{project_id}/assessments` - Start cloud environment assessment
- `GET /projects/{project_id}/assessments` - Get all assessments for a project
- `GET /assessments/{assessment_id}` - Get specific assessment details

### Resource Management
- `GET /projects/{project_id}/resources` - Get all discovered resources for a project
- `GET /projects/{project_id}/resources/summary` - Get resource summary by type and provider

### Health
- `GET /health` - Health check endpoint

---

## Security Service (Port 8015)

### Authentication
- `POST /auth/login` - User login
- `POST /auth/logout` - User logout
- `GET /auth/me` - Get current user information

### Tenant Management
- `POST /tenants` - Create new tenant (super admin only)
- `GET /tenants/{tenant_id}` - Get tenant information

### User Management
- `POST /tenants/{tenant_id}/users` - Create new user in tenant
- `GET /tenants/{tenant_id}/users` - Get all users in tenant

### Audit & Security
- `GET /tenants/{tenant_id}/audit-logs` - Get audit logs for tenant
- `GET /permissions/check/{permission}` - Check if current user has specific permission

### Health
- `GET /health` - Health check endpoint

---

## Collaboration Service (Port 8016)

### Workspace Management
- `POST /workspaces` - Create new team workspace
- `GET /workspaces/{workspace_id}` - Get workspace details

### Activity Management
- `POST /workspaces/{workspace_id}/activities` - Add activity to workspace
- `GET /workspaces/{workspace_id}/activities` - Get workspace activities

### Notifications
- `POST /workspaces/{workspace_id}/notifications` - Create notification
- `GET /users/{user_id}/notifications` - Get user notifications

### Real-time Communication
- `WebSocket /ws/{user_id}` - WebSocket endpoint for real-time communication

### Statistics
- `GET /stats` - Get collaboration statistics

### Health
- `GET /health` - Health check endpoint

---

## Knowledge Service (Port 8017)

### Document Management
- `POST /documents` - Add new knowledge document
- `GET /documents` - List knowledge documents
- `GET /documents/{doc_id}` - Get specific document

### Search & Analysis
- `POST /search` - Search knowledge documents
- `POST /qa` - Ask question and get AI-generated answer
- `POST /qa/projects/{project_id}` - Project-scoped QA using vector-service retrieval
- `GET /qa/{qa_id}` - Get specific Q&A pair

### Knowledge Graphs
- `POST /knowledge-graphs` - Create knowledge graph from documents
- `GET /knowledge-graphs/{graph_id}` - Get knowledge graph

### Statistics
- `GET /stats` - Get knowledge base statistics

### Health
- `GET /health` - Health check endpoint

---

## Common Patterns

### Authentication
All services use Bearer token authentication:
```
Authorization: Bearer {SERVICE_AUTH_TOKEN}
```

### Correlation ID
Most endpoints support correlation ID for request tracing:
```
X-Correlation-ID: {correlation_id}
```

### Error Responses
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `405` - Method Not Allowed
- `500` - Internal Server Error

### Pagination
List endpoints support pagination:
```
?limit=50&offset=0
```

---

## Service Dependencies

### Document Service Dependencies
- Storage Service (file operations)
- Vector Service (embeddings)
- Graph Service (entity extraction)
- Project Service (project metadata)
- Analytics Service (analysis results)
- Stats Service (event tracking)
- LLM Service (content analysis)

### Backend Dependencies
- Project Service (project data)
- Stats Service (statistics)
- WebSocket Service (real-time communication)
- Service Registry (service discovery)

### Reporting Service Dependencies
- Project Service (project metadata)
- Storage Service (file storage)
- MinIO (report storage)

### AI Agent Service Dependencies
- LLM Service (language model processing)
- Project Service (project context)
- WebSocket Service (real-time communication)

### WebSocket Service Dependencies
- Service Registry (service discovery)

### Service Registry Dependencies
- Docker (container monitoring)

### Cloud Tools Service Dependencies
- WebSocket Service (real-time notifications)
- Storage Service (assessment reports)

### Security Service Dependencies
- WebSocket Service (real-time notifications)

### Collaboration Service Dependencies
- Project Service (project data)
- Storage Service (file sharing)

### Knowledge Service Dependencies
- Document Service (document processing)
- Vector Service (semantic search)
- Storage Service (file operations)
- WebSocket Service (notifications)
- LLM Service (question answering)

### Cross-Service Communication
Services communicate via HTTP calls with proper error handling and fallbacks.

---

## Development Notes

When adding new endpoints:
1. Update this document with the new endpoint
2. Include method, path, and brief description
3. Note any special requirements (auth, parameters, etc.)
4. Update dependent services if needed

When modifying existing endpoints:
1. Update the description if functionality changes
2. Note breaking changes
3. Update client code accordingly

This document should be kept in sync with actual service implementations.