from sqlalchemy import create_engine, Column, String, DateTime, Text, ForeignKey, Table, Boolean, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
import os

# Database configuration
# Connect to PostgreSQL running in Docker (mapped to localhost:5432)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://projectuser:projectpass@localhost:5432/projectdb")

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Association table for many-to-many relationship between users and projects
project_user_association = Table(
    'project_user_association',
    Base.metadata,
    Column('user_id', UUID(as_uuid=True), ForeignKey('users.id'), primary_key=True),
    Column('project_id', UUID(as_uuid=True), ForeignKey('projects.id'), primary_key=True)
)

class UserModel(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="user")  # 'user' or 'platform_admin'
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Many-to-many relationship with projects
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

class ProjectFileModel(Base):
    __tablename__ = "project_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(100), nullable=True)
    upload_timestamp = Column(DateTime, default=datetime.utcnow)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)

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
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to project
    project = relationship("ProjectModel")

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
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
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
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
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

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
