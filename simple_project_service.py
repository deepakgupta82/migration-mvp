#!/usr/bin/env python3
"""
Simple project service for testing
"""
import uuid
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('simple_project_service.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Simple Project Service")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for testing
projects = {}
project_files = {}  # Store files by project_id

class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    client_name: str = ""
    client_contact: str = ""

class Project(BaseModel):
    id: str
    name: str
    description: str
    client_name: str
    client_contact: str
    status: str
    created_at: datetime
    updated_at: datetime

class ProjectFile(BaseModel):
    id: str
    project_id: str
    filename: str
    file_type: str
    file_size: int = 0
    upload_path: str = ""
    upload_timestamp: datetime  # Changed from created_at to match frontend
    created_at: datetime
    updated_at: datetime

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Simple project service is running"}

@app.get("/projects")
async def list_projects():
    """List all projects"""
    logger.info("Listing all projects")
    return list(projects.values())

@app.post("/projects")
async def create_project(project_data: ProjectCreate):
    """Create a new project"""
    logger.info(f"Creating project: {project_data.name}")

    project_id = str(uuid.uuid4())
    now = datetime.now()

    project = Project(
        id=project_id,
        name=project_data.name,
        description=project_data.description,
        client_name=project_data.client_name,
        client_contact=project_data.client_contact,
        status="created",
        created_at=now,
        updated_at=now
    )

    projects[project_id] = project
    logger.info(f"Project created successfully: {project_id}")

    return project

@app.get("/projects/{project_id}")
async def get_project(project_id: str):
    """Get a specific project"""
    logger.info(f"Getting project: {project_id}")

    if project_id not in projects:
        raise HTTPException(status_code=404, detail="Project not found")

    return projects[project_id]

@app.put("/projects/{project_id}")
async def update_project(project_id: str, project_data: dict):
    """Update a project"""
    logger.info(f"Updating project: {project_id}")

    if project_id not in projects:
        raise HTTPException(status_code=404, detail="Project not found")

    project = projects[project_id]

    # Update fields
    for key, value in project_data.items():
        if hasattr(project, key):
            setattr(project, key, value)

    project.updated_at = datetime.now()
    logger.info(f"Project updated successfully: {project_id}")

    return project

@app.post("/projects/{project_id}/files")
async def add_project_file(project_id: str, file_data: dict):
    """Add a file to a project"""
    logger.info(f"Adding file to project {project_id}: {file_data}")

    if project_id not in projects:
        raise HTTPException(status_code=404, detail="Project not found")

    file_id = str(uuid.uuid4())
    now = datetime.now()

    project_file = ProjectFile(
        id=file_id,
        project_id=project_id,
        filename=file_data.get('filename', ''),
        file_type=file_data.get('file_type', ''),
        file_size=file_data.get('file_size', 0),
        upload_path=file_data.get('upload_path', ''),
        upload_timestamp=now,  # Add upload_timestamp
        created_at=now,
        updated_at=now
    )

    if project_id not in project_files:
        project_files[project_id] = []

    # Check for duplicates (same filename and size)
    existing_files = project_files[project_id]
    duplicate = any(
        f.filename == project_file.filename and f.file_size == project_file.file_size
        for f in existing_files
    )

    if duplicate:
        logger.warning(f"Duplicate file detected, skipping: {project_file.filename}")
        # Return existing file instead of creating duplicate
        existing_file = next(
            f for f in existing_files
            if f.filename == project_file.filename and f.file_size == project_file.file_size
        )
        return existing_file

    project_files[project_id].append(project_file)
    logger.info(f"File added successfully: {file_id}")

    return project_file

@app.get("/projects/{project_id}/files")
async def list_project_files(project_id: str):
    """List all files for a project"""
    logger.info(f"Listing files for project: {project_id}")

    if project_id not in projects:
        raise HTTPException(status_code=404, detail="Project not found")

    return project_files.get(project_id, [])

@app.get("/projects/{project_id}/stats")
async def get_project_stats(project_id: str):
    """Get project statistics"""
    logger.info(f"Getting stats for project: {project_id}")

    if project_id not in projects:
        raise HTTPException(status_code=404, detail="Project not found")

    files = project_files.get(project_id, [])

    return {
        "project_id": project_id,
        "total_files": len(files),
        "total_size": sum(f.file_size for f in files),
        "file_types": list(set(f.file_type for f in files)),
        "last_updated": max([f.updated_at for f in files]) if files else None
    }

@app.delete("/projects/{project_id}/files")
async def clear_project_files(project_id: str):
    """Clear all files for a project (for testing)"""
    logger.info(f"Clearing files for project: {project_id}")

    if project_id not in projects:
        raise HTTPException(status_code=404, detail="Project not found")

    if project_id in project_files:
        file_count = len(project_files[project_id])
        project_files[project_id] = []
        logger.info(f"Cleared {file_count} files for project {project_id}")
        return {"message": f"Cleared {file_count} files", "project_id": project_id}
    else:
        return {"message": "No files to clear", "project_id": project_id}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
