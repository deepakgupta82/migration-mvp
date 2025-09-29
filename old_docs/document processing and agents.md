# Document Processing and AI Agents Documentation

## Overview

This document provides a comprehensive overview of how the document service processes documents in the Nagarro Ascent Platform, including all services involved, UI components, backend files, processing flow, functions used, database updates, and how AI agents utilize this information for answering queries and creating documents.

## Document Service Architecture

### Core Components

The document service (Port 8003) is the central component responsible for document processing. It consists of several key modules:

- **DocumentProcessor**: Main processing engine
- **StructuredDocumentProcessor**: Enhanced JSONL processing
- **EnhancedDocumentProcessor**: Advanced workflow processing
- **ContentExtractor**: Content extraction utilities
- **LLMContentAnalyzer**: LLM-enhanced analysis
- **ProgressTracker**: Real-time progress tracking
- **ServiceClient**: Inter-service communication

### Key Files and Directories

```
services/document-service/
├── app/
│   ├── routers/
│   │   └── documents.py          # Main API endpoints
│   ├── core/
│   │   ├── document_processor.py # Core processing logic
│   │   ├── structured_processor.py # JSONL processing
│   │   ├── enhanced_processor.py # Enhanced workflow
│   │   ├── content_extractor.py  # Content extraction
│   │   ├── llm_content_analyzer.py # LLM analysis
│   │   ├── progress_tracker.py   # Progress tracking
│   │   ├── semantic_chunking.py  # Text chunking
│   │   └── enrichment.py         # Content enrichment
│   └── models/                   # Data models
```

## Services Involved in Document Processing

### 1. Backend Service (Port 8000)
- **Purpose**: Main API gateway and business logic orchestration
- **Key Endpoints**:
  - `POST /api/projects/{project_id}/upload` - Document upload proxy
  - `GET /api/projects/{project_id}/uploaded-files` - Document listing proxy
  - `POST /api/projects/{project_id}/process-all` - Document processing proxy
  - `POST /api/projects/{project_id}/process-selected` - Selective processing proxy
  - `GET /health` - Platform health check
- **Role in Document Processing**: Routes requests to appropriate services, provides unified API interface

### 2. Project Service (Port 8002)
- **Purpose**: Project management and metadata
- **Key Endpoints**:
  - `POST /projects` - Create new project
  - `GET /projects/{project_id}` - Get project details
  - `GET /projects/{project_id}/files` - Get project files
  - `POST /projects/{project_id}/generation-requests` - Create document generation requests
- **Role in Document Processing**: Manages project context, file associations, and generation history

### 3. Reporting Service (Port 8001)
- **Purpose**: Report generation and document creation
- **Key Endpoints**:
  - Report generation endpoints (specific endpoints not detailed in current docs)
- **Role in Document Processing**: Generates final reports and documents from processed content

### 4. Document Service (Port 8003)
- **Purpose**: Core document processing and conversion
- **Key Endpoints**:
  - `POST /{project_id}/upload` - Upload documents
  - `POST /{project_id}/process-selected` - Process selected documents
  - `GET /{project_id}/status/{job_id}` - Get processing status
  - `POST /{project_id}/structured-process/{filename}` - Structured processing
- **Role in Document Processing**: Primary document conversion using Unstructured.io and MarkItDown

### 5. Stats Service (Port 8004)
- **Purpose**: Event tracking and analytics
- **Key Endpoints**:
  - `POST /api/stats/projects/{project_id}/events/document-processed` - Track processing
  - `POST /api/stats/projects/{project_id}/events/document-uploaded` - Track uploads
  - `POST /api/stats/projects/{project_id}/events/embeddings-updated` - Track embeddings
  - `POST /api/stats/projects/{project_id}/events/graph-updated` - Track graph updates
- **Role in Document Processing**: Tracks all processing events for analytics and monitoring

### 6. Vector Service (Port 8005)
- **Purpose**: Vector embeddings and semantic search
- **Key Endpoints**:
  - `POST /projects/{project_id}/collection` - Create vector collection
  - `POST /projects/{project_id}/documents/sync` - Sync documents to vectors
  - `POST /projects/{project_id}/search` - Semantic search
