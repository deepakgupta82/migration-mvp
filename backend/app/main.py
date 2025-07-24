import os
import sys
import tempfile
import logging
from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_ROOT = tempfile.gettempdir()
project_service = ProjectServiceClient()

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
        project_dir = os.path.join(UPLOAD_ROOT, f"project_{project_id}")
        rag_service = RAGService(project_id)
        # Add all uploaded files to RAGService
        for fname in os.listdir(project_dir):
            file_path = os.path.join(project_dir, fname)
            msg = rag_service.add_file(file_path)
            await websocket.send_text(msg)
        # Create and kickoff Crew
        llm, model = get_llm_and_model()
        crew = create_assessment_crew(project_id, llm)
        result = crew.kickoff()
        await websocket.send_text("FINAL_REPORT_MARKDOWN_START")
        await websocket.send_text(result)
        await websocket.send_text("FINAL_REPORT_MARKDOWN_END")
    except Exception as e:
        await websocket.send_text(f"Error: {str(e)}")
    finally:
        await websocket.close()
