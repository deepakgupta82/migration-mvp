"""
Project Service
Port: 8002
Responsibilities: Project management, deliverables, generation requests
"""

import os
import sys
import logging
import contextvars
import json
import time
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from sqlalchemy import text
from app.repositories.dependency_container import get_repository_container

"""Logging configuration with JSON format for Loki integration
Fields: ts, level, service, corr_id, project_id, msg
"""
# Correlation ID and Project ID contexts
correlation_id_ctx = contextvars.ContextVar("correlation_id", default=None)
project_id_ctx = contextvars.ContextVar("project_id", default=None)

class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    def format(self, record):
        log_data = {
            "ts": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "service": "project-service",
            "corr_id": getattr(record, 'correlation_id', '-') or '-',
            "project_id": getattr(record, 'project_id', '-') or '-',
            "msg": record.getMessage()
        }
        return json.dumps(log_data)

class SafeFormatter(logging.Formatter):
    """Safe text formatter for console output"""
    def format(self, record):
        if not hasattr(record, "correlation_id"):
            record.correlation_id = "-"
        if not hasattr(record, "project_id"):
            record.project_id = "-"
        return super().format(record)

# Ensure every LogRecord always has required attributes
_orig_factory = logging.getLogRecordFactory()

def _record_factory(*args, **kwargs):
    record = _orig_factory(*args, **kwargs)
    if not hasattr(record, "correlation_id"):
        record.correlation_id = "-"
    if not hasattr(record, "project_id"):
        record.project_id = "-"
    return record

logging.setLogRecordFactory(_record_factory)

# Global filter to update context variables on every record
class ContextLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            cid = correlation_id_ctx.get()
        except Exception:
            cid = None
        try:
            pid = project_id_ctx.get()
        except Exception:
            pid = None

        record.correlation_id = cid or getattr(record, 'correlation_id', '-') or '-'
        record.project_id = pid or getattr(record, 'project_id', '-') or '-'
        return True

# Configure logging with JSON format for files and text for console
os.makedirs("logs", exist_ok=True)

# Create formatters
json_formatter = JSONFormatter()
text_formatter = SafeFormatter(
    '%(asctime)s %(levelname)s [project-service] [corr_id=%(correlation_id)s] [project_id=%(project_id)s] %(message)s'
)

# Create handlers
file_handler = logging.FileHandler("logs/project-service.log", encoding="utf-8")
file_handler.setFormatter(json_formatter)
file_handler.addFilter(ContextLogFilter())

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(text_formatter)
console_handler.addFilter(ContextLogFilter())

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

# Ensure uvicorn loggers use the same handlers/formatters
for lname in ("uvicorn", "uvicorn.error", "uvicorn.access"):
    uv_logger = logging.getLogger(lname)
    uv_logger.setLevel(logging.INFO)
    # Clear default handlers if any to avoid duplicate formats
    for h in list(uv_logger.handlers):
        uv_logger.removeHandler(h)
    # Attach our handlers
    uv_logger.addHandler(file_handler)
    uv_logger.addHandler(console_handler)
    uv_logger.propagate = False

logger = logging.getLogger("project-service")

# Service start time for uptime calculation
SERVICE_START_TIME = time.time()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Modern FastAPI lifespan handler replacing deprecated @app.on_event"""
    # Startup
    logger.info("=== Project Service Starting ===")

    # Check required directories
    os.makedirs("logs", exist_ok=True)

    # Test critical imports and system dependencies
    logger.info("Testing critical dependencies...")
    try:
        # Test database connection
        try:
            from database import SessionLocal
            session = SessionLocal()
            # Test the connection
            session.execute(text("SELECT 1"))
            session.close()
            logger.info("✓ Database connection successful")
        except Exception as e:
            logger.error(f"✗ Database connection failed: {e}")

        # Test repository container
        try:
            container = get_repository_container()
            logger.info("✓ Repository container initialized")
        except Exception as e:
            logger.error(f"✗ Repository container failed: {e}")

    except Exception as e:
        logger.error(f"Dependency check failed: {e}")
        # Don't fail startup for import issues, let service run

    logger.info("Project Service startup complete")

    yield  # Service runs here

    # Shutdown
    logger.info("Project Service shutting down...")

# Create FastAPI app with lifespan
app = FastAPI(
    title="Project Service",
    description="Handles project management, deliverables, and generation requests",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS middleware
origins = ["http://localhost:3000", "http://localhost:8000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Correlation ID middleware
@app.middleware("http")
async def correlation_id_middleware(request, call_next):
    corr_id = request.headers.get("X-Correlation-ID")
    if not corr_id:
        import uuid
        corr_id = str(uuid.uuid4())

    token = correlation_id_ctx.set(corr_id)
    try:
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = corr_id
        return response
    finally:
        correlation_id_ctx.reset(token)

# Include routers
from app.routers.projects import router as projects_router
from app.routers.deliverables import router as deliverables_router
from app.routers.generation_requests import router as generation_requests_router
from app.routers.templates import router as templates_router

app.include_router(projects_router, prefix="/api/projects")
app.include_router(deliverables_router, prefix="/api/deliverables")
app.include_router(generation_requests_router, prefix="/api/generation-requests")
app.include_router(templates_router, prefix="/api/templates")

@app.get("/livez")
async def liveness_check():
    """Liveness probe - checks if service is running"""
    return {
        "status": "healthy",
        "service": "project-service",
        "uptime": int(time.time() - SERVICE_START_TIME),
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

@app.get("/healthz")
async def readiness_check():
    """Readiness probe - checks if service is ready to accept traffic"""
    # Check database connectivity
    try:
        from database import SessionLocal
        session = SessionLocal()
        session.execute(text("SELECT 1"))
        session.close()
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"

    # Determine overall status
    overall_status = "healthy" if db_status == "healthy" else "unhealthy"

    return {
        "status": overall_status,
        "service": "project-service",
        "uptime": int(time.time() - SERVICE_START_TIME),
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "dependencies": {
            "database": db_status
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint - backward compatibility alias to readiness"""
    return await readiness_check()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8002)),
        reload=True,
        log_level="info"
    )
