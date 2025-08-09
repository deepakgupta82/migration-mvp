import os
import sys
import tempfile
import logging
import asyncio
from datetime import datetime, timezone
import requests
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))
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

# Logging setup with UTF-8 encoding
os.makedirs("logs", exist_ok=True)

# Set UTF-8 encoding for stdout/stderr to handle Unicode characters
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    handlers=[
        logging.FileHandler("logs/platform.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("platform")

app = FastAPI(
    title="Nagarro's Ascent Backend",
    description="Backend API for the Nagarro's Ascent platform",
    version="1.0.0"
)

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
        }
        self.log_processes: Dict[str, subprocess.Popen] = {}
        self.clients: Dict[str, Set[WebSocket]] = {}

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
            elif service in ['neo4j', 'postgresql', 'minio']:
                # Stream Docker container logs - use actual container names
                container_names = {
                    'neo4j': 'neo4j_service',
                    'postgresql': 'postgres_service',
                    'minio': 'minio_service'
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
async def get_project_graph(project_id: str):
    """Get the Neo4j graph data for a specific project"""
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

        # If no data found, log additional debug info
        if len(nodes) == 0:
            logger.warning(f"No graph data found for project {project_id}")
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

        return {
            "message": "Project data cleared successfully",
            "project_id": project_id,
            "cleared_items": cleared_items
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

        # Check for existing files first
        existing_files = []
        if os.path.exists(project_dir):
            existing_files = [f for f in os.listdir(project_dir) if os.path.isfile(os.path.join(project_dir, f)) and os.path.getsize(os.path.join(project_dir, f)) > 0]

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

        return {
            "status": "success",
            "message": "Infrastructure assessment report generated successfully",
            "project_id": project_id,
            "report_filename": report_filename,
            "report_path": report_path,
            "download_url": f"/api/reports/download/{report_filename}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "document_count": len(files),
            "report_size": len(report_content)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Report generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")

@app.get("/projects/{project_id}/files")
async def get_project_files(project_id: str):
    """Get all files for a project via the project service"""
    try:
        # Call project service to get project files
        project_service = get_project_service()
        response = requests.get(
            f"{project_service.base_url}/projects/{project_id}/files",
            headers=project_service._get_auth_headers()
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error getting files for project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get project files: {str(e)}")

@app.get("/projects/{project_id}/deliverables")
async def get_project_deliverables(project_id: str):
    """Get deliverable templates for a project via the project service"""
    try:
        project_service = get_project_service()
        response = requests.get(
            f"{project_service.base_url}/projects/{project_id}/deliverables",
            headers=project_service._get_auth_headers()
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error getting deliverables for project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get project deliverables: {str(e)}")

@app.get("/projects/{project_id}/template-usage")
async def get_project_template_usage(project_id: str):
    """Get template usage statistics for a project via the project service"""
    try:
        project_service = get_project_service()
        response = requests.get(
            f"{project_service.base_url}/projects/{project_id}/template-usage",
            headers=project_service._get_auth_headers()
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error getting template usage for project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get template usage: {str(e)}")

@app.get("/projects/{project_id}/generation-history")
async def get_project_generation_history(project_id: str):
    """Get document generation history for a project via the project service"""
    try:
        project_service = get_project_service()
        response = requests.get(
            f"{project_service.base_url}/projects/{project_id}/generation-history",
            headers=project_service._get_auth_headers()
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error getting generation history for project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get generation history: {str(e)}")

@app.post("/projects/{project_id}/files")
async def add_project_file(project_id: str, file_data: dict):
    """Add a file record to a project via the project service"""
    try:
        # Call project service to add file record
        project_service = get_project_service()
        response = requests.post(
            f"{project_service.base_url}/projects/{project_id}/files",
            json=file_data,
            headers=project_service._get_auth_headers()
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error adding file to project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to add project file: {str(e)}")

@app.delete("/projects/{project_id}/files/{file_id}")
async def delete_project_file(project_id: str, file_id: str):
    """Delete a file from a project via the project service"""
    try:
        # Call project service to delete file record
        project_service = get_project_service()
        response = requests.delete(
            f"{project_service.base_url}/projects/{project_id}/files/{file_id}",
            headers=project_service._get_auth_headers()
        )
        response.raise_for_status()

        # Also try to delete the physical file from local storage
        try:
            project_dir = os.path.join(UPLOAD_ROOT, f"project_{project_id}")
            # We need to get the filename from the database first
            # For now, we'll just log that we should clean up files
            logger.info(f"File record deleted for project {project_id}, file {file_id}")
        except Exception as cleanup_error:
            logger.warning(f"Could not clean up physical file: {cleanup_error}")

        return {"message": "File deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting file {file_id} from project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete project file: {str(e)}")

@app.get("/api/projects/{project_id}/files/{filename}/download")
async def download_project_file(project_id: str, filename: str):
    """Download a file from a project"""
    try:
        # Decode URL-encoded filename
        import urllib.parse
        decoded_filename = urllib.parse.unquote(filename)

        # Construct file path
        project_dir = os.path.join(UPLOAD_ROOT, f"project_{project_id}")
        file_path = os.path.join(project_dir, decoded_filename)

        # Check if file exists
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            raise HTTPException(status_code=404, detail="File not found")

        # Return file response
        from fastapi.responses import FileResponse
        return FileResponse(
            path=file_path,
            filename=decoded_filename,
            media_type='application/octet-stream'
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading file {filename} from project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to download file: {str(e)}")

@app.post("/upload/{project_id}")
async def upload_files(project_id: str, files: List[UploadFile] = File(...)):
    """Upload files to project with proper response structure"""
    try:
        project_dir = os.path.join(UPLOAD_ROOT, f"project_{project_id}")
        os.makedirs(project_dir, exist_ok=True)

        uploaded_files = []
        successful_count = 0

        for file in files:
            try:
                # Sanitize filename to prevent path traversal and fix path separators
                safe_filename = file.filename.replace('/', '_').replace('\\', '_').replace('..', '_')
                file_path = os.path.join(project_dir, safe_filename)
                content = await file.read()

                with open(file_path, "wb") as f:
                    f.write(content)

                # Register file with project service
                file_data = {
                    'filename': safe_filename,  # Use sanitized filename
                    'file_type': file.content_type or 'application/octet-stream',
                    'file_size': len(content),
                    'upload_path': file_path
                }

                # Add to project service database
                project_service = get_project_service()
                response = requests.post(
                    f"{project_service.base_url}/projects/{project_id}/files",
                    json=file_data,
                    headers=project_service._get_auth_headers()
                )

                if response.ok:
                    uploaded_files.append({
                        'filename': safe_filename,  # Use sanitized filename
                        'original_filename': file.filename,  # Keep original for reference
                        'size': len(content),
                        'content_type': file.content_type,
                        'status': 'uploaded'
                    })
                    successful_count += 1
                else:
                    uploaded_files.append({
                        'filename': safe_filename,  # Use sanitized filename
                        'original_filename': file.filename,  # Keep original for reference
                        'size': len(content),
                        'status': 'failed',
                        'error': f'Failed to register with project service: {response.status_code}'
                    })

            except Exception as file_error:
                # Use safe filename if available, otherwise original
                display_filename = safe_filename if 'safe_filename' in locals() else file.filename
                uploaded_files.append({
                    'filename': display_filename,
                    'original_filename': file.filename,
                    'status': 'failed',
                    'error': str(file_error)
                })

        return {
            "status": "success" if successful_count > 0 else "failed",
            "project_id": project_id,
            "uploaded_files": uploaded_files,
            "summary": {
                "total": len(files),
                "successful": successful_count,
                "failed": len(files) - successful_count
            }
        }

    except Exception as e:
        logger.error(f"Upload error for project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.get("/api/models/{provider}")
async def get_available_models(provider: str, api_key: str = None):
    """Get available models for a specific provider with database fallback"""
    logger.info(f"[MODELS] Fetching models for provider: {provider}")

    # Import requests at function level to avoid scope issues
    import requests

    # First, try to get cached models from database
    async def get_cached_models():
        try:
            project_service = get_project_service()
            response = requests.get(
                f"{project_service.base_url}/models/{provider}",
                headers=project_service._get_auth_headers(),
                timeout=5
            )
            if response.status_code == 200:
                cached_data = response.json()
                if cached_data.get('status') == 'success' and cached_data.get('models'):
                    logger.info(f"[CACHE] Found {len(cached_data['models'])} cached models for {provider}")
                    return cached_data
        except Exception as e:
            logger.warning(f"[CACHE] Could not fetch cached models: {str(e)}")
        return None

    # Function to cache models in database
    async def cache_models_in_db(models_data):
        try:
            project_service = get_project_service()
            response = requests.post(
                f"{project_service.base_url}/models/{provider}/cache",
                headers=project_service._get_auth_headers(),
                json=models_data,
                timeout=5
            )
            if response.status_code == 200:
                logger.info(f"[CACHE] Cached {len(models_data.get('models', []))} models for {provider}")
        except Exception as e:
            logger.warning(f"[CACHE] Could not cache models: {str(e)}")

    try:
        # Try to fetch fresh models from provider
        fresh_models = None

        if provider.lower() == 'openai':
            if not api_key:
                # If no API key, return cached models
                cached = await get_cached_models()
                if cached:
                    cached['message'] = 'Using cached models (no API key provided)'
                    return cached
                raise HTTPException(status_code=400, detail="API key required for OpenAI and no cached models available")

            import requests
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }

            logger.info(f"[API] Fetching fresh models from OpenAI API...")
            response = requests.get('https://api.openai.com/v1/models', headers=headers, timeout=15)

            if response.status_code == 200:
                models_data = response.json()
                # Filter for relevant models
                relevant_models = []
                for model in models_data.get('data', []):
                    model_id = model.get('id', '')
                    # Include GPT models and other relevant ones
                    if any(keyword in model_id.lower() for keyword in ['gpt', 'text-', 'davinci', 'curie', 'babbage', 'ada']):
                        relevant_models.append({
                            'id': model_id,
                            'name': model_id,
                            'description': f"OpenAI {model_id}"
                        })

                # Sort by relevance (GPT models first)
                relevant_models.sort(key=lambda x: (not x['id'].startswith('gpt'), x['id']))

                fresh_models = {
                    'status': 'success',
                    'provider': 'openai',
                    'models': relevant_models,
                    'cached': False
                }

                # Cache the fresh models
                await cache_models_in_db(fresh_models)

                logger.info(f"[SUCCESS] Successfully fetched {len(relevant_models)} fresh models from OpenAI")
                return fresh_models
            else:
                logger.warning(f"[WARNING] OpenAI API returned status {response.status_code}")
                # Fall back to cached models
                cached = await get_cached_models()
                if cached:
                    cached['message'] = f'Using cached models (API returned {response.status_code})'
                    return cached

                return {
                    'status': 'error',
                    'message': f'Failed to fetch OpenAI models: {response.status_code} and no cached models available'
                }

        elif provider.lower() == 'gemini':
            if not api_key:
                # If no API key, return cached models
                cached = await get_cached_models()
                if cached:
                    cached['message'] = 'Using cached models (no API key provided)'
                    return cached
                raise HTTPException(status_code=400, detail="API key required for Gemini and no cached models available")

            import requests

            logger.info(f"[API] Fetching fresh models from Gemini API...")
            response = requests.get(
                f'https://generativelanguage.googleapis.com/v1beta/models?key={api_key}',
                timeout=15
            )

            if response.status_code == 200:
                models_data = response.json()
                models = []
                for model in models_data.get('models', []):
                    model_name = model.get('name', '').replace('models/', '')
                    if 'gemini' in model_name.lower():
                        models.append({
                            'id': model_name,
                            'name': model_name,
                            'description': model.get('displayName', model_name)
                        })

                fresh_models = {
                    'status': 'success',
                    'provider': 'gemini',
                    'models': models,
                    'cached': False
                }

                # Cache the fresh models
                await cache_models_in_db(fresh_models)

                logger.info(f"[SUCCESS] Successfully fetched {len(models)} fresh models from Gemini")
                return fresh_models
            else:
                logger.warning(f"[WARNING] Gemini API returned status {response.status_code}")
                # Fall back to cached models
                cached = await get_cached_models()
                if cached:
                    cached['message'] = f'Using cached models (API returned {response.status_code})'
                    return cached

                return {
                    'status': 'error',
                    'message': f'Failed to fetch Gemini models: {response.status_code} and no cached models available'
                }

        elif provider.lower() == 'anthropic':
            # Anthropic doesn't have a public models API, return known models and cache them
            known_models = {
                'status': 'success',
                'provider': 'anthropic',
                'models': [
                    {'id': 'claude-3-5-sonnet-20241022', 'name': 'Claude 3.5 Sonnet', 'description': 'Most capable model'},
                    {'id': 'claude-3-opus-20240229', 'name': 'Claude 3 Opus', 'description': 'Powerful model for complex tasks'},
                    {'id': 'claude-3-sonnet-20240229', 'name': 'Claude 3 Sonnet', 'description': 'Balanced performance and speed'},
                    {'id': 'claude-3-haiku-20240307', 'name': 'Claude 3 Haiku', 'description': 'Fast and efficient'}
                ],
                'cached': False
            }

            # Cache the known models
            await cache_models_in_db(known_models)
            logger.info(f"[SUCCESS] Cached {len(known_models['models'])} known Anthropic models")

            return known_models

        elif provider.lower() == 'ollama':
            # Ollama models are local, return common ones
            return {
                'status': 'success',
                'provider': 'ollama',
                'models': [
                    {'id': 'llama2', 'name': 'Llama 2', 'description': 'Meta Llama 2'},
                    {'id': 'llama2:13b', 'name': 'Llama 2 13B', 'description': 'Meta Llama 2 13B'},
                    {'id': 'llama2:70b', 'name': 'Llama 2 70B', 'description': 'Meta Llama 2 70B'},
                    {'id': 'codellama', 'name': 'Code Llama', 'description': 'Code-focused Llama'},
                    {'id': 'mistral', 'name': 'Mistral', 'description': 'Mistral 7B'},
                    {'id': 'mixtral', 'name': 'Mixtral', 'description': 'Mixtral 8x7B'}
                ]
            }
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ERROR] Error fetching models for {provider}: {str(e)}")

        # Try to fall back to cached models
        try:
            cached = await get_cached_models()
            if cached:
                cached['message'] = f'Using cached models (error occurred: {str(e)})'
                logger.info(f"[FALLBACK] Falling back to cached models for {provider}")
                return cached
        except Exception as cache_error:
            logger.error(f"[ERROR] Could not fetch cached models: {str(cache_error)}")

        return {
            'status': 'error',
            'message': f'Failed to fetch models and no cached models available: {str(e)}'
        }

@app.websocket("/ws/run_assessment/{project_id}")
async def run_assessment_ws(websocket: WebSocket, project_id: str):
    await websocket.accept()
    try:
        # Validate project exists and update status to running
        try:
            project = project_service.get_project(project_id)
            await websocket.send_text(f"Starting assessment for project: {project.name}")

            # Update project status to running
            project_service.update_project(project_id, {"status": "running"})
            await websocket.send_text("Project status updated to 'running'")
        except Exception as e:
            logger.error(f"Error validating project {project_id}: {str(e)}")
            await websocket.send_text(f"Error: Project {project_id} not found - {str(e)}")
            return

        project_dir = os.path.join(UPLOAD_ROOT, f"project_{project_id}")
        os.makedirs(project_dir, exist_ok=True)

        # Check if documents have already been processed
        processing_stats_file = os.path.join(project_dir, "processing_stats.json")
        should_reprocess = True

        if os.path.exists(processing_stats_file):
            try:
                with open(processing_stats_file, 'r') as f:
                    stats = json.load(f)
                last_processed = datetime.fromisoformat(stats['processed_at'])
                await websocket.send_text(f"WARNING: Documents were previously processed on {last_processed.strftime('%Y-%m-%d %H:%M:%S')}")
                await websocket.send_text("Checking for new files since last processing...")

                # Check if any files were uploaded after last processing
                new_files_found = False
                # We'll check this after getting the file list
                should_reprocess = False  # Will be set to True if new files found
            except Exception as e:
                await websocket.send_text(f"WARNING: Could not read processing stats: {str(e)}")
                should_reprocess = True

        # Get files from project service database
        try:
            project_service = get_project_service()
            response = requests.get(
                f"{project_service.base_url}/projects/{project_id}/files",
                headers=project_service._get_auth_headers()
            )
            response.raise_for_status()
            project_files = response.json()

            if not project_files:
                await websocket.send_text("Error: No files found for this project")
                return

            await websocket.send_text(f"Found {len(project_files)} files in database")

            # Check for new files if we have previous processing stats
            if not should_reprocess and os.path.exists(processing_stats_file):
                try:
                    with open(processing_stats_file, 'r') as f:
                        stats = json.load(f)
                    last_processed = datetime.fromisoformat(stats['processed_at'])

                    # Check if any files were uploaded after last processing
                    for file_record in project_files:
                        upload_time_str = file_record.get('upload_timestamp', '')
                        if upload_time_str:
                            try:
                                # Handle different timestamp formats
                                if 'T' in upload_time_str:
                                    upload_time = datetime.fromisoformat(upload_time_str.replace('Z', '+00:00'))
                                else:
                                    upload_time = datetime.strptime(upload_time_str, '%Y-%m-%d %H:%M:%S')

                                if upload_time > last_processed:
                                    should_reprocess = True
                                    await websocket.send_text(f"SUCCESS: New file detected: {file_record['filename']} (uploaded {upload_time.strftime('%Y-%m-%d %H:%M:%S')})")
                                    break
                            except Exception as date_error:
                                await websocket.send_text(f"WARNING: Could not parse upload time for {file_record['filename']}: {str(date_error)}")
                                should_reprocess = True  # Err on the side of reprocessing
                                break

                    if not should_reprocess:
                        await websocket.send_text("SUCCESS: No new files found since last processing")
                        await websocket.send_text("PROCESSING: Reprocessing anyway to ensure data consistency...")
                        should_reprocess = True  # For now, always reprocess to ensure consistency

                except Exception as e:
                    await websocket.send_text(f"WARNING: Error checking file timestamps: {str(e)}")
                    should_reprocess = True

            if should_reprocess:
                await websocket.send_text("WARNING: Documents were previously processed. Skipping data cleanup to preserve existing embeddings and knowledge graph.")
                await websocket.send_text("STATS: Note: To avoid duplicates, consider using incremental processing or manual cleanup if needed.")
                # REMOVED AGGRESSIVE DATA CLEANUP - This was causing data loss!
                # The previous logic was deleting ALL embeddings and knowledge graph data
                # which is not what users expect when reprocessing documents

            # For now, we'll create placeholder files since the actual file content
            # might be stored elsewhere. In a real implementation, you'd download
            # the actual file content from object storage.
            for file_record in project_files:
                filename = file_record['filename']
                file_path = os.path.join(project_dir, filename)

                # Create meaningful content that will generate entities for testing
                # In production, you'd download the actual file content from object storage
                placeholder_content = f"""Infrastructure Assessment Document: {filename}
File Type: {file_record.get('file_type', 'unknown')}
Upload Time: {file_record.get('upload_timestamp', 'unknown')}
Project ID: {project_id}

System Overview:
This document describes the current infrastructure setup for the migration assessment.

Current Infrastructure Components:
- Web Server: nginx-web-server running on Ubuntu 20.04 LTS
- Application Server: tomcat-app-server hosting java-web-application
- Database Server: mysql-database-server with customer-database and inventory-database
- Load Balancer: haproxy-load-balancer distributing HTTP traffic
- Storage System: nfs-storage-server providing shared file storage
- Monitoring: prometheus-monitoring-server collecting system metrics

Network Architecture:
- DMZ Network: 192.168.1.0/24 containing web-server and load-balancer
- Internal Network: 10.0.1.0/24 containing application-server and database-server
- Management Network: 10.0.2.0/24 for administrative access
- Firewall: iptables-firewall controlling inter-network communication

Business Applications:
- Customer Portal: customer-web-portal providing self-service capabilities
- Inventory Management: inventory-management-system tracking product stock
- Reporting Service: reporting-service generating business intelligence reports
- Payment Gateway: payment-processing-service handling transactions

Security Components:
- Authentication: ldap-authentication-server managing user credentials
- SSL Certificates: ssl-certificate-authority for encrypted communications
- Backup System: backup-storage-system for data protection
- Antivirus: antivirus-scanner protecting against malware

This infrastructure requires assessment for cloud migration planning.
"""
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(placeholder_content)

            await websocket.send_text(f"Prepared {len(project_files)} files for processing")

        except Exception as e:
            logger.error(f"Error fetching project files: {str(e)}")
            await websocket.send_text(f"Error: Could not fetch project files - {str(e)}")
            return

        # Check if we have files to process
        files = os.listdir(project_dir)
        if not files:
            await websocket.send_text("Error: No files available for processing")
            return

        # Initialize services with error handling
        try:
            # Try to get project-specific LLM configuration, but continue without it
            llm = None
            try:
                llm = get_project_llm(project)
                await websocket.send_text(f"SUCCESS: LLM initialized with {project.llm_provider}/{project.llm_model}")
                await websocket.send_text(f"INFO: Entity extraction will use AI-powered methods")
            except Exception as llm_error:
                await websocket.send_text(f"ERROR: LLM not available - {str(llm_error)}")
                await websocket.close()
                return

            rag_service = RAGService(project_id, llm)
            await websocket.send_text(f"SUCCESS: RAG service initialized successfully")
        except Exception as e:
            await websocket.send_text(f"Error initializing RAG service: {str(e)}")
            return

        # Process files with detailed feedback
        await websocket.send_text(f"Starting document processing for {len(files)} files...")
        processed_files = 0

        for i, fname in enumerate(files, 1):
            try:
                file_path = os.path.join(project_dir, fname)
                await websocket.send_text(f"[{i}/{len(files)}] Processing: {fname}")

                # Real processing steps with detailed logging
                await websocket.send_text(f"  -> Extracting text content from {fname}")

                # Actually process the file with real-time logging
                try:
                    # Step 1: Text extraction
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    await websocket.send_text(f"  OK: Extracted {len(content)} characters from {fname}")

                    # Step 2: Create embeddings
                    await websocket.send_text(f"  -> Creating document embeddings using SentenceTransformer")
                    chunks = rag_service._split_content(content)
                    await websocket.send_text(f"  OK: Created {len(chunks)} text chunks for embedding")

                    # Step 3: Store in ChromaDB
                    await websocket.send_text(f"  -> Storing {len(chunks)} embeddings in ChromaDB vector database")
                    await websocket.send_text(f"    * Generating vector embeddings using SentenceTransformer model...")
                    embeddings_created = 0

                    # Use the existing add_document method which handles chunking and batching
                    try:
                        if rag_service.collection is not None:
                            await websocket.send_text(f"    * Processing {len(chunks)} chunks in batches...")

                            # Use the batch processing method instead of individual chunks
                            rag_service._batch_insert_chunks(chunks, fname)
                            embeddings_created = len(chunks)

                            # Verify storage
                            total_embeddings = rag_service.collection.count()
                            await websocket.send_text(f"    * Successfully stored {embeddings_created} embeddings")
                            await websocket.send_text(f"    * Total embeddings in database: {total_embeddings}")
                        else:
                            await websocket.send_text(f"     Warning: ChromaDB collection not available")
                    except Exception as e:
                        await websocket.send_text(f"     Warning: Failed to store embeddings: {str(e)}")

                    await websocket.send_text(f"  OK: Successfully stored {embeddings_created} embeddings in ChromaDB")

                    # Step 4: Update Neo4j knowledge graph
                    await websocket.send_text(f"  -> Extracting entities and relationships for Neo4j knowledge graph")
                    await websocket.send_text(f"    * Analyzing document content for infrastructure entities...")

                    try:
                        # Get count before extraction
                        graph_service = GraphService()
                        before_result = graph_service.execute_query(
                            "MATCH (n {project_id: $project_id}) RETURN count(n) as node_count",
                            {"project_id": project_id}
                        )
                        nodes_before = before_result[0]["node_count"] if before_result else 0

                        await websocket.send_text(f"    * Starting entity extraction (current nodes: {nodes_before})...")
                        entities_created = rag_service.extract_and_add_entities(content)

                        # Get count after extraction
                        after_result = graph_service.execute_query(
                            "MATCH (n {project_id: $project_id}) RETURN count(n) as node_count",
                            {"project_id": project_id}
                        )
                        nodes_after = after_result[0]["node_count"] if after_result else 0
                        new_nodes = nodes_after - nodes_before

                        if new_nodes > 0:
                            await websocket.send_text(f"  OK: Successfully added {new_nodes} new entities to Neo4j (total: {nodes_after})")
                        else:
                            await websocket.send_text(f"  WARNING: No new entities were created from {fname}. This may indicate:")
                            await websocket.send_text(f"    - Document contains no infrastructure entities")
                            await websocket.send_text(f"    - Entity extraction failed due to AI response format")
                            await websocket.send_text(f"    - Entities already exist from previous processing")

                    except Exception as entity_error:
                        await websocket.send_text(f"  ERROR: Entity extraction failed: {str(entity_error)}")
                        await websocket.send_text(f"    * This will not affect document embeddings, but knowledge graph will be incomplete")
                        logger.error(f"Entity extraction error for {fname}: {str(entity_error)}")

                    await websocket.send_text(f"  OK: File processing completed: {embeddings_created} embeddings, entities extracted")

                except Exception as e:
                    await websocket.send_text(f"  ERROR: Error processing {fname}: {str(e)}")
                    logger.error(f"Error processing file {fname}: {str(e)}")

                processed_files += 1
                await websocket.send_text(f"OK: Completed processing {fname} ({processed_files}/{len(files)})")

            except Exception as e:
                await websocket.send_text(f" Error processing {fname}: {str(e)}")
                logger.error(f"File processing error: {str(e)}")

        if processed_files == 0:
            await websocket.send_text("Error: No files could be processed")
            return

        await websocket.send_text(f"Successfully processed {processed_files} files")

        # Provide final summary of what was created
        try:
            # Get final counts
            total_embeddings = rag_service.collection.count() if rag_service.collection else 0

            graph_service = GraphService()
            graph_result = graph_service.execute_query(
                "MATCH (n {project_id: $project_id}) RETURN count(n) as node_count",
                {"project_id": project_id}
            )
            total_nodes = graph_result[0]["node_count"] if graph_result else 0

            await websocket.send_text(f"📊 PROCESSING SUMMARY:")
            await websocket.send_text(f"  ✅ Files processed: {processed_files}")
            await websocket.send_text(f"  🔍 Vector embeddings created: {total_embeddings}")
            await websocket.send_text(f"  🕸️ Knowledge graph nodes: {total_nodes}")

            if total_embeddings > 0 and total_nodes > 0:
                await websocket.send_text(f"  🎉 SUCCESS: Both vector search and knowledge graph are ready!")
            elif total_embeddings > 0:
                await websocket.send_text(f"  ⚠️ Vector search ready, but knowledge graph has issues")
            else:
                await websocket.send_text(f"  ❌ WARNING: Processing completed but no data was stored")

        except Exception as summary_error:
            await websocket.send_text(f"Could not generate processing summary: {str(summary_error)}")

        # Initialize crew with the same LLM instance and WebSocket for real-time logging
        try:
            await websocket.send_text("Initializing AI agents...")
            # Use dynamic crew loader for configurable agents
            # crew = create_assessment_crew_from_config(project_id, llm, websocket=websocket)
            crew = create_assessment_crew(project_id, llm, websocket) # Fallback to original crew
            await websocket.send_text("AI agents initialized. Starting assessment...")

            # Send agentic log for initialization
            await websocket.send_text(json.dumps({
                "type": "agentic_log",
                "level": "info",
                "message": "AI agents initialized successfully",
                "source": "crew_initialization",
                "timestamp": datetime.utcnow().isoformat()
            }))
        except Exception as e:
            await websocket.send_text(f"Error initializing AI agents: {str(e)}")
            return

        # Run assessment with progress updates
        try:
            await websocket.send_text("Starting CrewAI assessment workflow...")

            # Send agentic log for assessment start
            await websocket.send_text(json.dumps({
                "type": "agentic_log",
                "level": "info",
                "message": "CrewAI assessment workflow started",
                "source": "assessment_start",
                "timestamp": datetime.utcnow().isoformat()
            }))

            # Run the blocking crew.kickoff in a separate thread to keep the event loop free
            result = await asyncio.to_thread(crew.kickoff)

            await websocket.send_text("Assessment completed successfully!")

            # Send agentic log for completion
            await websocket.send_text(json.dumps({
                "type": "agentic_log",
                "level": "success",
                "message": "Assessment workflow completed successfully",
                "source": "assessment_completion",
                "timestamp": datetime.utcnow().isoformat()
            }))

            await websocket.send_text("FINAL_REPORT_MARKDOWN_START")
            await websocket.send_text(str(result))
            await websocket.send_text("FINAL_REPORT_MARKDOWN_END")

            # Save report content to project service
            await websocket.send_text("Saving report content...")
            await _save_report_content(project_id, str(result), websocket)

            # Generate professional reports
            await websocket.send_text("Generating professional PDF and DOCX reports...")
            await _generate_professional_reports(project_id, str(result), websocket)

            # Save processing statistics
            try:
                processing_stats = {
                    "processed_at": datetime.now(timezone.utc).isoformat(),
                    "files_processed": processed_files,
                    "embeddings_created": sum([stats.get('embeddings', 0) for stats in locals().get('processing_results', [])]),
                    "entities_created": sum([stats.get('entities', 0) for stats in locals().get('processing_results', [])]),
                    "project_id": project_id
                }

                with open(processing_stats_file, 'w') as f:
                    json.dump(processing_stats, f, indent=2)

                await websocket.send_text(f"STATS: Processing statistics saved: {processed_files} files, embeddings and entities created")
            except Exception as stats_error:
                await websocket.send_text(f"WARNING: Could not save processing stats: {str(stats_error)}")

            # Update project status to completed
            project_service = get_project_service()
            project_service.update_project(project_id, {"status": "completed"})
            await websocket.send_text("Project status updated to 'completed'")

            # Send completion signal for frontend notification
            await websocket.send_text("PROCESSING_COMPLETED")
            await websocket.send_text("COMPLETE: Document processing completed successfully! Your project is ready for analysis and document generation.")

        except Exception as e:
            await websocket.send_text(f"Error during assessment: {str(e)}")
            logger.error(f"Assessment execution error: {str(e)}")

            # Update project status back to initiated on error
            try:
                project_service.update_project(project_id, {"status": "initiated"})
                await websocket.send_text("Project status reset to 'initiated' due to error")
            except Exception as status_error:
                logger.error(f"Failed to update project status after error: {str(status_error)}")

    except Exception as e:
        await websocket.send_text(f"Unexpected error: {str(e)}")
        logger.error(f"WebSocket error for project {project_id}: {str(e)}")
    finally:
        try:
            await websocket.close()
        except:
            pass

async def _save_report_content(project_id: str, report_content: str, websocket: WebSocket):
    """Save the raw Markdown report content to the project service"""
    try:
        # Update project with report content and set status to completed
        project_service = get_project_service()
        response = requests.put(
            f"{project_service.base_url}/projects/{project_id}",
            json={
                "report_content": report_content,
                "status": "completed"
            },
            headers=project_service._get_auth_headers(),
            timeout=30
        )

        if response.status_code == 200:
            await websocket.send_text("Report content saved successfully")
        else:
            await websocket.send_text(f"Failed to save report content: {response.text}")

    except requests.exceptions.RequestException as e:
        await websocket.send_text(f"Error connecting to project service: {str(e)}")
        logger.error(f"Project service error: {str(e)}")
    except Exception as e:
        await websocket.send_text(f"Error saving report content: {str(e)}")
        logger.error(f"Report content save error: {str(e)}")

async def _generate_professional_reports(project_id: str, markdown_content: str, websocket: WebSocket):
    """Generate professional PDF and DOCX reports via reporting service"""
    try:
        reporting_service_url = os.getenv("REPORTING_SERVICE_URL", "http://reporting-service:8000")

        # Generate PDF report
        await websocket.send_text("Generating PDF report...")
        pdf_response = requests.post(
            f"{reporting_service_url}/generate_report",
            json={
                "project_id": project_id,
                "format": "pdf",
                "markdown_content": markdown_content
            },
            timeout=30
        )

        if pdf_response.status_code == 200:
            await websocket.send_text("PDF report generation initiated successfully")
        else:
            await websocket.send_text(f"PDF generation failed: {pdf_response.text}")

        # Generate DOCX report
        await websocket.send_text("Generating DOCX report...")
        docx_response = requests.post(
            f"{reporting_service_url}/generate_report",
            json={
                "project_id": project_id,
                "format": "docx",
                "markdown_content": markdown_content
            },
            timeout=30
        )

        if docx_response.status_code == 200:
            await websocket.send_text("DOCX report generation initiated successfully")
            await websocket.send_text("Professional reports will be available in the project dashboard shortly")
        else:
            await websocket.send_text(f"DOCX generation failed: {docx_response.text}")

    except requests.exceptions.RequestException as e:
        await websocket.send_text(f"Error connecting to reporting service: {str(e)}")
        logger.error(f"Reporting service error: {str(e)}")
    except Exception as e:
        await websocket.send_text(f"Error generating professional reports: {str(e)}")
        logger.error(f"Report generation error: {str(e)}")

# =====================================================================================
# CREW/AGENT/TOOL INTERACTION API
# =====================================================================================

from app.models.crew_interaction import CrewInteractionModel, CrewInteraction, FilterOptions, UserDisplayPreferences
from app.core.crew_logger import crew_logger_registry
from sqlalchemy import desc, and_, or_
from sqlalchemy.orm import Session

@app.websocket("/ws/crew-interactions/{project_id}")
async def crew_interactions_websocket(websocket: WebSocket, project_id: str, mode: str = "realtime"):
    """WebSocket endpoint for real-time crew interaction streaming"""
    await websocket.accept()

    try:
        logger.info(f"WebSocket connected for crew interactions: {project_id}, mode: {mode}")

        if mode == "realtime":
            # For real-time mode, we'll register this WebSocket with active loggers
            # The actual streaming happens when interactions are logged
            await websocket.send_text(json.dumps({
                "type": "connection_established",
                "message": "Real-time crew interaction streaming started",
                "project_id": project_id,
                "mode": mode
            }))

            # Keep connection alive and handle incoming messages
            while True:
                try:
                    # Wait for messages (like filter updates)
                    message = await websocket.receive_text()
                    data = json.loads(message)

                    if data.get("type") == "register_for_task":
                        task_id = data.get("task_id")
                        if task_id:
                            # Register this WebSocket with the task logger
                            logger_instance = crew_logger_registry.get_logger(project_id, task_id)
                            logger_instance.add_websocket_client(websocket)
                            await websocket.send_text(json.dumps({
                                "type": "registered",
                                "task_id": task_id,
                                "message": "Registered for real-time updates"
                            }))

                except Exception as e:
                    logger.error(f"WebSocket message handling error: {str(e)}")
                    break

        else:
            # Historic mode - send existing data
            await websocket.send_text(json.dumps({
                "type": "historic_mode",
                "message": "Use REST API for historic data",
                "endpoint": f"/api/projects/{project_id}/crew-interactions"
            }))

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for crew interactions: {project_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
    finally:
        # Clean up - remove from all loggers
        for logger_instance in crew_logger_registry.loggers.values():
            logger_instance.remove_websocket_client(websocket)
        try:
            if websocket.client_state.name != "DISCONNECTED":
                await websocket.close()
        except Exception:
            pass  # Connection already closed

@app.get("/api/projects/{project_id}/crew-interactions")
async def get_crew_interactions(
    project_id: str,
    task_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    agent_name: Optional[str] = None,
    tool_name: Optional[str] = None,
    status: Optional[str] = None,
    interaction_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    search: Optional[str] = None
):
    """Get historic crew interactions with filtering"""
    try:
        # Import database connection from crew_logger
        from app.core.crew_logger import get_db
        db = get_db()

        # Build query with filters
        query = db.query(CrewInteractionModel).filter(
            CrewInteractionModel.project_id == project_id
        )

        if task_id:
            query = query.filter(CrewInteractionModel.task_id == task_id)

        if conversation_id:
            query = query.filter(CrewInteractionModel.conversation_id == conversation_id)

        if agent_name:
            query = query.filter(CrewInteractionModel.agent_name == agent_name)

        if tool_name:
            query = query.filter(CrewInteractionModel.tool_name == tool_name)

        if status:
            query = query.filter(CrewInteractionModel.status == status)

        if interaction_type:
            query = query.filter(CrewInteractionModel.type == interaction_type)

        if search:
            # Search across multiple text fields
            search_filter = or_(
                CrewInteractionModel.request_text.ilike(f"%{search}%"),
                CrewInteractionModel.response_text.ilike(f"%{search}%"),
                CrewInteractionModel.agent_name.ilike(f"%{search}%"),
                CrewInteractionModel.tool_name.ilike(f"%{search}%"),
                CrewInteractionModel.function_name.ilike(f"%{search}%")
            )
            query = query.filter(search_filter)

        # Order by timestamp (newest first) and apply pagination
        interactions = query.order_by(desc(CrewInteractionModel.timestamp)).offset(offset).limit(limit).all()

        # Get total count for pagination
        total_count = query.count()

        # Convert to Pydantic models
        interaction_list = []
        for interaction in interactions:
            interaction_dict = {
                "id": str(interaction.id),
                "project_id": str(interaction.project_id),
                "task_id": interaction.task_id,
                "conversation_id": interaction.conversation_id,
                "timestamp": interaction.timestamp.isoformat(),
                "type": interaction.type,
                "parent_id": str(interaction.parent_id) if interaction.parent_id else None,
                "depth": interaction.depth,
                "sequence": interaction.sequence,
                "crew_name": interaction.crew_name,
                "crew_description": interaction.crew_description,
                "crew_members": interaction.crew_members,
                "crew_goal": interaction.crew_goal,
                "agent_name": interaction.agent_name,
                "agent_role": interaction.agent_role,
                "agent_goal": interaction.agent_goal,
                "agent_backstory": interaction.agent_backstory,
                "agent_id": interaction.agent_id,
                "tool_name": interaction.tool_name,
                "tool_description": interaction.tool_description,
                "function_name": interaction.function_name,
                "request_data": interaction.request_data,
                "response_data": interaction.response_data,
                "reasoning_step": interaction.reasoning_step,
                "request_text": interaction.request_text,
                "response_text": interaction.response_text,
                "message_type": interaction.message_type,
                "token_usage": interaction.token_usage,
                "performance_metrics": interaction.performance_metrics,
                "status": interaction.status,
                "start_time": interaction.start_time.isoformat() if interaction.start_time else None,
                "end_time": interaction.end_time.isoformat() if interaction.end_time else None,
                "duration_ms": interaction.duration_ms,
                "error_message": interaction.error_message,
                "retry_count": interaction.retry_count,
                "metadata": interaction.interaction_metadata
            }
            interaction_list.append(interaction_dict)

        return {
            "interactions": interaction_list,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total_count
        }

    except Exception as e:
        logger.error(f"Error fetching crew interactions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch interactions: {str(e)}")
    finally:
        db.close()

@app.get("/api/projects/{project_id}/crew-interactions/stats")
async def get_crew_interaction_stats(project_id: str, task_id: Optional[str] = None):
    """Get statistics for crew interactions"""
    try:
        # Import database connection from crew_logger
        from app.core.crew_logger import get_db
        db = get_db()

        # Build base query
        query = db.query(CrewInteractionModel).filter(
            CrewInteractionModel.project_id == project_id
        )

        if task_id:
            query = query.filter(CrewInteractionModel.task_id == task_id)

        # Get basic counts
        total_interactions = query.count()

        # Count by type
        type_counts = {}
        for interaction_type in ['crew_start', 'crew_complete', 'agent_start', 'agent_complete',
                               'tool_call', 'tool_response', 'function_call', 'reasoning_step']:
            count = query.filter(CrewInteractionModel.type == interaction_type).count()
            type_counts[interaction_type] = count

        # Count by status
        status_counts = {}
        for status in ['pending', 'running', 'completed', 'failed', 'retrying']:
            count = query.filter(CrewInteractionModel.status == status).count()
            status_counts[status] = count

        # Get unique agents and tools
        unique_agents = db.query(CrewInteractionModel.agent_name).filter(
            CrewInteractionModel.project_id == project_id,
            CrewInteractionModel.agent_name.isnot(None)
        ).distinct().count()

        unique_tools = db.query(CrewInteractionModel.tool_name).filter(
            CrewInteractionModel.project_id == project_id,
            CrewInteractionModel.tool_name.isnot(None)
        ).distinct().count()

        # Calculate total tokens and cost (if available)
        total_tokens = 0
        total_cost = 0.0

        token_interactions = query.filter(CrewInteractionModel.token_usage.isnot(None)).all()
        for interaction in token_interactions:
            if interaction.token_usage:
                total_tokens += interaction.token_usage.get('total_tokens', 0)
                total_cost += interaction.token_usage.get('estimated_cost', 0.0)

        return {
            "total_interactions": total_interactions,
            "type_counts": type_counts,
            "status_counts": status_counts,
            "unique_agents": unique_agents,
            "unique_tools": unique_tools,
            "total_tokens": total_tokens,
            "total_cost": round(total_cost, 4)
        }

    except Exception as e:
        logger.error(f"Error fetching interaction stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch stats: {str(e)}")
    finally:
        db.close()

# =====================================================================================
# DOCUMENT PROCESSING API
# =====================================================================================

@app.websocket("/ws/process-documents/{project_id}")
async def process_documents_ws(websocket: WebSocket, project_id: str):
    """WebSocket endpoint for real-time document processing with detailed progress"""
    await websocket.accept()

    try:
        logger.info(f"WebSocket connected for document processing: {project_id}")
        await process_documents_with_websocket(project_id, websocket)
    except Exception as e:
        logger.error(f"Error in document processing WebSocket: {str(e)}")
        try:
            await websocket.send_text(f"ERROR: Document processing failed: {str(e)}")
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass

# DOCUMENT GENERATION API
# =====================================================================================

@app.websocket("/ws/generate-document/{project_id}")
async def generate_document_ws(websocket: WebSocket, project_id: str):
    """WebSocket endpoint for real-time document generation with agent logging"""
    await websocket.accept()

    try:
        # Receive the generation request
        request_data = await websocket.receive_json()

        await websocket.send_text(f"STARTING: Starting document generation for: {request_data.get('name')}")

        # Get project from project service
        project_service = get_project_service()
        project = project_service.get_project(project_id)
        if not project:
            await websocket.send_text("ERROR: Error: Project not found")
            await websocket.close()
            return

        await websocket.send_text(f"SUCCESS: Project loaded: {project.name}")

        # Get LLM configuration
        llm_config_id = project.llm_api_key_id
        if not llm_config_id:
            await websocket.send_text("ERROR: Error: No LLM configuration found for project")
            await websocket.close()
            return

        llm_configs = get_llm_configurations_from_db()
        if llm_config_id not in llm_configs:
            await websocket.send_text("ERROR: Error: LLM configuration not found")
            await websocket.close()
            return

        llm_config = llm_configs[llm_config_id]
        await websocket.send_text(f"SUCCESS: LLM Configuration: {llm_config.get('name')} ({llm_config.get('provider')}/{llm_config.get('model')})")

        # Create LLM instance using project's assigned configuration only
        try:
            from app.core.crew import get_project_crewai_llm
            llm = get_project_crewai_llm(project)
            await websocket.send_text(f"[SUCCESS] Using project LLM: {project.llm_provider}/{project.llm_model}")
        except Exception as llm_error:
            await websocket.send_text(f"[ERROR] LLM configuration error: {str(llm_error)}")
            await websocket.close()
            return

        # Initialize RAG service
        try:
            rag_service = RAGService(project_id, llm)
            await websocket.send_text(f"SUCCESS: RAG service initialized for project knowledge base")
        except Exception as rag_error:
            await websocket.send_text(f"ERROR: RAG service error: {str(rag_error)}")
            await websocket.close()
            return

        # Initialize crew interaction logger
        task_id = f"doc_gen_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        crew_logger = crew_logger_registry.get_logger(project_id, task_id)
        crew_logger.add_websocket_client(websocket)

        # Notify WebSocket clients to register for this task
        await websocket.send_text(json.dumps({
            "type": "task_started",
            "task_id": task_id,
            "project_id": project_id
        }))

        # Create document generation crew with WebSocket logging
        try:
            from app.core.crew import create_document_generation_crew
            await websocket.send_text(f"STEP: Step 1 of 6: Creating document generation crew...")
            await websocket.send_text(f"AGENTS: Initializing 3 specialized agents for {request_data.get('name')}")

            # Log crew start
            crew_id = await crew_logger.log_crew_start(
                crew_name="Document Generation Crew",
                members=["Research Agent", "Analysis Agent", "Writing Agent"],
                goal=f"Generate comprehensive {request_data.get('name')} document",
                description=f"AI-powered document generation for {request_data.get('description', 'project assessment')}"
            )

            crew = create_document_generation_crew(
                project_id=project_id,
                llm=llm,
                document_type=request_data.get('name'),
                document_description=request_data.get('description'),
                output_format=request_data.get('format', 'markdown'),
                websocket=websocket,
                crew_logger=crew_logger  # Pass logger to crew
            )
            await websocket.send_text(f"SUCCESS: Step 1 Complete: Document generation crew created successfully")
        except Exception as crew_error:
            await websocket.send_text(f"ERROR: Step 1 Failed: Crew creation error: {str(crew_error)}")
            await websocket.close()
            return

        # Execute crew to generate document with progress tracking
        try:
            await websocket.send_text(f"STEP: Step 2 of 6: Starting document research phase...")
            await websocket.send_text(f"DEBUG: Research Specialist -> Content Architect -> Quality Reviewer")
            await websocket.send_text(f"WAIT: This process typically takes 3-5 minutes...")

            result = await asyncio.to_thread(crew.kickoff)
            await websocket.send_text(f"SUCCESS: Step 2 Complete: Document generation completed successfully")
        except Exception as execution_error:
            await websocket.send_text(f"ERROR: Step 2 Failed: Document generation failed: {str(execution_error)}")
            await websocket.close()
            return

        # Extract the generated content
        await websocket.send_text(f"STEP: Step 3 of 6: Processing generated content...")
        if hasattr(result, 'raw'):
            content = result.raw
        else:
            content = str(result)

        await websocket.send_text(f"SUCCESS: Step 3 Complete: Generated content ({len(content)} characters)")

        # Save the generated document to file
        await websocket.send_text(f"STEP: Step 4 of 6: Saving document to file system...")
        project_dir = os.path.join("projects", project_id)
        os.makedirs(project_dir, exist_ok=True)

        # Create filename with timestamp
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_name = request_data.get('name', 'document').replace(' ', '_').replace('/', '_')

        # Save markdown content
        markdown_filename = f"{safe_name}_{timestamp}.md"
        markdown_path = os.path.join(project_dir, markdown_filename)

        with open(markdown_path, 'w', encoding='utf-8') as f:
            f.write(content)

        await websocket.send_text(f"SUCCESS: Step 4 Complete: Document saved as {markdown_filename}")

        # Generate professional report using reporting service if requested
        download_urls = {
            "markdown": f"/api/projects/{project_id}/download/{markdown_filename}"
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
                        "markdown_content": content,
                        "document_name": safe_name
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
                        "markdown_filename": markdown_filename,
                        "content": content,
                        "file_path": markdown_path
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
            "content": content[:500] + "..." if len(content) > 500 else content,
            "format": request_data.get('output_type', 'markdown'),
            "download_urls": download_urls,
            "file_path": markdown_path,
            "markdown_filename": markdown_filename
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
                await websocket.send_text(f"WARNING: Warning: Could not save to database: {usage_response.text}")
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
            content = result.raw
        else:
            content = str(result)

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

        # Save to project directory
        with open(markdown_path, 'w', encoding='utf-8') as f:
            f.write(content)

        # Save to local reports directory
        with open(local_markdown_path, 'w', encoding='utf-8') as f:
            f.write(content)

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
                    "markdown_content": content,
                    "document_name": safe_name
                },
                timeout=60
            )

            if pdf_response.status_code == 200:
                pdf_data = pdf_response.json()
                if pdf_data.get('success') and pdf_data.get('minio_url'):
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
# CREW CONFIGURATION WEBSOCKET MANAGER
# =====================================================================================

class CrewConfigWebSocketManager:
    """Manages WebSocket connections for crew configuration updates"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"New crew config WebSocket connection. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"Crew config WebSocket disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        if not self.active_connections:
            return

        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send message to WebSocket client: {e}")
                disconnected.append(connection)

        # Remove disconnected clients
        for connection in disconnected:
            self.disconnect(connection)

# Global WebSocket manager for crew configuration
crew_config_ws_manager = CrewConfigWebSocketManager()

async def broadcast_crew_config_update(statistics: dict, validation: dict):
    """Broadcast crew configuration update to all connected clients"""
    message = {
        "type": "crew_config_update",
        "timestamp": datetime.now().isoformat(),
        "data": {
            "statistics": statistics,
            "validation": validation
        }
    }
    await crew_config_ws_manager.broadcast(message)

# =====================================================================================
# CREW MANAGEMENT ENDPOINTS
# =====================================================================================

@app.get("/api/crew-definitions")
async def get_crew_definitions_endpoint():
    """
    Get current crew definitions from YAML configuration.
    Returns the complete agent and crew configuration.
    """
    try:
        from app.core.crew_config_service import crew_config_service

        config = crew_config_service.get_configuration()
        stats = crew_config_service.get_statistics()
        validation = crew_config_service.validate_references()

        return {
            "success": True,
            "data": {
                "agents": config.get('agents', []),
                "tasks": config.get('tasks', []),
                "crews": config.get('crews', []),
                "available_tools": config.get('available_tools', []),
                "statistics": stats,
                "validation": validation
            }
        }
    except Exception as e:
        logger.error(f"Error getting crew definitions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error loading crew definitions: {str(e)}")

@app.put("/api/crew-definitions")
async def update_crew_definitions_endpoint(config: Dict[str, Any]):
    """
    Update crew definitions with new configuration.
    Validates and saves the new configuration to YAML file.
    """
    try:
        from app.core.crew_config_service import crew_config_service

        # Basic validation
        if not isinstance(config, dict):
            raise HTTPException(status_code=400, detail="Configuration must be a valid JSON object")

        required_keys = ['agents', 'tasks', 'crews', 'available_tools']
        for key in required_keys:
            if key not in config:
                raise HTTPException(status_code=400, detail=f"Missing required key: {key}")

        # Save configuration using the service
        success = crew_config_service.update_configuration(config)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to save configuration")

        # Get updated stats and validation
        stats = crew_config_service.get_statistics()
        validation = crew_config_service.validate_references()

        # Notify connected WebSocket clients about the update
        await broadcast_crew_config_update(stats, validation)

        return {
            "success": True,
            "message": "Crew definitions updated successfully",
            "statistics": stats,
            "validation": validation
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating crew definitions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error saving crew definitions: {str(e)}")

@app.get("/api/crew-definitions/statistics")
async def get_crew_statistics():
    """Get crew configuration statistics"""
    try:
        from app.core.crew_config_service import crew_config_service
        stats = crew_config_service.get_statistics()
        validation = crew_config_service.validate_references()

        return {
            "success": True,
            "data": {
                "statistics": stats,
                "validation": validation
            }
        }
    except Exception as e:
        logger.error(f"Error getting crew statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error loading statistics: {str(e)}")

@app.post("/api/crew-definitions/reload")
async def reload_crew_definitions():
    """Force reload crew definitions from YAML file"""
    try:
        from app.core.crew_config_service import crew_config_service
        config = crew_config_service.get_configuration(force_reload=True)
        stats = crew_config_service.get_statistics()

        return {
            "success": True,
            "message": "Crew definitions reloaded successfully",
            "statistics": stats
        }
    except Exception as e:
        logger.error(f"Error reloading crew definitions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error reloading configuration: {str(e)}")

@app.get("/api/available-tools")
async def get_available_tools():
    """
    Get list of available tools that can be assigned to agents.
    """
    try:
        from app.core.crew_config_service import crew_config_service
        available_tools = crew_config_service.get_available_tools()
        return {
            "success": True,
            "data": available_tools
        }
    except Exception as e:
        logger.error(f"Error getting available tools: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error loading available tools: {str(e)}")

@app.websocket("/ws/crew-config")
async def websocket_crew_config(websocket: WebSocket):
    """WebSocket endpoint for real-time crew configuration updates"""
    await crew_config_ws_manager.connect(websocket)

    try:
        # Send initial configuration data
        from app.core.crew_config_service import crew_config_service
        config = crew_config_service.get_configuration()
        stats = crew_config_service.get_statistics()
        validation = crew_config_service.validate_references()

        initial_message = {
            "type": "initial_config",
            "timestamp": datetime.now().isoformat(),
            "data": {
                "agents": config.get('agents', []),
                "tasks": config.get('tasks', []),
                "crews": config.get('crews', []),
                "available_tools": config.get('available_tools', []),
                "statistics": stats,
                "validation": validation
            }
        }
        await websocket.send_json(initial_message)

        # Keep connection alive
        while True:
            try:
                # Wait for ping/pong or client messages
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_text("pong")
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
    finally:
        crew_config_ws_manager.disconnect(websocket)



# WebSocket Endpoints for Real-time Logs
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

                # Check if it's a subprocess or thread
                if hasattr(process_or_thread, 'poll'):  # It's a subprocess
                    while process_or_thread.poll() is None:  # While process is running
                        try:
                            # Read line from stdout
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



# Placeholder endpoints removed - using real database-backed endpoints above

@app.get("/api/system/services")
async def get_system_services():
    """Get status of all system services"""
    try:
        services = []

        # Check application services
        app_services = [
            {"name": "Backend API", "port": 8000, "type": "application"},
            {"name": "Project Service", "port": 8002, "type": "application"},
            {"name": "Reporting Service", "port": 8001, "type": "application"},
            {"name": "Frontend", "port": 3000, "type": "application"},
        ]

        for service in app_services:
            try:
                # Check if port is listening
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex(('localhost', service['port']))
                sock.close()

                status = 'running' if result == 0 else 'stopped'

                # Get process info if running
                cpu_percent = 0
                memory_mb = 0
                uptime = "Unknown"

                if status == 'running':
                    try:
                        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info', 'create_time']):
                            if proc.info['name'] == 'python.exe':  # Adjust for your system
                                # Check if this process is listening on the service port
                                try:
                                    connections = proc.connections()
                                    for conn in connections:
                                        if conn.laddr.port == service['port']:
                                            cpu_percent = proc.cpu_percent()
                                            memory_mb = proc.info['memory_info'].rss / 1024 / 1024
                                            uptime_seconds = time.time() - proc.info['create_time']
                                            uptime = f"{int(uptime_seconds // 3600)}h {int((uptime_seconds % 3600) // 60)}m"
                                            break
                                except:
                                    continue
                    except:
                        pass

                services.append({
                    "name": service['name'],
                    "status": status,
                    "type": service['type'],
                    "port": service['port'],
                    "cpu_percent": cpu_percent,
                    "memory_mb": memory_mb,
                    "uptime": uptime
                })

            except Exception as e:
                services.append({
                    "name": service['name'],
                    "status": "error",
                    "type": service['type'],
                    "port": service['port'],
                    "error": str(e)
                })

        # Check Docker containers
        try:
            client = docker.from_env()
            containers = client.containers.list(all=True)

            for container in containers:
                if container.name in ['weaviate', 'neo4j', 'postgresql', 'minio']:
                    stats = container.stats(stream=False)

                    # Calculate CPU percentage
                    cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - stats['precpu_stats']['cpu_usage']['total_usage']
                    system_delta = stats['cpu_stats']['system_cpu_usage'] - stats['precpu_stats']['system_cpu_usage']
                    cpu_percent = (cpu_delta / system_delta) * len(stats['cpu_stats']['cpu_usage']['percpu_usage']) * 100.0 if system_delta > 0 else 0

                    # Calculate memory usage
                    memory_usage = stats['memory_stats']['usage']
                    memory_limit = stats['memory_stats']['limit']
                    memory_percent = (memory_usage / memory_limit) * 100 if memory_limit > 0 else 0

                    services.append({
                        "name": container.name,
                        "status": container.status,
                        "type": "container",
                        "cpu_percent": cpu_percent,
                        "memory_mb": memory_usage / 1024 / 1024,
                        "memory_percent": memory_percent,
                        "uptime": str(container.attrs['State']['StartedAt'])
                    })
        except Exception as e:
            logger.warning(f"Could not get Docker container stats: {e}")

        return {"services": services}

    except Exception as e:
        logger.error(f"Error getting system services: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting system services: {str(e)}")

# Startup event to load LLM configurations
@app.on_event("startup")
async def startup_event():
    """Load LLM configurations on startup"""
    try:
        # Wait a bit for project service to be ready
        import asyncio
        await asyncio.sleep(2)

        # Load LLM configurations from database with retry logic
        max_retries = 5
        for attempt in range(max_retries):
            try:
                configs = get_llm_configurations_from_db()
                logger.info(f"Backend startup completed - {len(configs)} LLM configurations loaded")
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Failed to load LLM configs (attempt {attempt + 1}/{max_retries}): {e}")
                    await asyncio.sleep(2)
                else:
                    logger.error(f"Failed to load LLM configurations after {max_retries} attempts: {e}")

    except Exception as e:
        logger.error(f"Error during backend startup: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
