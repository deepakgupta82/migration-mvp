"""
Document Processing Service
Port: 8004
Responsibilities: Document upload handling, MarkItDown conversion, MinIO storage
"""

import os
import sys
import logging
import contextvars
import json
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from app.routers.documents import router as documents_router

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
            "service": "document-service",
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
    '%(asctime)s %(levelname)s [document-service] [corr_id=%(correlation_id)s] [project_id=%(project_id)s] %(message)s'
)

# Create handlers
file_handler = logging.FileHandler("logs/document-service.log", encoding="utf-8")
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

logger = logging.getLogger("document-service")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Modern FastAPI lifespan handler replacing deprecated @app.on_event"""
    # Startup
    logger.info("=== Document Service Starting ===")
    
    # Check required directories
    os.makedirs("logs", exist_ok=True)
    os.makedirs("temp", exist_ok=True)
    
    # Test critical imports
    logger.info("Testing critical dependencies...")
    try:
        # Test markitdown import
        try:
            import markitdown
            logger.info("✓ MarkItDown import successful")
        except ImportError as e:
            logger.warning(f"⚠ MarkItDown import failed: {e}")
            
        # Test PyMuPDF import
        try:
            import fitz  # PyMuPDF
            logger.info("✓ PyMuPDF (fitz) import successful")
        except ImportError as e:
            logger.warning(f"⚠ PyMuPDF import failed: {e}")
            
        # Test MinIO client
        try:
            from minio import Minio
            logger.info("✓ MinIO client import successful")
        except ImportError as e:
            logger.warning(f"⚠ MinIO client import failed: {e}")
            
        # Test Redis (if used)
        try:
            import redis
            logger.info("✓ Redis import successful")
        except ImportError as e:
            logger.info(f"ℹ Redis not available: {e}")
            
    except Exception as e:
        logger.error(f"Dependency check failed: {e}")
        # Don't fail startup for import issues, let service run
    
    logger.info("Document Service startup complete")
    
    yield  # Service runs here
    
    # Shutdown
    logger.info("Document Service shutting down...")

# Create FastAPI app with lifespan
app = FastAPI(
    title="Document Processing Service",
    description="Handles document conversion, processing, and storage operations",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS middleware
try:
    from app.core.config_client import cfg_get
    origins = cfg_get(["backend", "cors_origins"], ["http://localhost:3000", "http://localhost:8000"]) or ["http://localhost:3000", "http://localhost:8000"]
except Exception:
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
app.include_router(documents_router, prefix="/api/documents")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "service": "document-processing",
        "status": "healthy",
        "port": 8004,
        "version": "1.0.0"
    }

if __name__ == "__main__":
    cfg = _get_local_config_cached()
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", cfg.get('backend', {}).get('port', 8004))), reload=False)
'''
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8004,
        reload=False,
        log_level="info"
    ) '''
