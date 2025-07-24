"""MinIO adapter for local object storage."""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, AsyncIterator
from io import BytesIO
import aiofiles
import minio
from minio.error import S3Error

from ..interfaces import ObjectStorageInterface, ObjectMetadata
from ..exceptions import ObjectStorageError, ObjectNotFoundError


class MinioAdapter(ObjectStorageInterface):
    """
    MinIO adapter for local object storage.
    
    Implements the ObjectStorageInterface using MinIO client.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize MinIO adapter.
        
        Args:
            config: MinIO configuration
        """
        self.config = config
        self.endpoint = config.get("endpoint", "localhost:9000")
        self.access_key = config.get("access_key", "minioadmin")
        self.secret_key = config.get("secret_key", "minioadmin")
        self.secure = config.get("secure", False)
        self.bucket_name = config.get("bucket_name", "agentimigrate")
        
        self.client = minio.Minio(
            endpoint=self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure
        )
        
        # Ensure bucket exists
        asyncio.create_task(self._ensure_bucket_exists())
    
    async def _ensure_bucket_exists(self) -> None:
        """Ensure the bucket exists, create if it doesn't."""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
        except Exception as e:
            raise ObjectStorageError(
                f"Failed to ensure bucket exists: {str(e)}",
                bucket_name=self.bucket_name,
                operation="create_bucket"
            )
    
    async def put_object(
        self,
        key: str,
        data: Union[bytes, BytesIO],
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> str:
        """Store an object in MinIO."""
        try:
            if isinstance(data, bytes):
                data_stream = BytesIO(data)
                data_length = len(data)
            else:
                data_stream = data
                data_stream.seek(0, 2)  # Seek to end
                data_length = data_stream.tell()
                data_stream.seek(0)  # Seek back to beginning
            
            result = self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=key,
                data=data_stream,
                length=data_length,
                content_type=content_type,
                metadata=metadata
            )
            
            return result.etag
            
        except S3Error as e:
            raise ObjectStorageError(
                f"Failed to put object: {str(e)}",
                bucket_name=self.bucket_name,
                object_key=key,
                operation="put"
            )
    
    async def get_object(self, key: str) -> bytes:
        """Retrieve an object from MinIO."""
        try:
            response = self.client.get_object(self.bucket_name, key)
            data = response.read()
            response.close()
            response.release_conn()
            return data
            
        except S3Error as e:
            if e.code == "NoSuchKey":
                raise ObjectNotFoundError(key, self.bucket_name)
            raise ObjectStorageError(
                f"Failed to get object: {str(e)}",
                bucket_name=self.bucket_name,
                object_key=key,
                operation="get"
            )
    
    async def get_object_stream(self, key: str) -> AsyncIterator[bytes]:
        """Retrieve an object as a stream."""
        try:
            response = self.client.get_object(self.bucket_name, key)
            
            try:
                chunk_size = 8192
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
            finally:
                response.close()
                response.release_conn()
                
        except S3Error as e:
            if e.code == "NoSuchKey":
                raise ObjectNotFoundError(key, self.bucket_name)
            raise ObjectStorageError(
                f"Failed to stream object: {str(e)}",
                bucket_name=self.bucket_name,
                object_key=key,
                operation="stream"
            )
    
    async def delete_object(self, key: str) -> None:
        """Delete an object from MinIO."""
        try:
            self.client.remove_object(self.bucket_name, key)
            
        except S3Error as e:
            if e.code == "NoSuchKey":
                raise ObjectNotFoundError(key, self.bucket_name)
            raise ObjectStorageError(
                f"Failed to delete object: {str(e)}",
                bucket_name=self.bucket_name,
                object_key=key,
                operation="delete"
            )
    
    async def object_exists(self, key: str) -> bool:
        """Check if an object exists in MinIO."""
        try:
            self.client.stat_object(self.bucket_name, key)
            return True
        except S3Error as e:
            if e.code == "NoSuchKey":
                return False
            raise ObjectStorageError(
                f"Failed to check object existence: {str(e)}",
                bucket_name=self.bucket_name,
                object_key=key,
                operation="exists"
            )
    
    async def get_object_metadata(self, key: str) -> ObjectMetadata:
        """Get metadata for an object."""
        try:
            stat = self.client.stat_object(self.bucket_name, key)
            
            return ObjectMetadata(
                key=key,
                size=stat.size,
                last_modified=stat.last_modified,
                etag=stat.etag,
                content_type=stat.content_type,
                metadata=stat.metadata
            )
            
        except S3Error as e:
            if e.code == "NoSuchKey":
                raise ObjectNotFoundError(key, self.bucket_name)
            raise ObjectStorageError(
                f"Failed to get object metadata: {str(e)}",
                bucket_name=self.bucket_name,
                object_key=key,
                operation="metadata"
            )
    
    async def list_objects(
        self,
        prefix: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[ObjectMetadata]:
        """List objects in MinIO."""
        try:
            objects = self.client.list_objects(
                self.bucket_name,
                prefix=prefix,
                recursive=True
            )
            
            result = []
            count = 0
            
            for obj in objects:
                if limit and count >= limit:
                    break
                
                result.append(ObjectMetadata(
                    key=obj.object_name,
                    size=obj.size,
                    last_modified=obj.last_modified,
                    etag=obj.etag,
                    content_type=None,  # Not available in list operation
                    metadata={}
                ))
                count += 1
            
            return result
            
        except S3Error as e:
            raise ObjectStorageError(
                f"Failed to list objects: {str(e)}",
                bucket_name=self.bucket_name,
                operation="list"
            )
    
    async def generate_presigned_url(
        self,
        key: str,
        expiration_seconds: int = 3600,
        method: str = "GET"
    ) -> str:
        """Generate a presigned URL for object access."""
        try:
            if method.upper() == "GET":
                url = self.client.presigned_get_object(
                    self.bucket_name,
                    key,
                    expires=timedelta(seconds=expiration_seconds)
                )
            elif method.upper() == "PUT":
                url = self.client.presigned_put_object(
                    self.bucket_name,
                    key,
                    expires=timedelta(seconds=expiration_seconds)
                )
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            return url
            
        except S3Error as e:
            raise ObjectStorageError(
                f"Failed to generate presigned URL: {str(e)}",
                bucket_name=self.bucket_name,
                object_key=key,
                operation="presigned_url"
            )
    
    async def copy_object(
        self,
        source_key: str,
        destination_key: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> str:
        """Copy an object to a new location."""
        try:
            copy_source = minio.commonconfig.CopySource(self.bucket_name, source_key)
            
            result = self.client.copy_object(
                self.bucket_name,
                destination_key,
                copy_source,
                metadata=metadata
            )
            
            return result.etag
            
        except S3Error as e:
            if e.code == "NoSuchKey":
                raise ObjectNotFoundError(source_key, self.bucket_name)
            raise ObjectStorageError(
                f"Failed to copy object: {str(e)}",
                bucket_name=self.bucket_name,
                object_key=source_key,
                operation="copy"
            )
    
    async def health_check(self) -> bool:
        """Perform a health check on MinIO."""
        try:
            # Try to list buckets as a health check
            list(self.client.list_buckets())
            return True
        except Exception:
            return False
