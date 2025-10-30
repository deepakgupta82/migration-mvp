"""Add Terraform execution tracking

Revision ID: 002_add_terraform_execution
Revises: 001_create_tables
Create Date: 2025-01-08

Tables created:
- terraform_executions: Terraform operation audit trail (plan, apply, validate, destroy)
- terraform_resources: Individual resource change tracking
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002_add_terraform_execution'
down_revision = '001_create_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create Terraform execution tracking tables."""
    
    # Create enum types for Terraform execution
    op.execute("CREATE TYPE terraformexecutionstatus AS ENUM ('PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'CANCELLED')")
    op.execute("CREATE TYPE terraformexecutiontype AS ENUM ('INIT', 'PLAN', 'APPLY', 'DESTROY', 'VALIDATE')")
    
    # Create terraform_executions table
    op.create_table(
        'terraform_executions',
        sa.Column('execution_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('scan_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('policy_scans.scan_id', ondelete='SET NULL')),
        sa.Column('execution_type', sa.Enum('INIT', 'PLAN', 'APPLY', 'DESTROY', 'VALIDATE', name='terraformexecutiontype'), nullable=False),
        sa.Column('status', sa.Enum('PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'CANCELLED', name='terraformexecutionstatus'), nullable=False),
        sa.Column('workspace_path', sa.Text, nullable=False),
        sa.Column('workspace_name', sa.String(100)),
        sa.Column('var_file', sa.Text),
        sa.Column('variables', postgresql.JSON, default=dict),
        sa.Column('backend_config', postgresql.JSON, default=dict),
        sa.Column('target_resources', postgresql.JSON, default=list),
        sa.Column('auto_approve', sa.Boolean, default=False, nullable=False),
        sa.Column('plan_id', sa.String(100)),
        sa.Column('changes_summary', postgresql.JSON),
        sa.Column('resources_affected', postgresql.JSON, default=list),
        sa.Column('started_at', sa.DateTime),
        sa.Column('completed_at', sa.DateTime),
        sa.Column('duration_seconds', sa.Integer),
        sa.Column('output_text', sa.Text),
        sa.Column('error_message', sa.Text),
        sa.Column('error_details', postgresql.JSON),
        sa.Column('is_valid', sa.Boolean),
        sa.Column('diagnostics', postgresql.JSON, default=list),
        sa.Column('error_count', sa.Integer),
        sa.Column('warning_count', sa.Integer),
        sa.Column('execution_metadata', postgresql.JSON, default=dict),
        sa.Column('correlation_id', sa.String(100)),
        sa.Column('triggered_by', sa.String(255)),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )
    
    # Create indexes for terraform_executions
    op.create_index('ix_terraform_executions_project_id', 'terraform_executions', ['project_id'])
    op.create_index('ix_terraform_executions_status', 'terraform_executions', ['status'])
    op.create_index('ix_terraform_executions_execution_type', 'terraform_executions', ['execution_type'])
    op.create_index('ix_terraform_executions_project_status', 'terraform_executions', ['project_id', 'status'])
    op.create_index('ix_terraform_executions_correlation_id', 'terraform_executions', ['correlation_id'])
    op.create_index('ix_terraform_executions_created_at', 'terraform_executions', ['created_at'])
    
    # Create terraform_resources table
    op.create_table(
        'terraform_resources',
        sa.Column('resource_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('execution_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('terraform_executions.execution_id', ondelete='CASCADE'), nullable=False),
        sa.Column('resource_address', sa.Text, nullable=False),
        sa.Column('resource_type', sa.String(100), nullable=False),
        sa.Column('resource_name', sa.String(255), nullable=False),
        sa.Column('module_path', sa.Text),
        sa.Column('action', sa.String(50)),
        sa.Column('change_details', postgresql.JSON, default=dict),
        sa.Column('previous_state', postgresql.JSON),
        sa.Column('new_state', postgresql.JSON),
        sa.Column('provider', sa.String(100)),
        sa.Column('resource_metadata', postgresql.JSON, default=dict),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )
    
    # Create indexes for terraform_resources
    op.create_index('ix_terraform_resources_execution_id', 'terraform_resources', ['execution_id'])
    op.create_index('ix_terraform_resources_resource_type', 'terraform_resources', ['resource_type'])
    op.create_index('ix_terraform_resources_action', 'terraform_resources', ['action'])
    op.create_index('ix_terraform_resources_resource_address', 'terraform_resources', ['resource_address'])


def downgrade() -> None:
    """Drop Terraform execution tracking tables."""
    
    # Drop tables
    op.drop_table('terraform_resources')
    op.drop_table('terraform_executions')
    
    # Drop enum types
    op.execute('DROP TYPE IF EXISTS terraformexecutiontype')
    op.execute('DROP TYPE IF EXISTS terraformexecutionstatus')
