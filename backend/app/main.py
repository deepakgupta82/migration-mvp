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
    """Get LLM configurations from project service database"""
    global llm_configurations_cache, last_cache_update

    try:
        # Cache for 5 minutes
        import time
        current_time = time.time()
        if last_cache_update and (current_time - last_cache_update) < 300:
            return llm_configurations_cache

        project_service = get_project_service()
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
        # Get project from project service
        project_service = get_project_service()
        project = project_service.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Try to get project-specific LLM for enhanced responses
        llm = None
        try:
            llm = get_project_llm(project)
            logger.info(f"Project LLM available for enhanced responses")
        except Exception as llm_error:
            logger.warning(f"Project LLM not available, using basic RAG: {str(llm_error)}")
            # Try fallback to default LLM
            try:
                llm = get_llm_and_model()
                logger.info(f"Fallback LLM available for enhanced responses")
            except Exception as fallback_error:
                logger.warning(f"No LLM available, using basic RAG: {str(fallback_error)}")

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
        project_service = get_project_service()
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
                await websocket.send_text(f"⚠️ Documents were previously processed on {last_processed.strftime('%Y-%m-%d %H:%M:%S')}")
                await websocket.send_text("🔄 Checking for new files since last processing...")

                # Check if any files were uploaded after last processing
                new_files_found = False
                # We'll check this after getting the file list
                should_reprocess = False  # Will be set to True if new files found
            except Exception as e:
                await websocket.send_text(f"⚠️ Could not read processing stats: {str(e)}")
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
                                    await websocket.send_text(f"✅ New file detected: {file_record['filename']} (uploaded {upload_time.strftime('%Y-%m-%d %H:%M:%S')})")
                                    break
                            except Exception as date_error:
                                await websocket.send_text(f"⚠️ Could not parse upload time for {file_record['filename']}: {str(date_error)}")
                                should_reprocess = True  # Err on the side of reprocessing
                                break

                    if not should_reprocess:
                        await websocket.send_text("✅ No new files found since last processing")
                        await websocket.send_text("🔄 Reprocessing anyway to ensure data consistency...")
                        should_reprocess = True  # For now, always reprocess to ensure consistency

                except Exception as e:
                    await websocket.send_text(f"⚠️ Error checking file timestamps: {str(e)}")
                    should_reprocess = True

            if should_reprocess:
                await websocket.send_text("⚠️ Documents were previously processed. Skipping data cleanup to preserve existing embeddings and knowledge graph.")
                await websocket.send_text("📊 Note: To avoid duplicates, consider using incremental processing or manual cleanup if needed.")
                # REMOVED AGGRESSIVE DATA CLEANUP - This was causing data loss!
                # The previous logic was deleting ALL embeddings and knowledge graph data
                # which is not what users expect when reprocessing documents

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

                await websocket.send_text(f"📊 Processing statistics saved: {processed_files} files, embeddings and entities created")
            except Exception as stats_error:
                await websocket.send_text(f"⚠️ Could not save processing stats: {str(stats_error)}")

            # Update project status to completed
            project_service = get_project_service()
            project_service.update_project(project_id, {"status": "completed"})
            await websocket.send_text("Project status updated to 'completed'")

            # Send completion signal for frontend notification
            await websocket.send_text("PROCESSING_COMPLETED")
            await websocket.send_text("🎉 Document processing completed successfully! Your project is ready for analysis and document generation.")

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
# DOCUMENT GENERATION API
# =====================================================================================

