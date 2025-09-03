"""
Vector Search Service (Weaviate-backed)
Port: 8005
Responsibilities: Embedding generation, similarity search, and Weaviate operations
"""

import os
import sys
import logging
import contextvars
import time
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from app.routers.vectors import router as vectors_router
from app.core.correlation import correlation_id_ctx as shared_correlation_ctx

# Configure logging
# Correlation ID context
correlation_id_ctx = contextvars.ContextVar("correlation_id", default=None)

# Ensure every LogRecord always has correlation_id to avoid KeyError at startup
_orig_factory = logging.getLogRecordFactory()
def _record_factory(*args, **kwargs):
    record = _orig_factory(*args, **kwargs)
    if not hasattr(record, "correlation_id"):
        record.correlation_id = "-"
    return record
logging.setLogRecordFactory(_record_factory)

os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [vector-service] [corr_id=%(correlation_id)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/vector-service.log", encoding="utf-8"),
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

# Ensure uvicorn loggers use the same handlers/formatters
root_logger = logging.getLogger()
for lname in ("uvicorn", "uvicorn.error", "uvicorn.access"):
    uv_logger = logging.getLogger(lname)
    uv_logger.setLevel(logging.INFO)
    for h in list(uv_logger.handlers):
        uv_logger.removeHandler(h)
    for h in root_logger.handlers:
        uv_logger.addHandler(h)
    uv_logger.propagate = False

logger = logging.getLogger("vector-service")

# Service start time for uptime calculation
SERVICE_START_TIME = time.time()

# Create FastAPI app
app = FastAPI(
    title="Vector Search Service",
    description="Handles vector embeddings, Weaviate operations, and similarity search",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
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

# Include routers
app.include_router(vectors_router, prefix="/api/vectors")

async def check_dependencies():
    """Check service dependencies for readiness"""
    dependencies = {}

    # Check Weaviate
    try:
        import weaviate
        client = weaviate.Client(
            url=os.getenv("WEAVIATE_URL", "http://localhost:8080"),
            timeout_config=(5, 15)
        )
        # Simple connectivity check
        client.meta.get()
        dependencies["weaviate"] = "healthy"
    except Exception:
        dependencies["weaviate"] = "unhealthy"

    # Check Redis
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

    # Check sentence-transformers (optional)
    try:
        import sentence_transformers
        dependencies["sentence_transformers"] = "healthy"
    except Exception:
        dependencies["sentence_transformers"] = "unhealthy"

    return dependencies

@app.get("/livez")
async def liveness_check():
    """Liveness probe - checks if service is running"""
    return {
        "status": "healthy",
        "service": "vector-service",
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
        "service": "vector-service",
        "uptime": int(time.time() - SERVICE_START_TIME),
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "dependencies": dependencies
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test Weaviate connection
        from app.core.vector_processor import VectorProcessor
        processor = VectorProcessor()
        health = await processor.health_check()
        
        return {
            "service": "vector-search",
            "status": "healthy",
            "port": 8005,
            "version": "1.0.0",
            "weaviate": "connected",
            **health,
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "service": "vector-search",
            "status": "unhealthy",
            "port": 8005,
            "version": "1.0.0",
            "error": str(e)
        }

@app.on_event("startup")
async def startup_event():
    logger.info("Vector Search Service starting on port 8005...")
    
    # Create logs directory
    os.makedirs("logs", exist_ok=True)
    
    # Test dependencies
    try:
        import sentence_transformers
        import redis
        import weaviate
        logger.info("All dependencies verified")
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        raise
    
    # Start background model loading for improved response time
    try:
        from app.core.vector_processor import start_background_model_loading
        start_background_model_loading()
        logger.info("Background model loading initiated")
    except Exception as e:
        logger.warning(f"Failed to start background model loading: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Vector Search Service shutting down...")
    
    # Cleanup connections
    try:
        from app.core.vector_processor import get_vector_processor
        processor = get_vector_processor()
        processor.cleanup()
        logger.info("Connections cleaned up successfully")
    except Exception as e:
        logger.warning(f"Cleanup failed during shutdown: {e}")

# Correlation ID middleware and logging filter
@app.middleware("http")
async def correlation_id_middleware(request, call_next):
    corr_id = request.headers.get("X-Correlation-ID") or correlation_id_ctx.get()
    if not corr_id:
        corr_id = None
    token = None
    try:
        token = correlation_id_ctx.set(corr_id)
        try:
            shared_correlation_ctx.set(corr_id)
        except Exception:
            pass
    except Exception:
        pass

    class CorrelationIdLogFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            try:
                cid = correlation_id_ctx.get()
            except Exception:
                cid = None
            record.correlation_id = cid or "-"
            return True

    for handler in logging.getLogger().handlers:
        handler.addFilter(CorrelationIdLogFilter())

    response = await call_next(request)
    if corr_id:
        response.headers["X-Correlation-ID"] = corr_id
    if token is not None:
        try:
            correlation_id_ctx.reset(token)
        except Exception:
            pass
    return response

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8005)),
        reload=False,
        log_level="info",
    )
