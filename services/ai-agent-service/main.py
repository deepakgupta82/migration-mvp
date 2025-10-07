"""
AI Agent Orchestration Service
Port: 8008
Responsibilities: AI agent management, CrewAI workflows, task orchestration
"""

import os
import re
import sys
import logging
import contextvars
import asyncio
import json
import time
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import tempfile
import sys
import os
# Ensure shared services package is on path BEFORE importing routers that depend on it
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from app.routers.agents import router as agents_router
from app.routers.crew_config import router as crew_config_router
from app.routers.tools import router as tools_router
from app.routers.autogen import router as autogen_router
from services.shared.service_client import get_service_client
from app.routers.autogen_test import router as autogen_test_router
from app.routers.mcp import router as mcp_router
from app.routers.admin_prompts import router as admin_prompts_router
from app.core.agent_processor import AIAgentProcessor
from app.core.config_client import cfg_get
from app.core.autogen_copilot import AutoGenCopilot
from app.routers.autogen import set_autogen_copilot
from app.repository.conversations import ConversationRepository, set_conversation_repository
from app.websockets.autogen_ws import handle_autogen_websocket
from app.repository.mcp_registry import get_registry
from app.core.mcp_models import MCPServerConfig, ConnectionConfig, STDIOConnection

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
        
        # Initialize conversation repository using existing DB connection (from processor)
        conv_repo = None
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
            conv_repo = None

        # Initialize AutoGen copilot (after repository is available)
        try:
            # Initialize copilot in project-scoped key mode (no default model - must be supplied per project)
            llm_config = {
                "model": None,  # Must be supplied per project request via conversation_llm_config
                "api_key": None,  # Must be supplied per project request
                "temperature": float(os.getenv("AUTOGEN_TEMPERATURE", "0.7")),
                "timeout": int(os.getenv("AUTOGEN_TIMEOUT", "300")),
                "project_scoped": True
            }
            autogen_copilot = AutoGenCopilot(llm_config, conversation_repository=conv_repo)
            set_autogen_copilot(autogen_copilot)
            logger.info("AutoGen copilot initialized in project-scoped mode with persistent storage (awaiting per-project LLM config)")
        except Exception as e:
            logger.error(f"Failed to initialize AutoGen copilot (project-scoped mode): {e}")
            autogen_copilot = None
        
        # Make instances available to routes
        app.state.processor = processor
        app.state.autogen_copilot = autogen_copilot
        # Seed MCP registry with common AWS servers (disabled by default) if not present
        try:
            reg = get_registry()
            # Prefer npx so the binary can be run without setting cwd; operators may also switch to node dist/index.js with cwd
            seeds = [
                ("AWS Pricing MCP", ("npx", ["aws-pricing-mcp-server"]), "aws-pricing-mcp-server"),
                ("AWS S3 MCP", ("npx", ["aws-s3-mcp-server"]), "aws-s3-mcp-server"),
                ("AWS IAM MCP", ("npx", ["aws-iam-mcp-server"]), "aws-iam-mcp-server"),
                ("AWS CloudWatch MCP", ("npx", ["aws-cloudwatch-mcp-server"]), "aws-cloudwatch-mcp-server"),
                ("AWS Bedrock MCP", ("npx", ["aws-bedrock-mcp-server"]), "aws-bedrock-mcp-server"),
            ]
            for name, (command, args), env_hint in seeds:
                # Only add if not present by name
                exists = any(s.name == name for s in reg.list())
                if exists:
                    continue
                cfg = MCPServerConfig(
                    name=name,
                    provider="aws",
                    connection=ConnectionConfig(
                        transport="stdio",
                        stdio=STDIOConnection(
                            command=command,
                            args=args,
                            cwd=None,
                        ),
                    ),
                    is_enabled=False,
                    description=(
                        f"Seeded {name}. If you have Node installed, try 'npx {env_hint}'. "
                        f"Alternatively, clone/build the server and use 'node dist/index.js' with the server folder as cwd."
                    ),
                )
                reg.upsert(cfg)
            logger.info("MCP registry seeded with AWS server templates (disabled by default)")
        except Exception as e:
            logger.warning(f"Failed seeding MCP registry: {e}")
        
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
    "http://localhost:3001",
    "http://localhost:8000",
    "http://localhost:8008",
]

# Allow override via environment variable (comma separated)
env_origins = os.getenv("AI_AGENT_CORS_ORIGINS")
if env_origins:
    try:
        extra = [o.strip() for o in env_origins.split(",") if o.strip()]
        cors_origins = list(dict.fromkeys(cors_origins + extra))  # preserve order, dedupe
    except Exception:
        logger.warning("Failed parsing AI_AGENT_CORS_ORIGINS env var")

# For development, allow all origins to fix WebSocket CORS issues
# In production, this should be restricted to specific origins
if os.getenv("ENVIRONMENT", "development") == "development":
    cors_origins = ["*"]
    allow_credentials = False  # Cannot use credentials with wildcard origins
    logger.info("Development mode: Allowing all CORS origins for WebSocket compatibility")
