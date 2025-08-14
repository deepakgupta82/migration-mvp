# Copilot Instructions for Nagarro's Ascent Platform

## Architecture Overview

This is an **enterprise cloud migration assessment platform** with separated upload/processing workflow, multi-database architecture, and AI agent orchestration.

### Core Services Architecture
- **Frontend** (React/TypeScript, port 3000): Command center UI with Mantine components
- **Backend** (FastAPI, port 8000): Main API with AI agents, WebSocket streaming, document processing
- **Project Service** (FastAPI, port 8002): Project management and PostgreSQL operations  
- **Reporting Service** (FastAPI, port 8003): PDF/DOCX generation via MinIO storage

### Data Layer (4 Databases)
- **PostgreSQL** (port 5432): Projects, LLM configs, user data (`projectdb`/`projectuser`/`projectpass`)
- **ChromaDB** (`./data/chroma_db`): Vector embeddings using `all-MiniLM-L6-v2` model
- **Neo4j** (ports 7474/7687): IT infrastructure graph (`neo4j`/`password`)
- **MinIO** (ports 9000/9001): Object storage with buckets (`minioadmin`/`minioadmin`)

## Development Workflow

### Startup Sequence (Critical Order)
```bash
# 1. Infrastructure first (Docker/Rancher Desktop required)
docker-compose up -d postgres neo4j weaviate minio

# 2. Platform services (separate terminals)
cd project-service && python main.py      # Port 8002 first
cd backend && python -m app.main          # Port 8000 (20min startup - ML models)  
cd frontend && npm start                   # Port 3000 (auto-opens browser)
```

### Build Commands
```bash
# Fast development (recommended)
.\build-images.ps1                        # One-time: build images (8-15min)
.\start-platform-dev.ps1                 # Daily: fast startup (2-3min)

# Full Docker compose
docker-compose up -d                      # Traditional: 20+ min startup
```

## Key Code Patterns

### Document Processing Pipeline (Recently Refactored)
- **Upload**: `POST /upload/{project_id}` → MinIO storage only (no immediate processing)
- **Processing**: `POST /api/projects/{project_id}/process-all` → Background MarkItDown → ChromaDB → Neo4j
- **Selective**: `POST /api/projects/{project_id}/process-selected` → Process specific files
- **Status**: `GET /api/projects/{project_id}/uploaded-files` → List pending/processed files

### RAGService Pattern (`backend/app/core/rag_service.py`)
```python
# Conversion chain: MarkItDown → PyMuPDF → pdfminer → error document
# Storage: MinIO uploads_parsed/{filename}.md (canonical)
# Embeddings: ChromaDB project_{project_id} collections  
# Entities: Neo4j graph with project_id isolation
# Fallback: Always record metadata, skip expensive ops on failure
```

### WebSocket Broadcasting (`backend/app/core/process_ws.py`)
```python
# Project-scoped connections: /ws/{project_id}
# Messages: CONVERTED_TO_MD, EMBEDDINGS_ADDED, GRAPH_UPDATED
# Windows-safe: Handles ConnectionResetError gracefully
```

### LLM Factory Pattern (`backend/app/core/llm_config.py`)
```python
# Provider-based initialization: OpenAI/Anthropic/Gemini/Ollama
# Project-specific configs stored in PostgreSQL llm_configurations table
# Lazy loading with fallback handling for missing configurations
```

## Service Communication

### Storage Keys (MinIO)
```
projects/{project_id}/uploads/raw/{filename}      # Original uploads
projects/{project_id}/uploads/parsed/{filename}   # Canonical .md 
projects/{project_id}/metadata/{filename}         # Processing metadata
```

### Database Patterns
- **Project isolation**: All data includes `project_id` for multi-tenancy
- **ChromaDB collections**: `project_{project_id}` naming convention
- **Neo4j relationships**: Use `project_id` property for filtering
- **Connection pooling**: GraphService uses persistent Neo4j driver pool

## Troubleshooting

### Common Issues
- **Backend 20min startup**: Normal due to ML model loading (sentence-transformers)
- **Missing config.local.json**: Warning only, uses environment defaults
- **NoSuchKey errors**: Expected on first upload, not actual errors
- **Neo4j pool reinit**: Normal behavior, logs IPv4 loopback preference

### Health Checks
```bash
curl http://localhost:8002/health         # Project Service
curl http://localhost:8000/health         # Backend API  
curl http://localhost:3000                # Frontend
docker-compose ps                         # Infrastructure
```

### Performance Tips
- **RAM allocation**: 16GB to Docker recommended (8GB minimum)
- **Rancher Desktop**: Use dockerd runtime, not containerd
- **Build caching**: Keep Docker running between builds
- **Stats caching**: Platform/project stats use event-driven updates

## Project-Specific Conventions

### Error Handling
- Always record metadata even for failed conversions (`conversion_strategy` field)
- Separate upload from processing for better UX control
- WebSocket notifications for async operations with correlation IDs
- Graceful degradation: skip embeddings/entities on conversion failure

### AI Agent Integration  
- CrewAI orchestration in `backend/app/core/crew.py`
- Agent callbacks stream to WebSocket for real-time feedback
- LLM configurations stored in database, not hardcoded
- Support for multiple providers via factory pattern

### File Processing
- MarkItDown library (not MegaParse) for document conversion
- Multi-stage fallback: MarkItDown → PyMuPDF → pdfminer → error doc
- Reprocess flag bypasses cached canonical .md files
- Local temp files saved for debugging (`/tmp/{filename}`)

This platform emphasizes **separation of concerns**, **graceful failure handling**, and **enterprise-grade multi-tenancy** patterns.
