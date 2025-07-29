from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Optional, List
import uuid
from datetime import datetime, timedelta
import json
import os
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import (
    get_db, create_tables, ProjectModel, ProjectFileModel,
    UserModel, PlatformSettingModel, DeliverableTemplateModel
)
from auth import (
    authenticate_user, create_access_token, get_current_user, get_current_admin,
    get_password_hash, create_first_admin, ACCESS_TOKEN_EXPIRE_MINUTES
)
from schemas import (
    UserCreate, UserResponse, Token, ProjectCreate, ProjectResponse, ProjectUpdate,
    PlatformSettingCreate, PlatformSettingResponse, PlatformSettingUpdate,
    DeliverableTemplateCreate, DeliverableTemplateResponse, DeliverableTemplateUpdate,
    ProjectFileCreate, ProjectFileResponse, ProjectStats
)

app = FastAPI(title="Nagarro's Ascent Project Service", description="Microservice for managing migration assessment projects")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create database tables on startup
try:
    print("Creating database tables...")
    create_tables()
    print("Database tables created successfully")
except Exception as e:
    print(f"Warning: Could not create database tables: {e}")

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

# =====================================================================================
# Authentication Endpoints
# =====================================================================================

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Authenticate user and return JWT token."""
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/users/register", response_model=UserResponse)
async def register_user(user: UserCreate, db: Session = Depends(get_db)):
    """Register a new user. First user becomes platform admin."""
    # Check if user already exists
    db_user = db.query(UserModel).filter(UserModel.email == user.email).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Check if this is the first user
    user_count = db.query(UserModel).count()
    role = "platform_admin" if user_count == 0 else "user"

    # Create new user
    hashed_password = get_password_hash(user.password)
    db_user = UserModel(
        email=user.email,
        hashed_password=hashed_password,
        role=role
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.get("/users/me", response_model=UserResponse)
async def read_users_me(current_user: UserModel = Depends(get_current_user)):
    """Get current user information."""
    return current_user

@app.get("/users", response_model=List[UserResponse])
async def list_users(current_user: UserModel = Depends(get_current_admin), db: Session = Depends(get_db)):
    """List all users (admin only)."""
    users = db.query(UserModel).all()
    return users

# =====================================================================================
# Project Endpoints (with Authentication)
# =====================================================================================

@app.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project: ProjectCreate,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new migration assessment project"""
    db_project = ProjectModel(
        name=project.name,
        description=project.description,
        client_name=project.client_name,
        client_contact=project.client_contact,
        status="initiated",
        # LLM configuration
        llm_provider=project.llm_provider,
        llm_model=project.llm_model,
        llm_api_key_id=project.llm_api_key_id,
        llm_temperature=project.llm_temperature,
        llm_max_tokens=project.llm_max_tokens
    )

    # Associate the project with the current user
    db_project.users.append(current_user)

    db.add(db_project)
    db.commit()
    db.refresh(db_project)

    return db_project

