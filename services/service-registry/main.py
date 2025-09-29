"""
Service Registry & Distributed Health Monitoring Service

This service provides:
1. Service discovery and registration
2. Distributed health monitoring
3. Service status aggregation
4. Real-time health notifications
"""

import asyncio
import json
import logging
import time
import random
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager

import aiohttp
import docker
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Ensure uvicorn loggers use same handlers/formatters
_root_logger = logging.getLogger()
for _lname in ("uvicorn", "uvicorn.error", "uvicorn.access"):
    _uvl = logging.getLogger(_lname)
    _uvl.setLevel(logging.INFO)
    for _h in list(_uvl.handlers):
        _uvl.removeHandler(_h)
    for _h in _root_logger.handlers:
        _uvl.addHandler(_h)
    _uvl.propagate = False

@dataclass
class ServiceInfo:
    """Service registration information"""
    name: str
    host: str
    port: int
    health_endpoint: str
    status: str = "unknown"
    last_check: Optional[datetime] = None
    response_time: Optional[float] = None
    version: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class ServiceRegistryManager:
    """Manages service registration and health monitoring"""
    
    def __init__(self):
        self.services: Dict[str, ServiceInfo] = {}
        self.docker_client = None
        self.websocket_connections: List[WebSocket] = []
        self._monitoring_task = None
        
    async def initialize(self):
        """Initialize the service registry"""
        try:
            self.docker_client = docker.from_env()
            logger.info("Docker client initialized successfully")
        except Exception as e:
            logger.warning(f"Could not initialize Docker client: {e}")
            
        # Register known services
        await self._register_known_services()
        
        # Start health monitoring
        self._monitoring_task = asyncio.create_task(self._health_monitoring_loop())
        
    async def _register_known_services(self):
        """Register known platform services"""
        known_services = [
            ServiceInfo("backend", "localhost", 8000, "/health"),
            ServiceInfo("project-service", "localhost", 8002, "/health"),
            ServiceInfo("document-service", "localhost", 8003, "/health"),
            ServiceInfo("stats-service", "localhost", 8004, "/health"),
            ServiceInfo("vector-service", "localhost", 8005, "/health"),
            ServiceInfo("graph-service", "localhost", 8006, "/health"),
            ServiceInfo("llm-service", "localhost", 8007, "/health"),
            ServiceInfo("ai-agent-service", "localhost", 8008, "/health"),
            ServiceInfo("websocket-service", "localhost", 8009, "/health"),
            ServiceInfo("storage-service", "localhost", 8010, "/health"),
            ServiceInfo("service-registry", "localhost", 8011, "/health"),
            ServiceInfo("cloud-tools-service", "localhost", 8012, "/health"),
            ServiceInfo("analytics-service", "localhost", 8014, "/health"),
            ServiceInfo("security-service", "localhost", 8015, "/health"),
            ServiceInfo("collaboration-service", "localhost", 8016, "/health"),
            ServiceInfo("knowledge-service", "localhost", 8017, "/health"),
        ]
        
        for service in known_services:
            self.services[service.name] = service
            logger.info(f"Registered service: {service.name}")
    
    async def register_service(self, service_info: ServiceInfo) -> bool:
        """Register a new service"""
        try:
            self.services[service_info.name] = service_info
            logger.info(f"Service registered: {service_info.name} at {service_info.host}:{service_info.port}")
            
            # Perform initial health check
            await self._check_service_health(service_info.name)
            
            # Notify WebSocket clients
            await self._broadcast_service_update(service_info.name, "registered")
            
            return True
        except Exception as e:
            logger.error(f"Failed to register service {service_info.name}: {e}")
            return False
    
    async def unregister_service(self, service_name: str) -> bool:
        """Unregister a service"""
        if service_name in self.services:
            del self.services[service_name]
            logger.info(f"Service unregistered: {service_name}")
            
            # Notify WebSocket clients
            await self._broadcast_service_update(service_name, "unregistered")
            return True
        return False
    
    async def _check_service_health(self, service_name: str) -> bool:
        """Check health of a specific service"""
        if service_name not in self.services:
            return False
            
        service = self.services[service_name]
        start_time = time.time()
        
        try:
            health_url = f"http://{service.host}:{service.port}{service.health_endpoint}"
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.get(health_url) as response:
                    response_time = time.time() - start_time
                    
                    if response.status == 200:
                        service.status = "healthy"
                        service.response_time = response_time
                        service.last_check = datetime.now()
                        
                        # Try to get additional info from response
                        try:
                            data = await response.json()
                            if isinstance(data, dict):
                                service.version = data.get("version")
                                service.metadata.update(data.get("metadata", {}))
                        except:
                            pass
                            
                        return True
                    else:
                        service.status = "unhealthy"
                        service.response_time = response_time
                        service.last_check = datetime.now()
                        return False
                        
        except asyncio.TimeoutError:
            service.status = "timeout"
            service.response_time = time.time() - start_time
            service.last_check = datetime.now()
            return False
        except Exception as e:
            service.status = "error"
            service.response_time = time.time() - start_time
            service.last_check = datetime.now()
            service.metadata["last_error"] = str(e)
            logger.error(f"Health check failed for {service_name}: {e}")
            return False
    
    async def _health_monitoring_loop(self):
        """Continuous health monitoring loop"""
        while True:
            try:
                # Check all registered services
                health_tasks = []
                for service_name in list(self.services.keys()):
                    health_tasks.append(self._check_service_health(service_name))
                
                # Execute health checks concurrently
                results = await asyncio.gather(*health_tasks, return_exceptions=True)
                
                # Process results and broadcast updates
                for i, (service_name, result) in enumerate(zip(self.services.keys(), results)):
                    if isinstance(result, Exception):
                        logger.error(f"Health check exception for {service_name}: {result}")
                    else:
                        # Broadcast status update if status changed
                        service = self.services[service_name]
                        await self._broadcast_health_update(service_name, service.status)
                
                # Check Docker containers if available
                if self.docker_client:
                    await self._check_docker_containers()
                
                # Wait before next check with jitter; default ~120s
                base_interval = int(os.getenv("REGISTRY_HEALTH_INTERVAL_SEC", "120"))
                jitter = random.randint(-10, 10)
                await asyncio.sleep(max(30, base_interval + jitter))
                
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    async def _check_docker_containers(self):
        """Check Docker container status"""
        try:
            containers = self.docker_client.containers.list(all=True)
            
            for container in containers:
                container_name = container.name
                if any(service in container_name.lower() for service in self.services.keys()):
                    # Update service metadata with container info
                    for service_name, service in self.services.items():
                        if service_name.lower() in container_name.lower():
                            service.metadata.update({
                                "container_status": container.status,
                                "container_id": container.short_id,
                                "container_image": container.image.tags[0] if container.image.tags else "unknown"
                            })
                            break
                            
        except Exception as e:
            logger.error(f"Error checking Docker containers: {e}")
    
    async def _broadcast_service_update(self, service_name: str, action: str):
        """Broadcast service registration/unregistration updates"""
        message = {
            "type": "service_update",
            "service_name": service_name,
            "action": action,
            "timestamp": datetime.now().isoformat()
        }
        await self._broadcast_message(message)
    
    async def _broadcast_health_update(self, service_name: str, status: str):
        """Broadcast health status updates"""
        message = {
            "type": "health_update",
            "service_name": service_name,
            "status": status,
            "timestamp": datetime.now().isoformat()
        }
        await self._broadcast_message(message)
    
    async def _broadcast_message(self, message: dict):
        """Broadcast message to all WebSocket connections"""
        if not self.websocket_connections:
            return
            
        disconnected = []
        for websocket in self.websocket_connections:
            try:
                await websocket.send_text(json.dumps(message))
            except Exception:
                disconnected.append(websocket)
        
        # Remove disconnected clients
        for ws in disconnected:
            if ws in self.websocket_connections:
                self.websocket_connections.remove(ws)
    
    def get_service_status(self, service_name: Optional[str] = None) -> Dict[str, Any]:
        """Get status of services"""
        if service_name:
            if service_name in self.services:
                service = self.services[service_name]
                return {
                    "service": asdict(service),
                    "timestamp": datetime.now().isoformat()
                }
            else:
                raise HTTPException(status_code=404, message=f"Service {service_name} not found")
        
        # Return all services
        return {
            "services": {name: asdict(service) for name, service in self.services.items()},
            "summary": self._get_health_summary(),
            "timestamp": datetime.now().isoformat()
        }
    
    def _get_health_summary(self) -> Dict[str, Any]:
        """Get health summary of all services"""
        total = len(self.services)
        healthy = sum(1 for s in self.services.values() if s.status == "healthy")
        unhealthy = sum(1 for s in self.services.values() if s.status == "unhealthy")
        error = sum(1 for s in self.services.values() if s.status == "error")
        timeout = sum(1 for s in self.services.values() if s.status == "timeout")
        unknown = sum(1 for s in self.services.values() if s.status == "unknown")
        
        return {
            "total": total,
            "healthy": healthy,
            "unhealthy": unhealthy,
            "error": error,
            "timeout": timeout,
            "unknown": unknown,
            "health_percentage": (healthy / total * 100) if total > 0 else 0
        }
    
    async def add_websocket_connection(self, websocket: WebSocket):
        """Add WebSocket connection for real-time updates"""
        self.websocket_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total connections: {len(self.websocket_connections)}")
    
    async def remove_websocket_connection(self, websocket: WebSocket):
        """Remove WebSocket connection"""
        if websocket in self.websocket_connections:
            self.websocket_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Total connections: {len(self.websocket_connections)}")
    
    async def cleanup(self):
        """Cleanup resources"""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        
        if self.docker_client:
            self.docker_client.close()

