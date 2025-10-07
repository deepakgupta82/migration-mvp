# Document Processing Service Architecture

## Overview

The Document Processing Service is a comprehensive microservice (port 8003) responsible for handling document upload, conversion, processing, and storage operations within the Migration Platform. It implements a sophisticated pipeline that transforms various document formats into structured, searchable content with rich metadata.

## Service Architecture

### Core Components

- **FastAPI Web Framework**: RESTful API with automatic OpenAPI documentation
- **Structured Processing Pipeline**: Multi-stage document analysis and conversion
- **Service Integration Layer**: Cross-service communication with vector, graph, and storage services
- **Progress Tracking**: Real-time processing status and WebSocket notifications
- **Correlation ID Tracking**: End-to-end request tracing across distributed services

### Key Features

- **Multi-Format Support**: PDF, DOCX, XLSX, PPTX, TXT, MD, HTML, and more
- **OCR Integration**: Tesseract-based text extraction for scanned documents
- **Structured Output**: JSONL format with rich metadata and element classification
- **Batch Processing**: Parallel document processing with progress tracking
- **Service Discovery**: Dynamic service URL resolution
- **Health Monitoring**: Comprehensive health checks and dependency validation

## Technology Stack

### Core Dependencies

| Component | Purpose | Version |
|-----------|---------|---------|
| **FastAPI** | Web framework and API | Latest |
| **Uvicorn** | ASGI server | Latest |
| **MarkItDown** | Primary document conversion | ≥0.1.2 |
| **Unstructured.io** | Advanced document partitioning | ≥0.14.6 |
| **MinerU** | Advanced PDF layout analysis and structural extraction | Core |
| **PyMuPDF** | PDF text extraction fallback | ≥1.24.10 |
| **Tesseract OCR** | Optical character recognition | Latest |

### Supporting Libraries

- **Redis**: Caching and status tracking
- **MinIO**: Object storage integration
- **PostgreSQL**: Metadata persistence
- **WebSocket**: Real-time notifications
- **LangDetect**: Language identification
- **MSOffice Crypto Tool**: Encrypted document handling

### Development Tools

- **Python-Dotenv**: Environment configuration
- **HTTTPX**: Async HTTP client
- **AsyncIO**: Concurrent processing
- **ThreadPoolExecutor**: CPU-bound operation isolation

## Processing Pipeline Stages

### Stage 1: Document Ingestion

**Endpoint**: `POST /api/documents/process`
**Responsibilities**:
- File upload validation (size, type, integrity)
- Temporary file management
- Correlation ID assignment
- Initial metadata extraction

**Validation Rules**:
- Maximum file size: 100MB
- Supported formats: PDF, DOCX, XLSX, PPTX, TXT, MD, HTML, XML, JSON, CSV, RTF, ODT, ODS, ODP
- File integrity checks (non-empty, readable)

### Stage 2: Document Conversion & Structuring

**Primary Strategy**: Unstructured.io High-Resolution Partitioning
**Fallback Strategies**:
1. MarkItDown conversion
2. PyMuPDF text extraction
3. pdfminer fallback
4. pdfplumber advanced PDF processing

**Output Format**: Structured JSONL with element classification

**Element Types**:
- `title`: Document titles and headings
- `narrative_text`: Body text and paragraphs
- `list_item`: Bulleted or numbered lists
- `table`: Tabular data with structure
- `image`: Embedded images and figures
- `header`: Section headers
- `footer`: Page footers
- `caption`: Table/figure captions

### Stage 3: Content Enrichment

**LLM Analysis Integration**:
- Document summarization
- Content categorization
- Quality scoring
- Confidence assessment

**Section Enrichment**:
- Logical section identification
- Entity extraction
- Relationship detection
- Token budgeting and optimization

### Stage 4: Semantic Embedding

**Vector Service Integration**:
- Document chunking (semantic/layout-aware)
- Embedding generation
- Vector storage in specialized collections
- Kind-aware embeddings (raw_chunks, entity_cards, triple_cards)

**Chunking Strategies**:
- JSONL-aware chunking
- Semantic boundary detection
- Layout preservation
- Multi-modal content handling

### Stage 5: Knowledge Graph Construction

**Graph Service Integration**:
- Entity extraction and disambiguation
- Relationship identification
- Knowledge graph population
- Confidence scoring and validation

