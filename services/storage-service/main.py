#!/usr/bin/env python3
"""
Storage Service - Complete ObjectStorage microservice
Extracted from backend monolith for MinIO/S3 file operations


Port: 8010
Purpose: Centralized object storage management
Features: Multi-provider support, project-based organization, comprehensive file operations
"""

import logging
import sys
import os
import uuid
import contextvars
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.storage import router as storage_router
from app.core.config_client import cfg_get

# Context vars for correlation and request IDs
correlation_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("correlation_id", default="-")
request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

# Configure logging with correlation/request id support
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [corr_id=%(correlation_id)s req_id=%(request_id)s] - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('storage-service.log')
    ]
)

class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Inject correlation and request IDs into all log records
        try:
            record.correlation_id = correlation_id_ctx.get()
        except Exception:
            record.correlation_id = "-"
        try:
            record.request_id = request_id_ctx.get()
        except Exception:
            record.request_id = "-"
        return True

# Attach filter to all existing handlers
_root_logger = logging.getLogger()
_context_filter = ContextFilter()
for _handler in _root_logger.handlers:
    _handler.addFilter(_context_filter)

logger = logging.getLogger("storage-service")

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

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Storage Service starting up...")
    logger.info("Initializing storage processor...")
    
    try:
        # Test storage processor initialization
        from app.core.storage_processor import StorageProcessor
        processor = StorageProcessor()
        health = await processor.health_check()
        
        if health["status"] == "healthy":
            logger.info(f"Storage service ready - Provider: {health['provider']}")
            if health.get("bucket"):
                logger.info(f"Bucket: {health['bucket']}")
            if health.get("local_root"):
                logger.info(f"Local root: {health['local_root']}")
        else:
            logger.error(f"Storage service unhealthy: {health.get('error', 'Unknown error')}")
            
    except Exception as e:
        logger.error(f"Storage service initialization failed: {e}")
    
    yield
    
    # Shutdown
    logger.info("Storage Service shutting down...")

# Create FastAPI application
app = FastAPI(
    title="Nagarro Ascent - Storage Service",
    description="Centralized object storage microservice for file operations via MinIO/S3",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS middleware (origins from centralized config, fallback to common defaults)
cors_origins = cfg_get(["backend", "cors_origins"], []) or [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Correlation-ID", "X-Request-ID"],
)

# Correlation/Request ID middleware
@app.middleware("http")
async def correlation_middleware(request, call_next):
    # Fetch or create correlation id
    corr_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    req_id = str(uuid.uuid4())

    # Set context vars for logging
    token_corr = correlation_id_ctx.set(corr_id)
    token_req = request_id_ctx.set(req_id)

    # Process request
    try:
        response = await call_next(request)
    finally:
        # Ensure context is cleared for next request
        try:
            correlation_id_ctx.reset(token_corr)
            request_id_ctx.reset(token_req)
        except Exception:
            pass

    # Propagate IDs in response headers
    response.headers["X-Correlation-ID"] = corr_id
    response.headers["X-Request-ID"] = req_id
    # Helpful for browsers to access these headers
    response.headers.setdefault("Access-Control-Expose-Headers", "X-Correlation-ID, X-Request-ID")

    return response

# Include routers
app.include_router(storage_router, prefix="/api/storage")

# Health check endpoint at root level
@app.get("/health")
async def health_check():
    """Root level health check"""
    return {
        "service": "storage-service",
        "status": "healthy",
        "port": 8010,
        "version": "1.0.0"
    }

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with service information"""
    return {
        "service": "Nagarro Ascent Storage Service",
        "version": "1.0.0",
        "description": "Centralized object storage microservice",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "api": "/api/storage"
        },
        "features": [
            "Multi-provider storage support (MinIO/S3/Filesystem)",
            "Project-based file organization", 
            "File upload/download/listing/deletion",
            "Storage statistics and monitoring",
            "Background cleanup tasks",
            "Debug endpoints for troubleshooting"
        ]
    }

if __name__ == "__main__":
    import uvicorn
    
    logger.info("Starting Storage Service on port 8010...")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8010)),
        reload=False,
        log_level="info"
    )
