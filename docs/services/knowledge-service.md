# Knowledge Service

## Service Overview

The Knowledge Service is an advanced RAG (Retrieval-Augmented Generation) and knowledge management service that operates on port 8017. It provides intelligent document indexing, semantic search, knowledge graph construction, and context-aware question answering for the Nagarro Ascent platform.

### Key Features

- **Advanced RAG**: Retrieval-augmented generation for accurate responses
- **Semantic Search**: Vector-based document similarity search
- **Knowledge Graph**: Automated knowledge graph construction
- **Question Answering**: Context-aware Q&A with source attribution
- **Document Indexing**: Intelligent document processing and indexing
- **Multi-modal Search**: Hybrid keyword and semantic search
- **Knowledge Curation**: Knowledge base management and maintenance

## Functionality

### Core Capabilities

1. **Document Processing & Indexing**
   - Intelligent document chunking and embedding
   - Metadata extraction and enrichment
   - Relationship discovery and linking
   - Quality assessment and validation

2. **Advanced Search & Retrieval**
   - Semantic similarity search
   - Hybrid keyword + vector search
   - Knowledge graph traversal
   - Multi-source result fusion

3. **Question Answering**
   - Context-aware answer generation
   - Source attribution and verification
   - Confidence scoring and explanation
   - Follow-up question handling

4. **Knowledge Management**
   - Knowledge graph construction and querying
   - Entity relationship mapping
   - Knowledge base curation and maintenance
   - Version control and evolution tracking

### Dependencies

- **Vector Service**: Embedding generation and similarity search
- **LLM Service**: Answer generation and reasoning
- **Storage Service**: Document storage and retrieval
- **WebSocket Service**: Real-time knowledge updates

## APIs/Endpoints

### Document Management
- `POST /documents` - Add knowledge document
- `GET /documents` - List knowledge documents
- `GET /documents/{doc_id}` - Get specific document
- `DELETE /documents/{doc_id}` - Remove document

### Search Operations
- `POST /search` - Perform knowledge search
- `POST /qa` - Ask question (general knowledge)
- `POST /qa/projects/{project_id}` - Ask project-specific question

### Knowledge Graph
- `POST /knowledge-graphs` - Create knowledge graph
- `GET /knowledge-graphs/{graph_id}` - Get knowledge graph
- `POST /knowledge-graphs/{graph_id}/query` - Query knowledge graph

### Analytics
- `GET /stats` - Get knowledge base statistics
- `GET /analytics/search` - Search analytics and metrics

## Data Models

### Knowledge Document Structure
```json
{
  "doc_id": "doc_123",
  "title": "Cloud Migration Best Practices",
  "content": "Cloud migration requires careful planning...",
  "doc_type": "best_practices",
  "metadata": {
    "author": "Cloud Architecture Team",
    "version": "1.0",
    "category": "migration"
  },
  "tags": ["cloud", "migration", "best-practices"],
  "relationships": ["doc_456", "doc_789"],
  "created_at": "2024-01-01T00:00:00.000000",
  "updated_at": "2024-01-01T00:00:00.000000",
  "status": "indexed"
}
```

### Search Result Structure
```json
{
  "doc_id": "doc_123",
  "title": "Cloud Migration Best Practices",
  "content_snippet": "Cloud migration requires careful planning and execution...",
  "relevance_score": 0.95,
  "doc_type": "best_practices",
  "metadata": {
    "author": "Cloud Architecture Team",
    "category": "migration"
  },
  "tags": ["cloud", "migration"]
}
```

### Question Answer Structure
```json
{
  "qa_id": "qa_456",
  "question": "What are the key considerations for cloud migration?",
  "answer": "Key considerations include: assessment of current infrastructure, selection of appropriate cloud services, migration strategy, security requirements, performance optimization, and cost management...",
  "context_docs": ["doc_123", "doc_456"],
  "confidence": 0.92,
  "metadata": {
    "search_results_count": 5,
    "processing_time": 1.2
  },
  "created_at": "2024-01-01T12:00:00.000000"
}
```

