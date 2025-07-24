"""Abstract interface for object storage operations."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union, AsyncIterator
from datetime import datetime
from io import BytesIO


class ObjectMetadata:
    """Metadata for stored objects."""
    
    def __init__(
        self,
        key: str,
        size: int,
        last_modified: datetime,
        etag: str,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ):
        self.key = key
        self.size = size
        self.last_modified = last_modified
        self.etag = etag
        self.content_type = content_type
        self.metadata = metadata or {}


class ObjectStorageInterface(ABC):
    """
    Abstract interface for object storage operations.
    
    Provides a unified interface for different object storage implementations
    including MinIO, AWS S3, Azure Blob Storage, Google Cloud Storage, etc.
    """
    
    @abstractmethod
    async def put_object(
        self,
        key: str,
        data: Union[bytes, BytesIO],
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Store an object in the storage.
        
        Args:
            key: Object key/path
            data: Object data as bytes or BytesIO
            content_type: MIME type of the object
            metadata: Additional metadata for the object
            
        Returns:
            ETag or identifier of the stored object
        """
        pass
    
    @abstractmethod
    async def get_object(self, key: str) -> bytes:
        """
        Retrieve an object from storage.
        
        Args:
            key: Object key/path
            
        Returns:
            Object data as bytes
            
        Raises:
            ObjectNotFoundError: If object doesn't exist
        """
        pass
    
    @abstractmethod
    async def get_object_stream(self, key: str) -> AsyncIterator[bytes]:
        """
        Retrieve an object as a stream for large files.
        
        Args:
            key: Object key/path
            
        Yields:
            Chunks of object data
            
        Raises:
            ObjectNotFoundError: If object doesn't exist
        """
        pass
    
    @abstractmethod
    async def delete_object(self, key: str) -> None:
        """
        Delete an object from storage.
        
        Args:
            key: Object key/path
            
        Raises:
            ObjectNotFoundError: If object doesn't exist
        """
        pass
    
    @abstractmethod
    async def object_exists(self, key: str) -> bool:
        """
        Check if an object exists in storage.
        
        Args:
            key: Object key/path
            
        Returns:
            True if object exists, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_object_metadata(self, key: str) -> ObjectMetadata:
        """
        Get metadata for an object.
        
        Args:
            key: Object key/path
            
        Returns:
            Object metadata
            
        Raises:
            ObjectNotFoundError: If object doesn't exist
        """
        pass
    
    @abstractmethod
    async def list_objects(
        self,
        prefix: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[ObjectMetadata]:
        """
        List objects in storage.
        
        Args:
            prefix: Filter objects by key prefix
            limit: Maximum number of objects to return
            
        Returns:
            List of object metadata
        """
        pass
    
    @abstractmethod
    async def generate_presigned_url(
        self,
        key: str,
        expiration_seconds: int = 3600,
        method: str = "GET"
    ) -> str:
        """
        Generate a presigned URL for object access.
        
        Args:
            key: Object key/path
            expiration_seconds: URL expiration time in seconds
            method: HTTP method (GET, PUT, DELETE)
            
        Returns:
            Presigned URL
        """
        pass
    
    @abstractmethod
    async def copy_object(
        self,
        source_key: str,
        destination_key: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Copy an object to a new location.
        
        Args:
            source_key: Source object key/path
            destination_key: Destination object key/path
            metadata: Additional metadata for the copied object
            
        Returns:
            ETag of the copied object
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        Perform a health check on the storage service.
        
        Returns:
            True if storage is healthy, False otherwise
        """
        pass