- **Database**: Weaviate vector database
- **Role in Document Processing**: Creates and manages vector embeddings for semantic search

### 7. Graph Service (Port 8006)
- **Purpose**: Knowledge graph construction and entity relationships
- **Key Endpoints**:
  - `POST /projects/{project_id}/extract` - Entity extraction
  - `POST /projects/{project_id}/process-structured` - Structured processing
  - `GET /projects/{project_id}/graph` - Get project graph
- **Database**: Neo4j graph database
- **Role in Document Processing**: Extracts entities and builds knowledge graphs

### 8. LLM Service (Port 8007)
- **Purpose**: Large language model operations
- **Key Endpoints**:
  - `POST /api/llm/process` - Process LLM requests
  - `POST /api/llm/cluster` - Semantic clustering
  - `GET /api/llm/providers` - List LLM providers
- **Role in Document Processing**: Provides LLM capabilities for entity extraction, assessment, and content analysis

### 9. AI Agent Service (Port 8008)
- **Purpose**: AI agent orchestration (Crew AI, Autogen)
- **Key Endpoints**:
  - `POST /crews` - Create crew
  - `POST /crews/{crew_id}/execute` - Execute crew
  - `POST /autogen/sessions` - Create autogen session
- **Role in Document Processing**: Uses processed documents for query answering and document generation

### 10. WebSocket Service (Port 8009)
- **Purpose**: Real-time progress updates and notifications
- **Key Endpoints**:
  - `WS /ws/processing/{project_id}` - Processing updates
  - `WS /ws/document-processing/{project_id}` - Document processing
  - `POST /api/websocket/broadcast` - Broadcast messages
- **Role in Document Processing**: Provides real-time progress updates to UI

### 11. Storage Service (Port 8010)
- **Purpose**: File storage and retrieval
- **Key Endpoints**:
  - `POST /projects/{project_id}/upload/{category}` - Upload files
  - `GET /projects/{project_id}/download/{category}/{filename}` - Download files
  - `GET /projects/{project_id}/files/{category}` - List files
- **Categories Used**:
  - `uploads_raw`: Raw uploaded files
  - `uploads_parsed`: Processed markdown files
  - `metadata`: Processing metadata
  - `structured`: JSONL structured data
- **Role in Document Processing**: Stores all document artifacts and processed content

### 12. Service Registry (Port 8011)
- **Purpose**: Service discovery and registration
- **Key Endpoints**:
  - `GET /services` - List all registered services
  - `GET /services/{service_name}` - Get service details
  - `GET /health` - Registry health
- **Role in Document Processing**: Enables dynamic service discovery for inter-service communication

### 13. Cloud Tools Service (Port 8012)
- **Purpose**: Cloud integrations and tools
- **Key Endpoints**:
  - `GET /providers` - List cloud providers
  - `POST /providers/{provider}/connect` - Connect to provider
  - `GET /providers/{provider}/resources` - List resources
- **Role in Document Processing**: Provides cloud-based processing capabilities and integrations

### 14. Analytics Service (Port 8014)
- **Purpose**: Advanced analysis and insights
- **Key Endpoints**:
  - `POST /analytics/migration-complexity` - Generate migration complexity analysis
  - `POST /analytics/cost-optimization` - Generate cost optimization analysis
  - `POST /api/analysis` - Create analysis results
  - `POST /api/analysis/batch` - Batch analysis
- **Role in Document Processing**: Performs advanced analytics on processed document data

### 15. Security Service (Port 8015)
- **Purpose**: Authentication and authorization
- **Key Endpoints**:
  - `POST /auth/login` - User login
  - `POST /auth/logout` - User logout
  - `GET /auth/me` - Get current user
  - `GET /permissions` - Get user permissions
- **Role in Document Processing**: Secures document access and processing operations

### 16. Collaboration Service (Port 8016)
- **Purpose**: Team collaboration features
- **Key Endpoints**:
  - `GET /teams` - List teams
  - `POST /teams` - Create team
  - `POST /comments` - Add comment
  - `GET /comments/{resource_id}` - Get comments
- **Role in Document Processing**: Enables collaborative document processing and review

