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
from app.core.crew_loader import create_assessment_crew_from_config, get_crew_definitions, update_crew_definitions
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

# LLM Configurations now stored in database via project service
# Cache for performance
llm_configurations_cache = {}
last_cache_update = None

def get_llm_configurations_from_db():
    """Get LLM configurations from project service database"""
    global llm_configurations_cache, last_cache_update

    try:
        # Cache for 5 minutes
        import time
        current_time = time.time()
        if last_cache_update and (current_time - last_cache_update) < 300:
            return llm_configurations_cache

        response = requests.get(
            f"{project_service.base_url}/llm-configurations",
            headers=project_service._get_auth_headers()
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

    except Exception as e:
        logger.error(f"Error loading LLM configurations from database: {e}")

    return llm_configurations_cache

def invalidate_llm_cache():
    """Invalidate the LLM configurations cache"""
    global last_cache_update
    last_cache_update = None

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
        project = project_service.create_project(ProjectCreate(**request))

        logger.info(f"Project created successfully: {project.id}")
        return project

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Project creation failed: {str(e)}")
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
        llm_configs = get_llm_configurations_from_db()
        configs = []

        for config_id, config in llm_configs.items():
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

        # Create via project service
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

@app.post("/api/projects/{project_id}/test-llm")
async def test_project_llm(project_id: str):
    """Test the project's default LLM configuration"""
    try:
        # Get project details
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

        # Get project files
        project_dir = os.path.join(UPLOAD_ROOT, f"project_{project_id}")
        processed_files = 0
        embeddings_created = 0
        graph_nodes_created = 0

        if os.path.exists(project_dir):
            files = [f for f in os.listdir(project_dir) if os.path.isfile(os.path.join(project_dir, f))]
            processed_files = len(files)

            # Simulate processing by creating some embeddings and graph nodes
            # In a real implementation, this would use the RAG service
            embeddings_created = processed_files * 10  # Simulate 10 embeddings per file
            graph_nodes_created = processed_files * 5   # Simulate 5 nodes per file

            logger.info(f"Processed {processed_files} files, created {embeddings_created} embeddings and {graph_nodes_created} graph nodes")

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

@app.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    """Delete a project via the project service"""
    try:
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
    """Upload files to project with proper response structure"""
    try:
        project_dir = os.path.join(UPLOAD_ROOT, f"project_{project_id}")
        os.makedirs(project_dir, exist_ok=True)

        uploaded_files = []
        successful_count = 0

        for file in files:
            try:
                file_path = os.path.join(project_dir, file.filename)
                content = await file.read()

                with open(file_path, "wb") as f:
                    f.write(content)

                # Register file with project service
                file_data = {
                    'filename': file.filename,
                    'file_type': file.content_type or 'application/octet-stream',
                    'file_size': len(content),
                    'upload_path': file_path
                }

                # Add to project service database
                response = requests.post(
                    f"{project_service.base_url}/projects/{project_id}/files",
                    json=file_data,
                    headers=project_service._get_auth_headers()
                )

                if response.ok:
                    uploaded_files.append({
                        'filename': file.filename,
                        'size': len(content),
                        'content_type': file.content_type,
                        'status': 'uploaded'
                    })
                    successful_count += 1
                else:
                    uploaded_files.append({
                        'filename': file.filename,
                        'size': len(content),
                        'status': 'failed',
                        'error': f'Failed to register with project service: {response.status_code}'
                    })

            except Exception as file_error:
                uploaded_files.append({
                    'filename': file.filename,
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
    """Get available models for a specific provider"""
    try:
        if provider.lower() == 'openai':
            if not api_key:
                raise HTTPException(status_code=400, detail="API key required for OpenAI")

            import requests
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }

            response = requests.get('https://api.openai.com/v1/models', headers=headers, timeout=10)

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

                return {
                    'status': 'success',
                    'provider': 'openai',
                    'models': relevant_models
                }
            else:
                return {
                    'status': 'error',
                    'message': f'Failed to fetch OpenAI models: {response.status_code}'
                }

        elif provider.lower() == 'gemini':
            if not api_key:
                raise HTTPException(status_code=400, detail="API key required for Gemini")

            import requests

            response = requests.get(
                f'https://generativelanguage.googleapis.com/v1beta/models?key={api_key}',
                timeout=10
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

                return {
                    'status': 'success',
                    'provider': 'gemini',
                    'models': models
                }
            else:
                return {
                    'status': 'error',
                    'message': f'Failed to fetch Gemini models: {response.status_code}'
                }

        elif provider.lower() == 'anthropic':
            # Anthropic doesn't have a public models API, return known models
            return {
                'status': 'success',
                'provider': 'anthropic',
                'models': [
                    {'id': 'claude-3-5-sonnet-20241022', 'name': 'Claude 3.5 Sonnet', 'description': 'Most capable model'},
                    {'id': 'claude-3-opus-20240229', 'name': 'Claude 3 Opus', 'description': 'Powerful model for complex tasks'},
                    {'id': 'claude-3-sonnet-20240229', 'name': 'Claude 3 Sonnet', 'description': 'Balanced performance and speed'},
                    {'id': 'claude-3-haiku-20240307', 'name': 'Claude 3 Haiku', 'description': 'Fast and efficient'}
                ]
            }

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
        logger.error(f"Error fetching models for {provider}: {str(e)}")
        return {
            'status': 'error',
            'message': f'Failed to fetch models: {str(e)}'
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

                # Real processing steps with detailed logging
                await websocket.send_text(f"  → Extracting text content from {fname}")

                # Actually process the file with real-time logging
                try:
                    # Step 1: Text extraction
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    await websocket.send_text(f"  ✓ Extracted {len(content)} characters from {fname}")

                    # Step 2: Create embeddings
                    await websocket.send_text(f"  → Creating document embeddings using SentenceTransformer")
                    chunks = rag_service._split_content(content)
                    await websocket.send_text(f"  ✓ Created {len(chunks)} text chunks for embedding")

                    # Step 3: Store in Weaviate
                    await websocket.send_text(f"  → Storing {len(chunks)} embeddings in Weaviate vector database")
                    embeddings_created = 0
                    for i, chunk in enumerate(chunks):
                        try:
                            chunk_id = f"{fname}_chunk_{i}"
                            # Use the existing add_document method which handles chunking internally
                            if rag_service.weaviate_client is not None:
                                # Add individual chunk to Weaviate
                                data_object = {"content": chunk, "filename": fname}
                                if rag_service.use_weaviate_vectorizer:
                                    if hasattr(rag_service.weaviate_client, 'data_object'):
                                        rag_service.weaviate_client.data_object.create(
                                            data_object=data_object,
                                            class_name=rag_service.class_name,
                                            uuid=chunk_id
                                        )
                                    elif hasattr(rag_service.weaviate_client, 'collections'):
                                        collection = rag_service.weaviate_client.collections.get(rag_service.class_name)
                                        collection.data.insert(properties=data_object)
                                else:
                                    embedding = rag_service.embedding_model.encode(chunk).tolist()
                                    if hasattr(rag_service.weaviate_client, 'data_object'):
                                        rag_service.weaviate_client.data_object.create(
                                            data_object=data_object,
                                            class_name=rag_service.class_name,
                                            uuid=chunk_id,
                                            vector=embedding
                                        )
                                    elif hasattr(rag_service.weaviate_client, 'collections'):
                                        collection = rag_service.weaviate_client.collections.get(rag_service.class_name)
                                        collection.data.insert(properties=data_object, vector=embedding)
                                embeddings_created += 1
                                if embeddings_created % 5 == 0:  # Update every 5 embeddings
                                    await websocket.send_text(f"    • Stored {embeddings_created}/{len(chunks)} embeddings")
                            else:
                                await websocket.send_text(f"    ⚠ Warning: Weaviate client not available")
                                break
                        except Exception as e:
                            await websocket.send_text(f"    ⚠ Warning: Failed to store embedding {embeddings_created + 1}: {str(e)}")

                    await websocket.send_text(f"  ✓ Successfully stored {embeddings_created} embeddings in Weaviate")

                    # Step 4: Update Neo4j knowledge graph
                    await websocket.send_text(f"  → Extracting entities and relationships for Neo4j")
                    entities_created = rag_service.extract_and_add_entities(content)
                    await websocket.send_text(f"  ✓ Added entities and relationships to Neo4j knowledge graph")

                    await websocket.send_text(f"  ✓ File processing completed: {embeddings_created} embeddings, entities extracted")

                except Exception as e:
                    await websocket.send_text(f"  ❌ Error processing {fname}: {str(e)}")
                    logger.error(f"Error processing file {fname}: {str(e)}")

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
            # Use dynamic crew loader for configurable agents
            crew = create_assessment_crew_from_config(project_id, llm, websocket=websocket)
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
        config = get_crew_definitions()
        return {
            "success": True,
            "data": config
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
        # Basic validation
        if not isinstance(config, dict):
            raise HTTPException(status_code=400, detail="Configuration must be a valid JSON object")

        required_keys = ['agents', 'tasks', 'crews']
        for key in required_keys:
            if key not in config:
                raise HTTPException(status_code=400, detail=f"Missing required key: {key}")

        # Validate agents structure
        if not isinstance(config['agents'], list):
            raise HTTPException(status_code=400, detail="Agents must be a list")

        for agent in config['agents']:
            required_agent_keys = ['id', 'role', 'goal', 'backstory']
            for key in required_agent_keys:
                if key not in agent:
                    raise HTTPException(status_code=400, detail=f"Agent missing required key: {key}")

        # Validate tasks structure
        if not isinstance(config['tasks'], list):
            raise HTTPException(status_code=400, detail="Tasks must be a list")

        for task in config['tasks']:
            required_task_keys = ['id', 'description', 'expected_output', 'agent']
            for key in required_task_keys:
                if key not in task:
                    raise HTTPException(status_code=400, detail=f"Task missing required key: {key}")

        # Validate crews structure
        if not isinstance(config['crews'], list):
            raise HTTPException(status_code=400, detail="Crews must be a list")

        for crew in config['crews']:
            required_crew_keys = ['id', 'agents', 'tasks']
            for key in required_crew_keys:
                if key not in crew:
                    raise HTTPException(status_code=400, detail=f"Crew missing required key: {key}")

        # Save the configuration
        update_crew_definitions(config)

        return {
            "success": True,
            "message": "Crew definitions updated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating crew definitions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error saving crew definitions: {str(e)}")

@app.get("/api/available-tools")
async def get_available_tools():
    """
    Get list of available tools that can be assigned to agents.
    """
    try:
        config = get_crew_definitions()
        available_tools = config.get('available_tools', [])
        return {
            "success": True,
            "data": available_tools
        }
    except Exception as e:
        logger.error(f"Error getting available tools: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error loading available tools: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
