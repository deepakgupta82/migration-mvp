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
    """Upload documents to MinIO storage without processing"""
    try:
        # Import storage service
        import sys
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'backend'))
        from app.core.storage_service import get_storage
        
        storage = get_storage()
        uploaded_files = []
        
        for file in files:
            if not file.filename:
                continue
                
            # Save to temporary file
            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                content = await file.read()
                tmp_file.write(content)
                tmp_file_path = tmp_file.name
            
            try:
                # Upload to MinIO
                storage.upload(project_id, "uploads_raw", file.filename, tmp_file_path)
                uploaded_files.append({
                    "filename": file.filename,
                    "size": len(content),
                    "uploaded_at": datetime.now().isoformat()
                })
                logger.info(f"Uploaded {file.filename} to project {project_id}")
                
            finally:
                # Clean up temp file
                os.unlink(tmp_file_path)
        
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
    """List uploaded files and their processing status"""
    try:
        # Import storage service
        import sys
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'backend'))
        from app.core.storage_service import get_storage
        
        storage = get_storage()
        
        # Get raw uploaded files
        raw_files = storage.list_files(project_id, "uploads_raw")
        
        # Get processed files
        processed_files = storage.list_files(project_id, "uploads_parsed")
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
        # Import storage service
        import sys
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'backend'))
        from app.core.storage_service import get_storage
        
        storage = get_storage()
        uploaded_files = storage.list_files(project_id, "uploads_raw")
        
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
        # Import storage service
        import sys
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'backend'))
        from app.core.storage_service import get_storage
        
        storage = get_storage()
        uploaded_files = storage.list_files(project_id, "uploads_raw")
        
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
    """Background task to process files"""
    logger.info(f"Background processing started for job {job_id}: {len(file_names)} files")
    
    try:
        # Import storage service
        import sys
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'backend'))
        from app.core.storage_service import get_storage
        
        storage = get_storage()
        processed_count = 0
        failed_count = 0
        files_status = []
        
        for filename in file_names:
            try:
                # Update current processing status
                await processor.update_processing_status(project_id, job_id, {
                    "current_file": filename,
                    "processed_files": processed_count,
                    "failed_files": failed_count
                })
                
                # Download file from storage
                obj, content_type, size = storage.download(project_id, "uploads_raw", filename)
                
                # Save to temporary file
                with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                    data = obj.read()
                    tmp_file.write(data)
                    tmp_file_path = tmp_file.name
                
                try:
                    obj.close()
                except Exception:
                    pass
                
                try:
                    # Process the document
                    result = await processor.convert_document_to_markdown(
                        tmp_file_path, filename, project_id, reprocess
                    )
                    
                    # Save processed markdown to storage
                    if result.get("content"):
                        md_filename = result["md_filename"]
                        
                        # Save to temporary markdown file
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as md_file:
                            md_file.write(result["content"])
                            md_file_path = md_file.name
                        
                        try:
                            # Upload processed markdown to MinIO
                            storage.upload(project_id, "uploads_parsed", md_filename, md_file_path)
                            
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
                            
                            import json
                            metadata_filename = os.path.splitext(filename)[0] + "_metadata.json"
                            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as meta_file:
                                json.dump(metadata, meta_file, indent=2)
                                meta_file_path = meta_file.name
                            
                            try:
                                storage.upload(project_id, "metadata", metadata_filename, meta_file_path)
                            finally:
                                os.unlink(meta_file_path)
                            
                        finally:
                            os.unlink(md_file_path)
                    
                    processed_count += 1
                    files_status.append(FileStatus(
                        filename=filename,
                        status="success",
                        conversion_strategy=result.get("conversion_strategy"),
                        timestamp=result.get("timestamp")
                    ))
                    
                    logger.info(f"Successfully processed {filename} for project {project_id}")
                    
                    # Broadcast WebSocket message
                    try:
                        # Import WebSocket manager
                        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'backend'))
                        from app.core.process_ws import get_process_ws_manager
                        asyncio.create_task(
                            get_process_ws_manager().broadcast(
                                project_id, 
                                f"CONVERTED_TO_MD: {filename} → {result['md_filename']}"
                            )
                        )
                    except Exception as ws_e:
                        logger.warning(f"WebSocket broadcast failed: {ws_e}")
                    
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
