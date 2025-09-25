from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import uuid

from .models import Base, ProposalORM, TypeRegistryORM, get_engine_and_session


engine, SessionLocal = get_engine_and_session()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


@contextmanager
def session_scope():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


class PVCRepository:
    def get_type_registry(self, project_id: str) -> Dict[str, Any]:
        with session_scope() as s:
            tr: Optional[TypeRegistryORM] = (
                s.query(TypeRegistryORM).filter(TypeRegistryORM.project_id == project_id).one_or_none()
            )
            if tr is None:
                return {
                    "project_id": project_id,
                    "entity_types": [],
                    "relationship_types": [],
                    "version": 1,
                    "updated_at": datetime.utcnow().isoformat(),
                }
            return {
                "project_id": tr.project_id,
                "entity_types": tr.entity_types or [],
                "relationship_types": tr.relationship_types or [],
                "version": tr.version or 1,
                "updated_at": (tr.updated_at or datetime.utcnow()).isoformat(),
            }

    def upsert_type_registry(
        self, project_id: str, entity_types: List[Dict[str, Any]], relationship_types: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        now = datetime.utcnow()
        with session_scope() as s:
            tr: Optional[TypeRegistryORM] = (
                s.query(TypeRegistryORM).filter(TypeRegistryORM.project_id == project_id).one_or_none()
            )
            if tr is None:
                tr = TypeRegistryORM(
                    project_id=project_id,
                    entity_types=entity_types,
                    relationship_types=relationship_types,
                    version=1,
                    updated_at=now,
                )
                s.add(tr)
            else:
                tr.entity_types = entity_types
                tr.relationship_types = relationship_types
                tr.version = (tr.version or 1) + 1
                tr.updated_at = now
            s.flush()
            return {
                "project_id": tr.project_id,
                "entity_types": tr.entity_types or [],
                "relationship_types": tr.relationship_types or [],
                "version": tr.version or 1,
                "updated_at": (tr.updated_at or now).isoformat(),
            }

    def create_proposal(
        self, proposal_id: str, project_id: str, entities: List[Dict[str, Any]], relationships: List[Dict[str, Any]], facts: Optional[List[Dict[str, Any]]] = None, source_documents: Optional[List[Dict[str, Any]]] = None, proposal_type: str = "standard"
    ) -> Dict[str, Any]:
        with session_scope() as s:
            obj = ProposalORM(
                id=proposal_id,
                project_id=project_id,
                entities=entities,
                relationships=relationships,
                facts=facts or [],
                source_documents=source_documents or [],
                proposal_type=proposal_type,
                status="pending",
                counts_entities=len(entities or []),
                counts_relationships=len(relationships or []),
            )
            s.add(obj)
            s.flush()
            return {
                "proposal_id": obj.id,
                "status": obj.status,
                "proposal_type": obj.proposal_type,
                "entities": obj.counts_entities,
                "relationships": obj.counts_relationships,
            }

    def get_proposal(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        with session_scope() as s:
            p: Optional[ProposalORM] = s.query(ProposalORM).get(proposal_id)
            if p is None:
                return None
            return {
                "proposal_id": p.id,
                "project_id": p.project_id,
                "status": p.status,
                "proposal_type": getattr(p, 'proposal_type', 'standard'),
                "entities": p.entities or [],
                "relationships": p.relationships or [],
                "facts": getattr(p, 'facts', None) or [],
                "source_documents": getattr(p, 'source_documents', None) or [],
                "evidence": getattr(p, 'evidence', None) or [],
                "validation_metrics": getattr(p, 'validation_metrics', None) or {},
                "counts_entities": p.counts_entities or 0,
                "counts_relationships": p.counts_relationships or 0,
            }

    def set_proposal_status(self, proposal_id: str, status: str) -> None:
        with session_scope() as s:
            p: Optional[ProposalORM] = s.query(ProposalORM).get(proposal_id)
            if p is None:
                return
            p.status = status
            now = datetime.utcnow()
            if status == "validated":
                p.validated_at = now
            if status == "committed":
                p.committed_at = now
            s.add(p)

    def list_proposals(self, project_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List proposals for a project, optionally filtered by status."""
        with session_scope() as s:
            q = s.query(ProposalORM).filter(ProposalORM.project_id == project_id)
            if status:
                q = q.filter(ProposalORM.status == status)
            rows = q.all()
            out: List[Dict[str, Any]] = []
            for p in rows:
                out.append({
                    "proposal_id": p.id,
                    "project_id": p.project_id,
                    "status": p.status,
                    "proposal_type": getattr(p, 'proposal_type', 'standard'),
                    "entities": p.entities or [],
                    "relationships": p.relationships or [],
                    "facts": getattr(p, 'facts', None) or [],
                    "source_documents": getattr(p, 'source_documents', None) or [],
                    "evidence": getattr(p, 'evidence', None) or [],
                    "validation_metrics": getattr(p, 'validation_metrics', None) or {},
                    "counts_entities": p.counts_entities or 0,
                    "counts_relationships": p.counts_relationships or 0,
                })
            return out

    def create_fusion_proposal(self, project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Store a fusion proposal payload reusing proposals table."""
        proposal_id = payload.get("proposal_id") or str(uuid.uuid4())
        entities = payload.get("canonical_entities", [])
        relationships = payload.get("canonical_relationships", [])
        evidence = [
            {"kind": "fusion_stats", "data": payload.get("stats", {})}
        ]
        with session_scope() as s:
            obj = ProposalORM(
                id=proposal_id,
                project_id=project_id,
                entities=entities,
                relationships=relationships,
                proposal_type="fusion",
                evidence=evidence,
                validation_metrics={"fusion": payload.get("stats", {})},
                status="pending",
                counts_entities=len(entities),
                counts_relationships=len(relationships),
            )
            s.add(obj)
            s.flush()
            return {"proposal_id": obj.id, "status": obj.status, "proposal_type": obj.proposal_type}
