"""Assessment domain entity."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
import uuid

from ....common.exceptions import ValidationError, InvalidStateTransitionError


class AssessmentStatus(Enum):
    """Assessment status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    ANALYZING = "analyzing"
    GENERATING_REPORT = "generating_report"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AssessmentType(Enum):
    """Assessment type enumeration."""
    INFRASTRUCTURE = "infrastructure"
    APPLICATION = "application"
    DATA = "data"
    SECURITY = "security"
    COMPLIANCE = "compliance"
    FULL_STACK = "full_stack"


@dataclass
class AssessmentResult:
    """Assessment result data structure."""
    migration_strategy: str = ""
    estimated_cost: Optional[float] = None
    estimated_duration_weeks: Optional[int] = None
    risk_level: str = "medium"  # low, medium, high, critical
    recommendations: List[str] = field(default_factory=list)
    technical_debt_score: Optional[float] = None
    cloud_readiness_score: Optional[float] = None
    complexity_score: Optional[float] = None
    dependencies: List[Dict[str, Any]] = field(default_factory=list)
    architecture_patterns: List[str] = field(default_factory=list)
    technology_stack: List[str] = field(default_factory=list)


@dataclass
class Assessment:
    """
    Assessment domain entity representing a migration assessment.
    
    Contains all business logic and rules for assessment management.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str = ""
    name: str = ""
    type: AssessmentType = AssessmentType.INFRASTRUCTURE
    status: AssessmentStatus = AssessmentStatus.PENDING
    description: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_by: str = ""
    assigned_to: Optional[str] = None
    
    # Assessment configuration
    target_cloud_provider: str = ""  # aws, azure, gcp
    source_environment: str = ""
    assessment_scope: List[str] = field(default_factory=list)
    
    # Document and artifact tracking
    uploaded_documents: List[str] = field(default_factory=list)
    processed_documents: List[str] = field(default_factory=list)
    generated_artifacts: List[str] = field(default_factory=list)
    
    # Assessment results
    result: Optional[AssessmentResult] = None
    
    # Progress tracking
    progress_percentage: float = 0.0
    current_phase: str = ""
    phases_completed: List[str] = field(default_factory=list)
    
    # Error tracking
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate entity after initialization."""
        self.validate()
    
    def validate(self) -> None:
        """
        Validate the assessment entity.
        
        Raises:
            ValidationError: If validation fails
        """
        if not self.project_id or not self.project_id.strip():
            raise ValidationError("Project ID is required", field_name="project_id")
        
        if not self.name or not self.name.strip():
            raise ValidationError("Assessment name is required", field_name="name")
        
        if len(self.name) > 200:
            raise ValidationError(
                "Assessment name must be 200 characters or less",
                field_name="name",
                field_value=self.name
            )
        
        if not self.created_by or not self.created_by.strip():
            raise ValidationError("Created by is required", field_name="created_by")
        
        if self.progress_percentage < 0 or self.progress_percentage > 100:
            raise ValidationError(
                "Progress percentage must be between 0 and 100",
                field_name="progress_percentage",
                field_value=self.progress_percentage
            )
    
    def start(self, assigned_to: Optional[str] = None) -> None:
        """
        Start the assessment.
        
        Args:
            assigned_to: Optional user to assign the assessment to
            
        Raises:
            InvalidStateTransitionError: If assessment cannot be started
        """
        if self.status != AssessmentStatus.PENDING:
            raise InvalidStateTransitionError(
                entity_type="Assessment",
                entity_id=self.id,
                current_state=self.status.value,
                target_state=AssessmentStatus.IN_PROGRESS.value
            )
        
        self.status = AssessmentStatus.IN_PROGRESS
        self.started_at = datetime.utcnow()
        self.current_phase = "document_processing"
        self.progress_percentage = 5.0
        
        if assigned_to:
            self.assigned_to = assigned_to
        
        self.updated_at = datetime.utcnow()
    
    def update_progress(self, percentage: float, phase: str) -> None:
        """
        Update assessment progress.
        
        Args:
            percentage: Progress percentage (0-100)
            phase: Current phase name
            
        Raises:
            ValidationError: If percentage is invalid
        """
        if percentage < 0 or percentage > 100:
            raise ValidationError("Progress percentage must be between 0 and 100")
        
        self.progress_percentage = percentage
        self.current_phase = phase
        self.updated_at = datetime.utcnow()
    
    def complete_phase(self, phase: str) -> None:
        """
        Mark a phase as completed.
        
        Args:
            phase: Phase name to mark as completed
        """
        if phase not in self.phases_completed:
            self.phases_completed.append(phase)
            self.updated_at = datetime.utcnow()
    
    def add_document(self, document_id: str) -> None:
        """
        Add an uploaded document.
        
        Args:
            document_id: Document identifier
        """
        if document_id not in self.uploaded_documents:
            self.uploaded_documents.append(document_id)
            self.updated_at = datetime.utcnow()
    
    def mark_document_processed(self, document_id: str) -> None:
        """
        Mark a document as processed.
        
        Args:
            document_id: Document identifier
        """
        if document_id not in self.processed_documents:
            self.processed_documents.append(document_id)
            self.updated_at = datetime.utcnow()
    
    def add_generated_artifact(self, artifact_id: str) -> None:
        """
        Add a generated artifact.
        
        Args:
            artifact_id: Artifact identifier
        """
        if artifact_id not in self.generated_artifacts:
            self.generated_artifacts.append(artifact_id)
            self.updated_at = datetime.utcnow()
    
    def set_analyzing(self) -> None:
        """
        Set status to analyzing.
        
        Raises:
            InvalidStateTransitionError: If invalid transition
        """
        if self.status != AssessmentStatus.IN_PROGRESS:
            raise InvalidStateTransitionError(
                entity_type="Assessment",
                entity_id=self.id,
                current_state=self.status.value,
                target_state=AssessmentStatus.ANALYZING.value
            )
        
        self.status = AssessmentStatus.ANALYZING
        self.current_phase = "ai_analysis"
        self.progress_percentage = 60.0
        self.updated_at = datetime.utcnow()
    
    def set_generating_report(self) -> None:
        """
        Set status to generating report.
        
        Raises:
            InvalidStateTransitionError: If invalid transition
        """
        if self.status != AssessmentStatus.ANALYZING:
            raise InvalidStateTransitionError(
                entity_type="Assessment",
                entity_id=self.id,
                current_state=self.status.value,
                target_state=AssessmentStatus.GENERATING_REPORT.value
            )
        
        self.status = AssessmentStatus.GENERATING_REPORT
        self.current_phase = "report_generation"
        self.progress_percentage = 85.0
        self.updated_at = datetime.utcnow()
    
    def complete(self, result: AssessmentResult) -> None:
        """
        Complete the assessment with results.
        
        Args:
            result: Assessment results
            
        Raises:
            InvalidStateTransitionError: If assessment cannot be completed
        """
        if self.status not in [AssessmentStatus.ANALYZING, AssessmentStatus.GENERATING_REPORT]:
            raise InvalidStateTransitionError(
                entity_type="Assessment",
                entity_id=self.id,
                current_state=self.status.value,
                target_state=AssessmentStatus.COMPLETED.value
            )
        
        self.status = AssessmentStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.result = result
        self.progress_percentage = 100.0
        self.current_phase = "completed"
        self.error_message = None
        self.updated_at = datetime.utcnow()
    
    def fail(self, error_message: str) -> None:
        """
        Mark assessment as failed.
        
        Args:
            error_message: Error description
        """
        self.status = AssessmentStatus.FAILED
        self.error_message = error_message
        self.updated_at = datetime.utcnow()
    
    def cancel(self, reason: Optional[str] = None) -> None:
        """
        Cancel the assessment.
        
        Args:
            reason: Optional cancellation reason
        """
        if self.status == AssessmentStatus.COMPLETED:
            raise InvalidStateTransitionError(
                entity_type="Assessment",
                entity_id=self.id,
                current_state=self.status.value,
                target_state=AssessmentStatus.CANCELLED.value
            )
        
        self.status = AssessmentStatus.CANCELLED
        if reason:
            self.metadata["cancellation_reason"] = reason
        self.updated_at = datetime.utcnow()
    
    def retry(self) -> None:
        """
        Retry a failed assessment.
        
        Raises:
            InvalidStateTransitionError: If assessment cannot be retried
            ValidationError: If max retries exceeded
        """
        if self.status != AssessmentStatus.FAILED:
            raise InvalidStateTransitionError(
                entity_type="Assessment",
                entity_id=self.id,
                current_state=self.status.value,
                target_state=AssessmentStatus.PENDING.value
            )
        
        if self.retry_count >= self.max_retries:
            raise ValidationError(
                f"Maximum retry attempts ({self.max_retries}) exceeded",
                field_name="retry_count",
                field_value=self.retry_count
            )
        
        self.status = AssessmentStatus.PENDING
        self.retry_count += 1
        self.error_message = None
        self.progress_percentage = 0.0
        self.current_phase = ""
        self.updated_at = datetime.utcnow()
    
    def is_active(self) -> bool:
        """Check if assessment is in an active state."""
        return self.status in [
            AssessmentStatus.PENDING,
            AssessmentStatus.IN_PROGRESS,
            AssessmentStatus.ANALYZING,
            AssessmentStatus.GENERATING_REPORT
        ]
    
    def is_completed(self) -> bool:
        """Check if assessment is completed."""
        return self.status == AssessmentStatus.COMPLETED
    
    def can_be_cancelled(self) -> bool:
        """Check if assessment can be cancelled."""
        return self.status != AssessmentStatus.COMPLETED
