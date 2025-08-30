#!/usr/bin/env python3
"""
Knowledge Graph Service - Phase 3 of Microservices Architecture

Extracts Neo4j operations, entity extraction, and relationship mapping 
from the main backend into an independent service.

Key responsibilities:
- Neo4j database operations and graph management
- Entity extraction from documents
- Relationship mapping and graph construction
- Infrastructure topology visualization
- Dependency analysis and mapping

Port: 8006
Dependencies: Neo4j (7687), Redis (6379)
"""

import logging
import contextvars
import sys
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Note: Removed sys.path manipulation for proper package management

from app.routers import graphs
from app.core.graph_processor import GraphProcessor

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
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [graph-service] [corr_id=%(correlation_id)s] %(message)s',
    handlers=[
        logging.FileHandler('logs/graph-service.log'),
        logging.StreamHandler()
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

logger = logging.getLogger(__name__)

# Global graph processor instance
graph_processor = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    global graph_processor
    
    logger.info("Knowledge Graph Service starting on port 8006...")
    
    # Initialize graph processor
    graph_processor = GraphProcessor()
    await graph_processor.initialize()
    
    # Verify dependencies
    await verify_dependencies()
    
    yield
    
    # Cleanup
    if graph_processor:
        await graph_processor.cleanup()

async def verify_dependencies():
    """Verify all required dependencies are available"""
    try:
        from neo4j import GraphDatabase
        import redis
        logger.info("All dependencies verified")
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        raise

# Initialize FastAPI app
app = FastAPI(
    title="Knowledge Graph Service",
    description="Handles Neo4j operations, entity extraction, and relationship mapping",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
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
app.include_router(graphs.router, prefix="/api/graphs", tags=["graphs"])

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "service": "knowledge-graph",
        "status": "healthy",
        "port": 8006,
        "version": "1.0.0"
    }

# Make graph processor available to routers
@app.middleware("http")
async def add_graph_processor(request, call_next):
    """Add graph processor to request state"""
    request.state.graph_processor = graph_processor

    # Set correlation ID from header or existing context
    corr_id = request.headers.get("X-Correlation-ID") or correlation_id_ctx.get()
    if not corr_id:
        corr_id = None
    token = None
    try:
        token = correlation_id_ctx.set(corr_id)
    except Exception:
        pass

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
    uvicorn.run(app, host="0.0.0.0", port=8006, reload=False)
