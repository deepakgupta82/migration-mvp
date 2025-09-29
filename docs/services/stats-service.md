# Stats Service

## Service Overview

The Stats Service is an event-driven statistics and analytics service that provides real-time platform and project-level statistics aggregation. It operates on port 8004 and serves as the central hub for collecting, processing, and distributing statistical data across the Nagarro Ascent platform.

### Key Features

- **Real-time Statistics**: Event-driven updates for immediate data availability
- **Multi-level Aggregation**: Platform-wide and project-specific metrics
- **Redis Caching**: High-performance data storage with TTL-based expiration
- **WebSocket Support**: Real-time streaming of statistics updates
- **Event-driven Architecture**: Listens to platform events via Redis pub/sub
- **RESTful API**: Comprehensive endpoints for statistics retrieval and management

## Functionality

### Core Capabilities

1. **Platform Statistics Aggregation**
   - Total projects, documents, embeddings, and graph nodes
   - Service health monitoring
   - Performance metrics (processing times, cache hit ratios)

2. **Project-level Statistics**
   - Document counts and processing status
   - Embeddings and vector data metrics
   - Graph database statistics
   - Assessment progress tracking

3. **Event Processing**
   - Document processing events
   - Embeddings update events
   - Graph update events
   - Assessment status changes
   - Project lifecycle events

4. **Real-time Updates**
   - WebSocket endpoints for live statistics streaming
   - Event broadcasting to connected clients
   - Automatic cache invalidation and updates

### Dependencies

- **Redis**: Primary data store for caching and pub/sub messaging
- **Project Service**: Source for project information and synchronization
- **Document Service**: Document processing event source
- **Vector Service**: Embeddings update event source
- **Graph Service**: Graph update event source

## APIs/Endpoints

### REST API Endpoints

#### Platform Statistics
- `GET /api/stats/platform` - Get comprehensive platform statistics
- `GET /api/stats/projects` - Get statistics for all projects

#### Project Statistics
- `GET /api/stats/projects/{project_id}` - Get detailed statistics for a specific project

#### Manual Event Triggers (Testing/Admin)
- `POST /api/stats/projects/{project_id}/events/document-processed` - Trigger document processed event
- `POST /api/stats/projects/{project_id}/events/document-uploaded` - Trigger document uploaded event
- `POST /api/stats/projects/{project_id}/events/embeddings-updated` - Trigger embeddings updated event
- `POST /api/stats/projects/{project_id}/events/graph-updated` - Trigger graph updated event
- `POST /api/stats/projects/{project_id}/events/assessment-status` - Update assessment status

#### Service Management
- `POST /api/stats/services/{service_name}/health` - Update service health status

#### Administrative Endpoints
- `POST /api/stats/admin/reset` - Reset all statistics (admin only)
- `GET /api/stats/admin/cache-info` - Get Redis cache information

### WebSocket Endpoints

#### Real-time Statistics Streaming
- `WS /ws/platform-stats` - Real-time platform statistics updates
- `WS /ws/project-stats/{project_id}` - Real-time project-specific statistics updates

### Health Check Endpoints
- `GET /health` - Service health check with Redis connectivity status

## Data Models

### Platform Statistics Structure
```json
{
  "platform": {
    "total_projects": 0,
    "active_projects": 0,
    "total_documents": 0,
    "total_embeddings": 0,
    "total_graph_nodes": 0,
    "total_agents": 0,
    "active_assessments": 0,
    "last_updated": "2024-01-01T00:00:00.000000",
    "uptime_seconds": 0
  },
  "services": {
    "project_service": {"status": "healthy", "last_ping": "2024-01-01T00:00:00.000000"},
    "document_service": {"status": "healthy", "last_ping": "2024-01-01T00:00:00.000000"},
    "vector_service": {"status": "healthy", "last_ping": "2024-01-01T00:00:00.000000"},
    "graph_service": {"status": "healthy", "last_ping": "2024-01-01T00:00:00.000000"},
    "ai_agent_service": {"status": "unknown", "last_ping": null}
  },
  "performance": {
    "avg_document_processing_time": 0,
    "avg_query_response_time": 0,
    "cache_hit_ratio": 0.0
  }
}
```

### Project Statistics Structure
```json
{
  "project_id": "project_123",
  "name": "Migration Project Alpha",
  "status": "active",
  "files_count": 150,
  "embeddings_count": 2500,
  "graph_nodes": 75,
  "graph_relationships": 200,
  "assessment_status": "completed",
  "last_activity": "2024-01-01T00:00:00.000000",
  "last_updated": "2024-01-01T00:00:00.000000",
  "processing_stats": {
    "documents_processed": 145,
    "processing_errors": 2,
    "avg_processing_time": 2.3
  }
}
```

### Event Data Structures

#### Document Processed Event
```json
{
  "project_id": "project_123",
  "document": {
    "id": "doc_456",
    "filename": "architecture.pdf",
    "processing_time_ms": 2300,
    "status": "completed"
  }
}
```

#### Embeddings Updated Event
```json
{
  "project_id": "project_123",
  "embeddings": {
    "count": 500,
    "model": "text-embedding-ada-002",
    "dimensions": 1536
  }
}
```

#### Graph Updated Event
```json
{
  "project_id": "project_123",
  "graph": {
    "nodes": 25,
    "relationships": 45,
    "labels": ["Document", "Entity", "Concept"]
  }
}
```

## Key Components

### StatsProcessor (`app/core/stats_processor.py`)

**Core statistics calculation and caching engine**

- **Responsibilities**:
  - Platform and project metrics calculation
  - Redis cache management with TTL
  - Event handling and statistics updates
  - Service health monitoring
  - Project synchronization from Project Service