### 17. Knowledge Service (Port 8017)
- **Purpose**: Knowledge base management
- **Key Endpoints**:
  - `GET /knowledge` - Search knowledge base
  - `POST /knowledge` - Add knowledge
  - `GET /categories` - List categories
- **Role in Document Processing**: Manages and provides access to processed knowledge content

## UI Components and Files

### Frontend Components

```
frontend/src/
├── components/
│   ├── FileUpload.tsx                    # File upload interface
│   ├── ProcessingProgressView.tsx        # Processing progress display
│   ├── project-detail/
│   │   └── InteractiveGraphVisualizer.tsx # Graph visualization
│   └── DocumentViewer.tsx                # Document viewing
├── pages/
│   ├── settings/
│   │   └── KnowledgeBasePage.tsx         # Knowledge base management
│   └── project/
│       └── ProjectDetailPage.tsx         # Project details
└── types/
    └── messages.ts                       # WebSocket message types
```

### Key UI Components

1. **FileUpload Component**
   - Drag-and-drop file upload
   - File validation and size limits
   - Progress tracking during upload

2. **ProcessingProgressView Component**
   - Real-time processing status
   - WebSocket integration for live updates
   - Error handling and retry mechanisms

3. **InteractiveGraphVisualizer Component**
   - Graph visualization using vis-network
   - Node and relationship exploration
   - Search and filtering capabilities

## Backend Files and APIs

### Document Service APIs

#### Upload and Processing
- `POST /{project_id}/upload` - Upload documents
- `POST /{project_id}/process-selected` - Process selected documents
- `GET /{project_id}/status/{job_id}` - Get processing status

#### Structured Processing
- `POST /{project_id}/structured-process/{filename}` - Process single document
- `POST /{project_id}/structured-process-all` - Process all documents
- `GET /{project_id}/structured-status/{job_id}` - Get structured processing status

#### Analysis and Insights
- `POST /{project_id}/analyze/{filename}` - Analyze document
- `GET /{project_id}/insights` - Get project insights
- `POST /{project_id}/llm/{filename}` - LLM-enhanced analysis

#### Content Management
- `GET /{project_id}/content/{filename}` - Get document content
- `POST /{project_id}/chunks/{filename}` - Generate chunks
- `POST /{project_id}/extract-batch` - Extract content batch

### Vector Service APIs
- `POST /projects/{project_id}/collection` - Create collection
- `POST /projects/{project_id}/documents/sync` - Sync documents
- `POST /projects/{project_id}/search` - Search vectors

### Graph Service APIs
- `POST /projects/{project_id}/extract` - Extract entities
- `POST /projects/{project_id}/process-structured` - Process structured elements
- `GET /projects/{project_id}/graph` - Get graph data

## End-to-End Document Processing Flow

### Phase 1: Upload
1. User uploads files via `FileUpload.tsx`
2. Frontend calls `POST /api/documents/{project_id}/upload`
3. Document service streams files to Storage Service
4. Files stored in `uploads_raw` category
5. WebSocket notification sent to UI

### Phase 2: Processing Initiation
1. User selects files and initiates processing
2. Frontend calls `POST /api/documents/{project_id}/process-selected`
3. Document service validates file existence
4. Background processing job started
5. Progress tracking initialized

### Phase 3: Document Conversion (Enhanced Workflow)
1. **Download**: Files downloaded from Storage Service
2. **JSONL Conversion**: Unstructured.io processes document to JSONL format
3. **Entity Extraction**: LLM extracts entities and relationships
4. **Assessment**: LLM assesses document quality and content
5. **Insights Generation**: Project insights updated

### Phase 4: Content Storage
1. **Markdown Generation**: JSONL converted to markdown
2. **Chunking**: Text chunked using semantic strategies
3. **Metadata Creation**: Processing metadata stored
4. **File Upload**: Processed files uploaded to Storage Service

### Phase 5: Vector Database Update
1. **Collection Creation**: Vector collection ensured to exist
2. **Embedding Generation**: Chunks converted to vector embeddings
3. **Batch Sync**: Embeddings synced to Weaviate in batches
4. **Indexing**: Vectors indexed for semantic search

