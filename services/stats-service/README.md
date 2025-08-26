# Stats Service

Real-time event-driven statistics service for the Cloud Migration Platform.

## Overview

The Stats Service provides real-time statistics and metrics for the entire platform using an event-driven architecture with Redis pub/sub. It replaces the previous pull-based monolithic statistics system with efficient real-time updates.

## Features

- **Real-time Statistics**: WebSocket-based real-time updates for platform and project metrics
- **Event-driven Architecture**: Redis pub/sub integration for automatic metric updates
- **Platform Metrics**: Overall platform health, service status, and aggregate statistics
- **Project Metrics**: Per-project document processing, embeddings, assessments, and progress tracking
- **High Performance**: Redis caching for fast data retrieval
- **Scalable Design**: Microservice architecture with independent deployment

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Other Services│    │   Stats Service  │    │   Frontend/UI   │
│                 │    │                  │    │                 │
│  • Document     │───▶│  Event Listener  │    │   WebSocket     │
│  • Vector       │    │  (Redis Pub/Sub) │    │   Connections   │
│  • Graph        │    │        │         │◀───│                 │
│  • Assessment   │    │        ▼         │    │                 │
│                 │    │  Stats Processor │    │                 │
└─────────────────┘    │  (Redis Cache)   │    └─────────────────┘
                       │        │         │
                       │        ▼         │
                       │   REST API       │
                       └──────────────────┘
```

## API Endpoints

### Platform Statistics
- `GET /api/v1/stats/platform` - Get platform-wide statistics
- `GET /api/v1/stats/projects` - Get statistics for all projects

### Project Statistics
- `GET /api/v1/stats/projects/{project_id}` - Get specific project statistics

### WebSocket Endpoints
- `WS /ws/platform-stats` - Real-time platform statistics updates
- `WS /ws/project-stats/{project_id}` - Real-time project statistics updates

### Event Triggers (for testing)
- `POST /api/v1/stats/projects/{project_id}/events/document-processed`
- `POST /api/v1/stats/projects/{project_id}/events/embeddings-updated`
- `POST /api/v1/stats/projects/{project_id}/events/graph-updated`
- `POST /api/v1/stats/projects/{project_id}/events/assessment-status`

### Admin Endpoints
- `POST /api/v1/stats/admin/reset` - Reset all statistics
- `GET /api/v1/stats/admin/cache-info` - Get cache information

## Environment Setup

### Prerequisites
- Python 3.11
- Redis server (for caching and pub/sub)
- Access to project service and other platform services

### Virtual Environment
```bash
cd services/stats-service
python -m venv .venv
.venv\Scripts\activate  # Windows
# or
source .venv/bin/activate  # Linux/Mac
```

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Environment Variables
Create a `.env` file:
```env
# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0

# Service Configuration
SERVICE_NAME=stats-service
SERVICE_PORT=8004
LOG_LEVEL=INFO