**Processing Modes**:
- Single document processing
- Batch processing with parallel execution
- Incremental updates
- Retry logic with progressive timeouts

### Stage 6: Completion & Notification

**WebSocket Notifications**:
- Real-time progress updates
- Processing status broadcasts
- Completion confirmations
- Error notifications

**Analytics Integration**:
- Processing metrics collection
- Performance statistics
- Usage analytics
- Error tracking

### Stage 7: Fusion Capabilities

**Entity Deduplication and Canonicalization**:
- Cross-document entity resolution using multi-strategy matching
- Exact, fuzzy, attribute, and semantic matching approaches
- Union-find clustering for entity grouping
- Provenance tracking for canonical entities
- Confidence scoring and evidence aggregation

**Fusion Orchestrator**:
- Incremental fusion runs with entity and relationship deduplication
- Canonical entity and relationship creation
- Vector upsert for canonical entity and triple cards
- Analytics event emission for fusion metrics
- Deduplication ratio calculation and reporting

**Key Components**:
- `fusion_orchestrator.py`: Main orchestration logic
- `entity_resolver.py`: Multi-strategy entity matching
- `canonical_id_manager.py`: Neo4j persistence for canonical entities
- `graph_builder.py`: High-level graph building with resolution

## Data Flow Architecture

### Input Processing Flow

```
Document Upload → Validation → Temporary Storage → Processing Pipeline
       ↓              ↓              ↓              ↓
   File Check → Type Check → Size Check → Correlation ID Assignment
```

### Processing Pipeline Flow

```
Raw Document → Conversion Strategy Selection → Structured Elements → Enrichment
       ↓              ↓                           ↓              ↓
   Unstructured.io → MarkItDown → PyMuPDF → pdfminer → LLM Analysis → Section Enrichment
```

### Output Distribution Flow

```
Structured JSONL → Storage Service → Vector Service → Graph Service → WebSocket
       ↓              ↓              ↓              ↓              ↓
   MinIO Storage → Embedding → Knowledge Graph → Notifications → Analytics
```

### Service Integration Flow

```
Document Service → Service Discovery → Cross-Service Calls → Response Aggregation
       ↓              ↓              ↓              ↓
   URL Resolution → HTTP Requests → Result Processing → Status Updates
```

## File Handling Capabilities

### Supported File Formats

| Format | Primary Processor | OCR Required | Notes |
|--------|------------------|--------------|-------|
| PDF | Unstructured.io / MinerU | Optional | High-res partitioning, table extraction, layout analysis, reading order, section paths, multi-page table merging |
| DOCX | Unstructured.io | No | Native Office format support |
| XLSX | Unstructured.io / Streaming parser | No | Spreadsheet structure preservation, column type inference, large file streaming |
| PPTX | Unstructured.io / PowerPoint parser | No | Presentation content extraction, slide-level structure, notes processing |
| TXT | Direct processing | No | Plain text handling |
| MD | Direct processing | No | Markdown format support |
| HTML | Unstructured.io | No | Web content extraction |
| Images | Tesseract OCR | Yes | Embedded image processing |
| ZIP | Automatic extraction | No | Archive processing with recursive document handling |

### File Size and Performance Limits

- **Maximum File Size**: 100MB
- **PDF Page Limit**: 50 pages (configurable)
- **Processing Timeout**: 90 seconds (configurable)
- **Concurrent Integrations**: 2 parallel services (configurable)

### Temporary File Management

- Secure temporary directory creation
- Automatic cleanup after processing
- File locking prevention
- Memory-efficient streaming for large files

### Streaming Processing for Large Files

**JSONL Streaming Writer**:
- Progressive JSONL writing without full buffering
- Memory ceiling: <100MB regardless of file size
- Error recovery with partial output
- Async context manager support

**Spreadsheet Streaming Parser**:
- Row-by-row Excel/CSV iteration
- Column type inference on sampled rows
- Supports .xlsx and .csv formats
- Chunk-based processing for memory efficiency

**Streaming Threshold**:
- Files >50MB automatically use streaming mode
- Configurable threshold via `STREAMING_THRESHOLD_MB`

## OCR Capabilities

### Tesseract Integration

