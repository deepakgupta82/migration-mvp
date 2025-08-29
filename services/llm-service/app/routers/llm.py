#!/usr/bin/env python3
"""
LLM Router - Clean API endpoints for LLM orchestration
Handles process-specific LLM requests, configuration, and provider management
"""

from typing import Dict, List, Any, Optional, Union
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
import logging
import httpx
import os

from ..core.llm_processor import LLMProcessor, LLMProcessType

logger = logging.getLogger("llm-service")
router = APIRouter()

# Initialize clean processor
llm_processor = LLMProcessor()

# Request/Response Models
class ProcessLLMRequest(BaseModel):
    process_type: str = Field(..., description="Process type requiring LLM")
    prompt: str = Field(..., description="Prompt to process")
    project_id: Optional[str] = Field(None, description="Optional project ID")
    allow_global: Optional[bool] = Field(True, description="Allow fallback to global LLM configs if project configs are missing")

class ProcessLLMResponse(BaseModel):
    process_type: str
    response: str
    success: bool
    error: Optional[str] = None

class LLMConfigurationCreate(BaseModel):
    name: str = Field(..., description="Configuration name")
    provider: str = Field(..., description="LLM provider (openai, gemini, anthropic, ollama)")
    model: str = Field(..., description="Model name")
    api_key: str = Field(..., description="API key")
    google_cloud_project_id: Optional[str] = Field(None, description="Google Cloud Project ID (for Gemini)")
    temperature: Optional[str] = Field("0.1", description="Temperature setting")
    max_tokens: Optional[str] = Field("20000", description="Max tokens setting")
    description: Optional[str] = Field(None, description="Configuration description")

