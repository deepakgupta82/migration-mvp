# Vector Service

## Service Overview

The Vector Service is a high-performance vector search and embedding service that operates on port 8005. It provides semantic similarity search, embedding generation, and vector database operations using Weaviate as the underlying vector store. The service handles document chunking, embedding generation using Sentence Transformers, and supports both semantic and hybrid search capabilities.

### Key Features

- **Vector Embeddings**: Generation of high-dimensional embeddings using Sentence Transformers
- **Semantic Search**: Cosine similarity-based document retrieval
- **Hybrid Search**: Combination of semantic and keyword-based search
```
{
  "texts": ["..."],
  "model": "optional",
  "force_refresh": false,
  "project_id": "optional",
  "document_id": "optional",
  "canonical_ids": ["optional"]
}
```
- **Background Processing**: Asynchronous document processing and model loading

```
{
  "success": true,
  "embeddings": [[...]],
  "model": "default",
  "batch_size": 3,
  "cached": 2,
  "generated": 1,
  "cache_enabled": true,
  "metrics": {
    "requests": 10,
    "batches": 10,
    "cache_hits": 20,
    "cache_misses": 5,
    "last_request_ms": 12.5,
    "p50_ms": 11.8,
    "p95_ms": 22.1,
    "error_count": 0
  }
}
```
   - Similarity search with configurable limits
   - Collection management per project
   - Vector deletion and cleanup operations

3. **Search and Retrieval**
   - Semantic similarity search
   - Hybrid search combining semantic and BM25 keyword search
   - Kind-filtered search (raw_chunks, entity_cards, triple_cards)
   - Fusion search with Reciprocal Rank Fusion (RRF)

4. **Advanced Features**
   - Entity resolution clustering
   - Card generation from raw chunks
   - Citation preview with attribution scoring
   - Structured document processing with smart chunking

### Dependencies

- **Weaviate**: Vector database for storing embeddings and metadata
- **Redis**: Caching layer for search results and model status
- **Sentence Transformers**: ML library for embedding generation
- **Stats Service**: Event notifications for embedding updates
- **Document Service**: Source of document processing events

## APIs/Endpoints

### Core Vector Operations

#### Collection Management
- `POST /api/vectors/projects/{project_id}/collection` - Create/prepare project collection
- `GET /api/vectors/projects/{project_id}/collection` - Get collection information
- `DELETE /api/vectors/projects/{project_id}/collection` - Delete project vectors

#### Document Operations
- `POST /api/vectors/projects/{project_id}/documents` - Add documents (background processing)
- `POST /api/vectors/projects/{project_id}/documents/sync` - Add documents (synchronous)
- `DELETE /api/vectors/projects/{project_id}/documents/{filename}` - Delete document vectors

#### Search Operations
- `POST /api/vectors/projects/{project_id}/search` - Semantic similarity search
- `POST /api/vectors/projects/{project_id}/search/hybrid` - Hybrid semantic + keyword search

#### Kind-specific Operations
- `POST /api/vectors/projects/{project_id}/collections/{kind}/documents/sync` - Add documents to specific kind
- `POST /api/vectors/projects/{project_id}/collections/{kind}/search` - Search within specific kind
- `POST /api/vectors/projects/{project_id}/collections/{kind}/search/hybrid` - Hybrid search within kind

### Advanced Features

#### Bulk Embeddings
- `POST /api/vectors/bulk-embeddings` - Batch embedding generation with LRU+TTL caching

#### Entity Resolution
- `POST /api/vectors/entity-resolution` - Entity card clustering (scaffold)

#### Card Generation
- `POST /api/vectors/projects/{project_id}/generate-cards` - Generate entity and triple cards

#### Fusion Search
- `POST /api/vectors/projects/{project_id}/fusion/search` - Multi-kind fusion search with RRF

#### Citation Preview
- `GET /api/vectors/projects/{project_id}/citations/preview` - Preview citations with attribution scores

### Utility Endpoints

#### Health and Status
- `GET /api/vectors/health` - Service health check
- `POST /api/vectors/warm-up` - Warm up embedding models
- `GET /api/vectors/model-status` - Get model loading status

#### Statistics and Metrics
- `GET /api/vectors/projects/{project_id}/metrics` - Vector metrics by kind
- `GET /api/vectors/projects/{project_id}/stats` - Collection statistics
- `GET /api/vectors/projects/{project_id}/status` - Collection status
- `GET /api/vectors/projects/{project_id}/search/cache` - Search cache statistics

