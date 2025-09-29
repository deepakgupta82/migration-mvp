# Service Registry

## Service Overview

The Service Registry is a distributed service discovery and health monitoring service that operates on port 8011. It provides centralized service registration, discovery, health monitoring, and real-time status broadcasting for the Nagarro Ascent microservices platform.

### Key Features

- **Service Discovery**: Automatic service registration and discovery
- **Health Monitoring**: Continuous health checks and status tracking
- **Distributed Architecture**: Fault-tolerant service coordination
- **Real-time Notifications**: WebSocket-based status updates
- **Docker Integration**: Container status monitoring
- **Load Balancing Support**: Service endpoint distribution
- **Configuration Management**: Service metadata and configuration storage

## Functionality

### Core Capabilities

1. **Service Registration & Discovery**
   - Automatic service registration with health endpoints
   - Service discovery with load balancing
   - Service metadata management
   - Dynamic service lifecycle management

2. **Health Monitoring & Status**
   - Continuous health check execution
   - Service status aggregation and reporting
   - Failure detection and recovery
   - Performance metrics collection

3. **Real-time Communication**
   - WebSocket-based status broadcasting
   - Event-driven notifications
   - Real-time dashboard updates
   - Service status subscriptions

4. **Infrastructure Integration**
   - Docker container monitoring
   - Kubernetes service discovery integration
   - Network topology awareness
   - Cross-service dependency tracking

### Dependencies

- **Docker**: Container status monitoring
- **WebSocket Service**: Real-time status broadcasting
- **Redis**: Optional caching and pub/sub messaging
- **All Platform Services**: Service health monitoring targets

## APIs/Endpoints

### Service Management
- `POST /services/register` - Register a new service
- `DELETE /services/{service_name}` - Unregister a service
- `GET /services` - Get all registered services
- `GET /services/{service_name}` - Get specific service details

### Health Monitoring
- `GET /health` - Service registry health check
- `GET /health/summary` - Platform health summary
- `GET /livez` - Liveness probe
- `GET /healthz` - Readiness probe

### WebSocket Communication
- `WS /ws` - Real-time service status updates
- Service registration/unregistration events
- Health status change notifications
- Platform status broadcasts

## Data Models

### Service Info Structure
```json
{
  "name": "document-service",
  "host": "localhost",
  "port": 8003,
  "health_endpoint": "/health",
  "status": "healthy",
  "last_check": "2024-01-01T12:00:00.000000",
  "response_time": 0.045,
  "version": "1.0.0",
  "metadata": {
    "description": "Document processing service",
    "dependencies": ["storage-service", "vector-service"],
    "tags": ["document", "processing", "ai"]
  }
}
```

### Health Summary Structure
```json
{
  "total": 12,
  "healthy": 11,
  "unhealthy": 1,
  "error": 0,
  "timeout": 0,
  "unknown": 0,
  "health_percentage": 91.67,
  "last_updated": "2024-01-01T12:00:00.000000"
}
```

### Service Status Update Structure
```json
{
  "type": "health_update",
  "service_name": "document-service",
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00.000000",
  "response_time": 0.045,
  "details": {
    "version": "1.0.0",
    "uptime": 3600
  }
}
```

## Key Components

### ServiceRegistryManager (`main.py`)

**Core service registry orchestration**

- **Responsibilities**:
  - Service registration and discovery management
  - Health monitoring coordination
  - WebSocket communication handling
  - Docker integration and container monitoring

### Health Monitoring Loop

**Continuous service health checking**

- **Responsibilities**:
  - Periodic health check execution
  - Status change detection and notification
  - Performance metrics collection
  - Failure recovery and alerting

### WebSocket Gateway

**Real-time status broadcasting**

- **Responsibilities**:
  - WebSocket connection management
  - Message routing and broadcasting
  - Client subscription handling
  - Connection cleanup and scaling

## Data Flow

### Service Registration Flow

1. **Service Startup**: Service initializes and registers
2. **Registration Request**: Service sends registration to registry
3. **Validation**: Registration data validated
4. **Storage**: Service information stored in registry
5. **Health Check**: Initial health check performed
6. **Notification**: Registration event broadcast via WebSocket
7. **Discovery**: Service becomes available for discovery

### Health Monitoring Flow

1. **Health Check Cycle**: Registry checks all registered services
2. **HTTP Request**: Health endpoint called for each service
3. **Response Analysis**: Response time and status evaluated
4. **Status Update**: Service status updated in registry
5. **Threshold Check**: Status change thresholds evaluated
6. **Notification**: Status changes broadcast if significant
7. **Metrics Update**: Health metrics updated for monitoring

### Service Discovery Flow

1. **Discovery Request**: Client requests service information
2. **Lookup**: Service information retrieved from registry
3. **Load Balancing**: Available service instances evaluated
4. **Endpoint Selection**: Optimal endpoint selected
5. **Response**: Service endpoint information returned
6. **Caching**: Discovery results cached for performance

## Complete Working Details

### Configuration

**Environment Variables**:
- `REGISTRY_HEALTH_INTERVAL_SEC`: Health check interval (default: 120)
- `REGISTRY_HEALTH_TIMEOUT_SEC`: Health check timeout (default: 5)
- `REGISTRY_MAX_RETRIES`: Maximum registration retries
- `DOCKER_MONITORING_ENABLED`: Enable Docker container monitoring

### Service Health States

- **healthy**: Service responding normally
- **unhealthy**: Service returning error status
- **error**: Service throwing exceptions
- **timeout**: Service not responding within timeout
- **unknown**: Service status not yet determined

### Monitoring Intervals

- **Health Checks**: Every 120 seconds (configurable)
- **Docker Monitoring**: Integrated with health check cycle
- **WebSocket Ping**: Every 30 seconds for connection maintenance
- **Cache Cleanup**: Automatic cleanup of stale connections

### Performance Characteristics

- **Registration Speed**: Sub-second service registration
- **Health Check Latency**: 1-5 seconds per service
- **Discovery Speed**: Sub-millisecond cached lookups
- **Concurrent Connections**: Thousands of WebSocket connections
- **Memory Usage**: Efficient in-memory service storage

### Error Handling

- **Registration Failures**: Automatic retry with exponential backoff
- **Health Check Errors**: Individual service failure isolation
- **Network Issues**: Graceful degradation with cached data
- **WebSocket Failures**: Connection cleanup and client notification

### Monitoring and Observability

- **Service Metrics**: Registration counts, health status distribution
- **Performance Monitoring**: Health check response times, discovery latency
- **WebSocket Analytics**: Connection counts, message volumes
- **Docker Integration**: Container status and resource usage

### Security Considerations

- **Service Authentication**: Service registration authentication
- **Access Control**: Discovery endpoint access restrictions
- **Data Validation**: Service registration data validation
- **Audit Logging**: All registry operations logged

### Scaling Considerations

- **Horizontal Scaling**: Multiple registry instances with data synchronization
- **Load Balancing**: Service discovery load distribution
- **Caching**: Redis-based caching for high availability
- **WebSocket Scaling**: Connection distribution across instances