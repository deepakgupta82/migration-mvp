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
from app.core.rag_service import RAGService
from app.core.graph_service import GraphService
from app.core.crew import create_assessment_crew, get_llm_and_model, get_project_llm
# from app.core.crew_loader import create_assessment_crew_from_config, get_crew_definitions, update_crew_definitions
from app.core.project_service import ProjectServiceClient, ProjectCreate
from app.core.logging_config import init_logging, CorrelationIdMiddleware, correlation_id_ctx
from app.utils.sanitization import sanitize_agent_output, sanitize_for_latex

# Logging setup with UTF-8 encoding
init_logging()

# Load environment variables from .env file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

app = FastAPI(
    title="Nagarro's Ascent Backend",
    description="Backend API for the Nagarro's Ascent platform",
    version="1.0.0"
)
app.add_middleware(CorrelationIdMiddleware)

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
class LogConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {
            'backend': set(),
            'project_service': set(),
            'reporting_service': set(),
            'crews_agents': set(),
            'chromadb': set(),
            'neo4j': set(),
            'postgresql': set(),
            'minio': set(),
            'megaparse': set(),
        }
        self.log_processes: Dict[str, subprocess.Popen] = {}
        self.clients: Dict[str, Set[WebSocket]] = {}

        # Dedicated rotating file loggers for containerized services
        # Persist docker logs to files under logs/ with rotation
        from logging.handlers import RotatingFileHandler
        self.service_loggers: Dict[str, logging.Logger] = {}
        for svc in ["neo4j", "postgresql", "minio", "megaparse-service"]:
            svc_logger = logging.getLogger(f"services.{svc}")
            if not any(getattr(h, "baseFilename", "").endswith(f"{svc}.log") for h in svc_logger.handlers):
                os.makedirs("logs", exist_ok=True)
                handler = RotatingFileHandler(f"logs/{svc}.log", maxBytes=5 * 1024 * 1024, backupCount=3)
                handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
                svc_logger.addHandler(handler)
                svc_logger.setLevel(logging.INFO)
            self.service_loggers[svc] = svc_logger

    async def connect(self, websocket: WebSocket, service: str):
        await websocket.accept()
        if service not in self.active_connections:
            self.active_connections[service] = set()
        self.active_connections[service].add(websocket)
        logger.info(f"WebSocket connected for {service} logs")

    def disconnect(self, websocket: WebSocket, service: str):
        if service in self.active_connections:
            self.active_connections[service].discard(websocket)
        logger.info(f"WebSocket disconnected for {service} logs")

    async def send_log(self, service: str, message: dict):
        if service in self.active_connections:
            disconnected = set()
            for connection in self.active_connections[service]:
                try:
                    await connection.send_text(json.dumps(message))
                except:
                    disconnected.add(connection)

            # Remove disconnected connections
            for conn in disconnected:
                self.active_connections[service].discard(conn)

    def start_log_streaming(self, service: str):
        """Start streaming logs for a specific service"""
        if service in self.log_processes:
            return  # Already streaming

        try:
            if service == 'backend':
                # Stream backend logs - use PowerShell Get-Content for Windows
                if os.name == 'nt':  # Windows
                    process = subprocess.Popen(
                        ['powershell', '-Command', 'Get-Content', 'logs/platform.log', '-Wait', '-Tail', '100'],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        bufsize=1,
                        universal_newlines=True
                    )
                else:  # Unix/Linux
                    process = subprocess.Popen(
                        ['tail', '-f', 'logs/platform.log'],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        bufsize=1,
                        universal_newlines=True
)
            elif service in ['neo4j', 'postgresql', 'minio', 'megaparse-service']:
                # Stream Docker container logs - use actual container names
                container_names = {
                    'neo4j': 'neo4j_service',
                    'postgresql': 'postgres_service',
                    'minio': 'minio_service',
                    'megaparse-service': 'megaparse_service'
                }
                container_name = container_names.get(service, service)
                try:
                    process = subprocess.Popen(
                        ['docker', 'logs', '-f', '--tail', '100', container_name],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        bufsize=1,
                        universal_newlines=True
                    )

                    self.log_processes[service] = process
                    logger.info(f"Started Docker log streaming for {service} (container: {container_name})")

                    # Start reading from the process in a separate thread
                    import threading

                    def read_docker_logs():
                        """Read Docker logs and send to WebSocket clients"""
                        try:
                            while service in self.log_processes and process.poll() is None:
                                # Read from stdout
                                if process.stdout:
                                    line = process.stdout.readline()
                                    if line:
                                        timestamp = datetime.now().isoformat()
                                        log_entry = {
                                            "timestamp": timestamp,
                                            "level": "INFO",
                                            "service": service,
                                            "message": line.strip()
                                        }

                                        # Persist to service file logger
                                        try:
                                            if service in self.service_loggers:
                                                self.service_loggers[service].info(line.strip())
                                        except Exception:
                                            pass

                                        # Send to WebSocket clients
                                        import asyncio
                                        try:
                                            loop = asyncio.new_event_loop()
                                            asyncio.set_event_loop(loop)
                                            loop.run_until_complete(self.send_log(service, log_entry))
                                            loop.close()
                                        except Exception as e:
                                            logger.error(f"Error sending Docker log for {service}: {e}")

                                # Read from stderr
                                if process.stderr:
                                    error_line = process.stderr.readline()
                                    if error_line:
                                        timestamp = datetime.now().isoformat()
                                        log_entry = {
                                            "timestamp": timestamp,
                                            "level": "ERROR",
                                            "service": service,
                                            "message": error_line.strip()
                                        }

                                        # Persist to service file logger
                                        try:
                                            if service in self.service_loggers:
                                                self.service_loggers[service].error(error_line.strip())
                                        except Exception:
                                            pass

                                        # Send to WebSocket clients
                                        import asyncio
                                        try:
                                            loop = asyncio.new_event_loop()
                                            asyncio.set_event_loop(loop)
                                            loop.run_until_complete(self.send_log(service, log_entry))
                                            loop.close()
                                        except Exception as e:
                                            logger.error(f"Error sending Docker error log for {service}: {e}")

                        except Exception as e:
                            logger.error(f"Error reading Docker logs for {service}: {e}")
                        finally:
                            if process and process.poll() is None:
                                process.terminate()

                    # Start the log reading thread
                    thread = threading.Thread(target=read_docker_logs, daemon=True)
                    thread.start()
                    return

                except Exception as e:
                    logger.error(f"Failed to start Docker log streaming for {service}: {e}")
                    return
            else:
                # For other services, try to capture their stdout/stderr directly
                service_ports = {
                    'project_service': 8002,
                    'reporting_service': 8001,
                    'crews_agents': None
                }

                if service == 'project_service':
                    # Try to capture project service logs from its stdout
                    # Since it's running in a separate terminal, we'll generate informative logs
                    import threading
                    import time

                    def generate_service_logs():
                        """Generate service status logs"""
                        counter = 0
                        while service in self.log_processes:
                            counter += 1
                            timestamp = datetime.now().isoformat()

                            # Check if service is responding
                            try:
                                import requests
                                response = requests.get(f"http://localhost:8002/health", timeout=2)
                                if response.status_code == 200:
                                    message = f"[{service}] Service healthy - responded with status 200"
                                    level = "INFO"
                                else:
                                    message = f"[{service}] Service responded with status {response.status_code}"
                                    level = "WARNING"
                            except Exception as e:
                                message = f"[{service}] Service check failed: {str(e)}"
                                level = "ERROR"

                            log_entry = {
                                "timestamp": timestamp,
                                "level": level,
                                "service": service,
                                "message": message
                            }

                            # Send to all connected WebSocket clients
                            try:
                                import asyncio
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                                loop.run_until_complete(self.send_log(service, log_entry))
                                loop.close()
                            except Exception as e:
                                logger.error(f"Error sending service log for {service}: {e}")

                            time.sleep(10)  # Check every 10 seconds

                    # Start service log generation in a separate thread
                    thread = threading.Thread(target=generate_service_logs, daemon=True)
                    thread.start()
                    self.log_processes[service] = thread
                    logger.info(f"Started service monitoring for {service}")
                    return
                else:
                    # For other services, generate basic heartbeat logs
                    import threading
                    import time

                    def generate_basic_logs():
                        """Generate basic service logs"""
                        counter = 0
                        while service in self.log_processes:
                            counter += 1
                            timestamp = datetime.now().isoformat()
                            log_entry = {
                                "timestamp": timestamp,
                                "level": "INFO",
                                "service": service,
                                "message": f"[{service}] Service heartbeat #{counter} - monitoring active"
                            }

                            # Send to all connected WebSocket clients
                            try:
                                import asyncio
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                                loop.run_until_complete(self.send_log(service, log_entry))
                                loop.close()
                            except Exception as e:
                                logger.error(f"Error sending basic log for {service}: {e}")

                            time.sleep(15)  # Send a log every 15 seconds

                    # Start basic log generation in a separate thread
                    thread = threading.Thread(target=generate_basic_logs, daemon=True)
                    thread.start()
                    self.log_processes[service] = thread
                    logger.info(f"Started basic monitoring for {service}")
                    return

            self.log_processes[service] = process
            logger.info(f"Started log streaming for {service}")

        except Exception as e:
            logger.error(f"Failed to start log streaming for {service}: {e}")

    def stop_log_streaming(self, service: str):
        """Stop streaming logs for a specific service"""
        if service in self.log_processes:
            try:
                self.log_processes[service].terminate()
                del self.log_processes[service]
                logger.info(f"Stopped log streaming for {service}")
            except Exception as e:
                logger.error(f"Failed to stop log streaming for {service}: {e}")

    async def start_console_streaming(self, service: str, websocket):
        """Start streaming raw console output for a specific service/container"""
        console_key = f"{service}_console"

        if console_key in self.log_processes:
            return  # Already streaming

        try:
            # Map service names to container names
            container_names = {
                'backend': 'backend_service',
                'project_service': 'project_service',
                'reporting_service': 'reporting_service',
                'neo4j': 'neo4j_service',
                'postgresql': 'postgres_service',
                'minio': 'minio_service'
            }

            container_name = container_names.get(service, service)

            # Start Docker logs streaming for console output
            process = subprocess.Popen(
                ['docker', 'logs', '-f', '--tail', '50', container_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            self.log_processes[console_key] = process
            logger.info(f"Started console streaming for {service} (container: {container_name})")

            # Start reading from the process in a separate thread
            import threading

            def read_console_output():
                """Read raw console output and send to WebSocket clients"""
                try:
                    while console_key in self.log_processes and process.poll() is None:
                        # Read from stdout
                        if process.stdout:
                            line = process.stdout.readline()
                            if line:
                                timestamp = datetime.now().isoformat()
                                console_entry = {
                                    "timestamp": timestamp,
                                    "level": "INFO",
                                    "service": service,
                                    "message": line.rstrip(),  # Raw console output
                                    "raw": line.rstrip()
                                }

                                # Send to WebSocket clients
                                import asyncio
                                try:
                                    loop = asyncio.new_event_loop()
                                    asyncio.set_event_loop(loop)
                                    loop.run_until_complete(self.send_console_log(console_key, console_entry))
                                    loop.close()
                                except Exception as e:
                                    logger.error(f"Error sending console log for {service}: {e}")

                        # Read from stderr
                        if process.stderr:
                            error_line = process.stderr.readline()
                            if error_line:
                                timestamp = datetime.now().isoformat()
                                console_entry = {
                                    "timestamp": timestamp,
                                    "level": "ERROR",
                                    "service": service,
                                    "message": error_line.rstrip(),
                                    "raw": error_line.rstrip()
                                }

                                # Send to WebSocket clients
                                import asyncio
                                try:
                                    loop = asyncio.new_event_loop()
                                    asyncio.set_event_loop(loop)
                                    loop.run_until_complete(self.send_console_log(console_key, console_entry))
                                    loop.close()
                                except Exception as e:
                                    logger.error(f"Error sending console error for {service}: {e}")

                except Exception as e:
                    logger.error(f"Error reading console output for {service}: {e}")
                finally:
                    if process and process.poll() is None:
                        process.terminate()

            # Start the console reading thread
            thread = threading.Thread(target=read_console_output, daemon=True)
            thread.start()

        except Exception as e:
            logger.error(f"Failed to start console streaming for {service}: {e}")

    async def send_console_log(self, console_key: str, log_entry: dict):
        """Send console log to all connected WebSocket clients for this console stream"""
        if console_key in self.clients:
            disconnected = []
            for websocket in self.clients[console_key].copy():
                try:
                    await websocket.send_json(log_entry)
                except Exception as e:
                    logger.error(f"Failed to send console log to client: {e}")
                    disconnected.append(websocket)

            # Remove disconnected clients
            for conn in disconnected:
                self.clients[console_key].discard(conn)

log_manager = LogConnectionManager()

# Lazy initialization for project service
_project_service = None

def get_project_service():
    """Lazy load project service to improve startup time"""
    global _project_service
    if _project_service is None:
        _project_service = ProjectServiceClient()
    return _project_service

# LLM Configurations now stored in database via project service
# Cache for performance
llm_configurations_cache = {}
last_cache_update = None

def get_llm_configurations_from_db():
    """Get LLM configurations from project service database with caching"""
    global llm_configurations_cache, last_cache_update

    # Check if cache is still valid (cache for 30 seconds)
    import time
    current_time = time.time()
    if last_cache_update and (current_time - last_cache_update) < 30:
        return llm_configurations_cache

    try:
        project_service = get_project_service()
        response = requests.get(
            f"{project_service.base_url}/llm-configurations",
            headers=project_service._get_auth_headers(),
            timeout=5  # Add timeout to prevent hanging
        )

        if response.status_code == 200:
            configs_list = response.json()
            # Convert to dict format for backward compatibility
            llm_configurations_cache = {
                config['id']: config for config in configs_list
            }
            last_cache_update = current_time
            logger.info(f"Loaded {len(llm_configurations_cache)} LLM configurations from database")
        else:
            logger.error(f"Failed to load LLM configurations: {response.status_code}")
            logger.error(f"Response: {response.text}")
            # Fallback to JSON file
            raise Exception("Database load failed, falling back to JSON")

    except Exception as e:
        logger.warning(f"Error loading LLM configurations from database: {e}")
        logger.info("Falling back to JSON file for LLM configurations")

        # Fallback to JSON file
        try:
            import json
            json_path = os.path.join(os.path.dirname(__file__), "llm_configurations.json")
            if os.path.exists(json_path):
                with open(json_path, 'r') as f:
                    llm_configurations_cache = json.load(f)
                last_cache_update = current_time
                logger.info(f"Loaded {len(llm_configurations_cache)} LLM configurations from JSON file")
            else:
                logger.error("No LLM configurations JSON file found")
        except Exception as json_error:
            logger.error(f"Error loading LLM configurations from JSON: {json_error}")

    return llm_configurations_cache

def invalidate_llm_cache():
    """Invalidate the LLM configurations cache"""
    global last_cache_update, llm_configurations_cache
    last_cache_update = None
    llm_configurations_cache = {}

# Pydantic models for API requests/responses
class QueryRequest(BaseModel):
    question: str

class QueryResponse(BaseModel):
    answer: str
    project_id: str

class GraphResponse(BaseModel):
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]

class ReportResponse(BaseModel):
    project_id: str
    report_content: str

# New API Endpoints
@app.get("/api/projects/{project_id}/graph", response_model=GraphResponse)
async def get_project_graph(project_id: str, type: str = None):
    """Get the Neo4j graph data for a specific project, optionally filtered by type"""
    try:
        graph_service = GraphService()

        logger.info(f"Fetching graph data for project: {project_id}")

        # Query Neo4j for all nodes and relationships for this project
        nodes_query = "MATCH (n {project_id: $project_id}) RETURN n"
        relationships_query = "MATCH (a {project_id: $project_id})-[r]->(b {project_id: $project_id}) RETURN a, r, b"

        # Execute queries
        logger.debug(f"Executing nodes query: {nodes_query}")
        nodes_result = graph_service.execute_query(nodes_query, {"project_id": project_id})
        logger.debug(f"Nodes query returned {len(nodes_result)} results")

        logger.debug(f"Executing relationships query: {relationships_query}")
        relationships_result = graph_service.execute_query(relationships_query, {"project_id": project_id})
        logger.debug(f"Relationships query returned {len(relationships_result)} results")

        # Format nodes
        nodes = []
        if nodes_result:
            for record in nodes_result:
                node = record["n"]
                nodes.append({
                    "id": node.get("name", str(node.id)),
                    "label": node.get("name", "Unknown"),
                    "type": list(node.labels)[0] if node.labels else "Unknown",
                    "properties": dict(node)
                })

        # Format edges
        edges = []
        if relationships_result:
            for record in relationships_result:
                source_node = record["a"]
                target_node = record["b"]
                relationship = record["r"]

                edges.append({
                    "source": source_node.get("name", str(source_node.id)),
                    "target": target_node.get("name", str(target_node.id)),
                    "label": relationship.type,
                    "properties": dict(relationship)
                })

        logger.info(f"Graph query completed: {len(nodes)} nodes, {len(edges)} edges")

        # Filter for infrastructure-related nodes if type=infrastructure
        if type == "infrastructure":
            logger.info(f"Filtering for infrastructure-related nodes")

            # Define infrastructure-related types
            infrastructure_types = {
                'hostname', 'server', 'database', 'application', 'service', 'network',
                'storage', 'load_balancer', 'firewall', 'switch', 'router', 'cluster',
                'system_identifier', 'component_identifier', 'host', 'instance',
                'virtual_machine', 'container', 'pod', 'node', 'endpoint'
            }

            # Filter nodes based on their type property
            infrastructure_nodes = []
            for node in nodes:
                node_type = node.get('properties', {}).get('type', '').lower()
                node_label = node.get('type', '').lower()

                # Check if node type or label matches infrastructure types
                if (node_type in infrastructure_types or
                    node_label in infrastructure_types or
                    any(infra_type in node_type for infra_type in infrastructure_types) or
                    any(infra_type in node_label for infra_type in infrastructure_types)):
                    infrastructure_nodes.append(node)

            # Filter edges to only include those between infrastructure nodes
            infrastructure_node_ids = {node['id'] for node in infrastructure_nodes}
            infrastructure_edges = [
                edge for edge in edges
                if edge['source'] in infrastructure_node_ids and edge['target'] in infrastructure_node_ids
            ]

            logger.info(f"Infrastructure filtering: {len(infrastructure_nodes)} nodes, {len(infrastructure_edges)} edges")
            nodes = infrastructure_nodes
            edges = infrastructure_edges

        # If no data found, log additional debug info
        if len(nodes) == 0:
            logger.warning(f"No graph data found for project {project_id} (type: {type})")
            # Check if any nodes exist for this project at all
            all_nodes_query = "MATCH (n) WHERE n.project_id = $project_id RETURN count(n) as total"
            total_result = graph_service.execute_query(all_nodes_query, {"project_id": project_id})
            total_nodes = total_result[0]["total"] if total_result else 0
            logger.info(f"Total nodes in database for project {project_id}: {total_nodes}")

            # Also check if there are any nodes without project_id filter
            any_nodes_query = "MATCH (n) RETURN count(n) as total LIMIT 1"
            any_result = graph_service.execute_query(any_nodes_query, {})
            any_nodes = any_result[0]["total"] if any_result else 0
            logger.info(f"Total nodes in entire database: {any_nodes}")

        return GraphResponse(nodes=nodes, edges=edges)

    except Exception as e:
        logger.error(f"Error fetching graph for project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching graph data: {str(e)}")

@app.post("/api/projects/{project_id}/clear-data")
async def clear_project_data(project_id: str):
    """Clear all embeddings and knowledge graph data for a specific project"""
    try:
        # Get project from project service
        project_service = get_project_service()
        project = project_service.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Initialize services without loading heavy models
        graph_service = GraphService()

        cleared_items = {
            "chromadb_embeddings": 0,
            "neo4j_nodes": 0,
            "neo4j_relationships": 0
        }

        # Clear ChromaDB embeddings directly without RAGService
        try:
            import chromadb
            import os

            chroma_path = os.getenv("CHROMA_DB_PATH", "./data/chroma_db")
            chroma_client = chromadb.PersistentClient(path=chroma_path)
            collection_name = f"project_{project_id}"

            try:
                # Get the collection and count documents
                collection = chroma_client.get_collection(name=collection_name)
                cleared_items["chromadb_embeddings"] = collection.count()

                if cleared_items["chromadb_embeddings"] > 0:
                    # Delete and recreate collection (fastest way to clear all data)
                    chroma_client.delete_collection(name=collection_name)
                    chroma_client.create_collection(
                        name=collection_name,
                        metadata={"description": f"Document embeddings for project {project_id}"}
                    )
                    logger.info(f"Cleared {cleared_items['chromadb_embeddings']} embeddings from ChromaDB")
                else:
                    logger.info("No embeddings found to clear in ChromaDB")

            except Exception as collection_error:
                if "does not exist" in str(collection_error):
                    logger.info("ChromaDB collection does not exist - nothing to clear")
                    cleared_items["chromadb_embeddings"] = 0
                else:
                    logger.warning(f"Error accessing ChromaDB collection: {collection_error}")
                    cleared_items["chromadb_embeddings"] = 0

        except Exception as e:
            logger.warning(f"Error clearing ChromaDB data: {e}")

        # Clear Neo4j data
        try:
            if graph_service.driver:
                # Count nodes before deletion
                count_result = graph_service.execute_query(
                    "MATCH (n {project_id: $project_id}) RETURN count(n) as node_count",
                    {"project_id": project_id}
                )
                if count_result:
                    cleared_items["neo4j_nodes"] = count_result[0]["node_count"]

                # Count relationships before deletion
                rel_count_result = graph_service.execute_query(
                    "MATCH (a {project_id: $project_id})-[r]-(b {project_id: $project_id}) RETURN count(r) as rel_count",
                    {"project_id": project_id}
                )
                if rel_count_result:
                    cleared_items["neo4j_relationships"] = rel_count_result[0]["rel_count"]

                # Delete all nodes and relationships for this project
                graph_service.execute_query(
                    "MATCH (n {project_id: $project_id}) DETACH DELETE n",
                    {"project_id": project_id}
                )
                logger.info(f"Cleared {cleared_items['neo4j_nodes']} nodes and {cleared_items['neo4j_relationships']} relationships from Neo4j")
        except Exception as e:
            logger.warning(f"Error clearing Neo4j data: {e}")

        # Clear processing stats file to reset UI stats
        try:
            project_dir = os.path.join(UPLOAD_ROOT, f"project_{project_id}")
            processing_stats_file = os.path.join(project_dir, "processing_stats.json")
            if os.path.exists(processing_stats_file):
                os.remove(processing_stats_file)
                logger.info("Cleared processing stats file to reset UI")
        except Exception as e:
            logger.warning(f"Error clearing processing stats file: {e}")

        # Trigger stats update for data clearing
        try:
            from app.core.stats_service import get_stats_service
            stats_service = get_stats_service()
            await stats_service.update_project_stats(
                project_id,
                "data_cleared",
                {
                    "embeddings_cleared": cleared_items["chromadb_embeddings"],
                    "nodes_cleared": cleared_items["neo4j_nodes"],
                    "relationships_cleared": cleared_items["neo4j_relationships"]
                }
            )
        except Exception as stats_error:
            logger.warning(f"Failed to update stats after clearing data: {stats_error}")

        # Return response in format expected by frontend
        return {
            "message": "Project data cleared successfully",
            "project_id": project_id,
            "weaviate_embeddings": cleared_items["chromadb_embeddings"],  # Frontend expects weaviate_embeddings
            "chromadb_embeddings": cleared_items["chromadb_embeddings"],  # Also include new name for compatibility
            "neo4j_nodes": cleared_items["neo4j_nodes"],
            "neo4j_relationships": cleared_items["neo4j_relationships"],
            "cleared_items": cleared_items  # Keep original structure too
        }

    except Exception as e:
        logger.error(f"Error clearing data for project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error clearing project data: {str(e)}")

@app.post("/api/projects/{project_id}/query", response_model=QueryResponse)
async def query_project_knowledge(project_id: str, query_request: QueryRequest):
    """Query the RAG knowledge base for a specific project"""
    try:
        # Get project from project service
        project_service = get_project_service()
        project = project_service.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Get project-specific LLM - NO FALLBACKS
        try:
            llm = get_project_llm(project)
            logger.info(f"Using project LLM: {project.llm_provider}/{project.llm_model}")
        except Exception as llm_error:
            logger.error(f"Project LLM configuration error: {str(llm_error)}")
            raise HTTPException(
                status_code=500,
                detail=f"LLM configuration error for project {project_id}: {str(llm_error)}"
            )

        # Initialize RAG service with project LLM
        rag_service = RAGService(project_id, llm)

        # Query the knowledge base
        answer = rag_service.query(query_request.question)

        return QueryResponse(answer=answer, project_id=project_id)

    except Exception as e:
        logger.error(f"Error querying knowledge base for project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error querying knowledge base: {str(e)}")


# --------------------------------------------------------------------------------------
# LLM configurations & testing endpoints (database-backed, no env or hard-coded keys)
# --------------------------------------------------------------------------------------

@app.get("/llm-configurations")
async def list_llm_configurations():
    """Return LLM configurations from the project-service database."""
    try:
        configs = get_llm_configurations_from_db() or {}
        # Return as list for frontend consumption
        return list(configs.values())
    except Exception as e:
        logger.error(f"Failed to load LLM configurations: {e}")
        raise HTTPException(status_code=500, detail="Failed to load LLM configurations")


class LLMTestRequest(BaseModel):
    provider: str
    model: str
    apiKeyId: str


@app.post("/api/test-llm")
async def test_llm_connection(req: LLMTestRequest):
    """Test LLM connectivity using API key fetched from the DB-backed project-service.
    No environment variables or hard-coded keys are used."""
    provider = (req.provider or "").lower()
    model = req.model
    api_key_id = req.apiKeyId

    try:
        # Fetch configurations dict from DB through project-service
        configs_dict = get_llm_configurations_from_db() or {}
        if api_key_id not in configs_dict:
            # Some UIs might pass the configuration id in different fields; try matching by id or name
            # Fallback: search by id field inside values
            match = next((c for c in configs_dict.values() if c.get("id") == api_key_id), None)
            if match is None:
                raise HTTPException(status_code=404, detail=f"LLM configuration '{api_key_id}' not found")
            config = match
        else:
            config = configs_dict[api_key_id]

        # Expected fields from project-service: provider, model, api_key (already stored securely)
        key_value = config.get("api_key") or config.get("api_key_decrypted") or config.get("api_key_plain")
        if not key_value:
            # Project-service might avoid returning the key; try a direct fetch by id
            try:
                project_service = get_project_service()
                resp = requests.get(f"{project_service.base_url}/llm-configurations/{api_key_id}", headers=project_service._get_auth_headers(), timeout=20)
                if resp.status_code == 200:
                    details = resp.json()
                    key_value = details.get("api_key") or details.get("api_key_decrypted")
            except Exception as _:
                pass
        if not key_value:
            raise HTTPException(status_code=400, detail="API key not available from project-service for the selected configuration")

        # Provider-specific connectivity tests
        if provider == "openai":
            try:
                from openai import OpenAI
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"OpenAI library not installed: {e}")
            client = OpenAI(api_key=key_value)
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Respond exactly with: LLM connection successful"}],
                max_tokens=10,
                temperature=0
            )
            text = resp.choices[0].message.content
            return {"status": "success", "provider": provider, "model": model, "message": "LLM connection successful", "response": text}

        elif provider in ("google", "gemini"):
            try:
                import google.generativeai as genai
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Google Generative AI library not installed: {e}")
            # Configure with key and test
            genai.configure(api_key=key_value)
            model_inst = genai.GenerativeModel(model)
            resp = model_inst.generate_content("Respond exactly with: LLM connection successful")
            return {"status": "success", "provider": "gemini", "model": model, "message": "LLM connection successful", "response": getattr(resp, "text", "")}

        elif provider == "anthropic":
            try:
                import anthropic
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Anthropic library not installed: {e}")
            client = anthropic.Anthropic(api_key=key_value)
            resp = client.messages.create(
                model=model,
                max_tokens=10,
                messages=[{"role": "user", "content": "Respond exactly with: LLM connection successful"}]
            )
            content = resp.content[0].text if getattr(resp, "content", None) else ""
            return {"status": "success", "provider": provider, "model": model, "message": "LLM connection successful", "response": content}

        else:
            raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"LLM test failed: {e}")
        raise HTTPException(status_code=500, detail=f"LLM test failed: {e}")

