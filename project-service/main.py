from fastapi import FastAPI, HTTPException, status, Depends
from pydantic import BaseModel
from typing import Optional, List
import uuid
from datetime import datetime
import json
import os
from sqlalchemy.orm import Session
from database import get_db, create_tables, ProjectModel

app = FastAPI(title="Project Service", description="Microservice for managing migration assessment projects")

# Create database tables on startup
@app.on_event("startup")
def startup_event():
    create_tables()

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        db = next(get_db())
        db.execute("SELECT 1")
        db.close()

        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

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
    report_url: Optional[str] = None

class Project(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    client_name: str
    client_contact: Optional[str] = None
    status: str = "initiated"
    report_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

@app.post("/projects", response_model=Project, status_code=status.HTTP_201_CREATED)
async def create_project(project: ProjectCreate, db: Session = Depends(get_db)):
    """Create a new migration assessment project"""
    db_project = ProjectModel(
        name=project.name,
        description=project.description,
        client_name=project.client_name,
        client_contact=project.client_contact,
        status="initiated"
    )

    db.add(db_project)
    db.commit()
    db.refresh(db_project)

    return Project(
        id=str(db_project.id),
        name=db_project.name,
        description=db_project.description,
        client_name=db_project.client_name,
        client_contact=db_project.client_contact,
        status=db_project.status,
        report_url=db_project.report_url,
        created_at=db_project.created_at,
        updated_at=db_project.updated_at
    )

@app.get("/projects/{project_id}", response_model=Project)
async def get_project(project_id: str, db: Session = Depends(get_db)):
    """Get a specific project by ID"""
    db_project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    return Project(
        id=str(db_project.id),
        name=db_project.name,
        description=db_project.description,
        client_name=db_project.client_name,
        client_contact=db_project.client_contact,
        status=db_project.status,
        report_url=db_project.report_url,
        created_at=db_project.created_at,
        updated_at=db_project.updated_at
    )

@app.get("/projects", response_model=List[Project])
async def list_projects(db: Session = Depends(get_db)):
    """List all projects"""
    db_projects = db.query(ProjectModel).all()
    return [
        Project(
            id=str(project.id),
            name=project.name,
            description=project.description,
            client_name=project.client_name,
            client_contact=project.client_contact,
            status=project.status,
            report_url=project.report_url,
            created_at=project.created_at,
            updated_at=project.updated_at
        )
        for project in db_projects
    ]

@app.put("/projects/{project_id}", response_model=Project)
async def update_project(project_id: str, project_update: ProjectUpdate, db: Session = Depends(get_db)):
    """Update a project"""
    db_project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    update_data = project_update.dict(exclude_unset=True)

    for key, value in update_data.items():
        if value is not None:
            setattr(db_project, key, value)

    db_project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_project)

    return Project(
        id=str(db_project.id),
        name=db_project.name,
        description=db_project.description,
        client_name=db_project.client_name,
        client_contact=db_project.client_contact,
        status=db_project.status,
        report_url=db_project.report_url,
        created_at=db_project.created_at,
        updated_at=db_project.updated_at
    )

@app.delete("/projects/{project_id}")
async def delete_project(project_id: str, db: Session = Depends(get_db)):
    """Delete a project"""
    db_project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    db.delete(db_project)
    db.commit()
    return {"message": "Project deleted successfully"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