# Service start time for uptime calculation
SERVICE_START_TIME = time.time()

# Global service registry instance
service_registry = ServiceRegistryManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    await service_registry.initialize()
    logger.info("Service Registry started successfully")
    
    yield
    
    # Shutdown
    await service_registry.cleanup()
    logger.info("Service Registry shut down successfully")

# FastAPI app
app = FastAPI(
    title="Service Registry & Health Monitoring",
    description="Distributed service discovery and health monitoring for Nagarro Ascent Platform",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Trailing slash redirect middleware (308 Permanent Redirect)
@app.middleware("http")
async def trailing_slash_redirect_middleware(request, call_next):
    # Skip redirect for health check endpoints and non-GET requests
    if request.method != "GET" or request.url.path in ["/livez", "/healthz", "/health"]:
        return await call_next(request)

    # Check if path ends with trailing slash (except root path)
    if request.url.path.endswith("/") and request.url.path != "/":
        # Remove trailing slash for canonical path
        canonical_path = request.url.path.rstrip("/")
        query_string = str(request.url.query) if request.url.query else ""

        # Build redirect URL
        redirect_url = f"{request.url.scheme}://{request.url.host}:{request.url.port}{canonical_path}"
        if query_string:
            redirect_url += f"?{query_string}"

        # Return 308 Permanent Redirect
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=redirect_url, status_code=308)

    return await call_next(request)

