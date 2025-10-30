"""SQLAlchemy ORM models for IAC governance service."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Column, String, DateTime, Text, Integer, Boolean,
    JSON, ForeignKey, Index, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

Base = declarative_base()


class PolicySeverity(str, enum.Enum):
    """Policy violation severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ScanStatus(str, enum.Enum):
    """Policy scan status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RemediationStatus(str, enum.Enum):
    """Remediation action status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PolicyTemplate(Base):
    """
    Policy Template Model
    Stores reusable policy definitions for IAC compliance.
    """
    __tablename__ = "policy_templates"
    
    # Primary key
    template_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Template identification
    template_name = Column(String(255), nullable=False, index=True)
    template_description = Column(Text)
    policy_category = Column(String(100), nullable=False, index=True)  # security, cost, compliance, etc.
    severity = Column(SQLEnum(PolicySeverity), nullable=False, default=PolicySeverity.MEDIUM, index=True)
    
    # Policy engine
    engine_type = Column(String(50), nullable=False)  # opa, sentinel, custom
    policy_code = Column(Text, nullable=False)  # OPA Rego, Sentinel, etc.
    
    # IAC frameworks supported
    supported_frameworks = Column(JSON, nullable=False)  # ["terraform", "cloudformation", "arm", "pulumi"]
    
    # Cloud providers
    cloud_providers = Column(JSON, nullable=False)  # ["aws", "azure", "gcp", "multi-cloud"]
    
    # Policy configuration
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    is_blocking = Column(Boolean, default=False, nullable=False)  # Block deployment if violated
    auto_remediate = Column(Boolean, default=False, nullable=False)  # Auto-fix violations
    
    # Metadata
    tags = Column(JSON, default=list)  # Policy tags for organization
    policy_metadata = Column(JSON, default=dict)  # Additional metadata
    
    # Audit fields
    created_by = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    scans = relationship("PolicyScan", back_populates="template", cascade="all, delete-orphan")
    
    # Indexes for query optimization
    __table_args__ = (
        Index("ix_policy_templates_category_severity", "policy_category", "severity"),
        Index("ix_policy_templates_active", "is_active", "is_blocking"),
    )


class PolicyScan(Base):
    """
    Policy Scan Model
    Tracks IAC policy scan executions.
    """
    __tablename__ = "policy_scans"
    
    # Primary key
    scan_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Foreign keys
    template_id = Column(PGUUID(as_uuid=True), ForeignKey("policy_templates.template_id", ondelete="CASCADE"), nullable=True)
    project_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)  # Reference to project
    
    # Scan identification
    scan_name = Column(String(255), nullable=False)
    scan_description = Column(Text)
    
    # IAC source
    iac_framework = Column(String(50), nullable=False)  # terraform, cloudformation, arm, pulumi
    iac_version = Column(String(50))  # Framework version
    source_type = Column(String(50), nullable=False)  # repository, file, directory
    source_location = Column(Text, nullable=False)  # Git URL, file path, etc.
    source_branch = Column(String(100))  # For Git repos
    source_commit = Column(String(100))  # For Git repos
    
    # Scan execution
    status = Column(SQLEnum(ScanStatus), nullable=False, default=ScanStatus.PENDING, index=True)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    duration_seconds = Column(Integer)  # Scan duration
    
    # Scan results
    total_resources = Column(Integer, default=0)  # Total IAC resources scanned
    passed_checks = Column(Integer, default=0)
    failed_checks = Column(Integer, default=0)
    violations_critical = Column(Integer, default=0)
    violations_high = Column(Integer, default=0)
    violations_medium = Column(Integer, default=0)
    violations_low = Column(Integer, default=0)
    violations_info = Column(Integer, default=0)
    
    # Error tracking
    error_message = Column(Text)
    error_details = Column(JSON)
    
    # Scan configuration
    scan_config = Column(JSON, default=dict)  # Custom scan settings
    correlation_id = Column(String(100), index=True)  # For distributed tracing
    
    # Metadata
    scan_metadata = Column(JSON, default=dict)
    
    # Audit fields
    triggered_by = Column(String(255))  # User or service that triggered scan
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    template = relationship("PolicyTemplate", back_populates="scans")
    violations = relationship("PolicyViolation", back_populates="scan", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index("ix_policy_scans_project_status", "project_id", "status"),
        Index("ix_policy_scans_correlation", "correlation_id"),
        Index("ix_policy_scans_created", "created_at"),
    )


