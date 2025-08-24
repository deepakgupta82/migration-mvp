"""
LLM Orchestration Service
Port: 8007
Responsibilities: LLM provider management, configuration, testing, rate limiting
"""

import os
import sys
import logging
import contextvars
import json
from datetime import datetime
from contextlib import asynccontextmanager

# Add the parent directory to sys.path so we can import from the main app
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from app.routers.llm import router as llm_router
from app.core.llm_processor import LLMProcessor
from app.core.config_client import cfg_get

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
            "service": "llm-service",
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
    '%(asctime)s %(levelname)s [llm-service] [corr_id=%(correlation_id)s] [project_id=%(project_id)s] %(message)s'
)

# Create handlers
file_handler = logging.FileHandler("logs/llm-service.log", encoding="utf-8")
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
# CORS from centralized backend config
cors_origins = cfg_get(["backend", "cors_origins"], []) or [
    "http://localhost:3000",
    "http://localhost:8000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
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
    cfg = _get_local_config_cached()
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", cfg.get('backend', {}).get('port', 8007))), reload=False)
'''
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8007,
        reload=False,  # Set to False for production stability
        log_level="info"
    ) '''
