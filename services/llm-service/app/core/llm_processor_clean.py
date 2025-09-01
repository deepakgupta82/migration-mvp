#!/usr/bin/env python3
"""
LLM Service - Clean Architecture Implementation
Extracted from backend LLM factory with clean separation of concerns

This service handles:
- Process-specific LLM configuration and instantiation  
- Multi-provider support (OpenAI, Anthropic, Gemini, Ollama)
- Configuration management with caching
- API key management
- Model recommendations per process type
"""

import logging
import json
import os
import time
from typing import Optional, Dict, Any, List, Union
from enum import Enum
import httpx

logger = logging.getLogger("llm_service")

# Import LangChain components with graceful fallback
try:
    from langchain.schema.language_model import BaseLanguageModel
    from langchain_openai import ChatOpenAI
    from langchain_anthropic import ChatAnthropic
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_community.llms import Ollama
    LANGCHAIN_AVAILABLE = True
    logger.info("LangChain components loaded successfully")
except ImportError as e:
    logger.warning(f"LangChain not fully available: {e}")
    BaseLanguageModel = None
    LANGCHAIN_AVAILABLE = False

class LLMProcessType(Enum):
    """Process types that require different LLM configurations"""
    ENTITY_EXTRACTION = "entity_extraction"
    CREW_ASSESSMENT = "crew_assessment"
    CREW_DOCUMENTATION = "crew_documentation"
    RAG_SYNTHESIS = "rag_synthesis"
    HYBRID_SEARCH = "hybrid_search"
    CONTENT_SUMMARIZATION = "content_summarization"

