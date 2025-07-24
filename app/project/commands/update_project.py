"""Update project command and handler."""

from dataclasses import dataclass
from typing import List, Optional

from ...common.cqrs import Command, CommandHandler
from ...common.exceptions import ValidationError, EntityNotFoundError
from ..domain.repositories import ProjectRepository


@dataclass
class UpdateProjectCommand(Command):
    """Command to update an existing project."""
    project_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    estimated_duration_days: Optional[int] = None
    budget: Optional[float] = None
    tags: Optional[List[str]] = None


class UpdateProjectHandler(CommandHandler[UpdateProjectCommand]):
    """Handler for UpdateProjectCommand."""
    
    def __init__(self, project_repository: ProjectRepository):
        self.project_repository = project_repository
    
    async def handle(self, command: UpdateProjectCommand) -> None:
        """
        Handle project update.
        
        Args:
            command: Update project command
            
        Raises:
            EntityNotFoundError: If project doesn't exist
            ValidationError: If update data is invalid
            InvalidStateTransitionError: If project cannot be modified
        """
        # Get existing project
        project = await self.project_repository.get_by_id(command.project_id)
        if not project:
            raise EntityNotFoundError(
                entity_type="Project",
                entity_id=command.project_id
            )
        
        # Check if project can be modified
        if not project.can_be_modified():
            raise ValidationError(
                f"Project in status '{project.status.value}' cannot be modified",
                field_name="status",
                field_value=project.status.value
            )
        
        # Update fields if provided
        if command.name is not None:
            project.update_name(command.name)
        
        if command.description is not None:
            project.update_description(command.description)
        
        if command.estimated_duration_days is not None:
            if command.estimated_duration_days <= 0:
                raise ValidationError(
                    "Estimated duration must be positive",
                    field_name="estimated_duration_days",
                    field_value=command.estimated_duration_days
                )
            project.estimated_duration_days = command.estimated_duration_days
            project.updated_at = project.updated_at  # Trigger update
        
        if command.budget is not None:
            if command.budget < 0:
                raise ValidationError(
                    "Budget cannot be negative",
                    field_name="budget",
                    field_value=command.budget
                )
            project.budget = command.budget
            project.updated_at = project.updated_at  # Trigger update
        
        if command.tags is not None:
            project.tags = command.tags
            project.updated_at = project.updated_at  # Trigger update
        
        # Add command metadata
        project.update_metadata("last_updated_via", "api")
        project.update_metadata("last_command_id", command.command_id)
        
        # Save updated project
        await self.project_repository.update(project)
