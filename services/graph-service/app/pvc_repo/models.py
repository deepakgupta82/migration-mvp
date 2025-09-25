from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()


class ProposalORM(Base):
    __tablename__ = "pvc_proposals"
    id = Column(String(64), primary_key=True)
    project_id = Column(String(64), index=True, nullable=False)
    status = Column(String(32), default="pending", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    validated_at = Column(DateTime, nullable=True)
    committed_at = Column(DateTime, nullable=True)
    entities = Column(JSON, default=list)
    relationships = Column(JSON, default=list)
    # New optional fields for richer proposals
    facts = Column(JSON, default=list)
    source_documents = Column(JSON, default=list)
    counts_entities = Column(Integer, default=0)
    counts_relationships = Column(Integer, default=0)


class TypeRegistryORM(Base):
    __tablename__ = "pvc_type_registry"
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(64), index=True, nullable=False, unique=True)
    entity_types = Column(JSON, default=list)
    relationship_types = Column(JSON, default=list)
    version = Column(Integer, default=1)
    updated_at = Column(DateTime, default=datetime.utcnow)


def get_engine_and_session():
    # Support sqlite for local/dev, Postgres in prod
    db_url = os.getenv("GRAPH_DB_URL") or os.getenv("PVC_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not db_url:
        # default to sqlite file in service dir for quick dev
        db_url = "sqlite:///./pvc_repo.db"
    engine = create_engine(db_url, future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return engine, SessionLocal
