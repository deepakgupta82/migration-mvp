"""Abstract interface for graph database operations."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass


@dataclass
class GraphNode:
    """Represents a node in the graph database."""
    id: Optional[str]
    labels: List[str]
    properties: Dict[str, Any]


@dataclass
class GraphRelationship:
    """Represents a relationship in the graph database."""
    id: Optional[str]
    type: str
    start_node_id: str
    end_node_id: str
    properties: Dict[str, Any]


@dataclass
class GraphPath:
    """Represents a path in the graph database."""
    nodes: List[GraphNode]
    relationships: List[GraphRelationship]


class GraphDBInterface(ABC):
    """
    Abstract interface for graph database operations.
    
    Provides a unified interface for different graph database implementations
    including Neo4j, Amazon Neptune, Azure Cosmos DB, etc.
    """
    
    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the graph database."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the graph database."""
        pass
    
    @abstractmethod
    async def execute_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute a Cypher query and return results.
        
        Args:
            query: Cypher query string
            parameters: Query parameters
            
        Returns:
            List of dictionaries representing query results
        """
        pass
    
    @abstractmethod
    async def create_node(
        self,
        labels: List[str],
        properties: Dict[str, Any]
    ) -> str:
        """
        Create a new node in the graph.
        
        Args:
            labels: Node labels
            properties: Node properties
            
        Returns:
            Node ID
        """
        pass
    
    @abstractmethod
    async def get_node(self, node_id: str) -> Optional[GraphNode]:
        """
        Retrieve a node by ID.
        
        Args:
            node_id: Node ID
            
        Returns:
            GraphNode if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def update_node(
        self,
        node_id: str,
        properties: Dict[str, Any]
    ) -> None:
        """
        Update node properties.
        
        Args:
            node_id: Node ID
            properties: Properties to update
        """
        pass
    
    @abstractmethod
    async def delete_node(self, node_id: str) -> None:
        """
        Delete a node from the graph.
        
        Args:
            node_id: Node ID
        """
        pass
    
    @abstractmethod
    async def create_relationship(
        self,
        start_node_id: str,
        end_node_id: str,
        relationship_type: str,
        properties: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a relationship between two nodes.
        
        Args:
            start_node_id: Start node ID
            end_node_id: End node ID
            relationship_type: Relationship type
            properties: Relationship properties
            
        Returns:
            Relationship ID
        """
        pass
    
    @abstractmethod
    async def get_relationship(self, relationship_id: str) -> Optional[GraphRelationship]:
        """
        Retrieve a relationship by ID.
        
        Args:
            relationship_id: Relationship ID
            
        Returns:
            GraphRelationship if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def delete_relationship(self, relationship_id: str) -> None:
        """
        Delete a relationship from the graph.
        
        Args:
            relationship_id: Relationship ID
        """
        pass
    
    @abstractmethod
    async def find_nodes(
        self,
        labels: Optional[List[str]] = None,
        properties: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None
    ) -> List[GraphNode]:
        """
        Find nodes matching criteria.
        
        Args:
            labels: Node labels to match
            properties: Properties to match
            limit: Maximum number of nodes to return
            
        Returns:
            List of matching nodes
        """
        pass
    
    @abstractmethod
    async def find_paths(
        self,
        start_node_id: str,
        end_node_id: str,
        max_depth: int = 5,
        relationship_types: Optional[List[str]] = None
    ) -> List[GraphPath]:
        """
        Find paths between two nodes.
        
        Args:
            start_node_id: Start node ID
            end_node_id: End node ID
            max_depth: Maximum path depth
            relationship_types: Relationship types to traverse
            
        Returns:
            List of paths
        """
        pass
    
    @abstractmethod
    async def get_neighbors(
        self,
        node_id: str,
        relationship_types: Optional[List[str]] = None,
        direction: str = "both"
    ) -> List[GraphNode]:
        """
        Get neighboring nodes.
        
        Args:
            node_id: Node ID
            relationship_types: Relationship types to follow
            direction: Direction ("incoming", "outgoing", "both")
            
        Returns:
            List of neighboring nodes
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        Perform a health check on the graph database.
        
        Returns:
            True if database is healthy, False otherwise
        """
        pass
