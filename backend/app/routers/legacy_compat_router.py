import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, File, UploadFile
from fastapi.responses import JSONResponse

# Import models for the new upload flow
from app.models.upload_models import UploadResponse

logger = logging.getLogger("platform.legacy_compat_router")

router = APIRouter(tags=["legacy-compat"])  # no prefix, legacy paths are absolute


@router.post(
    "/upload/{project_id}",
    response_model=UploadResponse,
    summary="Upload files to project storage (no processing)",
)
async def upload_files(project_id: str, request: Request):
    """
    Upload files to MinIO storage without immediate processing.
    This separates upload from processing for better UX control.
    
    The frontend can then:
    - Click "Process All" to process all uploaded files
    - Select specific files and click "Process Selected"
    """
    import tempfile
    import os
    from app.core.storage_service import get_storage
    
    logger.info(f"File upload request for project {project_id}")
    
    try:
        # Parse multipart form data
        form = await request.form()
        uploaded_files = []
        storage = get_storage()
        
        # Process each uploaded file
        for field_name, field_value in form.items():
            if hasattr(field_value, 'filename') and hasattr(field_value, 'file'):
                # This is a file upload
                file = field_value
                if not file.filename:
                    continue
                    
                logger.info(f"Uploading file: {file.filename}")
                
                # Read file content
                content = await file.read()
                
                # Upload to MinIO raw storage
                storage.upload_bytes(
                    project_id=project_id,
                    category="uploads_raw", 
                    filename=file.filename,
                    data=content,
                    content_type=file.content_type or "application/octet-stream"
                )
                
                uploaded_files.append(file.filename)
                logger.info(f"Successfully uploaded {file.filename} to MinIO storage")
        
        if not uploaded_files:
            return UploadResponse(
                project_id=project_id,
                uploaded_files=[],
                status="no_files",
                message="No files were uploaded",
                upload_timestamp=datetime.now().isoformat()
            )
        
        # Return success response
        return UploadResponse(
            project_id=project_id,
            uploaded_files=uploaded_files,
            status="uploaded",
            message=f"Successfully uploaded {len(uploaded_files)} file(s) to storage. Use processing endpoints to convert and index.",
            upload_timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Upload failed for project {project_id}: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Upload failed: {str(e)}"
        )


# --- Legacy LLM routes for compatibility with older frontends ---

