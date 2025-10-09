"""Create IAC governance tables

Revision ID: 001_create_tables
Revises: 
Create Date: 2025-10-09

Tables created:
- policy_templates: Reusable policy definitions
- policy_scans: IAC scan executions
- policy_violations: Individual violations found
- remediation_actions: Automated/manual fixes
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
    """Create all IAC governance tables."""
    
    # Create policy_templates table
    op.create_table(
        'policy_templates',
        sa.Column('template_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('template_name', sa.String(255), nullable=False),
        sa.Column('template_description', sa.Text),
        sa.Column('policy_category', sa.String(100), nullable=False),
        sa.Column('severity', sa.Enum('CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO', name='policyseverity'), nullable=False),
        sa.Column('engine_type', sa.String(50), nullable=False),
        sa.Column('policy_code', sa.Text, nullable=False),
        sa.Column('supported_frameworks', postgresql.JSON, nullable=False),
        sa.Column('cloud_providers', postgresql.JSON, nullable=False),
        sa.Column('is_active', sa.Boolean, default=True, nullable=False),
        sa.Column('is_blocking', sa.Boolean, default=False, nullable=False),
        sa.Column('auto_remediate', sa.Boolean, default=False, nullable=False),
        sa.Column('tags', postgresql.JSON, default=list),
        sa.Column('policy_metadata', postgresql.JSON, default=dict),
        sa.Column('created_by', sa.String(255)),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )
    
    # Create indexes for policy_templates
    op.create_index('ix_policy_templates_template_name', 'policy_templates', ['template_name'])
    op.create_index('ix_policy_templates_policy_category', 'policy_templates', ['policy_category'])
    op.create_index('ix_policy_templates_severity', 'policy_templates', ['severity'])
    op.create_index('ix_policy_templates_category_severity', 'policy_templates', ['policy_category', 'severity'])
    op.create_index('ix_policy_templates_active', 'policy_templates', ['is_active', 'is_blocking'])
    
    # Create policy_scans table
    op.create_table(
        'policy_scans',
        sa.Column('scan_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('template_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('policy_templates.template_id', ondelete='CASCADE')),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('scan_name', sa.String(255), nullable=False),
        sa.Column('scan_description', sa.Text),
        sa.Column('iac_framework', sa.String(50), nullable=False),
        sa.Column('iac_version', sa.String(50)),
        sa.Column('source_type', sa.String(50), nullable=False),
        sa.Column('source_location', sa.Text, nullable=False),
        sa.Column('source_branch', sa.String(100)),
        sa.Column('source_commit', sa.String(100)),
        sa.Column('status', sa.Enum('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED', name='scanstatus'), nullable=False),
        sa.Column('started_at', sa.DateTime),
        sa.Column('completed_at', sa.DateTime),
        sa.Column('duration_seconds', sa.Integer),
        sa.Column('total_resources', sa.Integer, default=0),
        sa.Column('passed_checks', sa.Integer, default=0),
        sa.Column('failed_checks', sa.Integer, default=0),
        sa.Column('violations_critical', sa.Integer, default=0),
        sa.Column('violations_high', sa.Integer, default=0),
        sa.Column('violations_medium', sa.Integer, default=0),
        sa.Column('violations_low', sa.Integer, default=0),
        sa.Column('violations_info', sa.Integer, default=0),
        sa.Column('error_message', sa.Text),
        sa.Column('error_details', postgresql.JSON),
        sa.Column('scan_config', postgresql.JSON, default=dict),
        sa.Column('correlation_id', sa.String(100)),
        sa.Column('scan_metadata', postgresql.JSON, default=dict),
        sa.Column('triggered_by', sa.String(255)),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )
    
    # Create indexes for policy_scans
    op.create_index('ix_policy_scans_project_id', 'policy_scans', ['project_id'])
    op.create_index('ix_policy_scans_status', 'policy_scans', ['status'])
    op.create_index('ix_policy_scans_project_status', 'policy_scans', ['project_id', 'status'])
    op.create_index('ix_policy_scans_correlation_id', 'policy_scans', ['correlation_id'])
    op.create_index('ix_policy_scans_created_at', 'policy_scans', ['created_at'])
    
    # Create policy_violations table
    op.create_table(
        'policy_violations',
        sa.Column('violation_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('scan_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('policy_scans.scan_id', ondelete='CASCADE'), nullable=False),
        sa.Column('template_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('policy_templates.template_id', ondelete='SET NULL')),
        sa.Column('violation_rule', sa.String(255), nullable=False),
        sa.Column('severity', sa.Enum('CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO', name='policyseverity'), nullable=False),
        sa.Column('resource_type', sa.String(100), nullable=False),
        sa.Column('resource_name', sa.String(255), nullable=False),
        sa.Column('resource_identifier', sa.Text, nullable=False),
        sa.Column('file_path', sa.Text),
        sa.Column('line_number', sa.Integer),
        sa.Column('violation_message', sa.Text, nullable=False),
        sa.Column('violation_details', postgresql.JSON),
        sa.Column('recommended_fix', sa.Text),
        sa.Column('is_resolved', sa.Boolean, default=False, nullable=False),
        sa.Column('resolved_at', sa.DateTime),
        sa.Column('resolved_by', sa.String(255)),
        sa.Column('resolution_notes', sa.Text),
        sa.Column('is_suppressed', sa.Boolean, default=False, nullable=False),
        sa.Column('suppressed_reason', sa.Text),
        sa.Column('suppressed_until', sa.DateTime),
        sa.Column('violation_metadata', postgresql.JSON, default=dict),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )
    
    # Create indexes for policy_violations
    op.create_index('ix_policy_violations_scan_id', 'policy_violations', ['scan_id'])
    op.create_index('ix_policy_violations_severity', 'policy_violations', ['severity'])
    op.create_index('ix_policy_violations_scan_severity', 'policy_violations', ['scan_id', 'severity'])
    op.create_index('ix_policy_violations_violation_rule', 'policy_violations', ['violation_rule'])
    op.create_index('ix_policy_violations_is_resolved', 'policy_violations', ['is_resolved'])
    op.create_index('ix_policy_violations_resolved', 'policy_violations', ['is_resolved', 'is_suppressed'])
    
    # Create remediation_actions table
    op.create_table(
        'remediation_actions',
        sa.Column('action_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('violation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('policy_violations.violation_id', ondelete='CASCADE'), nullable=False),
        sa.Column('action_type', sa.String(100), nullable=False),
        sa.Column('action_name', sa.String(255), nullable=False),
        sa.Column('action_description', sa.Text),
        sa.Column('remediation_method', sa.String(100), nullable=False),
        sa.Column('remediation_code', sa.Text),
        sa.Column('remediation_params', postgresql.JSON, default=dict),
        sa.Column('status', sa.Enum('PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'SKIPPED', name='remediationstatus'), nullable=False),
        sa.Column('started_at', sa.DateTime),
        sa.Column('completed_at', sa.DateTime),
        sa.Column('duration_seconds', sa.Integer),
        sa.Column('is_successful', sa.Boolean),
        sa.Column('result', postgresql.JSON),
        sa.Column('error_message', sa.Text),
        sa.Column('requires_approval', sa.Boolean, default=False, nullable=False),
        sa.Column('approved_by', sa.String(255)),
        sa.Column('approved_at', sa.DateTime),
        sa.Column('approval_notes', sa.Text),
        sa.Column('action_metadata', postgresql.JSON, default=dict),
        sa.Column('correlation_id', sa.String(100)),
        sa.Column('triggered_by', sa.String(255)),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )
    
    # Create indexes for remediation_actions
    op.create_index('ix_remediation_actions_violation_id', 'remediation_actions', ['violation_id'])
    op.create_index('ix_remediation_actions_status', 'remediation_actions', ['status'])
    op.create_index('ix_remediation_actions_violation_status', 'remediation_actions', ['violation_id', 'status'])
    op.create_index('ix_remediation_actions_correlation_id', 'remediation_actions', ['correlation_id'])
    op.create_index('ix_remediation_actions_approval', 'remediation_actions', ['requires_approval', 'approved_at'])


def downgrade() -> None:
    """Drop all IAC governance tables."""
    op.drop_table('remediation_actions')
    op.drop_table('policy_violations')
    op.drop_table('policy_scans')
    op.drop_table('policy_templates')
    
    # Drop custom enums
    op.execute('DROP TYPE IF EXISTS remediationstatus')
    op.execute('DROP TYPE IF EXISTS scanstatus')
    op.execute('DROP TYPE IF EXISTS policyseverity')