class PolicyViolation(Base):
    """
    Policy Violation Model
    Tracks individual policy violations found during scans.
    """
    __tablename__ = "policy_violations"
    
    # Primary key
    violation_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Foreign keys
    scan_id = Column(PGUUID(as_uuid=True), ForeignKey("policy_scans.scan_id", ondelete="CASCADE"), nullable=False, index=True)
    template_id = Column(PGUUID(as_uuid=True), ForeignKey("policy_templates.template_id", ondelete="SET NULL"), nullable=True)
    
    # Violation identification
    violation_rule = Column(String(255), nullable=False, index=True)  # Policy rule violated
    severity = Column(SQLEnum(PolicySeverity), nullable=False, index=True)
    
    # Resource information
    resource_type = Column(String(100), nullable=False)  # aws_s3_bucket, azurerm_storage_account, etc.
    resource_name = Column(String(255), nullable=False)
    resource_identifier = Column(Text, nullable=False)  # Full resource identifier in IAC
    file_path = Column(Text)  # File containing the resource
    line_number = Column(Integer)  # Line number in file
    
    # Violation details
    violation_message = Column(Text, nullable=False)  # Human-readable description
    violation_details = Column(JSON)  # Detailed violation information
    recommended_fix = Column(Text)  # Suggested remediation
    
    # Status
    is_resolved = Column(Boolean, default=False, nullable=False, index=True)
    resolved_at = Column(DateTime)
    resolved_by = Column(String(255))
    resolution_notes = Column(Text)
    
    # Suppression
    is_suppressed = Column(Boolean, default=False, nullable=False)
    suppressed_reason = Column(Text)
    suppressed_until = Column(DateTime)  # Temporary suppression
    
    # Metadata
    violation_metadata = Column(JSON, default=dict)
    
    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    scan = relationship("PolicyScan", back_populates="violations")
    template = relationship("PolicyTemplate")
    remediation_actions = relationship("RemediationAction", back_populates="violation", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index("ix_policy_violations_scan_severity", "scan_id", "severity"),
        Index("ix_policy_violations_rule", "violation_rule"),
        Index("ix_policy_violations_resolved", "is_resolved", "is_suppressed"),
    )


