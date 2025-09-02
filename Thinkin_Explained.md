# Nagarro Ascent Platform: Document Processing and Information Extraction

## Overview

The Nagarro Ascent Platform is a comprehensive cloud migration assessment platform that leverages advanced AI and document processing technologies to analyze infrastructure documents, extract valuable insights, and generate actionable migration recommendations. This document provides a complete technical overview of the platform's document processing and information extraction capabilities.

## System Architecture

### Core Components

The platform follows a microservices architecture with 17 specialized services:

#### Frontend Layer (Port 3000)
- **Technology**: React 18 with TypeScript, Mantine UI
- **Key Components**:
  - `FileUpload.tsx` - Document upload interface
  - `ProcessingProgressView.tsx` - Real-time processing monitoring
  - `ChatInterface.tsx` - RAG knowledge queries
  - `GraphVisualizer.tsx` - Knowledge graph visualization
  - `AgentActivityLog.tsx` - AI agent activity tracking

#### API Gateway (Port 8000)
- **Technology**: FastAPI
- **Responsibilities**:
  - Single entry point for frontend requests
  - Service-to-service authentication
  - Request routing and load balancing
  - WebSocket coordination for real-time updates

#### Document Processing Services

**Document Service (Port 8003)**
- **Primary Technology**: Unstructured.io for JSONL processing
- **Capabilities**:
  - Multi-format support (PDF, DOCX, PPTX, TXT, MD, HTML, CSV)
  - Dual processing workflows (Enhanced with Unstructured.io, Traditional with MarkItDown)
  - OCR support via Tesseract
  - Automatic service integration (Vector, Graph, WebSocket)

**Vector Service (Port 8005)**
- **Technology**: Weaviate for vector embeddings
- **Capabilities**:
  - Semantic search and similarity matching
  - Project-scoped vector collections
  - Hybrid search (semantic + keyword)
  - Batch processing for large document sets

**Graph Service (Port 8006)**
- **Technology**: Neo4j for knowledge graphs
- **Capabilities**:
  - Entity extraction and relationship mapping
  - Project-isolated graph databases
  - Cypher query execution
  - Graph analytics (centrality, clusters, paths)

#### AI and Analytics Services

**AI Agent Service (Port 8008)**
- **Technology**: CrewAI framework
- **Capabilities**:
  - Multi-agent workflow orchestration
  - Specialized agents for different tasks
  - Real-time progress streaming
  - Background task execution

**LLM Service (Port 8007)**
- **Technology**: Provider-agnostic LLM integration
- **Supported Providers**: OpenAI, Anthropic, Google Gemini, Ollama
- **Capabilities**:
  - Project-specific LLM configurations
  - Lazy loading with fallbacks
  - Token management and cost tracking

#### Supporting Services

**Storage Service (Port 8010)**
- **Technology**: MinIO object storage
- **Capabilities**:
  - Project-scoped file organization
  - Multipart upload handling
  - File versioning and metadata

**WebSocket Service (Port 8009)**
- **Technology**: Real-time communication
- **Capabilities**:
  - Project-scoped channels
  - Progress updates and notifications
  - Cross-service event broadcasting

### Infrastructure Layer

**Containerized Services (Docker)**
- PostgreSQL (5432) - Relational data
- Neo4j (7474/7687) - Graph database
- MinIO (9000/9001) - Object storage
- Redis (6379) - Caching and messaging
- Weaviate (8080) - Vector database

## Document Processing Pipeline

### 1. Document Ingestion

**Upload Process:**
```
Frontend (FileUpload.tsx)
    ↓
API Gateway (POST /api/projects/{id}/upload)
    ↓
Storage Service (MinIO)
    ↓
Document Service (Background Processing)
```

**Key Features:**
- Drag-and-drop interface with progress tracking
- File validation and size limits (100MB max)
- Support for multiple file formats
- Automatic categorization (uploads_raw, uploads_parsed, metadata)

### 2. Document Conversion

**Enhanced Workflow (Primary):**
```python
# Unstructured.io Processing
elements = _u_partition(filename=file_path)
md_content = convert_to_markdown(elements)
jsonl_output = extract_structured_data(elements)
```

**Traditional Workflow (Fallback):**
```python
# MarkItDown with Fallbacks
content = markitdown.convert(file_path)
# Fallbacks: PyMuPDF → pdfminer → pdfplumber
```

**OCR Integration:**
```python
# Tesseract OCR for scanned documents
import pytesseract
text = pytesseract.image_to_string(image)
```

