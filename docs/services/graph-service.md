# Graph Service

## Service Overview

The Graph Service is a knowledge graph management service that operates on port 8006. It provides Neo4j-based graph database operations, entity extraction, relationship mapping, and graph visualization capabilities. The service handles knowledge graph construction, querying, and maintenance for the Nagarro Ascent platform.

### Key Features

- **Neo4j Integration**: Full graph database operations with Cypher queries
- **Entity Extraction**: Automatic entity identification from documents
- **Relationship Mapping**: Graph relationship creation and management
- **Knowledge Graph Construction**: Automated graph building from document content
- **Graph Querying**: Complex graph traversal and pattern matching
- **Visualization Support**: Graph data preparation for visualization tools
- **PVC Repository**: Persistent storage for graph metadata
- **Real-time Updates**: Event-driven graph updates

## Functionality

### Core Capabilities

1. **Graph Database Operations**
   - Node and relationship CRUD operations
   - Cypher query execution
   - Graph schema management
   - Batch operations for performance

2. **Entity and Relationship Management**
   - Entity extraction from text content
   - Relationship identification and classification
   - Graph node creation and linking
   - Entity resolution and deduplication

3. **Knowledge Graph Construction**
   - Automated graph building from documents
   - Ontology management
   - Graph consistency validation
   - Incremental graph updates

4. **Query and Analytics**
   - Complex graph queries
   - Path finding and traversal
   - Graph analytics and metrics
   - Subgraph extraction

### Dependencies

- **Neo4j**: Graph database for storing nodes and relationships
- **Redis**: Caching and session management
- **Stats Service**: Event notifications for graph updates
- **Document Service**: Source documents for graph construction

## APIs/Endpoints

### Graph Operations
- `GET /api/graphs/health` - Service health check
- `POST /api/graphs/projects/{project_id}/nodes` - Create graph nodes
- `GET /api/graphs/projects/{project_id}/nodes` - Query graph nodes
- `POST /api/graphs/projects/{project_id}/relationships` - Create relationships
- `GET /api/graphs/projects/{project_id}/relationships` - Query relationships

### Knowledge Graph Management
- `POST /api/graphs/projects/{project_id}/build` - Build knowledge graph from documents
- `GET /api/graphs/projects/{project_id}/graph` - Get project knowledge graph
- `POST /api/graphs/projects/{project_id}/query` - Execute graph queries
- `GET /api/graphs/projects/{project_id}/entities` - Get extracted entities

### Analytics and Visualization
- `GET /api/graphs/projects/{project_id}/analytics` - Graph analytics
- `GET /api/graphs/projects/{project_id}/visualization` - Visualization data
- `GET /api/graphs/projects/{project_id}/paths` - Path finding between entities

## Data Models

### Graph Node Structure
```json
{
  "node_id": "node_123",
  "labels": ["Entity", "Person"],
  "properties": {
    "name": "John Doe",
    "type": "person",
    "confidence": 0.95,
    "source_document": "doc_456"
  },
  "created_at": "2024-01-01T00:00:00.000000"
}
```

### Relationship Structure
```json
{
  "relationship_id": "rel_789",
  "type": "WORKS_FOR",
  "start_node": "node_123",
  "end_node": "node_456",
  "properties": {
    "confidence": 0.88,
    "source": "document_extraction"
  },
  "created_at": "2024-01-01T00:00:00.000000"
}
```

### Knowledge Graph Structure
```json
{
  "graph_id": "graph_proj_123",
  "project_id": "project_123",
  "nodes": [...],
  "relationships": [...],
  "metadata": {
    "total_nodes": 150,
    "total_relationships": 200,
    "entity_types": ["Person", "Organization", "Technology"],
    "created_at": "2024-01-01T00:00:00.000000",
    "last_updated": "2024-01-01T12:00:00.000000"
  }
}
```

## Key Components

### GraphProcessor (`app/core/graph_processor.py`)

**Core graph processing engine**

- **Responsibilities**:
  - Neo4j connection management
  - Graph schema initialization
  - Entity extraction and relationship identification
  - Graph construction and maintenance
  - Query execution and result processing

