"""AWS S3 adapter for cloud object storage."""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, AsyncIterator
from io import BytesIO
import aioboto3
from botocore.exceptions import ClientError, NoCredentialsError

from ..interfaces import ObjectStorageInterface, ObjectMetadata
from ..exceptions import ObjectStorageError, ObjectNotFoundError


class S3Adapter(ObjectStorageInterface):
    """
    AWS S3 adapter for cloud object storage.
    
    Implements the ObjectStorageInterface using aioboto3 for S3 operations.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize S3 adapter.
        
        Args:
            config: S3 configuration
        """
        self.config = config
        self.region = config.get("region", "us-east-1")
        self.bucket_name = config.get("bucket_name", "agentimigrate")
        self.access_key_id = config.get("access_key_id")
        self.secret_access_key = config.get("secret_access_key")
        
        # Create aioboto3 session
        self.session = aioboto3.Session(
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name=self.region
        )
    
    async def put_object(
        self,
        key: str,
        data: Union[bytes, BytesIO],
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> str:
        """Store an object in S3."""
        try:
            async with self.session.client('s3') as s3:
                put_args = {
                    'Bucket': self.bucket_name,
                    'Key': key,
                    'Body': data
                }
                
                if content_type:
                    put_args['ContentType'] = content_type
                
                if metadata:
                    put_args['Metadata'] = metadata
                
                response = await s3.put_object(**put_args)
                return response['ETag'].strip('"')
                
        except ClientError as e:
            raise ObjectStorageError(
                f"Failed to put object in S3: {str(e)}",
                bucket_name=self.bucket_name,
                object_key=key,
                operation="put",
                context={"error_code": e.response.get('Error', {}).get('Code')}
            )
        except NoCredentialsError as e:
            raise ObjectStorageError(
                f"AWS credentials not found: {str(e)}",
                bucket_name=self.bucket_name,
                object_key=key,
                operation="put"
            )
    
    async def get_object(self, key: str) -> bytes:
        """Retrieve an object from S3."""
        try:
            async with self.session.client('s3') as s3:
                response = await s3.get_object(Bucket=self.bucket_name, Key=key)
                
                # Read the streaming body
                data = await response['Body'].read()
                return data
                
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            if error_code == 'NoSuchKey':
                raise ObjectNotFoundError(key, self.bucket_name)
            raise ObjectStorageError(
                f"Failed to get object from S3: {str(e)}",
                bucket_name=self.bucket_name,
                object_key=key,
                operation="get",
                context={"error_code": error_code}
            )
    
    async def get_object_stream(self, key: str) -> AsyncIterator[bytes]:
        """Retrieve an object as a stream from S3."""
        try:
            async with self.session.client('s3') as s3:
                response = await s3.get_object(Bucket=self.bucket_name, Key=key)
                
                async for chunk in response['Body']:
                    yield chunk
                    
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            if error_code == 'NoSuchKey':
                raise ObjectNotFoundError(key, self.bucket_name)
            raise ObjectStorageError(
                f"Failed to stream object from S3: {str(e)}",
                bucket_name=self.bucket_name,
                object_key=key,
                operation="stream",
                context={"error_code": error_code}
            )
    
    async def delete_object(self, key: str) -> None:
        """Delete an object from S3."""
        try:
            async with self.session.client('s3') as s3:
                await s3.delete_object(Bucket=self.bucket_name, Key=key)
                
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            if error_code == 'NoSuchKey':
                raise ObjectNotFoundError(key, self.bucket_name)
            raise ObjectStorageError(
                f"Failed to delete object from S3: {str(e)}",
                bucket_name=self.bucket_name,
                object_key=key,
                operation="delete",
                context={"error_code": error_code}
            )
    
    async def object_exists(self, key: str) -> bool:
        """Check if an object exists in S3."""
        try:
            async with self.session.client('s3') as s3:
                await s3.head_object(Bucket=self.bucket_name, Key=key)
                return True
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            if error_code in ['NoSuchKey', '404']:
                return False
            raise ObjectStorageError(
                f"Failed to check object existence in S3: {str(e)}",
                bucket_name=self.bucket_name,
                object_key=key,
                operation="exists",
                context={"error_code": error_code}
            )
    
    async def get_object_metadata(self, key: str) -> ObjectMetadata:
        """Get metadata for an object in S3."""
        try:
            async with self.session.client('s3') as s3:
                response = await s3.head_object(Bucket=self.bucket_name, Key=key)
                
                return ObjectMetadata(
                    key=key,
                    size=response['ContentLength'],
                    last_modified=response['LastModified'],
                    etag=response['ETag'].strip('"'),
                    content_type=response.get('ContentType'),
                    metadata=response.get('Metadata', {})
                )
                
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            if error_code == 'NoSuchKey':
                raise ObjectNotFoundError(key, self.bucket_name)
            raise ObjectStorageError(
                f"Failed to get object metadata from S3: {str(e)}",
                bucket_name=self.bucket_name,
                object_key=key,
                operation="metadata",
                context={"error_code": error_code}
            )
    
    async def list_objects(
        self,
        prefix: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[ObjectMetadata]:
        """List objects in S3."""
        try:
            async with self.session.client('s3') as s3:
                list_args = {'Bucket': self.bucket_name}
                
                if prefix:
                    list_args['Prefix'] = prefix
                
                if limit:
                    list_args['MaxKeys'] = limit
                
                response = await s3.list_objects_v2(**list_args)
                
                objects = []
                for obj in response.get('Contents', []):
                    objects.append(ObjectMetadata(
                        key=obj['Key'],
                        size=obj['Size'],
                        last_modified=obj['LastModified'],
                        etag=obj['ETag'].strip('"'),
                        content_type=None,  # Not available in list operation
                        metadata={}
                    ))
                
                return objects
                
        except ClientError as e:
            raise ObjectStorageError(
                f"Failed to list objects in S3: {str(e)}",
                bucket_name=self.bucket_name,
                operation="list",
                context={"error_code": e.response.get('Error', {}).get('Code')}
            )
    
    async def generate_presigned_url(
        self,
        key: str,
        expiration_seconds: int = 3600,
        method: str = "GET"
    ) -> str:
        """Generate a presigned URL for S3 object access."""
        try:
            async with self.session.client('s3') as s3:
                if method.upper() == "GET":
                    url = await s3.generate_presigned_url(
                        'get_object',
                        Params={'Bucket': self.bucket_name, 'Key': key},
                        ExpiresIn=expiration_seconds
                    )
                elif method.upper() == "PUT":
                    url = await s3.generate_presigned_url(
                        'put_object',
                        Params={'Bucket': self.bucket_name, 'Key': key},
                        ExpiresIn=expiration_seconds
                    )
                else:
                    raise ValueError(f"Unsupported method: {method}")
                
                return url
                
        except ClientError as e:
            raise ObjectStorageError(
                f"Failed to generate presigned URL for S3: {str(e)}",
                bucket_name=self.bucket_name,
                object_key=key,
                operation="presigned_url",
                context={"error_code": e.response.get('Error', {}).get('Code')}
            )
    
    async def copy_object(
        self,
        source_key: str,
        destination_key: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> str:
        """Copy an object to a new location in S3."""
        try:
            async with self.session.client('s3') as s3:
                copy_source = {
                    'Bucket': self.bucket_name,
                    'Key': source_key
                }
                
                copy_args = {
                    'CopySource': copy_source,
                    'Bucket': self.bucket_name,
                    'Key': destination_key
                }
                
                if metadata:
                    copy_args['Metadata'] = metadata
                    copy_args['MetadataDirective'] = 'REPLACE'
                
                response = await s3.copy_object(**copy_args)
                return response['CopyObjectResult']['ETag'].strip('"')
                
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            if error_code == 'NoSuchKey':
                raise ObjectNotFoundError(source_key, self.bucket_name)
            raise ObjectStorageError(
                f"Failed to copy object in S3: {str(e)}",
                bucket_name=self.bucket_name,
                object_key=source_key,
                operation="copy",
                context={"error_code": error_code}
            )
    
    async def health_check(self) -> bool:
        """Perform a health check on S3."""
        try:
            async with self.session.client('s3') as s3:
                # Try to head the bucket as a health check
                await s3.head_bucket(Bucket=self.bucket_name)
                return True
        except Exception:
            return False
