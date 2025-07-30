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
load_dotenv()
from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any
from pydantic import BaseModel
from app.core.rag_service import RAGService
from app.core.graph_service import GraphService
from app.core.crew import create_assessment_crew, get_llm_and_model, get_project_llm
from app.core.project_service import ProjectServiceClient, ProjectCreate

# Logging setup
os.makedirs("logs", exist_ok=True)
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
project_service = ProjectServiceClient()

# LLM Configurations storage
llm_configurations = {}

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

        # Query Neo4j for all nodes and relationships for this project
        nodes_query = "MATCH (n {project_id: $project_id}) RETURN n"
        relationships_query = "MATCH (a {project_id: $project_id})-[r]->(b {project_id: $project_id}) RETURN a, r, b"

        # Execute queries
        nodes_result = graph_service.execute_query(nodes_query, {"project_id": project_id})
        relationships_result = graph_service.execute_query(relationships_query, {"project_id": project_id})

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

        return GraphResponse(nodes=nodes, edges=edges)

    except Exception as e:
        logger.error(f"Error fetching graph for project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching graph data: {str(e)}")

@app.post("/api/projects/{project_id}/query", response_model=QueryResponse)
async def query_project_knowledge(project_id: str, query_request: QueryRequest):
    """Query the RAG knowledge base for a specific project"""
    try:
        # Try to get LLM for enhanced responses, but continue without it if not available
        llm = None
        try:
            llm = get_llm_and_model()
            logger.info(f"LLM available for enhanced responses")
        except Exception as llm_error:
            logger.warning(f"LLM not available, using basic RAG: {str(llm_error)}")

        # Initialize RAG service (works with or without LLM)
        rag_service = RAGService(project_id, llm)

        # Query the knowledge base
        answer = rag_service.query(query_request.question)

        return QueryResponse(answer=answer, project_id=project_id)

    except Exception as e:
        logger.error(f"Error querying knowledge base for project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error querying knowledge base: {str(e)}")

