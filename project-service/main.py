from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import uuid
from datetime import datetime
import json
import os
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db, create_tables, ProjectModel, ProjectFileModel

app = FastAPI(title="Project Service", description="Microservice for managing migration assessment projects")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
        db.execute(text("SELECT 1"))
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
    report_content: Optional[str] = None
    report_artifact_url: Optional[str] = None

class Project(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    client_name: str
    client_contact: Optional[str] = None
    status: str = "initiated"
    report_url: Optional[str] = None
    report_content: Optional[str] = None
    report_artifact_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class ProjectFileCreate(BaseModel):
    filename: str
    file_type: Optional[str] = None

class ProjectFile(BaseModel):
    id: str
    filename: str
    file_type: Optional[str] = None
    upload_timestamp: datetime
    project_id: str

class ProjectStats(BaseModel):
    total_projects: int
    active_projects: int
    completed_assessments: int
    average_risk_score: Optional[float] = None

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
        report_content=db_project.report_content,
        report_artifact_url=db_project.report_artifact_url,
        created_at=db_project.created_at,
        updated_at=db_project.updated_at
    )

# Dashboard Stats - Must be before {project_id} route
@app.get("/projects/stats", response_model=ProjectStats)
async def get_project_stats(db: Session = Depends(get_db)):
    """Get dashboard statistics"""
    total_projects = db.query(ProjectModel).count()
    active_projects = db.query(ProjectModel).filter(ProjectModel.status.in_(["initiated", "running"])).count()
    completed_assessments = db.query(ProjectModel).filter(ProjectModel.status == "completed").count()

    # For now, we'll set average_risk_score to None since we don't have risk scoring yet
    # This can be enhanced later when risk scoring is implemented
    average_risk_score = None

    return ProjectStats(
        total_projects=total_projects,
        active_projects=active_projects,
        completed_assessments=completed_assessments,
        average_risk_score=average_risk_score
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
        report_content=db_project.report_content,
        report_artifact_url=db_project.report_artifact_url,
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
            report_content=project.report_content,
            report_artifact_url=project.report_artifact_url,
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
        report_content=db_project.report_content,
        report_artifact_url=db_project.report_artifact_url,
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

# Project Files Management
@app.post("/projects/{project_id}/files", response_model=ProjectFile, status_code=status.HTTP_201_CREATED)
async def create_project_file(project_id: str, file_data: ProjectFileCreate, db: Session = Depends(get_db)):
    """Add a file record to a project"""
    # Verify project exists
    db_project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    db_file = ProjectFileModel(
        filename=file_data.filename,
        file_type=file_data.file_type,
        project_id=project_id
    )

    db.add(db_file)
    db.commit()
    db.refresh(db_file)

    return ProjectFile(
        id=str(db_file.id),
        filename=db_file.filename,
        file_type=db_file.file_type,
        upload_timestamp=db_file.upload_timestamp,
        project_id=str(db_file.project_id)
    )

@app.get("/projects/{project_id}/files", response_model=List[ProjectFile])
async def get_project_files(project_id: str, db: Session = Depends(get_db)):
    """Get all files for a project"""
    # Verify project exists
    db_project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    db_files = db.query(ProjectFileModel).filter(ProjectFileModel.project_id == project_id).all()

    return [
        ProjectFile(
            id=str(file.id),
            filename=file.filename,
            file_type=file.file_type,
            upload_timestamp=file.upload_timestamp,
            project_id=str(file.project_id)
        )
        for file in db_files
    ]



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
