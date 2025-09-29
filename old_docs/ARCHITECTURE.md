# Ascent Platform Architecture (Current)

This document describes the current microservices architecture, runtime topology, data flows, and key interfaces for Nagarro's Ascent cloud migration assessment platform. It is tailored for automated agents and integrators.

It reflects the gateway-first design, strict service boundaries, and the refactored document-processing pipeline. Infrastructure (PostgreSQL, Neo4j, MinIO, Redis) runs in Docker; all app services run locally during development.

## Runtime Topology

- Frontend (React/TypeScript)
  - Port: 3000
  - Role: Command center UI (Mantine), calls Backend API Gateway only
- Backend API Gateway (FastAPI)
  - Port: 8000
  - Role: Single entry point for the UI; proxies requests to domain services; enforces service-to-service auth; streams events via WebSocket
- Project Service (FastAPI)
  - Port: 8002
  - Role: Project management (CRUD), LLM config CRUD, project-scoped metadata in PostgreSQL
- Reporting Service (FastAPI)
  - Port: 8003
  - Role: Document/PDF/DOCX generation and artifact storage in MinIO
- Document Service (FastAPI)
  - Port: 8004
  - Role: Upload orchestration, file listing, background conversion to canonical Markdown; interacts with Storage Service via HTTP
- Vector Service (FastAPI)
  - Port: 8005
  - Role: Vector embeddings and search (ChromaDB). Collections are project-scoped
- Graph Service (FastAPI)
  - Port: 8006
  - Role: Knowledge graph operations (Neo4j), project-isolated graph updates
- LLM Service (FastAPI)
  - Port: 8007
  - Role: Provider-agnostic LLM access via a factory; project-specific configurations from PostgreSQL
- AI Agent Service (FastAPI)
  - Port: 8008
  - Role: Crew/agent orchestration; long-running operations stream progress via WebSocket
- WebSocket Gateway
  - Port: 8009
  - Role: Project-scoped real-time channels (conversion, embeddings, graph updates, dashboard)
- Storage Service (FastAPI)
  - Port: 8010
  - Role: HTTP façade for object storage (MinIO/S3) and local filesystem dev mode
- Service Registry (FastAPI)
  - Port: 8011
  - Role: Service discovery and distributed health monitoring
- Cloud Tools Service (FastAPI)
  - Port: 8012
  - Role: Native cloud tool integrations (AWS, Azure, GCP) and migration assessment
- Agent Orchestration Service (FastAPI)
  - Port: 8013
  - Role: AI agent monitoring, task assignment, and performance analytics
- Analytics Service (FastAPI)
  - Port: 8014
  - Role: Advanced business intelligence and predictive analytics
- Security Service (FastAPI)
  - Port: 8015
  - Role: Multi-tenant authentication, RBAC, and security policy management
- Knowledge Service (FastAPI)
  - Port: 8016
  - Role: Advanced RAG, semantic search, and knowledge graph management
- Collaboration Service (FastAPI)
  - Port: 8017
  - Role: Real-time team collaboration, notifications, and activity tracking

## Infrastructure (Docker)

- PostgreSQL (5432)
  - Database: projectdb (prod), projectdb_dev (dev)
  - Holds projects, users, LLM configurations, and platform metadata
- Neo4j (7474/7687)
  - Project-isolated knowledge graph; relationships and nodes tagged with `project_id`
- MinIO (9000/9001)
  - Object storage for uploads, canonical Markdown, and processing metadata
- Redis (6379)
  - Caching for document conversion results and background job status

Note: In development, only MinIO, Redis, PostgreSQL, and Neo4j run in Docker. All microservices run locally.

## Service-to-Service Communication

- Transport: HTTP only (no cross-imports)
- Authorization: Bearer token on every inter-service call
  - Header: `Authorization: Bearer {SERVICE_AUTH_TOKEN}`
  - Gateway enforces token on inbound service calls; ServiceClient injects the token on outbound calls
- Timeouts and limits: httpx AsyncClient with sane timeouts for internal calls

