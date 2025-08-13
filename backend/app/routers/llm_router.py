from fastapi import APIRouter, HTTPException, Query
# ...existing code...

# Placeholder for crew config REST router import
# from app.api.routers import crew_config_router

import logging
# Replace legacy llm_config import with unified project_service cache
from app.core.project_service import get_llm_configurations_from_db as unified_get_llm_configs
from app.core.project_service import invalidate_llm_cache as unified_invalidate_llm_cache
from app.core.project_service import get_project_service
import requests, os

logger = logging.getLogger("platform.llm_router")

router = APIRouter(prefix="/api/llm", tags=["llm"])

@router.get("/configurations", summary="Get all LLM configurations")
async def get_llm_configurations():
    try:
        llm_configs = unified_get_llm_configs()
        configs = []
        for config_id, config in llm_configs.items():
            configs.append({
                "id": config_id,
                "name": config.get('name', 'Unknown'),
                "provider": config.get('provider', 'unknown'),
                "model": config.get('model', 'unknown'),
                "status": "configured" if config.get('api_key') and config.get('api_key') != 'your-api-key-here' else "needs_key"
            })
        return configs
    except Exception as e:
        logger.error(f"Error getting LLM configurations: {str(e)}")
        return []

@router.post("/configurations", summary="Create a new LLM configuration")
async def create_llm_configuration(request: dict):
    try:
        if not request.get('name'):
            raise HTTPException(status_code=400, detail="Name is required for LLM configuration")
        if not request.get('provider'):
            raise HTTPException(status_code=400, detail="Provider is required")
        if not request.get('model'):
            raise HTTPException(status_code=400, detail="Model is required")
        project_service = get_project_service()
        response = requests.post(
            f"{project_service.base_url}/llm-configurations",
            json={
                "name": request.get('name', ''),
                "provider": request.get('provider', ''),
                "model": request.get('model', ''),
                "api_key": request.get('api_key', ''),
                "temperature": str(request.get('temperature', 0.1)),
                "max_tokens": str(request.get('max_tokens', 4000)),
                "description": request.get('description', f"{request.get('name', '')} - {request.get('provider', '')}/{request.get('model', '')}")
            },
            headers=project_service._get_auth_headers()
        )
        if response.status_code == 201:
            config = response.json()
            unified_invalidate_llm_cache()
            logger.info(f"Created LLM configuration: {config['name']} ({config['id']})")
            return config
        else:
            raise HTTPException(status_code=response.status_code, detail=f"Failed to create configuration: {response.text}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating LLM configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create LLM configuration: {str(e)}")

@router.put("/configurations/{config_id}", summary="Update an LLM configuration")
async def update_llm_configuration(config_id: str, request: dict):
    try:
        project_service = get_project_service()
        response = requests.put(
            f"{project_service.base_url}/llm-configurations/{config_id}",
            json=request,
            headers=project_service._get_auth_headers()
        )
        if response.status_code == 200:
            config = response.json()
            unified_invalidate_llm_cache()
            logger.info(f"Updated LLM configuration: {config_id}")
            return config
        else:
            raise HTTPException(status_code=response.status_code, detail=f"Failed to update configuration: {response.text}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating LLM configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update LLM configuration: {str(e)}")

@router.delete("/configurations/{config_id}", summary="Delete an LLM configuration")
async def delete_llm_configuration(config_id: str):
    try:
        project_service = get_project_service()
        response = requests.delete(
            f"{project_service.base_url}/llm-configurations/{config_id}",
            headers=project_service._get_auth_headers()
        )
        if response.status_code == 200:
            result = response.json()
            unified_invalidate_llm_cache()
            logger.info(f"Deleted LLM configuration: {config_id}")
            return result
        else:
            raise HTTPException(status_code=response.status_code, detail=f"Failed to delete configuration: {response.text}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting LLM configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete LLM configuration: {str(e)}")

@router.get("/test-llm-config", summary="Test connectivity of default or specified LLM configuration")
async def test_llm_config(config_id: str = Query(None), test_query: str = Query("Hello, please respond with 'LLM test successful' to confirm connectivity.")):
    try:
        configs = unified_get_llm_configs()
        if not configs:
            raise HTTPException(status_code=404, detail="No LLM configurations available")
        cfg = None
        if config_id:
            cfg = configs.get(config_id)
            if not cfg:
                raise HTTPException(status_code=404, detail="Config not found")
        else:
            cfg = list(configs.values())[0]
        provider = cfg.get('provider')
        model = cfg.get('model')
        api_key = cfg.get('api_key')
        logger.info(f"Testing LLM config: provider={provider}, model={model}, api_key={'***' if api_key else None}")
        if not provider or not model or not api_key:
            raise HTTPException(status_code=400, detail="Configuration missing provider/model/api_key")
        # Test OpenAI connectivity
        if provider == "openai":
            import requests
            headers = {"Authorization": f"Bearer {api_key}"}
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": test_query}],
                "max_tokens": 32
            }
            resp = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=15)
            logger.info(f"OpenAI test response: status={resp.status_code}, body={resp.text[:200]}")
            if resp.ok:
                data = resp.json()
                reply = data["choices"][0]["message"]["content"] if data.get("choices") else ""
                return {"status": "ok", "provider": provider, "model": model, "reply": reply}
            else:
                raise HTTPException(status_code=resp.status_code, detail=f"OpenAI API error: {resp.text}")
        # Add similar test logic for other providers if needed
        return {"status": "ok", "provider": provider, "model": model}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"LLM config test failed: {e}")
        raise HTTPException(status_code=500, detail=f"LLM config test failed: {e}")

@router.get("/models/{provider}", summary="List available models for provider (dynamic if possible)")
async def list_provider_models(provider: str, api_key: str = Query(None)):
    try:
        provider = provider.lower()
        models = []
        if provider == "openai" and api_key:
            import requests
            headers = {"Authorization": f"Bearer {api_key}"}
            resp = requests.get("https://api.openai.com/v1/models", headers=headers, timeout=10)
            if resp.ok:
                data = resp.json()
                models = [m["id"] for m in data.get("data", []) if m.get("id")]
            else:
                raise HTTPException(status_code=resp.status_code, detail=f"OpenAI API error: {resp.text}")
        elif provider == "anthropic":
            models = ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"]
        elif provider == "gemini":
            models = [
                "gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-flash-preview-05-20",
                "gemini-live-2.5-flash-preview", "gemini-2.0-flash", "gemini-2.0-flash-001", "gemini-2.0-flash-exp",
                "gemini-2.0-flash-lite", "gemini-2.0-flash-live-001", "gemini-1.5-pro", "gemini-1.5-pro-001",
                "gemini-1.5-pro-002", "gemini-1.5-flash", "gemini-1.5-flash-001", "gemini-1.5-flash-002", "gemini-1.5-flash-8b"
            ]
        elif provider == "azure":
            models = ["gpt-4o", "gpt-4o-mini"]
        elif provider == "ollama":
            import requests
            resp = requests.get("http://localhost:11434/api/tags", timeout=5)
            if resp.ok:
                data = resp.json()
                models = [m["name"] for m in data.get("models", []) if m.get("name")]
        else:
            raise HTTPException(status_code=404, detail="Provider not supported")
        return {"provider": provider, "models": models}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"List models failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to list models")
