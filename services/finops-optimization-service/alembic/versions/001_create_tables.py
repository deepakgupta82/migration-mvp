"""Create FinOps Optimization tables with TimescaleDB support

Revision ID: 001
Revises: 
Create Date: 2025-01-09

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all tables for FinOps Optimization Service"""
    
    # Note: TimescaleDB extension is optional and not installed on this system
    # Using regular PostgreSQL tables instead
    
    # Note: Enum types are created automatically by SQLAlchemy when using postgresql.ENUM() in table definitions
    # No need to manually create them
    
    # 1. Create budgets table (no foreign keys, can be created first)
    op.create_table(
        'budgets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('budget_type', postgresql.ENUM('monthly', 'quarterly', 'annual', 'custom', name='budgettype'), nullable=False),
        sa.Column('amount', sa.DECIMAL(12, 2), nullable=False),
        sa.Column('currency', sa.String(10), server_default='USD'),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('alert_thresholds', postgresql.JSONB(), server_default='{"warning": 80, "critical": 95}'),
        sa.Column('filters', postgresql.JSONB(), server_default='{}'),
        sa.Column('current_spend', sa.DECIMAL(12, 2), server_default='0'),
        sa.Column('forecast_spend', sa.DECIMAL(12, 2)),
        sa.Column('status', postgresql.ENUM('active', 'exceeded', 'completed', name='budgetstatus'), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'))
    )
    op.create_index('idx_budgets_project', 'budgets', ['project_id'])
    op.create_index('idx_budgets_status', 'budgets', ['status'])
    
    # 2. Create cost_data table (regular table first, convert to hypertable after)
    op.create_table(
        'cost_data',
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('csp', sa.String(20), nullable=False),
        sa.Column('account_id', sa.String(255), nullable=False),
        sa.Column('service_name', sa.String(255), nullable=False),
        sa.Column('resource_id', sa.String(500)),
        sa.Column('region', sa.String(100)),
        sa.Column('usage_type', sa.String(255)),
        sa.Column('cost', sa.DECIMAL(12, 4), nullable=False),
        sa.Column('currency', sa.String(10), server_default='USD'),
        sa.Column('tags', postgresql.JSONB(), server_default='{}'),
        sa.Column('cost_metadata', postgresql.JSONB(), server_default='{}'),
        sa.PrimaryKeyConstraint('timestamp', 'id'),
        sa.CheckConstraint("csp IN ('aws', 'azure', 'gcp')", name='check_csp_valid')
    )
    
    # Note: If TimescaleDB is installed in the future, run:
    # SELECT create_hypertable('cost_data', 'timestamp', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);
    
    # Create indexes on cost_data
    op.create_index('idx_cost_data_project', 'cost_data', ['project_id'])
    op.create_index('idx_cost_data_csp', 'cost_data', ['csp'])
    op.create_index('idx_cost_data_service', 'cost_data', ['service_name'])
    op.create_index('idx_cost_data_project_time', 'cost_data', ['project_id', 'timestamp'])
    op.create_index('idx_cost_data_service_time', 'cost_data', ['service_name', 'timestamp'])
    op.execute("CREATE INDEX idx_cost_data_tags ON cost_data USING GIN(tags);")
    
    # 3. Create optimization_recommendations table
    op.create_table(
        'optimization_recommendations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('recommendation_type', postgresql.ENUM(
            'right-sizing', 'reserved-instance', 'savings-plan', 'storage-optimization',
            'idle-resource', 'underutilized-resource', 'reserved-capacity',
            name='recommendationtype'
        ), nullable=False),
        sa.Column('csp', sa.String(20), nullable=False),
        sa.Column('resource_id', sa.String(500), nullable=False),
        sa.Column('resource_type', sa.String(100), nullable=False),
        sa.Column('current_configuration', postgresql.JSONB(), server_default='{}'),
        sa.Column('recommended_configuration', postgresql.JSONB(), server_default='{}'),
        sa.Column('current_monthly_cost', sa.DECIMAL(12, 2), nullable=False),
        sa.Column('estimated_monthly_cost', sa.DECIMAL(12, 2), nullable=False),
        sa.Column('monthly_savings', sa.DECIMAL(12, 2), nullable=False),
        sa.Column('annual_savings', sa.DECIMAL(12, 2), nullable=False),
        sa.Column('confidence_score', sa.DECIMAL(3, 2)),
        sa.Column('implementation_effort', postgresql.ENUM('low', 'medium', 'high', name='effortlevel')),
        sa.Column('risk_level', postgresql.ENUM('low', 'medium', 'high', name='risklevel')),
        sa.Column('status', postgresql.ENUM('pending', 'approved', 'rejected', 'implemented', 'expired', name='recommendationstatus'), nullable=False, server_default='pending'),
        sa.Column('expires_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.CheckConstraint("confidence_score >= 0 AND confidence_score <= 1", name='check_confidence_score')
    )
    op.create_index('idx_recommendations_project', 'optimization_recommendations', ['project_id'])
    op.create_index('idx_recommendations_type', 'optimization_recommendations', ['recommendation_type'])
    op.create_index('idx_recommendations_status', 'optimization_recommendations', ['status'])
    
    # 4. Create anomaly_alerts table (has FK to budgets)
    op.create_table(
        'anomaly_alerts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('budget_id', postgresql.UUID(as_uuid=True)),
        sa.Column('alert_type', postgresql.ENUM('spike', 'trend', 'forecast-breach', 'budget-breach', name='anomalyalerttype'), nullable=False),
        sa.Column('csp', sa.String(20), nullable=False),
        sa.Column('service_name', sa.String(255)),
        sa.Column('resource_id', sa.String(500)),
        sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('baseline_cost', sa.DECIMAL(12, 2), nullable=False),
        sa.Column('actual_cost', sa.DECIMAL(12, 2), nullable=False),
        sa.Column('deviation_percentage', sa.DECIMAL(5, 2), nullable=False),
        sa.Column('severity', postgresql.ENUM('info', 'warning', 'critical', name='severity'), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('root_cause_analysis', postgresql.JSONB(), server_default='{}'),
        sa.Column('status', postgresql.ENUM('open', 'acknowledged', 'resolved', 'false-positive', name='alertstatus'), nullable=False, server_default='open'),
        sa.Column('acknowledged_by', sa.String(255)),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True)),
        sa.Column('resolved_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['budget_id'], ['budgets.id'], ondelete='SET NULL')
    )
    op.create_index('idx_anomaly_alerts_project', 'anomaly_alerts', ['project_id'])
    op.create_index('idx_anomaly_alerts_status', 'anomaly_alerts', ['status'])
    op.create_index('idx_anomaly_alerts_detected', 'anomaly_alerts', ['detected_at'])
    
    # 5. Create cost_allocation_rules table
    op.create_table(
        'cost_allocation_rules',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('rule_type', postgresql.ENUM('tag-based', 'service-based', 'account-based', 'custom', name='allocationruletype'), nullable=False),
        sa.Column('allocation_logic', postgresql.JSONB(), nullable=False),
        sa.Column('business_units', postgresql.JSONB(), server_default='[]'),
        sa.Column('enabled', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'))
    )
    op.create_index('idx_allocation_rules_project', 'cost_allocation_rules', ['project_id'])


def downgrade() -> None:
    """Drop all tables and enums"""
    
    # Drop tables in reverse order (respecting foreign keys)
    op.drop_table('cost_allocation_rules')
    op.drop_table('anomaly_alerts')
    op.drop_table('optimization_recommendations')
    op.drop_table('cost_data')
    op.drop_table('budgets')
    
    # Drop enums
    op.execute("DROP TYPE IF EXISTS allocationruletype CASCADE;")
    op.execute("DROP TYPE IF EXISTS alertstatus CASCADE;")
    op.execute("DROP TYPE IF EXISTS severity CASCADE;")
    op.execute("DROP TYPE IF EXISTS anomalyalerttype CASCADE;")
    op.execute("DROP TYPE IF EXISTS risklevel CASCADE;")
    op.execute("DROP TYPE IF EXISTS effortlevel CASCADE;")
    op.execute("DROP TYPE IF EXISTS recommendationstatus CASCADE;")
    op.execute("DROP TYPE IF EXISTS recommendationtype CASCADE;")
    op.execute("DROP TYPE IF EXISTS budgetstatus CASCADE;")
    op.execute("DROP TYPE IF EXISTS budgettype CASCADE;")