### Gateway ServiceClient Key Behaviors

- Always injects Authorization bearer token on outbound requests
- Multipart uploads: sends list of ('files', (filename, bytes, content_type)) tuples to support multi-file upload
- Document processing (selected): uses payload `{ "file_names": [..], "reprocess": false }`
- Normalizes legacy routes (e.g., `/upload/{project_id}`) to new service endpoints

## API Gateway Responsibilities

- Uniform API surface for the frontend under `/api/*`
- Route mapping to domain services (examples):
  - Projects → Project Service (`/api/projects/*`)
  - LLM providers/configs → LLM Service/Project Service
  - Documents → Document Service (`/api/projects/{project_id}/upload`, `.../process-*`, `.../uploaded-files`)
  - Storage passthrough (admin-only utilities) → Storage Service
- Legacy compatibility routes maintained where needed (e.g., `/upload/{project_id}`), internally delegated to the Document Service

## Storage Service Conventions (MinIO)

Object keys follow strict, project-scoped paths:

- `projects/{project_id}/uploads/raw/{filename}` — original uploads
- `projects/{project_id}/uploads/parsed/{filename}` — canonical Markdown (.md)
- `projects/{project_id}/metadata/{filename}` — processing metadata (JSON)

Categories used by the Storage Service API:

- `uploads_raw`, `uploads_parsed`, `metadata`

### Storage Service HTTP API (selected)

- `POST /api/storage/projects/{project_id}/upload/{category}` — multipart upload
- `GET /api/storage/projects/{project_id}/files/{category}` — list objects
- `GET /api/storage/projects/{project_id}/download/{category}/{filename}` — stream object
- `DELETE /api/storage/projects/{project_id}/delete/{category}/{filename}` — delete object

## Document Ingestion and Processing

- Upload (Frontend → Gateway → Document Service → Storage Service)
  - Endpoint: `POST /api/projects/{project_id}/upload`
  - Behavior: Stores files to `uploads_raw`; no immediate processing
- Listing
  - Endpoint: `GET /api/projects/{project_id}/uploaded-files`
  - Behavior: Returns pending vs. processed status by comparing `uploads_raw` and `uploads_parsed`
- Processing
  - All: `POST /api/projects/{project_id}/process-all`
  - Selected: `POST /api/projects/{project_id}/process-selected` with body `{ "file_names": ["a.pdf"], "reprocess": false }`
  - Behavior: Background task downloads raw files; converts to Markdown; uploads `.md` to `uploads_parsed` and metadata JSON to `metadata`

### Endpoints (Document Service via Gateway)

- `POST /api/projects/{project_id}/upload` → `POST document-service /api/documents/{project_id}/upload`
- `GET /api/projects/{project_id}/uploaded-files` → `GET document-service /api/documents/{project_id}/files`
- `POST /api/projects/{project_id}/process-all` → `POST document-service /api/documents/{project_id}/process-all`
- `POST /api/projects/{project_id}/process-selected` → `POST document-service /api/documents/{project_id}/process-selected`

### Conversion Strategy

- Primary: MarkItDown (canonical Markdown output)
- Fallbacks: PyMuPDF (for PDFs) → pdfminer (for PDFs)
- Error handling: Generates an error document on failure; metadata always recorded
- Caching: Redis stores per-file conversion results and job status (`document_conversion:{project_id}:{filename}`)
- Existing content short-circuit: If Markdown already exists in storage and `reprocess=false`, the system reuses it

### WebSocket Notifications

- Channel prefix: `/ws/{project_id}`
- Typical events: `CONVERTED_TO_MD`, `EMBEDDINGS_ADDED`, `GRAPH_UPDATED`
- Behavior: Handles Windows connection resets gracefully; messages are correlation-ID aware

## Vector and Graph Updates

- Embeddings
  - Store: ChromaDB; collection naming convention `project_{project_id}`
  - Trigger: After successful Markdown conversion
- Knowledge Graph
  - Store: Neo4j; all nodes/edges carry `project_id` for isolation
  - Trigger: Post-conversion entity extraction/relations (service-specific logic)

