"""add proposal_type column

Revision ID: 0004_add_proposal_type
Revises: 0003_enrich_proposals_with_evidence_and_indexes
Create Date: 2025-09-25
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0004_add_proposal_type'
down_revision = '0003_enrich_proposals_with_evidence_and_indexes'
branch_labels = None
depends_on = None

def upgrade():
    try:
        op.add_column('pvc_proposals', sa.Column('proposal_type', sa.String(length=32), nullable=False, server_default='standard'))
    except Exception:
        pass


def downgrade():
    try:
        op.drop_column('pvc_proposals', 'proposal_type')
    except Exception:
        pass
