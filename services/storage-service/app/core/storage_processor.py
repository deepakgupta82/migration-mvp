#!/usr/bin/env python3
"""
Storage Service Core Processor
Complete extraction of ObjectStorage business logic from backend monolith
Handles MinIO/S3 compatible storage with multi-provider support
"""

import os
import io
import logging
from typing import Optional, Tuple, List, Dict, Any
from datetime import datetime

from minio import Minio
from minio.error import S3Error

logger = logging.getLogger("storage-service")


class StorageProcessor:
    """
    Complete ObjectStorage implementation extracted from backend monolith.
    Handles MinIO/S3 compatible storage with pluggable provider support.
    
    Folder layout (keys):
      projects/{project_id}/uploads/raw/{filename}
      projects/{project_id}/uploads/parsed/{filename} 
      projects/{project_id}/uploads/canonical/{filename}
      projects/{project_id}/generated/reports/{filename}
      projects/{project_id}/logs/processing/{filename}
      projects/{project_id}/metadata/{filename}
    """

    def __init__(self):
        """Initialize storage processor with provider configuration"""
        # Provider selection with fallbacks
        provider = os.getenv("STORAGE_PROVIDER") or os.getenv("OBJECT_STORAGE_PROVIDER") or "minio"
        self.provider = provider.lower()
        
        if self.provider not in ("minio", "s3", "azure", "filesystem"):
            logger.warning(f"Unknown STORAGE_PROVIDER={self.provider}, defaulting to minio")
            self.provider = "minio"

        # Bucket configuration with comprehensive fallbacks
        bucket = (
            os.getenv("STORAGE_BUCKET")
            or os.getenv("OBJECT_STORAGE_BUCKET") 
            or os.getenv("MINIO_BUCKET_NAME")
            or "agentimigrate"
        )
        self.bucket = bucket.strip().lower()
        
        if "-" in self.bucket:
            logger.warning("STORAGE_BUCKET contains hyphens; consider removing them for cross-provider compatibility")

        # Initialize provider-specific client
        if self.provider in ("minio", "s3"):
            self._init_minio_client()
        else:
            self._init_filesystem_client()

    def _init_minio_client(self):
        """Initialize MinIO/S3 client with configuration"""
        try:
            # Endpoint and credentials with comprehensive fallbacks
            endpoint = (
                os.getenv("STORAGE_ENDPOINT") 
                or os.getenv("OBJECT_STORAGE_ENDPOINT") 
                or os.getenv("MINIO_ENDPOINT") 
                or "localhost:9000"
            )
            
            access_key = (
                os.getenv("STORAGE_ACCESS_KEY")
                or os.getenv("OBJECT_STORAGE_ACCESS_KEY")
                or os.getenv("MINIO_ACCESS_KEY")
                or os.getenv("MINIO_ROOT_USER")
                or "minioadmin"
            )
            
            secret_key = (
                os.getenv("STORAGE_SECRET_KEY")
                or os.getenv("OBJECT_STORAGE_SECRET_KEY")
                or os.getenv("MINIO_SECRET_KEY")
                or os.getenv("MINIO_ROOT_PASSWORD")
                or "minioadmin"
            )
            
            secure_env = (
                os.getenv("STORAGE_SECURE")
                or os.getenv("OBJECT_STORAGE_SECURE")
                or os.getenv("MINIO_SECURE")
                or "false"
            )
            secure = str(secure_env).lower() in ("1", "true", "yes")
            
            # Create MinIO client
            self.client = Minio(
                endpoint, 
                access_key=access_key, 
                secret_key=secret_key, 
                secure=secure
            )
            
            # Ensure bucket exists
            self._ensure_bucket()
            logger.info(f"MinIO client initialized - endpoint: {endpoint}, bucket: {self.bucket}, secure: {secure}")
            
        except Exception as e:
            logger.error(f"Failed to initialize MinIO client: {e}")
            raise

    def _init_filesystem_client(self):
        """Initialize filesystem fallback for development"""
        logger.warning(f"Provider {self.provider} not yet implemented; using filesystem fallback")
        self.client = None
        self.local_root = os.getenv("UPLOAD_ROOT_TMP") or os.getcwd()
        os.makedirs(self.local_root, exist_ok=True)
        logger.info(f"Filesystem storage initialized - root: {self.local_root}")

    def _ensure_bucket(self):
        """Ensure storage bucket exists"""
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                logger.info(f"Created storage bucket: {self.bucket}")
            else:
                logger.debug(f"Storage bucket exists: {self.bucket}")
        except Exception as e:
            logger.error(f"Failed ensuring bucket '{self.bucket}': {e}")
            raise

    def _get_storage_key(self, project_id: str, category: str, filename: str) -> str:
        """Generate storage key based on project layout"""
        base = f"projects/{project_id}"
        
        # Category to path mapping
        category_mapping = {
            "uploads_raw": f"{base}/uploads/raw/",
            "uploads_parsed": f"{base}/uploads/parsed/", 
            "uploads_canonical": f"{base}/uploads/canonical/",
            "generated_reports": f"{base}/generated/reports/",
            "logs_processing": f"{base}/logs/processing/",
            "metadata": f"{base}/metadata/",
        }
        
        prefix = category_mapping.get(category)
        if not prefix:
            raise ValueError(f"Unknown storage category: {category}")
            
        return prefix + filename

    async def upload_file_bytes(self, project_id: str, category: str, filename: str, 
                               data: bytes, content_type: Optional[str] = None) -> Dict[str, Any]:
        """Upload file from bytes data"""
        try:
            if self.client:
                # MinIO/S3 upload
                data_stream = io.BytesIO(data)
                length = len(data)
                ct = content_type or "application/octet-stream"
                key = self._get_storage_key(project_id, category, filename)
                
                # Upload to MinIO
                self.client.put_object(
                    self.bucket, 
                    key, 
                    data_stream, 
                    length=length, 
                    content_type=ct
                )
                
                logger.info(f"Uploaded file: {key} ({length} bytes)")
                
                return {
                    "success": True,
                    "key": key,
                    "size": length,
                    "content_type": ct,
                    "uploaded_at": datetime.now().isoformat()
                }
            else:
                # Filesystem fallback
                target = os.path.join(self.local_root, f"project_{project_id}", category)
                os.makedirs(target, exist_ok=True)
                fpath = os.path.join(target, filename)
                
                with open(fpath, "wb") as f:
                    f.write(data)
                
                logger.info(f"Uploaded file (filesystem): {fpath} ({len(data)} bytes)")
                
                return {
                    "success": True,
                    "key": fpath,
                    "size": len(data),
                    "content_type": content_type or "application/octet-stream",
                    "uploaded_at": datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Upload failed for {filename}: {e}")
            raise

    async def upload_text_content(self, project_id: str, category: str, filename: str, 
                                 text: str, content_type: Optional[str] = None) -> Dict[str, Any]:
        """Upload text content as UTF-8 encoded file"""
        data = text.encode("utf-8")
        ct = content_type or "text/plain; charset=utf-8"
        return await self.upload_file_bytes(project_id, category, filename, data, content_type=ct)

    async def download_file(self, project_id: str, category: str, filename: str) -> Dict[str, Any]:
        """Download file and return data with metadata"""
        try:
            if self.client:
                # MinIO/S3 download
                key = self._get_storage_key(project_id, category, filename)
                
                try:
                    response = self.client.get_object(self.bucket, key)
                    stat = self.client.stat_object(self.bucket, key)
                    data = response.read()
                    response.close()
                    
                    logger.info(f"Downloaded file: {key} ({stat.size} bytes)")
                    
                    return {
                        "success": True,
                        "data": data,
                        "content_type": stat.content_type or "application/octet-stream",
                        "size": stat.size,
                        "last_modified": stat.last_modified.isoformat() if stat.last_modified else None,
                        "filename": filename
                    }
                    
                except S3Error as e:
                    logger.error(f"Failed to download {key}: {e}")
                    raise FileNotFoundError(f"File not found: {key}")
            else:
                # Filesystem fallback  
                path = os.path.join(self.local_root, f"project_{project_id}", category, filename)
                
                if not os.path.exists(path):
                    raise FileNotFoundError(f"File not found: {path}")
                
                with open(path, "rb") as f:
                    data = f.read()
                
                stat = os.stat(path)
                
                logger.info(f"Downloaded file (filesystem): {path} ({stat.st_size} bytes)")
                
                return {
                    "success": True,
                    "data": data,
                    "content_type": "application/octet-stream",
                    "size": stat.st_size,
                    "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "filename": filename
                }
                
        except Exception as e:
            logger.error(f"Download failed for {filename}: {e}")
            raise

    async def list_project_files(self, project_id: str, category: str, 
                                suffix_filters: Optional[Tuple[str, ...]] = None) -> List[Dict[str, Any]]:
        """List files in project category with optional suffix filtering"""
        try:
            files = []
            
            if self.client:
                # MinIO/S3 listing
                prefix = self._get_storage_key(project_id, category, "")
                objects = self.client.list_objects(self.bucket, prefix=prefix, recursive=True)
                
                for obj in objects:
                    name = obj.object_name[len(prefix):]
                    if not name:
                        continue
                        
                    if suffix_filters and not name.lower().endswith(tuple(s.lower() for s in suffix_filters)):
                        continue
                    
                    files.append({
                        "filename": name,
                        "size": obj.size,
                        "last_modified": obj.last_modified.isoformat() if obj.last_modified else None,
                        "content_type": getattr(obj, 'content_type', 'application/octet-stream'),
                        "key": obj.object_name
                    })
            else:
                # Filesystem fallback
                root = os.path.join(self.local_root, f"project_{project_id}", category)
                
                if os.path.exists(root):
                    for f in os.listdir(root):
                        fpath = os.path.join(root, f)
                        if os.path.isfile(fpath):
                            if suffix_filters and not f.lower().endswith(tuple(s.lower() for s in suffix_filters)):
                                continue
                            
                            stat = os.stat(fpath)
                            files.append({
                                "filename": f,
                                "size": stat.st_size,
                                "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                                "content_type": "application/octet-stream",
                                "key": fpath
                            })
            
            logger.info(f"Listed {len(files)} files in project {project_id}/{category}")
            return files
            
        except Exception as e:
            logger.error(f"Failed to list files in {project_id}/{category}: {e}")
            raise

    async def delete_file(self, project_id: str, category: str, filename: str) -> Dict[str, Any]:
        """Delete file from storage"""
        try:
            if self.client:
                # MinIO/S3 delete
                key = self._get_storage_key(project_id, category, filename)
                self.client.remove_object(self.bucket, key)
                logger.info(f"Deleted file: {key}")
            else:
                # Filesystem delete
                path = os.path.join(self.local_root, f"project_{project_id}", category, filename)
                if os.path.exists(path):
                    os.unlink(path)
                    logger.info(f"Deleted file (filesystem): {path}")
                else:
                    raise FileNotFoundError(f"File not found: {path}")
            
            return {
                "success": True,
                "deleted_at": datetime.now().isoformat(),
                "filename": filename
            }
            
        except Exception as e:
            logger.error(f"Delete failed for {filename}: {e}")
            raise

    async def get_storage_stats(self, project_id: Optional[str] = None) -> Dict[str, Any]:
        """Get storage statistics for project or global"""
        try:
            stats = {
                "provider": self.provider,
                "bucket": self.bucket,
                "timestamp": datetime.now().isoformat()
            }
            
            if self.client:
                # MinIO/S3 stats
                if project_id:
                    prefix = f"projects/{project_id}/"
                    objects = self.client.list_objects(self.bucket, prefix=prefix, recursive=True)
                    total_size = 0
                    file_count = 0
                    
                    for obj in objects:
                        total_size += obj.size or 0
                        file_count += 1
                    
                    stats.update({
                        "project_id": project_id,
                        "total_files": file_count,
                        "total_size_bytes": total_size,
                        "total_size_mb": round(total_size / (1024 * 1024), 2)
                    })
                else:
                    # Global stats
                    objects = self.client.list_objects(self.bucket, recursive=True)
                    total_size = 0
                    file_count = 0
                    projects = set()
                    
                    for obj in objects:
                        total_size += obj.size or 0
                        file_count += 1
                        # Extract project ID from path
                        parts = obj.object_name.split('/')
                        if len(parts) >= 2 and parts[0] == 'projects':
                            projects.add(parts[1])
                    
                    stats.update({
                        "total_files": file_count,
                        "total_size_bytes": total_size,
                        "total_size_mb": round(total_size / (1024 * 1024), 2),
                        "total_projects": len(projects)
                    })
            else:
                # Filesystem stats
                stats["provider"] = "filesystem"
                stats["local_root"] = self.local_root
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")
            raise

    async def health_check(self) -> Dict[str, Any]:
        """Check storage service health"""
        try:
            if self.client:
                # Test bucket access
                bucket_exists = self.client.bucket_exists(self.bucket)
                return {
                    "status": "healthy",
                    "provider": self.provider,
                    "bucket": self.bucket,
                    "bucket_accessible": bucket_exists,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "status": "healthy",
                    "provider": "filesystem",
                    "local_root": self.local_root,
                    "root_accessible": os.path.exists(self.local_root),
                    "timestamp": datetime.now().isoformat()
                }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
