"""create analysis tables

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2025-09-01 15:36:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create analysis_versions table
    op.create_table('analysis_versions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('version_number', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('version_number')
    )

    # Create analysis_batches table
    op.create_table('analysis_batches',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('version_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('batch_name', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['version_id'], ['analysis_versions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create analysis_results table
    op.create_table('analysis_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('batch_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('result_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('line_number', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='processed'),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['batch_id'], ['analysis_batches.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('idx_analysis_batch_version_id', 'analysis_batches', ['version_id'], unique=False)
    op.create_index('idx_analysis_result_batch_id', 'analysis_results', ['batch_id'], unique=False)
    op.create_index('idx_analysis_batch_status', 'analysis_batches', ['status'], unique=False)
    op.create_index('idx_analysis_result_status', 'analysis_results', ['status'], unique=False)


def downgrade():
    # Drop indexes
    op.drop_index('idx_analysis_result_status', table_name='analysis_results')
    op.drop_index('idx_analysis_batch_status', table_name='analysis_batches')
    op.drop_index('idx_analysis_result_batch_id', table_name='analysis_results')
    op.drop_index('idx_analysis_batch_version_id', table_name='analysis_batches')

    # Drop tables
    op.drop_table('analysis_results')
    op.drop_table('analysis_batches')
    op.drop_table('analysis_versions')