@router.get(
    "/api/models/{provider}",
    summary="Legacy: list models for provider (static)",
)
async def legacy_list_models(provider: str, request: Request):
    """
    Legacy endpoint expected by older UI code.
    Returns a static list with the shape { status, models: [{id, name, description}], message }.
    """
    try:
        catalog = {
            "openai": [
                {"id": "gpt-4o", "name": "GPT-4o", "description": "OpenAI GPT-4o"},
                {"id": "gpt-4o-mini", "name": "GPT-4o mini", "description": "OpenAI GPT-4o mini"},
                {"id": "gpt-4.1", "name": "GPT-4.1", "description": "OpenAI GPT-4.1"},
                {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo", "description": "OpenAI GPT-3.5 Turbo"},
            ],
            "anthropic": [
                {"id": "claude-3-opus", "name": "Claude 3 Opus", "description": "Anthropic Claude 3 Opus"},
                {"id": "claude-3-sonnet", "name": "Claude 3 Sonnet", "description": "Anthropic Claude 3 Sonnet"},
                {"id": "claude-3-haiku", "name": "Claude 3 Haiku", "description": "Anthropic Claude 3 Haiku"},
            ],
            "gemini": [
                # Gemini 2.5 (latest)
                {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro", "description": "Google Gemini 2.5 Pro"},
                {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash", "description": "Google Gemini 2.5 Flash"},
                {"id": "gemini-2.5-flash-lite", "name": "Gemini 2.5 Flash Lite", "description": "Google Gemini 2.5 Flash Lite"},
                {"id": "gemini-2.5-flash-preview-05-20", "name": "Gemini 2.5 Flash Preview", "description": "Google Gemini 2.5 Flash Preview"},
                {"id": "gemini-live-2.5-flash-preview", "name": "Gemini 2.5 Flash Live", "description": "Google Gemini 2.5 Flash Live"},

                # Gemini 2.0
                {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash", "description": "Google Gemini 2.0 Flash"},
                {"id": "gemini-2.0-flash-001", "name": "Gemini 2.0 Flash (001)", "description": "Google Gemini 2.0 Flash (001)"},
                {"id": "gemini-2.0-flash-exp", "name": "Gemini 2.0 Flash (Experimental)", "description": "Google Gemini 2.0 Flash Experimental"},
                {"id": "gemini-2.0-flash-lite", "name": "Gemini 2.0 Flash Lite", "description": "Google Gemini 2.0 Flash Lite"},
                {"id": "gemini-2.0-flash-live-001", "name": "Gemini 2.0 Flash Live", "description": "Google Gemini 2.0 Flash Live (001)"},

                # Gemini 1.5 (deprecated but commonly referenced)
                {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro", "description": "Google Gemini 1.5 Pro (Deprecated)"},
                {"id": "gemini-1.5-pro-001", "name": "Gemini 1.5 Pro (001)", "description": "Google Gemini 1.5 Pro (001)"},
                {"id": "gemini-1.5-pro-002", "name": "Gemini 1.5 Pro (002)", "description": "Google Gemini 1.5 Pro (002)"},
                {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash", "description": "Google Gemini 1.5 Flash (Deprecated)"},
                {"id": "gemini-1.5-flash-001", "name": "Gemini 1.5 Flash (001)", "description": "Google Gemini 1.5 Flash (001)"},
                {"id": "gemini-1.5-flash-002", "name": "Gemini 1.5 Flash (002)", "description": "Google Gemini 1.5 Flash (002)"},
                {"id": "gemini-1.5-flash-8b", "name": "Gemini 1.5 Flash 8B", "description": "Google Gemini 1.5 Flash 8B (Deprecated)"},
            ],
            "azure": [
                {"id": "gpt-4o", "name": "GPT-4o (Azure)", "description": "Azure OpenAI GPT-4o"},
                {"id": "gpt-4o-mini", "name": "GPT-4o mini (Azure)", "description": "Azure OpenAI GPT-4o mini"},
            ],
            "ollama": [
                {"id": "llama3", "name": "Llama 3", "description": "Ollama Llama 3"},
                {"id": "mistral", "name": "Mistral", "description": "Ollama Mistral"},
                {"id": "codellama", "name": "Code Llama", "description": "Ollama Code Llama"},
                {"id": "phi3", "name": "Phi-3", "description": "Ollama Phi-3"},
            ],
        }
        models = catalog.get(provider.lower())
        if not models:
            return {
                "status": "error",
                "models": [],
                "message": f"Provider '{provider}' not supported",
            }
        return {
            "status": "success",
            "models": models,
            "message": "Static model catalog (no live provider call)",
        }
    except Exception as e:
        logging.getLogger("platform.legacy_compat_router").error(
            f"Legacy list models failed: {e}"
        )
        return {"status": "error", "models": [], "message": "Failed to list models"}


@router.post(
    "/api/test-llm-config",
    summary="Legacy: redirect to real LLM test endpoint",
)
async def legacy_test_llm_config(request: Request):
    """
    Legacy endpoint that now redirects to the real LLM testing endpoint
    in llm_router.py for actual LLM API testing instead of mock responses.
    """
    try:
        # Import the real test function
        from app.routers.llm_router import TestLLMConfigRequest, test_llm_config_post
        
        body = await request.json()
        
        # Transform legacy request to new format
        test_request = TestLLMConfigRequest(
            config_id=body.get("config_id"),
            provider=body.get("provider", ""),
            model=body.get("model", ""),
            api_key=body.get("api_key"),
            temperature=body.get("temperature", 0.1),
            max_tokens=body.get("max_tokens", 100),
            query=body.get("query", "Hello, please respond with 'LLM test successful' to confirm connectivity.")
        )
        
        # Call the real test endpoint
        return await test_llm_config_post(test_request)
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"LLM test failed: {str(e)}",
        }
        logging.getLogger("platform.legacy_compat_router").error(
            f"Legacy LLM test failed: {e}"
        )
        return {"status": "error", "message": "LLM config test failed"}
