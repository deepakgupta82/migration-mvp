import os
import sys
import tempfile
import logging
import asyncio
from datetime import datetime, timezone
import requests
import json
import re
import uuid
from contextvars import ContextVar
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any, Set, Optional
from pydantic import BaseModel
import subprocess
import psutil
import docker
import time
from functools import lru_cache
from contextlib import asynccontextmanager

from app.core.rag_service import RAGService
from app.core.graph_service import GraphService
from app.core.crew import create_assessment_crew
from app.core.llm_factory import get_llm_and_model, get_project_llm
# from app.core.crew_loader import create_assessment_crew_from_config, get_crew_definitions, update_crew_definitions
from app.core.project_service import (
    ProjectServiceClient,
    ProjectCreate,
    get_llm_configurations_from_db,
    invalidate_llm_cache,
    get_project_service,
)
from app.core.logging_config import init_logging, CorrelationIdMiddleware, correlation_id_ctx
from app.utils.sanitization import sanitize_agent_output, sanitize_for_latex
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

# WebSocket Connection Manager for Real-time Logs
# class LogConnectionManager:
#     def __init__(self):
#         self.active_connections: Dict[str, Set[WebSocket]] = {
#             'backend': set(),
#             'project_service': set(),
#             'reporting_service': set(),
#             'crews_agents': set(),
#             'chromadb': set(),
#             'neo4j': set(),
#             'postgresql': set(),
#             'minio': set(),
#             'megaparse': set(),
#         }
#         self.log_processes: Dict[str, subprocess.Popen] = {}
#         self.clients: Dict[str, Set[WebSocket]] = {}
#
#         # Dedicated rotating file loggers for containerized services
#         # Persist docker logs to files under logs/ with rotation
#         from logging.handlers import RotatingFileHandler
#         self.service_loggers: Dict[str, logging.Logger] = {}
#         for svc in ["neo4j", "postgresql", "minio", "megaparse-service"]:
#             svc_logger = logging.getLogger(f"services.{svc}")
#             if not any(getattr(h, "baseFilename", "").endswith(f"{svc}.log") for h in svc_logger.handlers):
#                 os.makedirs("logs", exist_ok=True)
#                 handler = RotatingFileHandler(f"logs/{svc}.log", maxBytes=5 * 1024 * 1024, backupCount=3)
#                 handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
#                 svc_logger.addHandler(handler)
#                 svc_logger.setLevel(logging.INFO)
#             self.service_loggers[svc] = svc_logger
#
#     async def connect(self, websocket: WebSocket, service: str):
#         await websocket.accept()
#         if service not in self.active_connections:
#             self.active_connections[service] = set()
#         self.active_connections[service].add(websocket)
#         logger.info(f"WebSocket connected for {service} logs")
#
#     def disconnect(self, websocket: WebSocket, service: str):
#         if service in self.active_connections:
#             self.active_connections[service].discard(websocket)
#         logger.info(f"WebSocket disconnected for {service} logs")
#
#     async def send_log(self, service: str, message: dict):
#         if service in self.active_connections:
#             disconnected = set()
#             for connection in self.active_connections[service]:
#                 try:
#                     await connection.send_text(json.dumps(message))
#                 except:
#                     disconnected.add(connection)
#
#             # Remove disconnected connections
#             for conn in disconnected:
#                 self.active_connections[service].discard(conn)
#
#     def start_log_streaming(self, service: str):
#         """Start streaming logs for a specific service"""
#         if service in self.log_processes:
#             return  # Already streaming
#
#         try:
#             if service == 'backend':
#                 # Stream backend logs - use PowerShell Get-Content for Windows
#                 if os.name == 'nt':  # Windows
#                     process = subprocess.Popen(
#                         ['powershell', '-Command', 'Get-Content', 'logs/platform.log', '-Wait', '-Tail', '100'],
#                         stdout=subprocess.PIPE,
#                         stderr=subprocess.PIPE,
#                         text=True,
#                         bufsize=1,
#                         universal_newlines=True
#                     )
#                 else:  # Unix/Linux
#                     process = subprocess.Popen(
#                         ['tail', '-f', 'logs/platform.log'],
#                         stdout=subprocess.PIPE,
#                         stderr=subprocess.PIPE,
#                         text=True,
#                         bufsize=1,
#                         universal_newlines=True
# )
#             elif service in ['neo4j', 'postgresql', 'minio', 'megaparse-service']:
#                 # Stream Docker container logs - use actual container names
#                 container_names = {
#                     'neo4j': 'neo4j_service',
#                     'postgresql': 'postgres_service',
#                     'minio': 'minio_service',
#                     'megaparse-service': 'megaparse_service'
#                 }
#                 container_name = container_names.get(service, service)
#                 try:
#                     process = subprocess.Popen(
#                         ['docker', 'logs', '-f', '--tail', '100', container_name],
#                         stdout=subprocess.PIPE,
#                         stderr=subprocess.PIPE,
#                         text=True,
#                         bufsize=1,
#                         universal_newlines=True
#                     )
#
#                     self.log_processes[service] = process
#                     logger.info(f"Started Docker log streaming for {service} (container: {container_name})")
#
#                     # Start reading from the process in a separate thread
#                     import threading
#
#                     def read_docker_logs():
#                         """Read Docker logs and send to WebSocket clients"""
#                         try:
#                             while service in self.log_processes and process.poll() is None:
#                                 # Read from stdout
#                                 if process.stdout:
#                                     line = process.stdout.readline()
#                                     if line:
#                                         timestamp = datetime.now().isoformat()
#                                         log_entry = {
#                                             "timestamp": timestamp,
#                                             "level": "INFO",
#                                             "service": service,
#                                             "message": line.strip()
#                                         }
#
#                                         # Persist to service file logger
#                                         try:
#                                             if service in self.service_loggers:
#                                                 self.service_loggers[service].info(line.strip())
#                                         except Exception:
#                                             pass
#
#                                         # Send to WebSocket clients
#                                         import asyncio
#                                         try:
#                                             loop = asyncio.new_event_loop()
#                                             asyncio.set_event_loop(loop)
#                                             loop.run_until_complete(self.send_log(service, log_entry))
#                                             loop.close()
#                                         except Exception as e:
#                                             logger.error(f"Error sending Docker log for {service}: {e}")
#
#                                 # Read from stderr
#                                 if process.stderr:
#                                     error_line = process.stderr.readline()
#                                     if error_line:
#                                         timestamp = datetime.now().isoformat()
#                                         log_entry = {
#                                             "timestamp": timestamp,
#                                             "level": "ERROR",
#                                             "service": service,
#                                             "message": error_line.strip()
#                                         }
#
#                                         # Persist to service file logger
#                                         try:
#                                             if service in self.service_loggers:
#                                                 self.service_loggers[service].error(error_line.strip())
#                                         except Exception:
#                                             pass
#
#                                         # Send to WebSocket clients
#                                         import asyncio
#                                         try:
#                                             loop = asyncio.new_event_loop()
#                                             asyncio.set_event_loop(loop)
#                                             loop.run_until_complete(self.send_log(service, log_entry))
#                                             loop.close()
#                                         except Exception as e:
#                                             logger.error(f"Error sending Docker error log for {service}: {e}")
#
#                         except Exception as e:
#                             logger.error(f"Error reading Docker logs for {service}: {e}")
#                         finally:
#                             if process and process.poll() is None:
#                                 process.terminate()
#
#                     # Start the log reading thread
#                     thread = threading.Thread(target=read_docker_logs, daemon=True)
#                     thread.start()
#                     return
#
#                 except Exception as e:
#                     logger.error(f"Failed to start Docker log streaming for {service}: {e}")
#                     return
#             else:
#                 # For other services, try to capture their stdout/stderr directly
#                 service_ports = {
#                     'project_service': 8002,
#                     'reporting_service': 8001,
#                     'crews_agents': None
#                 }
#
#                 if service == 'project_service':
#                     # Try to capture project service logs from its stdout
#                     # Since it's running in a separate terminal, we'll generate informative logs
#                     import threading
#                     import time
#
#                     def generate_service_logs():
#                         """Generate service status logs"""
#                         counter = 0
#                         while service in self.log_processes:
#                             counter += 1
#                             timestamp = datetime.now().isoformat()
#
#                             # Check if service is responding
#                             try:
#                                 import requests
#                                 response = requests.get(f"http://localhost:8002/health", timeout=2)
#                                 if response.status_code == 200:
#                                     message = f"[{service}] Service healthy - responded with status 200"
#                                     level = "INFO"
#                                 else:
#                                     message = f"[{service}] Service responded with status {response.status_code}"
#                                     level = "WARNING"
#                             except Exception as e:
#                                 message = f"[{service}] Service check failed: {str(e)}"
#                                 level = "ERROR"
#
#                             log_entry = {
#                                 "timestamp": timestamp,
#                                 "level": level,
#                                 "service": service,
#                                 "message": message
#                             }
#
#                             # Send to all connected WebSocket clients
#                             try:
#                                 import asyncio
#                                 loop = asyncio.new_event_loop()
#                                 asyncio.set_event_loop(loop)
#                                 loop.run_until_complete(self.send_log(service, log_entry))
#                                 loop.close()
#                             except Exception as e:
#                                 logger.error(f"Error sending service log for {service}: {e}")
#
#                             time.sleep(10)  # Check every 10 seconds
#
#                     # Start service log generation in a separate thread
#                     thread = threading.Thread(target=generate_service_logs, daemon=True)
#                     thread.start()
#                     self.log_processes[service] = thread
#                     logger.info(f"Started service monitoring for {service}")
#                     return
#                 else:
#                     # For other services, generate basic heartbeat logs
#                     import threading
#                     import time
#
#                     def generate_basic_logs():
#                         """Generate basic service logs"""
#                         counter = 0
#                         while service in self.log_processes:
#                             counter += 1
#                             timestamp = datetime.now().isoformat()
#                             log_entry = {
#                                 "timestamp": timestamp,
#                                 "level": "INFO",
#                                 "service": service,
#                                 "message": f"[{service}] Service heartbeat #{counter} - monitoring active"
#                             }
#
#                             # Send to all connected WebSocket clients
#                             try:
#                                 import asyncio
#                                 loop = asyncio.new_event_loop()
#                                 asyncio.set_event_loop(loop)
#                                 loop.run_until_complete(self.send_log(service, log_entry))
#                                 loop.close()
#                             except Exception as e:
#                                 logger.error(f"Error sending basic log for {service}: {e}")
#
#                             time.sleep(15)  # Send a log every 15 seconds
#
#                     # Start basic log generation in a separate thread
#                     thread = threading.Thread(target=generate_basic_logs, daemon=True)
#                     thread.start()
#                     self.log_processes[service] = thread
#                     logger.info(f"Started basic monitoring for {service}")
#                     return
#
#             self.log_processes[service] = process
#             logger.info(f"Started log streaming for {service}")
#
#         except Exception as e:
#             logger.error(f"Failed to start log streaming for {service}: {e}")
#
#     def stop_log_streaming(self, service: str):
#         """Stop streaming logs for a specific service"""
#         if service in self.log_processes:
#             try:
#                 self.log_processes[service].terminate()
#                 del self.log_processes[service]
#                 logger.info(f"Stopped log streaming for {service}")
#             except Exception as e:
#                 logger.error(f"Failed to stop log streaming for {service}: {e}")
#
#     async def start_console_streaming(self, service: str, websocket):
#         """Start streaming raw console output for a specific service/container"""
#         console_key = f"{service}_console"
#
#         if console_key in self.log_processes:
#             return  # Already streaming
#
#         try:
#             # Map service names to container names
#             container_names = {
#                 'backend': 'backend_service',
#                 'project_service': 'project_service',
#                 'reporting_service': 'reporting_service',
#                 'neo4j': 'neo4j_service',
#                 'postgresql': 'postgres_service',
#                 'minio': 'minio_service'
#             }
#
#             container_name = container_names.get(service, service)
#
#             # Start Docker logs streaming for console output
#             process = subprocess.Popen(
#                 ['docker', 'logs', '-f', '--tail', '50', container_name],
#                 stdout=subprocess.PIPE,
#                 stderr=subprocess.PIPE,
#                 text=True,
#                 bufsize=1,
#                 universal_newlines=True
#             )
#
#             self.log_processes[console_key] = process
#             logger.info(f"Started console streaming for {service} (container: {container_name})")
#
#             # Start reading from the process in a separate thread
#             import threading
#
#             def read_console_output():
#                 """Read raw console output and send to WebSocket clients"""
#                 try:
#                     while console_key in self.log_processes and process.poll() is None:
#                         # Read from stdout
#                         if process.stdout:
#                             line = process.stdout.readline()
#                             if line:
#                                 timestamp = datetime.now().isoformat()
#                                 console_entry = {
#                                     "timestamp": timestamp,
#                                     "level": "INFO",
#                                     "service": service,
#                                     "message": line.rstrip(),  # Raw console output
#                                     "raw": line.rstrip()
#                                 }
#
#                                 # Send to WebSocket clients
#                                 import asyncio
#                                 try:
#                                     loop = asyncio.new_event_loop()
#                                     asyncio.set_event_loop(loop)
#                                     loop.run_until_complete(self.send_console_log(console_key, console_entry))
#                                     loop.close()
#                                 except Exception as e:
#                                     logger.error(f"Error sending console log for {service}: {e}")
#
#                         # Read from stderr
#                         if process.stderr:
#                             error_line = process.stderr.readline()
#                             if error_line:
#                                 timestamp = datetime.now().isoformat()
#                                 console_entry = {
#                                     "timestamp": timestamp,
#                                     "level": "ERROR",
#                                     "service": service,
#                                     "message": error_line.rstrip(),
#                                     "raw": error_line.rstrip()
#                                 }
#
#                                 # Send to WebSocket clients
#                                 import asyncio
#                                 try:
#                                     loop = asyncio.new_event_loop()
#                                     asyncio.set_event_loop(loop)
#                                     loop.run_until_complete(self.send_console_log(console_key, console_entry))
#                                     loop.close()
#                                 except Exception as e:
#                                     logger.error(f"Error sending console error for {service}: {e}")
#
#                 except Exception as e:
#                     logger.error(f"Error reading console output for {service}: {e}")
#                 finally:
#                     if process and process.poll() is None:
#                         process.terminate()
#
#             # Start the console reading thread
#             thread = threading.Thread(target=read_console_output, daemon=True)
#             thread.start()
#
#         except Exception as e:
#             logger.error(f"Failed to start console streaming for {service}: {e}")
#
#     async def send_console_log(self, console_key: str, log_entry: dict):
#         """Send console log to all connected WebSocket clients for this console stream"""
#         if console_key in self.clients:
#             disconnected = []
#             for websocket in self.clients[console_key].copy():
#                 try:
#                     await websocket.send_json(log_entry)
#                 except Exception as e:
#                     logger.error(f"Failed to send console log to client: {e}")
#                     disconnected.append(websocket)
#
#             # Remove disconnected clients
#             for conn in disconnected:
#                 self.clients[console_key].discard(conn)

