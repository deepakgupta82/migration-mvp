"""add proposal_type column

Revision ID: 0004_add_proposal_type
Revises: 0003_enrich_proposals
Create Date: 2025-09-25

NOTE:
    The original down_revision incorrectly pointed to
    '0003_enrich_proposals_with_evidence_and_indexes' while the actual
    revision id defined in 0003 file is '0003_enrich_proposals'. This mismatch
    caused Alembic KeyError during upgrade (could not resolve revision map).
    Updated to correct chain so future upgrades succeed.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0004_add_proposal_type'
down_revision = '0003_enrich_proposals'
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
