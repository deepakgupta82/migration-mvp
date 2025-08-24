"""
AI Agent Orchestration Service
Port: 8008
Responsibilities: AI agent management, CrewAI workflows, task orchestration
"""

import os
import sys
import logging
import contextvars
import asyncio
import json
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import tempfile
from app.routers.agents import router as agents_router
from app.routers.crew_config import router as crew_config_router
from app.routers.tools import router as tools_router
from app.core.agent_processor import AIAgentProcessor
from app.core.config_client import cfg_get

"""Logging configuration with JSON format (Loki-friendly)
Fields: ts, level, service, corr_id, project_id, msg
"""
# Correlation ID and Project ID contexts
correlation_id_ctx = contextvars.ContextVar("correlation_id", default=None)
project_id_ctx = contextvars.ContextVar("project_id", default=None)

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "ts": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "service": "ai-agent-service",
            "corr_id": getattr(record, 'correlation_id', '-') or '-',
            "project_id": getattr(record, 'project_id', '-') or '-',
            "msg": record.getMessage()
        }
        return json.dumps(log_data)

class SafeFormatter(logging.Formatter):
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

# Configure logging handlers (write file logs outside workspace to avoid uvicorn reload loops)
log_base_dir = os.getenv("AI_AGENT_LOG_DIR") or os.path.join(tempfile.gettempdir(), "ai-agent-service")
os.makedirs(log_base_dir, exist_ok=True)
log_file_path = os.path.join(log_base_dir, "ai-agent-service.log")
json_formatter = JSONFormatter()
text_formatter = SafeFormatter(
    '%(asctime)s %(levelname)s [ai-agent-service] [corr_id=%(correlation_id)s] [project_id=%(project_id)s] %(message)s'
)

file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
file_handler.setFormatter(json_formatter)
file_handler.addFilter(ContextLogFilter())

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(text_formatter)
console_handler.addFilter(ContextLogFilter())

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

logger = logging.getLogger("ai-agent-service")

# Global processor instance
processor = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global processor
    
    logger.info("AI Agent Orchestration Service starting on port 8008...")
    
    try:
        # Initialize processor
        processor = AIAgentProcessor()
        
        # Verify dependencies
        dependencies = await processor.verify_dependencies()
        logger.info("All dependencies verified")
        
        # Make processor available to routes
        app.state.processor = processor
        
        try:
            yield
        except asyncio.CancelledError:
            # Graceful shutdown under reloader or server stop
            pass
        
    except Exception as e:
        logger.error(f"Failed to start AI Agent service: {e}")
        raise
    finally:
        try:
            logger.info("AI Agent Orchestration Service shutting down...")
        except Exception:
            pass

# Create FastAPI app with lifespan management
app = FastAPI(
    title="AI Agent Orchestration Service",
    description="AI agent management and multi-agent crew workflows",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware (origins from centralized config with sensible fallback)
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
    expose_headers=["X-Correlation-ID"],
)

# Include routers
app.include_router(agents_router, prefix="/api/agents")
app.include_router(crew_config_router)
app.include_router(tools_router)

# Correlation ID middleware
@app.middleware("http")
async def correlation_id_middleware(request, call_next):
    # Prefer inbound header; if missing, generate a new UUID to guarantee echo
    corr_id = request.headers.get("X-Correlation-ID") or correlation_id_ctx.get()
    if not corr_id:
        try:
            import uuid
            corr_id = str(uuid.uuid4())
        except Exception:
            corr_id = None
    token = None
    try:
        token = correlation_id_ctx.set(corr_id)
    except Exception:
        pass
    try:
        response = await call_next(request)
    finally:
        if token is not None:
            try:
                correlation_id_ctx.reset(token)
            except Exception:
                pass
    if corr_id:
        response.headers["X-Correlation-ID"] = corr_id
    return response

# Health check endpoint at root level
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "service": "ai-agent-orchestration",
        "status": "healthy",
        "port": 8008,
        "version": "1.0.0"
    }

if __name__ == "__main__":
    # Windows: prefer SelectorEventLoopPolicy to reduce spurious ConnectionResetError logs
    if os.name == "nt":
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except Exception:
            pass
    # Run without auto-reload for stability when launched directly
    port = int(os.getenv("PORT", "8008"))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info"
    )
