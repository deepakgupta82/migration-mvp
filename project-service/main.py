from fastapi import FastAPI, HTTPException, status, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
import uuid
import contextvars
from datetime import datetime, timedelta
import json
import os
import logging
from sqlalchemy import text
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError, OperationalError
from cachetools import TTLCache
import threading
from config_client import cfg_get


# Correlation ID context
correlation_id_ctx = contextvars.ContextVar("correlation_id", default=None)

# Logging filter to inject correlation ID
class CorrelationIdLogFilter(logging.Filter):
    def filter(self, record):
        try:
            record.correlation_id = correlation_id_ctx.get()
        except Exception:
            record.correlation_id = "-"
        if not record.correlation_id:
            record.correlation_id = "-"
        return True

os.makedirs('logs', exist_ok=True)
class SafeFormatter(logging.Formatter):
    def format(self, record):
        if not hasattr(record, "correlation_id"):
            record.correlation_id = "-"
        return super().format(record)

class JSONFormatter(logging.Formatter):
    def format(self, record):
        if not hasattr(record, "correlation_id"):
            record.correlation_id = "-"
        if not hasattr(record, "project_id"):
            record.project_id = "-"
        
        log_data = {
            "ts": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "service": "project-service",
            "corr_id": record.correlation_id,
            "project_id": getattr(record, 'project_id', '-') or '-',
            "msg": record.getMessage()
        }
        
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_data)

log_format = '%(asctime)s - %(name)s - %(levelname)s - [corr_id=%(correlation_id)s] - %(message)s'
# Configure logging with JSON format for files, text for console
json_formatter = JSONFormatter()
text_formatter = SafeFormatter(log_format)
correlation_filter = CorrelationIdLogFilter()

# Create file handler with JSON format
file_handler = logging.FileHandler('logs/project-service.log')
file_handler.setFormatter(json_formatter)
file_handler.addFilter(correlation_filter)

# Create console handler with text format
console_handler = logging.StreamHandler()
console_handler.setFormatter(text_formatter)
console_handler.addFilter(correlation_filter)

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
# Clear existing handlers
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)
# Add our configured handlers
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

logger = logging.getLogger(__name__)
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import (
    get_db, create_tables, ProjectModel, ProjectFileModel,
    UserModel, PlatformSettingModel, DeliverableTemplateModel, LLMConfigurationModel, ModelCacheModel, TemplateUsageModel,
    ProjectUserRoleModel, engine  # NEW enhanced role model + engine for pool monitoring
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
    LLMConfigurationResponse, LLMConfigurationUpdate,
    EnhancedUserResponse, ProjectRoleAssignment, ProjectUserRoleResponse,  # NEW enhanced schemas
    ProcessLLMConfigRequest, ProcessLLMConfigResponse, ProcessLLMTestRequest
)


app = FastAPI(title="Nagarro's Ascent Project Service", description="Microservice for managing migration assessment projects")

# In-memory caches for stats and project list
stats_cache = TTLCache(maxsize=10, ttl=10)
projects_cache = TTLCache(maxsize=50, ttl=10)
cache_lock = threading.Lock()

def invalidate_project_stats_cache():
    with cache_lock:
        stats_cache.clear()
        projects_cache.clear()

# Database error handling middleware
@app.middleware("http")
async def database_error_middleware(request: Request, call_next):
    """Middleware to handle database connection errors gracefully"""
    try:
        response = await call_next(request)
        return response
    except (SQLAlchemyTimeoutError, OperationalError) as e:
        logger.error(f"Database connection error on {request.url}: {str(e)}")
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Database connection error. Please try again later.",
                "error_type": "database_timeout",
                "timestamp": datetime.utcnow().isoformat(),
                "correlation_id": getattr(request.state, 'correlation_id', None)
            }
        )
    except Exception as e:
        # Let other exceptions be handled by default error handlers
        raise e