### 3. Information Extraction

**Entity Extraction:**
```python
# From Graph Service
entities = extract_entities(document_content)
relationships = map_relationships(entities)
store_in_neo4j(project_id, entities, relationships)
```

**Vector Embeddings:**
```python
# From Vector Service
chunks = semantic_chunking(document_content)
embeddings = generate_embeddings(chunks)
store_in_weaviate(project_id, chunks, embeddings)
```

### 4. AI Agent Processing

**Analysis Agent:**
```python
agent = AnalysisAgent()
insights = agent.analyze_document(content)
patterns = agent.extract_patterns(content)
recommendations = agent.generate_recommendations(insights)
```

**Post-Processing Agent:**
```python
agent = PostProcessingAgent()
knowledge_data = gather_knowledge_core_data(project_id, document_id)
insights = generate_insights_with_llm(knowledge_data)
store_insights_in_lessons_service(project_id, document_id, insights)
```

## Information Extraction Capabilities

### 1. Document Analysis Agents

**Analysis Agent**
- **Purpose**: Analyzes documents and extracts insights
- **Capabilities**:
  - Document analysis and data extraction
  - Pattern recognition
  - Structured data generation
  - Input types: Text, documents
  - Output types: Structured data, insights

**Assessment Agent**
- **Purpose**: Performs infrastructure assessments
- **Capabilities**:
  - Infrastructure analysis
  - Risk assessment
  - Recommendations generation
  - Input types: Infrastructure data, documents
  - Output types: Assessment reports, recommendations

**Documentation Agent**
- **Purpose**: Generates comprehensive documentation
- **Capabilities**:
  - Document generation
  - Report writing
  - Content formatting
  - Input types: Data, templates
  - Output types: Documents, reports

### 2. Specialized Processing Agents

**Document Research Specialist**
- **Expertise**: Information extraction, data analysis, knowledge synthesis
- **Background**: Fortune 500 companies, technical documentation analysis
- **Capabilities**: Advanced search, pattern identification, insight synthesis

**Content Architecture Specialist**
- **Expertise**: Document structure, information design, technical communication
- **Background**: Consulting firms, technical writing standards
- **Capabilities**: Content organization, information hierarchy, professional formatting

**Document Quality Assurance Specialist**
- **Expertise**: Technical writing, quality control, editorial review
- **Background**: Technical communication, quality management
- **Capabilities**: Consistency verification, accuracy checking, standards compliance

**Lessons Learned Analyst**
- **Expertise**: Knowledge management, document analysis, lessons learned capture
- **Background**: Enterprise document analysis, process improvement
- **Capabilities**: Pattern synthesis, anonymization, confidence scoring

### 3. Multi-Agent Crew Workflows

**Infrastructure Assessment Crew**
- **Agents**: Analysis Agent, Assessment Agent
- **Purpose**: Complete infrastructure analysis workflow
- **Estimated Time**: 15 minutes
- **Requirements**: Project documents, infrastructure inventory

**Documentation Generation Crew**
- **Agents**: Analysis Agent, Documentation Agent
- **Purpose**: Comprehensive documentation generation
- **Estimated Time**: 20 minutes
- **Requirements**: Project data, template preferences

**Migration Planning Crew**
- **Agents**: Analysis Agent, Assessment Agent, Migration Planner
- **Purpose**: End-to-end migration planning workflow
- **Estimated Time**: 30 minutes
- **Requirements**: Current infrastructure, target requirements

## Data Flow Architecture

### Document Processing Flow

```mermaid
graph TD
    A[Frontend Upload] --> B[API Gateway]
    B --> C[Storage Service]
    C --> D[Document Service]
    D --> E{Processing Strategy}
    E -->|Enhanced| F[Unstructured.io]
    E -->|Traditional| G[MarkItDown]
    F --> H[JSONL Output]
    G --> I[Markdown Output]
    H --> J[Vector Service]
    I --> J
    H --> K[Graph Service]
    I --> K
    J --> L[Weaviate]
    K --> M[Neo4j]
    D --> N[WebSocket Service]
    N --> O[Frontend Updates]
```

### Knowledge Query Flow

```mermaid
graph TD
    A[User Query] --> B[ChatInterface.tsx]
    B --> C[API Gateway]
    C --> D[Vector Service]
    D --> E[Weaviate Search]
    E --> F[Graph Service]
    F --> G[Neo4j Enrichment]
    G --> H[LLM Service]
    H --> I[Response Generation]
    I --> J[WebSocket Updates]
    J --> K[Frontend Display]
```