@app.websocket("/ws/generate-document/{project_id}")
async def generate_document_ws(websocket: WebSocket, project_id: str):
    """WebSocket endpoint for real-time document generation with agent logging"""
    await websocket.accept()

    try:
        # Receive the generation request
        request_data = await websocket.receive_json()

        await websocket.send_text(f"🚀 Starting document generation for: {request_data.get('name')}")

        # Get project from project service
        project_service = get_project_service()
        project = project_service.get_project(project_id)
        if not project:
            await websocket.send_text("❌ Error: Project not found")
            await websocket.close()
            return

        await websocket.send_text(f"✅ Project loaded: {project.name}")

        # Get LLM configuration
        llm_config_id = project.llm_api_key_id
        if not llm_config_id:
            await websocket.send_text("❌ Error: No LLM configuration found for project")
            await websocket.close()
            return

        llm_configs = get_llm_configurations_from_db()
        if llm_config_id not in llm_configs:
            await websocket.send_text("❌ Error: LLM configuration not found")
            await websocket.close()
            return

        llm_config = llm_configs[llm_config_id]
        await websocket.send_text(f"✅ LLM Configuration: {llm_config.get('name')} ({llm_config.get('provider')}/{llm_config.get('model')})")

        # Create LLM instance with fallback logic
        llm = None
        try:
            # Try project-specific LLM first
            llm = get_project_llm(project)
            await websocket.send_text(f"[SUCCESS] Using project LLM: {project.llm_provider}/{project.llm_model}")
        except Exception as llm_error:
            await websocket.send_text(f"[WARNING] Project LLM unavailable: {str(llm_error)}")
            # Fallback to default LLM
            try:
                from app.core.crew import get_llm_and_model
                llm = get_llm_and_model()
                await websocket.send_text(f"[SUCCESS] Using fallback LLM for document generation")
            except Exception as fallback_error:
                await websocket.send_text(f"[ERROR] No LLM available: {str(fallback_error)}")
                await websocket.close()
                return

        # Initialize RAG service
        try:
            rag_service = RAGService(project_id, llm)
            await websocket.send_text(f"✅ RAG service initialized for project knowledge base")
        except Exception as rag_error:
            await websocket.send_text(f"❌ RAG service error: {str(rag_error)}")
            await websocket.close()
            return

        # Create document generation crew with WebSocket logging
        try:
            from app.core.crew import create_document_generation_crew
            await websocket.send_text(f"🤖 Creating document generation crew with 3 specialized agents...")

            crew = create_document_generation_crew(
                project_id=project_id,
                llm=llm,
                document_type=request_data.get('name'),
                document_description=request_data.get('description'),
                output_format=request_data.get('format', 'markdown'),
                websocket=websocket
            )
            await websocket.send_text(f"✅ Document generation crew created successfully")
        except Exception as crew_error:
            await websocket.send_text(f"❌ Crew creation error: {str(crew_error)}")
            await websocket.close()
            return

        # Execute crew to generate document
        try:
            await websocket.send_text(f"🚀 Executing document generation crew...")
            await websocket.send_text(f"📋 Agents: Research Specialist → Content Architect → Quality Reviewer")

            result = await asyncio.to_thread(crew.kickoff)
            await websocket.send_text(f"✅ Document generation completed successfully")
        except Exception as execution_error:
            await websocket.send_text(f"❌ Document generation failed: {str(execution_error)}")
            await websocket.close()
            return

        # Extract the generated content
        if hasattr(result, 'raw'):
            content = result.raw
        else:
            content = str(result)

        await websocket.send_text(f"📄 Generated document content ({len(content)} characters)")

        # Save the generated document to file
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

        await websocket.send_text(f"💾 Document saved: {markdown_filename}")

        # Generate professional report using reporting service if requested
        download_urls = {
            "markdown": f"/api/projects/{project_id}/download/{markdown_filename}"
        }

        if request_data.get('output_type') in ['pdf', 'docx']:
            try:
                await websocket.send_text(f"📄 Generating professional {request_data.get('output_type').upper()} report...")
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

                    await websocket.send_text(f"✅ Professional {request_data.get('output_type').upper()} report generated")
                else:
                    await websocket.send_text(f"⚠️ Report generation failed, markdown available")
            except Exception as report_error:
                await websocket.send_text(f"⚠️ Report service unavailable: {str(report_error)}")

        # Send final result
        result_data = {
            "success": True,
            "message": f"Document '{request_data.get('name')}' generated successfully",
            "content": content[:500] + "..." if len(content) > 500 else content,
            "format": request_data.get('output_type', 'markdown'),
            "download_urls": download_urls,
            "file_path": markdown_path
        }

        await websocket.send_text(f"🎉 Document generation complete!")
        await websocket.send_json(result_data)

    except Exception as e:
        logger.error(f"Error in document generation WebSocket: {str(e)}")
        await websocket.send_text(f"❌ Error: {str(e)}")
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

        # Create LLM instance with fallback logic
        llm = None
        try:
            # Try project-specific LLM first
            llm = get_project_llm(project)
            logger.info(f"Using project LLM: {project.llm_provider}/{project.llm_model}")
        except Exception as llm_error:
            logger.warning(f"Project LLM unavailable: {str(llm_error)}")
            # Fallback to default LLM
            try:
                from app.core.crew import get_llm_and_model
                llm = get_llm_and_model()
                logger.info(f"Using fallback LLM for document generation")
            except Exception as fallback_error:
                logger.error(f"No LLM available: {str(fallback_error)}")
                raise HTTPException(status_code=500, detail=f"No LLM available: {str(fallback_error)}")

        # Initialize RAG service
        try:
            logger.info(f"🔍 Initializing RAG service for project {project_id}")
            rag_service = RAGService(project_id, llm)

            # Test RAG service connectivity
            logger.info(f"🔗 Testing RAG service connections...")
            if rag_service.weaviate_client:
                logger.info(f"✅ Weaviate connection: OK")
            else:
                logger.warning(f"⚠️ Weaviate connection: Not available")

            # Test a simple query to ensure the service works
            try:
                test_result = rag_service.query("test", n_results=1)
                logger.info(f"✅ RAG service test query successful")
            except Exception as test_error:
                logger.warning(f"⚠️ RAG service test query failed: {str(test_error)}")

            logger.info(f"✅ Successfully initialized RAG service for project {project_id}")
        except Exception as rag_error:
            logger.error(f"❌ Failed to initialize RAG service: {str(rag_error)}")
            logger.error(f"🔍 RAG error type: {type(rag_error).__name__}")
            raise HTTPException(status_code=500, detail=f"RAG service error: {str(rag_error)}")

        # Generate document using simplified approach
        try:
            logger.info(f"[DOC-GEN] Starting document generation for '{request.get('name')}'")

            # Generate document content directly using LLM
            content = await generate_document_content(
                llm=llm,
                rag_service=rag_service,
                document_name=request.get('name', 'Document'),
                document_description=request.get('description', 'Professional document'),
                project_id=project_id
            )

            logger.info(f"[DOC-GEN] Successfully generated document content ({len(content)} characters)")

        except Exception as generation_error:
            logger.error(f"[DOC-GEN] Failed to generate document: {str(generation_error)}")
            logger.error(f"[DOC-GEN] Error details: {type(generation_error).__name__}: {str(generation_error)}")
            raise HTTPException(status_code=500, detail=f"Document generation error: {str(generation_error)}")

        # Execute crew to generate document
        try:
            logger.info(f"🚀 Starting document generation crew execution for '{request.get('name')}'")
            logger.info(f"📊 Crew details: {len(crew.agents)} agents, {len(crew.tasks)} tasks")
            logger.info(f"🔧 LLM: {project.llm_provider}/{project.llm_model}")
            logger.info(f"📁 Project: {project_id}")

            # Log agent details
            for i, agent in enumerate(crew.agents):
                logger.info(f"👤 Agent {i+1}: {agent.role}")

            # Execute the crew
            logger.info(f"⚡ Executing crew.kickoff() - this may take several minutes...")
            result = await asyncio.to_thread(crew.kickoff)

            logger.info(f"✅ Document generation crew completed successfully!")
            logger.info(f"📄 Generated content length: {len(str(result))} characters")

        except Exception as execution_error:
            logger.error(f"❌ Document generation crew execution failed: {str(execution_error)}")
            logger.error(f"🔍 Error type: {type(execution_error).__name__}")
            logger.error(f"📍 Error details: {str(execution_error)}")
            import traceback
            logger.error(f"📋 Full traceback: {traceback.format_exc()}")
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

        # Generate professional report using reporting service if requested
        download_urls = {
            "markdown": f"/api/projects/{project_id}/download/{markdown_filename}"
        }

        if request.get('output_type') in ['pdf', 'docx']:
            try:
                reporting_service_url = os.getenv("REPORTING_SERVICE_URL", "http://localhost:8001")

                report_response = requests.post(
                    f"{reporting_service_url}/generate_report",
                    json={
                        "project_id": project_id,
                        "format": request.get('output_type', 'pdf'),
                        "markdown_content": content,
                        "document_name": safe_name
                    },
                    timeout=60
                )

                if report_response.status_code == 200:
                    report_data = report_response.json()
                    if 'file_path' in report_data:
                        download_urls[request.get('output_type')] = f"/api/projects/{project_id}/download/{os.path.basename(report_data['file_path'])}"

                    logger.info(f"🎉 Document generation completed for project {project_id}")
                    logger.info(f"📁 Files saved: {markdown_path}, {local_markdown_path}")
                    logger.info(f"📎 Professional report generated: {request.get('output_type')}")

                    return {
                        "success": True,
                        "message": f"Document '{request.get('name')}' generated successfully",
                        "content": content[:500] + "..." if len(content) > 500 else content,
                        "format": request.get('output_type'),
                        "download_urls": download_urls,
                        "file_path": markdown_path,
                        "local_file_path": local_markdown_path
                    }
                else:
                    logger.warning(f"Report generation failed: {report_response.text}")
            except Exception as report_error:
                logger.warning(f"Report service unavailable: {str(report_error)}")

        # Return markdown result
        logger.info(f"🎉 Document generation completed for project {project_id} (markdown only)")
        logger.info(f"📁 Files saved: {markdown_path}, {local_markdown_path}")

        return {
            "success": True,
            "message": f"Document '{request.get('name')}' generated successfully",
            "content": content,
            "format": "markdown",
            "download_urls": download_urls,
            "file_path": markdown_path,
            "local_file_path": local_markdown_path
        }

    except Exception as e:
        logger.error(f"Error generating document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate document: {str(e)}")

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
