"""Project Data Transfer Objects."""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Any

from ...common.cqrs import DTO
from ..domain.entities import Project, ProjectStatus


@dataclass
class ProjectDTO(DTO):
    """Data Transfer Object for Project entity."""
    id: str
    name: str
    description: str
    client_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    created_by: str
    assigned_to: Optional[str]
    estimated_duration_days: Optional[int]
    actual_duration_days: Optional[int]
    budget: Optional[float]
    tags: List[str]
    metadata: Dict[str, Any]
    
    @classmethod
    def from_entity(cls, project: Project) -> 'ProjectDTO':
        """
        Create DTO from Project entity.
        
        Args:
            project: Project entity
            
        Returns:
            ProjectDTO instance
        """
        return cls(
            id=project.id,
            name=project.name,
            description=project.description,
            client_id=project.client_id,
            status=project.status.value,
            created_at=project.created_at,
            updated_at=project.updated_at,
            created_by=project.created_by,
            assigned_to=project.assigned_to,
            estimated_duration_days=project.estimated_duration_days,
            actual_duration_days=project.actual_duration_days,
            budget=project.budget,
            tags=project.tags.copy(),
            metadata=project.metadata.copy()
        )


@dataclass
class ProjectSummaryDTO(DTO):
    """Summary Data Transfer Object for Project entity."""
    id: str
    name: str
    client_id: str
    status: str
    created_at: datetime
    assigned_to: Optional[str]
    estimated_duration_days: Optional[int]
    budget: Optional[float]
    tags: List[str]
    
    @classmethod
    def from_entity(cls, project: Project) -> 'ProjectSummaryDTO':
        """
        Create summary DTO from Project entity.
        
        Args:
            project: Project entity
            
        Returns:
            ProjectSummaryDTO instance
        """
        return cls(
            id=project.id,
            name=project.name,
            client_id=project.client_id,
            status=project.status.value,
            created_at=project.created_at,
            assigned_to=project.assigned_to,
            estimated_duration_days=project.estimated_duration_days,
            budget=project.budget,
            tags=project.tags.copy()
        )


@dataclass
class ProjectStatsDTO(DTO):
    """Statistics Data Transfer Object for projects."""
    total_projects: int
    status_counts: Dict[str, int]
    total_budget: Optional[float]
    average_duration: Optional[float]
    active_projects: int
    completed_projects: int
    
    @classmethod
    def from_counts(
        cls,
        total: int,
        status_counts: Dict[ProjectStatus, int],
        total_budget: Optional[float] = None,
        average_duration: Optional[float] = None
    ) -> 'ProjectStatsDTO':
        """
        Create stats DTO from count data.
        
        Args:
            total: Total project count
            status_counts: Count by status
            total_budget: Total budget across all projects
            average_duration: Average project duration
            
        Returns:
            ProjectStatsDTO instance
        """
        # Convert enum keys to string values
        status_counts_str = {
            status.value: count for status, count in status_counts.items()
        }
        
        active_count = (
            status_counts.get(ProjectStatus.ACTIVE, 0) +
            status_counts.get(ProjectStatus.IN_PROGRESS, 0)
        )
        
        completed_count = status_counts.get(ProjectStatus.COMPLETED, 0)
        
        return cls(
            total_projects=total,
            status_counts=status_counts_str,
            total_budget=total_budget,
            average_duration=average_duration,
            active_projects=active_count,
            completed_projects=completed_count
        )