- **Key Methods**:
  - `initialize()`: Sets up initial platform stats and syncs projects
  - `update_platform_metric()`: Updates platform-wide metrics
  - `update_project_metric()`: Updates project-specific metrics
  - `handle_*_event()`: Event-specific processing methods
  - `get_platform_stats()`: Retrieves cached platform statistics
  - `get_project_stats()`: Retrieves cached project statistics

### EventListener (`app/core/event_listener.py`)

**Event-driven update handler**

- **Responsibilities**:
  - Redis pub/sub subscription management
  - Event routing and processing
  - Background event listening loop
  - Manual event publishing for testing

- **Event Channels**:
  - `platform.document.processed`
  - `platform.embeddings.updated`
  - `platform.graph.updated`
  - `platform.assessment.status_changed`
  - `platform.project.created`
  - `platform.project.deleted`
  - `platform.service.health_check`

- **Key Methods**:
  - `start_listening()`: Initiates Redis pub/sub subscriptions
  - `_listen_loop()`: Main event processing loop
  - `_handle_event()`: Routes events to appropriate handlers
  - `publish_event()`: Manual event publishing

### Statistics Router (`app/routers/stats.py`)

**REST API endpoint definitions**

- **Responsibilities**:
  - HTTP endpoint definitions for statistics retrieval
  - Manual event trigger endpoints for testing
  - Administrative endpoints for cache management
  - Error handling and response formatting

### WebSocket Handlers (`app/websockets/handlers.py`)

**Real-time communication handlers**

- **Responsibilities**:
  - WebSocket connection management
  - Real-time statistics streaming
  - Connection lifecycle handling
  - Message broadcasting to clients

## Data Flow

### Event-Driven Updates

1. **Event Generation**: Platform services publish events to Redis pub/sub channels
2. **Event Reception**: EventListener receives events via Redis subscriptions
3. **Event Processing**: Events are routed to appropriate StatsProcessor methods
4. **Statistics Update**: StatsProcessor updates cached metrics in Redis
5. **Real-time Broadcasting**: Updated statistics are broadcast via WebSocket connections
6. **API Serving**: REST API endpoints serve cached statistics with low latency

### Statistics Retrieval

1. **API Request**: Client requests statistics via REST endpoints
2. **Cache Check**: StatsProcessor checks Redis for cached data
3. **Cache Hit**: Returns cached data if available and fresh
4. **Cache Miss**: Triggers background synchronization if needed
5. **Response**: Formatted statistics returned to client

### Initialization Flow

1. **Service Startup**: FastAPI lifespan event triggers initialization
2. **Redis Connection**: Establishes connection to Redis instance
3. **Platform Stats Init**: Creates initial platform statistics structure
4. **Project Sync**: Fetches project list from Project Service
5. **Project Stats Init**: Initializes statistics for each project
6. **Event Listener Start**: Begins listening for platform events
7. **Health Checks**: Starts periodic service health monitoring

## Complete Working Details

### Configuration

**Environment Variables**:
- `REDIS_URL`: Redis connection URL (default: `redis://localhost:6379`)
- `PROJECT_SERVICE_URL`: Project Service base URL (default: `http://localhost:8002`)
- `DOCUMENT_SERVICE_URL`: Document Service base URL (default: `http://localhost:8003`)
- `VECTOR_SERVICE_URL`: Vector Service base URL (default: `http://localhost:8005`)
- `GRAPH_SERVICE_URL`: Graph Service base URL (default: `http://localhost:8006`)
- `CORS_ALLOWED_ORIGINS`: Comma-separated allowed origins (default: `*`)

### Redis Data Structures

**Platform Statistics Key**: `platform_stats`
- TTL: 300 seconds (5 minutes)
- Contains: Platform metrics, service health, performance data

**Project Statistics Keys**: `project_stats:{project_id}`
- TTL: 300 seconds (5 minutes)
- Contains: Project-specific metrics and processing statistics

### Event Processing Pipeline

1. **Event Ingestion**: Events received via Redis pub/sub
2. **Validation**: Event data validated for required fields
3. **Processing**: Statistics calculations and cache updates
4. **Persistence**: Updated metrics stored in Redis with TTL
5. **Notification**: Real-time updates sent via WebSocket
6. **Logging**: All operations logged with correlation IDs

### Performance Characteristics

- **Cache TTL**: 5 minutes for all statistics
- **Event Processing**: Sub-millisecond processing latency
- **Redis Operations**: Async operations for high throughput
- **WebSocket Connections**: Support for multiple concurrent clients
- **Memory Usage**: Bounded by Redis cache size limits

### Error Handling

- **Redis Connection Failures**: Graceful degradation with cached data
- **Event Processing Errors**: Individual event failures don't stop processing
- **Service Unavailability**: Continues operation with last known good state
- **Cache Misses**: Automatic background synchronization
- **WebSocket Errors**: Connection cleanup and client notification

### Monitoring and Observability

- **Health Checks**: Redis connectivity and service status
- **Metrics**: Processing times, cache hit ratios, event counts
- **Logging**: Structured logging with correlation IDs
- **WebSocket Monitoring**: Connection counts and message rates
- **Cache Analytics**: Hit/miss ratios and memory usage

### Security Considerations

- **WebSocket Authentication**: Token-based authentication required
- **CORS Configuration**: Configurable origin restrictions
- **Input Validation**: All API inputs validated and sanitized
- **Rate Limiting**: Built-in protection against abuse
- **Audit Logging**: All operations logged for compliance

### Scaling Considerations

- **Horizontal Scaling**: Multiple instances can share Redis backend
- **Redis Clustering**: Supports Redis cluster for high availability
- **Event Partitioning**: Can partition events across multiple listeners
- **Cache Sharding**: Statistics can be sharded by project or service
- **WebSocket Load Balancing**: Support for load balancer sticky sessions