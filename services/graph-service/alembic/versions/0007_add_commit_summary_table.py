"""add commit summary table

Revision ID: 0007_add_commit_summary_table
Revises: 0006_add_pending_types_columns
Create Date: 2025-09-25
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import reflection

revision = "0007_add_commit_summary_table"
down_revision = "0006_add_pending_types_columns"
branch_labels = None
depends_on = None

def _has_table(table: str) -> bool:
    bind = op.get_bind()
    insp = reflection.Inspector.from_engine(bind)  # type: ignore
    try:
        return table in insp.get_table_names()
    except Exception:
        return False


def upgrade() -> None:
    if not _has_table("pvc_commit_summaries"):
        try:
            op.create_table(
                "pvc_commit_summaries",
                sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
                sa.Column("proposal_id", sa.String(64), index=True, nullable=False),
                sa.Column("project_id", sa.String(64), index=True, nullable=False),
                sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
                sa.Column("summary", sa.JSON(), nullable=True),
            )
            # Composite index for quick lookup
            op.create_index(
                "ix_pvc_commit_summaries_project_proposal",
                "pvc_commit_summaries",
                ["project_id", "proposal_id"],
                unique=False,
            )
        except Exception:
            # best-effort; ignore if concurrent creation
            pass


def downgrade() -> None:
    try:
        op.drop_table("pvc_commit_summaries")
    except Exception:
        pass