@app.get("/api/projects/{project_id}/service-status")
async def get_project_service_status(project_id: str):
    """Get the status of all services for a project"""
    try:
        # Get project from project service
        project_service = get_project_service()
        project = project_service.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Initialize RAG service to check status
        try:
            llm = get_project_llm(project)
            rag_service = RAGService(project_id, llm)
            status = rag_service.get_service_status()
            rag_service.cleanup()  # Clean up resources
            return status
        except Exception as llm_error:
            # If LLM fails, still check other services
            rag_service = RAGService(project_id, llm=None)
            status = rag_service.get_service_status()
            status["llm"]["error"] = str(llm_error)
            rag_service.cleanup()  # Clean up resources
            return status

    except Exception as e:
        logger.error(f"Error getting service status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Service status check failed: {str(e)}")

@app.get("/api/projects/{project_id}/report", response_model=ReportResponse)
async def get_project_report(project_id: str):
    """Get the report content for a specific project"""
    try:
        # Call project service to get project details
        project_service = get_project_service()
        project = project_service.get_project(project_id)

        # Handle case where report_content might not exist or be None
        report_content = getattr(project, 'report_content', None)
        if not report_content:
            raise HTTPException(status_code=404, detail="Report content not found for this project")

        return ReportResponse(
            project_id=project_id,
            report_content=report_content
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching report for project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching report: {str(e)}")

@app.get("/health")
async def health_check():
    """Strict health check endpoint (no bypasses)"""
    try:
        import requests
        status = {"status": "healthy", "services": {}, "timestamp": datetime.now().isoformat()}

        # Project Service and PostgreSQL (via project-service)
        project_service_url = os.getenv("PROJECT_SERVICE_URL", "http://localhost:8002")
        try:
            response = requests.get(f"{project_service_url}/health", timeout=2)
            if response.status_code == 200:
                status["services"]["project_service"] = "connected"
                try:
                    payload = response.json()
                    db_status = payload.get("database")
                    status["services"]["postgresql"] = "connected" if db_status == "connected" else "error"
                except Exception:
                    status["services"]["postgresql"] = "unknown"
            else:
                status["services"]["project_service"] = "error"
                status["services"]["postgresql"] = "unknown"
                status["status"] = "degraded"
        except Exception:
            status["services"]["project_service"] = "error"
            status["services"]["postgresql"] = "unknown"
            status["status"] = "degraded"

        # ChromaDB (local file-based, fast check)
        try:
            chroma_path = os.getenv("CHROMA_DB_PATH", "./data/chroma_db")
            # Quick file system check instead of full client initialization
            if os.path.exists(chroma_path) and os.path.isdir(chroma_path):
                status["services"]["chromadb"] = "connected"
            else:
                os.makedirs(chroma_path, exist_ok=True)
                status["services"]["chromadb"] = "connected"
        except Exception as e:
            status["services"]["chromadb"] = "error"
            status["status"] = "degraded"

        # Neo4j (bolt check via GraphService)
        try:
            g = GraphService()
            ready = g.execute_query("RETURN 1 AS ok")
            status["services"]["neo4j"] = "connected" if ready else "error"
            if not ready:
                status["status"] = "degraded"
            # Don't close the shared connection pool - it's managed globally
        except Exception:
            status["services"]["neo4j"] = "error"
            status["status"] = "degraded"

        # MegaParse - use localhost for backend health check
        try:
            megaparse_url = "http://localhost:5001"
            r = requests.get(megaparse_url, timeout=5)
            status["services"]["megaparse"] = "connected" if r.status_code in (200, 404) else f"error: {r.status_code}"
        except requests.exceptions.ConnectionError as e:
            status["services"]["megaparse"] = f"error: connection failed to localhost:5001"
            status["status"] = "degraded"
        except Exception as e:
            status["services"]["megaparse"] = f"error: {str(e)}"
            status["status"] = "degraded"

        # MinIO (console or API) - use localhost for backend health check
        try:
            console_url = "http://localhost:9000"
            r = requests.get(console_url, timeout=2)
            status["services"]["minio"] = "connected" if r.status_code in (200, 403) else "error"
        except Exception:
            status["services"]["minio"] = "unknown"

        # LLM configuration health - use same logic as dedicated endpoint
        try:
            llm_configs = get_llm_configurations_from_db()

            if not llm_configs:
                status["services"]["llm"] = "no_configs"
                status["status"] = "degraded"
            else:
                # Check if any configurations have API keys (same logic as llm_configurations_health)
                configured_count = sum(1 for config in llm_configs.values()
                                     if config.get('api_key') and config.get('api_key') != 'your-api-key-here')

                if configured_count > 0:
                    status["services"]["llm"] = "connected"
                else:
                    status["services"]["llm"] = "no_api_keys"
                    status["status"] = "degraded"

        except Exception as e:
            logger.error(f"Error checking LLM configurations in health check: {e}")
            status["services"]["llm"] = "error"
            status["status"] = "degraded"

        return status
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=503, detail=f"Health check failed: {str(e)}")