# External Services
PROJECT_SERVICE_URL=http://localhost:8002
BACKEND_SERVICE_URL=http://localhost:8000
```

## Running the Service

### Development
```bash
uvicorn main:app --host 0.0.0.0 --port 8004 --reload
```

### Production
```bash
uvicorn main:app --host 0.0.0.0 --port 8004 --workers 4
```

## Event System

The service listens to the following Redis channels for real-time updates:

### Document Processing Events
- `document.processed` - When a document is successfully processed
- `document.failed` - When document processing fails

### Vector/Embeddings Events
- `embeddings.updated` - When document embeddings are generated/updated
- `embeddings.batch_completed` - When a batch of embeddings is completed

### Graph Events
- `graph.updated` - When knowledge graph is updated
- `graph.node_added` - When new nodes are added to the graph

### Assessment Events
- `assessment.status_changed` - When assessment status changes
- `assessment.completed` - When assessment is completed

### Project Lifecycle Events
- `project.created` - When a new project is created
- `project.updated` - When project metadata is updated
- `project.deleted` - When a project is deleted

## Data Models

### Platform Statistics
```json
{
  "total_projects": 15,
  "total_documents": 1245,
  "total_embeddings": 856,
  "active_assessments": 3,
  "services_health": {
    "document-service": "healthy",
    "vector-service": "healthy",
    "graph-service": "degraded",
    "assessment-service": "healthy"
  },
  "performance_metrics": {
    "avg_processing_time": 2.5,
    "total_processing_time": 3600,
    "success_rate": 0.95
  },
  "last_updated": "2024-01-15T10:30:00Z"
}
```

### Project Statistics
```json
{
  "project_id": "proj_123",
  "name": "Legacy App Migration",
  "documents": {
    "total": 45,
    "processed": 42,
    "processing": 2,
    "failed": 1,
    "pending": 0
  },
  "embeddings": {
    "total": 38,
    "status": "completed"
  },
  "graph": {
    "nodes": 156,
    "relationships": 324,
    "last_updated": "2024-01-15T09:45:00Z"
  },
  "assessment": {
    "status": "completed",
    "score": 85,
    "recommendations": 12,
    "completed_at": "2024-01-15T08:20:00Z"
  },
  "processing_stats": {
    "total_time": 1800,
    "avg_doc_time": 42.8,
    "success_rate": 0.93
  },
  "last_updated": "2024-01-15T10:30:00Z"
}
```

## Integration with Other Services

### Publishing Events to Stats Service

Other services should publish events to Redis channels when significant actions occur:

```python
import redis
import json

# Initialize Redis client
redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)

# Publish document processed event
event_data = {
    "project_id": "proj_123",
    "document_id": "doc_456",
    "document_name": "legacy-system.pdf",
    "processing_time": 45.2,
    "status": "completed",
    "timestamp": "2024-01-15T10:30:00Z"
}

redis_client.publish("document.processed", json.dumps(event_data))
```

### Consuming Stats via WebSocket

Frontend applications can connect to WebSocket endpoints for real-time updates:

```javascript
// Connect to platform stats
const platformWs = new WebSocket('ws://localhost:8004/ws/platform-stats');
platformWs.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'platform_stats_update') {
        updatePlatformDashboard(data.data);
    }
};

// Connect to project-specific stats
const projectWs = new WebSocket('ws://localhost:8004/ws/project-stats/proj_123');
projectWs.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'project_stats_update') {
        updateProjectDashboard(data.data);
    }
};
```

## Performance Considerations

- **Redis Caching**: All statistics are cached in Redis for fast retrieval
- **Event Batching**: Multiple events can be batched for efficient processing
- **Connection Management**: WebSocket connections are efficiently managed and cleaned up
- **Memory Usage**: Statistics are stored efficiently with TTL for historical data

## Monitoring and Health Checks

The service provides health checks at `/health` endpoint and includes:
- Redis connectivity status
- Event listener status
- WebSocket connection count
- Memory usage statistics

## Development Guidelines

1. **Event Design**: Events should be idempotent and include all necessary context
2. **Error Handling**: All event processing includes proper error handling and logging
3. **Testing**: Use the manual event triggers for integration testing
4. **Performance**: Monitor Redis memory usage and connection counts
5. **Documentation**: Update this README when adding new event types or endpoints

## Troubleshooting

### Common Issues

1. **Redis Connection Issues**
   - Check Redis server status
   - Verify connection parameters in environment variables
   - Check firewall settings

2. **WebSocket Disconnections**
   - Implement reconnection logic in frontend
   - Check network stability
   - Monitor connection count via admin endpoints

3. **Event Processing Delays**
   - Check Redis pub/sub lag
   - Monitor event listener logs
   - Verify other services are publishing events correctly

4. **Inconsistent Statistics**
   - Use admin reset endpoint to re-sync data
   - Check for missing event publications from other services
   - Verify project service integration

## Future Enhancements

- **Historical Data**: Store historical statistics for trending analysis
- **Alerting**: Add threshold-based alerting for critical metrics
- **Metrics Export**: Prometheus/Grafana integration for monitoring
- **Event Replay**: Ability to replay events for data recovery
- **Advanced Analytics**: Machine learning-based trend analysis
