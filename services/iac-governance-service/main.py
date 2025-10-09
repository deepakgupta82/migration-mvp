"""
IAC Governance Service
Port: 8021
Responsibilities: Infrastructure-as-Code compliance, policy enforcement, security scanning
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
from sqlalchemy import text
import uvicorn

# Load environment variables from .env file
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

# Add parent directory to path for shared imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from app.core.config import config
from app.core.database import engine
from app.models import Base

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
logger = logging.getLogger("iac-governance-service")
logger.setLevel(getattr(logging, config.LOG_LEVEL))

if config.ENABLE_JSON_LOGS:
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
else:
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    logger.info(f"{config.SERVICE_NAME} starting on port {config.SERVICE_PORT}")
    
    # Test database connection
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            logger.info("Database connection successful")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        # Don't fail startup - allow service to run in degraded mode
    
    yield
    
    # Shutdown
    logger.info(f"{config.SERVICE_NAME} shutting down")
    engine.dispose()


# Create FastAPI application
app = FastAPI(
    title="IAC Governance Service",
    description="Infrastructure-as-Code compliance and policy enforcement",
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
        "description": "Infrastructure-as-Code compliance and policy enforcement",
        "docs": "/docs",
        "health": "/health",
    }


# Include routers (will be added as we build them)
# from app.routers import policies_router, scans_router
# app.include_router(policies_router)
# app.include_router(scans_router)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=config.SERVICE_PORT,
        reload=True,
    )