class LLMConfigurationUpdate(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    google_cloud_project_id: Optional[str] = None
    temperature: Optional[str] = None
    max_tokens: Optional[str] = None
    description: Optional[str] = None

class LLMConfigurationResponse(BaseModel):
    id: str
    name: str
    provider: str
    model: str
    google_cloud_project_id: Optional[str] = None
    temperature: str
    max_tokens: str
    description: Optional[str] = None
    created_at: str
    updated_at: str

class TestLLMConfigRequest(BaseModel):
    config_id: Optional[str] = None
    provider: str
    model: str
    api_key: Optional[str] = None
    temperature: Optional[float] = 0.1
    max_tokens: Optional[int] = 100
    query: Optional[str] = "TEST REQUEST: Please respond with 'TEST SUCCESSFUL - LLM is working correctly' to confirm connectivity."

class HealthResponse(BaseModel):
    service: str
    status: str
    langchain_available: bool
    supported_providers: List[str]
    process_types: List[str]
    cache_status: Dict[str, Any]

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Clean health check endpoint"""
    try:
        health_data = await llm_processor.health_check()
        return HealthResponse(
            service="llm-service",
            status=health_data["status"],
            langchain_available=health_data["langchain_available"],
            supported_providers=list(health_data.get("supported_providers", [])),
            process_types=health_data["process_types"],
            cache_status=health_data["cache_status"]
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@router.get("/providers")
async def list_providers():
    """List available LLM providers"""
    try:
        providers = await llm_processor.list_providers()
        return {"providers": providers}
    except Exception as e:
        logger.error(f"Error listing providers: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/providers/status")
async def get_provider_status():
    """Get status and configuration info for all providers"""
    try:
        status = await llm_processor.get_provider_status()
        return {"provider_status": status}
    except Exception as e:
        logger.error(f"Error getting provider status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/process-types")
async def list_process_types():
    """List supported LLM process types"""
    try:
        process_types = await llm_processor.list_process_types()
        return {"process_types": process_types}
    except Exception as e:
        logger.error(f"Error listing process types: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/recommendations/{process_type}")
async def get_model_recommendations(process_type: str):
    """Get model recommendations for specific process type"""
    try:
        recommendations = llm_processor.get_model_recommendations(process_type)
        return {
            "process_type": process_type,
            "recommendations": recommendations
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid process type: {process_type}")
    except Exception as e:
        logger.error(f"Error getting recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process", response_model=ProcessLLMResponse)
async def process_llm_request(request: ProcessLLMRequest, http_request: Request):
    """Process LLM request for specific process type"""
    try:
        corr_id = http_request.headers.get("X-Correlation-ID")
        response_text = await llm_processor.process_llm_request(
            process_type=request.process_type,
            prompt=request.prompt,
            project_id=request.project_id,
            corr_id=corr_id,
            allow_global=bool(request.allow_global if request.allow_global is not None else True)
        )
        
        return ProcessLLMResponse(
            process_type=request.process_type,
            response=response_text,
            success=True
        )
        
    except ValueError as e:
        return ProcessLLMResponse(
            process_type=request.process_type,
            response="",
            success=False,
            error=f"Invalid process type: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error processing LLM request: {e}")
        return ProcessLLMResponse(
            process_type=request.process_type,
            response="",
            success=False,
            error=str(e)
        )

@router.get("/resolve")
async def resolve_process_configuration(process_type: str, project_id: Optional[str] = None, request: Request = None, allow_global: bool = Query(True)):
    """Resolve provider/model configuration for a process+project without instantiating an LLM."""
    try:
        corr_id = request.headers.get("X-Correlation-ID") if request else None
        cfg = await llm_processor.resolve_process_configuration(process_type, project_id, corr_id=corr_id, allow_global=allow_global)
        if not cfg:
            raise HTTPException(status_code=404, detail="No configuration found")
        return cfg
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving process configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/configurations")
async def get_configurations():
    """Get LLM configurations"""
    try:
        configurations = await llm_processor.get_configurations()
        # Frontend expects a list; our processor returns a dict keyed by id
        if isinstance(configurations, dict):
            return list(configurations.values())
        return configurations
    except Exception as e:
        logger.error(f"Error getting configurations: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cache/invalidate")
async def invalidate_cache():
    """Invalidate configuration cache"""
    try:
        llm_processor.invalidate_cache()
        return {"message": "Cache invalidated successfully"}
    except Exception as e:
        logger.error(f"Error invalidating cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Legacy compatibility endpoints
@router.get("/entity-extraction/{project_id}")
async def get_entity_extraction_llm(project_id: str):
    """Legacy endpoint: Get LLM for entity extraction"""
    try:
        llm = await llm_processor.get_llm_for_entity_extraction(project_id)
        return {
            "project_id": project_id,
            "process_type": "entity_extraction", 
            "llm_available": llm is not None,
            "llm_type": str(type(llm).__name__) if llm else None
        }
    except Exception as e:
        logger.error(f"Error getting entity extraction LLM: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/crew-assessment/{project_id}")
async def get_crew_assessment_llm(project_id: str):
    """Legacy endpoint: Get LLM for crew assessment"""
    try:
        llm = await llm_processor.get_llm_for_crew_assessment(project_id)
        return {
            "project_id": project_id,
            "process_type": "crew_assessment",
            "llm_available": llm is not None,
            "llm_type": str(type(llm).__name__) if llm else None
        }
    except Exception as e:
        logger.error(f"Error getting crew assessment LLM: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/crew-documentation/{project_id}")
async def get_crew_documentation_llm(project_id: str):
    """Legacy endpoint: Get LLM for crew documentation"""
    try:
        llm = await llm_processor.get_llm_for_crew_documentation(project_id)
        return {
            "project_id": project_id,
            "process_type": "crew_documentation",
            "llm_available": llm is not None, 
            "llm_type": str(type(llm).__name__) if llm else None
        }
    except Exception as e:
        logger.error(f"Error getting crew documentation LLM: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# =====================================================================================
# LLM Configuration Management Endpoints
# =====================================================================================

@router.get("/configurations", summary="Get all LLM configurations")
async def get_llm_configurations():
    """List all LLM configurations"""
    try:
        # Route to project service for now - configurations are stored there
        project_service_url = os.getenv("PROJECT_SERVICE_URL", "http://localhost:8002")
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{project_service_url}/llm-configurations")
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Project service error: {response.status_code} - {response.text}")
                raise HTTPException(status_code=response.status_code, detail="Failed to fetch configurations")
    except httpx.RequestError as e:
        logger.error(f"Request error: {e}")
        raise HTTPException(status_code=503, detail="Project service unavailable")
    except Exception as e:
        logger.error(f"Error getting LLM configurations: {str(e)}")
        return []

@router.post("/configurations", summary="Create a new LLM configuration")
async def create_llm_configuration(config: LLMConfigurationCreate):
    """Create a new LLM configuration"""
    try:
        # Validate required fields
        if not config.api_key or config.api_key.strip() == '':
            raise HTTPException(status_code=400, detail="API key is required and cannot be empty")
        
        # Route to project service for now - configurations are stored there
        project_service_url = os.getenv("PROJECT_SERVICE_URL", "http://localhost:8002")
        payload = {
            "name": config.name,
            "provider": config.provider,
            "model": config.model,
            "api_key": config.api_key,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "description": config.description or f"{config.name} - {config.provider}/{config.model}",
            "google_cloud_project_id": config.google_cloud_project_id
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{project_service_url}/llm-configurations",
                json=payload,
                timeout=15.0
            )
            if response.status_code == 201:
                return response.json()
            else:
                logger.error(f"Project service error: {response.status_code} - {response.text}")
                raise HTTPException(status_code=response.status_code, detail=f"Failed to create configuration: {response.text}")
    except httpx.RequestError as e:
        logger.error(f"Request error: {e}")
        raise HTTPException(status_code=503, detail="Project service unavailable")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating LLM configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create LLM configuration: {str(e)}")

@router.put("/configurations/{config_id}", summary="Update an LLM configuration")
async def update_llm_configuration(config_id: str, config: LLMConfigurationUpdate):
    """Update an LLM configuration"""
    try:
        # Validate API key if it's being updated
        update_data = config.model_dump(exclude_unset=True)
        if 'api_key' in update_data and (not update_data['api_key'] or update_data['api_key'].strip() == ''):
            raise HTTPException(status_code=400, detail="API key cannot be empty")
            
        # Route to project service for now - configurations are stored there
        project_service_url = os.getenv("PROJECT_SERVICE_URL", "http://localhost:8002")
        
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{project_service_url}/llm-configurations/{config_id}",
                json=update_data,
                timeout=15.0
            )
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Project service error: {response.status_code} - {response.text}")
                raise HTTPException(status_code=response.status_code, detail=f"Failed to update configuration: {response.text}")
    except httpx.RequestError as e:
        logger.error(f"Request error: {e}")
        raise HTTPException(status_code=503, detail="Project service unavailable")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating LLM configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update LLM configuration: {str(e)}")

@router.delete("/configurations/{config_id}", summary="Delete an LLM configuration")
async def delete_llm_configuration(config_id: str):
    """Delete an LLM configuration"""
    try:
        # Route to project service for now - configurations are stored there
        project_service_url = os.getenv("PROJECT_SERVICE_URL", "http://localhost:8002")
        
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{project_service_url}/llm-configurations/{config_id}",
                timeout=15.0
            )
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Project service error: {response.status_code} - {response.text}")
                raise HTTPException(status_code=response.status_code, detail=f"Failed to delete configuration: {response.text}")
    except httpx.RequestError as e:
        logger.error(f"Request error: {e}")
        raise HTTPException(status_code=503, detail="Project service unavailable")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting LLM configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete LLM configuration: {str(e)}")

@router.get("/models/{provider}", summary="List available models for provider")
async def list_provider_models(provider: str, api_key: str = Query(None)):
    """List available models for a provider"""
    try:
        if provider.lower() == "gemini" and api_key:
            # Dynamically fetch Gemini models
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                
                available_models = []
                models_iterator = genai.list_models()
                for model in models_iterator:
                    if hasattr(model, 'supported_generation_methods') and 'generateContent' in model.supported_generation_methods:
                        model_name = model.name.replace('models/', '')
                        available_models.append({
                            "id": model_name,
                            "name": model_name,
                            "description": f"Google Gemini {model_name}"
                        })
                
                if available_models:
                    return {"provider": provider, "models": available_models, "cached": False}
                else:
                    # Fallback to static models
                    static_models = [
                        {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro", "description": "Google Gemini 2.5 Pro"},
                        {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash", "description": "Google Gemini 2.5 Flash"},
                        {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro", "description": "Google Gemini 1.5 Pro"},
                        {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash", "description": "Google Gemini 1.5 Flash"}
                    ]
                    return {"provider": provider, "models": static_models, "cached": True}
                    
            except Exception as e:
                logger.warning(f"Failed to fetch Gemini models dynamically: {e}")
                # Fallback to static models
                static_models = [
                    {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro", "description": "Google Gemini 2.5 Pro"},
                    {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash", "description": "Google Gemini 2.5 Flash"},
                    {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro", "description": "Google Gemini 1.5 Pro"},
                    {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash", "description": "Google Gemini 1.5 Flash"}
                ]
                return {"provider": provider, "models": static_models, "cached": True}
        
        # For other providers, return static models for now
        static_provider_models = {
            "openai": [
                {"id": "gpt-4o", "name": "GPT-4o", "description": "OpenAI GPT-4o"},
                {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "description": "OpenAI GPT-4o Mini"},
                {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "description": "OpenAI GPT-4 Turbo"},
                {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo", "description": "OpenAI GPT-3.5 Turbo"}
            ],
            "anthropic": [
                {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet", "description": "Anthropic Claude 3.5 Sonnet"},
                {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus", "description": "Anthropic Claude 3 Opus"},
                {"id": "claude-3-sonnet-20240229", "name": "Claude 3 Sonnet", "description": "Anthropic Claude 3 Sonnet"},
                {"id": "claude-3-haiku-20240307", "name": "Claude 3 Haiku", "description": "Anthropic Claude 3 Haiku"}
            ],
            "ollama": [
                {"id": "llama3.1:8b", "name": "Llama 3.1 8B", "description": "Meta Llama 3.1 8B"},
                {"id": "llama3.1:70b", "name": "Llama 3.1 70B", "description": "Meta Llama 3.1 70B"},
                {"id": "mistral:7b", "name": "Mistral 7B", "description": "Mistral 7B"},
                {"id": "codellama:13b", "name": "Code Llama 13B", "description": "Meta Code Llama 13B"}
            ]
        }
        
        models = static_provider_models.get(provider.lower(), [])
        return {"provider": provider, "models": models, "cached": True}
        
    except Exception as e:
        logger.error(f"Error listing models for {provider}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list models: {str(e)}")

@router.post("/test-llm-config", summary="Test LLM configuration")
async def test_llm_config(request: TestLLMConfigRequest):
    """Test LLM configuration by making a real API call"""
    try:
        # Use the processor to test the configuration
        provider = request.provider
        model = request.model
        api_key = request.api_key
        
        # If config_id is provided, fetch the configuration
        if request.config_id and not api_key:
            configs = await llm_processor.get_configurations()
            if request.config_id in configs:
                saved_config = configs[request.config_id]
                api_key = saved_config.get('api_key')
                provider = saved_config.get('provider', provider)
                model = saved_config.get('model', model)
        
        # Validate API key
        if not api_key or api_key.strip() == '':
            return {
                "status": "error",
                "message": f"No API key provided for {provider} provider. Please ensure the configuration has a valid API key.",
                "provider": provider,
                "model": model,
                "query": request.query
            }
        
        # Instantiate and test the LLM
        provider_config = llm_processor._provider_configs.get(provider.lower())
        if not provider_config or not provider_config['class']:
            return {
                "status": "error",
                "message": f"Provider {provider} is not supported or not available",
                "provider": provider,
                "model": model,
                "query": request.query
            }
        
        llm = llm_processor._instantiate_llm(
            provider=provider.lower(),
            llm_class=provider_config['class'],
            model=model,
            api_key=api_key,
            temperature=request.temperature or 0.1,
            max_tokens=request.max_tokens or 100
        )
        
        # Test with the query
        if provider.lower() == 'ollama':
            # Special handling for Ollama
            response = llm.invoke(request.query)
        else:
            # For other providers, use standard invoke
            from langchain.schema import HumanMessage
            response = llm.invoke([HumanMessage(content=request.query)])
            response = response.content if hasattr(response, 'content') else str(response)
        
        return {
            "status": "success",
            "provider": provider,
            "model": model,
            "query": request.query,
            "response": response,
            "echo": response,
            "timestamp": "current"
        }
        
    except Exception as e:
        logger.error(f"LLM config test failed: {e}")
        return {
            "status": "error",
            "message": f"LLM config test failed: {str(e)}",
            "provider": request.provider,
            "model": request.model,
            "query": request.query
        }
