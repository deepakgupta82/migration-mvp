"""
Document Processing Service
Port: 8004
Responsibilities: Document upload handling, MarkItDown conversion, MinIO storage
"""

import os
import sys
import logging
import contextvars
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from app.routers.documents import router as documents_router

"""Logging configuration
Ensures every record has a correlation_id attribute so formatters never fail,
and installs a global filter that injects the current correlation id from contextvars.
"""
# Correlation ID context
correlation_id_ctx = contextvars.ContextVar("correlation_id", default=None)

# Ensure every LogRecord always has correlation_id to avoid KeyError at startup
_orig_factory = logging.getLogRecordFactory()

def _record_factory(*args, **kwargs):
    record = _orig_factory(*args, **kwargs)
    # Provide a default so format strings with %(correlation_id)s never break
    if not hasattr(record, "correlation_id"):
        record.correlation_id = "-"
    return record

logging.setLogRecordFactory(_record_factory)

# Configure root logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [document-service] [corr_id=%(correlation_id)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/document-service.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

# Global filter to update correlation_id from contextvar on every record
class CorrelationIdLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            cid = correlation_id_ctx.get()
        except Exception:
            cid = None
        record.correlation_id = cid or getattr(record, 'correlation_id', '-') or '-'
        return True

# Attach filter once to all existing handlers
for handler in logging.getLogger().handlers:
    handler.addFilter(CorrelationIdLogFilter())

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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],
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
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8004,
        reload=False,
        log_level="info"
    )
