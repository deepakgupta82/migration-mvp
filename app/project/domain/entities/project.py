"""Project domain entity."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional
import uuid

from ....common.exceptions import ValidationError, InvalidStateTransitionError


class ProjectStatus(Enum):
    """Project status enumeration."""
    DRAFT = "draft"
    ACTIVE = "active"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


@dataclass
class Project:
    """
    Project domain entity representing a migration assessment project.
    
    Contains all business logic and rules for project management.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    client_id: str = ""
    status: ProjectStatus = ProjectStatus.DRAFT
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = ""
    assigned_to: Optional[str] = None
    estimated_duration_days: Optional[int] = None
    actual_duration_days: Optional[int] = None
    budget: Optional[float] = None
    tags: List[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate entity after initialization."""
        self.validate()
    
    def validate(self) -> None:
        """
        Validate the project entity.
        
        Raises:
            ValidationError: If validation fails
        """
        if not self.name or not self.name.strip():
            raise ValidationError("Project name is required", field_name="name")
        
        if len(self.name) > 200:
            raise ValidationError(
                "Project name must be 200 characters or less", 
                field_name="name",
                field_value=self.name
            )
        
        if not self.client_id or not self.client_id.strip():
            raise ValidationError("Client ID is required", field_name="client_id")
        
        if not self.created_by or not self.created_by.strip():
            raise ValidationError("Created by is required", field_name="created_by")
        
        if self.estimated_duration_days is not None and self.estimated_duration_days <= 0:
            raise ValidationError(
                "Estimated duration must be positive",
                field_name="estimated_duration_days",
                field_value=self.estimated_duration_days
            )
        
        if self.budget is not None and self.budget < 0:
            raise ValidationError(
                "Budget cannot be negative",
                field_name="budget", 
                field_value=self.budget
            )
    
    def update_name(self, new_name: str) -> None:
        """
        Update project name.
        
        Args:
            new_name: New project name
            
        Raises:
            ValidationError: If name is invalid
        """
        if not new_name or not new_name.strip():
            raise ValidationError("Project name cannot be empty")
        
        if len(new_name) > 200:
            raise ValidationError("Project name must be 200 characters or less")
        
        self.name = new_name.strip()
        self.updated_at = datetime.utcnow()
    
    def update_description(self, new_description: str) -> None:
        """
        Update project description.
        
        Args:
            new_description: New project description
        """
        self.description = new_description
        self.updated_at = datetime.utcnow()
    
    def assign_to(self, user_id: str) -> None:
        """
        Assign project to a user.
        
        Args:
            user_id: ID of the user to assign to
            
        Raises:
            ValidationError: If user_id is invalid
            InvalidStateTransitionError: If project cannot be assigned
        """
        if not user_id or not user_id.strip():
            raise ValidationError("User ID is required")
        
        if self.status in [ProjectStatus.COMPLETED, ProjectStatus.CANCELLED, ProjectStatus.ARCHIVED]:
            raise InvalidStateTransitionError(
                entity_type="Project",
                entity_id=self.id,
                current_state=self.status.value,
                target_state="assigned"
            )
        
        self.assigned_to = user_id
        self.updated_at = datetime.utcnow()
    
    def start(self) -> None:
        """
        Start the project.
        
        Raises:
            InvalidStateTransitionError: If project cannot be started
        """
        if self.status not in [ProjectStatus.DRAFT, ProjectStatus.ACTIVE]:
            raise InvalidStateTransitionError(
                entity_type="Project",
                entity_id=self.id,
                current_state=self.status.value,
                target_state=ProjectStatus.IN_PROGRESS.value
            )
        
        self.status = ProjectStatus.IN_PROGRESS
        self.updated_at = datetime.utcnow()
    
    def complete(self) -> None:
        """
        Mark project as completed.
        
        Raises:
            InvalidStateTransitionError: If project cannot be completed
        """
        if self.status != ProjectStatus.IN_PROGRESS:
            raise InvalidStateTransitionError(
                entity_type="Project",
                entity_id=self.id,
                current_state=self.status.value,
                target_state=ProjectStatus.COMPLETED.value
            )
        
        self.status = ProjectStatus.COMPLETED
        self.actual_duration_days = (datetime.utcnow() - self.created_at).days
        self.updated_at = datetime.utcnow()
    
    def cancel(self, reason: Optional[str] = None) -> None:
        """
        Cancel the project.
        
        Args:
            reason: Optional cancellation reason
            
        Raises:
            InvalidStateTransitionError: If project cannot be cancelled
        """
        if self.status in [ProjectStatus.COMPLETED, ProjectStatus.ARCHIVED]:
            raise InvalidStateTransitionError(
                entity_type="Project",
                entity_id=self.id,
                current_state=self.status.value,
                target_state=ProjectStatus.CANCELLED.value
            )
        
        self.status = ProjectStatus.CANCELLED
        if reason:
            self.metadata["cancellation_reason"] = reason
        self.updated_at = datetime.utcnow()
    
    def archive(self) -> None:
        """
        Archive the project.
        
        Raises:
            InvalidStateTransitionError: If project cannot be archived
        """
        if self.status not in [ProjectStatus.COMPLETED, ProjectStatus.CANCELLED]:
            raise InvalidStateTransitionError(
                entity_type="Project",
                entity_id=self.id,
                current_state=self.status.value,
                target_state=ProjectStatus.ARCHIVED.value
            )
        
        self.status = ProjectStatus.ARCHIVED
        self.updated_at = datetime.utcnow()
    
    def add_tag(self, tag: str) -> None:
        """
        Add a tag to the project.
        
        Args:
            tag: Tag to add
        """
        if tag and tag not in self.tags:
            self.tags.append(tag)
            self.updated_at = datetime.utcnow()
    
    def remove_tag(self, tag: str) -> None:
        """
        Remove a tag from the project.
        
        Args:
            tag: Tag to remove
        """
        if tag in self.tags:
            self.tags.remove(tag)
            self.updated_at = datetime.utcnow()
    
    def update_metadata(self, key: str, value: any) -> None:
        """
        Update project metadata.
        
        Args:
            key: Metadata key
            value: Metadata value
        """
        self.metadata[key] = value
        self.updated_at = datetime.utcnow()
    
    def is_active(self) -> bool:
        """Check if project is in an active state."""
        return self.status in [ProjectStatus.ACTIVE, ProjectStatus.IN_PROGRESS]
    
    def can_be_modified(self) -> bool:
        """Check if project can be modified."""
        return self.status not in [ProjectStatus.COMPLETED, ProjectStatus.CANCELLED, ProjectStatus.ARCHIVED]
