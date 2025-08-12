import os
import json
import time
import asyncio
import logging
import threading
import subprocess
from datetime import datetime
from typing import Dict, Set
from fastapi import WebSocket

logger = logging.getLogger("platform.log_stream")

class LogConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {
            'backend': set(), 'project_service': set(), 'reporting_service': set(),
            'crews_agents': set(), 'chromadb': set(), 'neo4j': set(), 'postgresql': set(),
            'minio': set(), 'megaparse': set(),
        }
        self.log_processes: Dict[str, subprocess.Popen] = {}
        self.clients: Dict[str, Set[WebSocket]] = {}
        from logging.handlers import RotatingFileHandler
        self.service_loggers: Dict[str, logging.Logger] = {}
        for svc in ["neo4j", "postgresql", "minio", "megaparse-service"]:
            svc_logger = logging.getLogger(f"services.{svc}")
            if not any(getattr(h, "baseFilename", "").endswith(f"{svc}.log") for h in svc_logger.handlers):
                os.makedirs("logs", exist_ok=True)
                handler = RotatingFileHandler(f"logs/{svc}.log", maxBytes=5*1024*1024, backupCount=3)
                handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
                svc_logger.addHandler(handler)
                svc_logger.setLevel(logging.INFO)
            self.service_loggers[svc] = svc_logger

    async def connect(self, websocket: WebSocket, service: str):
        await websocket.accept()
        self.active_connections.setdefault(service, set()).add(websocket)
        logger.info(f"WebSocket connected for {service} logs")

    def disconnect(self, websocket: WebSocket, service: str):
        if service in self.active_connections:
            self.active_connections[service].discard(websocket)
        logger.info(f"WebSocket disconnected for {service} logs")

    async def send_log(self, service: str, message: dict):
        if service not in self.active_connections:
            return
        disconnected = set()
        for connection in self.active_connections[service]:
            try:
                await connection.send_text(json.dumps(message))
            except Exception:
                disconnected.add(connection)
        for conn in disconnected:
            self.active_connections[service].discard(conn)

    def start_log_streaming(self, service: str):
        if service in self.log_processes:
            return
        try:
            if service == 'backend':
                if os.name == 'nt':
                    process = subprocess.Popen(
                        ['powershell', '-Command', 'Get-Content', 'logs/platform.log', '-Wait', '-Tail', '100'],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, universal_newlines=True)
                else:
                    process = subprocess.Popen(
                        ['tail', '-f', 'logs/platform.log'],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, universal_newlines=True)
            elif service in ['neo4j', 'postgresql', 'minio', 'megaparse-service']:
                container_names = {
                    'neo4j': 'neo4j_service', 'postgresql': 'postgres_service',
                    'minio': 'minio_service', 'megaparse-service': 'megaparse_service'
                }
                container_name = container_names.get(service, service)
                process = subprocess.Popen(
                    ['docker', 'logs', '-f', '--tail', '100', container_name],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, universal_newlines=True)
                self.log_processes[service] = process
                logger.info(f"Started Docker log streaming for {service}")
                def read_docker_logs():
                    try:
                        while service in self.log_processes and process.poll() is None:
                            if process.stdout:
                                line = process.stdout.readline()
                                if line:
                                    self._emit_line(service, line, 'INFO')
                            if process.stderr:
                                err = process.stderr.readline()
                                if err:
                                    self._emit_line(service, err, 'ERROR')
                    except Exception as e:
                        logger.error(f"Error reading Docker logs for {service}: {e}")
                    finally:
                        if process and process.poll() is None:
                            process.terminate()
                threading.Thread(target=read_docker_logs, daemon=True).start()
                return
            else:
                # Generic heartbeat for unknown services
                def generate_basic_logs():
                    counter = 0
                    while service in self.log_processes:
                        counter += 1
                        msg = {
                            "timestamp": datetime.now().isoformat(),
                            "level": "INFO",
                            "service": service,
                            "message": f"[{service}] Service heartbeat #{counter} - monitoring active"
                        }
                        try:
                            asyncio.run(self.send_log(service, msg))
                        except RuntimeError:
                            # Running inside loop; schedule instead
                            loop = asyncio.get_event_loop()
                            loop.create_task(self.send_log(service, msg))
                        time.sleep(15)
                t = threading.Thread(target=generate_basic_logs, daemon=True)
                t.start()
                self.log_processes[service] = t
                logger.info(f"Started basic monitoring for {service}")
                return
            self.log_processes[service] = process
        except Exception as e:
            logger.error(f"Failed to start log streaming for {service}: {e}")

    def _emit_line(self, service: str, line: str, level: str):
        # Infer WARNING from content if not explicitly marked as ERROR
        inferred_level = level
        try:
            content_lower = (line or "").lower()
            if level != 'ERROR' and (' warning ' in f' {content_lower} ' or '[warn' in content_lower or content_lower.startswith('warn')):
                inferred_level = 'WARNING'
        except Exception:
            pass

        def _style_for_level(lvl: str):
            # Return simple style hints for consumers (e.g., frontend) to color backgrounds
            # Colors use light backgrounds to distinguish quickly
            if lvl == 'ERROR':
                return {"bg": "#fdecea", "fg": "#611a15"}  # light red
            if lvl == 'WARNING':
                return {"bg": "#fff4e5", "fg": "#663c00"}  # light orange
            return None

        entry = {
            "timestamp": datetime.now().isoformat(),
            "level": inferred_level,
            "service": service,
            "message": line.strip(),
            "style": _style_for_level(inferred_level),
        }
        # Optional ANSI rendering for terminal consumers
        try:
            if inferred_level == 'ERROR':
                entry["ansi"] = f"\x1b[41;30m{line.strip()}\x1b[0m"  # red bg, black fg
            elif inferred_level == 'WARNING':
                entry["ansi"] = f"\x1b[43;30m{line.strip()}\x1b[0m"  # yellow bg, black fg
        except Exception:
            pass
        try:
            if service in self.service_loggers:
                if inferred_level == 'ERROR':
                    self.service_loggers[service].error(line.strip())
                elif inferred_level == 'WARNING':
                    self.service_loggers[service].warning(line.strip())
                else:
                    self.service_loggers[service].info(line.strip())
        except Exception:
            pass
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.send_log(service, entry))
            loop.close()
        except Exception:
            pass

    def stop_log_streaming(self, service: str):
        if service in self.log_processes:
            proc = self.log_processes[service]
            try:
                if hasattr(proc, 'terminate'):
                    proc.terminate()
            except Exception:
                pass
            del self.log_processes[service]

    async def start_console_streaming(self, service: str, websocket: WebSocket):
        console_key = f"{service}_console"
        if console_key in self.log_processes:
            return
        container_names = {
            'backend': 'backend_service', 'project_service': 'project_service',
            'reporting_service': 'reporting_service', 'neo4j': 'neo4j_service',
            'postgresql': 'postgres_service', 'minio': 'minio_service'
        }
        container_name = container_names.get(service, service)
        try:
            process = subprocess.Popen(
                ['docker', 'logs', '-f', '--tail', '50', container_name],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, universal_newlines=True)
            self.log_processes[console_key] = process
            def read_console():
                try:
                    while console_key in self.log_processes and process.poll() is None:
                        if process.stdout:
                            line = process.stdout.readline()
                            if line:
                                self._emit_console(console_key, service, line, 'INFO')
                        if process.stderr:
                            err = process.stderr.readline()
                            if err:
                                self._emit_console(console_key, service, err, 'ERROR')
                finally:
                    if process and process.poll() is None:
                        process.terminate()
            threading.Thread(target=read_console, daemon=True).start()
        except Exception as e:
            logger.error(f"Failed to start console streaming for {service}: {e}")

    async def send_console_log(self, console_key: str, log_entry: dict):
        if console_key in self.clients:
            disconnected = []
            for ws in self.clients[console_key].copy():
                try:
                    await ws.send_json(log_entry)
                except Exception:
                    disconnected.append(ws)
            for conn in disconnected:
                self.clients[console_key].discard(conn)

    def _emit_console(self, console_key: str, service: str, line: str, level: str):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "service": service,
            "message": line.rstrip(),
            "raw": line.rstrip()
        }
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.send_console_log(console_key, entry))
            loop.close()
        except Exception:
            pass

log_manager = LogConnectionManager()
