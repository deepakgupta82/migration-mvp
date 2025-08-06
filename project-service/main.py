from fastapi import FastAPI, HTTPException, status, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Optional, List
import uuid
from datetime import datetime, timedelta
import json
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('project_service.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import (
    get_db, create_tables, ProjectModel, ProjectFileModel,
    UserModel, PlatformSettingModel, DeliverableTemplateModel, LLMConfigurationModel, ModelCacheModel, TemplateUsageModel
)
from auth import (
    authenticate_user, create_access_token, get_current_user, get_current_admin,
    get_password_hash, create_first_admin, ACCESS_TOKEN_EXPIRE_MINUTES
)
from schemas import (
    UserCreate, UserResponse, Token, ProjectCreate, ProjectResponse, ProjectUpdate,
    PlatformSettingCreate, PlatformSettingResponse, PlatformSettingUpdate,
    DeliverableTemplateCreate, DeliverableTemplateResponse, DeliverableTemplateUpdate,
    ProjectFileCreate, ProjectFileResponse, ProjectStats, LLMConfigurationCreate,
    LLMConfigurationResponse, LLMConfigurationUpdate
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

# Seed default models
def seed_default_models():
    """Seed default models for all providers"""
    try:
        db = next(get_db())

        # Check if models already exist
        existing_models = db.query(ModelCacheModel).first()
        if existing_models:
            print("Models already seeded, skipping...")
            return

        default_models = [
            # OpenAI Models
            {"id": "openai_gpt-4o", "provider": "openai", "model_id": "gpt-4o", "model_name": "GPT-4o", "description": "OpenAI GPT-4o - Most capable model"},
            {"id": "openai_gpt-4o-mini", "provider": "openai", "model_id": "gpt-4o-mini", "model_name": "GPT-4o Mini", "description": "OpenAI GPT-4o Mini - Fast and efficient"},
            {"id": "openai_gpt-4-turbo", "provider": "openai", "model_id": "gpt-4-turbo", "model_name": "GPT-4 Turbo", "description": "OpenAI GPT-4 Turbo"},
            {"id": "openai_gpt-3.5-turbo", "provider": "openai", "model_id": "gpt-3.5-turbo", "model_name": "GPT-3.5 Turbo", "description": "OpenAI GPT-3.5 Turbo"},

            # Gemini Models
            {"id": "gemini_gemini-2.0-flash-exp", "provider": "gemini", "model_id": "gemini-2.0-flash-exp", "model_name": "Gemini 2.0 Flash", "description": "Google Gemini 2.0 Flash (Experimental)"},
            {"id": "gemini_gemini-1.5-pro", "provider": "gemini", "model_id": "gemini-1.5-pro", "model_name": "Gemini 1.5 Pro", "description": "Google Gemini 1.5 Pro"},
            {"id": "gemini_gemini-1.5-flash", "provider": "gemini", "model_id": "gemini-1.5-flash", "model_name": "Gemini 1.5 Flash", "description": "Google Gemini 1.5 Flash"},

            # Anthropic Models
            {"id": "anthropic_claude-3-5-sonnet-20241022", "provider": "anthropic", "model_id": "claude-3-5-sonnet-20241022", "model_name": "Claude 3.5 Sonnet", "description": "Anthropic Claude 3.5 Sonnet - Most capable model"},
            {"id": "anthropic_claude-3-opus-20240229", "provider": "anthropic", "model_id": "claude-3-opus-20240229", "model_name": "Claude 3 Opus", "description": "Anthropic Claude 3 Opus"},
            {"id": "anthropic_claude-3-sonnet-20240229", "provider": "anthropic", "model_id": "claude-3-sonnet-20240229", "model_name": "Claude 3 Sonnet", "description": "Anthropic Claude 3 Sonnet"},
            {"id": "anthropic_claude-3-haiku-20240307", "provider": "anthropic", "model_id": "claude-3-haiku-20240307", "model_name": "Claude 3 Haiku", "description": "Anthropic Claude 3 Haiku"},
        ]

        for model_data in default_models:
            model = ModelCacheModel(**model_data)
            db.add(model)

        db.commit()
        print(f"Seeded {len(default_models)} default models")

    except Exception as e:
        print(f"Warning: Could not seed default models: {e}")
    finally:
        db.close()

try:
    seed_default_models()
except Exception as e:
    print(f"Warning: Could not seed default models: {e}")

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
    """List projects accessible to the current user (latest first)"""
    if current_user.role == "platform_admin":
        # Platform admins see all projects, ordered by creation date (latest first)
        db_projects = db.query(ProjectModel).order_by(ProjectModel.created_at.desc()).all()
    else:
        # Regular users see only their projects, ordered by creation date (latest first)
        db_projects = db.query(ProjectModel).join(ProjectModel.users).filter(UserModel.id == current_user.id).order_by(ProjectModel.created_at.desc()).all()

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
    file_size: Optional[int] = None  # File size in bytes

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
        file_size=file_data.file_size,
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

@app.delete("/projects/{project_id}/files/{file_id}")
async def delete_project_file(
    project_id: str,
    file_id: str,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a file from a project"""
    # Verify project exists and user has access
    db_project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    if current_user.role != "platform_admin" and current_user not in db_project.users:
        raise HTTPException(status_code=403, detail="Access denied")

    # Find and delete the file
    db_file = db.query(ProjectFileModel).filter(
        ProjectFileModel.id == file_id,
        ProjectFileModel.project_id == project_id
    ).first()

    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")

    db.delete(db_file)
    db.commit()

    return {"message": "File deleted successfully"}

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

@app.get("/platform-settings", response_model=List[PlatformSettingResponse])
async def list_platform_settings_alias(
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all platform settings (alias endpoint for frontend compatibility)"""
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

# LLM Configuration Management
@app.get("/llm-configurations", response_model=List[LLMConfigurationResponse])
async def list_llm_configurations(
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all LLM configurations"""
    configurations = db.query(LLMConfigurationModel).all()
    return configurations

@app.post("/llm-configurations", response_model=LLMConfigurationResponse, status_code=status.HTTP_201_CREATED)
async def create_llm_configuration(
    config: LLMConfigurationCreate,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new LLM configuration"""
    # Generate unique ID based on name and timestamp
    import time
    config_id = f"{config.name.replace(' ', '_').lower()}_{int(time.time())}"

    db_config = LLMConfigurationModel(
        id=config_id,
        name=config.name,
        provider=config.provider,
        model=config.model,
        api_key=config.api_key,  # In production, encrypt this
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        description=config.description,
        created_by=current_user.id
    )

    db.add(db_config)
    db.commit()
    db.refresh(db_config)

    logger.info(f"Created LLM configuration: {config.name} ({config_id}) by user {current_user.email}")
    return db_config

@app.get("/llm-configurations/{config_id}", response_model=LLMConfigurationResponse)
async def get_llm_configuration(
    config_id: str,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific LLM configuration"""
    config = db.query(LLMConfigurationModel).filter(LLMConfigurationModel.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="LLM configuration not found")
    return config

@app.put("/llm-configurations/{config_id}", response_model=LLMConfigurationResponse)
async def update_llm_configuration(
    config_id: str,
    config_update: LLMConfigurationUpdate,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update an LLM configuration"""
    db_config = db.query(LLMConfigurationModel).filter(LLMConfigurationModel.id == config_id).first()
    if not db_config:
        raise HTTPException(status_code=404, detail="LLM configuration not found")

    # Update fields
    for field, value in config_update.dict(exclude_unset=True).items():
        setattr(db_config, field, value)

    db_config.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_config)

    logger.info(f"Updated LLM configuration: {config_id} by user {current_user.email}")
    return db_config

# Removed debug endpoints

@app.delete("/llm-configurations/{config_id}")
async def delete_llm_configuration(
    config_id: str,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete an LLM configuration"""
    db_config = db.query(LLMConfigurationModel).filter(LLMConfigurationModel.id == config_id).first()
    if not db_config:
        raise HTTPException(status_code=404, detail="LLM configuration not found")

    # Check if any projects are using this configuration
    projects_using_config = db.query(ProjectModel).filter(ProjectModel.llm_api_key_id == config_id).count()
    if projects_using_config > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete LLM configuration. {projects_using_config} project(s) are using it."
        )

    db.delete(db_config)
    db.commit()

    logger.info(f"Deleted LLM configuration: {config_id} by user {current_user.email}")
    return {"message": "LLM configuration deleted successfully"}


# ============================================================================
# MODEL CACHE ENDPOINTS
# ============================================================================

@app.get("/models/{provider}")
async def get_cached_models(provider: str, db: Session = Depends(get_db)):
    """Get cached models for a provider"""
    try:
        models = db.query(ModelCacheModel).filter(
            ModelCacheModel.provider == provider.lower(),
            ModelCacheModel.is_active == True
        ).all()

        return {
            "status": "success",
            "provider": provider,
            "models": [
                {
                    "id": model.model_id,
                    "name": model.model_name,
                    "description": model.description or f"{provider.title()} {model.model_name}"
                }
                for model in models
            ],
            "cached": True,
            "last_updated": models[0].last_updated.isoformat() if models else None
        }
    except Exception as e:
        logger.error(f"Error fetching cached models for {provider}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch cached models: {str(e)}")


@app.post("/models/{provider}/cache")
async def cache_models(provider: str, models_data: dict, db: Session = Depends(get_db)):
    """Cache models for a provider"""
    try:
        # Clear existing cache for this provider
        db.query(ModelCacheModel).filter(ModelCacheModel.provider == provider.lower()).delete()

        # Add new models to cache
        for model_data in models_data.get("models", []):
            cache_entry = ModelCacheModel(
                id=f"{provider.lower()}_{model_data['id']}",
                provider=provider.lower(),
                model_id=model_data["id"],
                model_name=model_data.get("name", model_data["id"]),
                description=model_data.get("description"),
                is_active=True
            )
            db.add(cache_entry)

        db.commit()

        logger.info(f"Cached {len(models_data.get('models', []))} models for provider {provider}")
        return {
            "status": "success",
            "message": f"Cached {len(models_data.get('models', []))} models for {provider}",
            "provider": provider
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error caching models for {provider}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to cache models: {str(e)}")

# Template Usage Tracking Endpoints
@app.post("/template-usage")
async def track_template_usage(
    template_name: str,
    template_type: str,
    project_id: str,
    output_type: str = "pdf",
    generation_status: str = "completed",
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Track template usage for statistics"""
    try:
        usage_record = TemplateUsageModel(
            template_name=template_name,
            template_type=template_type,
            project_id=project_id,
            used_by=current_user.id,
            output_type=output_type,
            generation_status=generation_status
        )

        db.add(usage_record)
        db.commit()
        db.refresh(usage_record)

        return {"success": True, "usage_id": str(usage_record.id)}
    except Exception as e:
        db.rollback()
        logger.error(f"Error tracking template usage: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to track template usage: {str(e)}")

@app.get("/projects/{project_id}/template-usage")
async def get_project_template_usage(
    project_id: str,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get template usage statistics for a specific project"""
    try:
        # Verify project access
        db_project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
        if not db_project:
            raise HTTPException(status_code=404, detail="Project not found")

        if current_user.role != "platform_admin" and current_user not in db_project.users:
            raise HTTPException(status_code=403, detail="Access denied")

        # Get usage statistics
        from sqlalchemy import func
        usage_stats = db.query(
            TemplateUsageModel.template_name,
            TemplateUsageModel.template_type,
            func.count(TemplateUsageModel.id).label('usage_count'),
            func.max(TemplateUsageModel.used_at).label('last_used')
        ).filter(
            TemplateUsageModel.project_id == project_id
        ).group_by(
            TemplateUsageModel.template_name,
            TemplateUsageModel.template_type
        ).all()

        return {
            "project_id": project_id,
            "template_usage": [
                {
                    "template_name": stat.template_name,
                    "template_type": stat.template_type,
                    "usage_count": stat.usage_count,
                    "last_used": stat.last_used.isoformat() if stat.last_used else None
                }
                for stat in usage_stats
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting project template usage: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get template usage: {str(e)}")

@app.get("/template-usage/global")
async def get_global_template_usage(
    current_user: UserModel = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get global template usage statistics (admin only)"""
    try:
        from sqlalchemy import func
        usage_stats = db.query(
            TemplateUsageModel.template_name,
            TemplateUsageModel.template_type,
            func.count(TemplateUsageModel.id).label('total_usage'),
            func.count(func.distinct(TemplateUsageModel.project_id)).label('projects_used'),
            func.max(TemplateUsageModel.used_at).label('last_used')
        ).group_by(
            TemplateUsageModel.template_name,
            TemplateUsageModel.template_type
        ).all()

        return {
            "global_template_usage": [
                {
                    "template_name": stat.template_name,
                    "template_type": stat.template_type,
                    "total_usage": stat.total_usage,
                    "projects_used": stat.projects_used,
                    "last_used": stat.last_used.isoformat() if stat.last_used else None
                }
                for stat in usage_stats
            ]
        }
    except Exception as e:
        logger.error(f"Error getting global template usage: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get global template usage: {str(e)}")

# Startup function to initialize database
@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    try:
        # Create tables
        create_tables()

        # Load existing LLM configurations
        db = next(get_db())
        existing_configs = db.query(LLMConfigurationModel).count()
        logger.info(f"Found {existing_configs} existing LLM configurations")
        db.close()

    except Exception as e:
        logger.error(f"Error during startup initialization: {str(e)}")

@app.get("/projects/{project_id}/generation-history")
async def get_project_generation_history(
    project_id: str,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get document generation history for a specific project"""
    try:
        # Verify project exists and user has access
        project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Get template usage history for this project
        history = db.query(TemplateUsageModel).filter(
            TemplateUsageModel.project_id == project_id
        ).order_by(TemplateUsageModel.used_at.desc()).all()

        # Format the response
        generation_history = []
        for usage in history:
            generation_history.append({
                "id": str(usage.id),
                "template_name": usage.template_name,
                "template_type": usage.template_type,
                "output_type": usage.output_type,
                "generation_status": usage.generation_status,
                "generated_at": usage.used_at.isoformat(),
                "generated_by": str(usage.used_by),
                "file_path": getattr(usage, 'file_path', None)
            })

        return generation_history

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting generation history for project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting generation history: {str(e)}")

@app.get("/projects/{project_id}/generation-requests")
async def get_generation_requests(project_id: str, db: Session = Depends(get_db)):
    """Get generation requests for a project"""
    try:
        # Verify project exists
        project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Query generation requests for this project
        from database import GenerationRequestModel
        requests = db.query(GenerationRequestModel).filter(
            GenerationRequestModel.project_id == project_id
        ).order_by(GenerationRequestModel.requested_at.desc()).all()

        # Convert to response format
        result = []
        for req in requests:
            result.append({
                "id": req.id,
                "template_id": req.template_id,
                "template_name": req.template_name,
                "requested_by": req.requested_by,
                "requested_at": req.requested_at.isoformat(),
                "status": req.status,
                "progress": req.progress,
                "download_url": req.download_url,
                "error_message": req.error_message,
                "markdown_filename": req.markdown_filename,
                "pdf_filename": req.pdf_filename,
                "docx_filename": req.docx_filename,
                "content": req.content[:500] + "..." if req.content and len(req.content) > 500 else req.content,
                "file_path": req.file_path
            })

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting generation requests for project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting generation requests: {str(e)}")

@app.post("/projects/{project_id}/generation-requests")
async def create_generation_request(project_id: str, request_data: dict, db: Session = Depends(get_db)):
    """Create a new generation request"""
    try:
        # Verify project exists
        project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        from database import GenerationRequestModel

        # Create new generation request
        new_request = GenerationRequestModel(
            id=request_data.get("id"),
            template_id=request_data.get("template_id"),
            template_name=request_data.get("template_name"),
            project_id=project_id,
            requested_by=request_data.get("requested_by"),
            status=request_data.get("status", "pending"),
            progress=request_data.get("progress", 0)
        )

        db.add(new_request)
        db.commit()
        db.refresh(new_request)

        return {"success": True, "request_id": new_request.id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating generation request: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating generation request: {str(e)}")

@app.put("/projects/{project_id}/generation-requests/{request_id}")
async def update_generation_request(project_id: str, request_id: str, update_data: dict, db: Session = Depends(get_db)):
    """Update a generation request"""
    try:
        from database import GenerationRequestModel

        # Find the request
        request = db.query(GenerationRequestModel).filter(
            GenerationRequestModel.id == request_id,
            GenerationRequestModel.project_id == project_id
        ).first()

        if not request:
            raise HTTPException(status_code=404, detail="Generation request not found")

        # Update fields
        for field, value in update_data.items():
            if hasattr(request, field):
                setattr(request, field, value)

        db.commit()
        db.refresh(request)

        return {"success": True, "request_id": request.id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating generation request: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating generation request: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
