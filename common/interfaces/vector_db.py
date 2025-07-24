"""Abstract interface for vector database operations."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
import numpy as np


@dataclass
class VectorDocument:
    """Represents a document with vector embedding."""
    id: str
    content: str
    vector: List[float]
    metadata: Dict[str, Any]


@dataclass
class SearchResult:
    """Represents a search result from vector database."""
    document: VectorDocument
    score: float
    distance: float


class VectorDBInterface(ABC):
    """
    Abstract interface for vector database operations.
    
    Provides a unified interface for different vector database implementations
    including Weaviate, Pinecone, Chroma, Qdrant, etc.
    """
    
    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the vector database."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the vector database."""
        pass
    
    @abstractmethod
    async def create_collection(
        self,
        collection_name: str,
        vector_dimension: int,
        distance_metric: str = "cosine",
        metadata_schema: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Create a new collection for storing vectors.
        
        Args:
            collection_name: Name of the collection
            vector_dimension: Dimension of the vectors
            distance_metric: Distance metric ("cosine", "euclidean", "dot")
            metadata_schema: Schema for metadata fields
        """
        pass
    
    @abstractmethod
    async def delete_collection(self, collection_name: str) -> None:
        """
        Delete a collection.
        
        Args:
            collection_name: Name of the collection to delete
        """
        pass
    
    @abstractmethod
    async def collection_exists(self, collection_name: str) -> bool:
        """
        Check if a collection exists.
        
        Args:
            collection_name: Name of the collection
            
        Returns:
            True if collection exists, False otherwise
        """
        pass
    
    @abstractmethod
    async def insert_document(
        self,
        collection_name: str,
        document: VectorDocument
    ) -> None:
        """
        Insert a document into a collection.
        
        Args:
            collection_name: Name of the collection
            document: Document to insert
        """
        pass
    
    @abstractmethod
    async def insert_documents(
        self,
        collection_name: str,
        documents: List[VectorDocument]
    ) -> None:
        """
        Insert multiple documents into a collection.
        
        Args:
            collection_name: Name of the collection
            documents: List of documents to insert
        """
        pass
    
    @abstractmethod
    async def get_document(
        self,
        collection_name: str,
        document_id: str
    ) -> Optional[VectorDocument]:
        """
        Retrieve a document by ID.
        
        Args:
            collection_name: Name of the collection
            document_id: Document ID
            
        Returns:
            VectorDocument if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def update_document(
        self,
        collection_name: str,
        document: VectorDocument
    ) -> None:
        """
        Update a document in the collection.
        
        Args:
            collection_name: Name of the collection
            document: Updated document
        """
        pass
    
    @abstractmethod
    async def delete_document(
        self,
        collection_name: str,
        document_id: str
    ) -> None:
        """
        Delete a document from the collection.
        
        Args:
            collection_name: Name of the collection
            document_id: Document ID to delete
        """
        pass
    
    @abstractmethod
    async def search_similar(
        self,
        collection_name: str,
        query_vector: List[float],
        limit: int = 10,
        min_score: Optional[float] = None,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        Search for similar documents using vector similarity.
        
        Args:
            collection_name: Name of the collection
            query_vector: Query vector
            limit: Maximum number of results
            min_score: Minimum similarity score
            metadata_filter: Filter by metadata fields
            
        Returns:
            List of search results ordered by similarity
        """
        pass
    
    @abstractmethod
    async def search_by_text(
        self,
        collection_name: str,
        query_text: str,
        limit: int = 10,
        min_score: Optional[float] = None,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        Search for similar documents using text query.
        
        Args:
            collection_name: Name of the collection
            query_text: Query text (will be embedded)
            limit: Maximum number of results
            min_score: Minimum similarity score
            metadata_filter: Filter by metadata fields
            
        Returns:
            List of search results ordered by similarity
        """
        pass
    
    @abstractmethod
    async def hybrid_search(
        self,
        collection_name: str,
        query_text: str,
        query_vector: Optional[List[float]] = None,
        text_weight: float = 0.5,
        vector_weight: float = 0.5,
        limit: int = 10,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        Perform hybrid search combining text and vector similarity.
        
        Args:
            collection_name: Name of the collection
            query_text: Query text
            query_vector: Optional query vector
            text_weight: Weight for text similarity
            vector_weight: Weight for vector similarity
            limit: Maximum number of results
            metadata_filter: Filter by metadata fields
            
        Returns:
            List of search results ordered by combined similarity
        """
        pass
    
    @abstractmethod
    async def get_collection_stats(self, collection_name: str) -> Dict[str, Any]:
        """
        Get statistics for a collection.
        
        Args:
            collection_name: Name of the collection
            
        Returns:
            Dictionary with collection statistics
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        Perform a health check on the vector database.
        
        Returns:
            True if database is healthy, False otherwise
        """
        pass
