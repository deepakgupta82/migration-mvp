"""enrich proposals with evidence + validation metrics and indexes

Revision ID: 0003_enrich_proposals
Revises: 0002_add_facts_and_sources
Create Date: 2025-09-25
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import reflection

revision = "0003_enrich_proposals"
down_revision = "0002_add_facts_and_sources"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = reflection.Inspector.from_engine(bind)  # type: ignore
    cols = [c['name'] for c in insp.get_columns(table)]
    return column in cols


def upgrade() -> None:
    # Add new JSON columns if not present (evidence + validation metrics)
    if not _has_column('pvc_proposals', 'evidence'):
        op.add_column('pvc_proposals', sa.Column('evidence', sa.JSON(), nullable=True))
    if not _has_column('pvc_proposals', 'validation_metrics'):
        op.add_column('pvc_proposals', sa.Column('validation_metrics', sa.JSON(), nullable=True))

    # Create GIN indexes for entities / relationships arrays where Postgres is used
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        try:
            op.execute('CREATE INDEX IF NOT EXISTS ix_pvc_proposals_entities_gin ON pvc_proposals USING GIN ((entities));')
        except Exception:
            pass
        try:
            op.execute('CREATE INDEX IF NOT EXISTS ix_pvc_proposals_relationships_gin ON pvc_proposals USING GIN ((relationships));')
        except Exception:
            pass


def downgrade() -> None:
    # Best-effort drops; keep indexes if failure
    try:
        op.drop_column('pvc_proposals', 'validation_metrics')
    except Exception:
        pass
    try:
        op.drop_column('pvc_proposals', 'evidence')
    except Exception:
        pass