### High-level Flow (ASCII)

Frontend → Gateway → Document → Storage

1) UI POST /api/projects/{pid}/upload (multipart)
2) Gateway → Document Service `/api/documents/{pid}/upload`
3) Document → Storage (category `uploads_raw`)
4) UI POST /api/projects/{pid}/process-all
5) Document background: download raw → convert (MarkItDown → fallbacks) → upload `.md` to `uploads_parsed` and metadata
6) Optional: Vector embeddings in Chroma, Graph updates in Neo4j
7) WebSocket events broadcast progress to `/ws/{pid}` subscribers

## LLM Configuration Pattern

- Factory-based initialization for providers (OpenAI, Anthropic, Gemini, Ollama)
- Project-specific configurations stored in PostgreSQL (`llm_configurations`)
- Lazy loading with safe fallbacks for missing configurations

## Multi-Tenancy Rules

- Every resource is scoped with `project_id`
- Storage keys, vector collections, graph properties, and WebSocket channels all include `project_id`
- Gateway and services validate project scope on all operations

## Environment and Settings

- `SERVICE_AUTH_TOKEN` — required for inter-service calls
- Database/Storage settings via environment; local defaults when `config.local.json` is missing
- Windows considerations: WebSocket layer and file path handling are Windows-safe

### Ports and URLs (Local Dev)

- Frontend: http://localhost:3000
- Backend Gateway: http://localhost:8000
- Project: http://localhost:8002
- Reporting: http://localhost:8003
- Document: http://localhost:8004
- Vector: http://localhost:8005
- Graph: http://localhost:8006
- LLM: http://localhost:8007
- AI Agent: http://localhost:8008
- WebSocket: http://localhost:8009
- Storage: http://localhost:8010
- Service Registry: http://localhost:8011
- Cloud Tools: http://localhost:8012
- Agent Orchestration: http://localhost:8013
- Analytics: http://localhost:8014
- Security: http://localhost:8015
- Knowledge: http://localhost:8016
- Collaboration: http://localhost:8017
- MinIO: http://localhost:9001 (console), S3 API on 9000
- PostgreSQL: localhost:5432, Neo4j: 7474/7687, Redis: 6379

## Phase 3 Enhanced Capabilities

### Service Registry & Health Monitoring
- Centralized service discovery and registration
- Distributed health checks with failover detection
- Service dependency mapping and monitoring
- Automatic service endpoint updates

### Cloud Tools Integration
- Native integrations with AWS, Azure, and GCP
- Automated cloud resource discovery and assessment
- Cost analysis and optimization recommendations
- Migration pathway analysis and planning
- Real-time cloud environment monitoring

### AI Agent Orchestration
- Advanced agent monitoring and performance analytics
- Dynamic task assignment and load balancing
- Agent health tracking and automatic recovery
- Real-time agent communication and coordination
- Comprehensive agent lifecycle management

### Advanced Analytics & Business Intelligence
- Migration complexity analysis and prediction
- Cost optimization insights and recommendations
- Agent efficiency analytics and performance metrics
- Predictive analytics for migration planning
- Advanced reporting and dashboard capabilities

### Multi-Tenant Security & RBAC
- Enterprise-grade multi-tenant authentication
- Fine-grained role-based access control (RBAC)
- Security policy management and enforcement
- Comprehensive audit logging and compliance
- JWT token management and session control

### Enhanced RAG & Knowledge Management
- Advanced semantic search with multiple strategies
- Knowledge graph construction and querying
- Intelligent document indexing and categorization
- Context-aware question answering system
- Knowledge base curation and management

### Real-time Collaboration & Notifications
- Team workspace management and coordination
- Real-time activity feeds and timeline tracking
- Intelligent notification system with multiple channels
- Cross-service event aggregation and broadcasting
- WebSocket-based real-time communication

## Health and Troubleshooting

