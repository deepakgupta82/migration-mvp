"""add payload_* columns for enriched proposal artifacts

Revision ID: 0005_add_payload_columns
Revises: 0004_add_proposal_type
Create Date: 2025-09-25
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import reflection

revision = "0005_add_payload_columns"
down_revision = "0004_add_proposal_type"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = reflection.Inspector.from_engine(bind)  # type: ignore
    try:
        cols = [c["name"] for c in insp.get_columns(table)]
    except Exception:
        return False
    return column in cols


def upgrade() -> None:
    # Add JSON payload columns if not already present (idempotent)
    for col in ["payload_entities", "payload_relationships", "payload_facts"]:
        if not _has_column("pvc_proposals", col):
            try:
                op.add_column("pvc_proposals", sa.Column(col, sa.JSON(), nullable=True))
            except Exception:
                pass

    # Create GIN indexes if running on Postgres for payload columns
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        statements = [
            "CREATE INDEX IF NOT EXISTS ix_pvc_proposals_payload_entities_gin ON pvc_proposals USING GIN ((payload_entities));",
            "CREATE INDEX IF NOT EXISTS ix_pvc_proposals_payload_relationships_gin ON pvc_proposals USING GIN ((payload_relationships));",
            "CREATE INDEX IF NOT EXISTS ix_pvc_proposals_payload_facts_gin ON pvc_proposals USING GIN ((payload_facts));",
        ]
        for stmt in statements:
            try:
                op.execute(stmt)
            except Exception:
                pass


def downgrade() -> None:
    # Best-effort removal of payload columns (indexes will drop automatically with table or remain harmless)
    for col in ["payload_facts", "payload_relationships", "payload_entities"]:
        try:
            op.drop_column("pvc_proposals", col)
        except Exception:
            pass
