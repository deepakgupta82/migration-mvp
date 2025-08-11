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
from app.routers import projects_router, llm_router, health_router, project_analysis_router
from app.core.log_stream import log_manager  # extracted log manager

# Logging setup with UTF-8 encoding
init_logging()
logger = logging.getLogger("backend")

# Load environment variables from .env file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        from app.core.project_service import get_llm_configurations_from_db
        configs = get_llm_configurations_from_db() or {}
        logger.info(f"Startup: loaded {len(configs)} LLM configurations")
    except Exception as e:
        logger.warning(f"Startup: failed to load LLM configs: {e}")
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
    except Exception as e:
        logger.warning(f"Shutdown cleanup issue: {e}")

app = FastAPI(
    title="Nagarro's Ascent Backend",
    description="Backend API for the Nagarro's Ascent platform",
    version="1.0.0",
    lifespan=lifespan
)
app.add_middleware(CorrelationIdMiddleware)

# Mount routers (Step 5 modularization)
app.include_router(projects_router.router)
app.include_router(llm_router.router)
app.include_router(health_router.router)
app.include_router(project_analysis_router.router)

# CORS configuration for both local development and Kubernetes deployment
allowed_origins = [
    "http://localhost:3000",  # Local development
    "http://localhost:30300",  # Kubernetes NodePort
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

if __name__ == "__main__":  # pragma: no cover
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True)
