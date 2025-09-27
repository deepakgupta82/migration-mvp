"""add pending type columns for proposals (A6 gating)

Revision ID: 0006_add_pending_types_columns
Revises: 0005_add_payload_columns
Create Date: 2025-09-25
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import reflection

revision = "0006_add_pending_types_columns"
down_revision = "0005_add_payload_columns"
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
    for col in ["pending_entity_types", "pending_relationship_types"]:
        if not _has_column("pvc_proposals", col):
            try:
                op.add_column("pvc_proposals", sa.Column(col, sa.JSON(), nullable=True))
            except Exception:
                pass


def downgrade() -> None:
    for col in ["pending_relationship_types", "pending_entity_types"]:
        try:
            op.drop_column("pvc_proposals", col)
        except Exception:
            pass