# Pydantic models
class ServiceRegistration(BaseModel):
    name: str
    host: str
    port: int
    health_endpoint: str
    version: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str = "2.0.0"
    service: str = "service-registry"

async def check_dependencies():
    """Check service dependencies for readiness"""
    dependencies = {}

    # Check PostgreSQL if used
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            database=os.getenv("POSTGRES_DB", "migration_platform"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", "postgres")
        )
        conn.close()
        dependencies["postgresql"] = "healthy"
    except Exception:
        dependencies["postgresql"] = "unhealthy"

    # Check Redis if used
    try:
        import redis
        redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            decode_responses=True
        )
        redis_client.ping()
        dependencies["redis"] = "healthy"
    except Exception:
        dependencies["redis"] = "unhealthy"

    # Check Docker connectivity
    try:
        if service_registry.docker_client:
            service_registry.docker_client.ping()
            dependencies["docker"] = "healthy"
        else:
            dependencies["docker"] = "not_configured"
    except Exception:
        dependencies["docker"] = "unhealthy"

    return dependencies

# API Endpoints
@app.get("/livez")
async def liveness_check():
    """Liveness probe - checks if service is running"""
    return {
        "status": "healthy",
        "service": "service-registry",
        "uptime": int(time.time() - SERVICE_START_TIME),
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0"
    }

@app.get("/healthz")
async def readiness_check():
    """Readiness probe - checks if service is ready to accept traffic"""
    dependencies = await check_dependencies()

    # Determine overall status
    overall_status = "healthy" if all(status == "healthy" for status in dependencies.values()) else "unhealthy"

    return {
        "status": overall_status,
        "service": "service-registry",
        "uptime": int(time.time() - SERVICE_START_TIME),
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0",
        "dependencies": dependencies
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat()
    )

@app.post("/services/register")
async def register_service(service: ServiceRegistration):
    """Register a new service"""
    service_info = ServiceInfo(
        name=service.name,
        host=service.host,
        port=service.port,
        health_endpoint=service.health_endpoint,
        version=service.version,
        metadata=service.metadata or {}
    )
    
    success = await service_registry.register_service(service_info)
    if success:
        return {"message": f"Service {service.name} registered successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to register service")

@app.delete("/services/{service_name}")
async def unregister_service(service_name: str):
    """Unregister a service"""
    success = await service_registry.unregister_service(service_name)
    if success:
        return {"message": f"Service {service_name} unregistered successfully"}
    else:
        raise HTTPException(status_code=404, detail="Service not found")

@app.get("/services")
async def get_all_services():
    """Get status of all services"""
    return service_registry.get_service_status()

@app.get("/services/{service_name}")
async def get_service_status(service_name: str):
    """Get status of a specific service"""
    return service_registry.get_service_status(service_name)

@app.get("/health/summary")
async def get_health_summary():
    """Get health summary of all services"""
    status = service_registry.get_service_status()
    return {
        "summary": status["summary"],
        "timestamp": status["timestamp"]
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time health updates"""
    await websocket.accept()
    await service_registry.add_websocket_connection(websocket)
    
    try:
        # Send initial status
        initial_status = service_registry.get_service_status()
        await websocket.send_text(json.dumps({
            "type": "initial_status",
            "data": initial_status
        }))
        
        # Keep connection alive
        while True:
            try:
                # Wait for ping/pong to keep connection alive
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                # Send ping
                await websocket.send_text(json.dumps({"type": "ping"}))
            except WebSocketDisconnect:
                break
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await service_registry.remove_websocket_connection(websocket)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8011,
        reload=True,
        log_level="info"
    )