#### Debug Endpoints
- `GET /api/vectors/debug/collections` - List Weaviate collections
- `GET /api/vectors/debug/model-info` - Embedding model information

### Structured Document Processing
- `POST /api/vectors/projects/{project_id}/process-structured` - Process structured document elements

## Data Models

### Document Input Structure
```json
{
  "id": "optional-document-id",
  "content": "Document text content to be embedded",
  "filename": "document.pdf",
  "source": "document-service",
  "chunk_index": 0,
  "metadata": {
    "author": "John Doe",
    "created_date": "2024-01-01",
    "page_number": 1
  }
}
```

### Search Request Structure
```json
{
  "query": "What is cloud migration?",
  "limit": 10,
  "include_metadata": true
}
```

### Search Response Structure
```json
{
  "query": "What is cloud migration?",
  "results": [
    {
      "content": "Cloud migration involves moving applications and data...",
      "distance": 0.123,
      "similarity_score": 0.877,
      "metadata": {
        "filename": "migration-guide.pdf",
        "chunk_index": 5,
        "source": "raw_chunks"
      }
    }
  ],
  "total_found": 1,
  "collection_name": "DocumentChunk",
  "search_timestamp": "2024-01-01T12:00:00.000000"
}
```

### Bulk Embeddings Request/Response
```json
{
  "project_id": "project_123",
  "texts": ["First text to embed", "Second text to embed"],
  "model": "default",
  "force_refresh": false
}
```

### Fusion Search Response
```json
{
  "project_id": "project_123",
  "query": "cloud migration strategies",
  "results": [
    {
      "doc_id": "migration-guide.pdf:5:hash123",
      "content_preview": "Cloud migration involves...",
      "kinds": ["raw_chunks", "entity_cards"],
      "rrf_score": 0.456,
      "primary_kind": "raw_chunks",
      "source": "document-service",
      "metadata": {
        "filename": "migration-guide.pdf",
        "chunk_index": 5
      }
    }
  ],
  "retrieval_stats": {
    "candidate_counts": {"raw_chunks": 25, "entity_cards": 15},
    "fused_candidates": 20,
    "returned": 10,
    "rrf_k": 60,
    "dedupe_ratio": 0.25,
    "hybrid_enabled": true
  },
  "timestamp": "2024-01-01T12:00:00.000000",
  "status": "success"
}
```

## Key Components

### VectorProcessor (`app/core/vector_processor.py`)

**Core vector processing engine**

- **Responsibilities**:
  - Weaviate client management and schema initialization
  - Embedding model loading and management (lazy/async)
  - Document addition with batch processing
  - Similarity and hybrid search operations
  - Collection management and cleanup
  - Health checks and connection management

- **Key Methods**:
  - `add_documents()`: Batch document embedding and storage
  - `similarity_search()`: Semantic search with caching
  - `hybrid_search()`: Combined semantic + keyword search
  - `health_check()`: Weaviate and Redis connectivity checks
  - `ensure_schema()`: Weaviate collection schema management

### Vectors Router (`app/routers/vectors.py`)

**FastAPI router for vector operations**

- **Responsibilities**:
  - HTTP endpoint definitions and request/response handling
  - Input validation and error handling
  - Background task management for document processing
  - Cache management for bulk embeddings
  - WebSocket integration for real-time updates

- **Key Features**:
  - LRU+TTL caching for bulk embeddings
  - Kind-filtered search operations
  - Fusion search with Reciprocal Rank Fusion
  - Entity resolution clustering
  - Structured document processing

### Correlation Context (`app/core/correlation.py`)

**Request correlation and logging support**

- **Responsibilities**:
  - Correlation ID management across requests
  - Structured logging with correlation tracking
  - Request tracing and debugging support

## Data Flow

### Document Processing Flow

1. **Document Ingestion**: Documents received via API with metadata
2. **Validation**: Content validation and error document filtering
3. **Chunking**: Text chunking for optimal embedding size
4. **Embedding Generation**: Batch embedding using Sentence Transformers
5. **Storage**: Vectors and metadata stored in Weaviate
6. **Notification**: Stats service notified of embedding updates
7. **Response**: Processing results returned to client

