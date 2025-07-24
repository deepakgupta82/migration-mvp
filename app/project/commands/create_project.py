"""Create project command and handler."""

from dataclasses import dataclass
from typing import List, Optional

from ...common.cqrs import Command, CommandHandler
from ...common.exceptions import ValidationError, DuplicateEntityError
from ..domain.entities import Project, ProjectStatus
from ..domain.repositories import ProjectRepository, ClientRepository


@dataclass
class CreateProjectCommand(Command):
    """Command to create a new project."""
    name: str
    description: str
    client_id: str
    estimated_duration_days: Optional[int] = None
    budget: Optional[float] = None
    tags: Optional[List[str]] = None
    
    def __post_init__(self):
        super().__post_init__()
        if self.tags is None:
            self.tags = []


class CreateProjectHandler(CommandHandler[CreateProjectCommand]):
    """Handler for CreateProjectCommand."""
    
    def __init__(
        self,
        project_repository: ProjectRepository,
        client_repository: ClientRepository
    ):
        self.project_repository = project_repository
        self.client_repository = client_repository
    
    async def handle(self, command: CreateProjectCommand) -> None:
        """
        Handle project creation.
        
        Args:
            command: Create project command
            
        Raises:
            ValidationError: If command data is invalid
            DuplicateEntityError: If project name already exists for client
            EntityNotFoundError: If client doesn't exist
        """
        # Validate client exists
        client = await self.client_repository.get_by_id(command.client_id)
        if not client:
            raise ValidationError(
                f"Client with ID '{command.client_id}' not found",
                field_name="client_id",
                field_value=command.client_id
            )
        
        # Check if project name already exists for this client
        existing_project = await self.project_repository.get_by_name(
            command.name, 
            command.client_id
        )
        if existing_project:
            raise DuplicateEntityError(
                entity_type="Project",
                identifier=command.name,
                identifier_field="name",
                context={"client_id": command.client_id}
            )
        
        # Create project entity
        project = Project(
            name=command.name,
            description=command.description,
            client_id=command.client_id,
            status=ProjectStatus.DRAFT,
            created_by=command.user_id or "system",
            estimated_duration_days=command.estimated_duration_days,
            budget=command.budget,
            tags=command.tags or [],
            metadata={
                "created_via": "api",
                "command_id": command.command_id
            }
        )
        
        # Save project
        await self.project_repository.create(project)