### Knowledge Graph Structure
```json
{
  "graph_id": "graph_789",
  "name": "Migration Knowledge Graph",
  "description": "Comprehensive migration knowledge network",
  "nodes": [
    {
      "id": "node_1",
      "label": "Cloud Migration",
      "type": "concept",
      "properties": {"importance": 0.9}
    }
  ],
  "edges": [
    {
      "from": "node_1",
      "to": "node_2",
      "type": "related_to",
      "weight": 0.8
    }
  ],
  "created_at": "2024-01-01T00:00:00.000000",
  "updated_at": "2024-01-01T00:00:00.000000"
}
```

## Key Components

### KnowledgeManager (`main.py`)

**Core knowledge orchestration engine**

- **Responsibilities**:
  - Document processing and indexing coordination
  - Search query routing and result fusion
  - Question answering pipeline management
  - Knowledge graph construction and querying

### Document Processor

**Intelligent document processing**

- **Responsibilities**:
  - Document chunking and preprocessing
  - Metadata extraction and enrichment
  - Relationship discovery and linking
  - Quality validation and indexing

### Search Engine

**Multi-modal search and retrieval**

- **Responsibilities**:
  - Semantic search execution
  - Hybrid search result fusion
  - Relevance ranking and scoring
  - Result caching and optimization

## Data Flow

### Document Indexing Flow

1. **Document Submission**: Document added to knowledge base
2. **Preprocessing**: Text extraction and cleaning
3. **Chunking**: Intelligent document segmentation
4. **Embedding Generation**: Vector embeddings created
5. **Relationship Discovery**: Related documents identified
6. **Indexing**: Document stored and indexed
7. **Notification**: Indexing completion notified

### Question Answering Flow

1. **Question Reception**: User question submitted
2. **Query Analysis**: Question intent and context analyzed
3. **Document Retrieval**: Relevant documents retrieved via search
4. **Context Assembly**: Relevant information assembled
5. **Answer Generation**: LLM generates answer with sources
6. **Confidence Scoring**: Answer quality and confidence assessed
7. **Response Delivery**: Answer with source attribution returned

### Knowledge Graph Construction Flow

1. **Document Selection**: Documents selected for graph construction
2. **Entity Extraction**: Named entities and concepts identified
3. **Relationship Mining**: Relationships between entities discovered
4. **Graph Construction**: Knowledge graph assembled
5. **Validation**: Graph consistency and quality validated
6. **Storage**: Graph stored for querying

## Complete Working Details

### Configuration

**Environment Variables**:
- `KNOWLEDGE_CHUNK_SIZE`: Document chunk size for processing
- `KNOWLEDGE_SIMILARITY_THRESHOLD`: Search similarity threshold
- `KNOWLEDGE_MAX_CONTEXT_DOCS`: Maximum context documents for Q&A
- `KNOWLEDGE_CACHE_TTL`: Search result cache TTL

### Document Types

- **Technical Documentation**: API docs, architecture guides
- **Migration Guides**: Step-by-step migration instructions
- **Architecture Documents**: System design and patterns
- **API Documentation**: Service and endpoint documentation
- **Troubleshooting**: Problem resolution guides
- **Best Practices**: Recommended approaches and patterns
- **Case Studies**: Real-world implementation examples
- **Research Papers**: Technical research and analysis

### Performance Characteristics

- **Indexing Speed**: 100-500 documents per minute
- **Search Latency**: 100-500ms for typical queries
- **Q&A Response Time**: 2-10 seconds with LLM generation
- **Concurrent Users**: High concurrency with caching

### Error Handling

- **Document Processing Failures**: Individual document error isolation
- **Search Failures**: Fallback to alternative search methods
- **LLM Generation Errors**: Graceful degradation with cached responses
- **Graph Construction Errors**: Partial graph construction continuation

### Monitoring and Observability

- **Indexing Metrics**: Document processing rates and success rates
- **Search Analytics**: Query patterns and performance metrics
- **Q&A Quality**: Answer accuracy and user satisfaction
- **Knowledge Growth**: Knowledge base size and evolution tracking

### Security Considerations

- **Access Control**: Project-scoped knowledge access
- **Content Filtering**: Sensitive information detection and handling
- **Audit Logging**: All knowledge operations logged
- **Data Privacy**: User data protection in Q&A responses

### Scaling Considerations

- **Document Sharding**: Knowledge base partitioning across instances
- **Search Distribution**: Parallel search execution
- **Caching**: Multi-level caching for performance
- **Graph Partitioning**: Large knowledge graph distribution