### AI Assessment Flow

```mermaid
graph TD
    A[Assessment Trigger] --> B[ProjectDetailView.tsx]
    B --> C[API Gateway]
    C --> D[AI Agent Service]
    D --> E{Crew Selection}
    E --> F[Infrastructure Crew]
    E --> G[Documentation Crew]
    E --> H[Migration Crew]
    F --> I[Agent Execution]
    G --> I
    H --> I
    I --> J[LLM Processing]
    J --> K[Result Storage]
    K --> L[WebSocket Updates]
    L --> M[AgentActivityLog.tsx]
```

## Configuration and Setup

### Environment Configuration

**Base Configuration (config/config.base.json):**
```json
{
  "document_processing": {
    "max_file_size_mb": 100,
    "supported_formats": ["pdf", "docx", "txt", "md"],
    "chunk_size": 1000,
    "chunk_overlap": 200
  },
  "llm": {
    "providers": {
      "openai": {"model": "gpt-4", "max_tokens": 4000},
      "anthropic": {"model": "claude-3-sonnet-20240229"},
      "google": {"model": "gemini-pro"}
    }
  }
}
```

### Service Dependencies

**Document Service Requirements:**
- Tesseract OCR (for scanned documents)
- Poppler (PDF rendering)
- Ghostscript (PDF utilities)
- Unstructured.io (primary processing)
- MarkItDown (fallback processing)

**AI Agent Service Requirements:**
- CrewAI framework
- Redis (task status tracking)
- PostgreSQL (configuration storage)
- LLM service integration

## User Flows

### 1. Document Upload and Processing

**User Journey:**
1. User selects files in `FileUpload.tsx`
2. Files uploaded to Storage Service via API Gateway
3. Document Service processes files in background
4. Real-time progress via `ProcessingProgressView.tsx`
5. Processed content stored in Vector and Graph databases
6. User notified of completion via WebSocket

**Technical Flow:**
```typescript
// Frontend upload
const uploadFiles = async (files: FileList) => {
  const formData = new FormData();
  Array.from(files).forEach(file => formData.append('files', file));

  const response = await api.post(`/api/projects/${projectId}/upload`, formData);
  return response.data;
};

// Backend processing
@app.post("/api/documents/{project_id}/process-all")
async def process_documents(project_id: str):
    # Start background processing
    job_id = await document_processor.process_all_documents(project_id)
    return {"job_id": job_id, "status": "processing"}
```

### 2. Knowledge Query and Chat

**User Journey:**
1. User enters query in `ChatInterface.tsx`
2. Query sent to Vector Service for semantic search
3. Graph Service provides context enrichment
4. LLM Service generates response
5. Response displayed with source citations

**Technical Flow:**
```typescript
// Frontend query
const queryKnowledge = async (query: string) => {
  const response = await api.post(`/api/projects/${projectId}/query`, {
    query,
    context: "infrastructure_assessment"
  });
  return response.data;
};

// Backend processing
@app.post("/api/projects/{project_id}/query")
async def query_knowledge(project_id: str, query: str):
    # Vector search
    vector_results = await vector_service.search(project_id, query)

    # Graph enrichment
    graph_context = await graph_service.enrich_context(project_id, vector_results)

    # LLM response
    response = await llm_service.generate_response(query, graph_context)

    return {"response": response, "sources": vector_results}
```

### 3. AI Assessment Workflow

**User Journey:**
1. User initiates assessment in `ProjectDetailView.tsx`
2. AI Agent Service starts crew workflow
3. Real-time progress in `AgentActivityLog.tsx`
4. Results stored and displayed
5. Reports generated via Reporting Service

**Technical Flow:**
```typescript
// Frontend assessment trigger
const startAssessment = async (crewType: string) => {
  const response = await api.post('/api/agents/workflows', {
    project_id: projectId,
    crew_type: crewType,
    workflow_config: {}
  });
  return response.data;
};

// Backend workflow
@app.post("/api/agents/workflows")
async def start_workflow(request: WorkflowRequest):
    # Start crew workflow
    job_id = await ai_agent_service.start_crew_workflow(
        request.crew_type,
        request.project_id
    )

    # Return job tracking
    return {"job_id": job_id, "status": "started"}
```

## Real-time Communication

### WebSocket Integration

