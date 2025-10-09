"""
Cloud Orchestration Service
Port: 8020
Responsibilities: Multi-cloud migration orchestration, wave management, MCP-based migration execution
"""

import os
import sys
import logging
import json
import contextvars
from datetime import datetime
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Load environment variables from .env file
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

# Add parent directory to path for shared imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from app.core.config import config
from app.core.database import engine
from app.models import Base
from app.routers import waves_router

# Correlation ID context
correlation_id_ctx = contextvars.ContextVar("correlation_id", default=None)


class JSONFormatter(logging.Formatter):
    """JSON log formatter for Loki integration."""
    
    def format(self, record):
        log_data = {
            "ts": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "service": config.SERVICE_NAME,
            "corr_id": getattr(record, 'correlation_id', '-') or '-',
            "msg": record.getMessage()
        }
        return json.dumps(log_data)


# Configure logging
def setup_logging():
    """Configure structured logging."""
    handler = logging.StreamHandler()
    
    if config.ENABLE_JSON_LOGS:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
    
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL.upper()),
        handlers=[handler]
    )


setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan events."""
    # Startup
    logger.info(f"{config.SERVICE_NAME} starting on port {config.SERVICE_PORT}")
    
    # Verify database connection
    try:
        with engine.connect() as conn:
            logger.info("Database connection verified")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise
    
    # TODO: Register with service registry
    if config.REGISTER_WITH_REGISTRY:
        logger.info("Service registry registration skipped (not implemented yet)")
    
    yield
    
    # Shutdown
    logger.info(f"{config.SERVICE_NAME} shutting down")
    engine.dispose()


# Create FastAPI application
app = FastAPI(
    title="Cloud Orchestration Service",
    description="Multi-cloud migration orchestration and wave management",
    version=config.SERVICE_VERSION,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """Extract or generate correlation ID for distributed tracing."""
    correlation_id = request.headers.get("X-Correlation-ID") or request.headers.get("x-correlation-id")
    
    if not correlation_id:
        import uuid
        correlation_id = str(uuid.uuid4())
    
    correlation_id_ctx.set(correlation_id)
    
    response: Response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    
    return response


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Log all requests with correlation ID."""
    if config.ENABLE_REQUEST_LOGGING:
        correlation_id = correlation_id_ctx.get()
        logger.info(
            f"Request: {request.method} {request.url.path}",
            extra={"correlation_id": correlation_id}
        )
    
    response = await call_next(request)
    return response


# Health endpoint
@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "service": config.SERVICE_NAME,
        "status": "healthy",
        "port": config.SERVICE_PORT,
        "version": config.SERVICE_VERSION,
    }


# Root endpoint
@app.get("/")
async def root():
    """Service information."""
    return {
        "service": config.SERVICE_NAME,
        "version": config.SERVICE_VERSION,
        "description": "Multi-cloud migration orchestration and wave management",
        "docs": "/docs",
        "health": "/health",
    }


# Include routers
app.include_router(waves_router)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=config.SERVICE_PORT,
        reload=True,
        log_level=config.LOG_LEVEL.lower(),
    )
