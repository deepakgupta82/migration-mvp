"""
Ollama API Router - For querying local Ollama installation
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging

from ..services.ollama_service import ollama_service

router = APIRouter(prefix="/api/ollama", tags=["ollama"])
logger = logging.getLogger(__name__)

class OllamaEndpointRequest(BaseModel):
    base_url: str

class OllamaModelTestRequest(BaseModel):
    model_name: str
    base_url: Optional[str] = None
    prompt: Optional[str] = "Hello! Please respond to confirm the model is working."

@router.get("/status")
async def get_ollama_status(base_url: Optional[str] = None):
    """Check if Ollama service is running"""
    try:
        is_running = await ollama_service.is_running(base_url)
        return {
            "running": is_running,
            "base_url": base_url or ollama_service.base_url
        }
    except Exception as e:
        logger.error(f"Failed to check Ollama status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test-endpoint")
async def test_ollama_endpoint(request: OllamaEndpointRequest):
    """Test if Ollama is running at provided endpoint and get available models"""
    try:
        result = await ollama_service.test_endpoint_and_get_models(request.base_url)
        if not result["success"]:
            raise HTTPException(
                status_code=503,
                detail=result["error"]
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to test Ollama endpoint {request.base_url}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/models")
async def get_ollama_models(base_url: Optional[str] = None):
    """Get available Ollama models"""
    try:
        # First check if Ollama is running
        if not await ollama_service.is_running(base_url):
            raise HTTPException(
                status_code=503,
                detail="Ollama service is not running. Please start Ollama and try again."
            )
        
        models = await ollama_service.get_available_models(base_url)
        return {
            "models": models,
            "count": len(models),
            "endpoint": base_url or ollama_service.base_url
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get Ollama models: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/models/test")
async def test_ollama_model(request: OllamaModelTestRequest):
    """Test if a specific Ollama model is working"""
    try:
        # Check if Ollama is running
        if not await ollama_service.is_running(request.base_url):
            raise HTTPException(
                status_code=503,
                detail="Ollama service is not running. Please start Ollama and try again."
            )
        
        result = await ollama_service.test_model(
            model_name=request.model_name,
            prompt=request.prompt or "Hello! Please respond to confirm the model is working.",
            base_url=request.base_url
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to test Ollama model {request.model_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/models/detailed")
async def get_detailed_ollama_models(base_url: Optional[str] = None):
    """Get detailed information about available Ollama models"""
    try:
        if not await ollama_service.is_running(base_url):
            raise HTTPException(
                status_code=503,
                detail="Ollama service is not running. Please start Ollama and try again."
            )
        
        models = await ollama_service.get_detailed_models(base_url)
        return {
            "models": models,
            "count": len(models),
            "endpoint": base_url or ollama_service.base_url
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get detailed Ollama models: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/models/{model_name}/check")
async def check_model_availability(model_name: str, base_url: Optional[str] = None):
    """Check if a specific model is available and loaded"""
    try:
        if not await ollama_service.is_running(base_url):
            raise HTTPException(
                status_code=503,
                detail="Ollama service is not running. Please start Ollama and try again."
            )
        
        result = await ollama_service.check_model_availability(model_name, base_url)
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to check model availability for {model_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
