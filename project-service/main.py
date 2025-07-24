from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List
import uuid
from datetime import datetime
import json
import os

app = FastAPI(title="Project Service", description="Microservice for managing migration assessment projects")

# In-memory storage for MVP (will be replaced with PostgreSQL)
projects_db = {}

class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    client_name: str
    client_contact: Optional[str] = None

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    client_name: Optional[str] = None
    client_contact: Optional[str] = None
    status: Optional[str] = None

class Project(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    client_name: str
    client_contact: Optional[str] = None
    status: str = "initiated"
    created_at: datetime
    updated_at: datetime

@app.post("/projects", response_model=Project, status_code=status.HTTP_201_CREATED)
async def create_project(project: ProjectCreate):
    """Create a new migration assessment project"""
    project_id = str(uuid.uuid4())
    now = datetime.now()
    
    new_project = Project(
        id=project_id,
        name=project.name,
        description=project.description,
        client_name=project.client_name,
        client_contact=project.client_contact,
        status="initiated",
        created_at=now,
        updated_at=now
    )
    
    projects_db[project_id] = new_project.dict()
    return new_project

@app.get("/projects/{project_id}", response_model=Project)
async def get_project(project_id: str):
    """Get a specific project by ID"""
    if project_id not in projects_db:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return Project(**projects_db[project_id])

@app.get("/projects", response_model=List[Project])
async def list_projects():
    """List all projects"""
    return [Project(**project) for project in projects_db.values()]

@app.put("/projects/{project_id}", response_model=Project)
async def update_project(project_id: str, project_update: ProjectUpdate):
    """Update a project"""
    if project_id not in projects_db:
        raise HTTPException(status_code=404, detail="Project not found")
    
    existing_project = projects_db[project_id]
    update_data = project_update.dict(exclude_unset=True)
    
    for key, value in update_data.items():
        if value is not None:
            existing_project[key] = value
    
    existing_project["updated_at"] = datetime.now()
    projects_db[project_id] = existing_project
    
    return Project(**existing_project)

@app.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    """Delete a project"""
    if project_id not in projects_db:
        raise HTTPException(status_code=404, detail="Project not found")
    
    del projects_db[project_id]
    return {"message": "Project deleted successfully"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
