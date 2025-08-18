"""
LLM Orchestration Service
Port: 8007
Responsibilities: LLM provider management, configuration, testing, rate limiting
"""

import os
import sys
import logging
import contextvars
from contextlib import asynccontextmanager

# Add the parent directory to sys.path so we can import from the main app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from app.routers.llm import router as llm_router
from app.core.llm_processor import LLMProcessor

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
    format='%(asctime)s %(levelname)s [llm-service] [corr_id=%(correlation_id)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler("logs/llm-service.log", encoding="utf-8"),
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

logger = logging.getLogger("llm-service")

# Global processor instance
processor = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global processor
    
    logger.info("LLM Orchestration Service starting on port 8007...")
    
    try:
        # Initialize processor
        processor = LLMProcessor()
        
        # Verify dependencies
        dependencies = await processor.verify_dependencies()
        logger.info("All dependencies verified")
        
        # Make processor available to routes
        app.state.processor = processor
        
        yield
        
    except Exception as e:
        logger.error(f"Failed to start LLM service: {e}")
        raise
    finally:
        logger.info("LLM Orchestration Service shutting down...")

# Create FastAPI app with lifespan management
app = FastAPI(
    title="LLM Orchestration Service",
    description="Centralized LLM provider management and orchestration",
    version="1.0.0",
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

# Include routers
app.include_router(llm_router, prefix="/api/llm")

# Correlation ID middleware and logging filter
@app.middleware("http")
async def correlation_id_middleware(request, call_next):
    corr_id = request.headers.get("X-Correlation-ID") or correlation_id_ctx.get()
    if not corr_id:
        corr_id = None
    token = None
    try:
        token = correlation_id_ctx.set(corr_id)
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

# Health check endpoint at root level
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "service": "llm-orchestration",
        "status": "healthy",
        "port": 8007,
        "version": "1.0.0"
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8007,
        reload=False,  # Set to False for production stability
        log_level="info"
    )
