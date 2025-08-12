import logging
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, UploadFile, File, Body

# Import the existing processing endpoint to delegate work
from app.routers.project_analysis_router import (
    process_project_documents,
    ProcessDocumentsResponse,
)

logger = logging.getLogger("platform.legacy_compat_router")

router = APIRouter(tags=["legacy-compat"])  # no prefix, legacy paths are absolute


@router.post(
    "/upload/{project_id}",
    response_model=ProcessDocumentsResponse,
    summary="Legacy upload endpoint (compatibility)",
)
async def legacy_upload(
    project_id: str,
    files: Optional[List[UploadFile]] = File(None),
    body: Optional[Dict[str, Any]] = Body(default=None),
):
    """
    Backwards compatible endpoint for older frontends posting to `/upload/{project_id}`.
    Delegates to the new `/api/projects/{project_id}/process-documents` flow.

    Supports both multipart file uploads (field name: `files`) and JSON payloads
    `{ "files": [{"filename": "..."}] }`.
    """
    logger.info(
        f"Compat route invoked for project {project_id}: forwarding to process-documents"
    )
    return await process_project_documents(project_id, files=files, body=body)
