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
import time
from datetime import datetime
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Note: Removed sys.path manipulation for proper package management

from app.routers import graphs
from app.routers.ontology import router as ontology_router
from app.routers.admin_prompts import router as admin_prompts_router
from app.core.graph_processor import GraphProcessor
from app.core.graph_builder import GraphBuilder

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

# Service start time for uptime calculation
SERVICE_START_TIME = time.time()

# Global graph processor instance
graph_processor = None

# Global graph builder instance (Phase 3B-4)
graph_builder = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    global graph_processor, graph_builder
    
    logger.info("Knowledge Graph Service starting on port 8006...")
    
    # Initialize graph processor
    graph_processor = GraphProcessor()
    await graph_processor.initialize()

    # Initialize graph builder dependencies (Phase 3B-4)
    from app.core.entity_resolver import EntityResolver
    from app.core.canonical_id_manager import CanonicalIDManager
    from app.core.relationship_inferencer import RelationshipInferencer
    
    entity_resolver = EntityResolver()
    canonical_id_manager = CanonicalIDManager(graph_processor.neo4j_driver)
    relationship_inferencer = RelationshipInferencer()
    
    # Initialize graph builder (Phase 3B-4)
    graph_builder = GraphBuilder(
        graph_processor=graph_processor,
        entity_resolver=entity_resolver,
        canonical_id_manager=canonical_id_manager,
        relationship_inferencer=relationship_inferencer,
        enable_resolution=True,
        enable_inference=True
    )
    logger.info("GraphBuilder initialized for Phase 3B-4 entity resolution and relationship inference")

    # Initialize PVC repository (Postgres/SQLite) if configured
    try:
        pvc_store = (os.getenv("PVC_STORE") or "redis").lower()
        if pvc_store == "postgres":
            try:
                from app.pvc_repo.repository import init_db
                init_db()
                logger.info("PVC repository initialized (Postgres/SQLAlchemy)")
            except Exception as e:
                logger.error(f"Failed to initialize PVC repository; continuing with Redis: {e}")
    except Exception:
        # Non-fatal; Redis path will still work
        pass
    
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
    default_origins = ["http://localhost:3000", "http://localhost:8000"]
    cfg_origins = cfg_get(["backend", "cors_origins"], default_origins) or default_origins
except Exception:
    cfg_origins = ["http://localhost:3000", "http://localhost:8000"]

# Optional environment variable override (comma-separated)
env_origins = os.getenv("GRAPH_CORS_ORIGINS")
if env_origins:
    try:
        parsed = [o.strip() for o in env_origins.split(",") if o.strip()]
        if parsed:
            cfg_origins = parsed
    except Exception:
        pass

origins = cfg_origins
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
app.include_router(graphs.router, prefix="/api/graphs", tags=["graphs"])
app.include_router(admin_prompts_router)
app.include_router(ontology_router)

async def check_dependencies():
    """Check service dependencies for readiness"""
    dependencies = {}

    # Check Neo4j
    try:
        from neo4j import GraphDatabase
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "password")
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
        driver.close()
        dependencies["neo4j"] = "healthy"
    except Exception:
        dependencies["neo4j"] = "unhealthy"

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

    return dependencies

@app.get("/livez")
async def liveness_check():
    """Liveness probe - checks if service is running"""
    return {
        "status": "healthy",
        "service": "graph-service",
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
        "service": "graph-service",
        "uptime": int(time.time() - SERVICE_START_TIME),
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "dependencies": dependencies
    }

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
    """Add graph processor and graph builder to request state"""
    request.state.graph_processor = graph_processor
    request.state.graph_builder = graph_builder

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
