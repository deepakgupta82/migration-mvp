# New Upload and Processing Flow Models
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class UploadResponse(BaseModel):
    """Simple response for file upload without processing"""
    project_id: str
    uploaded_files: List[str]
    status: str = "uploaded"
    message: str
    upload_timestamp: str

class ProcessRequest(BaseModel):
    """Request for processing documents"""
    file_names: Optional[List[str]] = None  # If None, process all
    reprocess: bool = False
    
class ProcessResponse(BaseModel):
    """Response for processing requests"""
    project_id: str
    job_id: str
    status: str = "started"
    files_to_process: List[str]
    message: str
    started_at: str
