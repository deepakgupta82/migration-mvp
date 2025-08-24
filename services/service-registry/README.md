# Service Registry & Distributed Health Monitoring

This service provides centralized service discovery and distributed health monitoring for the Nagarro Ascent Platform.

## Features

- **Service Discovery**: Automatic registration and discovery of platform services
- **Health Monitoring**: Continuous health checks with configurable intervals
- **Real-time Updates**: WebSocket-based real-time status notifications
- **Docker Integration**: Container status monitoring via Docker API
- **RESTful API**: Complete REST API for service management
- **Health Aggregation**: Service health summary and analytics

## API Endpoints

### Health Check
- `GET /health` - Service health status

### Service Management
- `POST /services/register` - Register a new service
- `DELETE /services/{service_name}` - Unregister a service
- `GET /services` - Get all services status
- `GET /services/{service_name}` - Get specific service status
- `GET /health/summary` - Get health summary

### Real-time Updates
- `WebSocket /ws` - Real-time health and service updates

## Usage

### Starting the Service
```bash
python main.py
```

### Service Registration
```python
import requests

service_data = {
    "name": "my-service",
    "host": "localhost", 
    "port": 8080,
    "health_endpoint": "/health",
    "version": "1.0.0",
    "metadata": {"team": "platform"}
}

response = requests.post("http://localhost:8011/services/register", json=service_data)
```

### WebSocket Client
```javascript
const ws = new WebSocket('ws://localhost:8011/ws');

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('Received:', data);
};
```

## Configuration

The service automatically registers known platform services and monitors their health every 30 seconds.

## Docker Support

The service can monitor Docker container status for registered services, providing additional container metadata.

## Environment Variables

- `LOG_LEVEL`: Logging level (default: INFO)
- `HEALTH_CHECK_INTERVAL`: Health check interval in seconds (default: 30)
- `DOCKER_ENABLED`: Enable Docker integration (default: true)