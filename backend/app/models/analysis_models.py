from sqlalchemy import Column, String, DateTime, Text, Integer, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from typing import Optional, Dict, Any
from pydantic import BaseModel

Base = declarative_base()

class AnalysisVersion(Base):
    __tablename__ = "analysis_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version_number = Column(String(50), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    batches = relationship("AnalysisBatch", back_populates="version")

class AnalysisBatch(Base):
    __tablename__ = "analysis_batches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version_id = Column(UUID(as_uuid=True), ForeignKey("analysis_versions.id"), nullable=False)
    batch_name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    version = relationship("AnalysisVersion", back_populates="batches")
    results = relationship("AnalysisResult", back_populates="batch")

class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id = Column(UUID(as_uuid=True), ForeignKey("analysis_batches.id"), nullable=False)
    result_data = Column(JSONB, nullable=False)
    line_number = Column(Integer, nullable=False)
    status = Column(String(50), nullable=False, default="processed")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    batch = relationship("AnalysisBatch", back_populates="results")

# Indexes for performance
Index('idx_analysis_batch_version_id', AnalysisBatch.version_id)
Index('idx_analysis_result_batch_id', AnalysisResult.batch_id)
Index('idx_analysis_batch_status', AnalysisBatch.status)
Index('idx_analysis_result_status', AnalysisResult.status)

# Pydantic models for API
class AnalysisVersionBase(BaseModel):
    version_number: str
    description: Optional[str] = None

class AnalysisVersionCreate(AnalysisVersionBase):
    pass

class AnalysisVersionResponse(AnalysisVersionBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class AnalysisBatchBase(BaseModel):
    batch_name: str
    status: str = "pending"

class AnalysisBatchCreate(AnalysisBatchBase):
    version_id: str

class AnalysisBatchResponse(AnalysisBatchBase):
    id: str
    version_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class AnalysisResultBase(BaseModel):
    result_data: Dict[str, Any]
    line_number: int
    status: str = "processed"

class AnalysisResultCreate(AnalysisResultBase):
    batch_id: str

class AnalysisResultResponse(AnalysisResultBase):
    id: str
    batch_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True