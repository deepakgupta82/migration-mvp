import logging
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, UploadFile, File, Body, Request

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
    request: Request,
    files: Optional[List[UploadFile]] = File(None),
    body: Optional[Dict[str, Any]] = Body(default=None),
):
    """
    Backwards compatible endpoint for older frontends posting to `/upload/{project_id}`.
    Delegates to the new `/api/projects/{project_id}/process-documents` flow.

    Supports both multipart file uploads and JSON payloads.
    Accepts any common form field names (file, files, document, documents, uploads).
    """
    logger.info(
        f"Compat route invoked for project {project_id}: forwarding to process-documents"
    )

    # If FastAPI didn't bind to `files` (field name mismatch), extract UploadFiles from the raw form
    files_to_use: Optional[List[UploadFile]] = files
    if not files_to_use:
        try:
            form = await request.form()
            collected: List[UploadFile] = []
            for key, value in form.multi_items():
                # value can be UploadFile or str; also handle lists
                if isinstance(value, UploadFile):
                    collected.append(value)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, UploadFile):
                            collected.append(item)
            if collected:
                files_to_use = collected
        except Exception:
            # Fall back silently; the downstream will return a helpful 422 if empty
            pass

    return await process_project_documents(project_id, files=files_to_use, body=body)
