# WebSocket Service

## Service Overview

The WebSocket Service is a real-time communication gateway that operates on port 8009. It provides WebSocket connection management, real-time broadcasting, and multi-channel communication for the Nagarro Ascent platform.

### Key Features

- **WebSocket Gateway**: Full-duplex communication channels
- **Multi-channel Broadcasting**: Project and platform-wide messaging
- **Connection Management**: Automatic cleanup and health monitoring
- **Real-time Updates**: Live notifications and status updates
- **Channel-based Communication**: Organized message routing
- **Connection Pooling**: Efficient resource management
- **Health Monitoring**: Connection status and performance tracking

## Functionality

### Core Capabilities

1. **Connection Management**
   - WebSocket connection establishment and maintenance
   - Automatic reconnection handling
   - Connection pooling and resource optimization
   - Timeout and cleanup management

2. **Message Broadcasting**
   - Real-time message distribution
   - Channel-based message routing
   - Selective broadcasting to user groups
   - Message queuing and delivery guarantees

3. **Real-time Updates**
   - Service status notifications
   - Progress updates for long-running operations
   - Live collaboration features
   - Event-driven notifications

4. **Channel Management**
   - Multiple communication channels
   - Channel subscription and unsubscription
   - Message filtering and routing
   - Channel-specific permissions

### Dependencies

- **Redis**: Message queuing and caching
- **Service Registry**: Service discovery and health monitoring
- **Stats Service**: Real-time statistics broadcasting

## APIs/Endpoints

### WebSocket Endpoints
- `WS /ws` - Main WebSocket connection endpoint
- `WS /ws/project/{project_id}` - Project-specific connections
- `WS /ws/service/{service_name}` - Service monitoring connections

### HTTP Endpoints
- `POST /broadcast` - Broadcast message to all connections
- `POST /broadcast/channel/{channel}` - Broadcast to specific channel
- `GET /connections` - Get connection statistics
- `POST /ping` - Send ping to maintain connections

## Data Models

### WebSocket Message Structure
```json
{
  "type": "notification",
  "channel": "platform",
  "data": {
    "event": "service_status",
    "service": "document-service",
    "status": "healthy"
  },
  "timestamp": "2024-01-01T12:00:00.000000"
}
```

### Broadcast Request Structure
```json
{
  "channel_type": "project_status",
  "project_id": "project_123",
  "message": {
    "type": "processing_complete",
    "document_count": 50,
    "processing_time": 120.5
  }
}
```

### Connection Info Structure
```json
{
  "total_connections": 25,
  "active_channels": ["platform", "project_123", "service_health"],
  "connections_per_channel": {
    "platform": 5,
    "project_123": 12,
    "service_health": 8
  },
  "uptime_seconds": 3600
}
```

## Key Components

### WebSocketGateway (`app/core/websocket_gateway.py`)

**Core WebSocket management engine**

- **Responsibilities**:
  - Connection lifecycle management
  - Message routing and broadcasting
  - Channel management and subscriptions
  - Connection health monitoring

### WebSocket Router (`app/routers/websocket.py`)

**WebSocket endpoint definitions**

- **Responsibilities**:
  - WebSocket connection handling
  - Message validation and processing
  - Error handling and logging
  - Connection cleanup

## Data Flow

### Connection Establishment Flow

1. **Connection Request**: Client initiates WebSocket connection
2. **Authentication**: Connection validated and authenticated
3. **Channel Subscription**: Client subscribes to relevant channels
4. **Connection Registration**: Connection added to active pool
5. **Heartbeat Setup**: Keep-alive mechanism established

### Message Broadcasting Flow

1. **Message Reception**: Message received for broadcasting
2. **Channel Resolution**: Target channels determined
3. **Connection Filtering**: Active connections for channels identified
4. **Message Distribution**: Message sent to all relevant connections
5. **Delivery Confirmation**: Success/failure tracking

## Complete Working Details

### Configuration

**Environment Variables**:
- `WEBSOCKET_MAX_CONNECTIONS`: Maximum concurrent connections
- `WEBSOCKET_TIMEOUT`: Connection timeout in seconds
- `WEBSOCKET_HEARTBEAT_INTERVAL`: Heartbeat interval
- `WEBSOCKET_CLEANUP_INTERVAL`: Connection cleanup interval

### Supported Channels

- **platform**: Platform-wide notifications
- **project_{id}**: Project-specific updates
- **service_{name}**: Service health and status
- **user_{id}**: User-specific messages

### Performance Characteristics

- **Connection Capacity**: Thousands of concurrent connections
- **Message Latency**: Sub-millisecond message delivery
- **Memory Usage**: Efficient connection pooling
- **Scalability**: Horizontal scaling support

### Error Handling

- **Connection Failures**: Automatic cleanup and reconnection
- **Message Delivery**: Retry logic for failed deliveries
- **Resource Limits**: Connection limits and throttling
- **Network Issues**: Graceful degradation

### Monitoring and Observability

- **Connection Metrics**: Active connections and channel usage
- **Message Statistics**: Delivery rates and failure counts
- **Performance Monitoring**: Latency and throughput metrics
- **Health Checks**: Connection health and system status

### Security Considerations

- **Authentication**: Connection-level authentication
- **Authorization**: Channel and message access control
- **Input Validation**: Message sanitization and validation
- **Rate Limiting**: Message rate limiting per connection

### Scaling Considerations

- **Load Balancing**: Connection distribution across instances
- **Shared State**: Redis-based connection state sharing
- **Horizontal Scaling**: Stateless connection handling
- **Resource Management**: Automatic scaling based on load