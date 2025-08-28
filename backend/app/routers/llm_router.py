from fastapi import APIRouter, HTTPException, Query
from typing import Optional
# ...existing code...

# Placeholder for crew config REST router import
# from app.api.routers import crew_config_router

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
# Replace legacy llm_config import with unified project_service cache
from app.core.project_service import get_llm_configurations_from_db as unified_get_llm_configs
from app.core.project_service import invalidate_llm_cache as unified_invalidate_llm_cache
from app.core.project_service import get_project_service
import requests, os

logger = logging.getLogger("platform.llm_router")

router = APIRouter(prefix="/api/llm", tags=["llm"])

# Simple in-memory cache for models (in production, use Redis or similar)
_models_cache: Dict[str, Dict] = {}

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
    correlation_id = f"llm-create-{datetime.now().isoformat()}-{os.urandom(4).hex()}"
    logger.info(f"🔧 [LLM_CREATE][{correlation_id}] Starting LLM configuration creation")
    logger.info(f"🔧 [LLM_CREATE][{correlation_id}] Request data: {dict(request, api_key='***' if request.get('api_key') else None)}")
    
    try:
        if not request.get('name'):
            error_msg = "Name is required for LLM configuration"
            logger.error(f"❌ [LLM_CREATE][{correlation_id}] {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)
        if not request.get('provider'):
            error_msg = "Provider is required"
            logger.error(f"❌ [LLM_CREATE][{correlation_id}] {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)
        if not request.get('model'):
            error_msg = "Model is required"
            logger.error(f"❌ [LLM_CREATE][{correlation_id}] {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)
            
        project_service = get_project_service()
        payload = {
            "name": request.get('name', ''),
            "provider": request.get('provider', ''),
            "model": request.get('model', ''),
            "api_key": request.get('api_key', ''),
            "temperature": str(request.get('temperature', 0.1)),
            "max_tokens": str(request.get('max_tokens', 4000)),
            "description": request.get('description', f"{request.get('name', '')} - {request.get('provider', '')}/{request.get('model', '')}")
        }
        
        logger.info(f"🔧 [LLM_CREATE][{correlation_id}] Calling project service: {project_service.base_url}/llm-configurations")
        logger.info(f"🔧 [LLM_CREATE][{correlation_id}] Payload: {dict(payload, api_key='***' if payload.get('api_key') else None)}")
        
        response = requests.post(
            f"{project_service.base_url}/llm-configurations",
            json=payload,
            headers=project_service._get_auth_headers(),
            timeout=15  # 15 second timeout to prevent hanging
        )
        
        logger.info(f"🔧 [LLM_CREATE][{correlation_id}] Project service response: status={response.status_code}")
        
        if response.status_code == 201:
            config = response.json()
            unified_invalidate_llm_cache()
            logger.info(f"✅ [LLM_CREATE][{correlation_id}] Created LLM configuration: {config.get('name')} ({config.get('id')})")
            return config
        else:
            error_text = response.text
            logger.error(f"❌ [LLM_CREATE][{correlation_id}] Project service error: {response.status_code} - {error_text}")
            raise HTTPException(status_code=response.status_code, detail=f"Failed to create configuration: {error_text}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [LLM_CREATE][{correlation_id}] Unexpected error: {str(e)}")
        logger.exception(f"❌ [LLM_CREATE][{correlation_id}] Full exception details:")
        raise HTTPException(status_code=500, detail=f"Failed to create LLM configuration: {str(e)}")

@router.put("/configurations/{config_id}", summary="Update an LLM configuration")
async def update_llm_configuration(config_id: str, request: dict):
    correlation_id = f"llm-update-{datetime.now().isoformat()}-{os.urandom(4).hex()}"
    logger.info(f"🔧 [LLM_UPDATE][{correlation_id}] Starting LLM configuration update for ID: {config_id}")
    logger.info(f"🔧 [LLM_UPDATE][{correlation_id}] Request data: {dict(request, api_key='***' if request.get('api_key') else None)}")
    
    try:
        project_service = get_project_service()
        logger.info(f"🔧 [LLM_UPDATE][{correlation_id}] Calling project service: {project_service.base_url}/llm-configurations/{config_id}")
        
        response = requests.put(
            f"{project_service.base_url}/llm-configurations/{config_id}",
            json=request,
            headers=project_service._get_auth_headers(),
            timeout=15  # 15 second timeout to prevent hanging
        )
        
        logger.info(f"🔧 [LLM_UPDATE][{correlation_id}] Project service response: status={response.status_code}")
        
        if response.status_code == 200:
            config = response.json()
            unified_invalidate_llm_cache()
            logger.info(f"✅ [LLM_UPDATE][{correlation_id}] Updated LLM configuration: {config_id}")
            return config
        else:
            error_text = response.text
            logger.error(f"❌ [LLM_UPDATE][{correlation_id}] Project service error: {response.status_code} - {error_text}")
            raise HTTPException(status_code=response.status_code, detail=f"Failed to update configuration: {error_text}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [LLM_UPDATE][{correlation_id}] Unexpected error: {str(e)}")
        logger.exception(f"❌ [LLM_UPDATE][{correlation_id}] Full exception details:")
        raise HTTPException(status_code=500, detail=f"Failed to update LLM configuration: {str(e)}")

@router.delete("/configurations/{config_id}", summary="Delete an LLM configuration")
async def delete_llm_configuration(config_id: str):
    correlation_id = f"llm-delete-{datetime.now().isoformat()}-{os.urandom(4).hex()}"
    logger.info(f"🔧 [LLM_DELETE][{correlation_id}] Starting LLM configuration deletion for ID: {config_id}")
    
    try:
        project_service = get_project_service()
        logger.info(f"🔧 [LLM_DELETE][{correlation_id}] Calling project service: {project_service.base_url}/llm-configurations/{config_id}")
        
        response = requests.delete(
            f"{project_service.base_url}/llm-configurations/{config_id}",
            headers=project_service._get_auth_headers(),
            timeout=15  # 15 second timeout to prevent hanging
        )
        
        logger.info(f"🔧 [LLM_DELETE][{correlation_id}] Project service response: status={response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            unified_invalidate_llm_cache()
            logger.info(f"✅ [LLM_DELETE][{correlation_id}] Deleted LLM configuration: {config_id}")
            return result
        else:
            error_text = response.text
            logger.error(f"❌ [LLM_DELETE][{correlation_id}] Project service error: {response.status_code} - {error_text}")
            raise HTTPException(status_code=response.status_code, detail=f"Failed to delete configuration: {error_text}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [LLM_DELETE][{correlation_id}] Unexpected error: {str(e)}")
        logger.exception(f"❌ [LLM_DELETE][{correlation_id}] Full exception details:")
        raise HTTPException(status_code=500, detail=f"Failed to delete LLM configuration: {str(e)}")

from pydantic import BaseModel
from typing import Optional

class TestLLMConfigRequest(BaseModel):
    config_id: Optional[str] = None
    provider: str
    model: str
    api_key: Optional[str] = None
    temperature: Optional[float] = 0.1
    max_tokens: Optional[int] = 100
    query: Optional[str] = "TEST REQUEST: Please respond with 'TEST SUCCESSFUL - LLM is working correctly' to confirm connectivity."

@router.post("/test-llm-config", summary="Test LLM configuration with real API call")
async def test_llm_config_post(request: TestLLMConfigRequest):
    """
    Test LLM configuration by making actual API calls to the provider.
    This replaces the legacy mock endpoint with real LLM testing.
    """
    correlation_id = f"llm-test-{datetime.now().isoformat()}-{os.urandom(4).hex()}"
    logger.info(f"🔧 [LLM_TEST][{correlation_id}] Starting LLM configuration test")
    logger.info(f"🔧 [LLM_TEST][{correlation_id}] Request: config_id={request.config_id}, provider={request.provider}, model={request.model}, api_key_length={len(request.api_key) if request.api_key else 0}")
    
    try:
        # If config_id is provided, fetch the configuration and use its API key
        api_key_to_use = request.api_key
        provider = request.provider
        model = request.model
        
        if request.config_id:
            logger.info(f"🔧 [LLM_TEST][{correlation_id}] Fetching saved configuration: {request.config_id}")
            # Fetch the saved configuration
            configs = unified_get_llm_configs()
            if request.config_id in configs:
                saved_config = configs[request.config_id]
                api_key_to_use = saved_config.get('api_key', request.api_key)
                provider = saved_config.get('provider', request.provider)
                model = saved_config.get('model', request.model)
                logger.info(f"🔧 [LLM_TEST][{correlation_id}] Using saved config: provider={provider}, model={model}, api_key_length={len(api_key_to_use) if api_key_to_use else 0}")
            else:
                logger.warning(f"⚠️ [LLM_TEST][{correlation_id}] Config ID {request.config_id} not found, using request parameters")
        
        # Validate that we have an API key for providers that require it
        if provider in ['openai', 'gemini', 'azure', 'custom'] and not api_key_to_use:
            error_msg = f"No API key provided for {provider} provider. Please ensure the configuration has a valid API key."
            logger.error(f"❌ [LLM_TEST][{correlation_id}] {error_msg}")
            return {
                "status": "error",
                "message": error_msg,
                "provider": provider,
                "model": model,
                "query": request.query or "TEST REQUEST: Please respond with 'TEST SUCCESSFUL - LLM is working correctly' to confirm connectivity.",
                "correlation_id": correlation_id
            }
        
        # Create a temporary configuration for testing
        api_key_preview = f"{api_key_to_use[:10]}..." if api_key_to_use and len(api_key_to_use) > 10 else f"'{api_key_to_use}'"
        logger.info(f"🔧 [LLM_TEST][{correlation_id}] Testing LLM config: provider={provider}, model={model}, api_key={api_key_preview}")
        
        # Get LLM factory and create LLM instance
        from app.core.llm_factory import llm_factory
        logger.info(f"🔧 [LLM_TEST][{correlation_id}] Creating LLM instance...")
        llm = llm_factory._instantiate_llm(
            provider=provider,
            model=model,
            api_key=api_key_to_use,
            temperature=request.temperature or 0.1,
            max_tokens=request.max_tokens or 100
        )
        
        if not llm:
            error_msg = f"Failed to create LLM instance for {provider}/{model}"
            logger.error(f"❌ [LLM_TEST][{correlation_id}] {error_msg}")
            return {
                "status": "error",
                "message": error_msg,
                "query": request.query,
                "correlation_id": correlation_id
            }
        
        logger.info(f"🔧 [LLM_TEST][{correlation_id}] LLM instance created successfully: {type(llm).__name__}")
        
        # Special handling for Ollama to provide better error messages
        if provider.lower() == 'ollama':
            logger.info(f"🔧 [LLM_TEST][{correlation_id}] Testing Ollama model: {model}")
            from app.services.ollama_service import ollama_service
            test_result = await ollama_service.test_model(
                model_name=model,
                prompt=request.query or "TEST REQUEST: Please respond with 'TEST SUCCESSFUL - LLM is working correctly' to confirm connectivity."
            )
            
            if not test_result["success"]:
                logger.error(f"❌ [LLM_TEST][{correlation_id}] Ollama test failed: {test_result['error']}")
                return {
                    "status": "error",
                    "message": test_result["error"],
                    "suggestion": test_result.get("suggestion", ""),
                    "provider": provider,
                    "model": model,
                    "query": request.query or "TEST REQUEST: Please respond with 'TEST SUCCESSFUL - LLM is working correctly' to confirm connectivity.",
                    "correlation_id": correlation_id
                }
            
            logger.info(f"✅ [LLM_TEST][{correlation_id}] Ollama test successful")
            return {
                "status": "success",
                "provider": provider,
                "model": model,
                "query": request.query or "TEST REQUEST: Please respond with 'TEST SUCCESSFUL - LLM is working correctly' to confirm connectivity.",
                "response": test_result["response"],
                "echo": test_result["response"],  # For UI compatibility
                "timestamp": datetime.now().isoformat(),
                "duration_ms": test_result.get("total_duration", 0) / 1000000 if test_result.get("total_duration") else None,
                "correlation_id": correlation_id
            }
        
        # Test the LLM with the provided query (for non-Ollama providers)
        from langchain.schema import HumanMessage
        test_message = request.query or "TEST REQUEST: Please respond with 'TEST SUCCESSFUL - LLM is working correctly' to confirm connectivity."
        logger.info(f"🔧 [LLM_TEST][{correlation_id}] Invoking LLM with message: {test_message[:50]}...")
        
        response = llm.invoke([HumanMessage(content=test_message)])
        
        # Extract response content
        response_content = response.content if hasattr(response, 'content') else str(response)
        logger.info(f"✅ [LLM_TEST][{correlation_id}] LLM test successful, response length: {len(response_content)}")
        
        return {
            "status": "success",
            "provider": provider,
            "model": model,
            "query": test_message,
            "response": response_content,
            "echo": response_content,  # For UI compatibility
            "timestamp": datetime.now().isoformat(),
            "correlation_id": correlation_id
        }
        
    except Exception as e:
        error_msg = f"LLM config test failed: {str(e)}"
        logger.error(f"❌ [LLM_TEST][{correlation_id}] {error_msg}")
        logger.exception(f"❌ [LLM_TEST][{correlation_id}] Full exception details:")
        
        # Use the variables if they were set, otherwise fall back to request
        try:
            error_provider = provider
            error_model = model
        except NameError:
            error_provider = request.provider
            error_model = request.model
            
        return {
            "status": "error", 
            "message": error_msg,
            "provider": error_provider,
            "model": error_model,
            "query": request.query or "TEST REQUEST: Please respond with 'TEST SUCCESSFUL - LLM is working correctly' to confirm connectivity.",
            "correlation_id": correlation_id
        }

@router.get("/test-llm-config", summary="Test connectivity of default or specified LLM configuration")
async def test_llm_config(config_id: str = Query(None), test_query: str = Query("TEST REQUEST: Please respond with 'TEST SUCCESSFUL - LLM is working correctly' to confirm connectivity.")):
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
                return {
                    "status": "success", 
                    "provider": provider, 
                    "model": model, 
                    "query": test_query,
                    "response": reply,
                    "echo": reply,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                raise HTTPException(status_code=resp.status_code, detail=f"OpenAI API error: {resp.text}")
        # Add similar test logic for other providers if needed
        return {
            "status": "success", 
            "provider": provider, 
            "model": model, 
            "query": test_query,
            "response": "TEST SUCCESSFUL - LLM is working correctly",
            "echo": "TEST SUCCESSFUL - LLM is working correctly", 
            "timestamp": datetime.now().isoformat()
        }
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
        
        # Simple in-memory cache for model lists (expires in 1 hour)
        cache_key = f"{provider}_models"
        cache_with_key = f"{provider}_models_with_key"
        
        # Try to get from cache first if no API key provided
        if not api_key:
            cached_models = await get_cached_models(cache_key)
            if cached_models:
                logger.info(f"Returning cached models for {provider} (no API key)")
                return {"provider": provider, "models": cached_models, "cached": True}
        else:
            # Check if we have cached models with API key validation
            cached_models_with_key = await get_cached_models(cache_with_key)
            if cached_models_with_key:
                logger.info(f"Returning cached models for {provider} (with validated API key)")
                return {"provider": provider, "models": cached_models_with_key, "cached": True}
        
        # Fetch models dynamically based on provider
        if provider == "openai" and api_key:
            logger.info(f"🔧 Fetching OpenAI models dynamically with API key")
            import requests
            headers = {"Authorization": f"Bearer {api_key}"}
            try:
                resp = requests.get("https://api.openai.com/v1/models", headers=headers, timeout=10)
                if resp.ok:
                    data = resp.json()
                    models = [m["id"] for m in data.get("data", []) if m.get("id")]
                    logger.info(f"✅ Successfully fetched {len(models)} OpenAI models from API")
                else:
                    logger.error(f"❌ OpenAI API error: {resp.status_code} - {resp.text}")
                    raise HTTPException(status_code=resp.status_code, detail=f"OpenAI API error: {resp.text}")
            except requests.exceptions.RequestException as e:
                logger.error(f"❌ OpenAI API request failed: {e}")
                raise HTTPException(status_code=500, detail=f"OpenAI API request failed: {e}")
        elif provider == "anthropic":
            # Try to dynamically fetch Anthropic models if API key provided
            if api_key:
                logger.info(f"🔧 Validating Anthropic API key and fetching models")
                try:
                    import anthropic
                    client = anthropic.Anthropic(api_key=api_key)
                    
                    # Anthropic doesn't have a public models API, but we can test the key and return known models
                    # Test the API key with a simple call
                    test_response = client.messages.create(
                        model="claude-3-haiku-20240307",
                        max_tokens=10,
                        messages=[{"role": "user", "content": "test"}]
                    )
                    
                    if test_response:
                        logger.info(f"✅ Anthropic API key validated successfully")
                        # API key is valid, return comprehensive model list
                        models = [
                            "claude-3-5-sonnet-20241022", "claude-3-5-sonnet-latest",
                            "claude-3-5-haiku-20241022", "claude-3-5-haiku-latest", 
                            "claude-3-opus-20240229", "claude-3-opus-latest",
                            "claude-3-sonnet-20240229", "claude-3-haiku-20240307"
                        ]
                    else:
                        logger.warning("Anthropic API test failed, using fallback models")
                        # Fallback to basic models
                        models = ["claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"]
                        
                except Exception as e:
                    logger.error(f"❌ Failed to validate Anthropic API key: {e}")
                    # Fallback to static list on error
                    models = ["claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"]
            else:
                logger.info(f"🔧 No API key provided for Anthropic, returning static list")
                # No API key provided, return basic static list
                models = ["claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"]
        elif provider == "gemini":
            # Try to dynamically fetch Gemini models if API key provided
            if api_key:
                try:
                    logger.info(f"🔧 Fetching Gemini models dynamically with API key")
                    import google.generativeai as genai
                    genai.configure(api_key=api_key)
                    
                    # Get available models from Google API
                    available_models = []
                    try:
                        models_iterator = genai.list_models()
                        for model in models_iterator:
                            if hasattr(model, 'supported_generation_methods') and 'generateContent' in model.supported_generation_methods:
                                model_name = model.name.replace('models/', '')
                                available_models.append(model_name)
                                logger.debug(f"Found Gemini model: {model_name}")
                    except Exception as list_error:
                        logger.error(f"Failed to list Gemini models: {list_error}")
                        raise list_error
                    
                    if available_models:
                        models = available_models
                        logger.info(f"✅ Successfully fetched {len(models)} Gemini models from API")
                    else:
                        logger.warning("No Gemini models returned from API, using fallback static list")
                        # Fallback to static list if no models returned
                        models = [
                            "gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-flash-preview-05-20",
                            "gemini-live-2.5-flash-preview", "gemini-2.0-flash", "gemini-2.0-flash-001", "gemini-2.0-flash-exp",
                            "gemini-2.0-flash-lite", "gemini-2.0-flash-live-001", "gemini-1.5-pro", "gemini-1.5-pro-001",
                            "gemini-1.5-pro-002", "gemini-1.5-flash", "gemini-1.5-flash-001", "gemini-1.5-flash-002", "gemini-1.5-flash-8b"
                        ]
                except Exception as e:
                    logger.error(f"❌ Failed to fetch Gemini models dynamically: {e}")
                    # Fallback to static list on error
                    models = [
                        "gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-flash-preview-05-20",
                        "gemini-live-2.5-flash-preview", "gemini-2.0-flash", "gemini-2.0-flash-001", "gemini-2.0-flash-exp",
                        "gemini-2.0-flash-lite", "gemini-2.0-flash-live-001", "gemini-1.5-pro", "gemini-1.5-pro-001",
                        "gemini-1.5-pro-002", "gemini-1.5-flash", "gemini-1.5-flash-001", "gemini-1.5-flash-002", "gemini-1.5-flash-8b"
                    ]
            else:
                logger.info(f"🔧 No API key provided for Gemini, returning static list")
                # No API key provided, return static list
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
        
        # Cache the results
        cache_key = f"{provider}_models"
        cache_with_key = f"{provider}_models_with_key"
        
        if api_key and models:
            # Cache models fetched with API key
            await cache_models(cache_with_key, models)
            logger.info(f"Cached {len(models)} models for {provider} with API key validation")
        elif models:
            # Cache models without API key validation
            await cache_models(cache_key, models)
            logger.info(f"Cached {len(models)} models for {provider} without API key")
        
        return {"provider": provider, "models": models, "cached": False}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"List models failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to list models")


@router.get("/models/{provider}/{model_name}/info", summary="Get detailed model information including max tokens")
async def get_model_info(provider: str, model_name: str, api_key: str = Query(None)):
    """Get detailed model information including maximum token count"""
    try:
        provider = provider.lower()
        model_info = {
            "provider": provider,
            "model": model_name,
            "max_tokens": 4000,  # Default fallback
            "context_window": None,
            "supports_streaming": True,
            "supports_function_calling": False
        }
        
        # Model-specific information with known token limits
        model_token_limits = {
            # OpenAI models
            "gpt-4": {"max_tokens": 8192, "context_window": 8192},
            "gpt-4-turbo": {"max_tokens": 128000, "context_window": 128000},
            "gpt-4o": {"max_tokens": 128000, "context_window": 128000},
            "gpt-4o-mini": {"max_tokens": 128000, "context_window": 128000},
            "gpt-3.5-turbo": {"max_tokens": 16385, "context_window": 16385},
            "o1-mini": {"max_tokens": 128000, "context_window": 128000},
            "o1-preview": {"max_tokens": 128000, "context_window": 128000},
            
            # Anthropic models
            "claude-3-opus": {"max_tokens": 200000, "context_window": 200000, "supports_function_calling": True},
            "claude-3-sonnet": {"max_tokens": 200000, "context_window": 200000, "supports_function_calling": True},
            "claude-3-haiku": {"max_tokens": 200000, "context_window": 200000, "supports_function_calling": True},
            "claude-3-5-sonnet": {"max_tokens": 200000, "context_window": 200000, "supports_function_calling": True},
            
            # Gemini models
            "gemini-2.5-pro": {"max_tokens": 8192, "context_window": 2000000},
            "gemini-2.5-flash": {"max_tokens": 8192, "context_window": 1000000},
            "gemini-2.5-flash-lite": {"max_tokens": 8192, "context_window": 1000000},
            "gemini-2.0-flash": {"max_tokens": 8192, "context_window": 1000000},
            "gemini-2.0-flash-exp": {"max_tokens": 8192, "context_window": 1000000},
            "gemini-1.5-pro": {"max_tokens": 8192, "context_window": 2000000},
            "gemini-1.5-flash": {"max_tokens": 8192, "context_window": 1000000},
            "gemini-1.5-flash-8b": {"max_tokens": 8192, "context_window": 1000000},
        }
        
        # Update with known information
        if model_name in model_token_limits:
            model_info.update(model_token_limits[model_name])
        
        # For OpenAI, try to get real-time information if API key is provided
        if provider == "openai" and api_key:
            try:
                import requests
                headers = {"Authorization": f"Bearer {api_key}"}
                resp = requests.get("https://api.openai.com/v1/models", headers=headers, timeout=10)
                if resp.ok:
                    data = resp.json()
                    for model in data.get("data", []):
                        if model.get("id") == model_name:
                            # OpenAI API doesn't return token limits, so we use our known values
                            model_info["supports_function_calling"] = True
                            model_info["created"] = model.get("created")
                            break
            except Exception as e:
                logger.warning(f"Could not fetch real-time OpenAI model info: {e}")
        
        # Try to query the model directly for token limits (experimental)
        if api_key and provider in ["openai", "anthropic", "gemini"]:
            try:
                # Test with a small query to validate the model works
                from app.core.llm_factory import llm_factory
                test_llm = llm_factory._instantiate_llm(
                    provider=provider,
                    model=model_name,
                    api_key=api_key,
                    temperature=0.1,
                    max_tokens=100
                )
                
                # Simple test query
                test_response = test_llm.invoke("What is 2+2?")
                if test_response:
                    model_info["validated"] = True
                    model_info["test_successful"] = True
                else:
                    model_info["validated"] = False
                    
            except Exception as e:
                logger.warning(f"Model validation failed for {provider}/{model_name}: {e}")
                model_info["validated"] = False
                model_info["validation_error"] = str(e)
        
        return {
            "status": "success",
            "model_info": model_info
        }
        
    except Exception as e:
        logger.error(f"Get model info failed for {provider}/{model_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get model info: {e}")

def _get_static_max_tokens(provider: str, model: str) -> int:
    """Get static max tokens for a model based on known limits"""
    # Model-specific information with known token limits
    model_token_limits = {
        # OpenAI models
        "gpt-4": {"max_tokens": 8192, "context_window": 8192},
        "gpt-4-turbo": {"max_tokens": 128000, "context_window": 128000},
        "gpt-4o": {"max_tokens": 128000, "context_window": 128000},
        "gpt-4o-mini": {"max_tokens": 128000, "context_window": 128000},
        "gpt-3.5-turbo": {"max_tokens": 16385, "context_window": 16385},
        "o1-mini": {"max_tokens": 128000, "context_window": 128000},
        "o1-preview": {"max_tokens": 128000, "context_window": 128000},

        # Anthropic models
        "claude-3-opus": {"max_tokens": 200000, "context_window": 200000},
        "claude-3-sonnet": {"max_tokens": 200000, "context_window": 200000},
        "claude-3-haiku": {"max_tokens": 200000, "context_window": 200000},
        "claude-3-5-sonnet": {"max_tokens": 200000, "context_window": 200000},

        # Gemini models
        "gemini-2.5-pro": {"max_tokens": 8192, "context_window": 2000000},
        "gemini-2.5-flash": {"max_tokens": 8192, "context_window": 1000000},
        "gemini-2.5-flash-lite": {"max_tokens": 8192, "context_window": 1000000},
        "gemini-2.0-flash": {"max_tokens": 8192, "context_window": 1000000},
        "gemini-2.0-flash-exp": {"max_tokens": 8192, "context_window": 1000000},
        "gemini-1.5-pro": {"max_tokens": 8192, "context_window": 2000000},
        "gemini-1.5-flash": {"max_tokens": 8192, "context_window": 1000000},
        "gemini-1.5-flash-8b": {"max_tokens": 8192, "context_window": 1000000},
    }

    # Return max_tokens if found, otherwise default to 4000
    return model_token_limits.get(model, {}).get("max_tokens", 4000)

@router.get("/models/{provider}/{model}/max-tokens", summary="Get maximum token limit for a specific model")
async def get_model_max_tokens_endpoint(provider: str, model: str, api_key: str = Query(None)):
    """
    Get the maximum token limit for a specific model.
    This endpoint queries the provider's API to determine the actual token limits.
    """
    try:
        logger.info(f"Getting max tokens for {provider}/{model}")

        # First try static lookup using the same logic as get_model_info
        static_max_tokens = _get_static_max_tokens(provider, model)

        result = {
            "provider": provider,
            "model": model,
            "max_tokens": static_max_tokens,
            "source": "static_lookup",
            "validated": False
        }

        # If API key is provided, try to validate with the actual provider
        if api_key and provider in ["openai", "anthropic", "gemini"]:
            try:
                if provider == "openai":
                    # Query OpenAI API for model details
                    import requests
                    headers = {"Authorization": f"Bearer {api_key}"}
                    response = requests.get("https://api.openai.com/v1/models", headers=headers, timeout=10)

                    if response.status_code == 200:
                        models_data = response.json()
                        for model_info in models_data.get("data", []):
                            if model_info.get("id") == model:
                                # OpenAI doesn't directly provide max_tokens in the models endpoint
                                # But we can validate the model exists and is accessible
                                result["validated"] = True
                                result["source"] = "openai_api_validated"
                                break

                elif provider == "gemini":
                    # For Gemini, we can test with a small request to validate
                    from app.core.llm_factory import llm_factory
                    test_llm = llm_factory._instantiate_llm(
                        provider=provider,
                        model=model,
                        api_key=api_key,
                        temperature=0.1,
                        max_tokens=100
                    )

                    # Test with a simple query
                    test_response = test_llm.invoke("Hi")
                    if test_response:
                        result["validated"] = True
                        result["source"] = "gemini_api_validated"

                        # For Gemini models, we can provide more accurate token limits
                        if "gemini-2.5-pro" in model:
                            result["max_tokens"] = 8192
                        elif "gemini-2.5-flash" in model:
                            result["max_tokens"] = 8192
                        elif "gemini-1.5-pro" in model:
                            result["max_tokens"] = 8192
                        elif "gemini-1.5-flash" in model:
                            result["max_tokens"] = 8192

                elif provider == "anthropic":
                    # For Anthropic, test with a small request
                    from app.core.llm_factory import llm_factory
                    test_llm = llm_factory._instantiate_llm(
                        provider=provider,
                        model=model,
                        api_key=api_key,
                        temperature=0.1,
                        max_tokens=100
                    )

                    test_response = test_llm.invoke("Hi")
                    if test_response:
                        result["validated"] = True
                        result["source"] = "anthropic_api_validated"

                        # Anthropic Claude models have known limits
                        if "claude-3.5-sonnet" in model:
                            result["max_tokens"] = 8192
                        elif "claude-3" in model:
                            result["max_tokens"] = 4096

            except Exception as e:
                logger.warning(f"API validation failed for {provider}/{model}: {e}")
                result["validation_error"] = str(e)

        return result

    except Exception as e:
        logger.error(f"Error getting max tokens for {provider}/{model}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get max tokens: {str(e)}")


# Cache helper functions
async def get_cached_models(cache_key: str) -> Optional[List[str]]:
    """Get cached models if they exist and are not expired (1 hour TTL)"""
    if cache_key in _models_cache:
        cache_entry = _models_cache[cache_key]
        cache_time = cache_entry.get("timestamp", 0)
        current_time = datetime.now().timestamp()
        
        # Check if cache is expired (1 hour = 3600 seconds)
        if current_time - cache_time < 3600:
            return cache_entry.get("models", [])
        else:
            # Remove expired cache
            del _models_cache[cache_key]
    
    return None

async def cache_models(cache_key: str, models: List[str]):
    """Cache models with current timestamp"""
    _models_cache[cache_key] = {
        "models": models,
        "timestamp": datetime.now().timestamp()
    }

@router.get("/models/cache/status", summary="Get cache status for debugging")
async def get_cache_status():
    """Get current cache status for debugging purposes"""
    cache_status = {}
    current_time = datetime.now().timestamp()
    
    for cache_key, cache_entry in _models_cache.items():
        cache_time = cache_entry.get("timestamp", 0)
        age_minutes = (current_time - cache_time) / 60
        
        cache_status[cache_key] = {
            "models_count": len(cache_entry.get("models", [])),
            "age_minutes": round(age_minutes, 2),
            "expired": age_minutes > 60  # 60 minutes TTL
        }
    
    return {
        "cache_entries": len(_models_cache),
        "cache_details": cache_status
    }

@router.get("/debug/connectivity", summary="Debug connectivity to project service")
async def debug_connectivity():
    """
    Debug endpoint to test connectivity to project service and other dependencies
    """
    debug_info = {
        "timestamp": datetime.now().isoformat(),
        "checks": []
    }
    
    # Test project service connectivity
    try:
        project_service = get_project_service()
        debug_info["project_service_url"] = project_service.base_url
        
        # Test basic connectivity
        response = requests.get(
            f"{project_service.base_url}/health",
            headers=project_service._get_auth_headers(),
            timeout=5
        )
        
        debug_info["checks"].append({
            "name": "project_service_health",
            "status": "success" if response.ok else "failed",
            "status_code": response.status_code,
            "response_time_ms": response.elapsed.total_seconds() * 1000 if response.elapsed else 0,
            "details": response.json() if response.ok else response.text[:200]
        })
    except Exception as e:
        debug_info["checks"].append({
            "name": "project_service_health",
            "status": "error",
            "error": str(e)
        })
    
    # Test LLM configurations endpoint
    try:
        project_service = get_project_service()
        response = requests.get(
            f"{project_service.base_url}/llm-configurations",
            headers=project_service._get_auth_headers(),
            timeout=5
        )
        
        debug_info["checks"].append({
            "name": "llm_configurations_endpoint",
            "status": "success" if response.ok else "failed",
            "status_code": response.status_code,
            "response_time_ms": response.elapsed.total_seconds() * 1000 if response.elapsed else 0,
            "config_count": len(response.json()) if response.ok else 0,
            "details": response.text[:200] if not response.ok else "OK"
        })
    except Exception as e:
        debug_info["checks"].append({
            "name": "llm_configurations_endpoint",
            "status": "error",
            "error": str(e)
        })
    
    # Test database connectivity through project service
    try:
        configs = unified_get_llm_configs()
        debug_info["checks"].append({
            "name": "llm_config_cache",
            "status": "success",
            "config_count": len(configs),
            "details": "Cache loaded successfully"
        })
    except Exception as e:
        debug_info["checks"].append({
            "name": "llm_config_cache",
            "status": "error",
            "error": str(e)
        })
    
    return debug_info
