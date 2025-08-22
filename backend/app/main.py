import os
import tempfile
import logging
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Set
from contextlib import asynccontextmanager

from app.core.logging_config import init_logging, CorrelationIdMiddleware
from app.routers import health_router
from app.routers import logs_router
from app.routers import config_router  # Configuration management
from app.routers import gateway_router  # API gateway routes (projects, health, etc.)
from app.core.log_stream import log_manager  # extracted log manager
from app.routers import legacy_compat_router  # legacy compat routes

# Logging setup with UTF-8 encoding
init_logging()
logger = logging.getLogger("backend")

# Load environment variables from .env file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

# Load local config if present
def _load_local_config():
    try:
        import json
        cfg_path = os.path.join(os.path.dirname(__file__), '..', 'config.local.json')
        if os.path.exists(cfg_path):
            with open(cfg_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to read local config: {e}")
    return {}

def _get_local_config_cached():
    # Simple cache with timestamp to avoid reading on every call
    # Reload if older than 5 seconds
    if not hasattr(_get_local_config_cached, "_cache"):
        _get_local_config_cached._cache = {"ts": 0, "cfg": {}}
    import time
    now = time.time()
    if now - _get_local_config_cached._cache["ts"] > 5:
        _get_local_config_cached._cache = {"ts": now, "cfg": _load_local_config()}
    return _get_local_config_cached._cache["cfg"]

# Windows asyncio: prefer SelectorEventLoopPolicy to reduce spurious ConnectionResetError logs
if os.name == "nt":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        logger.info("Windows: using SelectorEventLoopPolicy for asyncio")
    except Exception as e:
        logger.debug(f"Windows event loop policy set failed: {e}")
    # Suppress noisy ConnectionResetError (WinError 10054) from underlying sockets
    try:
        def _windows_asyncio_exception_handler(loop, context):
            exc = context.get("exception")
            msg = str(context.get("message") or "")
            text = f"{exc!r} {msg}"
            if isinstance(exc, ConnectionResetError) or (exc and "WinError 10054" in str(exc)) or ("WinError 10054" in text):
                logger.debug("Suppressed Windows ConnectionResetError 10054 from asyncio loop")
                return
            # Fallback to default behavior
            try:
                loop.default_exception_handler(context)  # type: ignore[attr-defined]
            except Exception:
                logging.getLogger("asyncio").error(f"Asyncio exception: {context}")

        loop = asyncio.get_event_loop()
        loop.set_exception_handler(_windows_asyncio_exception_handler)
    except Exception as e:
        logger.debug(f"Windows exception handler setup failed: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        from app.core.project_service import get_llm_configurations_from_db
        configs = get_llm_configurations_from_db() or {}
        logger.info(f"Startup: loaded {len(configs)} LLM configurations")
        from app.core.stats_service import get_stats_service
        get_stats_service().register_event_handlers()
        logger.info("Startup: registered stats event handlers")
    # Graph now accessed via graph-service; no direct Neo4j init needed
    except Exception as e:
        logger.warning(f"Startup: issues during init: {e}")
    # Warm platform stats asynchronously
    try:
        from app.core.stats_service import get_stats_service
        asyncio.create_task(get_stats_service().get_platform_stats_cached())
    except Exception:
        pass
    # Warm per-project stats (bounded concurrency, snapshot-first)
    async def warm_project_stats():
        try:
            from app.core.stats_service import get_stats_service
            from app.core.project_service import get_project_service
            svc = get_stats_service()
            ps = get_project_service()
            projects = []
            try:
                projects = ps.list_projects()
            except Exception as e:
                logger.warning(f"Warmup: list_projects failed: {e}")
                return
            from asyncio import Semaphore
            cfg = _get_local_config_cached()
            sem = Semaphore(int(os.getenv("WARMUP_STATS_CONCURRENCY", str(cfg.get('backend', {}).get('warmup_stats_concurrency', 6)))))
            async def warm(pid: str):
                async with sem:
                    try:
                        await svc.get_project_stats_cached(pid)
                    except Exception:
                        pass
            tasks = []
            cfg = _get_local_config_cached()
            for p in projects[:int(os.getenv("WARMUP_STATS_LIMIT", str(cfg.get('backend', {}).get('warmup_stats_limit', 50))))]:
                pid = getattr(p, 'id', None) or (p.get('id') if isinstance(p, dict) else None)
                if pid:
                    tasks.append(asyncio.create_task(warm(pid)))
            if tasks:
                try:
                    await asyncio.gather(*tasks)
                except Exception:
                    pass
            logger.info(f"Warmup: initialized stats for {len(tasks)} projects")
        except Exception as e:
            logger.warning(f"Warmup project stats failed: {e}")
    try:
        asyncio.create_task(warm_project_stats())
    except Exception:
        pass
    # Periodic integrity refresh
    async def periodic_stats_refresh():
        from app.core.stats_service import get_stats_service
        svc = get_stats_service()
        # Allow configuring refresh interval via env var or config file
        # Priority: env BACKEND_STATS_REFRESH_INTERVAL_SEC > config.local.json backend.stats_refresh_interval_sec > default 300
        refresh_interval = 300
        # Read initial interval
        try:
            env_val = os.getenv("BACKEND_STATS_REFRESH_INTERVAL_SEC")
            if env_val:
                refresh_interval = max(5, int(env_val))
            else:
                cfg = _get_local_config_cached()
                refresh_interval = int(cfg.get('backend', {}).get('stats_refresh_interval_sec', refresh_interval))
        except Exception as e:
            logger.warning(f"Failed to load stats refresh interval; using default {refresh_interval}s: {e}")
        while True:
            try:
                # refresh platform
                await svc.get_platform_stats_cached()
                # sample project cache refresh
                for pid in list(svc.project_cache.keys())[:5]:
                    await svc.get_project_stats_cached(pid)
            except Exception:
                pass
            # Re-read interval before sleeping to allow dynamic updates
            try:
                env_val = os.getenv("BACKEND_STATS_REFRESH_INTERVAL_SEC")
                if env_val:
                    refresh_interval = max(5, int(env_val))
                else:
                    cfg = _get_local_config_cached()
                    refresh_interval = int(cfg.get('backend', {}).get('stats_refresh_interval_sec', refresh_interval))
            except Exception:
                pass
            await asyncio.sleep(refresh_interval)
    try:
        asyncio.create_task(periodic_stats_refresh())
    except Exception:
        pass
    yield
    # Shutdown cleanup (stop any running log streaming processes)
    try:
        if 'log_manager' in globals():
            for svc, proc in list(log_manager.log_processes.items()):
                try:
                    if hasattr(proc, 'terminate'):
                        proc.terminate()
                except Exception:
                    pass
            logger.info("Shutdown: cleaned up log streaming processes")
    # No direct graph driver to close; handled by graph-service
    except Exception as e:
        logger.warning(f"Shutdown cleanup issue: {e}")

app = FastAPI(
    title="Nagarro's Ascent API Gateway",
    description="API Gateway for Nagarro's Ascent microservices platform - routes requests to 7 specialized services",
    version="2.0.0",
    lifespan=lifespan
)
app.add_middleware(CorrelationIdMiddleware)

# ---------------- WebSocket auth helper -----------------
async def _ws_require_auth(websocket: WebSocket, purpose: str = "ws") -> bool:
    """Validate WS auth via query param ?token=... or Authorization header.
    Accepts either JWT verified by backend.jwt_auth or a legacy SERVICE_AUTH_TOKEN.
    Returns True if authorized; otherwise closes with 1008 and returns False.
    """
    try:
        # Accept early to read headers consistently in some proxies; we'll still close if unauthorized
        if websocket.client_state.name == "CONNECTED":
            pass
        # Remove redundant accept; only accept once per connection
        try:
            params = dict(websocket.query_params) if websocket.query_params else {}
            token = params.get("token")
            # Prefer Authorization header if present
            if not token:
                auth_header = websocket.headers.get("authorization") if hasattr(websocket, "headers") else None
                token = auth_header.replace("Bearer ", "") if auth_header else None

            # Allow disabling WS auth for local debugging (env or config)
            disable_ws_auth = os.getenv("DISABLE_WS_AUTH")
            if disable_ws_auth is None:
                cfg = _get_local_config_cached()
                disable_ws_auth = str(cfg.get('backend', {}).get('disable_ws_auth', 0))
            if str(disable_ws_auth) == "1":
                logger.info(f"WS auth disabled by env for {purpose}")
                return True

            # Legacy token check first
            cfg = _get_local_config_cached()
            legacy = os.getenv("SERVICE_AUTH_TOKEN") or cfg.get('backend', {}).get('service_auth_token', 'service-backend-token')
            if token == legacy:
                return True

            # Validate JWT token (if available)
            from app.core.jwt_auth import verify_token
            valid = False
            if token:
                payload = verify_token(token)
                if payload:
                    valid = True

            if not valid:
                logger.warning(f"WebSocket auth failed for {purpose}")
                await websocket.close(code=1008)
                return False
            return True
        except Exception as e:
            try:
                await websocket.close(code=1008)
            except Exception:
                pass
            logger.error(f"WebSocket auth error for {purpose}: {e}")
            return False
    except Exception as e:
        logger.error(f"WebSocket auth outer error for {purpose}: {e}")
        return False

# ---------------- HTTP routers -----------------
# Register only gateway and necessary support routers
app.include_router(gateway_router.router)
app.include_router(logs_router.router)
app.include_router(config_router.router)
app.include_router(health_router.router)
# CORS configuration for both local development and Kubernetes deployment
allowed_origins = _get_local_config_cached().get('backend', {}).get('cors_origins') or [
    "http://localhost:3000",  # Local development
    "http://127.0.0.1:3000",  # Local development (numeric host)
    "http://localhost:30300",  # Kubernetes NodePort
    "http://127.0.0.1:30300",  # Alternate numeric access
    "http://frontend-service",  # Kubernetes service
    "http://frontend-service:80",  # Kubernetes service with port
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_ROOT = tempfile.gettempdir()

# =====================================================================================
# WEB SOCKET FOR REAL TIME LOGS (retained)
# =====================================================================================

@app.websocket("/ws/logs/{service}")
async def websocket_logs(websocket: WebSocket, service: str):
    """WebSocket endpoint for streaming real-time logs"""
    if not await _ws_require_auth(websocket, purpose=f"logs:{service}"):
        return
    await log_manager.connect(websocket, service)

    # Start log streaming for this service
    log_manager.start_log_streaming(service)

    try:
        # Keep connection alive and stream logs
        import asyncio

        async def stream_logs():
            """Stream logs from the service process"""
            if service in log_manager.log_processes:
                process_or_thread = log_manager.log_processes[service]

                # Check if it's a subprocess
                if hasattr(process_or_thread, 'poll'):  # It's a subprocess
                    while process_or_thread.poll() is None:  # While process is running
                        try:
                            # Read from stdout
                            if process_or_thread.stdout:
                                line = process_or_thread.stdout.readline()
                                if line:
                                    # Parse log line and send as JSON
                                    log_entry = {
                                        "timestamp": datetime.now().isoformat(),
                                        "level": "INFO",
                                        "service": service,
                                        "message": line.strip()
                                    }

                                    # Try to parse log level from line
                                    if "ERROR" in line.upper():
                                        log_entry["level"] = "ERROR"
                                    elif "WARNING" in line.upper() or "WARN" in line.upper():
                                        log_entry["level"] = "WARNING"
                                    elif "DEBUG" in line.upper():
                                        log_entry["level"] = "DEBUG"

                                    await log_manager.send_log(service, log_entry)

                            await asyncio.sleep(0.1)  # Small delay to prevent overwhelming
                        except Exception as e:
                            logger.error(f"Error streaming logs for {service}: {e}")
                            break
                else:
                    # It's a thread-based mock log generator, just keep the connection alive
                    # The logs are generated in the thread and sent via send_log
                    while service in log_manager.log_processes:
                        await asyncio.sleep(1)

        # Start streaming task
        stream_task = asyncio.create_task(stream_logs())

        # Keep WebSocket alive
        while True:
            try:
                # Wait for client messages (ping/pong)
                await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
            except asyncio.TimeoutError:
                # No message received, continue streaming
                continue
            except WebSocketDisconnect:
                break

    except WebSocketDisconnect:
        pass
    finally:
        # Clean up
        log_manager.disconnect(websocket, service)
        log_manager.stop_log_streaming(service)
        if 'stream_task' in locals():
            stream_task.cancel()

@app.websocket("/ws/console/{service}")
async def websocket_console(websocket: WebSocket, service: str):
    """WebSocket endpoint for streaming raw container console output (docker logs)"""
    if not await _ws_require_auth(websocket, purpose=f"console:{service}"):
        return
    await websocket.accept()

    try:
        # Add client to the service's console stream
        console_clients_key = f"{service}_console"
        if console_clients_key not in log_manager.clients:
            log_manager.clients[console_clients_key] = set()
        log_manager.clients[console_clients_key].add(websocket)

        logger.info(f"Client connected to {service} console stream")

        # Start console streaming for this service
        await log_manager.start_console_streaming(service, websocket)

        # Keep connection alive
        while True:
            try:
                await websocket.receive_text()
            except WebSocketDisconnect:
                break

    except WebSocketDisconnect:
        logger.info(f"Client disconnected from {service} console stream")
    except Exception as e:
        logger.error(f"WebSocket console error for {service}: {e}")
    finally:
        # Remove client from console stream
        console_clients_key = f"{service}_console"
        if console_clients_key in log_manager.clients:
            log_manager.clients[console_clients_key].discard(websocket)

# =====================================================================================
# ADDED: WebSocket endpoints for stats and crew config
# =====================================================================================
from app.core.websocket_stats_manager import get_websocket_stats_manager  # lazy init inside functions
from app.core.stats_service import get_stats_service

@app.get("/api/system/websocket-stats", summary="Get WebSocket connection statistics")
async def websocket_connection_stats():
    try:
        manager = get_websocket_stats_manager()
        return manager.get_connection_stats()
    except Exception as e:
        logger.error(f"Error getting WebSocket stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get WebSocket stats: {e}")

@app.websocket("/ws/project-stats/{project_id}")
async def websocket_project_stats(websocket: WebSocket, project_id: str):
    logger.info(f"WebSocket connection attempt for project stats: {project_id}")
    if not await _ws_require_auth(websocket, purpose=f"project-stats:{project_id}"):
        return
    await websocket.accept()
    logger.info(f"WebSocket connection accepted for project stats: {project_id}")
    try:
        manager = get_websocket_stats_manager()
        await manager.subscribe_to_project_stats(websocket, project_id)
        while True:
            try:
                msg = await websocket.receive_text()
                if msg == "ping":
                    await websocket.send_text("pong")
            except Exception:
                break
    except Exception as e:
        logger.error(f"Error in project stats WebSocket: {e}")
    finally:
        try:
            manager = get_websocket_stats_manager()
            await manager.disconnect_websocket(websocket)
        except Exception:
            pass

@app.websocket("/ws/platform-stats")
async def websocket_platform_stats(websocket: WebSocket):
    logger.info("WebSocket connection attempt for platform stats")
    if not await _ws_require_auth(websocket, purpose="platform-stats"):
        return
    await websocket.accept()
    logger.info("WebSocket connection accepted for platform stats")
    try:
        manager = get_websocket_stats_manager()
        await manager.subscribe_to_dashboard_stats(websocket)
        while True:
            try:
                msg = await websocket.receive_text()
                if msg == "ping":
                    await websocket.send_text("pong")
            except Exception:
                break
    except Exception as e:
        logger.error(f"Error in platform stats WebSocket: {e}")
    finally:
        try:
            manager = get_websocket_stats_manager()
            await manager.disconnect_websocket(websocket)
        except Exception:
            pass

# Crew-config websocket is now owned by the AI Agent service; gateway no longer serves /ws/crew-config

@app.get("/api/platform/stats", summary="Get current platform statistics (snapshot)")
async def get_platform_stats_snapshot():
    try:
        stats_service = get_stats_service()
        stats = await stats_service.calculate_platform_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting platform stats snapshot: {e}")
        raise HTTPException(status_code=500, detail="Failed to get platform stats")

@app.get("/api/platform/stats-fast", summary="Get fast cached platform statistics snapshot")
async def get_platform_stats_fast():
    try:
        from app.core.stats_service import get_stats_service
        stats_service = get_stats_service()
        stats = await stats_service.get_platform_stats_cached()
        return stats
    except Exception as e:
        logger.error(f"Error getting fast platform stats snapshot: {e}")
        raise HTTPException(status_code=500, detail="Failed to get platform stats")

# =====================================================================================
# ADDED: WebSocket endpoint for crew interactions
# =====================================================================================

@app.websocket("/ws/crew-interactions/{project_id}")
async def websocket_crew_interactions(websocket: WebSocket, project_id: str):
    """Realtime crew interactions across all tasks for a project.
    Provides initial handshake and instructions. Historic data via REST endpoint.
    """
    logger.info(f"Crew interactions WS connect attempt: project={project_id}")
    if not await _ws_require_auth(websocket, purpose=f"crew-interactions:{project_id}"):
        return
    await websocket.accept()
    # Import here to avoid heavy dependencies at startup
    from app.core.crew_logger import crew_logger_registry
    crew_logger_registry.register_project_websocket(project_id, websocket)
    try:
        await websocket.send_json({
            "type": "connection_established",
            "project_id": project_id,
            "mode": "realtime",
            "endpoint": f"/api/projects/{project_id}/crew-interactions"
        })
        while True:
            try:
                msg = await websocket.receive_text()
                # Optional: future commands (register_for_task etc.) not yet required; ignore for now
                if msg == "ping":
                    await websocket.send_text("pong")
            except WebSocketDisconnect:
                break
            except Exception:
                break
    finally:
        try:
            crew_logger_registry.unregister_project_websocket(project_id, websocket)
        except Exception:
            pass
        try:
            await websocket.close()
        except Exception:
            pass

@app.websocket("/ws/process-documents/{project_id}")
async def websocket_process_documents(websocket: WebSocket, project_id: str):
    if not await _ws_require_auth(websocket, purpose=f"process-documents:{project_id}"):
        return
    # Import here to avoid startup-time imports
    from app.core.process_ws import get_process_ws_manager
    manager = get_process_ws_manager()
    await manager.connect(project_id, websocket)
    try:
        while True:
            try:
                msg = await websocket.receive_text()
                if msg == "ping":
                    await websocket.send_text("pong")
            except WebSocketDisconnect:
                break
            except Exception:
                break
    finally:
        manager.disconnect(project_id, websocket)
        try:
            await websocket.close()
        except Exception:
            pass

if __name__ == "__main__":  # pragma: no cover
    import uvicorn
    # Run without auto-reload to prevent file write induced restarts; bind all interfaces
    cfg = _get_local_config_cached()
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", cfg.get('backend', {}).get('port', 8000))), reload=False)
