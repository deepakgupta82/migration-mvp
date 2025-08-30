from sqlalchemy import create_engine, Column, String, DateTime, Text, ForeignKey, Table, Boolean, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
import os
import time
import logging
from sqlalchemy.exc import OperationalError, TimeoutError as SQLAlchemyTimeoutError

logger = logging.getLogger(__name__)

# Database configuration
# Connect to PostgreSQL running in Docker (mapped to localhost:5432)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://projectuser:projectpass@localhost:5432/projectdb")

# Configure engine with proper connection pooling settings
engine = create_engine(
    DATABASE_URL,
    pool_size=20,          # Number of connections to keep in pool (increased from default 5)
    max_overflow=30,       # Maximum overflow connections (increased from default 10)
    pool_timeout=60,       # Timeout for getting connection from pool (increased from 30s)
    pool_recycle=3600,     # Recycle connections after 1 hour to prevent stale connections
    pool_pre_ping=True,    # Verify connections before use
    echo=False             # Set to True for debugging SQL queries
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Association table for many-to-many relationship between users and projects
project_user_association = Table(
    'project_user_association',
    Base.metadata,
    Column('user_id', UUID(as_uuid=True), ForeignKey('users.id'), primary_key=True),
    Column('project_id', UUID(as_uuid=True), ForeignKey('projects.id', ondelete="CASCADE"), primary_key=True)
)

class UserModel(Base):
    __tablename__ = "users"

    # Existing fields (UNCHANGED for backward compatibility)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="user")  # 'user' or 'platform_admin'
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # NEW enhanced fields (ADDITIVE - nullable for existing users)
    username = Column(String(100), unique=True, nullable=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    last_login = Column(DateTime, nullable=True)
    failed_login_attempts = Column(Integer, default=0)
    account_locked_until = Column(DateTime, nullable=True)

    # KEEP existing relationships (UNCHANGED)
    projects = relationship("ProjectModel", secondary=project_user_association, back_populates="users")

class ProjectModel(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    client_name = Column(String(255), nullable=False)
    client_contact = Column(String(255), nullable=True)
    status = Column(String(50), nullable=False, default="initiated")
    report_url = Column(String(500), nullable=True)  # URL to generated PDF/DOCX report
    report_content = Column(Text, nullable=True)  # Raw Markdown report content
    report_artifact_url = Column(String(500), nullable=True)  # URL to final report artifacts
    # Project context fields
    project_overview = Column(Text, nullable=True)
    project_intent = Column(Text, nullable=True)
    # Extended project context fields (all optional)
    client_summary = Column(Text, nullable=True)
    rfp_summary = Column(Text, nullable=True)
    rfp_responses = Column(Text, nullable=True)
    expectations = Column(Text, nullable=True)
    deliverables_summary = Column(Text, nullable=True)
    timeline_notes = Column(Text, nullable=True)

    # LLM Configuration fields
    llm_provider = Column(String(50), nullable=True)  # openai, anthropic, gemini, ollama, custom
    llm_model = Column(String(100), nullable=True)  # gpt-4o, claude-3-5-sonnet, gemini-2.0-flash-exp, etc.
    llm_api_key_id = Column(String(255), nullable=True)  # Reference to stored API key
    llm_temperature = Column(String(10), nullable=True, default="0.1")  # Temperature setting
    llm_max_tokens = Column(String(10), nullable=True, default="4000")  # Max tokens setting

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to project files
    files = relationship("ProjectFileModel", back_populates="project", cascade="all, delete-orphan")

    # Many-to-many relationship with users
    users = relationship("UserModel", secondary=project_user_association, back_populates="projects")

# NEW model for enhanced project role management (ADDITIVE)
class ProjectUserRoleModel(Base):
    __tablename__ = "project_user_roles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(50), nullable=False, default="project_user")  # 'project_admin', 'project_user'
    assigned_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    assigned_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("UserModel", foreign_keys=[user_id])
    project = relationship("ProjectModel", foreign_keys=[project_id])
    assigner = relationship("UserModel", foreign_keys=[assigned_by])

class ProjectFileModel(Base):
    __tablename__ = "project_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(100), nullable=True)
    file_size = Column(Integer, nullable=True)  # File size in bytes
    upload_timestamp = Column(DateTime, default=datetime.utcnow)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)

    # Relationship back to project
    project = relationship("ProjectModel", back_populates="files")

class PlatformSettingModel(Base):
    __tablename__ = "platform_settings"

    key = Column(String(255), primary_key=True, unique=True)
    value = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    last_updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to user who last updated
    updated_by_user = relationship("UserModel")

class DeliverableTemplateModel(Base):
    __tablename__ = "deliverable_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    prompt = Column(Text, nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True)  # Nullable for global templates
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # New fields for proper template management
    template_type = Column(String(20), nullable=False, default="project")  # "global" or "project"
    category = Column(String(50), nullable=True)  # "migration", "assessment", "architecture", etc.
    output_format = Column(String(20), nullable=False, default="pdf")  # "pdf", "docx", "xlsx", etc.
    is_active = Column(Boolean, default=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    template_content = Column(Text, nullable=True)  # Detailed template structure
    usage_count = Column(Integer, default=0)
    last_used = Column(DateTime, nullable=True)

    # Relationship to project (optional for global templates)
    project = relationship("ProjectModel")
    creator = relationship("UserModel", foreign_keys=[created_by])

class LLMConfigurationModel(Base):
    __tablename__ = "llm_configurations"

    id = Column(String(255), primary_key=True)  # Custom ID like "gemini1_1754014595"
    name = Column(String(255), nullable=False)  # User-friendly name like "My Gemini Config"
    provider = Column(String(50), nullable=False)  # openai, gemini, anthropic, etc.
    model = Column(String(100), nullable=False)  # gpt-4o, gemini-1.5-pro, etc.
    api_key = Column(Text, nullable=False)  # Encrypted API key
    temperature = Column(String(10), nullable=False, default="0.1")
    max_tokens = Column(String(10), nullable=False, default="4000")
    description = Column(Text, nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to user who created it
    creator = relationship("UserModel")


class ModelCacheModel(Base):
    """Model cache for storing LLM provider models"""
    __tablename__ = "model_cache"

    id = Column(String(255), primary_key=True)  # provider_model_id format
    provider = Column(String(50), nullable=False)  # openai, gemini, anthropic, etc.
    model_id = Column(String(200), nullable=False)  # actual model identifier
    model_name = Column(String(200), nullable=False)  # display name
    description = Column(Text, nullable=True)  # model description
    is_active = Column(Boolean, default=True)  # whether model is currently available
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

class TemplateUsageModel(Base):
    __tablename__ = "template_usage"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_name = Column(String(255), nullable=False)  # Template name
    template_type = Column(String(50), nullable=False)  # 'global' or 'project'
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    used_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    used_at = Column(DateTime, default=datetime.utcnow)
    output_type = Column(String(20), nullable=True)  # pdf, docx, etc.
    generation_status = Column(String(20), nullable=False, default="completed")  # completed, failed

    # Relationships
    project = relationship("ProjectModel")
    user = relationship("UserModel")

class GenerationRequestModel(Base):
    __tablename__ = "generation_requests"

    id = Column(String(255), primary_key=True)  # Custom ID like "req-1234567890"
    template_id = Column(String(255), nullable=False)
    template_name = Column(String(255), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    requested_by = Column(String(255), nullable=False)
    requested_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), nullable=False, default="pending")  # pending, generating, completed, failed
    progress = Column(Integer, default=0)
    download_url = Column(String(500), nullable=True)
    error_message = Column(Text, nullable=True)

    # Generated file information
    markdown_filename = Column(String(255), nullable=True)
    pdf_filename = Column(String(255), nullable=True)
    docx_filename = Column(String(255), nullable=True)
    content = Column(Text, nullable=True)
    file_path = Column(String(500), nullable=True)

    # Relationships
    project = relationship("ProjectModel")

# Create tables
def create_tables():
    Base.metadata.create_all(bind=engine)

# Enhanced database connection with retry logic
def get_db_with_retry(max_retries=3, base_delay=0.5):
    """Get database session with exponential backoff retry logic"""
    last_exception = None

    for attempt in range(max_retries):
        try:
            db = SessionLocal()
            # Test the connection
            db.execute("SELECT 1")
            return db
        except (OperationalError, SQLAlchemyTimeoutError) as e:
            last_exception = e
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)  # Exponential backoff
                logger.warning(f"Database connection attempt {attempt + 1} failed: {str(e)}. Retrying in {delay}s...")
                time.sleep(delay)
            else:
                logger.error(f"Database connection failed after {max_retries} attempts: {str(e)}")
                raise e
        except Exception as e:
            logger.error(f"Unexpected database error: {str(e)}")
            raise e

# Dependency to get database session with proper error handling
def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

# Enhanced database dependency with retry logic
def get_db_with_retry_dependency():
    """Enhanced database dependency with retry logic and connection validation"""
    db = None
    try:
        db = get_db_with_retry()
        yield db
    except Exception:
        if db:
            try:
                db.rollback()
            except Exception:
                pass
        raise
    finally:
        if db:
            try:
                db.close()
            except Exception:
                pass

# Database connection health check
def check_database_health():
    """Check database connection health and return detailed status"""
    try:
        db = get_db_with_retry(max_retries=2, base_delay=0.2)
        try:
            # Test basic connectivity
            result = db.execute("SELECT 1 as test")
            test_result = result.fetchone()

            # Get connection pool status
            pool = engine.pool
            pool_status = {
                "pool_size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
                "total_capacity": pool.size() + pool._max_overflow,
                "pool_utilization_percent": round((pool.checkedout() / (pool.size() + pool._max_overflow)) * 100, 1) if (pool.size() + pool._max_overflow) > 0 else 0
            }

            # Get database version
            version_result = db.execute("SELECT version()")
            version = version_result.fetchone()[0]

            # Get active connection count
            active_conn_result = db.execute("""
                SELECT
                    count(*) as total_connections,
                    count(CASE WHEN state = 'active' THEN 1 END) as active_connections,
                    count(CASE WHEN state = 'idle' THEN 1 END) as idle_connections,
                    count(CASE WHEN state = 'idle in transaction' THEN 1 END) as idle_in_transaction
                FROM pg_stat_activity
                WHERE datname = current_database()
            """)
            conn_stats = active_conn_result.fetchone()

            return {
                "status": "healthy",
                "database": "connected",
                "version": version,
                "pool_status": pool_status,
                "connection_stats": {
                    "total_connections": conn_stats.total_connections,
                    "active_connections": conn_stats.active_connections,
                    "idle_connections": conn_stats.idle_connections,
                    "idle_in_transaction": conn_stats.idle_in_transaction
                },
                "timestamp": datetime.utcnow().isoformat()
            }

        finally:
            db.close()

    except (OperationalError, SQLAlchemyTimeoutError) as e:
        logger.error(f"Database health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e),
            "error_type": "connection_error",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Database health check unexpected error: {str(e)}")
        return {
            "status": "unhealthy",
            "database": "error",
            "error": str(e),
            "error_type": "unexpected_error",
            "timestamp": datetime.utcnow().isoformat()
        }

# UUID validation helper
def validate_uuid(uuid_str: str) -> bool:
    """Validate if a string is a valid UUID format"""
    try:
        uuid.UUID(uuid_str)
        return True
    except (ValueError, TypeError):
        return False

# Enhanced project query with UUID validation
def get_project_by_id_safe(db, project_id: str):
    """Safely get project by ID with UUID validation"""
    if not validate_uuid(project_id):
        logger.warning(f"Invalid UUID format for project_id: {project_id}")
        return None

    try:
        project_uuid = uuid.UUID(project_id)
        return db.query(ProjectModel).filter(ProjectModel.id == project_uuid).first()
    except Exception as e:
        logger.error(f"Error querying project {project_id}: {str(e)}")
        return None