# Dashboard Stats - Must be before {project_id} route
@app.get("/projects/stats", response_model=ProjectStats)
async def get_project_stats(
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get dashboard statistics"""
    # Platform admins see all projects, users see only their projects
    if current_user.role == "platform_admin":
        total_projects = db.query(ProjectModel).count()
        active_projects = db.query(ProjectModel).filter(ProjectModel.status.in_(["initiated", "running"])).count()
        completed_assessments = db.query(ProjectModel).filter(ProjectModel.status == "completed").count()
    else:
        user_projects = db.query(ProjectModel).join(ProjectModel.users).filter(UserModel.id == current_user.id)
        total_projects = user_projects.count()
        active_projects = user_projects.filter(ProjectModel.status.in_(["initiated", "running"])).count()
        completed_assessments = user_projects.filter(ProjectModel.status == "completed").count()

    # For now, we'll set average_risk_score to None since we don't have risk scoring yet
    # This can be enhanced later when risk scoring is implemented
    average_risk_score = None

    return ProjectStats(
        total_projects=total_projects,
        active_projects=active_projects,
        completed_assessments=completed_assessments,
        average_risk_score=average_risk_score
    )

@app.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific project by ID"""
    db_project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check if user has access to this project
    if current_user.role != "platform_admin" and current_user not in db_project.users:
        raise HTTPException(status_code=403, detail="Access denied")

    return db_project

@app.get("/projects", response_model=List[ProjectResponse])
async def list_projects(
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List projects accessible to the current user"""
    if current_user.role == "platform_admin":
        # Platform admins see all projects
        db_projects = db.query(ProjectModel).all()
    else:
        # Regular users see only their projects
        db_projects = db.query(ProjectModel).join(ProjectModel.users).filter(UserModel.id == current_user.id).all()

    return db_projects

@app.put("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    project_update: ProjectUpdate,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a project"""
    db_project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check if user has access to this project
    if current_user.role != "platform_admin" and current_user not in db_project.users:
        raise HTTPException(status_code=403, detail="Access denied")

    update_data = project_update.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        if value is not None:
            setattr(db_project, key, value)

    db_project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_project)

    return db_project

@app.delete("/projects/{project_id}")
async def delete_project(
    project_id: str,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a project"""
    db_project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check if user has access to this project
    if current_user.role != "platform_admin" and current_user not in db_project.users:
        raise HTTPException(status_code=403, detail="Access denied")

    db.delete(db_project)
    db.commit()
    return {"message": "Project deleted successfully"}

# =====================================================================================
# Project Files Management
# =====================================================================================

class ProjectFileCreate(BaseModel):
    filename: str
    file_type: Optional[str] = None

@app.post("/projects/{project_id}/files", response_model=ProjectFileResponse, status_code=status.HTTP_201_CREATED)
async def create_project_file(
    project_id: str,
    file_data: ProjectFileCreate,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add a file record to a project"""
    # Verify project exists and user has access
    db_project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    if current_user.role != "platform_admin" and current_user not in db_project.users:
        raise HTTPException(status_code=403, detail="Access denied")

    db_file = ProjectFileModel(
        filename=file_data.filename,
        file_type=file_data.file_type,
        project_id=project_id
    )

    db.add(db_file)
    db.commit()
    db.refresh(db_file)

    return db_file

@app.get("/projects/{project_id}/files", response_model=List[ProjectFileResponse])
async def get_project_files(
    project_id: str,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all files for a project"""
    # Verify project exists and user has access
    db_project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    if current_user.role != "platform_admin" and current_user not in db_project.users:
        raise HTTPException(status_code=403, detail="Access denied")

    db_files = db.query(ProjectFileModel).filter(ProjectFileModel.project_id == project_id).all()
    return db_files

# =====================================================================================
# Platform Settings Endpoints (Admin Only)
# =====================================================================================

@app.get("/settings", response_model=List[PlatformSettingResponse])
async def list_platform_settings(
    current_admin: UserModel = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """List all platform settings (admin only)"""
    settings = db.query(PlatformSettingModel).all()
    return settings

@app.post("/settings", response_model=PlatformSettingResponse, status_code=status.HTTP_201_CREATED)
async def create_platform_setting(
    setting: PlatformSettingCreate,
    current_admin: UserModel = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Create a new platform setting (admin only)"""
    # Check if setting already exists
    existing_setting = db.query(PlatformSettingModel).filter(PlatformSettingModel.key == setting.key).first()
    if existing_setting:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Setting with this key already exists"
        )

    db_setting = PlatformSettingModel(
        key=setting.key,
        value=setting.value,
        description=setting.description,
        last_updated_by=current_admin.id
    )

    db.add(db_setting)
    db.commit()
    db.refresh(db_setting)
    return db_setting

@app.put("/settings/{setting_key}", response_model=PlatformSettingResponse)
async def update_platform_setting(
    setting_key: str,
    setting_update: PlatformSettingUpdate,
    current_admin: UserModel = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Update a platform setting (admin only)"""
    db_setting = db.query(PlatformSettingModel).filter(PlatformSettingModel.key == setting_key).first()
    if not db_setting:
        raise HTTPException(status_code=404, detail="Setting not found")

    update_data = setting_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            setattr(db_setting, key, value)

    db_setting.last_updated_by = current_admin.id
    db_setting.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_setting)
    return db_setting

@app.delete("/settings/{setting_key}")
async def delete_platform_setting(
    setting_key: str,
    current_admin: UserModel = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Delete a platform setting (admin only)"""
    db_setting = db.query(PlatformSettingModel).filter(PlatformSettingModel.key == setting_key).first()
    if not db_setting:
        raise HTTPException(status_code=404, detail="Setting not found")

    db.delete(db_setting)
    db.commit()
    return {"message": "Setting deleted successfully"}

# =====================================================================================
# Deliverable Template Endpoints
# =====================================================================================

@app.get("/projects/{project_id}/deliverables", response_model=List[DeliverableTemplateResponse])
async def list_deliverable_templates(
    project_id: str,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List deliverable templates for a project"""
    # Verify project exists and user has access
    db_project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    if current_user.role != "platform_admin" and current_user not in db_project.users:
        raise HTTPException(status_code=403, detail="Access denied")

    templates = db.query(DeliverableTemplateModel).filter(DeliverableTemplateModel.project_id == project_id).all()
    return templates

@app.post("/projects/{project_id}/deliverables", response_model=DeliverableTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_deliverable_template(
    project_id: str,
    template: DeliverableTemplateCreate,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new deliverable template for a project"""
    # Verify project exists and user has access
    db_project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    if current_user.role != "platform_admin" and current_user not in db_project.users:
        raise HTTPException(status_code=403, detail="Access denied")

    db_template = DeliverableTemplateModel(
        name=template.name,
        description=template.description,
        prompt=template.prompt,
        project_id=project_id
    )

    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template

@app.put("/projects/{project_id}/deliverables/{template_id}", response_model=DeliverableTemplateResponse)
async def update_deliverable_template(
    project_id: str,
    template_id: str,
    template_update: DeliverableTemplateUpdate,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a deliverable template"""
    # Verify project exists and user has access
    db_project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    if current_user.role != "platform_admin" and current_user not in db_project.users:
        raise HTTPException(status_code=403, detail="Access denied")

    db_template = db.query(DeliverableTemplateModel).filter(
        DeliverableTemplateModel.id == template_id,
        DeliverableTemplateModel.project_id == project_id
    ).first()
    if not db_template:
        raise HTTPException(status_code=404, detail="Template not found")

    update_data = template_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            setattr(db_template, key, value)

    db_template.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_template)
    return db_template

@app.delete("/projects/{project_id}/deliverables/{template_id}")
async def delete_deliverable_template(
    project_id: str,
    template_id: str,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a deliverable template"""
    # Verify project exists and user has access
    db_project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    if current_user.role != "platform_admin" and current_user not in db_project.users:
        raise HTTPException(status_code=403, detail="Access denied")

    db_template = db.query(DeliverableTemplateModel).filter(
        DeliverableTemplateModel.id == template_id,
        DeliverableTemplateModel.project_id == project_id
    ).first()
    if not db_template:
        raise HTTPException(status_code=404, detail="Template not found")

    db.delete(db_template)
    db.commit()
    return {"message": "Template deleted successfully"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