**Configuration**:
- Path: `C:\Users\deepakgupta13\AppData\Local\Programs\Tesseract-OCR\tesseract.exe`
- Environment: `TESSERACT_CMD` variable
- PATH inclusion for subprocess calls

**OCR Triggers**:
- Scanned PDF documents
- Image-based content
- Low text-to-image ratio detection
- Fallback when primary processors fail

**Validation Process**:
- Subprocess availability check
- Version verification
- Error handling and fallback strategies

**Tesseract Validation Script**:
- `validate_tesseract.py`: Standalone validation utility
- Tests Tesseract installation and PATH configuration
- Provides detailed error messages and setup instructions
- Can be run independently for troubleshooting OCR issues

### OCR Processing Flow

```
Document Detection → OCR Capability Check → Tesseract Execution → Text Extraction
       ↓              ↓              ↓              ↓
   Image Analysis → Path Validation → OCR Processing → Content Integration
```

## Integration Points

### Storage Service Integration

**Endpoints**:
- `GET /api/storage/projects/{project_id}/download/uploads_raw/{filename}`
- `POST /api/storage/projects/{project_id}/upload/structured`
- `GET /api/storage/projects/{project_id}/download/structured/{filename}`

**Responsibilities**:
- Raw document storage
- Processed content persistence
- Metadata management
- File retrieval for reprocessing

### Vector Service Integration

**Endpoints**:
- `POST /api/vectors/projects/{project_id}/process-structured`
- `POST /api/vectors/projects/{project_id}/collections/{kind}/documents/sync`

**Features**:
- Structured document embedding
- Kind-aware vector collections
- Batch processing support
- Embedding quality metrics

### Graph Service Integration

**Endpoints**:
- `POST /api/graphs/projects/{project_id}/process-structured`
- `POST /api/graphs/projects/{project_id}/structured/facts`

**Capabilities**:
- Entity extraction and linking
- Relationship discovery
- Knowledge graph construction
- Confidence scoring

### WebSocket Service Integration

**Features**:
- Real-time processing updates
- Progress notifications
- Error broadcasting
- Completion confirmations

### Analytics Service Integration

**Data Collection**:
- Processing metrics
- Performance statistics
- Error rates and patterns
- Usage analytics

### Enhanced Assessment Endpoints

**Document Assessment**:
- `GET /api/documents/{project_id}/documents/{filename}/assessment/formatted`
- Generates comprehensive 500-line assessment using LLM
- Includes executive overview, key topics, technologies, infrastructure, data assets, security, and recommendations
- Retrieves structured facts from graph service for enhanced analysis

**Project Insights**:
- `POST /api/documents/{project_id}/generate-comprehensive-insights`
- Aggregates assessments from all project documents
- Generates 1500-line comprehensive project-level analysis
- Includes executive summary, technology landscape, infrastructure analysis, and migration insights
- Handles large content with truncation and extended timeouts

**Assessment Features**:
- LLM-powered structured analysis with predefined prompts
- Content truncation for performance (15k chars for documents, 30k for assessments)
- Caching for facts retrieval (24-hour TTL)
- Error handling with fallback formatting

## Performance Considerations

### Optimization Strategies

**Parallel Processing**:
- Concurrent service integrations
- Thread pool for CPU-bound operations
- Async I/O for network operations
- Batch processing capabilities

**Caching Mechanisms**:
- Redis-based status tracking
- LLM analysis result caching
- Section enrichment caching
- Service discovery caching

**Resource Management**:
- Configurable timeouts and limits
- Memory-efficient streaming
- Temporary file cleanup
- Connection pooling

### Performance Metrics

**Processing Times**:
- Average document processing: <30 seconds
- Large document processing: <90 seconds
- Batch processing: Variable based on document count

**Throughput**:
- Concurrent processing limit: 2 parallel integrations
- Queue-based processing for high volume
- Resource utilization monitoring

### Scalability Features

**Horizontal Scaling**:
- Stateless service design
- External state management (Redis, PostgreSQL)
- Service discovery for dynamic scaling

**Load Balancing**:
- Round-robin distribution
- Health check integration
- Circuit breaker patterns

## Architectural Design Patterns

### Microservice Architecture

**Service Boundaries**:
- Single responsibility: Document processing only
- API-first design with OpenAPI specification
- Event-driven communication via WebSocket

