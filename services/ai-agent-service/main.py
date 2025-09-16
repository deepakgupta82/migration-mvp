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
import time
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import tempfile
from app.routers.agents import router as agents_router
from app.routers.crew_config import router as crew_config_router
from app.routers.tools import router as tools_router
from app.routers.autogen import router as autogen_router
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from services.shared.service_client import get_service_client
from app.routers.autogen_test import router as autogen_test_router
from app.core.agent_processor import AIAgentProcessor
from app.core.config_client import cfg_get
from app.core.autogen_copilot import AutoGenCopilot
from app.routers.autogen import set_autogen_copilot
from app.repository.conversations import ConversationRepository, set_conversation_repository
from app.websockets.autogen_ws import handle_autogen_websocket

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

# Service start time for uptime calculation
SERVICE_START_TIME = time.time()

# Global processor and AutoGen instances
processor = None
autogen_copilot = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global processor, autogen_copilot
    
    logger.info("AI Agent Orchestration Service starting on port 8008...")
    
    try:
        # Initialize processor
        processor = AIAgentProcessor()
        
        # Verify dependencies
        dependencies = await processor.verify_dependencies()
        logger.info("All dependencies verified")
        
    # Initialize AutoGen copilot
        try:
            # Initialize copilot in project-scoped key mode (no env api key allowed)
            llm_config = {
                "model": os.getenv("AUTOGEN_MODEL", "gpt-4"),
                "api_key": None,  # must be supplied per project request
                "temperature": float(os.getenv("AUTOGEN_TEMPERATURE", "0.7")),
                "timeout": int(os.getenv("AUTOGEN_TIMEOUT", "300")),
                "project_scoped": True
            }
            autogen_copilot = AutoGenCopilot(llm_config)
            set_autogen_copilot(autogen_copilot)
            logger.info("AutoGen copilot initialized in project-scoped mode (awaiting per-project LLM config)")
        except Exception as e:
            logger.error(f"Failed to initialize AutoGen copilot (project-scoped mode): {e}")
            autogen_copilot = None

        # Initialize conversation repository using existing DB connection (from processor)
        try:
            if getattr(processor, "db_connection", None):
                conv_repo = ConversationRepository(processor.db_connection)
                conv_repo.ensure_tables()
                set_conversation_repository(conv_repo)
                logger.info("Conversation repository initialized & tables ensured")
            else:
                logger.warning("Processor DB connection not available; conversation persistence disabled")
        except Exception as e:
            logger.error(f"Failed to initialize conversation repository: {e}")
        
        # Make instances available to routes
        app.state.processor = processor
        app.state.autogen_copilot = autogen_copilot
        
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
    description="AI agent management, multi-agent crew workflows, and AutoGen copilot",
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
app.include_router(agents_router, prefix="/api/agents")
app.include_router(crew_config_router)
app.include_router(tools_router)
app.include_router(autogen_router, prefix="/api/autogen", tags=["AutoGen Copilot"])
app.include_router(autogen_test_router, prefix="/api/autogen", tags=["AutoGen Testing"])

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

async def check_dependencies():
    """Check service dependencies for readiness"""
    dependencies = {}

    # Check PostgreSQL
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

    # Indicate that OpenAI provider key is project-scoped; do not validate env key
    dependencies["llm_key_mode"] = "project_scoped_only"
    if os.getenv("OPENAI_API_KEY"):
        dependencies["openai_env_key_present_but_ignored"] = True
    else:
        dependencies["openai_env_key_present_but_ignored"] = False

    return dependencies

@app.get("/livez")
async def liveness_check():
    """Liveness probe - checks if service is running"""
    return {
        "status": "healthy",
        "service": "ai-agent-service",
        "uptime": int(time.time() - SERVICE_START_TIME),
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

@app.get("/healthz")
async def readiness_check():
    """Readiness probe - checks if service is ready to accept traffic"""
    dependencies = await check_dependencies()

    # Determine overall status
    overall_status = "healthy" if all(status in ["healthy", "configured"] for status in dependencies.values()) else "unhealthy"

    return {
        "status": overall_status,
        "service": "ai-agent-service",
        "uptime": int(time.time() - SERVICE_START_TIME),
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "dependencies": dependencies
    }

# Health check endpoint at root level
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "service": "ai-agent-orchestration",
        "status": "healthy",
        "port": 8008,
        "version": "1.0.0",
        "autogen_available": autogen_copilot is not None
    }

# AutoGen WebSocket endpoint
@app.websocket("/ws/autogen/{session_id}")
async def autogen_websocket_endpoint(websocket, session_id: str):
    """WebSocket endpoint for real-time AutoGen conversations"""
    if autogen_copilot is None:
        await websocket.close(code=1000, reason="AutoGen copilot not available")
        return
    
    await handle_autogen_websocket(websocket, session_id, autogen_copilot)

# Backward-compatible alias explicitly for discussions feature (same handler)
@app.websocket("/ws/autogen/discussions/{session_id}")
async def autogen_discussions_websocket_endpoint(websocket, session_id: str):
    """Alias WebSocket endpoint for Discussions UI (maps to core autogen handler)."""
    if autogen_copilot is None:
        await websocket.close(code=1000, reason="AutoGen copilot not available")
        return
    await handle_autogen_websocket(websocket, session_id, autogen_copilot)

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
