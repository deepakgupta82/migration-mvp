# Backend Service Documentation

## Service Overview

The Backend service is the central API Gateway for the Migration Platform, implemented as a FastAPI application. It serves as the primary entry point for all client requests, routing them to specialized microservices while providing unified authentication, caching, and real-time communication capabilities.

**Port:** 8000
**Technology:** FastAPI (Python)
**Role:** API Gateway and orchestration layer

## Functionality

The Backend service provides the following core functionalities:

- **API Gateway Routing:** Routes requests to 7 specialized microservices (project-service, document-service, reporting-service, vector-service, graph-service, llm-service, ai-agent-service, storage-service, websocket-service, knowledge-service, analytics-service)
- **Authentication & Authorization:** JWT-based authentication with role-based access control
- **Real-time Communication:** WebSocket endpoints for logs, stats, crew interactions, and document processing
- **Caching:** In-memory TTL caching for health checks, stats, and templates
- **Health Monitoring:** Comprehensive health checks for all services and infrastructure
- **Statistics Aggregation:** Platform and project-level statistics with real-time updates
- **Configuration Management:** Centralized configuration loading and validation

## APIs/Endpoints

### Health & Monitoring
- `GET /api/health` - Comprehensive health check with service statuses
- `GET /health` - Health check alias
- `GET /api/health/containers` - Container statistics proxy
- `GET /api/system/websocket-stats` - WebSocket connection statistics

#### Environment variables (Health & Containers)
- `HEALTH_CACHE_TTL_SEC` or `HEALTH_POLL_INTERVAL_SEC`: Minimum 60. Controls cache TTL for `/api/health` so UI will not see updates more frequently than this.
- `CONTAINERS_CACHE_TTL_SEC` or `CONTAINERS_POLL_INTERVAL_SEC`: Minimum 60. Controls cache TTL for `/api/health/containers`.
    - The UI can additionally set `REACT_APP_HEALTH_POLL_INTERVAL_MS` and `REACT_APP_CONTAINERS_POLL_INTERVAL_MS` (in milliseconds). Both enforce a minimum of 60000ms.

Notes:
- Application service statuses on the Overview tab are sourced from the Service Registry via `/api/health` and are shown in the left column.
- The right column only displays infrastructure containers (neo4j, minio, loki, promtail, redis, postgresql, weaviate). Application services are no longer duplicated there.

### Project Management
- `GET /api/projects/` - List all projects
- `POST /api/projects/` - Create new project
- `GET /api/projects/{project_id}` - Get project details
- `PUT /api/projects/{project_id}` - Update project
- `DELETE /api/projects/{project_id}` - Delete project
- `GET /api/projects/stats` - Project statistics
- `GET /api/projects/{project_id}/stats` - Individual project statistics

### Document Processing
- `POST /api/projects/{project_id}/upload` - Upload documents
- `POST /api/projects/{project_id}/process-selected` - Process selected documents
- `POST /api/projects/{project_id}/documents/generate` - Generate documents from templates
- `GET /api/projects/{project_id}/download/{filename}` - Download generated documents

### Knowledge Base
- `POST /api/projects/{project_id}/query` - Query project knowledge base
- `POST /api/projects/{project_id}/chat` - Chat with project knowledge base
- `GET /api/projects/{project_id}/graph` - Get project knowledge graph

### LLM Configuration
- `GET /api/llm/providers` - Get available LLM providers
- `GET /api/llm/configurations` - List LLM configurations
- `POST /api/llm/configurations` - Create LLM configuration
- `PUT /api/llm/configurations/{config_id}` - Update LLM configuration
- `DELETE /api/llm/configurations/{config_id}` - Delete LLM configuration
- `POST /api/llm/test-llm-config` - Test LLM configuration

### Analytics
- `GET /api/analytics/fusion` - Fusion search analytics
- `GET /api/analytics/rag` - RAG synthesis analytics
- `GET /api/analytics/dashboard` - Combined analytics dashboard

### AI Agent Integration
- `GET /api/agents` - List available AI agents
- `GET /api/crews` - List available AI crews
- `POST /api/agents/{agent_id}/tasks` - Start agent task
- `POST /api/crews/{crew_id}/workflows` - Start crew workflow
- `POST /api/projects/{project_id}/crews/document/run` - Run document crew
- `POST /api/projects/{project_id}/crews/assessment/run` - Run assessment crew

