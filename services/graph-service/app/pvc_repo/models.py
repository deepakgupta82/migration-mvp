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
    proposal_type = Column(String(32), default="standard", nullable=False)  # standard|fusion|other
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    validated_at = Column(DateTime, nullable=True)
    committed_at = Column(DateTime, nullable=True)
    entities = Column(JSON, default=list)
    relationships = Column(JSON, default=list)
    # New optional fields for richer proposals
    facts = Column(JSON, default=list)
    source_documents = Column(JSON, default=list)
    evidence = Column(JSON, default=list)  # evidence blocks referencing source elements
    validation_metrics = Column(JSON, default=dict)  # quality metrics from validation pass
    counts_entities = Column(Integer, default=0)
    counts_relationships = Column(Integer, default=0)
    # Payload detail columns (A5) store raw enriched artifacts that underpin the summarized top-level
    # entities/relationships/facts lists. These allow downstream review, re-validation, and selective
    # recomposition without re-running section enrichment.
    payload_entities = Column(JSON, default=list)
    payload_relationships = Column(JSON, default=list)
    payload_facts = Column(JSON, default=list)
    # A6: pending (unapproved) types captured when AUTO_REGISTER_TYPES disabled; proposal stalls at 'pending_types'
    pending_entity_types = Column(JSON, default=list)
    pending_relationship_types = Column(JSON, default=list)


class TypeRegistryORM(Base):
    __tablename__ = "pvc_type_registry"
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(64), index=True, nullable=False, unique=True)
    entity_types = Column(JSON, default=list)
    relationship_types = Column(JSON, default=list)
    version = Column(Integer, default=1)
    updated_at = Column(DateTime, default=datetime.utcnow)


class CommitSummaryORM(Base):
    __tablename__ = "pvc_commit_summaries"
    id = Column(Integer, primary_key=True, autoincrement=True)
    proposal_id = Column(String(64), index=True, nullable=False)
    project_id = Column(String(64), index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    summary = Column(JSON, default=dict)


class CanonicalEntityIndexORM(Base):
    __tablename__ = "pvc_canonical_entity_index"
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(64), index=True, nullable=False)
    slug = Column(String(128), index=True, nullable=False)
    name = Column(String(256), nullable=True)
    type = Column(String(64), nullable=True)
    occurrences = Column(Integer, default=0)
    degree_in = Column(Integer, default=0)
    degree_out = Column(Integer, default=0)
    total_degree = Column(Integer, default=0)
    relationship_type_counts = Column(JSON, default=dict)
    first_proposal_id = Column(String(64), nullable=True)
    last_proposal_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


def get_engine_and_session():
    # Support sqlite for local/dev, Postgres in prod
    db_url = os.getenv("GRAPH_DB_URL") or os.getenv("PVC_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not db_url:
        # default to sqlite file in service dir for quick dev
        db_url = "sqlite:///./pvc_repo.db"
    engine = create_engine(db_url, future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return engine, SessionLocal