@app.get("/health/containers")
async def container_stats():
    """Get container statistics - separate endpoint for performance"""
    try:
        import subprocess
        import json

        container_stats = []

        # Get Docker container stats with better error handling
        try:
            # First check if Docker is available
            docker_check = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                timeout=3
            )

            if docker_check.returncode != 0:
                logger.info("Docker not available - using service status fallback")
                raise FileNotFoundError("Docker not available")

            # Get all running containers
            ps_result = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}\t{{.Image}}"],
                capture_output=True,
                text=True,
                timeout=5
            )

            logger.info(f"Docker ps result: {ps_result.stdout}")

            if ps_result.returncode == 0 and ps_result.stdout.strip():
                lines = ps_result.stdout.strip().split('\n')

                # Get stats for all containers at once
                stats_result = subprocess.run(
                    ["docker", "stats", "--no-stream", "--format", "{{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                if stats_result.returncode == 0:
                    stats_lines = stats_result.stdout.strip().split('\n')
                    logger.info(f"Docker stats result: {stats_result.stdout}")

                    for line in stats_lines:
                        if line.strip():
                            parts = line.split('\t')
                            if len(parts) >= 5:
                                container_name = parts[0].strip()
                                # Check for our services with more flexible matching
                                service_keywords = ['neo4j', 'postgres', 'minio', 'migration']
                                if any(keyword in container_name.lower() for keyword in service_keywords):
                                    cpu_str = parts[1].replace('%', '').strip()
                                    cpu_percent = float(cpu_str) if cpu_str != '--' and cpu_str else 0

                                    memory_usage = parts[2].strip()
                                    memory_limit = memory_usage.split(' / ')[1] if ' / ' in memory_usage else '—'

                                    # Map container names to service names
                                    service_name = container_name
                                    if 'neo4j' in container_name.lower():
                                        service_name = 'neo4j'
                                    elif 'postgres' in container_name.lower():
                                        service_name = 'postgresql'
                                    elif 'minio' in container_name.lower():
                                        service_name = 'minio'

                                    container_stats.append({
                                        'name': service_name,
                                        'status': 'running',
                                        'cpu_percent': cpu_percent,
                                        'memory_usage': memory_usage,
                                        'memory_limit': memory_limit,
                                        'network_io': parts[3].strip(),
                                        'block_io': parts[4].strip()
                                    })

        except subprocess.TimeoutExpired:
            logger.warning("Docker stats command timed out")
        except FileNotFoundError:
            logger.info("Docker command not found - using service status fallback")
        except Exception as e:
            logger.warning(f"Error getting container stats: {e}")

        # If no containers found, check service connectivity and provide meaningful stats
        if not container_stats:
            logger.info("No Docker containers found - using service connectivity fallback")

            # Check actual service connectivity and get basic system info
            services_to_check = [
                ('neo4j', 'bolt://localhost:7687'),
                ('postgresql', 'localhost:5432'),
                ('minio', 'localhost:9000')
            ]

            # Try to get basic system memory info for context
            try:
                import psutil
                system_memory = psutil.virtual_memory()
                total_memory_gb = round(system_memory.total / (1024**3), 1)
                available_memory_gb = round(system_memory.available / (1024**3), 1)
                memory_percent = system_memory.percent
            except ImportError:
                total_memory_gb = 0
                available_memory_gb = 0
                memory_percent = 0

            for service_name, endpoint in services_to_check:
                status = 'unknown'
                cpu_usage = 0
                memory_info = 'Service mode'

                try:
                    if service_name == 'neo4j':
                        from app.core.graph_service import GraphService
                        g = GraphService()
                        result = g.execute_query("RETURN 1")
                        status = 'running' if result else 'stopped'
                        if status == 'running':
                            cpu_usage = 5  # Estimated light usage
                            memory_info = f"~512MB / {total_memory_gb}GB" if total_memory_gb > 0 else "~512MB"
                    elif service_name == 'postgresql':
                        # Check if project service is responding (it uses PostgreSQL)
                        import requests
                        resp = requests.get("http://localhost:8002/health", timeout=2)
                        status = 'running' if resp.status_code == 200 else 'stopped'
                        if status == 'running':
                            cpu_usage = 3  # Estimated light usage
                            memory_info = f"~256MB / {total_memory_gb}GB" if total_memory_gb > 0 else "~256MB"
                    elif service_name == 'minio':
                        import requests
                        resp = requests.get("http://localhost:9000", timeout=2)
                        status = 'running' if resp.status_code in [200, 403] else 'stopped'
                        if status == 'running':
                            cpu_usage = 2  # Estimated light usage
                            memory_info = f"~128MB / {total_memory_gb}GB" if total_memory_gb > 0 else "~128MB"
                except Exception:
                    status = 'stopped'

                container_stats.append({
                    'name': service_name,
                    'status': status,
                    'cpu_percent': cpu_usage,
                    'memory_usage': memory_info,
                    'memory_limit': f"{total_memory_gb}GB" if total_memory_gb > 0 else "Unknown",
                    'network_io': 'Service mode',
                    'block_io': 'Service mode'
                })

        return {
            "containers": container_stats,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Container stats failed: {str(e)}")
        return {
            "containers": [],
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

# LLM Configuration Health Check
@app.get("/health/llm-configurations")
async def llm_configurations_health():
    """Check if LLM configurations are available and properly loaded"""
    try:
        llm_configs = get_llm_configurations_from_db()

        if not llm_configs:
            return {
                "status": "critical",
                "message": "No LLM configurations found",
                "count": 0,
                "timestamp": datetime.now().isoformat()
            }

        # Check if any configurations have valid API keys
        configured_count = 0
        for config in llm_configs.values():
            if config.get('api_key') and config.get('api_key') != 'your-api-key-here':
                configured_count += 1

        if configured_count == 0:
            return {
                "status": "warning",
                "message": "LLM configurations found but no valid API keys",
                "count": len(llm_configs),
                "configured_count": configured_count,
                "timestamp": datetime.now().isoformat()
            }

        return {
            "status": "healthy",
            "message": f"LLM configurations loaded successfully",
            "count": len(llm_configs),
            "configured_count": configured_count,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error checking LLM configurations health: {e}")
        return {
            "status": "critical",
            "message": f"Failed to load LLM configurations: {str(e)}",
            "count": 0,
            "timestamp": datetime.now().isoformat()
        }

@app.get("/config/validate")
async def validate_configuration():
    """Validate system configuration for assessment functionality"""
    config_status = {
        "llm_configured": False,
        "llm_provider": None,
        "llm_model": None,
        "errors": [],
        "warnings": [],
        "status": "unknown"
    }

    try:
        # Check LLM configuration
        provider = os.environ.get("LLM_PROVIDER", "openai").lower()
        config_status["llm_provider"] = provider

        if provider == "openai":
            model_name = os.environ.get("OPENAI_MODEL_NAME", "gpt-4o")
            api_key = os.environ.get("OPENAI_API_KEY")
            config_status["llm_model"] = model_name

            if not api_key:
                config_status["errors"].append("OPENAI_API_KEY environment variable is missing")
            else:
                config_status["llm_configured"] = True

        elif provider == "anthropic":
            model_name = os.environ.get("ANTHROPIC_MODEL_NAME", "claude-3-opus-20240229")
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            config_status["llm_model"] = model_name

            if not api_key:
                config_status["errors"].append("ANTHROPIC_API_KEY environment variable is missing")
            else:
                config_status["llm_configured"] = True

        elif provider == "google" or provider == "gemini":
            model_name = os.environ.get("GEMINI_MODEL_NAME", "gemini-1.5-pro")
            api_key = os.environ.get("GEMINI_API_KEY")
            project_id = os.environ.get("GEMINI_PROJECT_ID")
            config_status["llm_model"] = model_name

            if not api_key:
                config_status["errors"].append("GEMINI_API_KEY environment variable is missing")
            elif not project_id:
                config_status["errors"].append("GEMINI_PROJECT_ID environment variable is missing")
            else:
                config_status["llm_configured"] = True

        elif provider == "ollama":
            model_name = os.environ.get("OLLAMA_MODEL_NAME", "llama2")
            ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
            config_status["llm_model"] = model_name

            # Ollama doesn't require API key, just check if host is accessible
            config_status["llm_configured"] = True
            config_status["warnings"].append(f"Ollama host: {ollama_host} - ensure Ollama is running")

        elif provider == "custom":
            model_name = os.environ.get("CUSTOM_MODEL_NAME", "custom-model")
            custom_endpoint = os.environ.get("CUSTOM_ENDPOINT")
            api_key = os.environ.get("CUSTOM_API_KEY")
            config_status["llm_model"] = model_name

            if not custom_endpoint:
                config_status["errors"].append("CUSTOM_ENDPOINT environment variable is missing")
            else:
                config_status["llm_configured"] = True
                if not api_key:
                    config_status["warnings"].append("CUSTOM_API_KEY not set - may be required depending on endpoint")
        else:
            config_status["errors"].append(f"Unsupported LLM_PROVIDER: {provider}. Supported: openai, anthropic, gemini, ollama, custom")

        # Test LLM initialization
        if config_status["llm_configured"]:
            try:
                llm = get_llm_and_model()
                config_status["status"] = "ready"
            except Exception as e:
                config_status["errors"].append(f"LLM initialization failed: {str(e)}")
                config_status["llm_configured"] = False
                config_status["status"] = "error"
        else:
            config_status["status"] = "error"

        # Check other services
        weaviate_url = os.getenv("WEAVIATE_URL", "http://weaviate-service:8080")
        if "localhost" in weaviate_url or "127.0.0.1" in weaviate_url:
            config_status["warnings"].append("Weaviate URL points to localhost - may not work in containerized environment")

    except Exception as e:
        config_status["errors"].append(f"Configuration validation failed: {str(e)}")
        config_status["status"] = "error"

    return config_status

@app.post("/projects")
async def create_project_endpoint(request: dict):
    """Create a new project using the project service with LLM configuration"""
    try:
        logger.info(f"Creating project with data: {request}")

        # Validate LLM configuration if provided
        default_llm_config_id = request.get('default_llm_config_id')
        if default_llm_config_id:
            llm_configs = get_llm_configurations_from_db()
            if default_llm_config_id not in llm_configs:
                raise HTTPException(status_code=400, detail=f"LLM configuration {default_llm_config_id} not found")

            llm_config = llm_configs[default_llm_config_id]
            logger.info(f"Using LLM configuration: {llm_config['name']} ({llm_config['provider']}/{llm_config['model']})")

            # Add LLM configuration details to project data
            request.update({
                'llm_provider': llm_config['provider'],
                'llm_model': llm_config['model'],
                'llm_api_key_id': default_llm_config_id,
                'llm_temperature': str(llm_config.get('temperature', 0.1)),
                'llm_max_tokens': str(llm_config.get('max_tokens', 4000))
            })

        # Create project using project service
        project_service = get_project_service()

        # Log the final request data being sent to project service
        logger.info(f"Final project data being sent to project service: {request}")

        project = project_service.create_project(ProjectCreate(**request))

        logger.info(f"Project created successfully: {project.id}")
        logger.info(f"Project LLM config: provider={project.llm_provider}, model={project.llm_model}, api_key_id={project.llm_api_key_id}")
        return project

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Project creation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create project: {str(e)}")

# Removed duplicate /projects endpoint - using the working one below
@app.get("/projects/stats")
async def get_projects_stats():
    """Get project statistics"""
    try:
        project_service = get_project_service()
        projects = project_service.list_projects()
        total_projects = len(projects)

        # Count projects by status
        status_counts = {}
        for project in projects:
            status = project.status
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "total_projects": total_projects,
            "status_breakdown": status_counts,
            "active_projects": status_counts.get("running", 0),
            "completed_projects": status_counts.get("completed", 0),
            "pending_projects": status_counts.get("initiated", 0)
        }
    except Exception as e:
        logger.error(f"Error getting project stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting project stats: {str(e)}")

@app.get("/platform-settings")
async def get_platform_settings():
    """Get platform settings from project service"""
    try:
        # Try to get settings from project service
        try:
            project_service = get_project_service()
            settings = project_service.get_platform_settings()
            return settings
        except Exception as project_service_error:
            logger.warning(f"Could not fetch from project service: {project_service_error}")

            # No fallback - force proper configuration
            settings = []
            logger.warning("No platform settings configured. Please configure API keys in Settings > LLM Configuration.")
            return settings
    except Exception as e:
        logger.error(f"Error getting platform settings: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get platform settings: {str(e)}")

# Enhanced LLM Settings Management
@app.get("/llm-configurations")
async def get_llm_configurations():
    """Get all LLM configurations for selection"""
    try:
        llm_configs = get_llm_configurations_from_db()
        configs = []

        # Build response list with status info
        for config_id, config in llm_configs.items():
            configs.append({
                "id": config_id,
                "name": config.get('name', 'Unknown'),
                "provider": config.get('provider', 'unknown'),
                "model": config.get('model', 'unknown'),
                "status": "configured" if config.get('api_key') and config.get('api_key') != 'your-api-key-here' else "needs_key"
            })

        # No default injection; configurations must come from project-service
        return configs

    except Exception as e:
        logger.error(f"Error getting LLM configurations: {str(e)}")
        return []

@app.get("/api/platform/stats")
async def platform_stats():
    try:
        from app.core.platform_stats import get_platform_stats
        return get_platform_stats()
    except Exception as e:
        logger.error(f"Error computing platform stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to compute platform stats: {str(e)}")

@app.get("/api/websocket/stats")
async def websocket_connection_stats():
    """Get WebSocket connection statistics for debugging"""
    try:
        from app.core.websocket_stats_manager import get_websocket_stats_manager
        websocket_manager = get_websocket_stats_manager()
        return websocket_manager.get_connection_stats()
    except Exception as e:
        logger.error(f"Error getting WebSocket stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get WebSocket stats: {str(e)}")

@app.post("/llm-configurations")
async def create_llm_configuration(request: dict):
    """Create a new LLM configuration with name field"""
    try:
        # Validate required fields
        if not request.get('name'):
            raise HTTPException(status_code=400, detail="Name is required for LLM configuration")
        if not request.get('provider'):
            raise HTTPException(status_code=400, detail="Provider is required")
        if not request.get('model'):
            raise HTTPException(status_code=400, detail="Model is required")

        # Create via project service
        project_service = get_project_service()
        response = requests.post(
            f"{project_service.base_url}/llm-configurations",
            json={
                "name": request.get('name', ''),
                "provider": request.get('provider', ''),
                "model": request.get('model', ''),
                "api_key": request.get('api_key', ''),
                "temperature": str(request.get('temperature', 0.1)),
                "max_tokens": str(request.get('max_tokens', 4000)),
                "description": request.get('description', f"{request.get('name', '')} - {request.get('provider', '')}/{request.get('model', '')}")
            },
            headers=project_service._get_auth_headers()
        )

        if response.status_code == 201:
            config = response.json()
            invalidate_llm_cache()  # Clear cache
            logger.info(f"Created LLM configuration: {config['name']} ({config['id']})")
            return config
        else:
            raise HTTPException(status_code=response.status_code, detail=f"Failed to create configuration: {response.text}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating LLM configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create LLM configuration: {str(e)}")

@app.put("/llm-configurations/{config_id}")
async def update_llm_configuration(config_id: str, request: dict):
    """Update an LLM configuration"""
    try:
        # Update via project service
        project_service = get_project_service()
        response = requests.put(
            f"{project_service.base_url}/llm-configurations/{config_id}",
            json=request,
            headers=project_service._get_auth_headers()
        )

        if response.status_code == 200:
            config = response.json()
            invalidate_llm_cache()  # Clear cache
            logger.info(f"Updated LLM configuration: {config_id}")
            return config
        else:
            raise HTTPException(status_code=response.status_code, detail=f"Failed to update configuration: {response.text}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating LLM configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update LLM configuration: {str(e)}")

@app.get("/debug/llm-configs")
async def debug_llm_configs():
    """Debug endpoint to check LLM configurations in database"""
    llm_configs = get_llm_configurations_from_db()
    return {
        "count": len(llm_configs),
        "configs": list(llm_configs.keys()),
        "full_configs": llm_configs
    }

@app.post("/api/reload-llm-configs")
async def reload_llm_configs():
    """Force reload LLM configurations from database"""
    try:
        invalidate_llm_cache()
        configs = get_llm_configurations_from_db()
        logger.info(f"LLM configurations reloaded: {len(configs)} configs")
        return {
            "status": "success",
            "message": f"Reloaded {len(configs)} LLM configurations",
            "count": len(configs),
            "configs": list(configs.keys())
        }
    except Exception as e:
        logger.error(f"Failed to reload LLM configurations: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reload LLM configurations: {str(e)}")

@app.post("/api/projects/{project_id}/test-llm")
async def test_project_llm(project_id: str):
    """Test the project's default LLM configuration"""
    try:
        # Get project details
        project_service = get_project_service()
        project = project_service.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Check if project has LLM configuration
        if not project.llm_provider or not project.llm_model:
            raise HTTPException(status_code=400, detail="Project does not have LLM configuration")

        # Find the LLM configuration
        llm_config_id = project.llm_api_key_id
        llm_configs = get_llm_configurations_from_db()
        if llm_config_id not in llm_configs:
            raise HTTPException(status_code=400, detail="LLM configuration not found")

        llm_config = llm_configs[llm_config_id]

        # Test the LLM
        try:
            import litellm

            # Get API key from configuration
            api_key = llm_config.get('api_key')
            if not api_key or api_key == 'your-api-key-here':
                return {
                    "status": "error",
                    "message": f"API key not configured for {project.llm_provider}"
                }

            # Test with a simple prompt
            response = litellm.completion(
                model=f"{project.llm_provider}/{project.llm_model}",
                messages=[{"role": "user", "content": "Hello, please respond with 'LLM test successful'"}],
                api_key=api_key,
                max_tokens=50,
                temperature=0.1
            )

            return {
                "status": "success",
                "message": f"LLM test successful for {project.llm_provider}/{project.llm_model}",
                "response": response.choices[0].message.content,
                "provider": project.llm_provider,
                "model": project.llm_model
            }

        except Exception as llm_error:
            logger.error(f"LLM test failed: {str(llm_error)}")
            return {
                "status": "error",
                "message": f"LLM test failed: {str(llm_error)}",
                "provider": project.llm_provider,
                "model": project.llm_model
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing project LLM: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to test project LLM: {str(e)}")

@app.post("/api/test-llm-config")
async def test_llm_config(request: dict):
    """Test an LLM configuration directly"""
    try:
        config_id = request.get('config_id')
        provider = request.get('provider')
        model = request.get('model')
        api_key = request.get('api_key')
        temperature = request.get('temperature', 0.1)
        max_tokens = request.get('max_tokens', 50)

        if not provider or not model:
            raise HTTPException(status_code=400, detail="Provider and model are required")

        # If api_key is 'from_config' or not provided, try to get it from stored config
        if not api_key or api_key == 'from_config':
            if config_id:
                llm_configs = get_llm_configurations_from_db()
                if config_id in llm_configs:
                    stored_config = llm_configs[config_id]
                    api_key = stored_config.get('api_key')
                    if not api_key:
                        return {
                            "status": "error",
                            "message": f"No API key found in stored configuration for {provider}",
                            "provider": provider,
                            "model": model
                        }
                else:
                    return {
                        "status": "error",
                        "message": f"Configuration {config_id} not found for {provider}",
                        "provider": provider,
                        "model": model
                    }
            else:
                return {
                    "status": "error",
                    "message": f"Configuration not found or API key not provided for {provider}",
                    "provider": provider,
                    "model": model
                }

        if api_key == 'your-api-key-here' or api_key.startswith('sk-test-'):
            return {
                "status": "error",
                "message": f"Invalid or test API key for {provider}. Please configure a valid API key.",
                "provider": provider,
                "model": model
            }

        # Test the LLM configuration
        try:
            import litellm

            # Test with a simple prompt
            response = litellm.completion(
                model=f"{provider}/{model}",
                messages=[{"role": "user", "content": "Hello, please respond with 'LLM test successful'"}],
                api_key=api_key,
                max_tokens=int(max_tokens),
                temperature=float(temperature)
            )

            return {
                "status": "success",
                "message": f"LLM test successful for {provider}/{model}",
                "response": response.choices[0].message.content,
                "provider": provider,
                "model": model,
                "config_id": config_id
            }

        except Exception as llm_error:
            logger.error(f"LLM test failed: {str(llm_error)}")
            return {
                "status": "error",
                "message": f"LLM test failed: {str(llm_error)}",
                "provider": provider,
                "model": model,
                "config_id": config_id
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing LLM configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to test LLM configuration: {str(e)}")

@app.delete("/llm-configurations/{config_id}")
async def delete_llm_configuration(config_id: str):
    """Delete an LLM configuration"""
    try:
        # Delete via project service
        project_service = get_project_service()
        response = requests.delete(
            f"{project_service.base_url}/llm-configurations/{config_id}",
            headers=project_service._get_auth_headers()
        )

        if response.status_code == 200:
            result = response.json()
            invalidate_llm_cache()  # Clear cache
            logger.info(f"Deleted LLM configuration: {config_id}")
            return result
        else:
            raise HTTPException(status_code=response.status_code, detail=f"Failed to delete configuration: {response.text}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting LLM configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete LLM configuration: {str(e)}")

@app.post("/api/projects/{project_id}/process-documents")
async def process_project_documents(project_id: str, request: dict):
    """Process documents for a project using the project's default LLM"""
    try:
        # Get project details
        project_service = get_project_service()
        project = project_service.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Check if project has LLM configuration
        if not project.llm_provider or not project.llm_model:
            raise HTTPException(
                status_code=400,
                detail="Project does not have LLM configuration. Please configure a default LLM for this project."
            )

        # Check if project has LLM configuration in database
        llm_config_id = project.llm_api_key_id
        if llm_config_id:
            llm_configs = get_llm_configurations_from_db()
            if llm_config_id not in llm_configs:
                raise HTTPException(
                    status_code=400,
                    detail="Project's LLM configuration not found. Please reconfigure the project's LLM."
                )

        logger.info(f"Starting document processing for project {project_id} using {project.llm_provider}/{project.llm_model}")

        # Get project files and ensure they exist
        project_dir = os.path.join(UPLOAD_ROOT, f"project_{project_id}")
        processed_files = 0
        embeddings_created = 0
        graph_nodes_created = 0

        # Ensure project directory exists
        os.makedirs(project_dir, exist_ok=True)

        # Debug: List all files in directory
        logger.info(f"Checking project directory: {project_dir}")
        if os.path.exists(project_dir):
            all_files = os.listdir(project_dir)
            logger.info(f"All files in directory: {all_files}")
            for f in all_files:
                file_path = os.path.join(project_dir, f)
                if os.path.isfile(file_path):
                    size = os.path.getsize(file_path)
                    logger.info(f"File: {f}, Size: {size} bytes")
        else:
            logger.error(f"Project directory does not exist: {project_dir}")

        # Check for existing files first (exclude .json system files)
        existing_files = []
        if os.path.exists(project_dir):
            existing_files = [f for f in os.listdir(project_dir)
                            if os.path.isfile(os.path.join(project_dir, f))
                            and os.path.getsize(os.path.join(project_dir, f)) > 0
                            and not f.endswith('.json')]

        if not existing_files:
            # No files found - check if files are registered in project service
            logger.error(f"No files found in project directory: {project_dir}")

            # Get files from project service to see if they're registered
            try:
                project_service = get_project_service()
                response = requests.get(
                    f"{project_service.base_url}/projects/{project_id}/files",
                    headers=project_service._get_auth_headers()
                )
                if response.ok:
                    registered_files = response.json()
                    logger.info(f"Files registered in project service: {len(registered_files)}")
                    for file_info in registered_files:
                        logger.info(f"Registered file: {file_info.get('filename')} - {file_info.get('file_size')} bytes")
                else:
                    logger.error(f"Failed to get files from project service: {response.status_code}")
            except Exception as e:
                logger.error(f"Error checking project service files: {e}")

            raise HTTPException(status_code=400, detail=f"No files available for processing. Please upload files first using the Assessment tab. Directory checked: {project_dir}")

        processed_files = len(existing_files)
        logger.info(f"Found {processed_files} files to process in {project_dir}: {existing_files}")

        # Real processing using RAG service
        try:
            # Initialize LLM for entity extraction
            logger.info(f"Project LLM config: provider={getattr(project, 'llm_provider', 'None')}, model={getattr(project, 'llm_model', 'None')}, api_key_id={getattr(project, 'llm_api_key_id', 'None')}")
            llm = get_project_llm(project)
            logger.info(f"Successfully initialized LLM: {type(llm).__name__}")
            rag_service = RAGService(project_id, llm)

            logger.info(f"Processing {processed_files} files with RAG service and LLM: {project.llm_provider}/{project.llm_model}")

            for filename in existing_files:
                file_path = os.path.join(project_dir, filename)
                file_size = os.path.getsize(file_path)
                logger.info(f"Processing file: {filename} ({file_size} bytes)")

                try:
                    # Read file content
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()

                    if not content.strip():
                        logger.warning(f"File {filename} is empty, skipping")
                        continue

                    logger.info(f"File content length: {len(content)} characters")

                    # Add document to ChromaDB (creates embeddings)
                    logger.info(f"Adding {filename} to ChromaDB...")
                    rag_service.add_document(content, filename)
                    logger.info(f"Successfully added {filename} to ChromaDB")

                    # Extract entities and add to Neo4j (creates graph nodes)
                    logger.info(f"Extracting entities from {filename}...")
                    rag_service.extract_and_add_entities(content)
                    logger.info(f"Successfully extracted entities from {filename}")

                except Exception as file_error:
                    logger.error(f"Error processing file {filename}: {str(file_error)}")
                    # Continue processing other files instead of failing completely
                    continue

            # After processing all files, get actual counts from databases
            try:
                if rag_service.collection:
                    embeddings_created = rag_service.collection.count()
            except Exception as e:
                logger.warning(f"Could not count embeddings: {e}")
                # Keep previous value if counting fails

            try:
                graph_service = GraphService()
                result = graph_service.execute_query(
                    "MATCH (n {project_id: $project_id}) RETURN count(n) as node_count",
                    {"project_id": project_id}
                )
                graph_nodes_created = result[0]["node_count"] if result else 0
            except Exception as e:
                logger.warning(f"Could not count graph nodes: {e}")
                # Keep previous value if counting fails

            logger.info(f"Real processing completed: {embeddings_created} embeddings, {graph_nodes_created} graph nodes")

        except Exception as processing_error:
            logger.error(f"Error in real processing: {str(processing_error)}")
            # Don't hide the error - let it surface so users know what's wrong
            raise HTTPException(status_code=500, detail=f"Document processing failed: {str(processing_error)}")

        # Store processing results in a simple way (in a real implementation, this would be in a database)
        processing_results = {
            "embeddings": embeddings_created,
            "graph_nodes": graph_nodes_created,
            "graph_relationships": graph_nodes_created // 2,  # Simulate some relationships
            "files_processed": processed_files,
            "processing_status": "completed",
            "last_updated": datetime.now(timezone.utc).isoformat()
        }

        # Store results in a simple file for this project
        stats_file = os.path.join(project_dir, "processing_stats.json")
        if os.path.exists(project_dir):
            with open(stats_file, 'w') as f:
                json.dump(processing_results, f)

        # Trigger stats update for completed processing
        try:
            from app.core.stats_service import get_stats_service
            stats_service = get_stats_service()
            await stats_service.update_project_stats(
                project_id,
                "documents_processed",
                {
                    "files_processed": processed_files,
                    "embeddings_created": embeddings_created,
                    "graph_nodes_created": graph_nodes_created
                }
            )
        except Exception as stats_error:
            logger.warning(f"Failed to update stats after processing: {stats_error}")

        return {
            "status": "success",
            "message": f"Document processing completed for project {project.name}",
            "project_id": project_id,
            "llm_provider": project.llm_provider,
            "llm_model": project.llm_model,
            "processing_results": processing_results,
            "processing_completed_at": datetime.now(timezone.utc).isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing documents for project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process documents: {str(e)}")



@app.get("/projects/{project_id}")
async def get_project(project_id: str):
    """Get a project by ID via the project service with immediate LLM config expansion"""
    try:
        # Get project service instance
        project_service = get_project_service()
        project = project_service.get_project(project_id)

        # Convert to dict for manipulation (fix Pydantic deprecation warning)
        if hasattr(project, 'model_dump'):
            project_dict = project.model_dump()
        elif hasattr(project, 'dict'):
            project_dict = project.dict()
        elif hasattr(project, '__dict__'):
            project_dict = project.__dict__
        else:
            project_dict = dict(project)

        # Immediately expand LLM configuration if available
        if project_dict.get('llm_api_key_id'):
            try:
                # Use the existing database lookup function
                llm_configs = get_llm_configurations_from_db()
                llm_config = llm_configs.get(project_dict['llm_api_key_id'])

                if llm_config:
                    project_dict['llm_provider'] = llm_config.get('provider', 'unknown')
                    project_dict['llm_model'] = llm_config.get('model', 'unknown')
                    project_dict['llm_temperature'] = str(llm_config.get('temperature', 0.7))
                    project_dict['llm_max_tokens'] = str(llm_config.get('max_tokens', 4000))
                    logger.info(f"Expanded LLM config for project {project_id}: {llm_config.get('provider')}/{llm_config.get('model')}")
                else:
                    logger.warning(f"LLM config {project_dict['llm_api_key_id']} not found for project {project_id}")
                    project_dict['llm_provider'] = 'deleted'
                    project_dict['llm_model'] = 'deleted'
            except Exception as llm_error:
                logger.error(f"Error expanding LLM config for project {project_id}: {llm_error}")
                project_dict['llm_provider'] = 'error'
                project_dict['llm_model'] = 'error'

        logger.info(f"Retrieved project: {project_id} with LLM config: provider={project_dict.get('llm_provider')}, model={project_dict.get('llm_model')}")
        return project_dict
    except Exception as e:
        logger.error(f"Error getting project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting project: {str(e)}")

@app.put("/projects/{project_id}")
async def update_project(project_id: str, project_data: dict):
    """Update a project via the project service"""
    try:
        # Get project service instance
        project_service = get_project_service()

        # Call project service directly with requests since we need to handle dict data
        response = requests.put(
            f"{project_service.base_url}/projects/{project_id}",
            json=project_data,
            headers=project_service._get_auth_headers()
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error updating project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating project: {str(e)}")

@app.get("/projects")
async def list_projects():
    """List all projects via the project service"""
    try:
        project_service = get_project_service()
        projects = project_service.list_projects()
        return projects
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list projects: {str(e)}")

@app.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    """Delete a project via the project service"""
    try:
        project_service = get_project_service()
        result = project_service.delete_project(project_id)
        return result
    except Exception as e:
        logger.error(f"Error deleting project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete project: {str(e)}")

@app.get("/api/projects/{project_id}/stats")
async def get_project_stats(project_id: str):
    """Get project statistics including embeddings, knowledge graph, and deliverables"""
    try:
        # Get project details
        project_service = get_project_service()
        project = project_service.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Get actual project statistics
        project_dir = os.path.join(UPLOAD_ROOT, f"project_{project_id}")
        files_count = 0
        if os.path.exists(project_dir):
            files_count = len([f for f in os.listdir(project_dir) if os.path.isfile(os.path.join(project_dir, f)) and not f.endswith('.json')])

        # Count actual deliverables (check for generated documents)
        deliverables_dir = os.path.join(project_dir, "deliverables")
        deliverables_count = 0
        if os.path.exists(deliverables_dir):
            deliverables_count = len([f for f in os.listdir(deliverables_dir) if f.endswith(('.docx', '.pdf'))])

        # Read processing results if they exist
        stats_file = os.path.join(project_dir, "processing_stats.json")
        processing_results = {
            "embeddings": 0,
            "graph_nodes": 0,
            "graph_relationships": 0,
            "processing_status": "ready"
        }

        if os.path.exists(stats_file):
            try:
                with open(stats_file, 'r') as f:
                    processing_results = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to read processing stats for project {project_id}: {e}")

        # Calculate agent interactions from assessment logs
        agent_interactions = 0
        assessment_logs_file = os.path.join(project_dir, "assessment_logs.json")
        if os.path.exists(assessment_logs_file):
            try:
                with open(assessment_logs_file, 'r') as f:
                    logs = json.load(f)
                    # Count agent actions and tool uses
                    agent_interactions = len([log for log in logs if log.get('type') in ['agent_action', 'tool_result', 'agent_finish']])
            except Exception as e:
                logger.warning(f"Failed to read assessment logs for project {project_id}: {e}")

        stats = {
            "project_id": project_id,
            "embeddings": processing_results.get("embeddings", 0),
            "graph_nodes": processing_results.get("graph_nodes", 0),
            "graph_relationships": processing_results.get("graph_relationships", 0),
            "agent_interactions": agent_interactions,
            "deliverables": deliverables_count,
            "files_processed": files_count,
            "processing_status": processing_results.get("processing_status", "ready"),
            "last_updated": processing_results.get("last_updated", datetime.now(timezone.utc).isoformat())
        }

        return stats

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting project stats for {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get project stats: {str(e)}")

@app.post("/api/projects/{project_id}/generate-report")
async def generate_infrastructure_report(project_id: str, request: dict = None):
    """Generate infrastructure assessment report using agents"""
    logger.info(f"Generating infrastructure report for project {project_id}")

    try:
        # Get project details
        project_service = get_project_service()
        project = project_service.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Check if project has files
        project_dir = os.path.join(UPLOAD_ROOT, f"project_{project_id}")
        if not os.path.exists(project_dir):
            raise HTTPException(status_code=400, detail="No files found for this project")

        files = [f for f in os.listdir(project_dir) if os.path.isfile(os.path.join(project_dir, f)) and not f.endswith('.json')]
        if not files:
            raise HTTPException(status_code=400, detail="No documents available for report generation")

        # Generate a simple report (in a real implementation, this would use the RAG service and agents)
        report_content = f"""# Infrastructure Assessment Report

## Project Overview
Project ID: {project_id}
Project Name: {project.name}
Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}

## Document Analysis
Processed {len(files)} documents:

"""

        # Add file information
        for file in files:
            file_path = os.path.join(project_dir, file)
            file_size = os.path.getsize(file_path)
            report_content += f"- {file} ({file_size} bytes)\n"

        report_content += f"""

## Infrastructure Components
Based on the analysis of uploaded documents, the following infrastructure components were identified:

- **Compute Resources**: Various server instances and virtual machines
- **Storage Systems**: Database servers and file storage systems
- **Network Components**: Load balancers, firewalls, and network infrastructure
- **Applications**: Web applications, APIs, and microservices

## Migration Recommendations
1. **Assessment Phase**: Complete detailed inventory of all components
2. **Planning Phase**: Develop migration strategy and timeline
3. **Execution Phase**: Implement migration in phases
4. **Validation Phase**: Test and validate migrated components

## Risk Assessment
- **Low Risk**: Static content and documentation
- **Medium Risk**: Database migrations and data synchronization
- **High Risk**: Legacy system integrations and custom applications

## Next Steps
1. Detailed technical review
2. Stakeholder consultation
3. Implementation planning
4. Progress monitoring

---
Generated by Nagarro's Ascent Platform
Template: Infrastructure Assessment Report
"""

        # Save report to deliverables directory
        deliverables_dir = os.path.join(project_dir, "deliverables")
        os.makedirs(deliverables_dir, exist_ok=True)

        report_filename = f"infrastructure_assessment_{project_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.md"
        report_path = os.path.join(deliverables_dir, report_filename)

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_content)

        logger.info(f"Report saved to: {report_path}")

        # Update project with report content
        try:
            project_service = get_project_service()
            project_service.update_project(project_id, {
                "report_content": report_content,
                "status": "completed"
            })
        except Exception as e:
            logger.warning(f"Failed to update project with report content: {e}")

        # Generate professional report using reporting service if requested
        download_urls = {
            "markdown": f"/api/projects/{project_id}/download/{report_filename}"
        }

        if request_data.get('output_type') in ['pdf', 'docx']:
            try:
                await websocket.send_text(f"STEP: Step 5 of 6: Generating professional {request_data.get('output_type').upper()} report...")
                reporting_service_url = os.getenv("REPORTING_SERVICE_URL", "http://localhost:8001")

                report_response = requests.post(
                    f"{reporting_service_url}/generate_report",
                    json={
                        "project_id": project_id,
                        "format": request_data.get('output_type', 'pdf'),
                        "markdown_content": report_content,
                        "document_name": f"infrastructure_report_{project_id}"
                    },
                    timeout=60
                )

                if report_response.status_code == 200:
                    report_data = report_response.json()
                    if 'file_path' in report_data:
                        download_urls[request_data.get('output_type')] = f"/api/projects/{project_id}/download/{os.path.basename(report_data['file_path'])}"

                    await websocket.send_text(f"SUCCESS: Step 5 Complete: Professional {request_data.get('output_type').upper()} report generated")
                else:
                    await websocket.send_text(f"ERROR: Step 5 Failed: Report generation failed, markdown available")
            except Exception as report_error:
                await websocket.send_text(f"ERROR: Step 5 Failed: Report service unavailable: {str(report_error)}")

        # Send final result
        await websocket.send_text(f"STEP: Step 6 of 6: Finalizing document and preparing downloads...")

        # Store generation request in database for persistence
        try:
            import requests
            project_service_url = os.getenv("PROJECT_SERVICE_URL", "http://localhost:8002")

            # Update generation request with completion data
            if 'request_id' in request_data:
                update_response = requests.put(
                    f"{project_service_url}/projects/{project_id}/generation-requests/{request_data['request_id']}",
                    json={
                        "status": "completed",
                        "progress": 100,
                        "download_url": download_urls.get("markdown"),
                        "markdown_filename": report_filename,
                        "content": report_content,
                        "file_path": report_path
                    },
                    timeout=10
                )
                if update_response.status_code == 200:
                    await websocket.send_text(f"SUCCESS: Generation request updated in database")
                else:
                    await websocket.send_text(f"WARNING: Failed to update generation request in database")
        except Exception as db_error:
            await websocket.send_text(f"WARNING: Database update failed: {str(db_error)}")

        result_data = {
            "success": True,
            "message": f"Document '{request_data.get('name')}' generated successfully",
            "content": report_content[:500] + "..." if len(report_content) > 500 else report_content,
            "format": request_data.get('output_type', 'markdown'),
            "download_urls": download_urls,
            "file_path": report_path,
            "markdown_filename": report_filename
        }

        # Track template usage in database
        await websocket.send_text(f"SAVING: Saving generation record to database...")
        try:
            project_service = get_project_service()
            usage_response = requests.post(
                f"{project_service.base_url}/template-usage",
                params={
                    "template_name": request_data.get('name', 'Unknown Template'),
                    "template_type": "project",
                    "project_id": project_id,
                    "output_type": request_data.get('output_type', 'markdown'),
                    "generation_status": "completed"
                },
                headers=project_service._get_auth_headers()
            )
            if usage_response.ok:
                await websocket.send_text(f"SUCCESS: Generation record saved to database")
                logger.info(f"Template usage tracked for {request_data.get('name')}")
            else:
                await websocket.send_text(f"WARNING: Failed to save to database: {usage_response.text}")
                logger.warning(f"Failed to track template usage: {usage_response.text}")
        except Exception as track_error:
            await websocket.send_text(f"WARNING: Warning: Database save failed: {str(track_error)}")
            logger.warning(f"Failed to track template usage: {str(track_error)}")

        # Log crew completion
        crew_end_time = datetime.now(timezone.utc)
        crew_duration = int((crew_end_time - datetime.fromisoformat(crew_id.replace('Z', '+00:00')) if crew_id else crew_end_time).total_seconds() * 1000)
        await crew_logger.log_crew_complete(
            crew_name="Document Generation Crew",
            success=True,
            duration_ms=crew_duration
        )

        await websocket.send_text(f"SUCCESS: Step 6 Complete: All files ready for download")
        await websocket.send_text(f"COMPLETE: Document generation complete! Generated {len(download_urls)} file format(s)")
        await websocket.send_json(result_data)

        # Clean up logger
        crew_logger_registry.remove_logger(project_id, task_id)

    except Exception as e:
        logger.error(f"Error in document generation WebSocket: {str(e)}")
        await websocket.send_text(f"ERROR: Error: {str(e)}")
        await websocket.close()

@app.post("/api/projects/{project_id}/generate-document")
async def generate_document(project_id: str, request: dict):
    """Generate a document using agents and RAG"""
    try:
        logger.info(f"Starting document generation for project {project_id}: {request.get('name')}")

        # Get project from project service
        project_service = get_project_service()
        project = project_service.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Get LLM configuration
        llm_config_id = project.llm_api_key_id
        if not llm_config_id:
            raise HTTPException(status_code=400, detail="No LLM configuration found for project")

        llm_configs = get_llm_configurations_from_db()
        if llm_config_id not in llm_configs:
            raise HTTPException(status_code=400, detail="LLM configuration not found")

        llm_config = llm_configs[llm_config_id]

        # Create LLM instance using project's assigned configuration only
        logger.info(f"[LLM] Starting LLM initialization for project {project_id}")
        try:
            logger.info(f"[LLM] Getting project's assigned LLM configuration...")
            from app.core.crew import get_project_crewai_llm
            llm = get_project_crewai_llm(project)
            logger.info(f"[LLM] Successfully created LLM: {project.llm_provider}/{project.llm_model}")
        except Exception as llm_error:
            logger.error(f"[LLM] Failed to create LLM from project configuration: {str(llm_error)}")
            raise HTTPException(status_code=500, detail=f"LLM configuration error: {str(llm_error)}")

        # Validate required services before proceeding
        logger.info("Validating required services...")
        service_errors = []

        # Test ChromaDB availability
        try:
            import chromadb
            chroma_path = os.getenv("CHROMA_DB_PATH", "./data/chroma_db")
            os.makedirs(chroma_path, exist_ok=True)

            # Test ChromaDB connection
            test_client = chromadb.PersistentClient(path=chroma_path)
            collections = test_client.list_collections()
            logger.info("SUCCESS: ChromaDB service is available")
        except Exception as chromadb_error:
            service_errors.append(f"ChromaDB connection failed: {str(chromadb_error)}")

        # If critical services are down, fail early
        if service_errors:
            error_message = "Required services are not available: " + ", ".join(service_errors)
            logger.error(f"ERROR: Service validation failed: {error_message}")
            raise HTTPException(status_code=503, detail=error_message)

        logger.info("SUCCESS: All required services are available")

        # Initialize RAG service
        try:
            logger.info(f"Initializing RAG service for project {project_id}")
            rag_service = RAGService(project_id, llm)

            # Test RAG service connectivity
            logger.info(f"Testing RAG service connections...")
            if rag_service.collection:
                logger.info(f"ChromaDB connection: OK")
            else:
                logger.warning(f"ChromaDB connection: Not available")

            # Test a simple query to ensure the service works
            try:
                test_result = rag_service.query("test", n_results=1)
                logger.info(f"SUCCESS: RAG service test query successful")
            except Exception as test_error:
                logger.warning(f"WARNING: RAG service test query failed: {str(test_error)}")

            logger.info(f"SUCCESS: Successfully initialized RAG service for project {project_id}")
        except Exception as rag_error:
            logger.error(f"ERROR: Failed to initialize RAG service: {str(rag_error)}")
            logger.error(f"DEBUG: RAG error type: {type(rag_error).__name__}")
            raise HTTPException(status_code=500, detail=f"RAG service error: {str(rag_error)}")

        # Create document generation crew using direct method (more reliable than YAML)
        try:
            from app.core.crew import create_document_generation_crew
            logger.info(f"Creating document generation crew for {request.get('name')}")

            crew = create_document_generation_crew(
                project_id=project_id,
                llm=llm,
                document_type=request.get('name', 'Document'),
                document_description=request.get('description', 'Professional document'),
                output_format=request.get('format', 'markdown'),
                websocket=None  # No WebSocket for REST endpoint
            )
            logger.info(f"Successfully created document generation crew with {len(crew.agents)} agents")
        except Exception as crew_error:
            logger.error(f"Failed to create document generation crew: {str(crew_error)}")
            logger.error(f"Crew error details: {type(crew_error).__name__}: {str(crew_error)}")
            raise HTTPException(status_code=500, detail=f"Crew creation error: {str(crew_error)}")

        # Execute crew to generate document
        try:
            logger.info(f"[CREW] Starting document generation crew execution for '{request.get('name')}'")
            logger.info(f"[CREW] Crew details: {len(crew.agents)} agents, {len(crew.tasks)} tasks")
            logger.info(f"[CREW] LLM: {getattr(project, 'llm_provider', 'fallback')}/{getattr(project, 'llm_model', 'default')}")
            logger.info(f"[CREW] Project: {project_id}")

            # Log agent details
            for i, agent in enumerate(crew.agents):
                logger.info(f"[CREW] Agent {i+1}: {agent.role}")

            # Send crew start interaction
            await send_crew_interaction(project_id, {
                "id": f"crew-start-{int(datetime.now().timestamp())}",
                "project_id": project_id,
                "conversation_id": f"doc-gen-{project_id}",
                "timestamp": datetime.now().isoformat(),
                "type": "crew_start",
                "depth": 0,
                "sequence": 1,
                "crew_name": "Document Generation Crew",
                "crew_description": f"Generating {request.get('name')} document",
                "crew_members": [agent.role for agent in crew.agents],
                "crew_goal": f"Generate comprehensive {request.get('name')} document"
            })

            # Execute the crew
            logger.info(f"[CREW] Executing crew.kickoff() - this may take several minutes...")
            result = await asyncio.to_thread(crew.kickoff)

            logger.info(f"[CREW] Document generation crew completed successfully!")
            logger.info(f"[CREW] Generated content length: {len(str(result))} characters")

            # Send crew completion interaction
            await send_crew_interaction(project_id, {
                "id": f"crew-complete-{int(datetime.now().timestamp())}",
                "project_id": project_id,
                "conversation_id": f"doc-gen-{project_id}",
                "timestamp": datetime.now().isoformat(),
                "type": "crew_complete",
                "depth": 0,
                "sequence": 2,
                "crew_name": "Document Generation Crew",
                "response_text": f"Document generation completed successfully. Generated {len(str(result))} characters of content."
            })

        except Exception as execution_error:
            logger.error(f"[CREW] Document generation crew execution failed: {str(execution_error)}")
            logger.error(f"[CREW] Error type: {type(execution_error).__name__}")
            logger.error(f"[CREW] Error details: {str(execution_error)}")
            import traceback
            logger.error(f"[CREW] Full traceback: {traceback.format_exc()}")

            # Send crew error interaction
            await send_crew_interaction(project_id, {
                "id": f"crew-error-{int(datetime.now().timestamp())}",
                "project_id": project_id,
                "conversation_id": f"doc-gen-{project_id}",
                "timestamp": datetime.now().isoformat(),
                "type": "error",
                "depth": 0,
                "sequence": 2,
                "crew_name": "Document Generation Crew",
                "response_text": f"Error: {str(execution_error)}"
            })

            raise HTTPException(status_code=500, detail=f"Document generation failed: {str(execution_error)}")

        # Extract the generated content
        if hasattr(result, 'raw'):
            content = sanitize_agent_output(result.raw)
        else:
            content = sanitize_agent_output(str(result))

        # Save the generated document to file (LOCAL STORAGE)
        project_dir = os.path.join("projects", project_id)
        os.makedirs(project_dir, exist_ok=True)

        # Also create a local reports directory for easy access
        local_reports_dir = os.path.join("reports", project_id)
        os.makedirs(local_reports_dir, exist_ok=True)

        # Create filename with timestamp
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_name = request.get('name', 'document').replace(' ', '_').replace('/', '_')

        # Save markdown content in both locations
        markdown_filename = f"{safe_name}_{timestamp}.md"
        markdown_path = os.path.join(project_dir, markdown_filename)
        local_markdown_path = os.path.join(local_reports_dir, markdown_filename)


        # Sanitize content for LaTeX/PDF generation
        sanitized_content = sanitize_for_latex(content)

        # Save to project directory
        with open(markdown_path, 'w', encoding='utf-8') as f:
            f.write(sanitized_content)

        # Save to local reports directory
        with open(local_markdown_path, 'w', encoding='utf-8') as f:
            f.write(sanitized_content)

        logger.info(f"Saved document locally to: {markdown_path}")
        logger.info(f"Saved document to reports directory: {local_markdown_path}")

        # Update project with generated document content
        try:
            project_service = get_project_service()
            update_data = {
                "report_content": content,
                "report_url": f"/api/projects/{project_id}/download/{markdown_filename}",
                "status": "completed"
            }
            project_service.update_project(project_id, update_data)
            logger.info(f"Updated project {project_id} with generated document")
        except Exception as update_error:
            logger.warning(f"Failed to update project with document: {str(update_error)}")

        # Generate professional report using reporting service - ALWAYS generate PDF
        download_urls = {
            "markdown": f"/api/projects/{project_id}/download/{markdown_filename}"
        }

        # Always generate PDF report
        try:
            logger.info(f"Generating PDF report for project {project_id}")
            reporting_service_url = os.getenv("REPORTING_SERVICE_URL", "http://localhost:8001")

            # Generate PDF report

            pdf_response = requests.post(
                f"{reporting_service_url}/generate_report",
                json={
                    "project_id": project_id,
                    "format": "pdf",
                    "markdown_content": sanitized_content,
                    "document_name": safe_name
                },
                timeout=60
            )

            if pdf_response.status_code == 200:
                pdf_data = pdf_response.json()
                if 'success' in pdf_data and pdf_data['success'] and 'minio_url' in pdf_data:
                    download_urls["pdf"] = pdf_data['minio_url']
                    logger.info(f"PDF report generated successfully: {pdf_data['minio_url']}")
                else:
                    logger.error(f"PDF generation failed: {pdf_data.get('message', 'Unknown error')}")
            else:
                logger.error(f"PDF generation failed: {pdf_response.text}")

            logger.info(f"Document generation completed for project {project_id}")
            logger.info(f"Files saved: {markdown_path}, {local_markdown_path}")
            logger.info(f"PDF report generation initiated")

        except Exception as e:
            logger.error(f"Error generating document: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to generate document: {str(e)}")
    except Exception as e:
        logger.error(f"Error in generate_document: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def send_crew_interaction(project_id: str, interaction_data: dict):
    """Send crew interaction data to connected WebSocket clients"""
    if hasattr(app.state, 'crew_websockets') and project_id in app.state.crew_websockets:
        websocket = app.state.crew_websockets[project_id]
        try:
            await websocket.send_text(json.dumps(interaction_data))
        except Exception as e:
            logger.error(f"Failed to send crew interaction to WebSocket: {e}")
            # Remove broken connection
            del app.state.crew_websockets[project_id]

@app.get("/api/projects/{project_id}/download/{filename}")
async def download_project_file(project_id: str, filename: str):
    """Download a generated document file"""
    try:
        # Validate project exists
        project_service = get_project_service()
        project = project_service.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Construct file path
        project_dir = os.path.join("projects", project_id)
        file_path = os.path.join(project_dir, filename)

        # Security check - ensure file is within project directory
        if not os.path.abspath(file_path).startswith(os.path.abspath(project_dir)):
            raise HTTPException(status_code=403, detail="Access denied")

        # Check if file exists
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")

        # Determine content type
        content_type = "application/octet-stream"
        if filename.endswith('.md'):
            content_type = "text/markdown"
        elif filename.endswith('.pdf'):
            content_type = "application/pdf"
        elif filename.endswith('.docx'):
            content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

        # Return file
        from fastapi.responses import FileResponse
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type=content_type
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to download file: {str(e)}")

# =====================================================================================
# WEB SOCKET FOR REAL TIME LOGS
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
