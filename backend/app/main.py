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

from app.core.project_service import get_llm_configurations_from_db
from app.core.logging_config import init_logging, CorrelationIdMiddleware
from app.routers import projects_router, llm_router, health_router, project_analysis_router, platform_settings_router
from app.routers import logs_router
from app.routers import llm_config_router  # process-specific LLM configuration endpoints
from app.routers import ollama_router  # Ollama service integration
from app.routers import template_usage_router  # Global template usage statistics
from app.routers import config_router  # Configuration management
from app.routers import gateway_router  # API gateway routes (projects, health, etc.)
from app.core.log_stream import log_manager  # extracted log manager
from app.core.crew_logger import crew_logger_registry  # ensure import present for crew interactions WS
from app.core.crew_config_ws import get_crew_config_ws_manager
from app.core.process_ws import get_process_ws_manager
from app.core.project_service import get_project_service
from app.routers import legacy_compat_router  # legacy compat routes

# Logging setup with UTF-8 encoding
init_logging()
logger = logging.getLogger("backend")

# Load environment variables from .env file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

# Windows asyncio: prefer SelectorEventLoopPolicy to reduce spurious ConnectionResetError logs
if os.name == "nt":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        logger.info("Windows: using SelectorEventLoopPolicy for asyncio")
    except Exception as e:
        logger.debug(f"Windows event loop policy set failed: {e}")

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
        # Initialize global graph service to prevent frequent reinitializations
        from app.core.global_graph_service import get_graph_service
        get_graph_service()
        logger.info("Startup: initialized global GraphService")
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
            svc = get_stats_service()
            ps = get_project_service()
            projects = []
            try:
                projects = ps.list_projects()
            except Exception as e:
                logger.warning(f"Warmup: list_projects failed: {e}")
                return
            from asyncio import Semaphore
            sem = Semaphore(int(os.getenv("WARMUP_STATS_CONCURRENCY", "6")))
            async def warm(pid: str):
                async with sem:
                    try:
                        await svc.get_project_stats_cached(pid)
                    except Exception:
                        pass
            tasks = []
            for p in projects[:int(os.getenv("WARMUP_STATS_LIMIT", "50"))]:
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
        while True:
            try:
                # refresh platform
                await svc.get_platform_stats_cached()
                # sample project cache refresh
                for pid in list(svc.project_cache.keys())[:5]:
                    await svc.get_project_stats_cached(pid)
            except Exception:
                pass
            await asyncio.sleep(60)
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
        # Close global graph service
        from app.core.global_graph_service import close_graph_service
        close_graph_service()
        logger.info("Shutdown: closed global GraphService")
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

            # Allow disabling WS auth for local debugging
            if os.getenv("DISABLE_WS_AUTH", "0") == "1":
                logger.info(f"WS auth disabled by env for {purpose}")
                return True

            # Legacy token check first
            legacy = os.getenv("SERVICE_AUTH_TOKEN", "service-backend-token")
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
# Register gateway and key feature routers
app.include_router(gateway_router.router)
# Ensure projects API is available at /api/projects (direct router, no harm alongside gateway)
app.include_router(projects_router.router)
app.include_router(llm_router.router)
app.include_router(llm_config_router.router, prefix="/api/projects", tags=["llm-process"])
# Optional: expose non-gateway health if used elsewhere
app.include_router(health_router.router)
# CORS configuration for both local development and Kubernetes deployment
allowed_origins = [
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
        crew_logger_registry.unregister_project_websocket(project_id, websocket)
        try:
            await websocket.close()
        except Exception:
            pass

@app.websocket("/ws/process-documents/{project_id}")
async def websocket_process_documents(websocket: WebSocket, project_id: str):
    if not await _ws_require_auth(websocket, purpose=f"process-documents:{project_id}"):
        return
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
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=False)
