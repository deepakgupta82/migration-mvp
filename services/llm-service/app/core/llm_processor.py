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
import asyncio
import re
from typing import Optional, Dict, Any, List, Union
from enum import Enum
import httpx
from .config_client import cfg_get
from .usage_client import get_usage_logger

logger = logging.getLogger("llm_service")


def strip_markdown_code_blocks(text: str) -> str:
    """
    Remove markdown code fences from LLM responses.
    
    Handles patterns like:
    - ```json\\n{...}\\n```
    - ```\\n{...}\\n```
    - ``` {...} ```
    
    Args:
        text: Raw LLM response text
        
    Returns:
        Clean text with markdown code blocks removed
    """
    if not text:
        return text
    
    # Remove opening fence: ```json or ```
    text = re.sub(r'^```(?:json|python|yaml|xml|markdown)?\s*\n?', '', text, flags=re.MULTILINE)
    
    # Remove closing fence: ```
    text = re.sub(r'\n?```\s*$', '', text, flags=re.MULTILINE)
    
    return text.strip()


# Import LangChain components with graceful fallback
try:
    from langchain.schema.language_model import BaseLanguageModel
    from langchain_openai import ChatOpenAI
    from langchain_anthropic import ChatAnthropic
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_community.llms import Ollama
    from langchain.callbacks.base import BaseCallbackHandler
    LANGCHAIN_AVAILABLE = True
    logger.info("LangChain components loaded successfully")
except ImportError as e:
    logger.warning(f"LangChain not fully available: {e}")
    BaseLanguageModel = None
    BaseCallbackHandler = None
    LANGCHAIN_AVAILABLE = False

class CorrelationIdCallbackHandler(BaseCallbackHandler):
    """Custom LangChain callback handler to track correlation IDs in LLM calls"""
    
    def __init__(self, correlation_id: Optional[str] = None):
        super().__init__()
        self.correlation_id = correlation_id or "unknown"
        
    def on_llm_start(self, serialized, prompts, **kwargs):
        """Called when LLM starts processing"""
        logger.info(f"LLM call started | corr_id={self.correlation_id} provider={serialized.get('name', 'unknown')}")
        
    def on_llm_end(self, response, **kwargs):
        """Called when LLM finishes processing"""
        logger.info(f"LLM call completed | corr_id={self.correlation_id}")
        
    def on_llm_error(self, error, **kwargs):
        """Called when LLM encounters an error"""
        logger.error(f"LLM call failed | corr_id={self.correlation_id} error={str(error)}")
        
    def on_chain_start(self, serialized, inputs, **kwargs):
        """Called when chain starts"""
        logger.debug(f"Chain started | corr_id={self.correlation_id}")
        
    def on_chain_end(self, outputs, **kwargs):
        """Called when chain ends"""
        logger.debug(f"Chain completed | corr_id={self.correlation_id}")

class LLMProcessType(Enum):
    """Process types that require different LLM configurations"""
    ENTITY_EXTRACTION = "entity_extraction"
    FACT_EXTRACTION = "fact_extraction"
    DOCUMENT_ANALYSIS = "document_analysis"  # Added for document type classification
    DOCUMENT_ASSESSMENT = "document_assessment"  # Added for document quality assessment
    CREW_ASSESSMENT = "crew_assessment"
    CREW_DOCUMENTATION = "crew_documentation"
    RAG_SYNTHESIS = "rag_synthesis"
    HYBRID_SEARCH = "hybrid_search"
    CONTENT_SUMMARIZATION = "content_summarization"
    CONVERSATION = "conversation"
    TABLE_EXTRACTION = "table_extraction"
    DIAGRAM_UNDERSTANDING = "diagram_understanding"

