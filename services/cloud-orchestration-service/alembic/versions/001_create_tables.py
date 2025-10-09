"""Create initial cloud orchestration tables.

Revision ID: 001_create_tables
Revises: 
Create Date: 2025-10-09 12:10:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_create_tables'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create migration_waves, migration_resources, and migration_tasks tables."""
    
    # Create migration_waves table
    op.create_table(
        'migration_waves',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='planning'),
        sa.Column('target_cloud', sa.String(50), nullable=False),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('wave_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    
    # Create indexes for migration_waves
    op.create_index('idx_wave_name', 'migration_waves', ['name'])
    op.create_index('idx_wave_status', 'migration_waves', ['status'])
    op.create_index('idx_wave_target_cloud', 'migration_waves', ['target_cloud'])
    op.create_index('idx_wave_status_cloud', 'migration_waves', ['status', 'target_cloud'])
    op.create_index('idx_wave_start_date', 'migration_waves', ['start_date'])
    
    # Create migration_resources table
    op.create_table(
        'migration_resources',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('wave_id', sa.String(36), nullable=False),
        sa.Column('resource_type', sa.String(100), nullable=False),
        sa.Column('source_identifier', sa.String(500), nullable=False),
        sa.Column('target_identifier', sa.String(500), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('dependencies', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='[]'),
        sa.Column('resource_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['wave_id'], ['migration_waves.id'], ondelete='CASCADE'),
    )
    
    # Create indexes for migration_resources
    op.create_index('idx_resource_wave_id', 'migration_resources', ['wave_id'])
    op.create_index('idx_resource_type', 'migration_resources', ['resource_type'])
    op.create_index('idx_resource_status', 'migration_resources', ['status'])
    op.create_index('idx_resource_wave_status', 'migration_resources', ['wave_id', 'status'])
    op.create_index('idx_source_identifier', 'migration_resources', ['source_identifier'])
    
    # Create migration_tasks table
    op.create_table(
        'migration_tasks',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('resource_id', sa.String(36), nullable=False),
        sa.Column('task_type', sa.String(100), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('execution_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('task_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'),
        sa.ForeignKeyConstraint(['resource_id'], ['migration_resources.id'], ondelete='CASCADE'),
    )
    
    # Create indexes for migration_tasks
    op.create_index('idx_task_resource_id', 'migration_tasks', ['resource_id'])
    op.create_index('idx_task_status', 'migration_tasks', ['status'])
    op.create_index('idx_task_type', 'migration_tasks', ['task_type'])
    op.create_index('idx_task_resource_order', 'migration_tasks', ['resource_id', 'execution_order'])


def downgrade() -> None:
    """Drop all cloud orchestration tables."""
    op.drop_table('migration_tasks')
    op.drop_table('migration_resources')
    op.drop_table('migration_waves')
