#!/usr/bin/env python3
"""
Storage Service Router - API endpoints for object storage operations
Handles file upload, download, listing, and management via MinIO/S3
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Query, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import logging
import io

from ..core.storage_processor import StorageProcessor

logger = logging.getLogger("storage-service.router")

# Initialize processor
storage_processor = StorageProcessor()

# Dependency function for FastAPI
def get_storage_processor() -> "StorageProcessor":
    """Get the global storage processor instance"""
    return storage_processor

# Create router
router = APIRouter(tags=["storage"])

# Pydantic models for request/response
class UploadResponse(BaseModel):
    success: bool
    key: str
    size: int
    content_type: str
    uploaded_at: str

class FileInfo(BaseModel):
    filename: str
    size: int
    last_modified: Optional[str]
    content_type: str
    key: str

class StorageStats(BaseModel):
    provider: str
    bucket: str
    timestamp: str
    total_files: Optional[int] = None
    total_size_bytes: Optional[int] = None
    total_size_mb: Optional[float] = None
    total_projects: Optional[int] = None

class HealthResponse(BaseModel):
    status: str
    provider: str
    bucket: Optional[str] = None
    local_root: Optional[str] = None
    bucket_accessible: Optional[bool] = None
    root_accessible: Optional[bool] = None
    timestamp: str

class TextUploadRequest(BaseModel):
    content: str = Field(..., description="Text content to upload")
    content_type: Optional[str] = Field("text/plain; charset=utf-8", description="Content type")

# Health check endpoint
@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Storage service health check"""
    try:
        health_data = await storage_processor.health_check()
        return HealthResponse(**health_data)
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

# File upload endpoints
@router.post("/projects/{project_id}/upload/{category}")
async def upload_files(
    project_id: str,
    category: str,
    files: List[UploadFile] = File(...)
):
    """Upload multiple files to project storage"""
    try:
        uploaded_files = []
        
        for file in files:
            if not file.filename:
                continue
            
            # Read file content
            content = await file.read()
            
            # Upload file
            result = await storage_processor.upload_file_bytes(
                project_id=project_id,
                category=category,
                filename=file.filename,
                data=content,
                content_type=file.content_type
            )
            
            uploaded_files.append(result)
            logger.info(f"Uploaded {file.filename} to {project_id}/{category}")
        
        return {
            "project_id": project_id,
            "category": category,
            "uploaded_files": uploaded_files,
            "total_uploaded": len(uploaded_files)
        }
        
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.post("/projects/{project_id}/upload-text/{category}")
async def upload_text_content(
    project_id: str,
    category: str,
    filename: str,
    request: TextUploadRequest
):
    """Upload text content to project storage"""
    try:
        result = await storage_processor.upload_text_content(
            project_id=project_id,
            category=category,
            filename=filename,
            text=request.content,
            content_type=request.content_type
        )
        
        logger.info(f"Uploaded text content {filename} to {project_id}/{category}")
        return result
        
    except Exception as e:
        logger.error(f"Text upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Text upload failed: {str(e)}")

# File download endpoint
@router.get("/projects/{project_id}/download/{category}/{filename}")
async def download_file(project_id: str, category: str, filename: str):
    """Download file from project storage"""
    try:
        result = await storage_processor.download_file(project_id, category, filename)
        
        # Create streaming response
        file_stream = io.BytesIO(result["data"])
        
        return StreamingResponse(
            io.BytesIO(result["data"]),
            media_type=result["content_type"],
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Length": str(result["size"])
            }
        )
        
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")
    except Exception as e:
        logger.error(f"Download failed: {e}")
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

# File listing endpoint
@router.get("/projects/{project_id}/files/{category}")
async def list_project_files(
    project_id: str,
    category: str,
    suffix_filter: Optional[str] = Query(None, description="Comma-separated file extensions to filter (e.g., 'pdf,docx')")
):
    """List files in project category"""
    try:
        # Parse suffix filter
        suffix_filters = None
        if suffix_filter:
            suffix_filters = tuple(ext.strip().lower() for ext in suffix_filter.split(','))
        
        files = await storage_processor.list_project_files(
            project_id=project_id,
            category=category,
            suffix_filters=suffix_filters
        )
        
        return {
            "project_id": project_id,
            "category": category,
            "files": files,
            "total_files": len(files),
            "suffix_filter": suffix_filters
        }
        
    except Exception as e:
        logger.error(f"File listing failed: {e}")
        raise HTTPException(status_code=500, detail=f"File listing failed: {str(e)}")

# File deletion endpoint
@router.delete("/projects/{project_id}/files/{category}/{filename}")
async def delete_file(project_id: str, category: str, filename: str):
    """Delete file from project storage"""
    try:
        result = await storage_processor.delete_file(project_id, category, filename)
        logger.info(f"Deleted file {filename} from {project_id}/{category}")
        return result
        
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")
    except Exception as e:
        logger.error(f"Delete failed: {e}")
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")