# Correlation ID middleware
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    corr_id = request.headers.get("X-Correlation-ID")
    if not corr_id:
        corr_id = str(uuid.uuid4())
    # Set in contextvar and request.state
    token = correlation_id_ctx.set(corr_id)
    request.state.correlation_id = corr_id
    try:
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = corr_id
        return response
    finally:
        correlation_id_ctx.reset(token)

# Add CORS middleware (origins from centralized config; default to '*' for compatibility)
cors_origins = cfg_get(["backend", "cors_origins"], ["*"]) or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
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

# Ensure new additive columns exist for backward compatibility (idempotent)
def ensure_additive_columns():
    try:
        db = next(get_db())
        # Add columns project_overview, project_intent if not present
        try:
            db.execute(text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='projects' AND column_name='project_overview'
                    ) THEN
                        ALTER TABLE projects ADD COLUMN project_overview TEXT;
                    END IF;
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='projects' AND column_name='project_intent'
                    ) THEN
                        ALTER TABLE projects ADD COLUMN project_intent TEXT;
                    END IF;
                    -- Extended project context fields
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='projects' AND column_name='client_summary'
                    ) THEN
                        ALTER TABLE projects ADD COLUMN client_summary TEXT;
                    END IF;
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='projects' AND column_name='rfp_summary'
                    ) THEN
                        ALTER TABLE projects ADD COLUMN rfp_summary TEXT;
                    END IF;
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='projects' AND column_name='rfp_responses'
                    ) THEN
                        ALTER TABLE projects ADD COLUMN rfp_responses TEXT;
                    END IF;
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='projects' AND column_name='expectations'
                    ) THEN
                        ALTER TABLE projects ADD COLUMN expectations TEXT;
                    END IF;
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='projects' AND column_name='deliverables_summary'
                    ) THEN
                        ALTER TABLE projects ADD COLUMN deliverables_summary TEXT;
                    END IF;
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='projects' AND column_name='timeline_notes'
                    ) THEN
                        ALTER TABLE projects ADD COLUMN timeline_notes TEXT;
                    END IF;
                END$$;
            """))
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
    except Exception as e:
        print(f"Warning: Could not ensure additive columns: {e}")

try:
    ensure_additive_columns()
except Exception as e:
    print(f"Warning during additive column ensure: {e}")

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
    """Health check endpoint with enhanced database monitoring"""
    db = None
    try:
        # Test database connection with timeout handling
        db = next(get_db())
        db.execute(text("SELECT 1"))
        
        # Get connection pool status
        pool = engine.pool
        pool_status = {
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "total_capacity": pool.size() + pool._max_overflow
        }

        return {
            "status": "healthy",
            "database": "connected",
            "pool_status": pool_status,
            "timestamp": datetime.utcnow().isoformat(),
            "service": "project-service"
        }
    except (SQLAlchemyTimeoutError, OperationalError) as e:
        logger.error(f"Database connection failed in health check: {str(e)}")
        raise HTTPException(
            status_code=503, 
            detail={
                "status": "unhealthy",
                "database": "disconnected",
                "error": "Database connection timeout or operational error",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    except Exception as e:
        logger.error(f"Unexpected error in health check: {str(e)}")
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")
    finally:
        if db:
            db.close()

@app.get("/db/status")
async def database_status(current_user: UserModel = Depends(get_current_user)):
    """Detailed database status endpoint for monitoring"""
    db = None
    try:
        db = next(get_db())
        
        # Get connection pool information
        pool = engine.pool
        pool_status = {
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "total_capacity": pool.size() + pool._max_overflow
        }
        
        # Test basic query
        result = db.execute(text("SELECT version()"))
        version = result.fetchone()[0]
        
        # Get active connections count
        active_connections_result = db.execute(text("""
            SELECT count(*) as active_connections,
                   count(CASE WHEN state = 'active' THEN 1 END) as running_queries,
                   count(CASE WHEN state = 'idle' THEN 1 END) as idle_connections
            FROM pg_stat_activity 
            WHERE datname = current_database()
        """))
        active_conn_data = active_connections_result.fetchone()
        
        return {
            "status": "connected",
            "database": {
                "version": version,
                "active_connections": active_conn_data.active_connections,
                "running_queries": active_conn_data.running_queries,
                "idle_connections": active_conn_data.idle_connections,
                "pool_status": pool_status,
                "pool_utilization": f"{pool_status['checked_out']}/{pool_status['total_capacity']} ({round(pool_status['checked_out']/pool_status['total_capacity']*100, 1)}%)"
            },
            "timestamp": datetime.utcnow().isoformat(),
            "service": "project-service"
        }
    except (SQLAlchemyTimeoutError, OperationalError) as e:
        logger.error(f"Database status check failed: {str(e)}")
        raise HTTPException(
            status_code=503, 
            detail={
                "status": "error",
                "error": "Database connection timeout or operational error",
                "error_details": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    except Exception as e:
        logger.error(f"Database status check failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database status check failed: {str(e)}")
    finally:
        if db:
            db.close()

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
@app.get("/db/version")
async def db_version(db: Session = Depends(get_db)):
    try:
        from sqlalchemy import text
        row = db.execute(text("SELECT version()"))
        version = None
        for r in row:
            version = r[0]
            break
        return {"version": version}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get DB version: {str(e)}")


@app.get("/users/me", response_model=UserResponse)
async def read_users_me(current_user: UserModel = Depends(get_current_user)):
    """Get current user information."""
    return current_user

@app.get("/users", response_model=List[UserResponse])
async def list_users(current_user: UserModel = Depends(get_current_admin), db: Session = Depends(get_db)):
    """List all users (admin only) - EXISTING ENDPOINT UNCHANGED."""
    users = db.query(UserModel).all()
    return users

# NEW enhanced user endpoints (ADDITIVE)
@app.get("/users/enhanced", response_model=List[EnhancedUserResponse])
async def list_users_enhanced(
    page: int = 1,
    limit: int = 50,
    search: Optional[str] = None,
    current_user: UserModel = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """List users with enhanced information and pagination (NEW ENDPOINT)"""
    from sqlalchemy import or_

    query = db.query(UserModel)

    if search:
        query = query.filter(
            or_(
                UserModel.email.ilike(f"%{search}%"),
                UserModel.username.ilike(f"%{search}%"),
                UserModel.first_name.ilike(f"%{search}%"),
                UserModel.last_name.ilike(f"%{search}%")
            )
        )

    # Apply pagination
    offset = (page - 1) * limit
    users = query.offset(offset).limit(limit).all()

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
        llm_max_tokens=project.llm_max_tokens,
        # Ensure extended project context is persisted on create
        rfp_summary=getattr(project, "rfp_summary", None),
        timeline_notes=getattr(project, "timeline_notes", None)
    )

    # Associate the project with the current user
    db_project.users.append(current_user)

    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    invalidate_project_stats_cache()

    return db_project

# Dashboard Stats - Must be before {project_id} route
@app.get("/projects/stats", response_model=ProjectStats)
async def get_project_stats(
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get dashboard statistics (cached)"""
    cache_key = f"{current_user.id}:{current_user.role}"
    with cache_lock:
        cached_stats = stats_cache.get(cache_key)
    if cached_stats:
        return cached_stats

    if current_user.role == "platform_admin":
        total_projects = db.query(ProjectModel).count()
        active_projects = db.query(ProjectModel).filter(ProjectModel.status.in_(["initiated", "running"])).count()
        completed_assessments = db.query(ProjectModel).filter(ProjectModel.status == "completed").count()
    else:
        user_projects = db.query(ProjectModel).join(ProjectModel.users).filter(UserModel.id == current_user.id)
        total_projects = user_projects.count()
        active_projects = user_projects.filter(ProjectModel.status.in_(["initiated", "running"])).count()
        completed_assessments = user_projects.filter(ProjectModel.status == "completed").count()

    average_risk_score = None

    stats = ProjectStats(
        total_projects=total_projects,
        active_projects=active_projects,
        completed_assessments=completed_assessments,
        average_risk_score=average_risk_score
    )
    with cache_lock:
        stats_cache[cache_key] = stats
    return stats

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
    """List projects accessible to the current user (cached, latest first)"""
    cache_key = f"{current_user.id}:{current_user.role}"
    with cache_lock:
        cached_projects = projects_cache.get(cache_key)
    if cached_projects:
        return cached_projects

    if current_user.role == "platform_admin":
        db_projects = db.query(ProjectModel).order_by(ProjectModel.created_at.desc()).all()
    else:
        db_projects = db.query(ProjectModel).join(ProjectModel.users).filter(UserModel.id == current_user.id).order_by(ProjectModel.created_at.desc()).all()

    with cache_lock:
        projects_cache[cache_key] = db_projects
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

    # Includes new fields like project_overview, project_intent if present
    update_data = project_update.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        if value is not None:
            # FIX: Properly validate and convert LLM configuration values
            if key in ['llm_temperature', 'llm_max_tokens']:
                try:
                    # Ensure values are stored as strings but validate they're convertible
                    if key == 'llm_temperature':
                        float(value)  # Validate it's a valid float
                    elif key == 'llm_max_tokens':
                        int(value)    # Validate it's a valid int
                    # Store as string (as per database schema)
                    setattr(db_project, key, str(value))
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid {key} value '{value}': {e}. Using existing value.")
                    continue
            else:
                setattr(db_project, key, value)

    db_project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_project)
    invalidate_project_stats_cache()

    return db_project