### Phase 6: Graph Database Update
1. **Entity Extraction**: Entities identified from JSONL content
2. **Relationship Mining**: Relationships extracted between entities
3. **Node Creation**: Entity nodes created in Neo4j
4. **Relationship Creation**: Relationships established between nodes
5. **Document Linking**: Document nodes linked to entities

### Phase 7: Completion and Notification
1. **Status Update**: Processing status marked as completed
2. **WebSocket Broadcast**: Completion notification sent
3. **Stats Update**: Processing metrics recorded
4. **UI Update**: Progress view updated with completion status

## Key Functions and Methods

### Document Processing Functions

#### Core Processing
- `enhanced_processor.process_document_enhanced()` - Main enhanced processing
- `structured_processor.process_document_structured()` - JSONL processing
- `processor.convert_document_to_markdown()` - Traditional processing
- `content_extractor.extract_and_update_project_file()` - Content extraction

#### Chunking and Enrichment
- `chunk_text_semantic()` - Semantic text chunking
- `enrich_text()` - Content enrichment (keywords, summaries)
- `_chunk_markdown_text()` - Markdown-specific chunking

#### Entity and Relationship Extraction
- `graph_processor.extract_entities_from_document()` - Entity extraction
- `graph_processor.add_entities_to_graph()` - Graph population
- `_extract_entities_from_structured_elements()` - Structured element processing

### Vector Database Functions
- `vector_service.sync_documents()` - Document synchronization
- `vector_service.batch_add_documents()` - Batch embedding creation
- `vector_service.search()` - Semantic search execution

### Graph Database Functions
- `graph_processor.upsert_entity()` - Entity creation/update
- `graph_processor.create_relationship()` - Relationship creation
- `graph_processor.get_project_graph()` - Graph retrieval

### WebSocket Functions
- `websocket_gateway.broadcast_to_project()` - Project broadcasting
- `websocket_gateway.send_to_connection()` - Direct messaging
- `progress_tracker.update_processing_status()` - Status updates

## Vector Database Updates

### Collection Management
1. **Collection Creation**: Automatic creation of project-specific collections
2. **Schema Validation**: Collection schema verification
3. **Index Optimization**: Vector index configuration

### Document Synchronization
1. **Chunk Processing**: Documents split into semantic chunks
2. **Embedding Generation**: Each chunk converted to vector representation
3. **Batch Upload**: Vectors uploaded in optimized batches
4. **Metadata Association**: Chunks linked to source documents

### Search Optimization
1. **Index Updates**: Vector indices updated for new content
2. **Similarity Metrics**: Cosine similarity and other metrics configured
3. **Performance Tuning**: Query optimization and caching

## Graph Database Updates

### Entity Extraction Process
1. **Document Analysis**: LLM analyzes document content for entities
2. **Entity Classification**: Entities categorized (Server, Application, Database, etc.)
3. **Property Extraction**: Entity properties extracted (hostname, OS, etc.)
4. **Relationship Identification**: Connections between entities identified

### Graph Construction
1. **Node Creation**: Entity nodes created with properties
2. **Relationship Creation**: Relationships established between nodes
3. **Project Association**: All nodes linked to project
4. **Document Linking**: Document nodes connected to extracted entities

### Graph Enhancement
1. **Insight Generation**: Higher-level insights derived from entities
2. **Pattern Recognition**: Common patterns identified and stored
3. **Knowledge Evolution**: Graph updated with new discoveries

## AI Agent Integration

### Crew AI Agents

#### Architecture
Crew AI agents are orchestrated through the AI Agent Service (Port 8008) and utilize document processing data through:

1. **Knowledge Base Access**: Agents query vector database for semantic search
2. **Graph Traversal**: Agents explore entity relationships in Neo4j
3. **Document Retrieval**: Agents access processed document content
4. **Context Enrichment**: Agents use extracted insights and discoveries

#### Query Answering Process
1. **Query Reception**: User query received via Chatbubble interface
2. **Intent Analysis**: Crew AI analyzes query intent
3. **Knowledge Retrieval**:
   - Vector search for relevant document chunks
   - Graph queries for related entities
   - Discovery lookup for key facts
4. **Context Assembly**: Relevant information assembled from multiple sources
5. **Response Generation**: LLM generates comprehensive answer
6. **Source Attribution**: Response includes source document references

