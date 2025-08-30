"""
WebSocket Gateway Service
Port: 8009
Responsibilities: WebSocket connection management, real-time broadcasting, multi-channel communication
"""

import os
import sys
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uuid
import contextvars
import uvicorn
from app.routers.websocket import router as websocket_router
from app.core.websocket_gateway import WebSocketGateway

# Correlation ID context
correlation_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("correlation_id", default="-")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [websocket-service] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("websocket_service")

# Ensure uvicorn loggers use the same handlers/formatters
_root_logger = logging.getLogger()
for _lname in ("uvicorn", "uvicorn.error", "uvicorn.access"):
    _uv_logger = logging.getLogger(_lname)
    _uv_logger.setLevel(logging.INFO)
    for _h in list(_uv_logger.handlers):
        _uv_logger.removeHandler(_h)
    for _h in _root_logger.handlers:
        _uv_logger.addHandler(_h)
    _uv_logger.propagate = False

# Global gateway instance
gateway = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global gateway
    
    logger.info("WebSocket Gateway Service starting on port 8009...")
    
    try:
        # Initialize gateway
        gateway = WebSocketGateway()
        
        # Make gateway available to routes
        app.state.gateway = gateway
        
        logger.info("WebSocket Gateway Service ready")
        yield
        
    except Exception as e:
        logger.error(f"Failed to start WebSocket Gateway service: {e}")
        raise
    finally:
        logger.info("WebSocket Gateway Service shutting down...")
        
        # Cleanup all connections
        if gateway:
            await gateway.cleanup_stale_connections(0)  # Force cleanup all

def _generate_unique_id(route):
    """Ensure OpenAPI operationId uniqueness based on explicit name if present.
    Falls back to function name when name isn't set.
    Format: <route_name_or_fn>_<method>_<path>
    """
    try:
        method = sorted(route.methods)[0].lower() if getattr(route, "methods", None) else "get"
        path = (route.path_format or "/").strip("/").replace("/", "_") or "root"
        base = route.name or getattr(route.endpoint, "__name__", "endpoint")
        return f"{base}_{method}_{path}"
    except Exception:
        # Safe fallback
        return getattr(route.endpoint, "__name__", "endpoint")

# Create FastAPI app with lifespan management and deterministic unique IDs
app = FastAPI(
    title="WebSocket Gateway Service",
    description="WebSocket connection management and real-time broadcasting",
    version="1.0.0",
    lifespan=lifespan,
    generate_unique_id_function=_generate_unique_id,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Correlation-ID"],
)

# Correlation ID middleware to ensure echo/propagation
@app.middleware("http")
async def correlation_id_middleware(request, call_next):
    corr_id = request.headers.get("X-Correlation-ID")
    if not corr_id:
        try:
            corr_id = str(uuid.uuid4())
        except Exception:
            corr_id = "-"
    token = None
    try:
        token = correlation_id_ctx.set(corr_id)
    except Exception:
        pass
    try:
        response = await call_next(request)
    finally:
        if token is not None:
            try:
                correlation_id_ctx.reset(token)
            except Exception:
                pass
    if corr_id and corr_id != "-":
        response.headers["X-Correlation-ID"] = corr_id
        # Helpful for browsers
        response.headers.setdefault("Access-Control-Expose-Headers", "X-Correlation-ID")
    return response

# Include WebSocket router
app.include_router(websocket_router)

# Health check is provided by router at /health to avoid duplicate operation IDs

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8009)),
        reload=False,  # WebSocket services work better without reload
        log_level="info"
    )