class LLMProcessor:
    """
    Clean LLM processing service with proper separation of concerns
    """
    
    def __init__(self):
        self.logger = logger
        self._config_cache = {}
        self._last_cache_update = None
        self._cache_ttl = 30  # 30 seconds cache TTL
        # Prefer centralized config, then env, then default
        self._service_token = (
            cfg_get(["llm_service", "service_auth_token"]) or os.getenv("SERVICE_AUTH_TOKEN", "service-backend-token")
        )
        # Enforcement: require project-assigned LLM config; disallow global fallback when enabled
        enf_val = cfg_get(["llm_service", "enforce_project_llm"], os.getenv("ENFORCE_PROJECT_LLM", "true"))
        if isinstance(enf_val, bool):
            self._enforce_project_llm = enf_val
        else:
            self._enforce_project_llm = str(enf_val).lower() in ("1", "true", "yes")
        
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
            LLMProcessType.FACT_EXTRACTION: {
                'openai': ['gpt-4o-mini', 'gpt-3.5-turbo'],
                'anthropic': ['claude-3-haiku-20240307'],
                'gemini': ['gemini-1.5-flash', 'gemini-1.0-pro'],
                'ollama': ['llama3.1:8b', 'mistral:7b']
            },
            LLMProcessType.DOCUMENT_ANALYSIS: {
                'openai': ['gpt-4o-mini', 'gpt-3.5-turbo'],
                'anthropic': ['claude-3-haiku-20240307'],
                'gemini': ['gemini-1.5-flash', 'gemini-1.0-pro'],
                'ollama': ['llama3.1:8b', 'mistral:7b']
            },
            LLMProcessType.TABLE_EXTRACTION: {
                'openai': ['gpt-4o', 'gpt-4o-mini'],
                'anthropic': ['claude-3-5-sonnet-20241022', 'claude-3-haiku-20240307'],
                'gemini': ['gemini-1.5-pro', 'gemini-1.5-flash'],
                'ollama': ['llama3.1:70b', 'llama3.1:8b']
            },
            LLMProcessType.DIAGRAM_UNDERSTANDING: {
                'openai': ['gpt-4o'],
                'anthropic': ['claude-3-5-sonnet-20241022'],
                'gemini': ['gemini-1.5-pro'],
                'ollama': ['llama3.1:70b']
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
            },
            LLMProcessType.CONVERSATION: {
                'openai': ['gpt-4o', 'gpt-4o-mini', 'gpt-3.5-turbo'],
                'anthropic': ['claude-3-sonnet-20240229', 'claude-3-haiku-20240307'],
                'gemini': ['gemini-1.5-pro', 'gemini-1.5-flash'],
                'ollama': ['llama3.1:8b', 'mistral:7b']
            }
        }

    async def verify_dependencies(self) -> Dict[str, bool]:
        """Verify all service dependencies"""
        dependencies = {}
        
        # Check LangChain availability
        dependencies['langchain'] = LANGCHAIN_AVAILABLE
        if LANGCHAIN_AVAILABLE:
            self.logger.info("✓ LangChain components available")
        else:
            self.logger.error("✗ LangChain components not available")
        
        # Check project service connectivity
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "http://localhost:8002/health",
                    timeout=5.0
                )
                dependencies['project_service'] = response.status_code == 200
                if dependencies['project_service']:
                    self.logger.info("✓ Project service connection verified")
                else:
                    self.logger.error("✗ Project service connection failed")
        except Exception as e:
            dependencies['project_service'] = False
            self.logger.error(f"✗ Project service connection failed: {e}")
        
        # Check provider availability
        providers_available = 0
        for provider, config in self._provider_configs.items():
            if config['class'] is not None:
                providers_available += 1
        
        dependencies['providers_available'] = providers_available > 0
        if providers_available > 0:
            self.logger.info(f"✓ {providers_available} LLM providers available")
        else:
            self.logger.error("✗ No LLM providers available")
            
        return dependencies

    async def get_process_llm(self,
                              process_type: Union[LLMProcessType, str],
                              project_id: Optional[str] = None,
                              corr_id: Optional[str] = None,
                              allow_global: bool = True) -> Optional[Any]:
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
            
            # If enforcement is enabled, disallow global fallback and require project_id
            effective_allow_global = False if self._enforce_project_llm else allow_global
            if self._enforce_project_llm and not project_id:
                self.logger.error("Project ID is required when enforce_project_llm is enabled")
                return None

            # Get configuration for this process type
            config = await self._get_process_configuration(process_type, project_id, corr_id=corr_id, allow_global=effective_allow_global)
            if not config:
                self.logger.warning(f"No LLM configuration found for process: {process_type.value}")
                return None
            # Emit a clear, structured log of which configuration was selected
            try:
                cfg_id = config.get('id') or config.get('config_id')
                provider = config.get('provider')
                model = config.get('model_name') or config.get('model')
                is_default = bool(config.get('is_default', False))
                origin = 'default' if is_default else ('project_specific' if project_id else 'global')
                self.logger.info(
                    f"LLM config selected | process={process_type.value} project_id={project_id or '-'} "
                    f"origin={origin} config_id={cfg_id or '-'} provider={provider or '-'} model={model or '-'}"
                )
            except Exception as _:
                # Best-effort logging; never break selection
                pass
            
            # Create LLM instance from configuration
            # Prefer strict JSON responses for extraction workflows
            prefer_json = False
            pt_val = process_type.value if isinstance(process_type, LLMProcessType) else str(process_type)
            if pt_val in (LLMProcessType.ENTITY_EXTRACTION.value, LLMProcessType.FACT_EXTRACTION.value, "entity_extraction", "fact_extraction"):
                prefer_json = True
            return await self._create_llm_instance(config, corr_id, prefer_json=prefer_json)
            
        except Exception as e:
            self.logger.error(f"Error getting process LLM for {process_type}: {e}")
            return None

    async def _get_process_configuration(self,
                                         process_type: LLMProcessType,
                                         project_id: str = None,
                                         corr_id: Optional[str] = None,
                                         allow_global: bool = True) -> Optional[Dict[str, Any]]:
        """Get configuration for specific process type with project-aware fallback.

        Order:
        1) Project's per-process config (via project-service)
        2) Project's default LLM settings
        3) Global LLM configurations (first available)
        """
        try:
            headers = self._build_auth_headers(corr_id)

            # 1) Project-specific per-process config
            if project_id:
                proc_cfg = await self._fetch_project_process_config(project_id, process_type.value, headers)
                if proc_cfg:
                    # If API key is referenced by id, resolve it
                    cfg = await self._materialize_api_key(proc_cfg, headers)
                    if cfg:
                        return cfg

                # 2) Fallback to project default settings
                proj = await self._fetch_project_details(project_id, headers)
                if proj and (proj.get('llm_provider') and proj.get('llm_model')):
                    base_cfg = {
                        'provider': proj.get('llm_provider'),
                        'model': proj.get('llm_model'),
                        'temperature': float(proj.get('llm_temperature') or 0.1),
                        'max_tokens': int(proj.get('llm_max_tokens') or 4000),
                        'api_key_id': proj.get('llm_api_key_id')
                    }
                    cfg = await self._materialize_api_key(base_cfg, headers)
                    if cfg:
                        self.logger.info(
                            f"Using project default LLM config for {process_type.value} (project_id={project_id})"
                        )
                        return cfg

            # 3) Global configurations list (from /llm-configurations) - only if allowed and not enforced
            if allow_global and not self._enforce_project_llm:
                configurations = await self._load_configurations(headers=headers)
                if configurations:
                    # Choose the first valid configuration
                    for config_id, config in configurations.items():
                        if config.get('provider') and (config.get('model') or config.get('model_name')):
                            self.logger.info(
                                f"Using global LLM config for {process_type.value} (config_id={config.get('id') or config_id})"
                            )
                            return config

            return None

        except Exception as e:
            self.logger.error(f"Error getting process configuration: {e}")
            return None

    async def _load_configurations(self, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
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
                    headers=headers or self._build_auth_headers(None),
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
            self.logger.warning(f"Error loading configurations from project-service: {e}")
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

    async def _create_llm_instance(self, config: Dict[str, Any], correlation_id: Optional[str] = None, prefer_json: bool = False) -> Optional[Any]:
        """Create LLM instance from configuration with correlation ID tracking"""
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
            # Default max_tokens for modern LLMs with high output capacity
            # Gemini 2.5 Pro: 1M input, 32,768 output tokens
            # GPT-4o: 128K input, 16,384 output tokens
            # Claude 3.5 Sonnet: 200K input, 8,192 output tokens
            max_tokens = int(config.get('max_tokens', 32768))  # Support high-capacity models
            
            # Create callback handler for correlation ID tracking
            callbacks = []
            if LANGCHAIN_AVAILABLE and BaseCallbackHandler and correlation_id:
                callbacks.append(CorrelationIdCallbackHandler(correlation_id))
            
            # Create LLM instance based on provider with increased timeout and callbacks
            # Timeout increased to 1800s (30 min) for heavy concurrent document processing
            # with 10-20 documents - entity extraction and relationship analysis can be intensive
            if provider == 'openai':
                return llm_class(
                    model=model,
                    api_key=api_key,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=1800.0,  # 30 minutes for heavy LLM processing
                    max_retries=3,  # Added retry mechanism
                    callbacks=callbacks if callbacks else None,
                    # Encourage strict JSON output when supported by the provider
                    **({"response_format": {"type": "json_object"}} if prefer_json else {})
                )
            elif provider == 'anthropic':
                return llm_class(
                    model=model,
                    api_key=api_key,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=1800.0,  # 30 minutes for heavy LLM processing
                    max_retries=3,  # Added retry mechanism
                    callbacks=callbacks if callbacks else None
                )
            elif provider == 'gemini':
                # Clean model name for Gemini
                clean_model = model.replace('models/', '').replace('gemini/', '')
                return llm_class(
                    model=clean_model,
                    google_api_key=api_key,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=1800.0,  # 30 minutes for heavy LLM processing
                    max_retries=3,  # Added retry mechanism
                    callbacks=callbacks if callbacks else None,
                    # Prefer native JSON responses when supported by the provider
                    **({"response_mime_type": "application/json"} if prefer_json else {})
                )
            elif provider == 'ollama':
                return llm_class(
                    model=model,
                    temperature=temperature,
                    timeout=1800.0,  # 30 minutes for heavy LLM processing
                    max_retries=3,  # Added retry mechanism
                    callbacks=callbacks if callbacks else None
                )
            else:
                raise ValueError(f"Unsupported provider: {provider}")
                
        except Exception as e:
            self.logger.error(f"Error creating LLM instance: {e}")
            return None

    def _build_auth_headers(self, corr_id: Optional[str]) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._service_token}"
        }
        if corr_id:
            headers["X-Correlation-ID"] = corr_id
        return headers

    async def _fetch_project_details(self, project_id: str, headers: Dict[str, str]) -> Optional[Dict[str, Any]]:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"http://localhost:8002/projects/{project_id}", headers=headers, timeout=10.0)
                if resp.status_code == 200:
                    return resp.json()
                else:
                    self.logger.warning(f"Failed to fetch project {project_id}: {resp.status_code}")
                    return None
        except Exception as e:
            self.logger.error(f"Error fetching project details: {e}")
            return None

    async def _fetch_project_process_config(self, project_id: str, process_key: str, headers: Dict[str, str]) -> Optional[Dict[str, Any]]:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"http://localhost:8002/projects/{project_id}/llm-process-configs", headers=headers, timeout=10.0)
                if resp.status_code == 200:
                    cfgs = resp.json() or {}
                    cfg = cfgs.get(process_key)
                    # The endpoint returns shaped data under keys; when called via FastAPI response_model,
                    # fields may be nested differently. Handle dict or wrapped response.
                    if not cfg and isinstance(cfgs, dict):
                        cfg = cfgs.get(process_key)
                    if cfg and isinstance(cfg, dict):
                        self.logger.info(f"Found project process config for {process_key} (project_id={project_id})")
                        return cfg
                else:
                    self.logger.warning(f"Failed to fetch process config for project {project_id}: {resp.status_code}")
                    return None
        except Exception as e:
            self.logger.error(f"Error fetching process config: {e}")
            return None

    async def _fetch_llm_config_by_id(self, config_id: str, headers: Dict[str, str]) -> Optional[Dict[str, Any]]:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"http://localhost:8002/llm-configurations/{config_id}", headers=headers, timeout=10.0)
                if resp.status_code == 200:
                    return resp.json()
                else:
                    self.logger.warning(f"Failed to fetch LLM config {config_id}: {resp.status_code}")
                    return None
        except Exception as e:
            self.logger.error(f"Error fetching LLM config by id: {e}")
            return None

    async def _materialize_api_key(self, cfg: Dict[str, Any], headers: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """Ensure api_key is present in cfg if api_key_id is provided."""
        if not cfg:
            return None
        if cfg.get('api_key'):
            return cfg
        api_key_id = cfg.get('api_key_id') or cfg.get('llm_api_key_id')
        if api_key_id:
            full = await self._fetch_llm_config_by_id(api_key_id, headers)
            if full and full.get('api_key'):
                out = dict(cfg)
                out['api_key'] = full['api_key']
                # Align model key name if needed
                if 'model_name' not in out and 'model' in out:
                    out['model_name'] = out['model']
                return out
        return cfg

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
                        max_tokens: int,
                        correlation_id: Optional[str] = None) -> Any:
        """Instantiate LLM based on provider with clean parameters and correlation ID tracking"""
        try:
            # Create callback handler for correlation ID tracking
            callbacks = []
            if LANGCHAIN_AVAILABLE and BaseCallbackHandler and correlation_id:
                callbacks.append(CorrelationIdCallbackHandler(correlation_id))
            
            if provider == 'openai':
                return llm_class(
                    model=model,
                    api_key=api_key,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    callbacks=callbacks if callbacks else None
                )
            elif provider == 'anthropic':
                return llm_class(
                    model=model,
                    api_key=api_key,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    callbacks=callbacks if callbacks else None
                )
            elif provider == 'gemini':
                # Clean model name for Gemini
                clean_model = model.replace('models/', '').replace('gemini/', '')
                return llm_class(
                    model=clean_model,
                    google_api_key=api_key,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    max_retries=2,  # Limit retries to prevent excessive API calls
                    request_timeout=30,  # 30 second timeout
                    callbacks=callbacks if callbacks else None
                )
            elif provider == 'ollama':
                return llm_class(
                    model=model,
                    temperature=temperature,
                    callbacks=callbacks if callbacks else None
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
                                  project_id: str = None,
                                  corr_id: Optional[str] = None,
                                  allow_global: bool = True) -> str:
        """Process LLM request for specific process type with robust error handling"""
        # Capture start time for duration metrics
        start_ts = time.time()
        provider_for_log: Optional[str] = None
        model_for_log: Optional[str] = None
        max_tokens_cfg: Optional[int] = None
        try:
            debug_llm_cfg = cfg_get(["llm_service", "debug_llm_logs"], None)
            if isinstance(debug_llm_cfg, bool):
                debug_llm = debug_llm_cfg
            else:
                debug_llm = os.getenv("DEBUG_LLM_LOGS", "false").lower() in ("1", "true", "yes")
            
            # Get appropriate LLM instance
            effective_allow_global = False if getattr(self, "_enforce_project_llm", False) else allow_global
            if getattr(self, "_enforce_project_llm", False) and not project_id:
                raise ValueError("Project ID is required by policy: enforce_project_llm=true")
            # Resolve configuration first to record provider/model even if instantiation fails
            resolved_cfg = await self.resolve_process_configuration(process_type, project_id, corr_id=corr_id, allow_global=effective_allow_global)
            if resolved_cfg:
                provider_for_log = resolved_cfg.get("provider")
                model_for_log = resolved_cfg.get("model")
                try:
                    max_tokens_cfg = int(resolved_cfg.get("max_tokens") or 0) or None
                except Exception:
                    max_tokens_cfg = None

            llm = await self.get_process_llm(process_type, project_id, corr_id=corr_id, allow_global=effective_allow_global)
            if not llm:
                error_msg = f"No project-assigned LLM configuration found for process type: {getattr(process_type, 'value', process_type)}"
                self.logger.error(error_msg)
                # Under enforcement, treat as hard error
                if getattr(self, "_enforce_project_llm", False):
                    # Log failed usage
                    try:
                        dur_ms = int((time.time() - start_ts) * 1000)
                        await get_usage_logger().log_llm_call(
                            project_id=project_id,
                            correlation_id=corr_id,
                            provider=provider_for_log,
                            model=model_for_log,
                            prompt=prompt,
                            response=None,
                            input_tokens=self._estimate_tokens(prompt),
                            output_tokens=0,
                            total_tokens=self._estimate_tokens(prompt),
                            duration_ms=dur_ms,
                            status="error",
                            error_message=error_msg,
                            metadata={"process_type": getattr(process_type, 'value', process_type)},
                        )
                    except Exception:
                        pass
                    raise ValueError(error_msg)
                # Non-enforced: return fallback and log
                try:
                    dur_ms = int((time.time() - start_ts) * 1000)
                    await get_usage_logger().log_llm_call(
                        project_id=project_id,
                        correlation_id=corr_id,
                        provider=provider_for_log,
                        model=model_for_log,
                        prompt=prompt,
                        response=None,
                        input_tokens=self._estimate_tokens(prompt),
                        output_tokens=0,
                        total_tokens=self._estimate_tokens(prompt),
                        duration_ms=dur_ms,
                        status="error",
                        error_message=error_msg,
                        metadata={"process_type": getattr(process_type, 'value', process_type)},
                    )
                except Exception:
                    pass
                return self._create_fallback_response(process_type, error_msg)
            
            # Structured pre-call logging
            safe_prompt = prompt[:5000] if debug_llm else f"{prompt[:200]}... (truncated)"
            self.logger.info(
                f"LLM call | process={getattr(process_type, 'value', process_type)} project_id={project_id or '-'} "
                f"corr_id={corr_id or '-'} prompt_chars={len(prompt)}"
            )
            if debug_llm:
                self.logger.debug(f"LLM prompt preview: {safe_prompt}")

            # Enhance prompt with correlation ID for debugging (for entity extraction and similar analytical tasks)
            enhanced_prompt = prompt
            if corr_id and (isinstance(process_type, LLMProcessType) and process_type in [
                LLMProcessType.ENTITY_EXTRACTION, LLMProcessType.FACT_EXTRACTION, 
                LLMProcessType.CREW_ASSESSMENT, LLMProcessType.CONTENT_SUMMARIZATION
            ] or (isinstance(process_type, str) and process_type in [
                "entity_extraction", "fact_extraction", "crew_assessment", "content_summarization"
            ])):
                # Add correlation ID as metadata comment at the end of the prompt
                enhanced_prompt = f"{prompt}\n\n---\nCorrelation ID: {corr_id}"
            
            # Log full prompt before LLM call (not truncated)
            self.logger.info(f"Full LLM prompt for {process_type} (corr_id={corr_id or '-'}):\n{enhanced_prompt}\n{'='*80}")

            # Generate response with retry logic
            response = None
            max_retries = 3
            
            for attempt in range(max_retries):
                try:
                    self.logger.info(f"LLM API call attempt {attempt + 1}/3 | corr_id={corr_id or '-'} provider={llm.__class__.__name__}")
                    
                    # Enhanced invocation with different methods for better compatibility
                    if hasattr(llm, 'ainvoke'):
                        response = await llm.ainvoke(enhanced_prompt)
                    elif hasattr(llm, 'agenerate'):
                        response = await llm.agenerate([enhanced_prompt])
                        response = response.generations[0][0].text
                    elif hasattr(llm, 'invoke'):
                        # Try message format first for ChatModels
                        try:
                            from langchain.schema import HumanMessage
                            if hasattr(llm, '_llm_type') and 'chat' in str(llm._llm_type).lower():
                                response = llm.invoke([HumanMessage(content=enhanced_prompt)])
                            else:
                                response = llm.invoke(enhanced_prompt)
                        except Exception:
                            # Fallback to direct string invoke
                            response = llm.invoke(enhanced_prompt)
                    else:
                        # Synchronous fallback
                        response = llm.invoke(enhanced_prompt)
                    break
                except Exception as retry_error:
                    self.logger.warning(f"LLM call attempt {attempt + 1} failed | corr_id={corr_id or '-'} error={retry_error}")
                    if attempt == max_retries - 1:
                        # Log failure before raising
                        try:
                            dur_ms = int((time.time() - start_ts) * 1000)
                            await get_usage_logger().log_llm_call(
                                project_id=project_id,
                                correlation_id=corr_id,
                                provider=provider_for_log,
                                model=model_for_log,
                                prompt=enhanced_prompt,
                                response=None,
                                input_tokens=self._estimate_tokens(enhanced_prompt),
                                output_tokens=0,
                                total_tokens=self._estimate_tokens(enhanced_prompt),
                                duration_ms=dur_ms,
                                status="error",
                                error_message=str(retry_error),
                                metadata={"process_type": getattr(process_type, 'value', process_type)},
                            )
                        except Exception:
                            pass
                        raise retry_error
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
            
            # Extract and validate content from response
            if response is None:
                error_msg = "LLM returned None response"
                self.logger.error(f"{error_msg} | corr_id={corr_id or '-'}")
                try:
                    dur_ms = int((time.time() - start_ts) * 1000)
                    await get_usage_logger().log_llm_call(
                        project_id=project_id,
                        correlation_id=corr_id,
                        provider=provider_for_log,
                        model=model_for_log,
                        prompt=enhanced_prompt,
                        response=None,
                        input_tokens=self._estimate_tokens(enhanced_prompt),
                        output_tokens=0,
                        total_tokens=self._estimate_tokens(enhanced_prompt),
                        duration_ms=dur_ms,
                        status="error",
                        error_message=error_msg,
                        metadata={"process_type": getattr(process_type, 'value', process_type)},
                    )
                except Exception:
                    pass
                return self._create_fallback_response(process_type, error_msg)
            
            # Extract content from response
            out = response.content if hasattr(response, 'content') else str(response)
            
            # Extract actual token counts from response metadata
            in_tokens = None
            out_tokens = None
            try:
                if hasattr(response, 'response_metadata'):
                    metadata = response.response_metadata
                    # Gemini format
                    if 'usage_metadata' in metadata:
                        usage = metadata['usage_metadata']
                        in_tokens = usage.get('prompt_token_count')
                        out_tokens = usage.get('candidates_token_count')
                    # OpenAI format
                    elif 'token_usage' in metadata:
                        usage = metadata['token_usage']
                        in_tokens = usage.get('prompt_tokens')
                        out_tokens = usage.get('completion_tokens')
                    # Alternative OpenAI format
                    elif 'usage' in metadata:
                        usage = metadata['usage']
                        in_tokens = usage.get('prompt_tokens')
                        out_tokens = usage.get('completion_tokens')
            except Exception as token_err:
                self.logger.debug(f"Could not extract token counts from response: {token_err}")
            
            # Fallback to estimation if actual counts unavailable
            if in_tokens is None:
                in_tokens = self._estimate_tokens(enhanced_prompt)
            if out_tokens is None:
                out_tokens = self._estimate_tokens(out)
            
            # Validate output
            if not out or out.strip() == "":
                error_msg = "LLM returned empty response"
                # Enhanced debugging for empty responses
                self.logger.error(f"{error_msg} - Response object: {type(response)} | corr_id={corr_id or '-'}")
                if hasattr(response, '__dict__'):
                    self.logger.error(f"Response attributes: {list(response.__dict__.keys())} | corr_id={corr_id or '-'}")
                if hasattr(response, 'response_metadata'):
                    self.logger.error(f"Response metadata: {response.response_metadata} | corr_id={corr_id or '-'}")
                
                # For entity extraction, try to create a more helpful fallback
                if (isinstance(process_type, LLMProcessType) and process_type == LLMProcessType.ENTITY_EXTRACTION) or \
                   (isinstance(process_type, str) and process_type == "entity_extraction"):
                    # Log prompt details for debugging
                    self.logger.error(f"Empty response for entity extraction. Prompt length: {len(prompt)} chars | corr_id={corr_id or '-'}")
                    if len(prompt) > 15000:
                        self.logger.error("Prompt may be too long for model - consider chunking")
                    
                try:
                    dur_ms = int((time.time() - start_ts) * 1000)
                    await get_usage_logger().log_llm_call(
                        project_id=project_id,
                        correlation_id=corr_id,
                        provider=provider_for_log,
                        model=model_for_log,
                        prompt=enhanced_prompt,
                        response="",
                        input_tokens=self._estimate_tokens(enhanced_prompt),
                        output_tokens=0,
                        total_tokens=self._estimate_tokens(enhanced_prompt),
                        duration_ms=dur_ms,
                        status="error",
                        error_message=error_msg,
                        metadata={"process_type": getattr(process_type, 'value', process_type)},
                    )
                except Exception:
                    pass
                return self._create_fallback_response(process_type, error_msg)
            
            # For entity/fact extraction, validate JSON structure strictly
            is_entity = (isinstance(process_type, LLMProcessType) and process_type == LLMProcessType.ENTITY_EXTRACTION) or \
                        (isinstance(process_type, str) and process_type == "entity_extraction")
            is_fact = (isinstance(process_type, LLMProcessType) and process_type == LLMProcessType.FACT_EXTRACTION) or \
                      (isinstance(process_type, str) and process_type == "fact_extraction")
            if is_entity or is_fact:
                # CRITICAL FIX: Strip markdown code blocks BEFORE any JSON parsing
                # This prevents 100% entity extraction failure when LLM wraps responses in ```json blocks
                original_out = out
                out = strip_markdown_code_blocks(out)
                if out != original_out:
                    self.logger.info(f"Stripped markdown code blocks from LLM response | original_len={len(original_out)} cleaned_len={len(out)}")
                
                # Log full response to console for debugging (not truncated)
                self.logger.info(f"Full LLM response for {process_type}:\n{out}\n{'='*80}")
                
                try:
                    import json
                    parsed = json.loads(out)
                    
                    # SEPARATE HANDLING FOR FACTS VS ENTITIES
                    # Facts should remain as array [{text, category, confidence}]
                    # Entities need {entities: [], relationships: []} structure
                    
                    if is_fact:
                        # Facts extraction - expect array of {text, category, confidence}
                        if isinstance(parsed, list):
                            # Perfect - facts are already in correct format
                            self.logger.info(f"Fact extraction validation complete: {len(parsed)} facts")
                        elif isinstance(parsed, dict):
                            # Check if dict contains a facts array under a key
                            if 'facts' in parsed and isinstance(parsed['facts'], list):
                                self.logger.info(f"Extracting facts from 'facts' key: {len(parsed['facts'])} items")
                                out = json.dumps(parsed['facts'])
                            elif 'extracted_facts' in parsed and isinstance(parsed['extracted_facts'], list):
                                self.logger.info(f"Extracting facts from 'extracted_facts' key: {len(parsed['extracted_facts'])} items")
                                out = json.dumps(parsed['extracted_facts'])
                            else:
                                # Dict doesn't have facts array - might be single fact
                                if 'text' in parsed:
                                    self.logger.warning("Single fact dict returned, wrapping in array")
                                    out = json.dumps([parsed])
                                else:
                                    self.logger.error(f"Unexpected fact extraction response format: dict with keys {list(parsed.keys())}")
                            self.logger.info("Fact extraction JSON validation complete")
                        else:
                            self.logger.error(f"Unexpected fact extraction type: {type(parsed)}")
                    
                    elif is_entity:
                        # Entity extraction - enforce {entities: [], relationships: []} structure
                        if not isinstance(parsed, dict):
                            self.logger.warning(f"Entity extraction response not a dict, wrapping: {type(parsed)}")
                            wrapped = {"entities": parsed if isinstance(parsed, list) else [parsed], "relationships": []}
                            out = json.dumps(wrapped)
                            parsed = wrapped
                        elif "entities" not in parsed:
                            self.logger.warning("Entity extraction response missing 'entities' key, adding empty list")
                            parsed["entities"] = []
                            out = json.dumps(parsed)
                        elif "relationships" not in parsed:
                            self.logger.warning("Entity extraction response missing 'relationships' key, adding empty list")
                            parsed["relationships"] = []
                            out = json.dumps(parsed)
                        
                        # Validate entity structure
                        entities = parsed.get("entities", [])
                        relationships = parsed.get("relationships", [])
                        
                        if not isinstance(entities, list):
                            self.logger.warning(f"Entities field is not a list: {type(entities)}, converting")
                            parsed["entities"] = [entities] if entities else []
                            out = json.dumps(parsed)
                        
                        if not isinstance(relationships, list):
                            self.logger.warning(f"Relationships field is not a list: {type(relationships)}, converting")
                            parsed["relationships"] = [relationships] if relationships else []
                            out = json.dumps(parsed)
                        
                        # Log successful validation
                        entity_count = len(parsed.get("entities", []))
                        rel_count = len(parsed.get("relationships", []))
                        self.logger.info(f"Entity extraction validation complete: {entity_count} entities, {rel_count} relationships")
                    
                except json.JSONDecodeError as json_error:
                    self.logger.warning(f"Extraction response not valid JSON: {json_error}")
                    prev = out
                    # Check if response is empty or whitespace
                    if not prev or not prev.strip():
                        self.logger.error("LLM returned empty response - creating fallback")
                        out = self._create_fallback_response(process_type, "LLM returned empty response")
                    else:
                        # Strip common markdown fences and retry
                        out = prev.replace('```json', '').replace('```', '').strip()
                        try:
                            _ = json.loads(out)
                        except Exception:
                            self.logger.warning(f"Response content (first 500 chars): {prev[:500]}...")
                            # Try to repair and extract JSON from the response
                            out = self._enhanced_json_repair(prev, process_type)
            
            if debug_llm:
                preview = out[:2000]
                self.logger.debug(f"LLM response preview (first 2000 chars): {preview}")
            else:
                # Log token counts when available
                token_info = ""
                if in_tokens and out_tokens:
                    token_info = f" prompt_tokens={in_tokens} completion_tokens={out_tokens} total_tokens={in_tokens + out_tokens}"
                elif in_tokens or out_tokens:
                    token_info = f" prompt_tokens={in_tokens or 'N/A'} completion_tokens={out_tokens or 'N/A'}"
                self.logger.info(f"LLM call complete | chars={len(out)}{token_info} corr_id={corr_id or '-'}")
            # Emit success usage log
            try:
                dur_ms = int((time.time() - start_ts) * 1000)
                # Note: in_tokens and out_tokens already extracted from response metadata above
                total_tokens = (in_tokens or 0) + (out_tokens or 0)
                await get_usage_logger().log_llm_call(
                    project_id=project_id,
                    correlation_id=corr_id,
                    provider=provider_for_log,
                    model=model_for_log,
                    prompt=enhanced_prompt,
                    response=out,
                    # Full conversation logging (Fix #3)
                    prompt_text=enhanced_prompt,
                    response_text=out,
                    messages=None,  # Could be populated for multi-turn conversations
                    input_tokens=in_tokens,
                    output_tokens=out_tokens,
                    total_tokens=total_tokens,
                    duration_ms=dur_ms,
                    status="success",
                    metadata={
                        "process_type": getattr(process_type, 'value', process_type),
                        "max_tokens_cfg": max_tokens_cfg,
                        "tokens_source": "actual" if (in_tokens and not self._estimate_tokens(enhanced_prompt) == in_tokens) else "estimated"
                    },
                )
            except Exception:
                pass
            
            return out
                
        except Exception as e:
            error_msg = f"Error processing LLM request: {e}"
            self.logger.error(f"{error_msg} | corr_id={corr_id or '-'} process_type={getattr(process_type, 'value', process_type)}")
            # Emit error usage log (best-effort)
            try:
                dur_ms = int((time.time() - start_ts) * 1000)
                await get_usage_logger().log_llm_call(
                    project_id=project_id,
                    correlation_id=corr_id,
                    provider=provider_for_log,
                    model=model_for_log,
                    prompt=prompt,
                    response=None,
                    input_tokens=self._estimate_tokens(prompt),
                    output_tokens=0,
                    total_tokens=self._estimate_tokens(prompt),
                    duration_ms=dur_ms,
                    status="error",
                    error_message=str(e),
                    metadata={"process_type": getattr(process_type, 'value', process_type)},
                )
            except Exception:
                pass
            return self._create_fallback_response(process_type, error_msg)

    def _estimate_tokens(self, text: Optional[str]) -> Optional[int]:
        """Very rough token estimate: word count * 1.3. Safe when tokenizers unavailable."""
        try:
            if not text:
                return 0
            # Basic heuristic: words multiplied by 1.3, cap to a large reasonable bound
            wc = len(str(text).split())
            est = int(wc * 1.3)
            return min(est, 200000)
        except Exception:
            return None

    def _create_fallback_response(self, process_type: Union[LLMProcessType, str], error_msg: str) -> str:
        """Create a fallback response for failed LLM calls"""
        if (isinstance(process_type, LLMProcessType) and process_type == LLMProcessType.ENTITY_EXTRACTION) or \
           (isinstance(process_type, str) and process_type == "entity_extraction"):
            return json.dumps({
                "entities": [],
                "relationships": [],
                "error": error_msg,
                "status": "failed"
            })
        else:
            return f"Error: {error_msg}"

    def _repair_and_extract_json(self, response_text: str, process_type: Union[LLMProcessType, str]) -> str:
        """Advanced JSON repair and extraction with multiple strategies"""
        import json
        import re

        try:
            # Strategy 1: Try to fix common JSON issues
            cleaned_text = self._clean_json_response(response_text)

            # Strategy 2: Try to parse the cleaned text
            try:
                parsed = json.loads(cleaned_text)
                if (isinstance(process_type, LLMProcessType) and process_type == LLMProcessType.ENTITY_EXTRACTION) or \
                   (isinstance(process_type, str) and process_type == "entity_extraction"):
                    return self._normalize_entity_extraction_response(parsed)
                else:
                    return json.dumps(parsed)
            except json.JSONDecodeError:
                pass

            # Strategy 3: Use the existing extraction method as fallback
            return self._extract_or_create_json(response_text, process_type)

        except Exception as e:
            self.logger.error(f"Failed to repair JSON: {e}")
            return self._create_fallback_response(process_type, f"JSON repair failed: {str(e)}")

    def _clean_json_response(self, response_text: str) -> str:
        """Clean and repair common JSON formatting issues"""
        import re

        # Remove markdown code blocks
        response_text = re.sub(r'```json\s*', '', response_text)
        response_text = re.sub(r'```\s*$', '', response_text)

        # Remove common prefixes that might interfere with JSON parsing
        prefixes_to_remove = [
            r'^Here is the result:\s*',
            r'^The result is:\s*',
            r'^Response:\s*',
            r'^Answer:\s*',
            r'^Output:\s*',
            r'^Result:\s*',
            r'^JSON:\s*',
            r'^The extracted entities are:\s*',
            r'^Entity extraction result:\s*',
            r'^Here are the extracted entities:\s*',
            r'^Based on the document, here are the entities:\s*'
        ]

        for prefix in prefixes_to_remove:
            response_text = re.sub(prefix, '', response_text, flags=re.IGNORECASE | re.MULTILINE)

        # Fix common JSON issues
        response_text = response_text.strip()

        # Fix unterminated strings by ensuring quotes are balanced
        response_text = self._fix_unterminated_strings(response_text)

        # Fix trailing commas
        response_text = re.sub(r',(\s*[}\]])', r'\1', response_text)

        # Fix missing commas between array elements or object properties
        response_text = re.sub(r'}(\s*")', r'},\1', response_text)
        response_text = re.sub(r'](\s*")', r'],\1', response_text)

        return response_text

    def _fix_unterminated_strings(self, text: str) -> str:
        """Fix unterminated string literals in JSON"""
        import re

        # Find all string literals (quoted text)
        string_pattern = r'"(?:[^"\\]|\\.)*"'
        strings = re.findall(string_pattern, text)

        # Check for unterminated strings
        lines = text.split('\n')
        fixed_lines = []

        for line in lines:
            # Count quotes in the line
            quote_count = line.count('"') - line.count('\\"')  # Subtract escaped quotes

            # If odd number of quotes, the string is likely unterminated
            if quote_count % 2 != 0:
                # Try to fix by adding closing quote at end of line
                if not line.rstrip().endswith('"'):
                    line = line.rstrip() + '"'

            fixed_lines.append(line)

        return '\n'.join(fixed_lines)
        """Extract JSON from response text or create valid JSON structure"""
        import json
        import re
        
        try:
            # Strategy 1: Try to find JSON in the response using multiple patterns
            json_patterns = [
                r'```json\s*(\{.*?\})\s*```',  # JSON code blocks
                r'```json\s*(\[.*?\])\s*```',  # JSON array code blocks
                r'(\{[\s\S]*?\n\})',  # Multi-line JSON objects
                r'(\[[\s\S]*?\])',  # Multi-line JSON arrays
                r'\{[^{}]*\{[^{}]*\}[^{}]*\}',  # Nested JSON objects
                r'\{[^{}]*\}',  # Simple JSON objects
                r'\[.*\]',  # Simple JSON arrays
            ]
            
            for pattern in json_patterns:
                matches = re.findall(pattern, response_text, re.DOTALL | re.MULTILINE)
                for match in matches:
                    try:
                        # Clean up the match
                        cleaned_match = match.strip()
                        if cleaned_match.startswith('```json'):
                            cleaned_match = cleaned_match[7:]
                        if cleaned_match.endswith('```'):
                            cleaned_match = cleaned_match[:-3]
                        cleaned_match = cleaned_match.strip()
                        
                        # Try to parse the cleaned match
                        parsed = json.loads(cleaned_match)
                        
                        # Validate and normalize for entity extraction
                        if (isinstance(process_type, LLMProcessType) and process_type == LLMProcessType.ENTITY_EXTRACTION) or \
                           (isinstance(process_type, str) and process_type == "entity_extraction"):
                            return self._normalize_entity_extraction_response(parsed)
                        else:
                            return json.dumps(parsed)
                            
                    except json.JSONDecodeError:
                        continue
            
            # Strategy 2: Look for JSON-like content after common prefixes
            json_prefixes = [
                "Here is the result:",
                "The result is:",
                "Response:",
                "Answer:",
                "Output:",
                "Result:",
                "JSON:",
                "The extracted entities are:",
                "Entity extraction result:"
            ]
            
            for prefix in json_prefixes:
                if prefix.lower() in response_text.lower():
                    # Find content after the prefix
                    prefix_index = response_text.lower().find(prefix.lower())
                    content_after_prefix = response_text[prefix_index + len(prefix):].strip()
                    
                    # Try to extract JSON from the remaining content
                    json_match = re.search(r'(\{[\s\S]*?\n\}|\[[\s\S]*?\])', content_after_prefix, re.DOTALL)
                    if json_match:
                        try:
                            parsed = json.loads(json_match.group(1))
                            if (isinstance(process_type, LLMProcessType) and process_type == LLMProcessType.ENTITY_EXTRACTION) or \
                               (isinstance(process_type, str) and process_type == "entity_extraction"):
                                return self._normalize_entity_extraction_response(parsed)
                            else:
                                return json.dumps(parsed)
                        except json.JSONDecodeError:
                            continue
            
            # Strategy 3: Try to parse the entire response as JSON (fallback)
            try:
                parsed = json.loads(response_text.strip())
                if (isinstance(process_type, LLMProcessType) and process_type == LLMProcessType.ENTITY_EXTRACTION) or \
                   (isinstance(process_type, str) and process_type == "entity_extraction"):
                    return self._normalize_entity_extraction_response(parsed)
                else:
                    return json.dumps(parsed)
            except json.JSONDecodeError:
                pass
            
            # Strategy 4: Create minimal structure based on process type
            if (isinstance(process_type, LLMProcessType) and process_type == LLMProcessType.ENTITY_EXTRACTION) or \
               (isinstance(process_type, str) and process_type == "entity_extraction"):
                return json.dumps({
                    "entities": [],
                    "relationships": [],
                    "raw_response": response_text[:500],
                    "status": "parsing_failed",
                    "extraction_method": "fallback"
                })
            else:
                return json.dumps({
                    "response": response_text, 
                    "status": "parsing_failed",
                    "extraction_method": "fallback"
                })
                
        except Exception as e:
            self.logger.error(f"Failed to extract/create JSON: {e}")
            return json.dumps({
                "error": str(e), 
                "status": "failed",
                "extraction_method": "error_fallback"
            })
    
    def _normalize_entity_extraction_response(self, parsed: Any) -> str:
        """Normalize entity extraction response to ensure consistent structure"""
        import json
        
        try:
            # Ensure it's a dictionary
            if not isinstance(parsed, dict):
                if isinstance(parsed, list):
                    parsed = {"entities": parsed, "relationships": []}
                else:
                    parsed = {"entities": [parsed] if parsed else [], "relationships": []}
            
            # Ensure entities field exists and is a list
            if "entities" not in parsed:
                parsed["entities"] = []
            elif not isinstance(parsed["entities"], list):
                parsed["entities"] = [parsed["entities"]] if parsed["entities"] else []
            
            # Ensure relationships field exists and is a list
            if "relationships" not in parsed:
                parsed["relationships"] = []
            elif not isinstance(parsed["relationships"], list):
                parsed["relationships"] = [parsed["relationships"]] if parsed["relationships"] else []
            
            # Validate entity structure (optional - be lenient)
            validated_entities = []
            for entity in parsed["entities"]:
                if isinstance(entity, dict):
                    # Ensure required fields
                    if "name" not in entity:
                        entity["name"] = str(entity.get("name", f"entity_{len(validated_entities)}"))
                    validated_entities.append(entity)
                elif isinstance(entity, str):
                    # Convert string entities to proper format
                    validated_entities.append({
                        "name": entity,
                        "type": "extracted_from_text",
                        "confidence": 0.6
                    })
            
            parsed["entities"] = validated_entities
            
            return json.dumps(parsed)
            
        except Exception as e:
            self.logger.error(f"Failed to normalize entity extraction response: {e}")
            return json.dumps({
                "entities": [],
                "relationships": [],
                "error": str(e),
                "status": "normalization_failed"
            })

    def _repair_and_extract_json(self, response_text: str, process_type: Union[LLMProcessType, str]) -> str:
        """Advanced JSON repair and extraction with multiple strategies"""
        import json
        import re

        try:
            # Strategy 1: Try to fix common JSON issues
            cleaned_text = self._clean_json_response(response_text)

            # Strategy 2: Try to parse the cleaned text
            try:
                parsed = json.loads(cleaned_text)
                if (isinstance(process_type, LLMProcessType) and process_type == LLMProcessType.ENTITY_EXTRACTION) or \
                   (isinstance(process_type, str) and process_type == "entity_extraction"):
                    return self._normalize_entity_extraction_response(parsed)
                else:
                    return json.dumps(parsed)
            except json.JSONDecodeError:
                pass

            # Strategy 3: Use the existing extraction method as fallback
            return self._extract_or_create_json(response_text, process_type)

        except Exception as e:
            self.logger.error(f"Failed to repair JSON: {e}")
            return self._create_fallback_response(process_type, f"JSON repair failed: {str(e)}")

    def _clean_json_response(self, response_text: str) -> str:
        """Clean and repair common JSON formatting issues"""
        import re

        # Remove markdown code blocks
        response_text = re.sub(r'```json\s*', '', response_text)
        response_text = re.sub(r'```\s*$', '', response_text)

        # Remove common prefixes that might interfere with JSON parsing
        prefixes_to_remove = [
            r'^Here is the result:\s*',
            r'^The result is:\s*',
            r'^Response:\s*',
            r'^Answer:\s*',
            r'^Output:\s*',
            r'^Result:\s*',
            r'^JSON:\s*',
            r'^The extracted entities are:\s*',
            r'^Entity extraction result:\s*',
            r'^Here are the extracted entities:\s*',
            r'^Based on the document, here are the entities:\s*'
        ]

        for prefix in prefixes_to_remove:
            response_text = re.sub(prefix, '', response_text, flags=re.IGNORECASE | re.MULTILINE)

        # Fix common JSON issues
        response_text = response_text.strip()

        # Fix unterminated strings by ensuring quotes are balanced
        response_text = self._fix_unterminated_strings(response_text)

        # Fix trailing commas
        response_text = re.sub(r',(\s*[}\]])', r'\1', response_text)

        # Fix missing commas between array elements or object properties
        response_text = re.sub(r'}(\s*")', r'},\1', response_text)
        response_text = re.sub(r'](\s*")', r'],\1', response_text)

        return response_text

    def _fix_unterminated_strings(self, text: str) -> str:
        """Fix unterminated string literals in JSON"""
        import re

        # Find all string literals (quoted text)
        string_pattern = r'"(?:[^"\\]|\\.)*"'
        strings = re.findall(string_pattern, text)

        # Check for unterminated strings
        lines = text.split('\n')
        fixed_lines = []

        for line in lines:
            # Count quotes in the line
            quote_count = line.count('"') - line.count('\\"')  # Subtract escaped quotes

            # If odd number of quotes, the string is likely unterminated
            if quote_count % 2 != 0:
                # Try to fix by adding closing quote at end of line
                if not line.rstrip().endswith('"'):
                    line = line.rstrip() + '"'

            fixed_lines.append(line)

        return '\n'.join(fixed_lines)

    def _enhanced_json_repair(self, response_text: str, process_type: Union[LLMProcessType, str]) -> str:
        """Enhanced JSON repair specifically for LLM responses with common formatting issues"""
        import json
        import re

        try:
            self.logger.info("Attempting enhanced JSON repair for malformed LLM response")

            # Preserve the original unmodified text for safe fallback extraction
            original_text = response_text

            # NEW: Detect if response was likely truncated at max_tokens limit
            # Updated thresholds for high-capacity models (Gemini 2.5 Pro: 32K output)
            truncation_indicators = [
                'Unterminated string',  # Common JSON error for truncated responses
                len(response_text) > 120000,  # Very large responses (>120KB, ~30K tokens)
                not response_text.rstrip().endswith('}'),  # Missing closing brace
                response_text.count('{') > response_text.count('}'),  # Unbalanced braces
            ]
            
            if any(truncation_indicators):
                self.logger.warning(
                    f"Response appears truncated (len={len(response_text)}). "
                    "Consider increasing max_tokens in LLM config for very large extractions. "
                    "Current model limits: Gemini 2.5 Pro=32,768 tokens, GPT-4o=16,384 tokens."
                )
                # Try to salvage what we have by closing the JSON structure
                response_text = self._fix_truncated_json(response_text, process_type)

            # Strategy 1: Handle unterminated strings (most common issue from logs)
            response_text = self._fix_unterminated_strings_advanced(response_text)

            # Strategy 2: Remove common LLM prefixes and formatting
            response_text = self._clean_llm_response_prefixes(response_text)

            # Strategy 3: Fix structural JSON issues
            response_text = self._fix_common_json_structural_issues(response_text)

            # Strategy 4: Try to parse the repaired text
            try:
                parsed = json.loads(response_text)
                self.logger.info("Enhanced JSON repair successful")
                if (isinstance(process_type, LLMProcessType) and process_type == LLMProcessType.ENTITY_EXTRACTION) or \
                   (isinstance(process_type, str) and process_type == "entity_extraction"):
                    return self._normalize_entity_extraction_response(parsed)
                else:
                    return json.dumps(parsed)
            except json.JSONDecodeError as e:
                self.logger.warning(f"Enhanced repair failed, falling back to extraction: {e}")
                # IMPORTANT: fall back using the ORIGINAL text to avoid compounding repair errors
                return self._extract_json_from_mixed_content(original_text, process_type)

        except Exception as e:
            self.logger.error(f"Enhanced JSON repair failed: {e}")
            return self._create_fallback_response(process_type, f"Enhanced JSON repair failed: {str(e)}")

    def _fix_truncated_json(self, text: str, process_type: Union[LLMProcessType, str]) -> str:
        """Attempt to salvage a truncated JSON response by closing structures"""
        import json
        
        try:
            # Try to find where the truncation occurred
            # Look for the last complete entity or relationship
            is_entity_extraction = (
                (isinstance(process_type, LLMProcessType) and process_type == LLMProcessType.ENTITY_EXTRACTION) or
                (isinstance(process_type, str) and process_type == "entity_extraction")
            )
            
            if is_entity_extraction:
                # Find the last complete entity/relationship block
                # Look for pattern: {...}, followed by more content or truncation
                last_complete_comma = text.rfind('},')
                if last_complete_comma > 0:
                    # Truncate at the last complete item
                    text = text[:last_complete_comma + 1]
                    # Close the arrays and root object
                    if '"relationships"' in text:
                        # We're in relationships array
                        text += ']}'
                    else:
                        # We're in entities array
                        text += '], "relationships": []}'
                    
                    # Count entities by counting "id" fields (extract pattern outside f-string)
                    id_pattern = '"id"'
                    entity_count = text.count(id_pattern)
                    self.logger.info(f"Salvaged {entity_count} entities from truncated response")
                    return text
            
            # Generic truncation fix - try to balance braces
            open_braces = text.count('{')
            close_braces = text.count('}')
            open_brackets = text.count('[')
            close_brackets = text.count(']')
            
            # Add missing closing characters
            text = text.rstrip().rstrip(',')  # Remove trailing comma if any
            text += ']' * (open_brackets - close_brackets)
            text += '}' * (open_braces - close_braces)
            
            return text
            
        except Exception as e:
            self.logger.warning(f"Failed to fix truncated JSON: {e}")
            return text

    def _fix_unterminated_strings_advanced(self, text: str) -> str:
        """Advanced fix for unterminated strings in LLM responses"""
        import re

        # Pattern to find potential unterminated strings
        # Look for quoted strings that don't have closing quotes
        lines = text.split('\n')
        fixed_lines = []

        for line in lines:
            # Skip lines that are clearly not JSON
            if not any(char in line for char in ['{', '}', '[', ']', '"', ':', ',']):
                fixed_lines.append(line)
                continue

            # Count unescaped quotes
            quote_positions = []
            i = 0
            while i < len(line):
                if line[i] == '"' and (i == 0 or line[i-1] != '\\'):
                    quote_positions.append(i)
                i += 1

            # If odd number of quotes, try to fix
            if len(quote_positions) % 2 != 0:
                # Find the last quote and check if it needs a closing quote
                last_quote_pos = quote_positions[-1]

                # Look for the next structural character after the quote
                remaining = line[last_quote_pos + 1:]
                next_structural = re.search(r'[}\],]', remaining)

                if next_structural:
                    # Insert closing quote before the structural character
                    insert_pos = last_quote_pos + 1 + next_structural.start()
                    line = line[:insert_pos] + '"' + line[insert_pos:]
                else:
                    # Add closing quote at end of line if no structural chars found
                    line = line.rstrip() + '"'

            fixed_lines.append(line)

        return '\n'.join(fixed_lines)

    def _clean_llm_response_prefixes(self, text: str) -> str:
        """Remove common LLM response prefixes that interfere with JSON parsing"""
        import re

        # Common prefixes to remove
        prefixes_to_remove = [
            r'^Here is the JSON response:\s*',
            r'^The JSON result is:\s*',
            r'^Response in JSON format:\s*',
            r'^JSON output:\s*',
            r'^The extracted information in JSON:\s*',
            r'^Entity extraction results:\s*',
            r'^Here are the entities found:\s*',
            r'^Based on the analysis:\s*',
            r'^The following entities were extracted:\s*',
            r'^Entity extraction completed\.\s*',
            r'^Analysis result:\s*',
            r'^Result:\s*',
            r'^Output:\s*',
            r'^Answer:\s*',
            r'^Final answer:\s*',
            r'^The answer is:\s*'
        ]

        for prefix in prefixes_to_remove:
            text = re.sub(prefix, '', text, flags=re.IGNORECASE | re.MULTILINE)

        # Remove markdown formatting
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*$', '', text)
        text = re.sub(r'`([^`]*)`', r'\1', text)  # Remove inline code formatting

        return text.strip()

    def _fix_common_json_structural_issues(self, text: str) -> str:
        """Fix common structural issues in JSON from LLM responses"""
        import re

        # Fix trailing commas before closing braces/brackets
        text = re.sub(r',(\s*[}\]])', r'\1', text)

        # Avoid aggressive structural rewrites which can corrupt valid JSON (e.g., removing quotes from keys).
        # Keep the function conservative; deeper fixes are handled by extraction routines.

        return text

    def _extract_json_from_mixed_content(self, text: str, process_type: Union[LLMProcessType, str]) -> str:
        """Extract JSON from mixed content with text and JSON.
        Improved: scan ALL candidates and prefer the largest valid object containing 'entities'/'relationships'.
        """
        import json
        import re

        try:
            cleaned_text = self._clean_llm_response_prefixes(text or "")

            # Find ALL top-level JSON candidates (objects and arrays)
            def _find_all_json_candidates(s: str) -> List[str]:
                stack = []
                start_idx = None
                in_string = False
                esc = False
                out: List[str] = []
                for i, ch in enumerate(s):
                    if in_string:
                        if esc:
                            esc = False
                        elif ch == '\\':
                            esc = True
                        elif ch == '"':
                            in_string = False
                        continue
                    if ch == '"':
                        in_string = True
                        continue
                    if ch in '{[':
                        if not stack:
                            start_idx = i
                        stack.append(ch)
                    elif ch in '}]' and stack:
                        open_ch = stack.pop()
                        if (open_ch == '{' and ch != '}') or (open_ch == '[' and ch != ']'):
                            # mismatched, reset object capture
                            stack.clear()
                            start_idx = None
                            continue
                        if not stack and start_idx is not None:
                            out.append(s[start_idx:i+1])
                            start_idx = None
                return out

            candidates = _find_all_json_candidates(cleaned_text)

            best_obj = None
            best_score = -1
            best_len = 0
            parsed_candidates = 0

            for blob in candidates:
                try:
                    obj = json.loads(blob)
                except json.JSONDecodeError:
                    # try minimal trailing comma repair
                    try:
                        repaired = re.sub(r",\s*([}\]])", r"\\1", blob)
                        obj = json.loads(repaired)
                    except Exception:
                        continue
                parsed_candidates += 1
                score = 0
                ent_len = rel_len = 0
                if isinstance(obj, dict):
                    ents = obj.get("entities")
                    rels = obj.get("relationships")
                    if ents is not None:
                        score += 2
                        if isinstance(ents, list):
                            ent_len = len(ents)
                            if ent_len > 0:
                                score += 2
                    if rels is not None:
                        score += 1
                        if isinstance(rels, list):
                            rel_len = len(rels)
                            if rel_len > 0:
                                score += 1
                # Prefer dicts for entity extraction; arrays are allowed for other processes
                if not isinstance(obj, dict) and ((isinstance(process_type, LLMProcessType) and process_type == LLMProcessType.ENTITY_EXTRACTION) or (isinstance(process_type, str) and process_type == "entity_extraction")):
                    score -= 1  # slight penalty
                if score > best_score or (score == best_score and len(blob) > best_len):
                    best_obj = obj
                    best_score = score
                    best_len = len(blob)

            # If we found a suitable candidate, return it (normalized when entity_extraction)
            if best_obj is not None:
                try:
                    ent_count = len(best_obj.get("entities", [])) if isinstance(best_obj, dict) else 0
                    rel_count = len(best_obj.get("relationships", [])) if isinstance(best_obj, dict) else 0
                except Exception:
                    ent_count = rel_count = 0
                self.logger.info(
                    f"JSON candidate selection: found={len(candidates)} parsed={parsed_candidates} "
                    f"selected_len={best_len} entities={ent_count} relationships={rel_count}"
                )
                if (isinstance(process_type, LLMProcessType) and process_type == LLMProcessType.ENTITY_EXTRACTION) or \
                   (isinstance(process_type, str) and process_type == "entity_extraction"):
                    return self._normalize_entity_extraction_response(best_obj)
                else:
                    return json.dumps(best_obj)

            # Fallback regex-based search: collect ALL matches and apply same selection
            regex_patterns = [
                r'\{[^{}]*\{[^{}]*\}[^{}]*\}',  # nested
                r'\{[\s\S]*?\}',               # objects
                r'\[[\s\S]*?\]',               # arrays
            ]
            regex_candidates: List[str] = []
            for pat in regex_patterns:
                regex_candidates.extend(re.findall(pat, cleaned_text, re.DOTALL))

            best_obj = None
            best_score = -1
            best_len = 0
            parsed_candidates = 0
            for blob in regex_candidates:
                try:
                    obj = json.loads(blob.strip())
                except json.JSONDecodeError:
                    continue
                parsed_candidates += 1
                score = 0
                ent_len = rel_len = 0
                if isinstance(obj, dict):
                    ents = obj.get("entities")
                    rels = obj.get("relationships")
                    if ents is not None:
                        score += 2
                        if isinstance(ents, list):
                            ent_len = len(ents)
                            if ent_len > 0:
                                score += 2
                    if rels is not None:
                        score += 1
                        if isinstance(rels, list):
                            rel_len = len(rels)
                            if rel_len > 0:
                                score += 1
                if not isinstance(obj, dict) and ((isinstance(process_type, LLMProcessType) and process_type == LLMProcessType.ENTITY_EXTRACTION) or (isinstance(process_type, str) and process_type == "entity_extraction")):
                    score -= 1
                if score > best_score or (score == best_score and len(blob) > best_len):
                    best_obj = obj
                    best_score = score
                    best_len = len(blob)

            if best_obj is not None:
                try:
                    ent_count = len(best_obj.get("entities", [])) if isinstance(best_obj, dict) else 0
                    rel_count = len(best_obj.get("relationships", [])) if isinstance(best_obj, dict) else 0
                except Exception:
                    ent_count = rel_count = 0
                self.logger.info(
                    f"JSON candidate selection (regex): found={len(regex_candidates)} parsed={parsed_candidates} "
                    f"selected_len={best_len} entities={ent_count} relationships={rel_count}"
                )
                if (isinstance(process_type, LLMProcessType) and process_type == LLMProcessType.ENTITY_EXTRACTION) or \
                   (isinstance(process_type, str) and process_type == "entity_extraction"):
                    return self._normalize_entity_extraction_response(best_obj)
                else:
                    return json.dumps(best_obj)

            # Last resort: construct from text content
            return self._construct_json_from_text(text, process_type)

        except Exception as e:
            self.logger.error(f"Failed to extract JSON from mixed content: {e}")
            return self._create_fallback_response(process_type, f"JSON extraction failed: {str(e)}")

    def _construct_json_from_text(self, text: str, process_type: Union[LLMProcessType, str]) -> str:
        """Construct valid JSON from unstructured text content"""
        import json

        try:
            # For entity extraction, try to extract entities from text
            if (isinstance(process_type, LLMProcessType) and process_type == LLMProcessType.ENTITY_EXTRACTION) or \
               (isinstance(process_type, str) and process_type == "entity_extraction"):

                # Look for entity-like patterns in the text
                entities = []
                lines = text.split('\n')

                for line in lines:
                    line = line.strip()
                    if line and len(line) > 2 and not line.startswith(('http', 'Error', 'Note')):
                        # Simple heuristic: treat non-empty lines as potential entities
                        if ',' in line:
                            # Split comma-separated entities
                            parts = [part.strip() for part in line.split(',') if part.strip()]
                            for part in parts:
                                if len(part) > 1:
                                    entities.append({
                                        "name": part,
                                        "type": "extracted_from_text",
                                        "confidence": 0.5
                                    })
                        else:
                            entities.append({
                                "name": line,
                                "type": "extracted_from_text",
                                "confidence": 0.5
                            })

                return json.dumps({
                    "entities": entities[:20],  # Limit to 20 entities
                    "relationships": [],
                    "extraction_method": "text_parsing_fallback",
                    "status": "partial_success"
                })

            else:
                # For other process types, return the text as-is in a structured format
                return json.dumps({
                    "response": text,
                    "extraction_method": "text_fallback",
                    "status": "partial_success"
                })

        except Exception as e:
            self.logger.error(f"Failed to construct JSON from text: {e}")
            return self._create_fallback_response(process_type, f"Text construction failed: {str(e)}")

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

    async def get_llm_for_fact_extraction(self, project_id: str = None):
        """Legacy compatibility: Get LLM for fact extraction"""
        return await self.get_process_llm(LLMProcessType.FACT_EXTRACTION, project_id)

    async def get_llm_for_crew_assessment(self, project_id: str = None):
        """Legacy compatibility: Get LLM for crew assessment"""
        return await self.get_process_llm(LLMProcessType.CREW_ASSESSMENT, project_id)

    async def get_llm_for_crew_documentation(self, project_id: str = None):
        """Legacy compatibility: Get LLM for crew documentation"""
        return await self.get_process_llm(LLMProcessType.CREW_DOCUMENTATION, project_id)

    async def get_default_llm(self, project_id: str = None) -> Optional[Any]:
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

    # Public resolver for process configuration (provider/model) without creating an LLM instance
    async def resolve_process_configuration(self,
                                            process_type: Union[LLMProcessType, str],
                                            project_id: Optional[str] = None,
                                            corr_id: Optional[str] = None,
                                            allow_global: bool = True) -> Optional[Dict[str, Any]]:
        try:
            if isinstance(process_type, str):
                process_type = LLMProcessType(process_type)
            effective_allow_global = False if getattr(self, "_enforce_project_llm", False) else allow_global
            if getattr(self, "_enforce_project_llm", False) and not project_id:
                self.logger.error("Project ID is required when enforce_project_llm is enabled")
                return None
            cfg = await self._get_process_configuration(process_type, project_id, corr_id=corr_id, allow_global=effective_allow_global)
            if not cfg:
                return None
            # Normalize keys
            out = {
                "provider": cfg.get("provider"),
                "model": cfg.get("model_name") or cfg.get("model"),
                "temperature": cfg.get("temperature"),
                "max_tokens": cfg.get("max_tokens"),
                "is_default": bool(cfg.get("is_default", False)),
                "config_id": cfg.get("id") or cfg.get("config_id"),
                "project_id": project_id,
                "process_type": process_type.value
            }
            return out
        except Exception as e:
            self.logger.error(f"Error resolving process configuration: {e}")
            return None
