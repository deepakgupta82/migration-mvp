"""Project repository interface."""

from abc import ABC, abstractmethod
from typing import List, Optional
from ..entities import Project, ProjectStatus


class ProjectRepository(ABC):
    """
    Abstract repository interface for Project entities.
    
    Defines the contract for project data access operations
    without coupling to specific database implementations.
    """
    
    @abstractmethod
    async def create(self, project: Project) -> Project:
        """
        Create a new project.
        
        Args:
            project: Project entity to create
            
        Returns:
            Created project with generated ID
            
        Raises:
            DuplicateEntityError: If project with same name exists for client
            DatabaseError: If database operation fails
        """
        pass
    
    @abstractmethod
    async def get_by_id(self, project_id: str) -> Optional[Project]:
        """
        Get project by ID.
        
        Args:
            project_id: Project ID
            
        Returns:
            Project if found, None otherwise
            
        Raises:
            DatabaseError: If database operation fails
        """
        pass
    
    @abstractmethod
    async def get_by_name(self, name: str, client_id: str) -> Optional[Project]:
        """
        Get project by name and client.
        
        Args:
            name: Project name
            client_id: Client ID
            
        Returns:
            Project if found, None otherwise
            
        Raises:
            DatabaseError: If database operation fails
        """
        pass
    
    @abstractmethod
    async def update(self, project: Project) -> Project:
        """
        Update an existing project.
        
        Args:
            project: Project entity to update
            
        Returns:
            Updated project
            
        Raises:
            EntityNotFoundError: If project doesn't exist
            ConcurrencyError: If project was modified by another process
            DatabaseError: If database operation fails
        """
        pass
    
    @abstractmethod
    async def delete(self, project_id: str) -> None:
        """
        Delete a project.
        
        Args:
            project_id: Project ID to delete
            
        Raises:
            EntityNotFoundError: If project doesn't exist
            DatabaseError: If database operation fails
        """
        pass
    
    @abstractmethod
    async def list_by_client(
        self,
        client_id: str,
        status: Optional[ProjectStatus] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Project]:
        """
        List projects for a client.
        
        Args:
            client_id: Client ID
            status: Optional status filter
            limit: Maximum number of projects to return
            offset: Number of projects to skip
            
        Returns:
            List of projects
            
        Raises:
            DatabaseError: If database operation fails
        """
        pass
    
    @abstractmethod
    async def list_by_user(
        self,
        user_id: str,
        status: Optional[ProjectStatus] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Project]:
        """
        List projects assigned to a user.
        
        Args:
            user_id: User ID
            status: Optional status filter
            limit: Maximum number of projects to return
            offset: Number of projects to skip
            
        Returns:
            List of projects
            
        Raises:
            DatabaseError: If database operation fails
        """
        pass
    
    @abstractmethod
    async def search(
        self,
        query: str,
        client_id: Optional[str] = None,
        status: Optional[ProjectStatus] = None,
        tags: Optional[List[str]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Project]:
        """
        Search projects by various criteria.
        
        Args:
            query: Search query (name, description)
            client_id: Optional client filter
            status: Optional status filter
            tags: Optional tags filter
            limit: Maximum number of projects to return
            offset: Number of projects to skip
            
        Returns:
            List of matching projects
            
        Raises:
            DatabaseError: If database operation fails
        """
        pass
    
    @abstractmethod
    async def count_by_status(self, client_id: Optional[str] = None) -> dict:
        """
        Count projects by status.
        
        Args:
            client_id: Optional client filter
            
        Returns:
            Dictionary mapping status to count
            
        Raises:
            DatabaseError: If database operation fails
        """
        pass
    
    @abstractmethod
    async def exists(self, project_id: str) -> bool:
        """
        Check if project exists.
        
        Args:
            project_id: Project ID
            
        Returns:
            True if project exists, False otherwise
            
        Raises:
            DatabaseError: If database operation fails
        """
        pass
