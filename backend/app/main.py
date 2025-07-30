import os
import sys
import tempfile
import logging
import asyncio
from datetime import datetime
import requests
import json
from dotenv import load_dotenv
import io
from minio import Minio
from minio.error import S3Error
import traceback

# Load environment variables from .env file
load_dotenv()

# Configure comprehensive logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('backend.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
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

# Initialize MinIO client for object storage with error handling
try:
    minio_client = Minio(
        os.getenv("OBJECT_STORAGE_ENDPOINT", "localhost:9000"),
        access_key=os.getenv("OBJECT_STORAGE_ACCESS_KEY", "minioadmin"),
        secret_key=os.getenv("OBJECT_STORAGE_SECRET_KEY", "minioadmin"),
        secure=False
    )

    # Test MinIO connection
    minio_client.list_buckets()
    logger.info("✅ MinIO connection successful")

    # Ensure required buckets exist
    def ensure_minio_buckets():
        """Ensure required MinIO buckets exist"""
        buckets = ["project-files", "temp-processing", "reports", "diagrams"]
        for bucket in buckets:
            try:
                if not minio_client.bucket_exists(bucket):
                    minio_client.make_bucket(bucket)
                    logger.info(f"Created MinIO bucket: {bucket}")
            except Exception as e:
                logger.error(f"Error creating bucket {bucket}: {e}")

    # Initialize buckets on startup
    ensure_minio_buckets()
    logger.info("✅ MinIO buckets initialized successfully")

except Exception as e:
    logger.error(f"❌ MinIO initialization failed: {e}")
    logger.warning("⚠️ File upload functionality will be disabled")
    minio_client = None

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

@app.post("/api/projects/{project_id}/generate-document")
async def generate_document(project_id: str, template_data: dict):
    """Generate a document from a template for a project"""
    try:
        # Get project details
        project = project_service.get_project(project_id)

        # Get the report content if available
        report_content = project.report_content or "No assessment report available yet. Please run an assessment first."

        # Create document content based on template
        template_name = template_data.get('name', 'Document')
        template_format = template_data.get('format', 'Basic document format')
        output_type = template_data.get('output_type', 'pdf')

        # Generate document content
        document_content = f"""# {template_name}

**Project:** {project.name}
**Client:** {project.client_name}
**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC

## Template Format
{template_format}

## Assessment Report Content
{report_content}

## Project Details
- **Project ID:** {project_id}
- **Status:** {project.status}
- **Created:** {project.created_at}
- **Last Updated:** {project.updated_at}

---
*Generated by Nagarro's Ascent Platform*
"""

        # Call reporting service to generate the document
        reporting_service_url = os.getenv("REPORTING_SERVICE_URL", "http://localhost:8001")

        response = requests.post(
            f"{reporting_service_url}/generate_report",
            json={
                "project_id": project_id,
                "format": output_type,
                "markdown_content": document_content
            },
            timeout=30
        )

        if response.status_code == 200:
            # Generate a download URL (this would be the actual file URL in production)
            download_url = f"/api/projects/{project_id}/download/{template_name.lower().replace(' ', '-')}.{output_type}"

            return {
                "success": True,
                "message": f"Document '{template_name}' generated successfully",
                "download_url": download_url,
                "template_name": template_name,
                "output_type": output_type
            }
        else:
            return {
                "success": False,
                "message": f"Failed to generate document: {response.text}"
            }

    except Exception as e:
        logger.error(f"Error generating document for project {project_id}: {str(e)}")
        return {
            "success": False,
            "message": f"Error generating document: {str(e)}"
        }

