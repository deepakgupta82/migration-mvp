import os
import sys
import tempfile
import logging
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from .core.rag_service import RAGService
from .core.crew import create_assessment_crew, get_llm_and_model
from .core.project_service import ProjectServiceClient, ProjectCreate

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

app = FastAPI()

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

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test project service connection
        projects = project_service.list_projects()

        # Test RAG service components
        test_rag = RAGService("health-check")

        return {
            "status": "healthy",
            "services": {
                "project_service": "connected",
                "rag_service": "connected",
                "weaviate": "connected",
                "neo4j": "connected"
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

@app.post("/projects")
async def create_project(project_data: ProjectCreate):
    """Create a new project via the project service"""
    try:
        project = project_service.create_project(project_data)
        return project
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create project: {str(e)}")

@app.get("/projects/{project_id}")
async def get_project(project_id: str):
    """Get a project by ID via the project service"""
    try:
        project = project_service.get_project(project_id)
        return project
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Project not found: {str(e)}")

@app.get("/projects")
async def list_projects():
    """List all projects via the project service"""
    try:
        projects = project_service.list_projects()
        return projects
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list projects: {str(e)}")

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
        # Validate project exists
        try:
            project = project_service.get_project(project_id)
            await websocket.send_text(f"Starting assessment for project: {project.name}")
        except Exception as e:
            await websocket.send_text(f"Error: Project {project_id} not found")
            return

        project_dir = os.path.join(UPLOAD_ROOT, f"project_{project_id}")

        # Check if project directory exists and has files
        if not os.path.exists(project_dir):
            await websocket.send_text("Error: No files uploaded for this project")
            return

        files = os.listdir(project_dir)
        if not files:
            await websocket.send_text("Error: No files found in project directory")
            return

        await websocket.send_text(f"Found {len(files)} files to process")

        # Initialize services with error handling
        try:
            rag_service = RAGService(project_id)
            await websocket.send_text("RAG service initialized successfully")
        except Exception as e:
            await websocket.send_text(f"Error initializing RAG service: {str(e)}")
            return

        # Process files
        processed_files = 0
        for fname in files:
            try:
                file_path = os.path.join(project_dir, fname)
                await websocket.send_text(f"Processing file: {fname}")
                msg = rag_service.add_file(file_path)
                await websocket.send_text(msg)
                processed_files += 1
            except Exception as e:
                await websocket.send_text(f"Error processing {fname}: {str(e)}")
                logger.error(f"File processing error: {str(e)}")

        if processed_files == 0:
            await websocket.send_text("Error: No files could be processed")
            return

        await websocket.send_text(f"Successfully processed {processed_files} files")

        # Initialize LLM and crew
        try:
            await websocket.send_text("Initializing AI agents...")
            llm = get_llm_and_model()
            crew = create_assessment_crew(project_id, llm)
            await websocket.send_text("AI agents initialized. Starting assessment...")
        except Exception as e:
            await websocket.send_text(f"Error initializing AI agents: {str(e)}")
            return

        # Run assessment
        try:
            result = crew.kickoff()
            await websocket.send_text("Assessment completed successfully!")
            await websocket.send_text("FINAL_REPORT_MARKDOWN_START")
            await websocket.send_text(str(result))
            await websocket.send_text("FINAL_REPORT_MARKDOWN_END")
        except Exception as e:
            await websocket.send_text(f"Error during assessment: {str(e)}")
            logger.error(f"Assessment execution error: {str(e)}")

    except Exception as e:
        await websocket.send_text(f"Unexpected error: {str(e)}")
        logger.error(f"WebSocket error for project {project_id}: {str(e)}")
    finally:
        try:
            await websocket.close()
        except:
            pass
