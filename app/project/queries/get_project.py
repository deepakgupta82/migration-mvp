"""Get project query and handler."""

from dataclasses import dataclass
from typing import Optional

from ...common.cqrs import Query, QueryHandler
from ...common.exceptions import EntityNotFoundError
from ..domain.repositories import ProjectRepository
from ..dto import ProjectDTO


@dataclass
class GetProjectQuery(Query):
    """Query to get a project by ID."""
    project_id: str


class GetProjectHandler(QueryHandler[GetProjectQuery, ProjectDTO]):
    """Handler for GetProjectQuery."""
    
    def __init__(self, project_repository: ProjectRepository):
        self.project_repository = project_repository
    
    async def handle(self, query: GetProjectQuery) -> ProjectDTO:
        """
        Handle get project query.
        
        Args:
            query: Get project query
            
        Returns:
            Project DTO
            
        Raises:
            EntityNotFoundError: If project doesn't exist
        """
        project = await self.project_repository.get_by_id(query.project_id)
        
        if not project:
            raise EntityNotFoundError(
                entity_type="Project",
                entity_id=query.project_id
            )
        
        return ProjectDTO.from_entity(project)