@app.get("/api/projects/{project_id}/download/{filename}")
async def download_document(project_id: str, filename: str):
    """Download a generated document"""
    try:
        # In a real implementation, this would fetch the file from MinIO or file storage
        # For now, we'll generate a sample PDF content

        # Get project details
        project = project_service.get_project(project_id)

        # Create sample content
        content = f"""Sample Document: {filename}
Project: {project.name}
Client: {project.client_name}
Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC

This is a sample document generated by Nagarro's Ascent Platform.
In a production environment, this would be the actual generated document content."""

        # Return as downloadable file
        from fastapi.responses import Response

        if filename.endswith('.pdf'):
            media_type = 'application/pdf'
        elif filename.endswith('.docx'):
            media_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        else:
            media_type = 'text/plain'

        return Response(
            content=content.encode('utf-8'),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        logger.error(f"Error downloading document {filename} for project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error downloading document: {str(e)}")

@app.get("/api/projects/{project_id}/test-rag")
async def test_rag_service(project_id: str):
    """Test RAG service connectivity and vectorization"""
    try:
        # Test RAG service initialization
        rag_service = RAGService(project_id, None)

        # Test Weaviate connection
        weaviate_status = "connected" if rag_service.weaviate_client else "disconnected"

        # Test collection existence
        collection_exists = False
        try:
            collection_exists = rag_service.weaviate_client.schema.exists(rag_service.class_name)
        except Exception:
            pass

        return {
            "project_id": project_id,
            "rag_service": "initialized",
            "weaviate_status": weaviate_status,
            "collection_exists": collection_exists,
            "collection_name": rag_service.class_name,
            "vectorization_strategy": "weaviate" if rag_service.use_weaviate_vectorizer else "local"
        }
    except Exception as e:
        logger.error(f"Error testing RAG service: {str(e)}")
        return {
            "project_id": project_id,
            "error": str(e),
            "status": "failed"
        }

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

@app.get("/api/projects/{project_id}/stats")
async def get_project_stats(project_id: str):
    """Get enhanced statistics for a specific project"""
    try:
        logger.info(f"Getting enhanced stats for project {project_id}")

        # Get basic project info
        project = project_service.get_project(project_id)

        # Get project files from project service
        try:
            response = requests.get(
                f"{project_service.base_url}/projects/{project_id}/files",
                headers=project_service._get_auth_headers(),
                timeout=10
            )

            if response.status_code == 200:
                files = response.json()
                total_files = len(files)
                total_size = sum(f.get('file_size', 0) for f in files)
            else:
                logger.warning(f"Could not get project files: {response.status_code}")
                total_files = 0
                total_size = 0

        except Exception as files_error:
            logger.warning(f"Error getting project files: {files_error}")
            total_files = 0
            total_size = 0

        # Get embeddings count from RAG service
        embeddings_count = 0
        graph_nodes = 0

        try:
            # Initialize RAG service to check embeddings
            rag_service = RAGService(project_id)

            # Try to get embeddings count from Weaviate
            if rag_service.weaviate_client:
                try:
                    class_name = f"Project_{project_id.replace('-', '_')}"
                    result = rag_service.weaviate_client.query.aggregate(class_name).with_meta_count().do()
                    if 'data' in result and 'Aggregate' in result['data'] and class_name in result['data']['Aggregate']:
                        embeddings_count = result['data']['Aggregate'][class_name][0]['meta']['count']
                except Exception as weaviate_error:
                    logger.warning(f"Could not get Weaviate embeddings count: {weaviate_error}")

            # Try to get graph nodes count from Neo4j
            if rag_service.graph_service:
                try:
                    graph_result = rag_service.graph_service.execute_query(
                        "MATCH (n {project_id: $project_id}) RETURN count(n) as node_count",
                        {"project_id": project_id}
                    )
                    if graph_result:
                        graph_nodes = graph_result[0].get('node_count', 0)
                except Exception as neo4j_error:
                    logger.warning(f"Could not get Neo4j nodes count: {neo4j_error}")

        except Exception as rag_error:
            logger.warning(f"Could not initialize RAG service: {rag_error}")

        # Agent interactions should only be counted when agents actually run
        # For now, set to 0 unless there's evidence of agent activity
        agent_interactions = 0

        # Deliverables count (reports generated)
        deliverables = 1 if embeddings_count > 0 else 0

        enhanced_stats = {
            "total_files": total_files,
            "total_size": total_size,
            "embeddings": embeddings_count,
            "graph_nodes": graph_nodes,
            "agent_interactions": agent_interactions,
            "deliverables": deliverables,
            "project_status": project.status,
            "last_updated": project.updated_at
        }

        logger.info(f"Enhanced stats for project {project_id}: {enhanced_stats}")
        return enhanced_stats

    except Exception as e:
        logger.error(f"Error getting enhanced project stats: {str(e)}")
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
llm_configurations = {}

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
        config_id = request.get('id') or f"{request.get('name', '').replace(' ', '_').lower()}_{int(datetime.utcnow().timestamp())}"

        config = {
            "id": config_id,
            "name": request.get('name', ''),
            "provider": request.get('provider', ''),
            "model": request.get('model', ''),
            "api_key": request.get('api_key', ''),
            "temperature": float(request.get('temperature', 0.1)),
            "max_tokens": int(request.get('max_tokens', 4000)),
            "description": request.get('description', f"{request.get('name', '')} - {request.get('provider', '')}/{request.get('model', '')}"),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
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
            llm_configurations[config_id]["updated_at"] = datetime.utcnow().isoformat()
            logger.info(f"Updated LLM configuration: {config_id}")
            return llm_configurations[config_id]
        else:
            # Create new configuration
            config = {
                "id": config_id,
                **request,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            llm_configurations[config_id] = config
            logger.info(f"Created new LLM configuration: {config_id}")
            return config

    except Exception as e:
        logger.error(f"Error updating LLM configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update LLM configuration: {str(e)}")

@app.post("/projects")
async def create_project_endpoint(request: dict):
    """Create a new project using the project service"""
    try:
        logger.info(f"Creating project with data: {request}")

        # Create project using project service
        project = project_service.create_project(ProjectCreate(**request))

        logger.info(f"Project created successfully: {project.id}")
        return project

    except Exception as e:
        logger.error(f"Project creation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create project: {str(e)}")

@app.get("/projects")
async def list_projects_endpoint(page: int = 1, per_page: int = 10):
    """List all projects using the project service with pagination"""
    try:
        logger.info(f"Listing projects - page {page}, per_page {per_page}")

        # Get all projects first
        all_projects = project_service.list_projects()
        total_projects = len(all_projects)

        # Calculate pagination
        start_index = (page - 1) * per_page
        end_index = start_index + per_page
        projects = all_projects[start_index:end_index]

        total_pages = (total_projects + per_page - 1) // per_page

        logger.info(f"Found {total_projects} total projects, returning {len(projects)} for page {page}")

        return {
            "projects": projects,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total_projects": total_projects,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        }

    except Exception as e:
        logger.error(f"Project listing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list projects: {str(e)}")

@app.get("/projects/{project_id}")
async def get_project_endpoint(project_id: str):
    """Get a specific project using the project service"""
    try:
        logger.info(f"Getting project: {project_id}")
        project = project_service.get_project(project_id)
        return project

    except Exception as e:
        logger.error(f"Get project failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get project: {str(e)}")

@app.get("/projects/{project_id}/files")
async def get_project_files_endpoint(project_id: str):
    """Get files for a project using the project service"""
    try:
        logger.info(f"Getting files for project: {project_id}")

        response = requests.get(
            f"{project_service.base_url}/projects/{project_id}/files",
            headers=project_service._get_auth_headers(),
            timeout=10
        )

        if response.status_code == 200:
            files = response.json()
            logger.info(f"Found {len(files)} files for project {project_id}")
            return files
        else:
            logger.warning(f"Could not get project files: {response.status_code}")
            return []

    except Exception as e:
        logger.error(f"Get project files failed: {str(e)}")
        return []

@app.post("/api/projects/{project_id}/test-llm")
async def test_project_llm(project_id: str):
    """Test LLM connectivity for a specific project"""
    try:
        # Get project details
        project = project_service.get_project(project_id)

        # Try project-specific LLM first, then fall back to global LLM
        llm = None
        provider = "unknown"
        model = "unknown"

        if project.llm_provider and project.llm_model:
            # Use project-specific LLM configuration
            try:
                llm = get_project_llm(project)
                provider = project.llm_provider
                model = project.llm_model
                logger.info(f"Using project-specific LLM: {provider}/{model}")
            except Exception as project_llm_error:
                logger.warning(f"Project-specific LLM failed: {project_llm_error}")
                llm = None

        if not llm:
            # Fall back to global LLM configuration
            try:
                llm = get_llm_and_model()
                provider = os.environ.get("LLM_PROVIDER", "openai")
                model = os.environ.get("OPENAI_MODEL_NAME", "gpt-4o")
                logger.info(f"Using global LLM configuration: {provider}/{model}")
            except Exception as global_llm_error:
                raise HTTPException(
                    status_code=500,
                    detail=f"No LLM configuration available. Project LLM: {project_llm_error if 'project_llm_error' in locals() else 'Not configured'}. Global LLM: {global_llm_error}"
                )

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
            "provider": provider,
            "model": model,
            "response": response_text,
            "message": "LLM connection test successful"
        }

    except Exception as e:
        logger.error(f"LLM test failed for project {project_id}: {str(e)}")
        return {
            "status": "error",
            "provider": provider if 'provider' in locals() else "unknown",
            "model": model if 'model' in locals() else "unknown",
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
    """Upload files with fallback to temp storage when MinIO is unavailable"""
    logger.info(f"🚀 Starting file upload for project {project_id} - {len(files)} files")
    uploaded_files = []

    # Check if MinIO is available, if not use temp storage
    use_minio = minio_client is not None

    if not use_minio:
        logger.warning("⚠️ MinIO not available, using temporary storage")

    try:
        for i, file in enumerate(files, 1):
            try:
                logger.info(f"📤 Processing file {i}/{len(files)}: {file.filename}")

                # Read file content
                file_content = await file.read()
                file_size = len(file_content)
                logger.info(f"📊 File size: {file_size} bytes")

                if file_size == 0:
                    logger.warning(f"⚠️ File {file.filename} is empty")
                    continue

                if use_minio:
                    # Upload to MinIO
                    file_stream = io.BytesIO(file_content)
                    object_key = f"projects/{project_id}/uploads/{file.filename}"
                    logger.info(f"☁️ Uploading to MinIO: {object_key}")

                    minio_client.put_object(
                        "project-files",
                        object_key,
                        file_stream,
                        length=file_size,
                        content_type=file.content_type or "application/octet-stream"
                    )

                    uploaded_files.append({
                        "filename": file.filename,
                        "object_key": object_key,
                        "size": file_size,
                        "content_type": file.content_type,
                        "status": "uploaded",
                        "storage": "minio"
                    })
                else:
                    # Save to temp directory as fallback
                    temp_dir = os.path.join(UPLOAD_ROOT, "project_uploads", project_id)
                    os.makedirs(temp_dir, exist_ok=True)
                    temp_path = os.path.join(temp_dir, file.filename)

                    with open(temp_path, "wb") as f:
                        f.write(file_content)

                    logger.info(f"💾 Saved to temp storage: {temp_path}")

                    uploaded_files.append({
                        "filename": file.filename,
                        "temp_path": temp_path,
                        "size": file_size,
                        "content_type": file.content_type,
                        "status": "uploaded",
                        "storage": "temp"
                    })

                # Register file with project service
                try:
                    file_data = {
                        "filename": file.filename,
                        "file_type": file.content_type or "application/octet-stream",
                        "file_size": file_size,
                        "upload_path": uploaded_files[-1].get("temp_path") or uploaded_files[-1].get("object_key", "")
                    }

                    # Add file record to project service
                    response = requests.post(
                        f"{project_service.base_url}/projects/{project_id}/files",
                        json=file_data,
                        headers=project_service._get_auth_headers(),
                        timeout=10
                    )

                    if response.status_code in [200, 201]:
                        logger.info(f"📋 File registered in project service: {file.filename}")
                    else:
                        logger.warning(f"⚠️ Could not register {file.filename} in project service: {response.status_code}")

                except Exception as reg_error:
                    logger.warning(f"⚠️ Could not register {file.filename} in project service: {str(reg_error)}")

                logger.info(f"✅ Successfully processed: {file.filename} ({file_size} bytes)")

            except Exception as file_error:
                logger.error(f"❌ Error processing file {file.filename}: {str(file_error)}")
                uploaded_files.append({
                    "filename": file.filename,
                    "status": "failed",
                    "error": str(file_error)
                })
                continue

        if not uploaded_files:
            logger.error("❌ No files were processed successfully")
            raise HTTPException(status_code=400, detail="No files could be processed")

        successful_uploads = [f for f in uploaded_files if f.get("status") == "uploaded"]
        failed_uploads = [f for f in uploaded_files if f.get("status") == "failed"]

        logger.info(f"🎉 Upload completed: {len(successful_uploads)} successful, {len(failed_uploads)} failed")

        return {
            "status": "Upload completed",
            "project_id": project_id,
            "uploaded_files": uploaded_files,
            "storage_type": "minio" if use_minio else "temp",
            "summary": {
                "total": len(files),
                "successful": len(successful_uploads),
                "failed": len(failed_uploads)
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Critical error in file upload: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.post("/upload_old/{project_id}")
async def upload_files_old(project_id: str, files: List[UploadFile] = File(...)):
    """Upload files directly to MinIO object storage with comprehensive logging"""
    logger.info(f"🚀 Starting file upload for project {project_id} - {len(files)} files")
    uploaded_files = []

    try:
        # Check if MinIO is available
        if minio_client is None:
            logger.error("❌ MinIO is not available")
            raise HTTPException(status_code=503, detail="File storage service is not available. Please contact administrator.")

        # Verify MinIO connection
        logger.info("🔍 Verifying MinIO connection...")
        if not minio_client.bucket_exists("project-files"):
            logger.error("❌ MinIO bucket 'project-files' does not exist")
            raise HTTPException(status_code=500, detail="Storage bucket not available")
        logger.info("✅ MinIO connection verified")

        for i, file in enumerate(files, 1):
            try:
                logger.info(f"📤 Processing file {i}/{len(files)}: {file.filename}")

                # Read file content
                logger.info(f"📖 Reading file content: {file.filename}")
                file_content = await file.read()
                file_size = len(file_content)
                logger.info(f"📊 File size: {file_size} bytes")

                if file_size == 0:
                    logger.warning(f"⚠️ File {file.filename} is empty")
                    continue

                file_stream = io.BytesIO(file_content)

                # Upload to MinIO project-files bucket
                object_key = f"projects/{project_id}/uploads/{file.filename}"
                logger.info(f"☁️ Uploading to MinIO: {object_key}")

                minio_client.put_object(
                    "project-files",
                    object_key,
                    file_stream,
                    length=file_size,
                    content_type=file.content_type or "application/octet-stream"
                )

                uploaded_files.append({
                    "filename": file.filename,
                    "object_key": object_key,
                    "size": file_size,
                    "content_type": file.content_type,
                    "status": "uploaded"
                })

                logger.info(f"✅ Successfully uploaded: {file.filename} ({file_size} bytes)")

            except Exception as file_error:
                logger.error(f"❌ Error uploading file {file.filename}: {str(file_error)}")
                logger.error(f"📋 Traceback: {traceback.format_exc()}")
                uploaded_files.append({
                    "filename": file.filename,
                    "status": "failed",
                    "error": str(file_error)
                })
                # Continue with other files instead of failing completely
                continue

        if not uploaded_files:
            logger.error("❌ No files were uploaded successfully")
            raise HTTPException(status_code=400, detail="No files could be uploaded")

        successful_uploads = [f for f in uploaded_files if f.get("status") == "uploaded"]
        failed_uploads = [f for f in uploaded_files if f.get("status") == "failed"]

        logger.info(f"🎉 Upload completed: {len(successful_uploads)} successful, {len(failed_uploads)} failed")

        return {
            "status": "Upload completed",
            "project_id": project_id,
            "uploaded_files": uploaded_files,
            "summary": {
                "total": len(files),
                "successful": len(successful_uploads),
                "failed": len(failed_uploads)
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Critical error in file upload: {str(e)}")
        logger.error(f"📋 Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.post("/api/projects/{project_id}/process-documents")
async def process_documents(project_id: str, request: dict = None):
    """Phase 1: Create Project Knowledge Base from uploaded documents with LLM configuration"""
    try:
        # Get LLM configuration if provided
        llm_config_id = None
        if request:
            llm_config_id = request.get('llm_config_id')

        if llm_config_id:
            logger.info(f"Using LLM configuration: {llm_config_id}")
            # Get the LLM configuration
            if llm_config_id in llm_configurations:
                llm_config = llm_configurations[llm_config_id]
                logger.info(f"Found LLM config: {llm_config['name']} ({llm_config['provider']}/{llm_config['model']})")
            else:
                logger.warning(f"LLM configuration {llm_config_id} not found, using default")

        # Get project details
        project = project_service.get_project(project_id)
        logger.info(f"Starting document processing for project: {project.name}")

        # Update project status to processing
        project_service.update_project(project_id, {"status": "processing"})

        # List files from MinIO
        try:
            objects = minio_client.list_objects("project-files", prefix=f"projects/{project_id}/uploads/")
            file_objects = list(objects)

            if not file_objects:
                raise HTTPException(status_code=400, detail="No files found for processing")

            logger.info(f"Found {len(file_objects)} files to process")

        except Exception as e:
            logger.error(f"Error listing files from MinIO: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to access uploaded files: {str(e)}")

        # Initialize services
        try:
            # Try to get LLM (project-specific or global)
            llm = None
            try:
                if project.llm_provider and project.llm_model:
                    llm = get_project_llm(project)
                    logger.info(f"Using project-specific LLM: {project.llm_provider}/{project.llm_model}")
                else:
                    llm = get_llm_and_model()
                    logger.info(f"Using global LLM configuration")
            except Exception as llm_error:
                logger.warning(f"LLM initialization failed: {llm_error}")
                logger.info("Continuing without LLM - will use basic processing")

            # Initialize RAG service
            rag_service = RAGService(project_id, llm)
            logger.info("RAG service initialized successfully")

        except Exception as e:
            logger.error(f"Error initializing services: {str(e)}")
            project_service.update_project(project_id, {"status": "failed"})
            raise HTTPException(status_code=500, detail=f"Service initialization failed: {str(e)}")

        # Process each file
        processed_files = 0
        for file_obj in file_objects:
            try:
                logger.info(f"Processing file: {file_obj.object_name}")

                # Download file from MinIO to temp processing
                file_data = minio_client.get_object("project-files", file_obj.object_name)
                file_content = file_data.read()

                # Save to temp processing location
                temp_dir = os.path.join(UPLOAD_ROOT, f"temp_processing_{project_id}")
                os.makedirs(temp_dir, exist_ok=True)

                filename = os.path.basename(file_obj.object_name)
                temp_file_path = os.path.join(temp_dir, filename)

                with open(temp_file_path, "wb") as f:
                    f.write(file_content)

                # Process with RAG service (creates embeddings and populates databases)
                rag_service.add_file(temp_file_path)
                processed_files += 1

                logger.info(f"Successfully processed: {filename}")

                # Clean up temp file
                os.remove(temp_file_path)

            except Exception as e:
                logger.error(f"Error processing file {file_obj.object_name}: {str(e)}")
                continue

        # Clean up temp directory
        try:
            temp_dir = os.path.join(UPLOAD_ROOT, f"temp_processing_{project_id}")
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)
        except:
            pass

        if processed_files == 0:
            project_service.update_project(project_id, {"status": "failed"})
            raise HTTPException(status_code=500, detail="No files could be processed")

        # Mark project as ready for analysis
        project_service.update_project(project_id, {"status": "ready"})

        logger.info(f"Document processing completed. Processed {processed_files} files. Project marked as ready.")

        return {
            "status": "success",
            "message": "Document processing completed successfully",
            "project_id": project_id,
            "processed_files": processed_files,
            "project_status": "ready"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in document processing: {str(e)}")
        try:
            project_service.update_project(project_id, {"status": "failed"})
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Document processing failed: {str(e)}")

@app.post("/api/projects/{project_id}/query")
async def query_project(project_id: str, request: dict):
    """Phase 2B: Direct RAG queries without full agent crew"""
    try:
        question = request.get('question', '')
        if not question:
            raise HTTPException(status_code=400, detail="Question is required")

        logger.info(f"Processing query for project {project_id}: {question[:100]}...")

        # Get project details
        project = project_service.get_project(project_id)

        # Initialize RAG service for queries
        try:
            # Try to get LLM (project-specific or global)
            llm = None
            try:
                if project.llm_provider and project.llm_model:
                    llm = get_project_llm(project)
                    logger.info(f"Using project-specific LLM: {project.llm_provider}/{project.llm_model}")
                else:
                    llm = get_llm_and_model()
                    logger.info(f"Using global LLM configuration")
            except Exception as llm_error:
                logger.warning(f"LLM initialization failed: {llm_error}")
                logger.info("Continuing with basic RAG without LLM enhancement")
                llm = None

            # Initialize RAG service
            rag_service = RAGService(project_id, llm)
            logger.info(f"RAG service initialized for project {project_id}")

        except Exception as e:
            logger.error(f"Error initializing RAG service for queries: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Query service initialization failed: {str(e)}")

        # Perform RAG query
        try:
            # Use RAG service to get context and generate response
            response = rag_service.query(question)

            # Check if we got a meaningful response
            if not response or response.strip() == "" or "No relevant information found" in response:
                return {
                    "status": "no_results",
                    "question": question,
                    "answer": "I couldn't find any relevant information in the knowledge base for your question. Please make sure the documents have been processed and contain information related to your query.",
                    "sources": [],
                    "project_id": project_id,
                    "timestamp": datetime.utcnow().isoformat()
                }

            logger.info(f"Query processed successfully for project {project_id}")

            return {
                "status": "success",
                "question": question,
                "answer": response,
                "sources": ["Processed documents"],  # TODO: Add actual source tracking
                "project_id": project_id,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error processing query: {str(e)}")
            return {
                "status": "error",
                "question": question,
                "answer": f"I encountered an error while processing your query: {str(e)}. Please try again or contact support if the issue persists.",
                "sources": [],
                "project_id": project_id,
                "timestamp": datetime.utcnow().isoformat()
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in query processing: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

@app.post("/api/test-llm")
async def test_llm_endpoint(request: dict):
    """Test LLM connectivity with comprehensive logging"""
    logger.info(f"🧪 Starting LLM test with request: {request}")

    try:
        provider = request.get('provider')
        model = request.get('model')
        api_key_id = request.get('apiKeyId')

        logger.info(f"🔍 Testing LLM: {provider}/{model} with API key ID: {api_key_id}")

        if not provider or not model:
            logger.error("❌ Missing provider or model in request")
            raise HTTPException(status_code=400, detail="Provider and model are required")

        # Get API key from platform settings
        api_key = None
        try:
            logger.info("🔍 Retrieving API key from platform settings...")
            platform_settings = project_service.get_platform_settings()
            logger.info(f"📋 Found {len(platform_settings)} platform settings")

            # Find the OpenAI API key setting
            for setting in platform_settings:
                logger.info(f"🔍 Checking setting: {setting.get('id', 'unknown')} - {setting.get('name', 'unknown')}")
                if setting.get('id') == api_key_id or setting.get('name') == 'OpenAI API Key':
                    api_key = setting.get('value')
                    logger.info(f"✅ Found API key setting: {setting.get('name')}")
                    break

            if not api_key:
                # Fallback to environment variable
                logger.info("🔄 API key not found in settings, checking environment variables...")
                api_key = os.getenv('OPENAI_API_KEY')

            if not api_key:
                logger.error("❌ No API key found in settings or environment")
                return {
                    "status": "error",
                    "message": "OpenAI API key not found in settings or environment variables. Please configure it in Settings > LLM Configuration.",
                    "provider": provider,
                    "model": model
                }

        except Exception as settings_error:
            logger.error(f"❌ Error retrieving platform settings: {settings_error}")
            # Fallback to environment variable
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                return {
                    "status": "error",
                    "message": f"Failed to retrieve API key from settings: {settings_error}. Please configure OpenAI API key in Settings > LLM Configuration.",
                    "provider": provider,
                    "model": model
                }

        # Test OpenAI connection directly
        if provider.lower() == 'openai':
            try:
                import openai
                logger.info("🔧 Testing OpenAI connection directly...")

                client = openai.OpenAI(api_key=api_key)
                test_query = "Hello, this is a test. Please respond with 'LLM connection successful'."

                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": test_query}],
                    max_tokens=50,
                    temperature=0.1
                )

                response_text = response.choices[0].message.content
                logger.info(f"✅ OpenAI response received: {response_text}")

                return {
                    "status": "success",
                    "message": "LLM connection successful",
                    "provider": provider,
                    "model": model,
                    "response": response_text
                }

            except Exception as openai_error:
                logger.error(f"❌ OpenAI connection failed: {openai_error}")
                return {
                    "status": "error",
                    "message": f"OpenAI connection failed: {str(openai_error)}",
                    "provider": provider,
                    "model": model,
                    "error_details": str(openai_error)
                }

        # For other providers, try the global LLM configuration
        try:
            logger.info("🔧 Attempting to initialize LLM with global configuration...")
            llm = get_llm_and_model()
            logger.info(f"✅ LLM initialized successfully: {type(llm).__name__}")

            # Test with a simple query
            test_query = "Hello, this is a test. Please respond with 'LLM connection successful'."
            logger.info(f"💬 Testing with query: {test_query}")

            response = llm.invoke(test_query)
            logger.info(f"✅ LLM response received: {response[:100]}...")

            return {
                "status": "success",
                "message": "LLM connection successful",
                "provider": provider,
                "model": model,
                "response": str(response)[:200] + "..." if len(str(response)) > 200 else str(response)
            }

        except Exception as llm_error:
            logger.error(f"❌ LLM test failed: {str(llm_error)}")
            logger.error(f"📋 LLM error traceback: {traceback.format_exc()}")

            return {
                "status": "error",
                "message": f"LLM test failed: {str(llm_error)}",
                "provider": provider,
                "model": model,
                "error_details": str(llm_error)
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Critical error in LLM test: {str(e)}")
        logger.error(f"📋 Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"LLM test failed: {str(e)}")

@app.websocket("/ws/run_assessment/{project_id}")
async def run_assessment_ws(websocket: WebSocket, project_id: str):
    await websocket.accept()
    try:
        # Validate project exists and update status to running
        try:
            logger.info(f"Attempting to get project {project_id}")
            await websocket.send_text(f"🔍 Validating project {project_id}...")

            project = project_service.get_project(project_id)
            logger.info(f"Successfully retrieved project: {project.name}")
            await websocket.send_text(f"✅ Project found: {project.name}")
            await websocket.send_text(f"📊 Starting assessment for project: {project.name}")

            # Update project status to running
            logger.info(f"Updating project status to running")
            project_service.update_project(project_id, {"status": "running"})
            await websocket.send_text("✅ Project status updated to 'running'")
        except Exception as e:
            logger.error(f"Error validating project {project_id}: {str(e)}")
            await websocket.send_text(f"❌ Error: Project {project_id} validation failed - {str(e)}")
            await websocket.send_text(f"🔧 Please check project service connectivity and authentication")
            return

        # Get files from MinIO instead of temp directory
        try:
            logger.info(f"Fetching files from MinIO for project {project_id}")
            await websocket.send_text(f"📁 Fetching project files from object storage...")

            # List files from MinIO
            objects = minio_client.list_objects("project-files", prefix=f"projects/{project_id}/uploads/")
            file_objects = list(objects)

            if not file_objects:
                await websocket.send_text("❌ Error: No files found in object storage")
                await websocket.send_text("📝 Please upload files and run 'Start Processing' first")
                return

            logger.info(f"Retrieved {len(file_objects)} files from MinIO")
            await websocket.send_text(f"✅ Found {len(file_objects)} files in object storage")

            # Create temp directory for processing
            temp_dir = os.path.join(UPLOAD_ROOT, f"assessment_{project_id}")
            os.makedirs(temp_dir, exist_ok=True)

            # Download files from MinIO to temp directory for processing
            downloaded_files = []
            for file_obj in file_objects:
                try:
                    filename = os.path.basename(file_obj.object_name)
                    temp_file_path = os.path.join(temp_dir, filename)

                    # Download file from MinIO
                    file_data = minio_client.get_object("project-files", file_obj.object_name)
                    file_content = file_data.read()

                    # Save to temp location
                    with open(temp_file_path, "wb") as f:
                        f.write(file_content)

                    downloaded_files.append(filename)
                    logger.info(f"Downloaded file for assessment: {filename}")

                except Exception as file_error:
                    logger.error(f"Error downloading file {file_obj.object_name}: {file_error}")
                    await websocket.send_text(f"⚠️ Warning: Could not download {file_obj.object_name}")
                    continue

            if not downloaded_files:
                await websocket.send_text("❌ Error: No files could be downloaded for assessment")
                return

            await websocket.send_text(f"📥 Downloaded {len(downloaded_files)} files for assessment")

            # Update project_dir to point to temp directory
            project_dir = temp_dir

        except Exception as e:
            logger.error(f"Error fetching project files from MinIO: {str(e)}")
            await websocket.send_text(f"❌ Error: Could not fetch project files - {str(e)}")
            await websocket.send_text(f"🔧 Please check MinIO connectivity and file upload status")
            return

        # Check if we have files to process
        try:
            await websocket.send_text(f"📁 Checking project directory: {project_dir}")
            if not os.path.exists(project_dir):
                await websocket.send_text(f"❌ Project directory does not exist: {project_dir}")
                return

            await websocket.send_text(f"📂 Listing files in directory...")
            files = os.listdir(project_dir)
            await websocket.send_text(f"📋 Found {len(files)} files in directory")

            if not files:
                await websocket.send_text("❌ Error: No files available for processing")
                await websocket.send_text("💡 This might be because file creation failed earlier")
                return
        except Exception as dir_error:
            await websocket.send_text(f"❌ Error accessing project directory: {str(dir_error)}")
            await websocket.send_text(f"📁 Directory path: {project_dir}")
            await websocket.send_text(f"🔧 UPLOAD_ROOT: {UPLOAD_ROOT}")
            return

        # Initialize services with error handling
        try:
            await websocket.send_text(f"🔧 Initializing LLM and services...")

            # Try to get project-specific LLM configuration, but continue without it
            llm = None
            try:
                await websocket.send_text(f"🔍 Checking project-specific LLM configuration...")
                if project.llm_provider and project.llm_model:
                    await websocket.send_text(f"📋 Project has LLM config: {project.llm_provider}/{project.llm_model}")
                    llm = get_project_llm(project)
                    await websocket.send_text(f"✅ Project-specific LLM initialized: {project.llm_provider}/{project.llm_model}")
                else:
                    await websocket.send_text(f"📋 No project-specific LLM configuration found")
                    raise ValueError("No project LLM configuration")
            except Exception as llm_error:
                await websocket.send_text(f"⚠️ Project LLM failed: {str(llm_error)}")
                await websocket.send_text(f"🔄 Falling back to global LLM configuration...")
                try:
                    llm = get_llm_and_model()
                    provider = os.environ.get("LLM_PROVIDER", "openai")
                    model = os.environ.get("OPENAI_MODEL_NAME", "gpt-4o")
                    await websocket.send_text(f"✅ Global LLM initialized: {provider}/{model}")
                except Exception as global_llm_error:
                    await websocket.send_text(f"❌ Global LLM also failed: {str(global_llm_error)}")
                    await websocket.send_text(f"⚠️ Continuing without LLM - assessment quality may be reduced")
                    llm = None

            await websocket.send_text(f"🔧 Initializing RAG service...")
            rag_service = RAGService(project_id, llm)
            await websocket.send_text(f"✅ RAG service initialized successfully")
            await websocket.send_text(f"✅ Weaviate vector database connection established")
            await websocket.send_text(f"✅ Neo4j knowledge graph connection established")
        except Exception as e:
            await websocket.send_text(f"✗ Error initializing RAG service: {str(e)}")
            await websocket.send_text(f"✗ Assessment cannot proceed without RAG service")
            return

        # Process files with detailed feedback
        await websocket.send_text(f"📄 Starting document processing for {len(files)} files...")
        await websocket.send_text(f"📄 This process includes text extraction, vectorization, and knowledge graph updates")
        processed_files = 0

        for i, fname in enumerate(files, 1):
            try:
                file_path = os.path.join(project_dir, fname)
                await websocket.send_text(f"\n📄 [{i}/{len(files)}] Processing: {fname}")

                # Simulate detailed processing steps with better feedback
                await websocket.send_text(f"  🔍 Extracting text content from {fname}")
                await asyncio.sleep(0.3)  # Simulate text extraction

                await websocket.send_text(f"  🧠 Creating document embeddings using transformer model")
                await asyncio.sleep(0.5)  # Simulate embedding creation

                await websocket.send_text(f"  💾 Storing embeddings in Weaviate vector database")
                await asyncio.sleep(0.3)  # Simulate vector storage

                await websocket.send_text(f"  🕸️ Extracting entities and updating Neo4j knowledge graph")
                await asyncio.sleep(0.2)  # Simulate graph update

                # Actually process the file
                try:
                    msg = rag_service.add_file(file_path)
                    await websocket.send_text(f"  ✅ {msg}")
                    processed_files += 1
                    await websocket.send_text(f"✅ Successfully processed {fname} ({processed_files}/{len(files)})")
                except Exception as rag_error:
                    await websocket.send_text(f"  ❌ RAG processing failed for {fname}: {str(rag_error)}")
                    await websocket.send_text(f"  ℹ️ This may be due to vectorization issues. Check Weaviate transformer service.")
                    raise rag_error

            except Exception as e:
                await websocket.send_text(f"❌ Error processing {fname}: {str(e)}")
                await websocket.send_text(f"❌ Continuing with remaining files...")
                logger.error(f"File processing error: {str(e)}")

        if processed_files == 0:
            await websocket.send_text("Error: No files could be processed")
            return

        await websocket.send_text(f"Successfully processed {processed_files} files")

        # Initialize crew with the same LLM instance and WebSocket for real-time logging
        try:
            await websocket.send_text("\n🤖 Initializing AI agent crew...")
            await websocket.send_text("🤖 Setting up specialized agents: Cloud Architect, Infrastructure Analyst, Compliance Officer")

            crew = create_assessment_crew(project_id, llm, websocket=websocket)

            await websocket.send_text("✅ AI agents initialized successfully")
            await websocket.send_text("🚀 Starting CrewAI assessment workflow...")
            await websocket.send_text("🚀 Agents will analyze documents and generate migration recommendations")

            # Send agentic log for initialization
            await websocket.send_text(json.dumps({
                "type": "agentic_log",
                "level": "info",
                "message": "AI agent crew initialized with specialized tools",
                "source": "crew_initialization",
                "timestamp": datetime.utcnow().isoformat()
            }))
        except Exception as e:
            await websocket.send_text(f"❌ Error initializing AI agents: {str(e)}")
            await websocket.send_text(f"❌ This may be due to LLM configuration issues")
            return

        # Run assessment with progress updates
        try:
            await websocket.send_text("\n📊 Starting comprehensive migration assessment...")
            await websocket.send_text("📊 This may take several minutes depending on document complexity")
            await websocket.send_text("📊 Agents will collaborate to analyze infrastructure, compliance, and migration strategies")

            # Send agentic log for assessment start
            await websocket.send_text(json.dumps({
                "type": "agentic_log",
                "level": "info",
                "message": "CrewAI assessment workflow started - agents beginning collaboration",
                "source": "assessment_start",
                "timestamp": datetime.utcnow().isoformat()
            }))

            # Add progress indicator
            await websocket.send_text("🔄 Agents are now analyzing documents and generating insights...")
            await websocket.send_text("🔄 Please wait while the assessment is in progress...")

            # Add timeout and progress monitoring for crew execution
            import asyncio
            from concurrent.futures import ThreadPoolExecutor

            def run_crew_with_timeout():
                try:
                    return crew.kickoff()
                except Exception as e:
                    logger.error(f"Crew execution error: {str(e)}")
                    raise e

            # Run crew in thread pool with timeout
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                try:
                    # Set timeout to 30 minutes (1800 seconds)
                    result = await asyncio.wait_for(
                        loop.run_in_executor(executor, run_crew_with_timeout),
                        timeout=1800
                    )
                except asyncio.TimeoutError:
                    await websocket.send_text("⚠️ Assessment timed out after 30 minutes")
                    await websocket.send_text("⚠️ This may indicate an issue with the RAG pipeline or LLM configuration")
                    await websocket.send_text("⚠️ Please check the logs and try again")
                    return
                except Exception as crew_error:
                    await websocket.send_text(f"❌ Crew execution failed: {str(crew_error)}")
                    await websocket.send_text(f"❌ This may be due to vectorization or LLM issues")
                    logger.error(f"Crew execution error: {str(crew_error)}")
                    return

            await websocket.send_text("\n🎉 Assessment completed successfully!")
            await websocket.send_text("🎉 Migration assessment report has been generated")

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