### Search Flow

1. **Query Reception**: Search query received with parameters
2. **Cache Check**: Redis cache checked for previous results
3. **Embedding Generation**: Query text converted to embedding vector
4. **Vector Search**: Similarity search performed in Weaviate
5. **Result Processing**: Results formatted with metadata
6. **Caching**: Results cached in Redis for future requests
7. **Response**: Formatted search results returned

### Fusion Search Flow

1. **Multi-kind Retrieval**: Parallel search across different kinds
2. **Candidate Collection**: Top candidates gathered from each kind
3. **Deduplication**: Results deduplicated by content hash
4. **RRF Scoring**: Reciprocal Rank Fusion applied
5. **Hybrid Enhancement**: Optional lexical and centrality scoring
6. **Ranking**: Final results ranked by combined score
7. **Response**: Unified results with attribution metadata

## Complete Working Details

### Configuration

**Environment Variables**:
- `WEAVIATE_URL`: Weaviate server URL (default: `http://localhost:8080`)
- `EMBEDDING_MODEL`: Sentence Transformer model name (default: `all-MiniLM-L6-v2`)
- `VECTOR_EMBED_BATCH_SIZE`: Batch size for embedding generation (default: `32`)
- `VECTOR_ADD_BATCH_SIZE`: Batch size for document addition (default: `128`)
- `VECTOR_HEALTH_CACHE_TTL_SEC`: Health check cache TTL (default: `60`)
- `EMBED_CACHE_MAX_ENTRIES`: Maximum cached embeddings (default: `2048`)
- `EMBED_CACHE_TTL_SECONDS`: Embedding cache TTL (default: `3600`)

### Weaviate Schema

**DocumentChunk Collection**:
```python
properties = [
    Property(name="content", data_type=DataType.TEXT),
    Property(name="project_id", data_type=DataType.TEXT),
    Property(name="filename", data_type=DataType.TEXT),
    Property(name="chunk_index", data_type=DataType.INT),
    Property(name="source", data_type=DataType.TEXT),
    Property(name="timestamp", data_type=DataType.TEXT),
    Property(name="metadata_json", data_type=DataType.TEXT),
]
```

### Supported Kinds

- **raw_chunks**: Original document chunks
- **entity_cards**: Generated entity knowledge cards
- **triple_cards**: Generated relationship knowledge cards

### Embedding Models

**Supported Models**:
- `all-MiniLM-L6-v2`: Fast, general-purpose model (384 dimensions)
- `jina-embeddings-v2-base-en`: High-quality model (768 dimensions)

### Caching Strategy

**Redis Caching**:
- Search results cached for 10 minutes
- Bulk embeddings cached with LRU eviction
- Health status cached for 60 seconds
- Collection statistics cached for 5 minutes

### Performance Characteristics

- **Embedding Generation**: Batch processing with configurable sizes
- **Search Latency**: Sub-second for cached queries, 2-5 seconds for new queries
- **Concurrent Requests**: Async processing supports high concurrency
- **Memory Usage**: Lazy model loading, configurable cache sizes
- **Storage Efficiency**: Vector compression and metadata optimization

### Error Handling

- **Model Loading Failures**: Graceful fallback with error logging
- **Weaviate Connection Issues**: Health checks and retry logic
- **Invalid Documents**: Content validation and error filtering
- **Batch Processing Errors**: Individual failure handling without stopping batch
- **Cache Misses**: Automatic background synchronization

### Monitoring and Observability

- **Health Checks**: Weaviate and Redis connectivity monitoring
- **Metrics**: Embedding generation stats, search performance, cache hit rates
- **Logging**: Structured logging with correlation IDs
- **Debug Endpoints**: Model information and collection statistics
- **Performance Tracking**: Batch processing times and throughput

### Security Considerations

- **Input Validation**: All text inputs validated and sanitized
- **Rate Limiting**: Built-in protection against abuse
- **Access Control**: Project-scoped operations
- **Audit Logging**: All operations logged for compliance
- **Data Privacy**: Metadata handling with privacy considerations

### Scaling Considerations

- **Horizontal Scaling**: Stateless design supports multiple instances
- **Model Optimization**: Configurable batch sizes and caching
- **Database Sharding**: Weaviate clustering support
- **Cache Distribution**: Redis cluster compatibility
- **Load Balancing**: Support for request distribution across instances