**Channels and Events:**
```typescript
// Processing updates
/ws/processing/{project_id}
{
  "event": "CONVERTED_TO_MD",
  "data": {"filename": "doc.pdf", "status": "completed"}
}

// Assessment progress
/ws/run_assessment/{project_id}
{
  "event": "AGENT_STEP_COMPLETED",
  "data": {"agent": "analysis_agent", "step": "entity_extraction"}
}

// Platform notifications
/ws/notifications/{user_id}
{
  "event": "PROJECT_UPDATED",
  "data": {"project_id": "123", "action": "document_processed"}
}
```

### Progress Tracking

**Frontend Progress Monitoring:**
```typescript
// Real-time progress updates
useWebSocket(`/ws/processing/${projectId}`, (message) => {
  if (message.event === 'PROCESSING_PROGRESS') {
    setProgress(message.data.progress);
    setCurrentStep(message.data.step);
  }
});
```

## Security and Authentication

### Service-to-Service Authentication

**Bearer Token Pattern:**
```http
Authorization: Bearer service-backend-token
X-Correlation-ID: unique-request-id
```

**Token Management:**
- Gateway validates all inter-service calls
- Services inject tokens on outbound requests
- Correlation IDs track requests across services

### Multi-Tenant Security

**Project Isolation:**
- All resources scoped by `project_id`
- Storage keys, vector collections, graph data isolated
- Gateway enforces project scope on all operations

## Monitoring and Observability

### Health Checks

**Service Health Endpoints:**
```bash
# Individual services
curl http://localhost:8003/health  # Document Service
curl http://localhost:8005/health  # Vector Service
curl http://localhost:8006/health  # Graph Service

# Gateway aggregation
curl http://localhost:8000/api/health  # All services status
```

### Logging and Tracing

**Structured Logging:**
```json
{
  "ts": "2025-09-02T02:34:59.683Z",
  "level": "INFO",
  "service": "document-service",
  "corr_id": "abc-123",
  "project_id": "project-456",
  "msg": "Document processing completed"
}
```

**Correlation ID Tracking:**
- Every request gets unique correlation ID
- Traced across all service calls
- Enables debugging of complex workflows

## Performance Considerations

### Optimization Strategies

**Document Processing:**
- File size limits (100MB max)
- Timeout controls (90s conversion, 30s HTTP)
- Background processing for large files
- Caching of processed results

**Vector Operations:**
- Batch processing (50 documents per batch)
- Semantic chunking with overlap
- Index optimization for search performance

**Graph Operations:**
- Project-isolated databases
- Optimized Cypher queries
- Connection pooling

### Scalability Features

**Concurrent Processing:**
- Multiple document processing jobs
- Parallel agent execution
- WebSocket connection management

**Resource Management:**
- Memory limits for AI agents (512MB)
- Connection pooling for databases
- Automatic cleanup of temporary files

## Integration Patterns

### External Service Integration

**LLM Providers:**
```python
# Provider-agnostic interface
llm_config = {
    "provider": "openai",
    "model": "gpt-4",
    "api_key": os.getenv("OPENAI_API_KEY")
}

response = await llm_service.process(llm_config, prompt)
```

**Cloud Storage:**
```python
# MinIO integration
await storage_service.upload_file(
    project_id=project_id,
    category="uploads_raw",
    filename=filename,
    content=file_content
)
```

### API Gateway Patterns

**Request Routing:**
```python
# Gateway routes to appropriate service
@app.post("/api/projects/{project_id}/upload")
async def upload_documents(project_id: str, files: List[UploadFile]):
    # Route to Document Service
    return await document_service.upload_files(project_id, files)
```

**Service Discovery:**
```python
# Dynamic service location
service_url = await service_registry.get_service_url("document-service")
response = await httpx.post(f"{service_url}/api/process", json=payload)
```

## Conclusion

The Nagarro Ascent Platform provides a comprehensive, AI-powered document processing and information extraction system built on a robust microservices architecture. Key capabilities include:

- **Advanced Document Processing**: Multi-format support with Unstructured.io and OCR integration
- **Intelligent Information Extraction**: AI agents for analysis, assessment, and insights generation
- **Knowledge Management**: Vector embeddings and graph databases for semantic search and relationships
- **Real-time Processing**: WebSocket-based progress tracking and notifications
- **Scalable Architecture**: Microservices with service discovery and health monitoring
- **Security**: Multi-tenant isolation with comprehensive authentication

The platform enables organizations to efficiently process complex infrastructure documents, extract valuable insights, and generate actionable migration recommendations through sophisticated AI workflows and knowledge management capabilities.