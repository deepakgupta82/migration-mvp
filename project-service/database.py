from sqlalchemy import create_engine, Column, String, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
import os

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://projectuser:projectpass@postgres:5432/projectdb")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to project files
    files = relationship("ProjectFileModel", back_populates="project", cascade="all, delete-orphan")

class ProjectFileModel(Base):
    __tablename__ = "project_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(100), nullable=True)
    upload_timestamp = Column(DateTime, default=datetime.utcnow)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)

    # Relationship back to project
    project = relationship("ProjectModel", back_populates="files")

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
