import logging
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Request

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
async def legacy_upload(project_id: str, request: Request):
    """
    Backwards compatible endpoint for older frontends posting to `/upload/{project_id}`.
    Delegates to the new `/api/projects/{project_id}/process-documents` flow.

    Important: Do not parse the request body here to avoid consuming the stream;
    the downstream processor will handle multipart and JSON bodies directly.
    """
    logger.info(
        f"Compat route invoked for project {project_id}: forwarding to process-documents"
    )
    return await process_project_documents(project_id, request)
