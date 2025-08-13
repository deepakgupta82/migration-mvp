import logging
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Request, HTTPException

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
    summary="Legacy: test LLM configuration (mock)",
)
async def legacy_test_llm_config(request: Request):
    """
    Legacy endpoint expected by older UI. Accepts JSON body with config info and
    returns a uniform success payload. This does not perform a live API call.
    """
    try:
        body = await request.json()
        provider = body.get("provider")
        model = body.get("model")
        test_query = body.get(
            "query",
            "Hello, please respond with 'LLM test successful' to confirm connectivity.",
        )
        if not provider or not model:
            return {
                "status": "error",
                "message": "Missing provider or model",
            }
        return {
            "status": "success",
            "provider": provider,
            "model": model,
            "echo": "LLM test successful",
            "response": "LLM test successful",  # duplicate for UI compatibility
            "query": test_query,
        }
    except Exception as e:
        logging.getLogger("platform.legacy_compat_router").error(
            f"Legacy LLM test failed: {e}"
        )
        return {"status": "error", "message": "LLM config test failed"}