class RemediationAction(Base):
    """
    Remediation Action Model
    Tracks automated and manual remediation actions for policy violations.
    """
    __tablename__ = "remediation_actions"
    
    # Primary key
    action_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Foreign keys
    violation_id = Column(PGUUID(as_uuid=True), ForeignKey("policy_violations.violation_id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Action identification
    action_type = Column(String(100), nullable=False)  # auto_fix, manual_fix, suppress, ignore
    action_name = Column(String(255), nullable=False)
    action_description = Column(Text)
    
    # Remediation details
    remediation_method = Column(String(100), nullable=False)  # terraform_apply, manual_edit, api_call, etc.
    remediation_code = Column(Text)  # Code/script to apply fix
    remediation_params = Column(JSON, default=dict)  # Parameters for remediation
    
    # Execution
    status = Column(SQLEnum(RemediationStatus), nullable=False, default=RemediationStatus.PENDING, index=True)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    duration_seconds = Column(Integer)
    
    # Results
    is_successful = Column(Boolean)
    result = Column(JSON)  # Remediation execution result
    error_message = Column(Text)
    
    # Approval workflow
    requires_approval = Column(Boolean, default=False, nullable=False)
    approved_by = Column(String(255))
    approved_at = Column(DateTime)
    approval_notes = Column(Text)
    
    # Metadata
    action_metadata = Column(JSON, default=dict)
    correlation_id = Column(String(100), index=True)
    
    # Audit fields
    triggered_by = Column(String(255))  # User or service that triggered action
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    violation = relationship("PolicyViolation", back_populates="remediation_actions")
    
    # Indexes
    __table_args__ = (
        Index("ix_remediation_actions_violation_status", "violation_id", "status"),
        Index("ix_remediation_actions_correlation", "correlation_id"),
        Index("ix_remediation_actions_approval", "requires_approval", "approved_at"),
    )


class TerraformExecutionStatus(str, enum.Enum):
    """Terraform execution status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TerraformExecutionType(str, enum.Enum):
    """Terraform execution operation type."""
    INIT = "init"
    PLAN = "plan"
    APPLY = "apply"
    DESTROY = "destroy"
    VALIDATE = "validate"


class TerraformExecution(Base):
    """
    Terraform Execution Model
    Tracks Terraform operations (plan, apply, destroy, etc.) for audit and history.
    """
    __tablename__ = "terraform_executions"
    
    # Primary Key
    execution_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Project and scan association
    project_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    scan_id = Column(PGUUID(as_uuid=True), ForeignKey("policy_scans.scan_id", ondelete="SET NULL"))
    
    # Execution details
    execution_type = Column(SQLEnum(TerraformExecutionType), nullable=False, index=True)
    status = Column(SQLEnum(TerraformExecutionStatus), nullable=False, default=TerraformExecutionStatus.PENDING, index=True)
    
    # Workspace details
    workspace_path = Column(Text, nullable=False)
    workspace_name = Column(String(255))
    
    # Execution configuration
    var_file = Column(Text)  # Path to .tfvars file
    variables = Column(JSON, default=dict)  # Variable overrides
    backend_config = Column(JSON, default=dict)  # Backend configuration
    target_resources = Column(JSON, default=list)  # List of target resource addresses
    auto_approve = Column(Boolean, default=False)
    
    # Execution results
    plan_id = Column(String(255))  # Unique plan identifier
    changes_summary = Column(JSON, default=dict)  # {add: N, change: N, delete: N}
    resources_affected = Column(JSON, default=list)  # List of resource addresses
    
    # Timing
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    duration_seconds = Column(Integer)
    
    # Output and errors
    output_text = Column(Text)  # Full Terraform output
    error_message = Column(Text)
    error_details = Column(JSON)
    
    # Validation results (for validate operations)
    is_valid = Column(Boolean)
    diagnostics = Column(JSON, default=list)  # Validation errors/warnings
    error_count = Column(Integer, default=0)
    warning_count = Column(Integer, default=0)
    
    # Metadata
    execution_metadata = Column(JSON, default=dict)
    correlation_id = Column(String(100), index=True)
    
    # Audit fields
    triggered_by = Column(String(255))  # User or service that triggered execution
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    scan = relationship("PolicyScan", back_populates="terraform_executions")
    resources = relationship("TerraformResource", back_populates="execution", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index("ix_terraform_executions_project_id", "project_id"),
        Index("ix_terraform_executions_status", "status"),
        Index("ix_terraform_executions_type", "execution_type"),
        Index("ix_terraform_executions_project_status", "project_id", "status"),
        Index("ix_terraform_executions_correlation", "correlation_id"),
        Index("ix_terraform_executions_created_at", "created_at"),
    )


class TerraformResource(Base):
    """
    Terraform Resource Model
    Tracks individual resources managed by Terraform for detailed change tracking.
    """
    __tablename__ = "terraform_resources"
    
    # Primary Key
    resource_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Foreign Keys
    execution_id = Column(PGUUID(as_uuid=True), ForeignKey("terraform_executions.execution_id", ondelete="CASCADE"), nullable=False)
    
    # Resource identification
    resource_address = Column(Text, nullable=False)  # Full Terraform address (e.g., aws_instance.example)
    resource_type = Column(String(255), nullable=False, index=True)  # Resource type (e.g., aws_instance)
    resource_name = Column(String(255), nullable=False)  # Resource name (e.g., example)
    module_path = Column(Text)  # Module path if resource is in a module
    
    # Change tracking
    action = Column(String(50))  # create, update, delete, read, no-op
    change_details = Column(JSON, default=dict)  # Detailed changes from plan
    
    # Resource state
    previous_state = Column(JSON)  # State before change
    new_state = Column(JSON)  # State after change
    
    # Provider info
    provider = Column(String(100))  # Provider name (e.g., aws, azurerm, google)
    
    # Metadata
    resource_metadata = Column(JSON, default=dict)
    
    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    execution = relationship("TerraformExecution", back_populates="resources")
    
    # Indexes
    __table_args__ = (
        Index("ix_terraform_resources_execution_id", "execution_id"),
        Index("ix_terraform_resources_type", "resource_type"),
        Index("ix_terraform_resources_action", "action"),
        Index("ix_terraform_resources_address", "resource_address"),
    )


# Update PolicyScan to add terraform_executions relationship
PolicyScan.terraform_executions = relationship(
    "TerraformExecution",
    back_populates="scan",
    cascade="all, delete-orphan"
)