**Cross-Service Communication**:
- HTTP-based service calls
- Correlation ID propagation
- Error handling and retry logic
- Timeout management

### Processing Pipeline Pattern

**Stage Isolation**:
- Independent processing stages
- Fallback strategies for each stage
- Error recovery and continuation
- Progress tracking and reporting

**Data Transformation**:
- Structured data formats (JSONL)
- Metadata enrichment
- Quality scoring and validation
- Backward compatibility

### Observer Pattern for Notifications

**Event Broadcasting**:
- WebSocket-based real-time updates
- Event deduplication
- Subscriber management
- Error notification handling

### Strategy Pattern for Processing

**Multiple Conversion Strategies**:
- Primary and fallback processors
- Format-specific optimizations
- Quality-based selection
- Performance trade-offs

## Error Handling and Resilience

### Error Categories

**Validation Errors**:
- File format not supported
- File size exceeded
- Corrupted file detection

**Processing Errors**:
- OCR dependency missing
- Conversion strategy failures
- Timeout conditions

**Integration Errors**:
- Service unavailability
- Network timeouts
- Authentication failures

### Recovery Mechanisms

**Retry Logic**:
- Progressive timeout increases
- Exponential backoff
- Maximum retry limits
- Circuit breaker patterns

**Fallback Strategies**:
- Multiple conversion approaches
- Graceful degradation
- Partial result handling
- Error document generation

## Monitoring and Observability

### Health Checks

**Liveness Probe**: `/livez`
- Service uptime and basic status
- Memory and thread information

**Readiness Probe**: `/healthz`
- Dependency health verification
- Database and service connectivity

### Logging and Tracing

**Structured Logging**:
- JSON format for Loki integration
- Correlation ID tracking
- Project and service context
- Performance metrics

**Metrics Collection**:
- Processing duration tracking
- Success/failure rates
- Resource utilization
- Integration performance

### Debugging Support

**Debug Output**:
- Conversion strategy logging
- Temporary file preservation
- Processing artifact storage
- Configuration validation

## Configuration Management

### Environment Variables

**Core Configuration**:
- `DOCUMENT_HTTP_TIMEOUT_SEC`: HTTP timeout (default: 30s)
- `CONVERSION_TIMEOUT_SEC`: Processing timeout (default: 90s)
- `PDF_MAX_PAGES`: Maximum PDF pages (default: 50)
- `MAX_CHUNKS`: Maximum processing chunks (default: unlimited)

**Service URLs**:
- `STORAGE_SERVICE_URL`: Storage service endpoint
- `VECTOR_SERVICE_URL`: Vector service endpoint
- `GRAPH_SERVICE_URL`: Graph service endpoint
- `WEBSOCKET_SERVICE_URL`: WebSocket service endpoint

**Feature Flags**:
- `ENABLE_VECTOR_INTEGRATION`: Vector service integration
- `ENABLE_GRAPH_INTEGRATION`: Graph service integration
- `ENABLE_LLM_ANALYSIS`: LLM content analysis
- `ENABLE_PARALLEL_PROCESSING`: Parallel execution

## Security Considerations

### Input Validation

**File Upload Security**:
- Content type verification
- File signature validation
- Size limit enforcement
- Path traversal prevention

### Service Authentication

**Token-Based Auth**:
- Service authentication tokens
- Request header validation
- Cross-service trust establishment

### Data Protection

**Sensitive Data Handling**:
- Temporary file cleanup
- Secure file storage
- Access control enforcement
- Audit logging

## Future Enhancements

### Planned Features

**Advanced OCR**:
- Multi-language OCR support
- Handwriting recognition
- Form field extraction

**Enhanced Processing**:
- Multi-modal content analysis
- Document comparison capabilities
- Automated summarization

**Performance Improvements**:
- GPU acceleration for processing
- Distributed processing clusters
- Advanced caching strategies

**Integration Expansion**:
- Additional vector databases
- Graph database alternatives
- External LLM providers

**PVC Tiered Processing**:
- Planned T1/T2/T3 endpoint tiers for different processing priorities
- PVC-enabled processing with governance controls
- Tiered resource allocation and quality-of-service levels

This document processing service represents a sophisticated, production-ready solution for document analysis and knowledge extraction within the Migration Platform ecosystem.