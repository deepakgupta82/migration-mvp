"""
Ollama Service Integration for querying available models
"""
import aiohttp
import asyncio
import logging
from typing import List, Dict, Any, Optional
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class OllamaService:
    """Service for interacting with local Ollama installation"""
    
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url.rstrip('/')
        
    async def is_running(self, base_url: Optional[str] = None) -> bool:
        """Check if Ollama service is running at the specified endpoint"""
        url = (base_url or self.base_url).rstrip('/')
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.get(f"{url}/api/version") as response:
                    return response.status == 200
        except Exception as e:
            logger.debug(f"Ollama not running at {url}: {e}")
            return False
    
    async def get_available_models(self, base_url: Optional[str] = None) -> List[str]:
        """Get list of available Ollama models with full names including tags"""
        url = (base_url or self.base_url).rstrip('/')
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get(f"{url}/api/tags") as response:
                    if response.status != 200:
                        raise HTTPException(
                            status_code=503,
                            detail="Ollama service is not responding. Please ensure Ollama is running."
                        )
                    
                    data = await response.json()
                    models = []
                    
                    for model in data.get('models', []):
                        # Keep full model name including tag (e.g., "llama3:8b-instruct-q4_K_M")
                        name = model.get('name', '')
                        if name:
                            models.append(name)
                    
                    # Sort by name for consistent ordering
                    models.sort()
                    return models
                    
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get Ollama models from {url}: {e}")
            raise HTTPException(
                status_code=503,
                detail=f"Failed to connect to Ollama: {str(e)}"
            )
    
    async def check_model_availability(self, model_name: str, base_url: Optional[str] = None) -> Dict[str, Any]:
        """Check if a specific model is available and loaded in Ollama"""
        url = (base_url or self.base_url).rstrip('/')
        try:
            # First check if the model is in the available models list
            available_models = await self.get_available_models(base_url)
            if model_name not in available_models:
                return {
                    "available": False,
                    "loaded": False,
                    "error": f"Model '{model_name}' is not installed. Available models: {', '.join(available_models)}",
                    "suggestion": f"Install the model with: ollama pull {model_name}"
                }
            
            # Check if model is currently loaded (running) by trying to get model info
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                # Try to show model info (this loads the model if not already loaded)
                payload = {"name": model_name}
                async with session.post(f"{url}/api/show", json=payload) as response:
                    if response.status == 200:
                        model_info = await response.json()
                        return {
                            "available": True,
                            "loaded": True,
                            "model_info": model_info,
                            "size": model_info.get('details', {}).get('parameter_size', 'unknown'),
                            "family": model_info.get('details', {}).get('family', 'unknown')
                        }
                    else:
                        error_text = await response.text()
                        return {
                            "available": True,
                            "loaded": False,
                            "error": f"Model exists but couldn't be loaded: {error_text}"
                        }
                        
        except Exception as e:
            logger.error(f"Error checking model availability for {model_name}: {e}")
            return {
                "available": False,
                "loaded": False,
                "error": f"Error checking model: {str(e)}"
            }

    async def get_detailed_models(self, base_url: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get detailed list of available Ollama models"""
        url = (base_url or self.base_url).rstrip('/')
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get(f"{url}/api/tags") as response:
                    if response.status != 200:
                        raise HTTPException(
                            status_code=503,
                            detail="Ollama service is not responding. Please ensure Ollama is running."
                        )
                    
                    data = await response.json()
                    models = []
                    
                    for model in data.get('models', []):
                        models.append({
                            'name': model.get('name', ''),
                            'size': model.get('size', 0),
                            'modified_at': model.get('modified_at', ''),
                            'digest': model.get('digest', ''),
                            'details': model.get('details', {}),
                            'format': model.get('format', ''),
                            'family': model.get('family', '')
                        })
                    
                    # Sort by name for consistent ordering
                    models.sort(key=lambda x: x['name'])
                    return models
                    
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get detailed Ollama models from {url}: {e}")
            raise HTTPException(
                status_code=503,
                detail=f"Failed to connect to Ollama: {str(e)}"
            )
    
    async def test_model(self, model_name: str, prompt: str = "Hello", base_url: Optional[str] = None) -> Dict[str, Any]:
        """Test if a specific Ollama model is working"""
        url = (base_url or self.base_url).rstrip('/')
        
        # First check if model is available and loaded
        availability = await self.check_model_availability(model_name, base_url)
        if not availability["available"]:
            return {
                "success": False,
                "error": availability["error"],
                "suggestion": availability.get("suggestion", ""),
                "endpoint": url
            }
        
        if not availability["loaded"]:
            return {
                "success": False,
                "error": f"Model '{model_name}' is installed but not loaded. {availability.get('error', '')}",
                "suggestion": f"The model may need to be initialized. Try: ollama run {model_name}",
                "endpoint": url
            }
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                payload = {
                    "model": model_name,
                    "prompt": prompt,
                    "stream": False
                }
                
                async with session.post(f"{url}/api/generate", json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        # Check if it's a model not found error
                        if "model" in error_text.lower() and ("not found" in error_text.lower() or "404" in error_text):
                            return {
                                "success": False,
                                "error": f"Model '{model_name}' not found. Maybe you need to pull the model with `ollama pull {model_name}`.",
                                "suggestion": f"ollama pull {model_name}",
                                "endpoint": url
                            }
                        else:
                            return {
                                "success": False,
                                "error": f"Model test failed: {error_text}",
                                "endpoint": url
                            }
                    
                    result = await response.json()
                    return {
                        "success": True,
                        "response": result.get('response', ''),
                        "model": model_name,
                        "endpoint": url,
                        "total_duration": result.get('total_duration', 0),
                        "load_duration": result.get('load_duration', 0),
                        "prompt_eval_duration": result.get('prompt_eval_duration', 0),
                        "model_info": availability.get("model_info", {})
                    }
                    
        except Exception as e:
            logger.error(f"Failed to test Ollama model {model_name} at {url}: {e}")
            return {
                "success": False,
                "error": f"Model test failed: {str(e)}",
                "endpoint": url
            }

    async def test_endpoint_and_get_models(self, base_url: str) -> Dict[str, Any]:
        """Test endpoint and get available models in one call - for frontend validation"""
        url = base_url.rstrip('/')
        try:
            # Test if Ollama is running
            is_running = await self.is_running(url)
            if not is_running:
                return {
                    "success": False,
                    "error": "Ollama service is not running at this endpoint",
                    "endpoint": url,
                    "models": []
                }

            # Get available models
            models = await self.get_available_models(url)
            return {
                "success": True,
                "endpoint": url,
                "models": models,
                "message": f"Connected successfully. Found {len(models)} models."
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "endpoint": url,
                "models": []
            }

# Global instance
ollama_service = OllamaService()