class LLMProcessor:
    """
    Clean LLM processing service with proper separation of concerns
    """
    
    def __init__(self):
        self.logger = logger
        self._config_cache = {}
        self._last_cache_update = None
        self._cache_ttl = 30  # 30 seconds cache TTL
        
        # Provider configuration mapping
        self._provider_configs = {
            'openai': {
                'class': ChatOpenAI if LANGCHAIN_AVAILABLE else None,
                'env_key': 'OPENAI_API_KEY',
                'requires_api_key': True
            },
            'anthropic': {
                'class': ChatAnthropic if LANGCHAIN_AVAILABLE else None,
                'env_key': 'ANTHROPIC_API_KEY', 
                'requires_api_key': True
            },
            'gemini': {
                'class': ChatGoogleGenerativeAI if LANGCHAIN_AVAILABLE else None,
                'env_key': 'GOOGLE_API_KEY',
                'requires_api_key': True
            },
            'ollama': {
                'class': Ollama if LANGCHAIN_AVAILABLE else None,
                'env_key': None,
                'requires_api_key': False
            }
        }
        
        # Process-specific model recommendations
        self._model_recommendations = {
            LLMProcessType.ENTITY_EXTRACTION: {
                'openai': ['gpt-4o-mini', 'gpt-3.5-turbo'],
                'anthropic': ['claude-3-haiku-20240307'],
                'gemini': ['gemini-1.5-flash', 'gemini-1.0-pro'],
                'ollama': ['llama3.1:8b', 'mistral:7b']
            },
            LLMProcessType.CREW_ASSESSMENT: {
                'openai': ['gpt-4o', 'gpt-4-turbo'],
                'anthropic': ['claude-3-sonnet-20240229', 'claude-3-opus-20240229'],
                'gemini': ['gemini-1.5-pro', 'gemini-1.0-pro'],
                'ollama': ['llama3.1:70b', 'mixtral:8x7b']
            },
            LLMProcessType.CREW_DOCUMENTATION: {
                'openai': ['gpt-4o', 'gpt-4-turbo'],
                'anthropic': ['claude-3-sonnet-20240229'],
                'gemini': ['gemini-1.5-pro'],
                'ollama': ['llama3.1:70b', 'codestral:22b']
            },
            LLMProcessType.RAG_SYNTHESIS: {
                'openai': ['gpt-4o-mini', 'gpt-3.5-turbo'],
                'anthropic': ['claude-3-haiku-20240307'],
                'gemini': ['gemini-1.5-flash'],
                'ollama': ['llama3.1:8b', 'mistral:7b']
            },
            LLMProcessType.HYBRID_SEARCH: {
                'openai': ['gpt-4o-mini', 'gpt-3.5-turbo'],
                'anthropic': ['claude-3-haiku-20240307'],
                'gemini': ['gemini-1.5-flash'],
                'ollama': ['llama3.1:8b', 'codellama:13b']
            },
            LLMProcessType.CONTENT_SUMMARIZATION: {
                'openai': ['gpt-4o-mini', 'gpt-4o', 'gpt-3.5-turbo'],
                'anthropic': ['claude-3-haiku-20240307', 'claude-3-sonnet-20240229'],
                'gemini': ['gemini-1.5-flash', 'gemini-1.5-pro'],
                'ollama': ['llama3.1:8b', 'mistral:7b']
            }
        }

    async def get_process_llm(self, 
                            process_type: Union[LLMProcessType, str], 
                            project_id: str = None) -> Optional[BaseLanguageModel]:
        """
        Get appropriate LLM instance for specific process type
        
        Args:
            process_type: Type of process requiring LLM
            project_id: Optional project ID for project-specific configuration
            
        Returns:
            Configured LLM instance or None if not available
        """
        if not LANGCHAIN_AVAILABLE:
            self.logger.error("LangChain not available for LLM instantiation")
            return None
            
        try:
            # Normalize process type
            if isinstance(process_type, str):
                process_type = LLMProcessType(process_type)
                
            self.logger.info(f"Getting LLM for process: {process_type.value}")
            
            # Get configuration for this process type
            config = await self._get_process_configuration(process_type, project_id)
            if not config:
                self.logger.warning(f"No LLM configuration found for process: {process_type.value}")
                return None
            
            # Create LLM instance from configuration
            return await self._create_llm_instance(config)
            
        except Exception as e:
            self.logger.error(f"Error getting process LLM for {process_type}: {e}")
            return None

    async def _get_process_configuration(self, 
                                       process_type: LLMProcessType, 
                                       project_id: str = None) -> Optional[Dict[str, Any]]:
        """Get configuration for specific process type"""
        try:
            # Load configurations from cache or database
            configurations = await self._load_configurations()
            
            if not configurations:
                return None
            
            # Look for process-specific configuration
            for config_id, config in configurations.items():
                if config.get('process_type') == process_type.value:
                    if project_id is None or config.get('project_id') == project_id:
                        self.logger.info(f"Found process-specific config for {process_type.value}")
                        return config
            
            # Fallback to default configuration
            for config_id, config in configurations.items():
                if config.get('is_default', False):
                    self.logger.info(f"Using default LLM config for {process_type.value}")
                    return config
                    
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting process configuration: {e}")
            return None

    async def _load_configurations(self) -> Dict[str, Any]:
        """Load LLM configurations with caching"""
        current_time = time.time()
        
        # Return cached data if still valid
        if (self._last_cache_update and 
            (current_time - self._last_cache_update) < self._cache_ttl):
            return self._config_cache
        
        try:
            # Fetch from project service
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "http://localhost:8002/llm-configurations",
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    configs_list = response.json()
                    self._config_cache = {config['id']: config for config in configs_list}
                    self._last_cache_update = current_time
                    self.logger.info(f"Loaded {len(self._config_cache)} LLM configurations")
                else:
                    self.logger.error(f"Failed to load configurations: {response.status_code}")
                    # Keep existing cache on error
                    
        except Exception as e:
            self.logger.warning(f"Error loading configurations from database: {e}")
            # Fallback to JSON file if available
            await self._load_from_json_fallback()
        
        return self._config_cache

    async def _load_from_json_fallback(self):
        """Load configurations from JSON file as fallback"""
        try:
            json_path = os.path.join(os.path.dirname(__file__), "../llm_configurations.json")
            if os.path.exists(json_path):
                with open(json_path, 'r') as f:
                    file_configs = json.load(f)
                self._config_cache = file_configs
                self._last_cache_update = time.time()
                self.logger.info(f"Loaded {len(self._config_cache)} configs from JSON fallback")
            else:
                self.logger.warning("No JSON fallback file found")
        except Exception as e:
            self.logger.error(f"Error loading JSON fallback: {e}")

    async def _create_llm_instance(self, config: Dict[str, Any]) -> Optional[BaseLanguageModel]:
        """Create LLM instance from configuration"""
        try:
            provider = config.get('provider')
            model = config.get('model_name') or config.get('model')
            
            if not provider or not model:
                self.logger.error("Configuration missing provider or model")
                return None
            
            # Get provider configuration
            provider_config = self._provider_configs.get(provider)
            if not provider_config:
                self.logger.error(f"Unsupported provider: {provider}")
                return None
            
            llm_class = provider_config['class']
            if not llm_class:
                self.logger.error(f"LLM class not available for provider: {provider}")
                return None
            
            # Get API key if required
            api_key = None
            if provider_config['requires_api_key']:
                api_key = self._get_api_key(config, provider_config['env_key'])
                if not api_key:
                    self.logger.error(f"No API key available for provider: {provider}")
                    return None
            
            # Get configuration parameters
            temperature = float(config.get('temperature', 0.1))
            # FIX: Don't hard-code default max_tokens to 4000, use a more reasonable default
            # or inherit from the provider/model configuration
            max_tokens = int(config.get('max_tokens', 8000))  # Increased default for better functionality
            
            # Create LLM instance based on provider
            return self._instantiate_llm(provider, llm_class, model, api_key, temperature, max_tokens)
            
        except Exception as e:
            self.logger.error(f"Error creating LLM instance: {e}")
            return None

    def _get_api_key(self, config: Dict[str, Any], env_key: str) -> Optional[str]:
        """Get API key from configuration or environment"""
        # Priority: config > environment variable
        api_key = config.get('api_key')
        if api_key:
            return api_key
        
        if env_key:
            api_key = os.getenv(env_key)
            if api_key:
                return api_key
        
        return None

    def _instantiate_llm(self, 
                        provider: str, 
                        llm_class: type, 
                        model: str, 
                        api_key: Optional[str], 
                        temperature: float, 
                        max_tokens: int) -> BaseLanguageModel:
        """Instantiate LLM based on provider with clean parameters"""
        try:
            if provider == 'openai':
                return llm_class(
                    model=model,
                    api_key=api_key,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            elif provider == 'anthropic':
                return llm_class(
                    model=model,
                    api_key=api_key,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            elif provider == 'gemini':
                # Clean model name for Gemini
                clean_model = model.replace('models/', '').replace('gemini/', '')
                return llm_class(
                    model=clean_model,
                    google_api_key=api_key,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            elif provider == 'ollama':
                return llm_class(
                    model=model,
                    temperature=temperature
                )
            else:
                raise ValueError(f"Unsupported provider: {provider}")
                
        except Exception as e:
            self.logger.error(f"Error instantiating {provider} LLM: {e}")
            raise

    def get_model_recommendations(self, process_type: Union[LLMProcessType, str]) -> Dict[str, List[str]]:
        """Get recommended models for specific process type"""
        if isinstance(process_type, str):
            process_type = LLMProcessType(process_type)
            
        return self._model_recommendations.get(process_type, {})

    async def process_llm_request(self, 
                                process_type: Union[LLMProcessType, str], 
                                prompt: str, 
                                project_id: str = None) -> str:
        """Process LLM request for specific process type"""
        try:
            # Get appropriate LLM instance
            llm = await self.get_process_llm(process_type, project_id)
            if not llm:
                return f"No LLM available for process type: {process_type}"
            
            # Generate response
            if hasattr(llm, 'ainvoke'):
                response = await llm.ainvoke(prompt)
            elif hasattr(llm, 'agenerate'):
                response = await llm.agenerate([prompt])
                response = response.generations[0][0].text
            else:
                # Synchronous fallback
                response = llm.invoke(prompt)
            
            # Extract content from response
            if hasattr(response, 'content'):
                return response.content
            else:
                return str(response)
                
        except Exception as e:
            self.logger.error(f"Error processing LLM request: {e}")
            return f"Error: {str(e)}"

    def invalidate_cache(self):
        """Invalidate configuration cache"""
        self._last_cache_update = None
        self._config_cache = {}
        self.logger.info("Configuration cache invalidated")

    async def health_check(self) -> Dict[str, Any]:
        """Health check for LLM service"""
        return {
            "status": "healthy",
            "langchain_available": LANGCHAIN_AVAILABLE,
            "supported_providers": list(self._provider_configs.keys()),
            "process_types": [pt.value for pt in LLMProcessType],
            "cache_status": {
                "configurations_cached": len(self._config_cache),
                "last_update": self._last_cache_update,
                "cache_ttl": self._cache_ttl
            }
        }

    # Legacy compatibility methods
    async def get_llm_for_entity_extraction(self, project_id: str = None):
        """Legacy compatibility: Get LLM for entity extraction"""
        return await self.get_process_llm(LLMProcessType.ENTITY_EXTRACTION, project_id)

    async def get_llm_for_crew_assessment(self, project_id: str = None):
        """Legacy compatibility: Get LLM for crew assessment"""
        return await self.get_process_llm(LLMProcessType.CREW_ASSESSMENT, project_id)

    async def get_llm_for_crew_documentation(self, project_id: str = None):
        """Legacy compatibility: Get LLM for crew documentation"""
        return await self.get_process_llm(LLMProcessType.CREW_DOCUMENTATION, project_id)

    async def get_default_llm(self, project_id: str = None):
        """Get default LLM configuration"""
        configurations = await self._load_configurations()
        for config in configurations.values():
            if config.get('is_default', False):
                return await self._create_llm_instance(config)
        return None

    # Service API methods
    async def list_providers(self) -> List[str]:
        """List available LLM providers"""
        return list(self._provider_configs.keys())

    async def get_configurations(self) -> Dict[str, Any]:
        """Get all LLM configurations"""
        return await self._load_configurations()

    async def list_process_types(self) -> List[str]:
        """List supported process types"""
        return [pt.value for pt in LLMProcessType]

    async def get_provider_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all providers"""
        status = {}
        
        for provider, config in self._provider_configs.items():
            # Check API key availability
            has_key = True
            if config['requires_api_key'] and config['env_key']:
                has_key = bool(os.getenv(config['env_key']))
            
            status[provider] = {
                "available": config['class'] is not None,
                "configured": has_key,
                "requires_api_key": config['requires_api_key'],
                "recommendations": {
                    pt.value: self._model_recommendations.get(pt, {}).get(provider, [])
                    for pt in LLMProcessType
                }
            }
        
        return status
