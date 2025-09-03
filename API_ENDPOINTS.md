# Migration Platform API Endpoints Reference

This document provides a comprehensive reference of all API endpoints across all services in the migration platform. Each endpoint includes a brief description of its functionality.

## Table of Contents
- [Document Service (Port 8003)](#document-service-port-8003)
- [Project Service (Port 8002)](#project-service-port-8002)
- [Storage Service (Port 8010)](#storage-service-port-8010)
- [Vector Service (Port 8005)](#vector-service-port-8005)
- [Graph Service (Port 8006)](#graph-service-port-8006)
- [Analytics Service (Port 8014)](#analytics-service-port-8014)
- [Stats Service (Port 8004)](#stats-service-port-8004)
- [LLM Service (Port 8007)](#llm-service-port-8007)

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