- Health endpoints: Each service exposes `/health`
- Known behaviors:
  - ML model loading (e.g., sentence-transformers) can increase startup times
  - `NoSuchKey` from MinIO on first-time access is expected; not an error
  - Neo4j driver may reinitialize pool; logs are normal
- Resource tips:
  - Allocate sufficient RAM to Docker (16GB recommended, 8GB minimum)
  - Keep Docker running between builds for better caching

### Common Pitfalls and Remedies

- 404 on upload/list: verify gateway routes map to `/api/documents/*` and legacy `/upload/{pid}` delegates to Document Service
- Multipart upload failures: ensure multipart uses repeated `files` parts (list of tuples) and correct content types
- "No module named app.core.storage_service": indicates cross-import; replace with HTTP calls to Storage Service
- MinIO `NoSuchKey`: expected for first-time access; treat as non-error in code paths
- Windows ConnectionResetError on WebSocket: handled; okay to ignore transient warnings

## Development Workflow (Local + Docker Infra)

- Start infrastructure (Docker): PostgreSQL, Neo4j, MinIO, Redis
- Run services locally in this preferred order:
  1) Project Service (8002)
  2) Backend API Gateway (8000)
  3) Remaining services as needed: Reporting (8003), Document (8004), Vector (8005), Graph (8006), LLM (8007), AI Agent (8008), WebSocket (8009), Storage (8010)
- Frontend runs on 3000 and talks to the Gateway

## Restart Guidance

- After code changes to: Gateway, Document Service, Project Service, or Storage Service, restart the affected service(s)
- After model or provider changes: restart LLM/Vector/Graph services as appropriate

## Interface Summary (Selected)

- Gateway (8000)
  - `/api/projects/*` → Project Service
  - `/api/projects/{project_id}/upload` → Document Service
  - `/api/projects/{project_id}/uploaded-files` → Document Service
  - `/api/projects/{project_id}/process-all` → Document Service
  - `/api/projects/{project_id}/process-selected` → Document Service
  - `/api/llm/*` → LLM Service / Project Service
- Document Service (8004, base `/api/documents`)
  - `POST /{project_id}/upload` — multipart uploads (forwards to Storage Service)
  - `GET /{project_id}/files` — combined view of raw vs. parsed
  - `POST /{project_id}/process-all` — background processing
  - `POST /{project_id}/process-selected` — selective processing

## Security and AuthZ Model

- Bearer token is mandatory for all service-to-service requests
- Gateway validates token and scopes requests per `project_id`
- Services should avoid trusting caller input; rely on Gateway or internal checks for isolation

## Observability

- Structured logs per service; include `project_id` and correlation IDs when available
- WebSocket broadcasts for long-running operations; clients can subscribe on `/ws/{project_id}`

## Known Variants / Legacy

- Some legacy endpoints exist under the Gateway for frontend compatibility. These internally delegate to the appropriate new microservice.
- Vector store defaults to ChromaDB; historical references to Weaviate may exist in docs but are not active in the current runtime.

## Error Handling and Metadata

- Always write processing metadata even on failure (`conversion_strategy`, `timestamp`, status)
- Graceful degradation: skip embeddings or graph updates if conversion failed
- Local debug artifacts saved to `markitdown_debug/` per file

## Security and Logging

- Bearer token required for service-to-service calls
- Project-scoped access patterns reduce lateral data exposure
- Centralized logging via Gateway; services log with correlation IDs when available

## Notes and Conventions

- Frontend must call the Gateway only; direct calls to microservices are not supported
- All service URLs and ports listed are the current defaults for local development
- Vector store defaults to ChromaDB (local path: `./data/chroma_db`)

---

This document is intended for agents and developers integrating with or extending the platform. It captures the current, gateway-centric architecture with isolated domain services and a robust, fault-tolerant document processing pipeline.

Appendix A: Glossary
- Canonical Markdown: The standardized .md representation of any uploaded document.
- Categories: Storage folders mapped as API categories (`uploads_raw`, `uploads_parsed`, `metadata`).
- Legacy route: An endpoint kept for backward compatibility that now proxies to the newer service path.
