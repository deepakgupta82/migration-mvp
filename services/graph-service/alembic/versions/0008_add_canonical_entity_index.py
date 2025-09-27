"""add canonical entity index table

Revision ID: 0008_add_canonical_entity_index
Revises: 0007_add_commit_summary_table
Create Date: 2025-09-26
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import reflection

revision = "0008_add_canonical_entity_index"
down_revision = "0007_add_commit_summary_table"
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
    if not _has_table("pvc_canonical_entity_index"):
        try:
            op.create_table(
                "pvc_canonical_entity_index",
                sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
                sa.Column("project_id", sa.String(64), nullable=False),
                sa.Column("slug", sa.String(128), nullable=False),
                sa.Column("name", sa.String(256), nullable=True),
                sa.Column("type", sa.String(64), nullable=True),
                sa.Column("occurrences", sa.Integer(), nullable=False, server_default="0"),
                sa.Column("degree_in", sa.Integer(), nullable=False, server_default="0"),
                sa.Column("degree_out", sa.Integer(), nullable=False, server_default="0"),
                sa.Column("total_degree", sa.Integer(), nullable=False, server_default="0"),
                sa.Column("relationship_type_counts", sa.JSON(), nullable=True),
                sa.Column("first_proposal_id", sa.String(64), nullable=True),
                sa.Column("last_proposal_id", sa.String(64), nullable=True),
                sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
                sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            )
            op.create_index(
                "ix_canonical_entity_project_slug",
                "pvc_canonical_entity_index",
                ["project_id", "slug"],
                unique=True,
            )
            op.create_index(
                "ix_canonical_entity_project_degree",
                "pvc_canonical_entity_index",
                ["project_id", "total_degree"],
                unique=False,
            )
        except Exception:
            pass


def downgrade() -> None:
    try:
        op.drop_table("pvc_canonical_entity_index")
    except Exception:
        pass