else:
    allow_credentials = True

# Allow localhost/127.0.0.1 on any port by default for dev WebSocket usage
default_origin_regex = r"^https?://(localhost|127\.0\.0\.1)(:\\d+)?$"
origin_regex = os.getenv("AI_AGENT_CORS_ORIGIN_REGEX", default_origin_regex)

logger.info(f"CORS origins configured: {cors_origins}")
logger.info(f"CORS origin regex: {origin_regex}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=origin_regex if cors_origins != ["*"] else None,  # Don't use regex with wildcard
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Correlation-ID"],
)

# Additional CORS configuration for WebSocket connections
@app.middleware("http")
async def websocket_cors_middleware(request, call_next):
    """Handle CORS for WebSocket connections including upgrade requests"""

    # Check if this is a WebSocket upgrade request
    upgrade_header = request.headers.get("upgrade", "").lower()
    connection_header = request.headers.get("connection", "").lower()
    is_websocket_upgrade = (
        upgrade_header == "websocket" or
        "upgrade" in connection_header or
        request.url.path.startswith("/ws/")
    )

    # Handle OPTIONS preflight requests for WebSocket connections
    if is_websocket_upgrade and request.method == "OPTIONS":
        response = Response(status_code=200)
        origin = request.headers.get("Origin", "*")
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "X-Correlation-ID, Authorization, Content-Type, Upgrade, Connection, Sec-WebSocket-Key, Sec-WebSocket-Version, Sec-WebSocket-Protocol"
        response.headers["Access-Control-Max-Age"] = "86400"  # 24 hours
        logger.info(f"Handled WebSocket OPTIONS preflight for {request.url.path}")
        return response

    # For WebSocket upgrade requests (GET method), let them proceed to WebSocket endpoints
    # Do NOT return a response here - that prevents the WebSocket handshake

    # Continue with normal request processing
    response = await call_next(request)

    # Add CORS headers to all WebSocket-related responses
    if request.url.path.startswith("/ws/"):
        origin = request.headers.get("Origin", "*")
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"

    return response

# WebSocket authentication helper (following backend service pattern)
async def _ws_require_auth(websocket: WebSocket, purpose: str = "ws") -> bool:
    """Validate WS auth via query param ?token=... or Authorization header.
    Returns True if authorized; otherwise closes with 1008 and returns False.
    """
    try:
        # Extract token from query parameters
        params = dict(websocket.query_params) if getattr(websocket, "query_params", None) else {}
        token = params.get("token")

        # Prefer Authorization header if present
        headers = getattr(websocket, "headers", {}) or {}
        if not token:
            auth_header = headers.get("authorization")
            token = auth_header.replace("Bearer ", "") if auth_header else None

        # Debug logging to diagnose 403 causes (mask most of token if present)
        try:
            origin = headers.get("origin")
            corr = dict(params).get("correlation_id") or headers.get("x-correlation-id")
            token_preview = (token[:4] + "***") if token else None
            logger.info(f"WS auth check purpose={purpose} origin={origin} has_token={bool(token)} token_preview={token_preview} params_keys={list(params.keys())} corr_id={corr}")
        except Exception:
            pass

        # For development, accept the service token
        expected_token = "service-backend-token"
        if token == expected_token:
            logger.info(f"WebSocket auth successful for {purpose}")
            return True

        # Dev convenience: if origin is localhost, allow without token (development only)
        try:
            origin = headers.get("origin") or ""
            if origin and re.match(origin_regex, origin):
                logger.info(
                    f"WebSocket auth (DEV override) accepted for {purpose} origin={origin} token_present={bool(token)}"
                )
                return True
        except Exception:
            pass

        # If no valid token, reject the connection
        try:
            origin = headers.get("origin") or ""
            origin_matches = bool(re.match(origin_regex, origin)) if origin else False
        except Exception:
            origin = None
            origin_matches = False
        logger.warning(
            f"WebSocket auth failed for {purpose}: invalid or missing token; origin={origin} origin_matches_dev={origin_matches} params={params}"
        )
        await websocket.close(code=1008, reason="Authentication required")
        return False

    except Exception as e:
        logger.error(f"WebSocket auth error for {purpose}: {e}")
        try:
            await websocket.close(code=1008, reason="Authentication error")
        except Exception:
            pass
        return False

# Trailing slash redirect middleware (308 Permanent Redirect)
@app.middleware("http")
async def trailing_slash_redirect_middleware(request, call_next):
    # Skip redirect for health check endpoints, non-GET requests, and websocket upgrade handshakes
    if (
        request.method != "GET" 
        or request.url.path in ["/livez", "/healthz", "/health"]
        or request.headers.get("upgrade", "").lower() == "websocket"
    ):
        return await call_next(request)

    # Check if path ends with trailing slash (except root path)
    if request.url.path.endswith("/") and request.url.path != "/":
        canonical_path = request.url.path.rstrip("/")
        query_string = str(request.url.query) if request.url.query else ""

        redirect_url = f"{request.url.scheme}://{request.url.host}:{request.url.port}{canonical_path}"
        if query_string:
            redirect_url += f"?{query_string}"

        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=redirect_url, status_code=308)

    return await call_next(request)

