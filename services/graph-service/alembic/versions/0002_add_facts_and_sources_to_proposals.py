"""add facts and sources to pvc_proposals

Revision ID: 0002_add_facts_and_sources
Revises: 0001_init_pvc_repo
Create Date: 2025-09-24

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0002_add_facts_and_sources'
down_revision = '0001_init_pvc_repo'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('pvc_proposals', sa.Column('facts', sa.JSON(), nullable=True))
    op.add_column('pvc_proposals', sa.Column('source_documents', sa.JSON(), nullable=True))


def downgrade() -> None:
    try:
        op.drop_column('pvc_proposals', 'source_documents')
    except Exception:
        pass
    try:
        op.drop_column('pvc_proposals', 'facts')
    except Exception:
        pass