#### Document Creation Process
1. **Task Analysis**: Crew AI breaks down document creation requirements
2. **Research Phase**: Agents research using vector and graph databases
3. **Content Gathering**: Relevant information extracted from documents
4. **Structure Planning**: Document structure planned using insights
5. **Content Generation**: LLM generates document content
6. **Fact Verification**: Generated content verified against knowledge base
7. **Document Assembly**: Final document assembled and stored

### Chatbubble Interface

#### Integration Points
1. **Real-time Communication**: WebSocket integration for live updates
2. **Query Processing**: Direct integration with Crew AI agents
3. **Document References**: Links to source documents in responses
4. **Progress Tracking**: Real-time progress for long-running tasks

#### Data Utilization
1. **Vector Search Results**: Semantic search results displayed
2. **Graph Visualizations**: Interactive graph views in responses
3. **Document Previews**: Processed document content access
4. **Insight Summaries**: Key insights from document analysis

### Autogen Agents

#### Multi-Agent Orchestration
Autogen agents utilize document processing data through:

1. **Conversational Interface**: Natural language interaction
2. **Tool Integration**: Access to vector search, graph queries, document retrieval
3. **Collaborative Processing**: Multiple agents working together
4. **Dynamic Knowledge Access**: Real-time access to processed documents

#### Query Processing Workflow
1. **Query Reception**: User query processed by Autogen framework
2. **Agent Assignment**: Appropriate agents selected for task
3. **Tool Execution**:
   - Vector search for relevant content
   - Graph traversal for relationship discovery
   - Document content extraction
4. **Information Synthesis**: Agents collaborate to synthesize information
5. **Response Formulation**: Coordinated response generation
6. **Quality Assurance**: Cross-verification between agents

#### Document Generation Capabilities
1. **Requirement Analysis**: Autogen agents analyze document requirements
2. **Research Coordination**: Multiple agents research different aspects
3. **Content Integration**: Information integrated from various sources
4. **Review Process**: Automated review and refinement
5. **Final Assembly**: Document assembled with proper formatting

## Data Flow Architecture

### Document Processing Pipeline
```
Frontend (FileUpload.tsx)
    ↓
API Gateway → Document Service
    ↓
Storage Service (Raw Files)
    ↓
Enhanced Processing (JSONL + LLM)
    ↓
Vector Service (Embeddings)
    ↓
Graph Service (Entities)
    ↓
WebSocket Updates
    ↓
UI Updates (ProcessingProgressView.tsx)
```

### AI Agent Query Flow
```
User Query (Chatbubble)
    ↓
AI Agent Service (Crew AI / Autogen)
    ↓
Knowledge Retrieval:
├── Vector Search (Weaviate)
├── Graph Query (Neo4j)
└── Document Access (Storage)
    ↓
Context Assembly
    ↓
LLM Response Generation
    ↓
Response with Source Attribution
```

## Performance and Scalability

### Processing Optimizations
1. **Background Processing**: All heavy operations run asynchronously
2. **Batch Operations**: Vector embeddings and graph updates batched
3. **Progress Tracking**: Real-time status updates via WebSocket
4. **Error Handling**: Graceful degradation and retry mechanisms

### Database Optimizations
1. **Vector Indexing**: Optimized for similarity search performance
2. **Graph Partitioning**: Project-based graph isolation
3. **Caching**: Redis caching for frequently accessed data
4. **Connection Pooling**: Efficient database connection management

### Monitoring and Analytics
1. **Processing Metrics**: Detailed performance tracking
2. **Error Monitoring**: Comprehensive error logging and alerting
3. **Usage Analytics**: User interaction and system usage tracking
4. **Health Checks**: Service health monitoring across all components

## Conclusion

The document processing system in the Nagarro Ascent Platform provides a comprehensive, scalable solution for document ingestion, processing, and knowledge extraction. Through the integration of multiple specialized services and AI agents, it enables sophisticated query answering and document generation capabilities that leverage both semantic search and structured knowledge graphs.

The system's modular architecture ensures maintainability and extensibility, while the real-time progress tracking and WebSocket integration provide excellent user experience. The AI agent integration through Crew AI and Autogen frameworks enables advanced conversational interfaces and automated document generation workflows.