# NOTE: get_project_service now imported from core.project_service (cached singleton)

# Functional endpoints reside in routers; main keeps only websocket wiring + legacy stubs.

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
                                        "level": "INFO",  # Default level, can be parsed from line
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True)

# Deprecated legacy (pre-router) Project endpoints ----------------------------
# (Keep these 410 stubs to signal migration; remove later once clients updated)
@app.post("/projects")
async def create_project_endpoint(request: dict):  # pragma: no cover
    raise HTTPException(status_code=410, detail="Deprecated. Use POST /api/projects/")

@app.get("/projects")
async def list_projects_legacy():  # pragma: no cover
    raise HTTPException(status_code=410, detail="Deprecated. Use GET /api/projects/")

@app.get("/projects/stats")
async def get_projects_stats_legacy():  # pragma: no cover
    raise HTTPException(status_code=410, detail="Deprecated. Use GET /api/projects/stats")

@app.get("/projects/{project_id}")
async def get_project_legacy(project_id: str):  # pragma: no cover
    raise HTTPException(status_code=410, detail="Deprecated. Use GET /api/projects/{project_id}")

@app.put("/projects/{project_id}")
async def update_project_legacy(project_id: str, project_data: dict):  # pragma: no cover
    raise HTTPException(status_code=410, detail="Deprecated. Use PUT /api/projects/{project_id}")

@app.delete("/projects/{project_id}")
async def delete_project_legacy(project_id: str):  # pragma: no cover
    raise HTTPException(status_code=410, detail="Deprecated. Use DELETE /api/projects/{project_id}")

# Deprecated legacy LLM configuration endpoints (moved to /api/llm/configurations)
@app.get("/llm-configurations")
async def get_llm_configurations_legacy():  # pragma: no cover
    raise HTTPException(status_code=410, detail="Deprecated. Use GET /api/llm/configurations")

@app.post("/llm-configurations")
async def create_llm_configuration_legacy(request: dict):  # pragma: no cover
    raise HTTPException(status_code=410, detail="Deprecated. Use POST /api/llm/configurations")

@app.put("/llm-configurations/{config_id}")
async def update_llm_configuration_legacy(config_id: str, request: dict):  # pragma: no cover
    raise HTTPException(status_code=410, detail="Deprecated. Use PUT /api/llm/configurations/{config_id}")

@app.delete("/llm-configurations/{config_id}")
async def delete_llm_configuration_legacy(config_id: str):  # pragma: no cover
    raise HTTPException(status_code=410, detail="Deprecated. Use DELETE /api/llm/configurations/{config_id}")
