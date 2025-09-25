"""init pvc repo

Revision ID: 0001_init_pvc_repo
Revises: 
Create Date: 2025-09-22

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_init_pvc_repo'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'pvc_proposals',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('project_id', sa.String(length=64), nullable=False, index=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('validated_at', sa.DateTime(), nullable=True),
        sa.Column('committed_at', sa.DateTime(), nullable=True),
        sa.Column('entities', sa.JSON(), nullable=True),
        sa.Column('relationships', sa.JSON(), nullable=True),
        sa.Column('counts_entities', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('counts_relationships', sa.Integer(), nullable=True, server_default='0'),
    )
    # Explicit indexes for common queries
    op.create_index('ix_pvc_proposals_project', 'pvc_proposals', ['project_id'])
    op.create_index('ix_pvc_proposals_status', 'pvc_proposals', ['status'])

    op.create_table(
        'pvc_type_registry',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('project_id', sa.String(length=64), nullable=False),
        sa.Column('entity_types', sa.JSON(), nullable=True),
        sa.Column('relationship_types', sa.JSON(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=True, server_default='1'),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_pvc_type_registry_project', 'pvc_type_registry', ['project_id'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_pvc_type_registry_project', table_name='pvc_type_registry')
    op.drop_table('pvc_type_registry')
    op.drop_index('ix_pvc_proposals_status', table_name='pvc_proposals')
    op.drop_index('ix_pvc_proposals_project', table_name='pvc_proposals')
    op.drop_table('pvc_proposals')