### Graphs Router (`app/routers/graphs.py`)

**FastAPI router for graph operations**

- **Responsibilities**:
  - HTTP endpoint definitions
  - Request validation and response formatting
  - Error handling and logging
  - Background task management

### PVC Repository (`app/pvc_repo/`)

**Persistent storage for graph metadata**

- **Responsibilities**:
  - Graph metadata persistence
  - Query history and caching
  - Configuration storage

## Data Flow

### Graph Construction Flow

1. **Document Ingestion**: Documents received for graph construction
2. **Entity Extraction**: NLP-based entity identification
3. **Relationship Identification**: Pattern-based relationship extraction
4. **Node Creation**: Graph nodes created for entities
5. **Relationship Creation**: Edges created between related nodes
6. **Graph Validation**: Consistency and quality checks
7. **Persistence**: Graph stored in Neo4j database

### Query Processing Flow

1. **Query Reception**: Graph query received via API
2. **Query Validation**: Cypher query syntax validation
3. **Execution**: Query executed against Neo4j
4. **Result Processing**: Results formatted and enriched
5. **Response**: Query results returned to client

## Complete Working Details

### Configuration

**Environment Variables**:
- `NEO4J_URI`: Neo4j connection URI (default: `bolt://localhost:7687`)
- `NEO4J_USER`: Neo4j username (default: `neo4j`)
- `NEO4J_PASSWORD`: Neo4j password (default: `password`)
- `PVC_STORE`: Storage backend for PVC data (default: `redis`)

### Neo4j Schema

**Node Labels**:
- `Entity`: Base entity type
- `Person`: Person entities
- `Organization`: Organization entities
- `Technology`: Technology entities
- `Document`: Source documents

**Relationship Types**:
- `MENTIONS`: Entity mentions in documents
- `RELATED_TO`: General relationships
- `WORKS_FOR`: Employment relationships
- `USES`: Technology usage relationships

### Performance Characteristics

- **Query Latency**: Sub-second for simple queries, seconds for complex traversals
- **Concurrent Operations**: Neo4j connection pooling for high concurrency
- **Memory Usage**: Efficient graph algorithms with memory bounds
- **Storage Scaling**: Neo4j clustering support for large graphs

### Error Handling

- **Connection Failures**: Automatic reconnection with retry logic
- **Query Errors**: Detailed error messages with suggestions
- **Data Validation**: Input validation and sanitization
- **Transaction Rollback**: Atomic operations with rollback on failure

### Monitoring and Observability

- **Health Checks**: Neo4j connectivity and service status
- **Metrics**: Query performance, graph size statistics
- **Logging**: Structured logging with correlation IDs
- **Graph Analytics**: Node/relationship counts and distributions

### Security Considerations

- **Access Control**: Project-scoped graph operations
- **Query Validation**: Safe Cypher query execution
- **Data Privacy**: Sensitive information handling
- **Audit Logging**: All graph operations logged

### Scaling Considerations

- **Database Clustering**: Neo4j cluster support for high availability
- **Query Optimization**: Index usage and query planning
- **Caching**: Redis caching for frequent queries
- **Load Balancing**: Multiple service instances support

## Table-aware LLM Extraction (Update)

When processing spreadsheet or table-like content (e.g., .xlsx, .xls, .csv or structured elements summarized as `TABLE:`), the graph-service augments the LLM prompt with explicit row-aware guidance:

- Treat headers as schema and iterate rows.
- Emit Entities per row (Server, Application, Environment, OperatingSystem, Hardware, IPAddress, Network, Datacenter when present).
- Emit Relationships per row using actual values:
  - HOSTS (Server -> Application)
  - RUNS_ON (Server -> OperatingSystem)
  - HAS_ENV (Application -> Environment)
  - LOCATED_IN (Server -> Datacenter)
  - HAS_IP (Server -> IPAddress)
  - POWERED_BY (Server -> Hardware)
  - IN_SUBNET (Server -> Network) when applicable
- Output must strictly be a single JSON object: { "entities": [], "relationships": [] }.