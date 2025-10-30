"""
SQLAlchemy ORM models for FinOps Optimization Service
"""
from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, ForeignKey, Text, Enum as SQLEnum, DECIMAL, Date, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.core.database import Base


class BudgetType(str, enum.Enum):
    """Budget period types"""
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    CUSTOM = "custom"


class BudgetStatus(str, enum.Enum):
    """Budget status"""
    ACTIVE = "active"
    EXCEEDED = "exceeded"
    COMPLETED = "completed"


class RecommendationType(str, enum.Enum):
    """Optimization recommendation types"""
    RIGHT_SIZING = "right-sizing"
    RESERVED_INSTANCE = "reserved-instance"
    SAVINGS_PLAN = "savings-plan"
    STORAGE_OPTIMIZATION = "storage-optimization"
    IDLE_RESOURCE = "idle-resource"
    UNDERUTILIZED_RESOURCE = "underutilized-resource"
    RESERVED_CAPACITY = "reserved-capacity"


class RecommendationStatus(str, enum.Enum):
    """Recommendation status"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    IMPLEMENTED = "implemented"
    EXPIRED = "expired"


class EffortLevel(str, enum.Enum):
    """Implementation effort level"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskLevel(str, enum.Enum):
    """Risk level"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AnomalyAlertType(str, enum.Enum):
    """Anomaly alert types"""
    SPIKE = "spike"
    TREND = "trend"
    FORECAST_BREACH = "forecast-breach"
    BUDGET_BREACH = "budget-breach"


class Severity(str, enum.Enum):
    """Severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(str, enum.Enum):
    """Alert status"""
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false-positive"


class AllocationRuleType(str, enum.Enum):
    """Cost allocation rule types"""
    TAG_BASED = "tag-based"
    SERVICE_BASED = "service-based"
    ACCOUNT_BASED = "account-based"
    CUSTOM = "custom"


# Note: cost_data table will be created as TimescaleDB hypertable in migration
class CostData(Base):
    """
    Time-series cost data (TimescaleDB hypertable)
    Stores granular cost data from multiple cloud providers
    """
    __tablename__ = "cost_data"
    
    # Primary key components
    timestamp = Column(DateTime(timezone=True), nullable=False, primary_key=True)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Core fields
    project_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    csp = Column(String(20), nullable=False, index=True)  # aws, azure, gcp
    account_id = Column(String(255), nullable=False)
    service_name = Column(String(255), nullable=False, index=True)
    resource_id = Column(String(500))
    region = Column(String(100))
    usage_type = Column(String(255))
    
    # Cost metrics
    cost = Column(DECIMAL(12, 4), nullable=False)
    currency = Column(String(10), default="USD")
    
    # Metadata
    tags = Column(JSONB, default={})
    cost_metadata = Column(JSONB, default={})
    
    __table_args__ = (
        Index('idx_cost_data_project_time', 'project_id', 'timestamp'),
        Index('idx_cost_data_service_time', 'service_name', 'timestamp'),
        Index('idx_cost_data_tags', 'tags', postgresql_using='gin'),
        CheckConstraint("csp IN ('aws', 'azure', 'gcp')", name='check_csp_valid'),
    )


class Budget(Base):
    """Budget definitions and tracking"""
    __tablename__ = "budgets"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Budget configuration
    name = Column(String(255), nullable=False)
    description = Column(Text)
    budget_type = Column(SQLEnum(BudgetType), nullable=False)
    amount = Column(DECIMAL(12, 2), nullable=False)
    currency = Column(String(10), default="USD")
    
    # Period
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    
    # Alert configuration
    alert_thresholds = Column(JSONB, default={"warning": 80, "critical": 95})
    
    # Filters for budget scope
    filters = Column(JSONB, default={})  # {csp, service, tags}
    
    # Current tracking
    current_spend = Column(DECIMAL(12, 2), default=0)
    forecast_spend = Column(DECIMAL(12, 2))
    status = Column(SQLEnum(BudgetStatus), nullable=False, default=BudgetStatus.ACTIVE)
    
    # Audit
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    anomaly_alerts = relationship("AnomalyAlert", back_populates="budget", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_budgets_status', 'status'),
    )


class OptimizationRecommendation(Base):
    """Cost optimization recommendations"""
    __tablename__ = "optimization_recommendations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Recommendation details
    recommendation_type = Column(SQLEnum(RecommendationType), nullable=False, index=True)
    csp = Column(String(20), nullable=False)
    resource_id = Column(String(500), nullable=False)
    resource_type = Column(String(100), nullable=False)
    
    # Configuration
    current_configuration = Column(JSONB, default={})
    recommended_configuration = Column(JSONB, default={})
    
    # Cost impact
    current_monthly_cost = Column(DECIMAL(12, 2), nullable=False)
    estimated_monthly_cost = Column(DECIMAL(12, 2), nullable=False)
    monthly_savings = Column(DECIMAL(12, 2), nullable=False)
    annual_savings = Column(DECIMAL(12, 2), nullable=False)
    
    # Metadata
    confidence_score = Column(DECIMAL(3, 2))  # 0.00 to 1.00
    implementation_effort = Column(SQLEnum(EffortLevel))
    risk_level = Column(SQLEnum(RiskLevel))
    
    # Status
    status = Column(SQLEnum(RecommendationStatus), nullable=False, default=RecommendationStatus.PENDING, index=True)
    expires_at = Column(DateTime(timezone=True))
    
    # Audit
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 1", name='check_confidence_score'),
    )


class AnomalyAlert(Base):
    """Cost anomaly alerts"""
    __tablename__ = "anomaly_alerts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    budget_id = Column(UUID(as_uuid=True), ForeignKey("budgets.id", ondelete="SET NULL"))
    
    # Alert details
    alert_type = Column(SQLEnum(AnomalyAlertType), nullable=False)
    csp = Column(String(20), nullable=False)
    service_name = Column(String(255))
    resource_id = Column(String(500))
    
    # Anomaly metrics
    detected_at = Column(DateTime(timezone=True), nullable=False, index=True)
    baseline_cost = Column(DECIMAL(12, 2), nullable=False)
    actual_cost = Column(DECIMAL(12, 2), nullable=False)
    deviation_percentage = Column(DECIMAL(5, 2), nullable=False)
    
    # Severity and message
    severity = Column(SQLEnum(Severity), nullable=False)
    message = Column(Text, nullable=False)
    root_cause_analysis = Column(JSONB, default={})
    
    # Status tracking
    status = Column(SQLEnum(AlertStatus), nullable=False, default=AlertStatus.OPEN, index=True)
    acknowledged_by = Column(String(255))
    acknowledged_at = Column(DateTime(timezone=True))
    resolved_at = Column(DateTime(timezone=True))
    
    # Audit
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    budget = relationship("Budget", back_populates="anomaly_alerts")


class CostAllocationRule(Base):
    """Cost allocation and chargeback rules"""
    __tablename__ = "cost_allocation_rules"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Rule configuration
    name = Column(String(255), nullable=False)
    description = Column(Text)
    rule_type = Column(SQLEnum(AllocationRuleType), nullable=False)
    
    # Allocation logic
    allocation_logic = Column(JSONB, nullable=False)  # {tag_key, mappings, etc.}
    business_units = Column(JSONB, default=[])
    
    # Status
    enabled = Column(Boolean, default=True)
    
    # Audit
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
