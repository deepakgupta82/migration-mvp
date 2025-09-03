"""
Document Processing Service
Port: 8003
Responsibilities: Document upload handling, MarkItDown conversion, MinIO storage
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

logger = logging.getLogger("document-service")

# Service start time for uptime calculation
SERVICE_START_TIME = time.time()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Modern FastAPI lifespan handler replacing deprecated @app.on_event"""
    # Startup
    logger.info("=== Document Service Starting ===")
    
    # Check required directories
    os.makedirs("logs", exist_ok=True)
    os.makedirs("temp", exist_ok=True)
    
    # Test critical imports and system dependencies
    logger.info("Testing critical dependencies...")
    try:
        # Configure Tesseract OCR path explicitly for Windows
        tesseract_path = r"C:\Users\deepakgupta13\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
        tesseract_dir = r"C:\Users\deepakgupta13\AppData\Local\Programs\Tesseract-OCR"
        
        if os.path.exists(tesseract_path):
            # Set environment variable for unstructured library
            os.environ['TESSERACT_CMD'] = tesseract_path
            
            # CRITICAL: Add Tesseract directory to PATH for subprocess calls
            current_path = os.environ.get('PATH', '')
            if tesseract_dir not in current_path:
                os.environ['PATH'] = f"{tesseract_dir};{current_path}"
                logger.info(f"✓ Tesseract directory added to PATH: {tesseract_dir}")
            
            logger.info(f"✓ Tesseract path configured: {tesseract_path}")
            
            # Also configure pytesseract if available
            try:
                import pytesseract
                pytesseract.pytesseract.tesseract_cmd = tesseract_path
                logger.info("✓ pytesseract path configured")
            except ImportError:
                logger.info("ℹ pytesseract not available (optional)")
        else:
            logger.warning(f"⚠ Tesseract not found at expected path: {tesseract_path}")
        
        # Test Tesseract OCR availability
        try:
            import shutil
            import subprocess
            tesseract_cmd = shutil.which("tesseract") or tesseract_path
            if os.path.exists(tesseract_cmd):
                # Verify Tesseract is working
                result = subprocess.run([tesseract_cmd, "--version"], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    version_info = result.stdout.split('\n')[0] if result.stdout else "unknown version"
                    logger.info(f"✓ Tesseract OCR available: {version_info} at {tesseract_cmd}")
                else:
                    logger.error(f"✗ Tesseract found but not working: {result.stderr}")
            else:
                logger.error("✗ Tesseract OCR not found - document processing may fail")
                logger.error("   Install Tesseract OCR: https://github.com/UB-Mannheim/tesseract/wiki")
        except Exception as e:
            logger.error(f"✗ Tesseract validation failed: {e}")
            
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
    
    # Initialize table model optimization to reduce 2-minute loading delay
    try:
        from app.core.table_model_manager import init_table_model_optimization
        init_table_model_optimization()
        logger.info("✓ Table model optimization initialized")
    except Exception as e:
        logger.warning(f"⚠ Table model optimization failed: {e}")
    
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

# Include routers with both prefixed and non-prefixed versions for backward compatibility
app.include_router(documents_router, prefix="/api/documents")
app.include_router(documents_router)  # Backward compatibility - no prefix

async def check_dependencies():
    """Check service dependencies for readiness"""
    dependencies = {}

    # Check MinIO
    try:
        from minio import Minio
        minio_client = Minio(
            os.getenv("MINIO_ENDPOINT", "localhost:9000"),
            access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
            secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
            secure=False
        )
        # Simple bucket exists check
        minio_client.bucket_exists("documents")
        dependencies["minio"] = "healthy"
    except Exception as e:
        dependencies["minio"] = "unhealthy"

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

    return dependencies

@app.get("/livez")
async def liveness_check():
    """Liveness probe - checks if service is running"""
    return {
        "status": "healthy",
        "service": "document-service",
        "uptime": int(time.time() - SERVICE_START_TIME),
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

@app.get("/healthz")
async def readiness_check():
    """Readiness probe - checks if service is ready to accept traffic"""
    dependencies = await check_dependencies()

    # Determine overall status
    overall_status = "healthy" if all(status == "healthy" for status in dependencies.values()) else "unhealthy"

    return {
        "status": overall_status,
        "service": "document-service",
        "uptime": int(time.time() - SERVICE_START_TIME),
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "dependencies": dependencies
    }

@app.get("/health")
async def health_check():
    """Health check endpoint - backward compatibility alias to readiness"""
    return await readiness_check()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8003)),
        reload=False,
        log_level="info"
    )