# Include routers
app.include_router(agents_router, prefix="/api/agents")
app.include_router(crew_config_router)
app.include_router(tools_router)
app.include_router(autogen_router, prefix="/api/autogen", tags=["AutoGen Copilot"])
app.include_router(autogen_test_router, prefix="/api/autogen", tags=["AutoGen Testing"])
app.include_router(admin_prompts_router)
app.include_router(mcp_router)

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
        "timestamp": datetime.utcnow().isoformat(),
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
        "timestamp": datetime.utcnow().isoformat(),
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
@app.middleware("websocket")
async def ws_logging_middleware(websocket: WebSocket, call_next):
    try:
        headers = getattr(websocket, "headers", {}) or {}
        origin = headers.get("origin")
        path = getattr(websocket, "url", None)
        logger.info(f"WS middleware: incoming handshake path={path} origin={origin}")
    except Exception:
        pass
    return await call_next(websocket)

@app.websocket("/ws/autogen/{session_id}")
async def autogen_websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time AutoGen conversations"""
    logger.info(
        f"WebSocket handshake /ws/autogen/{session_id} origin={getattr(websocket, 'headers', {}).get('origin')} query={getattr(websocket, 'query_params', None)}"
    )

    # Check authentication using the helper function
    if not await _ws_require_auth(websocket, purpose=f"autogen:{session_id}"):
        # Note: returning here without accept will surface as 403 in access logs (expected for unauthenticated)
        return

    try:
        # Delegate acceptance to the WebSocket manager inside the handler to avoid double-accept
        if autogen_copilot is None:
            logger.warning("AutoGen copilot not available")
            # Accept temporarily to deliver the error payload, then close cleanly
            try:
                await websocket.accept()
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "error": "AutoGen copilot not available",
                    "timestamp": datetime.utcnow().isoformat()
                }))
            finally:
                try:
                    await websocket.close(code=1000, reason="AutoGen copilot not available")
                except Exception:
                    pass
            return

        logger.info(f"Starting WebSocket handler for session {session_id}")
        await handle_autogen_websocket(websocket, session_id, autogen_copilot)

    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
        try:
            await websocket.close(code=1011, reason=f"Internal error: {str(e)}")
        except Exception:
            pass

# Trailing slash alias (some clients accidentally include trailing slash)
@app.websocket("/ws/autogen/{session_id}/")
async def autogen_websocket_endpoint_trailing(websocket: WebSocket, session_id: str):
    logger.info(
    f"WebSocket handshake (trailing) /ws/autogen/{session_id}/ origin={getattr(websocket, 'headers', {}).get('origin')} query={getattr(websocket, 'query_params', None)}"
    )

    # Check authentication using the helper function
    if not await _ws_require_auth(websocket, purpose=f"autogen:{session_id}"):
        return

    if autogen_copilot is None:
        # Accept temporarily to deliver the error payload, then close
        try:
            await websocket.accept()
            await websocket.send_text(json.dumps({
                "type": "error",
                "error": "AutoGen copilot not available",
                "timestamp": datetime.utcnow().isoformat()
            }))
        finally:
            try:
                await websocket.close(code=1000, reason="AutoGen copilot not available")
            except Exception:
                pass
        return

    # Delegate to handler (which will accept the connection)
    await handle_autogen_websocket(websocket, session_id, autogen_copilot)

# Backward-compatible alias explicitly for discussions feature (same handler)
@app.websocket("/ws/autogen/discussions/{session_id}")
async def autogen_discussions_websocket_endpoint(websocket: WebSocket, session_id: str):
    """Alias WebSocket endpoint for Discussions UI (maps to core autogen handler)."""
    logger.info(
    f"WebSocket handshake /ws/autogen/discussions/{session_id} origin={getattr(websocket, 'headers', {}).get('origin')} query={getattr(websocket, 'query_params', None)}"
    )

    # Check authentication using the helper function
    if not await _ws_require_auth(websocket, purpose=f"autogen:{session_id}"):
        return

    if autogen_copilot is None:
        # Accept temporarily to deliver the error payload, then close
        try:
            await websocket.accept()
            await websocket.send_text(json.dumps({
                "type": "error",
                "error": "AutoGen copilot not available",
                "timestamp": datetime.utcnow().isoformat()
            }))
        finally:
            try:
                await websocket.close(code=1000, reason="AutoGen copilot not available")
            except Exception:
                pass
        return

    # Delegate to handler (which will accept the connection)
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