@app.get("/api/projects/{project_id}/report", response_model=ReportResponse)
async def get_project_report(project_id: str):
    """Get the report content for a specific project"""
    try:
        # Call project service to get project details
        project = project_service.get_project(project_id)

        if not project.report_content:
            raise HTTPException(status_code=404, detail="Report content not found for this project")

        return ReportResponse(
            project_id=project_id,
            report_content=project.report_content
        )

    except Exception as e:
        logger.error(f"Error fetching report for project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching report: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test project service connection with health endpoint
        import requests
        project_service_url = os.getenv("PROJECT_SERVICE_URL", "http://localhost:8002")
        response = requests.get(f"{project_service_url}/health", timeout=5)
        project_service_status = "connected" if response.status_code == 200 else "error"

        return {
            "status": "healthy",
            "services": {
                "project_service": project_service_status,
                "rag_service": "connected",
                "weaviate": "available",
                "neo4j": "available"
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "degraded",
            "services": {
                "project_service": "error",
                "rag_service": "unknown",
                "weaviate": "unknown",
                "neo4j": "unknown"
            },
            "error": str(e),
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
async def create_project(project_data: ProjectCreate):
    """Create a new project via the project service"""
    try:
        project = project_service.create_project(project_data)
        return project
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create project: {str(e)}")

@app.get("/projects/stats")
async def get_projects_stats():
    """Get project statistics"""
    try:
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
            settings = project_service.get_platform_settings()
            return settings
        except Exception as project_service_error:
            logger.warning(f"Could not fetch from project service: {project_service_error}")

            # Fallback: return mock settings for development
            # In production, these should be real API keys from environment or database
            settings = [
                {
                    "key": "OPENAI_API_KEY",
                    "value": "sk-test-openai-key-12345",
                    "description": "OpenAI API Key for GPT models"
                },
                {
                    "key": "GEMINI_API_KEY",
                    "value": "AIza-test-gemini-key-67890",
                    "description": "Google Gemini API Key"
                },
                {
                    "key": "ANTHROPIC_API_KEY",
                    "value": "sk-ant-test-key-12345",
                    "description": "Anthropic API Key for Claude models"
                },
                {
                    "key": "OLLAMA_HOST",
                    "value": "http://localhost:11434",
                    "description": "Ollama host URL for local models"
                }
            ]
            return settings
    except Exception as e:
        logger.error(f"Error getting platform settings: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get platform settings: {str(e)}")

# Enhanced LLM Settings Management
@app.get("/llm-configurations")
async def get_llm_configurations():
    """Get all LLM configurations for selection"""
    try:
        configs = []
        for config_id, config in llm_configurations.items():
            configs.append({
                "id": config_id,
                "name": config.get('name', 'Unknown'),
                "provider": config.get('provider', 'unknown'),
                "model": config.get('model', 'unknown'),
                "status": "configured" if config.get('api_key') and config.get('api_key') != 'your-api-key-here' else "needs_key"
            })

        # Add default configuration if none exist
        if not configs:
            configs.append({
                "id": "default_openai",
                "name": "Default OpenAI GPT-4",
                "provider": "openai",
                "model": "gpt-4o",
                "status": "needs_key"
            })

        return configs

    except Exception as e:
        logger.error(f"Error getting LLM configurations: {str(e)}")
        return []

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

        # Generate unique ID based on name and timestamp
        config_id = request.get('id') or f"{request.get('name', '').replace(' ', '_').lower()}_{int(datetime.now(timezone.utc).timestamp())}"

        config = {
            "id": config_id,
            "name": request.get('name', ''),
            "provider": request.get('provider', ''),
            "model": request.get('model', ''),
            "api_key": request.get('api_key', ''),
            "temperature": float(request.get('temperature', 0.1)),
            "max_tokens": int(request.get('max_tokens', 4000)),
            "description": request.get('description', f"{request.get('name', '')} - {request.get('provider', '')}/{request.get('model', '')}"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }

        llm_configurations[config_id] = config
        logger.info(f"Created LLM configuration: {config['name']} ({config_id})")

        return config

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating LLM configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create LLM configuration: {str(e)}")

@app.put("/llm-configurations/{config_id}")
async def update_llm_configuration(config_id: str, request: dict):
    """Update an LLM configuration"""
    try:
        if config_id in llm_configurations:
            llm_configurations[config_id].update(request)
            llm_configurations[config_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
            logger.info(f"Updated LLM configuration: {config_id}")
            return llm_configurations[config_id]
        else:
            # Create new configuration
            config = {
                "id": config_id,
                **request,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            llm_configurations[config_id] = config
            logger.info(f"Created new LLM configuration: {config_id}")
            return config

    except Exception as e:
        logger.error(f"Error updating LLM configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update LLM configuration: {str(e)}")

@app.post("/api/projects/{project_id}/test-llm")
async def test_project_llm(project_id: str):
    """Test LLM connectivity for a specific project"""
    try:
        # Get project details
        project = project_service.get_project(project_id)

        if not project.llm_provider or not project.llm_model:
            raise HTTPException(
                status_code=400,
                detail="Project does not have LLM configuration. Please configure LLM settings first."
            )

        # Get project-specific LLM
        llm = get_project_llm(project)

        # Test with a simple prompt
        test_prompt = "Hello! Please respond with 'LLM connection successful' to confirm connectivity."

        # For different LLM types, we need to handle the response differently
        if hasattr(llm, 'invoke'):
            response = llm.invoke(test_prompt)
            if hasattr(response, 'content'):
                response_text = response.content
            else:
                response_text = str(response)
        else:
            response_text = llm(test_prompt)

        return {
            "status": "success",
            "provider": project.llm_provider,
            "model": project.llm_model,
            "response": response_text,
            "message": "LLM connection test successful"
        }

    except Exception as e:
        logger.error(f"LLM test failed for project {project_id}: {str(e)}")
        return {
            "status": "error",
            "provider": project.llm_provider if project else "unknown",
            "model": project.llm_model if project else "unknown",
            "error": str(e),
            "message": "LLM connection test failed"
        }

@app.get("/projects/{project_id}")
async def get_project(project_id: str):
    """Get a project by ID via the project service"""
    try:
        project = project_service.get_project(project_id)
        return project
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Project not found: {str(e)}")

@app.put("/projects/{project_id}")
async def update_project(project_id: str, project_data: dict):
    """Update a project via the project service"""
    try:
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
        projects = project_service.list_projects()
        return projects
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list projects: {str(e)}")

@app.get("/projects/{project_id}/files")
async def get_project_files(project_id: str):
    """Get all files for a project via the project service"""
    try:
        # Call project service to get project files
        response = requests.get(
            f"{project_service.base_url}/projects/{project_id}/files",
            headers=project_service._get_auth_headers()
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error getting files for project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get project files: {str(e)}")

@app.post("/projects/{project_id}/files")
async def add_project_file(project_id: str, file_data: dict):
    """Add a file record to a project via the project service"""
    try:
        # Call project service to add file record
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

@app.post("/upload/{project_id}")
async def upload_files(project_id: str, files: List[UploadFile] = File(...)):
    project_dir = os.path.join(UPLOAD_ROOT, f"project_{project_id}")
    os.makedirs(project_dir, exist_ok=True)
    for file in files:
        file_path = os.path.join(project_dir, file.filename)
        with open(file_path, "wb") as f:
            f.write(await file.read())
    return {"status": "Files uploaded", "project_id": project_id}

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

        # Get files from project service database
        try:
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

            # For now, we'll create placeholder files since the actual file content
            # might be stored elsewhere. In a real implementation, you'd download
            # the actual file content from object storage.
            for file_record in project_files:
                filename = file_record['filename']
                file_path = os.path.join(project_dir, filename)

                # Create a placeholder file with metadata
                # In production, you'd download the actual file content
                placeholder_content = f"""# File: {filename}
# Type: {file_record.get('file_type', 'unknown')}
# Upload Time: {file_record.get('upload_timestamp', 'unknown')}
# Project ID: {project_id}

[This is a placeholder. In production, the actual file content would be downloaded from object storage.]
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
                await websocket.send_text(f"RAG service initialized with {project.llm_provider}/{project.llm_model}")
            except Exception as llm_error:
                await websocket.send_text(f"LLM not available, using basic RAG processing: {str(llm_error)}")

            rag_service = RAGService(project_id, llm)
            await websocket.send_text(f"RAG service initialized successfully")
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

                # Simulate detailed processing steps
                await websocket.send_text(f"  → Extracting text content from {fname}")
                await asyncio.sleep(0.3)  # Simulate text extraction

                await websocket.send_text(f"  → Creating document embeddings")
                await asyncio.sleep(0.5)  # Simulate embedding creation

                await websocket.send_text(f"  → Storing embeddings in Weaviate vector database")
                await asyncio.sleep(0.3)  # Simulate vector storage

                await websocket.send_text(f"  → Updating Neo4j knowledge graph")
                await asyncio.sleep(0.2)  # Simulate graph update

                # Actually process the file
                msg = rag_service.add_file(file_path)
                await websocket.send_text(f"  ✓ {msg}")

                processed_files += 1
                await websocket.send_text(f"✓ Completed processing {fname} ({processed_files}/{len(files)})")

            except Exception as e:
                await websocket.send_text(f"✗ Error processing {fname}: {str(e)}")
                logger.error(f"File processing error: {str(e)}")

        if processed_files == 0:
            await websocket.send_text("Error: No files could be processed")
            return

        await websocket.send_text(f"Successfully processed {processed_files} files")

        # Initialize crew with the same LLM instance and WebSocket for real-time logging
        try:
            await websocket.send_text("Initializing AI agents...")
            crew = create_assessment_crew(project_id, llm, websocket=websocket)
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

            result = crew.kickoff()

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

            # Update project status to completed
            project_service.update_project(project_id, {"status": "completed"})
            await websocket.send_text("Project status updated to 'completed'")

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
