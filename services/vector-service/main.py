"""
Vector Search Service
Port: 8005
Responsibilities: ChromaDB operations, embedding generation, similarity search
"""

import os
import sys
import logging
import contextvars

# Add the parent directory to sys.path so we can import from the main app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

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

logger = logging.getLogger("vector-service")

# Create FastAPI app
app = FastAPI(
    title="Vector Search Service",
    description="Handles vector embeddings, ChromaDB operations, and similarity search",
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

# Include routers
app.include_router(vectors_router, prefix="/api/vectors")

# Health check endpoint at root level
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "service": "vector-search",
        "status": "healthy",
        "port": 8005,
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test ChromaDB connection
        from app.core.vector_processor import VectorProcessor
        processor = VectorProcessor()
        await processor.health_check()
        
        return {
            "service": "vector-search",
            "status": "healthy",
            "port": 8005,
            "version": "1.0.0",
            "chromadb": "connected"
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
    
    # Verify ChromaDB path
    try:
        from app.core.config_client import cfg_get
        chroma_path = cfg_get(["vector_service", "chroma_db_path"], os.getenv("CHROMA_DB_PATH", "../../data/chroma_db"))
    except Exception:
        chroma_path = os.getenv("CHROMA_DB_PATH", "../../data/chroma_db")
    abs_chroma_path = os.path.abspath(chroma_path)
    
    if not os.path.exists(abs_chroma_path):
        logger.warning(f"ChromaDB path does not exist: {abs_chroma_path}")
        os.makedirs(abs_chroma_path, exist_ok=True)
        logger.info(f"Created ChromaDB directory: {abs_chroma_path}")
    
    # Test dependencies
    try:
        import chromadb
        import sentence_transformers
        import redis
        logger.info("All dependencies verified")
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        raise

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
    cfg = _get_local_config_cached()
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", cfg.get('backend', {}).get('port', 8005))), reload=False)
'''
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8005,
        reload=False,
        log_level="info"
    ) '''