### WebSocket Endpoints
- `WS /ws/logs/{service}` - Real-time service logs streaming
- `WS /ws/console/{service}` - Raw container console output
- `WS /ws/project-stats/{project_id}` - Project statistics updates
- `WS /ws/platform-stats` - Platform statistics updates
- `WS /ws/crew-interactions/{project_id}` - Crew interaction updates
- `WS /ws/document-processing/{project_id}` - Document processing updates

## Data Models/Schemas

### Core Models
```python
class ProjectCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    client_name: str
    client_contact: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_api_key_id: Optional[str] = None

class QueryRequest(BaseModel):
    query: str
    limit: Optional[int] = 10
    use_llm: Optional[bool] = False

class LLMConfigurationCreate(BaseModel):
    name: str
    provider: str
    model: str
    api_key: str
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    description: Optional[str] = None
```

### Response Models
- `ProjectResponse` - Project details with user associations
- `LLMConfigurationResponse` - LLM configuration details
- `PlatformSettingResponse` - Platform configuration settings

## Key Components

### Core Services
- **Service Client (`service_client.py`)**: Handles HTTP communication with microservices
- **Stats Service (`stats_service.py`)**: Aggregates and caches platform/project statistics
- **Project Service (`project_service.py`)**: Project data management and caching
- **JWT Auth (`jwt_auth.py`)**: Token validation and user authentication
- **Log Manager (`log_stream.py`)**: WebSocket log streaming management

### Managers
- **WebSocket Stats Manager (`websocket_stats_manager.py`)**: Real-time stats broadcasting
- **Process WebSocket Manager (`process_ws.py`)**: Document processing WebSocket handling
- **Crew Logger Registry (`crew_logger.py`)**: AI crew interaction logging

### Utilities
- **Event Bus (`event_bus.py`)**: Inter-service event communication
- **Correlation ID Middleware**: Request tracing across services
- **Config Parsers (`config_parsers.py`)**: Configuration file handling
- **Sanitization Utils (`sanitization.py`)**: Input validation and cleaning
- **Semantic Chunker (`semantic_chunker.py`)**: Document text chunking
- **Cypher Generator (`cypher_generator.py`)**: Neo4j query generation

## Data Flow

### Request Processing
1. **Authentication**: JWT token validation via `Authorization` header or `token` query parameter
2. **Routing**: Gateway routes requests to appropriate microservices based on URL patterns
3. **Caching**: Frequently accessed data (health, stats, templates) cached with TTL
4. **Response**: Aggregated responses from microservices returned to client

### Real-time Updates
1. **WebSocket Connection**: Clients establish WebSocket connections for real-time data
2. **Event Subscription**: Services register for specific event types
3. **Broadcasting**: Events published to connected clients via WebSocket
4. **State Management**: Connection state tracked and cleaned up on disconnect

### Statistics Aggregation
1. **Event-driven Updates**: Microservices publish stats events via event bus
2. **Caching**: Stats cached with configurable TTL for performance
3. **Real-time Broadcasting**: Updates pushed to WebSocket subscribers
4. **Fallback**: Cached data served when services unavailable

## Complete Working Details

### Startup Process
1. **Environment Loading**: Load configuration from `.env` and `config.local.json`
2. **Database Initialization**: Ensure PostgreSQL connectivity
3. **Service Discovery**: Load microservice endpoints and health checks
4. **Cache Warming**: Pre-load frequently accessed data
5. **WebSocket Managers**: Initialize real-time communication handlers

### Configuration
- **Environment Variables**: Service URLs, database connections, cache TTLs
- **Local Config**: `config.local.json` for development overrides
- **Dynamic Config**: Runtime configuration updates without restart

### Error Handling
- **Service Unavailable**: Graceful degradation with cached responses
- **Timeout Handling**: Configurable timeouts with fallback behavior
- **Correlation IDs**: Request tracing across service boundaries
- **Logging**: Structured JSON logging with correlation ID injection

### Security
- **JWT Authentication**: Bearer token validation
- **Role-based Access**: Platform admin vs project user permissions
- **WebSocket Auth**: Token validation for real-time connections
- **Input Validation**: Pydantic model validation and sanitization

### Performance Optimizations
- **Caching**: Multi-level caching (memory, Redis integration)
- **Connection Pooling**: Database connection reuse
- **Async Operations**: Non-blocking I/O for external service calls
- **Background Tasks**: Asynchronous processing for heavy operations

### Monitoring & Observability
- **Health Checks**: Comprehensive service health monitoring
- **Metrics**: WebSocket connection stats, request counts
- **Logging**: Structured logging with service correlation
- **Tracing**: Request correlation across microservices

The Backend service acts as the intelligent orchestration layer, providing a unified API surface while maintaining loose coupling with specialized microservices.