# Storage statistics
@router.get("/projects/{project_id}/stats")
async def get_project_storage_stats(project_id: str):
    """Get storage statistics for specific project"""
    try:
        stats = await storage_processor.get_storage_stats(project_id=project_id)
        return stats
    except Exception as e:
        logger.error(f"Failed to get project stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get project stats: {str(e)}")

@router.get("/stats/global")
async def get_global_storage_stats():
    """Get global storage statistics"""
    try:
        stats = await storage_processor.get_storage_stats()
        return stats
    except Exception as e:
        logger.error(f"Failed to get global stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get global stats: {str(e)}")

# Storage categories endpoint
@router.get("/categories")
async def get_storage_categories():
    """Get available storage categories"""
    return {
        "categories": [
            {
                "name": "uploads_raw",
                "description": "Raw uploaded files before processing",
                "path_pattern": "projects/{project_id}/uploads/raw/"
            },
            {
                "name": "uploads_parsed", 
                "description": "Parsed/processed uploaded files",
                "path_pattern": "projects/{project_id}/uploads/parsed/"
            },
            {
                "name": "uploads_canonical",
                "description": "Canonical processed files (markdown)",
                "path_pattern": "projects/{project_id}/uploads/canonical/"
            },
            {
                "name": "structured",
                "description": "Structured JSONL files from enhanced document processing",
                "path_pattern": "projects/{project_id}/structured/"
            },
            {
                "name": "generated_reports",
                "description": "Generated assessment reports",
                "path_pattern": "projects/{project_id}/generated/reports/"
            },
            {
                "name": "logs_processing",
                "description": "Processing logs and debug information",
                "path_pattern": "projects/{project_id}/logs/processing/"
            },
            {
                "name": "metadata",
                "description": "File metadata and processing information",
                "path_pattern": "projects/{project_id}/metadata/"
            }
        ],
        "total_categories": 7
    }

# Cleanup endpoints
@router.post("/projects/{project_id}/cleanup/{category}")
async def cleanup_category(project_id: str, category: str, background_tasks: BackgroundTasks):
    """Delete all files in project category (background task)"""
    try:
        async def cleanup_files():
            files = await storage_processor.list_project_files(project_id, category)
            deleted_count = 0
            
            for file_info in files:
                try:
                    await storage_processor.delete_file(project_id, category, file_info["filename"])
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"Failed to delete {file_info['filename']}: {e}")
            
            logger.info(f"Cleanup completed for {project_id}/{category}: {deleted_count} files deleted")
        
        background_tasks.add_task(cleanup_files)
        
        return {
            "message": f"Cleanup task started for {project_id}/{category}",
            "status": "background_task_queued"
        }
        
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")

# Debug endpoints
@router.get("/debug/bucket-info")
async def get_bucket_info():
    """Get detailed bucket information for debugging"""
    try:
        health_data = await storage_processor.health_check()
        global_stats = await storage_processor.get_storage_stats()
        
        return {
            "health": health_data,
            "global_stats": global_stats,
            "provider_info": {
                "provider": storage_processor.provider,
                "bucket": storage_processor.bucket,
                "client_type": type(storage_processor.client).__name__ if storage_processor.client else "filesystem"
            }
        }
    except Exception as e:
        logger.error(f"Debug info failed: {e}")
        raise HTTPException(status_code=500, detail=f"Debug info failed: {str(e)}")

@router.get("/debug/project-structure/{project_id}")
async def get_project_structure(project_id: str):
    """Get complete project storage structure for debugging"""
    try:
        structure = {}
        categories = ["uploads_raw", "uploads_parsed", "uploads_canonical", 
                     "structured", "generated_reports", "logs_processing", "metadata"]
        
        for category in categories:
            try:
                files = await storage_processor.list_project_files(project_id, category)
                structure[category] = {
                    "file_count": len(files),
                    "files": files[:10] if len(files) > 10 else files,  # Limit to 10 for debugging
                    "truncated": len(files) > 10
                }
            except Exception as e:
                structure[category] = {"error": str(e)}
        
        return {
            "project_id": project_id,
            "structure": structure,
            "timestamp": storage_processor.__class__.__name__
        }
        
    except Exception as e:
        logger.error(f"Project structure debug failed: {e}")
        raise HTTPException(status_code=500, detail=f"Project structure debug failed: {str(e)}")

@router.delete("/projects/{project_id}/documents/{filename}", summary="Delete document and related files")
async def delete_document_and_related(
    project_id: str,
    filename: str,
    storage_processor=Depends(get_storage_processor)
):
    """Delete a document and all related files (.md, .json, etc.)"""
    try:
        result = await storage_processor.delete_document_and_related(project_id, filename)
        logger.info(f"Deleted document and related files: {result.get('deleted_files', [])}")
        return result
        
    except Exception as e:
        logger.error(f"Failed to delete document {filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")
