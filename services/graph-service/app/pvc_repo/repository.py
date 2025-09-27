from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import uuid

from .models import Base, ProposalORM, TypeRegistryORM, CommitSummaryORM, CanonicalEntityIndexORM, get_engine_and_session


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
        self, proposal_id: str, project_id: str, entities: List[Dict[str, Any]], relationships: List[Dict[str, Any]], facts: Optional[List[Dict[str, Any]]] = None, source_documents: Optional[List[Dict[str, Any]]] = None, proposal_type: str = "standard", payload_entities: Optional[List[Dict[str, Any]]] = None, payload_relationships: Optional[List[Dict[str, Any]]] = None, payload_facts: Optional[List[Dict[str, Any]]] = None
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
                payload_entities=payload_entities or [],
                payload_relationships=payload_relationships or [],
                payload_facts=payload_facts or [],
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
                "payload_entities": getattr(p, 'payload_entities', None) or [],
                "payload_relationships": getattr(p, 'payload_relationships', None) or [],
                "payload_facts": getattr(p, 'payload_facts', None) or [],
                "pending_entity_types": getattr(p, 'pending_entity_types', None) or [],
                "pending_relationship_types": getattr(p, 'pending_relationship_types', None) or [],
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

    def update_proposal_validation(
        self,
        proposal_id: str,
        validation_metrics: Dict[str, Any],
        evidence: Optional[List[Dict[str, Any]]] = None,
        auto_status: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Persist validation metrics (and optional evidence) for a proposal.

        Sets status to 'validated' (unless auto_status False) and stamps validated_at.
        Returns the updated lightweight proposal dict or None if not found.
        """
        with session_scope() as s:
            p: Optional[ProposalORM] = s.query(ProposalORM).get(proposal_id)
            if p is None:
                return None
            p.validation_metrics = (validation_metrics or {})
            if evidence is not None:
                # Merge with existing evidence (avoid duplication by kind if present)
                existing = p.evidence or []
                # naive append; de-dup by (kind, hash(data))
                merged = existing + evidence
                seen = set()
                dedup: List[Dict[str, Any]] = []
                for ev in merged:
                    if not isinstance(ev, dict):
                        continue
                    key = (ev.get("kind"), str(ev.get("data"))[:200])
                    if key in seen:
                        continue
                    seen.add(key)
                    dedup.append(ev)
                p.evidence = dedup
            if auto_status:
                p.status = "validated"
                p.validated_at = datetime.utcnow()
            s.add(p)
            s.flush()
            return {
                "proposal_id": p.id,
                "project_id": p.project_id,
                "status": p.status,
                "validation_metrics": p.validation_metrics or {},
            }

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
                    "payload_entities": getattr(p, 'payload_entities', None) or [],
                    "payload_relationships": getattr(p, 'payload_relationships', None) or [],
                    "payload_facts": getattr(p, 'payload_facts', None) or [],
                    "pending_entity_types": getattr(p, 'pending_entity_types', None) or [],
                    "pending_relationship_types": getattr(p, 'pending_relationship_types', None) or [],
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

    # --- Commit Summary Helpers ---
    def add_commit_summary(self, proposal_id: str, project_id: str, summary: Dict[str, Any]) -> Dict[str, Any]:
        with session_scope() as s:
            obj = CommitSummaryORM(proposal_id=proposal_id, project_id=project_id, summary=summary or {})
            s.add(obj)
            s.flush()
            return {"id": obj.id, "proposal_id": obj.proposal_id, "project_id": obj.project_id, "created_at": obj.created_at.isoformat()}

    def get_commit_summary(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        with session_scope() as s:
            cs: Optional[CommitSummaryORM] = (
                s.query(CommitSummaryORM).filter(CommitSummaryORM.proposal_id == proposal_id).order_by(CommitSummaryORM.id.desc()).first()
            )
            if not cs:
                return None
            return {"id": cs.id, "proposal_id": cs.proposal_id, "project_id": cs.project_id, "summary": cs.summary or {}, "created_at": cs.created_at.isoformat()}

    def list_commit_summaries(self, project_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        with session_scope() as s:
            rows: List[CommitSummaryORM] = (
                s.query(CommitSummaryORM).filter(CommitSummaryORM.project_id == project_id).order_by(CommitSummaryORM.id.desc()).limit(limit).all()
            )
            out: List[Dict[str, Any]] = []
            for r in rows:
                out.append({"id": r.id, "proposal_id": r.proposal_id, "project_id": r.project_id, "summary": r.summary or {}, "created_at": r.created_at.isoformat()})
            return out

    # --- Canonical Entity Index Methods ---
    def upsert_canonical_entities(self, project_id: str, proposal_id: str, rows: List[Dict[str, Any]]) -> int:
        """Upsert a batch of canonical entity index rows.

        Each row expected keys: slug, name, type, occurrences, degree_in, degree_out,
        total_degree, relationship_type_counts.
        Slug+project is the natural key. We update counts & degrees cumulatively and track
        first/last proposal ids.
        Returns number of rows processed.
        """
        if not rows:
            return 0
        now = datetime.utcnow()
        processed = 0
        with session_scope() as s:
            for r in rows:
                slug = r.get("slug")
                if not slug:
                    continue
                existing: Optional[CanonicalEntityIndexORM] = (
                    s.query(CanonicalEntityIndexORM)
                    .filter(CanonicalEntityIndexORM.project_id == project_id, CanonicalEntityIndexORM.slug == slug)
                    .one_or_none()
                )
                if existing is None:
                    obj = CanonicalEntityIndexORM(
                        project_id=project_id,
                        slug=slug,
                        name=r.get("name"),
                        type=r.get("type"),
                        occurrences=r.get("occurrences", 0),
                        degree_in=r.get("degree_in", 0),
                        degree_out=r.get("degree_out", 0),
                        total_degree=r.get("total_degree", 0),
                        relationship_type_counts=r.get("relationship_type_counts", {}) or {},
                        first_proposal_id=proposal_id,
                        last_proposal_id=proposal_id,
                        created_at=now,
                        updated_at=now,
                    )
                    s.add(obj)
                else:
                    # cumulative updates
                    existing.occurrences += r.get("occurrences", 0)
                    existing.degree_in += r.get("degree_in", 0)
                    existing.degree_out += r.get("degree_out", 0)
                    existing.total_degree += r.get("total_degree", 0)
                    # merge relationship_type_counts
                    rtc_new = r.get("relationship_type_counts") or {}
                    base_rtc = existing.relationship_type_counts or {}
                    for k, v in rtc_new.items():
                        try:
                            base_rtc[k] = int(base_rtc.get(k, 0)) + int(v)
                        except Exception:
                            pass
                    existing.relationship_type_counts = base_rtc
                    if not existing.first_proposal_id:
                        existing.first_proposal_id = proposal_id
                    existing.last_proposal_id = proposal_id
                    existing.updated_at = now
                    s.add(existing)
                processed += 1
            s.flush()
        return processed

    def list_canonical_entities(self, project_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        with session_scope() as s:
            rows: List[CanonicalEntityIndexORM] = (
                s.query(CanonicalEntityIndexORM)
                .filter(CanonicalEntityIndexORM.project_id == project_id)
                .order_by(CanonicalEntityIndexORM.total_degree.desc())
                .limit(limit)
                .all()
            )
            out: List[Dict[str, Any]] = []
            for r in rows:
                out.append({
                    "slug": r.slug,
                    "name": r.name,
                    "type": r.type,
                    "occurrences": r.occurrences,
                    "degree_in": r.degree_in,
                    "degree_out": r.degree_out,
                    "total_degree": r.total_degree,
                    "relationship_type_counts": r.relationship_type_counts or {},
                    "first_proposal_id": r.first_proposal_id,
                    "last_proposal_id": r.last_proposal_id,
                    "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                })
            return out
