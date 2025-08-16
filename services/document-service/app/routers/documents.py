"""
Document Processing Router
Handles document upload, processing, and status endpoints
"""

from fastapi import APIRouter, HTTPException, Form, File, UploadFile, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import List, Optional
import uuid
import tempfile
import os
import logging
from datetime import datetime
import asyncio

from ..core.document_processor import DocumentProcessor

logger = logging.getLogger("document-service.router")
router = APIRouter()

# Initialize document processor
processor = DocumentProcessor()

# Pydantic models for request/response
from pydantic import BaseModel

class ProcessRequest(BaseModel):
    file_names: Optional[List[str]] = None
    reprocess: bool = False

class ProcessResponse(BaseModel):
    project_id: str
    job_id: str
    status: str
    files_to_process: List[str]
    message: str
    started_at: str

class FileStatus(BaseModel):
    filename: str
    status: str
    conversion_strategy: Optional[str] = None
    timestamp: Optional[str] = None
    error: Optional[str] = None

class ProcessingStatus(BaseModel):
    project_id: str
    job_id: str
    status: str
    total_files: int
    processed_files: int
    failed_files: int
    current_file: Optional[str] = None
    files_status: List[FileStatus] = []
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    last_updated: Optional[str] = None

@router.post("/{project_id}/upload")
async def upload_documents(
    project_id: str,
    files: List[UploadFile] = File(...)
):
    """Upload documents to Storage Service (port 8010)"""
    try:
        import httpx
        
        uploaded_files = []
        
        # Create HTTP client to call Storage Service
        async with httpx.AsyncClient() as client:
            for file in files:
                if not file.filename:
                    continue
                
                # Read file content
                content = await file.read()
                
                # Prepare multipart form data for Storage Service
                files_data = {
                    'files': (file.filename, content, file.content_type or 'application/octet-stream')
                }
                
                # Call Storage Service upload endpoint
                storage_response = await client.post(
                    f"http://localhost:8010/api/storage/projects/{project_id}/upload/uploads_raw",
                    files=files_data,
                    headers={
                        "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
                    }
                )
                
                if storage_response.status_code == 200:
                    uploaded_files.append({
                        "filename": file.filename,
                        "size": len(content),
                        "uploaded_at": datetime.now().isoformat()
                    })
                    logger.info(f"Uploaded {file.filename} to project {project_id}")
                else:
                    logger.error(f"Storage service upload failed for {file.filename}: {storage_response.status_code}")
                    raise HTTPException(
                        status_code=500, 
                        detail=f"Storage service upload failed: {storage_response.status_code}"
                    )
        
        return {
            "project_id": project_id,
            "uploaded_files": uploaded_files,
            "total_uploaded": len(uploaded_files),
            "message": f"Successfully uploaded {len(uploaded_files)} files"
        }
        
    except Exception as e:
        logger.error(f"Upload failed for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.get("/{project_id}/files")
async def list_uploaded_files(project_id: str):
    """List uploaded files via Storage Service"""
    try:
        import httpx
        
        # Call Storage Service to list files
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://localhost:8010/api/storage/projects/{project_id}/files/uploads_raw",
                headers={
                    "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
                }
            )
            
            if response.status_code == 200:
                storage_result = response.json()
                raw_files = [f["filename"] for f in storage_result.get("files", [])]
            else:
                raw_files = []
            
            # Get processed files
            processed_response = await client.get(
                f"http://localhost:8010/api/storage/projects/{project_id}/files/uploads_parsed",
                headers={
                    "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
                }
            )
            
            if processed_response.status_code == 200:
                processed_result = processed_response.json()
                processed_files = [f["filename"] for f in processed_result.get("files", [])]
            else:
                processed_files = []
                
        processed_base_names = {f.rsplit('.', 1)[0] for f in processed_files if '.' in f}
        
        # Categorize files
        pending_files = []
        completed_files = []
        
        for filename in raw_files:
            base_name = filename.rsplit('.', 1)[0] if '.' in filename else filename
            if base_name in processed_base_names:
                completed_files.append(filename)
            else:
                pending_files.append(filename)
        
        return {
            "project_id": project_id,
            "uploaded_files": raw_files,
            "processed_files": completed_files,
            "pending_files": pending_files,
            "counts": {
                "total_uploaded": len(raw_files),
                "processed": len(completed_files),
                "pending": len(pending_files)
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to list files for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")

@router.post("/{project_id}/process-all", response_model=ProcessResponse)
async def process_all_documents(
    project_id: str, 
    background_tasks: BackgroundTasks,
    request_data: ProcessRequest = ProcessRequest()
):
    """Process all uploaded documents"""
    try:
        # Call Storage Service to get uploaded files (NO BACKEND IMPORTS!)
        import httpx
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://localhost:8010/api/storage/projects/{project_id}/files/uploads_raw",
                headers={
                    "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
                }
            )
            
            if response.status_code == 200:
                storage_result = response.json()
                uploaded_files = [f["filename"] for f in storage_result.get("files", [])]
            else:
                uploaded_files = []
        
        if not uploaded_files:
            raise HTTPException(status_code=404, detail="No uploaded files found for processing")
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        logger.info(f"Starting processing job {job_id} for project {project_id}: {len(uploaded_files)} files")
        
        # Initialize processing status
        await processor.update_processing_status(project_id, job_id, {
            "status": "started",
            "total_files": len(uploaded_files),
            "processed_files": 0,
            "failed_files": 0,
            "files_to_process": uploaded_files,
            "started_at": datetime.now().isoformat()
        })
        
        # Start background processing
        background_tasks.add_task(
            _process_files_background, 
            project_id, 
            uploaded_files, 
            request_data.reprocess, 
            job_id
        )
        
        return ProcessResponse(
            project_id=project_id,
            job_id=job_id,
            status="started",
            files_to_process=uploaded_files,
            message=f"Started processing {len(uploaded_files)} files in background",
            started_at=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Failed to start processing for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start processing: {str(e)}")

@router.post("/{project_id}/process-selected", response_model=ProcessResponse)
async def process_selected_documents(
    project_id: str,
    background_tasks: BackgroundTasks,
    request_data: ProcessRequest
):
    """Process selected documents"""
    if not request_data.file_names:
        raise HTTPException(status_code=400, detail="No files specified for processing")
    
    try:
        # Call Storage Service to verify files exist (NO BACKEND IMPORTS!)
        import httpx
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://localhost:8010/api/storage/projects/{project_id}/files/uploads_raw",
                headers={
                    "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
                }
            )
            
            if response.status_code == 200:
                storage_result = response.json()
                uploaded_files = [f["filename"] for f in storage_result.get("files", [])]
            else:
                uploaded_files = []
        
        # Verify selected files exist
        missing_files = [f for f in request_data.file_names if f not in uploaded_files]
        if missing_files:
            raise HTTPException(
                status_code=404, 
                detail=f"Files not found: {', '.join(missing_files)}"
            )
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        logger.info(f"Starting selective processing job {job_id} for project {project_id}: {len(request_data.file_names)} files")
        
        # Initialize processing status
        await processor.update_processing_status(project_id, job_id, {
            "status": "started",
            "total_files": len(request_data.file_names),
            "processed_files": 0,
            "failed_files": 0,
            "files_to_process": request_data.file_names,
            "started_at": datetime.now().isoformat()
        })
        
        # Start background processing
        background_tasks.add_task(
            _process_files_background, 
            project_id, 
            request_data.file_names, 
            request_data.reprocess, 
            job_id
        )
        
        return ProcessResponse(
            project_id=project_id,
            job_id=job_id,
            status="started",
            files_to_process=request_data.file_names,
            message=f"Started processing {len(request_data.file_names)} selected files",
            started_at=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Failed to start selective processing for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start processing: {str(e)}")

@router.get("/{project_id}/status/{job_id}", response_model=ProcessingStatus)
async def get_processing_status(project_id: str, job_id: str):
    """Get processing status for a job"""
    try:
        status = await processor.get_processing_status(project_id, job_id)
        
        if status.get("status") == "not_found":
            raise HTTPException(status_code=404, detail="Processing job not found")
        
        return ProcessingStatus(**status)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get processing status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")

async def _process_files_background(project_id: str, file_names: List[str], reprocess: bool, job_id: str):
    """Background task to process files - FIXED to use HTTP calls instead of imports"""
    logger.info(f"Background processing started for job {job_id}: {len(file_names)} files")
    
    try:
        # Use HTTP calls to Storage Service instead of direct imports
        import httpx
        import json
        
        processed_count = 0
        failed_count = 0
        files_status = []
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            for filename in file_names:
                try:
                    # Update current processing status
                    await processor.update_processing_status(project_id, job_id, {
                        "current_file": filename,
                        "processed_files": processed_count,
                        "failed_files": failed_count
                    })
                    
                    # Download file from Storage Service
                    download_response = await client.get(
                        f"http://localhost:8010/api/storage/projects/{project_id}/download/uploads_raw/{filename}",
                        headers={
                            "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
                        }
                    )
                    
                    if download_response.status_code != 200:
                        raise Exception(f"Failed to download file from storage: {download_response.status_code}")
                    
                    # Save to temporary file
                    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                        tmp_file.write(download_response.content)
                        tmp_file_path = tmp_file.name
                    
                    try:
                        # Process the document using DocumentProcessor
                        result = await processor.convert_document_to_markdown(
                            tmp_file_path, filename, project_id, reprocess
                        )
                        
                        # Upload processed markdown back to Storage Service
                        if result.get("content"):
                            md_filename = result["md_filename"]
                            
                            # Upload processed markdown
                            files_data = {
                                'files': (md_filename, result["content"].encode('utf-8'), 'text/markdown')
                            }
                            
                            upload_response = await client.post(
                                f"http://localhost:8010/api/storage/projects/{project_id}/upload/uploads_parsed",
                                files=files_data,
                                headers={
                                    "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
                                }
                            )
                            
                            if upload_response.status_code != 200:
                                logger.warning(f"Failed to upload processed markdown: {upload_response.status_code}")
                            
                            # Save metadata
                            metadata = {
                                "original_filename": filename,
                                "md_filename": md_filename,
                                "conversion_strategy": result.get("conversion_strategy"),
                                "timestamp": result.get("timestamp"),
                                "file_size": result.get("file_size"),
                                "content_length": result.get("content_length"),
                                "status": result.get("status")
                            }
                            
                            metadata_filename = os.path.splitext(filename)[0] + "_metadata.json"
                            metadata_json = json.dumps(metadata, indent=2)
                            
                            # Upload metadata to Storage Service
                            metadata_files_data = {
                                'files': (metadata_filename, metadata_json.encode('utf-8'), 'application/json')
                            }
                            
                            metadata_response = await client.post(
                                f"http://localhost:8010/api/storage/projects/{project_id}/upload/metadata",
                                files=metadata_files_data,
                                headers={
                                    "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
                                }
                            )
                            
                            if metadata_response.status_code != 200:
                                logger.warning(f"Failed to upload metadata: {metadata_response.status_code}")
                        
                        processed_count += 1
                        files_status.append(FileStatus(
                            filename=filename,
                            status="success",
                            conversion_strategy=result.get("conversion_strategy"),
                            timestamp=result.get("timestamp")
                        ))
                        
                        logger.info(f"Successfully processed {filename} for project {project_id}")
                        
                        # Note: WebSocket broadcasting will be handled by other services
                        # Document Service should focus only on document processing
                        
                    finally:
                        # Clean up temp file
                        os.unlink(tmp_file_path)
                
                except Exception as e:
                    failed_count += 1
                    files_status.append(FileStatus(
                        filename=filename,
                        status="error",
                        error=str(e),
                        timestamp=datetime.now().isoformat()
                    ))
                    logger.error(f"Failed to process {filename}: {e}")
        
        # Update final status
        await processor.update_processing_status(project_id, job_id, {
            "status": "completed" if failed_count == 0 else "completed_with_errors",
            "processed_files": processed_count,
            "failed_files": failed_count,
            "files_status": [status.dict() for status in files_status],
            "completed_at": datetime.now().isoformat(),
            "current_file": None
        })
        
        logger.info(f"Background processing completed for job {job_id}: {processed_count} success, {failed_count} failed")
        
    except Exception as e:
        logger.error(f"Background processing failed for job {job_id}: {e}")
        
        # Update error status
        await processor.update_processing_status(project_id, job_id, {
            "status": "failed",
            "error": str(e),
            "completed_at": datetime.now().isoformat()
        })
