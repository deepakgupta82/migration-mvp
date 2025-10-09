"""SQLAlchemy ORM models for cloud orchestration service.

This module defines the database models for multi-cloud migration orchestration:
- MigrationWave: Logical grouping of resources to migrate together
- MigrationResource: Individual resources to be migrated
- MigrationTask: Atomic migration tasks for each resource
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from enum import Enum

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Integer,
    ForeignKey,
    Text,
    JSON,
    Index,
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class WaveStatus(str, Enum):
    """Migration wave lifecycle states."""
    PLANNING = "planning"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class ResourceStatus(str, Enum):
    """Migration resource states."""
    PENDING = "pending"
    VALIDATING = "validating"
    READY = "ready"
    MIGRATING = "migrating"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class TaskStatus(str, Enum):
    """Migration task states."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    SKIPPED = "skipped"


class TargetCloud(str, Enum):
    """Supported target cloud platforms."""
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    MULTI = "multi"  # Multi-cloud wave


class MigrationWave(Base):
    """Logical grouping of resources to migrate together.
    
    A wave represents a coordinated migration effort with a defined
    schedule, target cloud, and set of resources. Waves help organize
    large-scale migrations into manageable chunks.
    """
    
    __tablename__ = "migration_waves"
    
    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default=WaveStatus.PLANNING.value, index=True)
    target_cloud = Column(String(50), nullable=False, index=True)
    
    # Scheduling
    start_date = Column(DateTime(timezone=True), nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=True)
    
    # Metadata and configuration
    wave_metadata = Column(JSON, nullable=True, default=dict)
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    resources = relationship("MigrationResource", back_populates="wave", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index("idx_wave_status_cloud", "status", "target_cloud"),
        Index("idx_wave_start_date", "start_date"),
    )


class MigrationResource(Base):
    """Individual resource to be migrated within a wave.
    
    Represents a single infrastructure component (VM, database, storage, etc.)
    that needs to be migrated. Tracks source and target identifiers,
    dependencies, and migration status.
    """
    
    __tablename__ = "migration_resources"
    
    id = Column(String(36), primary_key=True)
    wave_id = Column(String(36), ForeignKey("migration_waves.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Resource identification
    resource_type = Column(String(100), nullable=False, index=True)  # e.g., "vm", "database", "storage"
    source_identifier = Column(String(500), nullable=False)  # Source cloud resource ID
    target_identifier = Column(String(500), nullable=True)  # Target cloud resource ID (populated after migration)
    
    # Status and dependencies
    status = Column(String(50), nullable=False, default=ResourceStatus.PENDING.value, index=True)
    dependencies = Column(JSON, nullable=True, default=list)  # List of resource IDs that must complete first
    
    # Metadata and configuration
    resource_metadata = Column(JSON, nullable=True, default=dict)  # Resource-specific config, tags, etc.
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    wave = relationship("MigrationWave", back_populates="resources")
    tasks = relationship("MigrationTask", back_populates="resource", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index("idx_resource_wave_status", "wave_id", "status"),
        Index("idx_resource_type", "resource_type"),
        Index("idx_source_identifier", "source_identifier"),
    )


class MigrationTask(Base):
    """Atomic migration task for a resource.
    
    Represents a single, executable step in migrating a resource.
    Examples: replication_init, cutover, validation, rollback.
    Tasks are executed in order and can be retried.
    """
    
    __tablename__ = "migration_tasks"
    
    id = Column(String(36), primary_key=True)
    resource_id = Column(String(36), ForeignKey("migration_resources.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Task identification
    task_type = Column(String(100), nullable=False, index=True)  # e.g., "replication", "cutover", "validation"
    status = Column(String(50), nullable=False, default=TaskStatus.PENDING.value, index=True)
    execution_order = Column(Integer, nullable=False, default=0)  # Order within resource migration
    
    # Retry and error handling
    retry_count = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)
    
    # Timing
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Metadata and configuration
    task_metadata = Column(JSON, nullable=True, default=dict)  # Task-specific parameters, MCP tool args, etc.
    
    # Relationships
    resource = relationship("MigrationResource", back_populates="tasks")
    
    # Indexes
    __table_args__ = (
        Index("idx_task_resource_order", "resource_id", "execution_order"),
        Index("idx_task_status", "status"),
        Index("idx_task_type", "task_type"),
    )