# =====================================================================================
# Per-Process LLM Config Endpoints (Project-owned)
# =====================================================================================

@app.get("/projects/{project_id}/llm-process-configs", response_model=ProcessLLMConfigResponse)
async def get_project_llm_process_configs(
    project_id: str,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if current_user.role != "platform_admin" and current_user not in project.users:
        raise HTTPException(status_code=403, detail="Access denied")

    def _parse_json(value):
        if not value:
            return None
        try:
            return json.loads(value) if isinstance(value, str) else value
        except Exception:
            return None

    # Individual columns
    configs = {
        "entity_extraction": _parse_json(getattr(project, "entity_extraction_llm_config", None)),
        "crew_assessment": _parse_json(getattr(project, "crew_assessment_llm_config", None)),
        "crew_documentation": _parse_json(getattr(project, "crew_documentation_llm_config", None)),
        "rag_synthesis": _parse_json(getattr(project, "rag_synthesis_llm_config", None)),
        "hybrid_search": _parse_json(getattr(project, "hybrid_search_llm_config", None)) if hasattr(project, "hybrid_search_llm_config") else None,
    }

    # Merge nested JSON overrides
    nested = _parse_json(getattr(project, "llm_process_configs", None)) or {}
    configs.update({k: v for k, v in nested.items() if v is not None})

    return ProcessLLMConfigResponse(
        project_id=project_id,
        entity_extraction=configs.get("entity_extraction"),
        crew_assessment=configs.get("crew_assessment"),
        crew_documentation=configs.get("crew_documentation"),
        rag_synthesis=configs.get("rag_synthesis"),
        hybrid_search=configs.get("hybrid_search"),
    )


@app.post("/projects/{project_id}/llm-process-configs")
async def update_project_llm_process_configs(
    project_id: str,
    config_request: ProcessLLMConfigRequest,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if current_user.role != "platform_admin" and current_user not in project.users:
        raise HTTPException(status_code=403, detail="Access denied")

    def _dump(val):
        return json.dumps(val) if val is not None else None

    # Update individual columns if present
    if config_request.entity_extraction is not None:
        project.entity_extraction_llm_config = _dump(config_request.entity_extraction.model_dump())
    if config_request.crew_assessment is not None:
        project.crew_assessment_llm_config = _dump(config_request.crew_assessment.model_dump())
    if config_request.crew_documentation is not None:
        project.crew_documentation_llm_config = _dump(config_request.crew_documentation.model_dump())
    if config_request.rag_synthesis is not None:
        project.rag_synthesis_llm_config = _dump(config_request.rag_synthesis.model_dump())
    if config_request.hybrid_search is not None and hasattr(project, "hybrid_search_llm_config"):
        project.hybrid_search_llm_config = _dump(config_request.hybrid_search.model_dump())

    # Also store combined nested JSON for flexible access
    nested = {}
    for key in [
        ("entity_extraction", config_request.entity_extraction),
        ("crew_assessment", config_request.crew_assessment),
        ("crew_documentation", config_request.crew_documentation),
        ("rag_synthesis", config_request.rag_synthesis),
        ("hybrid_search", config_request.hybrid_search),
    ]:
        name, val = key
        if val is not None:
            nested[name] = val.model_dump()
    if nested:
        project.llm_process_configs = json.dumps(nested)

    project.updated_at = datetime.utcnow()
    db.commit()
    return {"status": "success", "message": "Process LLM configurations updated"}


@app.post("/projects/{project_id}/process-llm-config/{process_key}/test")
async def test_project_llm_process_config(
    project_id: str,
    process_key: str,
    request: ProcessLLMTestRequest,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if current_user.role != "platform_admin" and current_user not in project.users:
        raise HTTPException(status_code=403, detail="Access denied")

    # Build a minimal echo-style response for now; deeper provider validation can be added later
    selected = None
    if request.provider and request.model:
        selected = {
            "provider": request.provider,
            "model": request.model,
            "temperature": request.temperature or 0.1,
        }
    else:
        # Try to pick from nested configs
        try:
            nested = json.loads(project.llm_process_configs) if project.llm_process_configs else {}
            selected = nested.get(process_key)
        except Exception:
            selected = None

    if not selected and getattr(project, f"{process_key}_llm_config", None):
        try:
            val = getattr(project, f"{process_key}_llm_config")
            selected = json.loads(val) if isinstance(val, str) else val
        except Exception:
            selected = None

    if not selected and request.use_project_default:
        # Fall back to project's default fields
        selected = {
            "provider": project.llm_provider,
            "model": project.llm_model,
            "temperature": float(project.llm_temperature) if project.llm_temperature else 0.1,
            "api_key_id": project.llm_api_key_id,
        }

    # Simulate a test call result
    if not selected or not selected.get("provider") or not selected.get("model"):
        return {"success": False, "status": "error", "error": "Missing provider/model to test"}

    return {
        "success": True,
        "status": "ok",
        "provider": selected.get("provider"),
        "model": selected.get("model"),
        "message": "Test request accepted",
        "echo": request.query or "OK",
    }

@app.delete("/projects/{project_id}")
async def delete_project(
    project_id: str,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a project and all associated data"""
    db_project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check if user has access to this project
    if current_user.role != "platform_admin" and current_user not in db_project.users:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        # Use an explicit transactional block to ensure atomicity and avoid aborted transaction state
        with db.begin():
            # 1. Delete project files
            db.query(ProjectFileModel).filter(ProjectFileModel.project_id == project_id).delete(synchronize_session=False)

            # 2. Delete template usage records (optional table)
            try:
                db.execute(text("DELETE FROM template_usage WHERE project_id = :project_id"), {"project_id": project_id})
            except Exception:
                # Table might not exist in some deployments
                pass

            # 3. Delete generation requests (optional table)
            try:
                db.execute(text("DELETE FROM generation_requests WHERE project_id = :project_id"), {"project_id": project_id})
            except Exception:
                pass

            # 4. Delete project templates (optional table)
            try:
                db.execute(text("DELETE FROM project_templates WHERE project_id = :project_id"), {"project_id": project_id})
            except Exception:
                pass

            # 5. Delete project-user associations (legacy join table)
            try:
                db.execute(text("DELETE FROM project_user_association WHERE project_id = :project_id"), {"project_id": project_id})
            except Exception:
                pass

            # 6. Finally delete the project itself
            db.delete(db_project)

        # If we reach here, transaction committed successfully
        invalidate_project_stats_cache()
        return {"message": "Project and all associated data deleted successfully"}

    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Failed to delete project: {str(e)}")

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

@app.get("/projects/{project_id}/files/count")
async def get_project_files_count(
    project_id: str,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a lightweight count of files for a project"""
    # Verify project exists and user has access
    db_project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    if current_user.role != "platform_admin" and current_user not in db_project.users:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        count = db.query(ProjectFileModel).filter(ProjectFileModel.project_id == project_id).count()
        return {"count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get file count: {str(e)}")

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

    templates = db.query(DeliverableTemplateModel).filter(
        DeliverableTemplateModel.project_id == project_id,
        DeliverableTemplateModel.template_type == "project"
    ).all()
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

# =====================================================================================
# Global Document Template Endpoints
# =====================================================================================

@app.get("/templates/global", response_model=List[DeliverableTemplateResponse])
async def list_global_templates(
    db: Session = Depends(get_db)
):
    """Get all global document templates available to all projects"""
    try:
        print("DEBUG: Starting global templates query...")
        templates = db.query(DeliverableTemplateModel).filter(
            DeliverableTemplateModel.template_type == "global",
            DeliverableTemplateModel.is_active == True
        ).all()
        print(f"DEBUG: Found {len(templates)} templates")
        return templates
    except Exception as e:
        print(f"DEBUG: Error in global templates: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error fetching global templates: {str(e)}")

@app.post("/templates/global", response_model=DeliverableTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_global_template(
    template: DeliverableTemplateCreate,
    db: Session = Depends(get_db)
):
    """Create a new global document template"""
    try:
        # Create global template (project_id = None)
        db_template = DeliverableTemplateModel(
            name=template.name,
            description=template.description,
            prompt=template.prompt,
            project_id=None,  # Global template
            template_type="global",
            category=getattr(template, 'category', 'migration'),
            output_format=getattr(template, 'output_format', 'pdf'),
            created_by=None,  # No user required for global templates
            template_content=getattr(template, 'template_content', ''),
        )
        db.add(db_template)
        db.commit()
        db.refresh(db_template)
        return db_template
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating global template: {str(e)}")

@app.delete("/templates/global/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_global_template(
    template_id: str,
    db: Session = Depends(get_db)
):
    """Delete a global document template"""
    try:
        # Find the template
        db_template = db.query(DeliverableTemplateModel).filter(
            DeliverableTemplateModel.id == template_id,
            DeliverableTemplateModel.template_type == "global"
        ).first()

        if not db_template:
            raise HTTPException(status_code=404, detail="Global template not found")

        # Delete the template
        db.delete(db_template)
        db.commit()

        return None  # 204 No Content

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting global template: {str(e)}")

@app.get("/templates/all/{project_id}")
async def get_all_available_templates(
    project_id: str,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get both global and project-specific templates for a project"""
    # Verify project exists and user has access
    db_project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    if current_user.role != "platform_admin" and current_user not in db_project.users:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        # Get global templates
        global_templates = db.query(DeliverableTemplateModel).filter(
            DeliverableTemplateModel.template_type == "global",
            DeliverableTemplateModel.is_active == True
        ).all()

        # Get project-specific templates
        project_templates = db.query(DeliverableTemplateModel).filter(
            DeliverableTemplateModel.project_id == project_id,
            DeliverableTemplateModel.template_type == "project"
        ).all()

        return {
            "global_templates": global_templates,
            "project_templates": project_templates,
            "total_count": len(global_templates) + len(project_templates)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching templates: {str(e)}")

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
    # Validate required fields
    if not config.api_key or config.api_key.strip() == '':
        raise HTTPException(status_code=400, detail="API key is required and cannot be empty")
    
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

    # Validate API key if it's being updated
    update_data = config_update.model_dump(exclude_unset=True)
    if 'api_key' in update_data and (not update_data['api_key'] or update_data['api_key'].strip() == ''):
        raise HTTPException(status_code=400, detail="API key cannot be empty")

    # Update fields - only update fields that are explicitly provided and not None
    for field, value in update_data.items():
        if value is not None:  # Only update if value is not None
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

# NEW project role management endpoints (ADDITIVE)
@app.post("/projects/{project_id}/users/{user_id}/assign-role")
async def assign_project_role(
    project_id: str,
    user_id: str,
    role_data: ProjectRoleAssignment,
    current_user: UserModel = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Assign a role to a user for a specific project (NEW ENDPOINT)"""
    from uuid import UUID

    try:
        project_uuid = UUID(project_id)
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")

    # Verify project exists
    project = db.query(ProjectModel).filter(ProjectModel.id == project_uuid).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Verify user exists
    user = db.query(UserModel).filter(UserModel.id == user_uuid).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if role assignment already exists
    existing_role = db.query(ProjectUserRoleModel).filter(
        ProjectUserRoleModel.user_id == user_uuid,
        ProjectUserRoleModel.project_id == project_uuid
    ).first()

    if existing_role:
        # Update existing role
        existing_role.role = role_data.role
        existing_role.assigned_by = current_user.id
        existing_role.updated_at = datetime.utcnow()
    else:
        # Create new role assignment
        new_role = ProjectUserRoleModel(
            user_id=user_uuid,
            project_id=project_uuid,
            role=role_data.role,
            assigned_by=current_user.id
        )
        db.add(new_role)

        # ALSO add to old association table for backward compatibility
        from sqlalchemy import text
        db.execute(text("""
            INSERT INTO project_user_association (user_id, project_id)
            VALUES (:user_id, :project_id)
            ON CONFLICT (user_id, project_id) DO NOTHING
        """), {"user_id": user_uuid, "project_id": project_uuid})

    db.commit()
    return {"status": "success", "message": "Role assigned successfully"}

@app.get("/projects/{project_id}/users")
async def list_project_users(
    project_id: str,
    current_user: UserModel = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """List all users assigned to a project with their roles (NEW ENDPOINT)"""
    from uuid import UUID

    try:
        project_uuid = UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project ID format")

    # Verify project exists
    project = db.query(ProjectModel).filter(ProjectModel.id == project_uuid).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get users with enhanced roles
    from sqlalchemy import text
    result = db.execute(text("""
        SELECT DISTINCT
            u.id, u.email, u.username, u.first_name, u.last_name, u.role as platform_role,
            COALESCE(pur.role, 'project_user') as project_role,
            COALESCE(pur.assigned_at, p.created_at) as assigned_at,
            pur.assigned_by
        FROM users u
        LEFT JOIN project_user_roles pur ON u.id = pur.user_id AND pur.project_id = :project_id
        LEFT JOIN project_user_association pua ON u.id = pua.user_id AND pua.project_id = :project_id
        JOIN projects p ON p.id = :project_id
        WHERE (pur.user_id IS NOT NULL OR pua.user_id IS NOT NULL OR u.role = 'platform_admin')
        AND u.is_active = true
        ORDER BY u.email
    """), {"project_id": project_uuid})

    users = []
    for row in result:
        users.append({
            "id": str(row.id),
            "email": row.email,
            "username": row.username,
            "first_name": row.first_name,
            "last_name": row.last_name,
            "platform_role": row.platform_role,
            "project_role": row.project_role,
            "assigned_at": row.assigned_at.isoformat() if row.assigned_at else None,
            "assigned_by": str(row.assigned_by) if row.assigned_by else None
        })

    return users

@app.delete("/projects/{project_id}/users/{user_id}")
async def remove_user_from_project(
    project_id: str,
    user_id: str,
    current_user: UserModel = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Remove a user from a project (NEW ENDPOINT)"""
    from uuid import UUID

    try:
        project_uuid = UUID(project_id)
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")

    # Remove from enhanced role table
    role_assignment = db.query(ProjectUserRoleModel).filter(
        ProjectUserRoleModel.user_id == user_uuid,
        ProjectUserRoleModel.project_id == project_uuid
    ).first()

    if role_assignment:
        db.delete(role_assignment)

    # Remove from old association table for backward compatibility
    from sqlalchemy import text
    db.execute(text("""
        DELETE FROM project_user_association
        WHERE user_id = :user_id AND project_id = :project_id
    """), {"user_id": user_uuid, "project_id": project_uuid})

    db.commit()
    return {"status": "success", "message": "User removed from project"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
