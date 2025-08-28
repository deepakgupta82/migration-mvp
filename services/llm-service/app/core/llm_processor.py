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
from typing import Optional, Dict, Any, List, Union
from enum import Enum
import httpx
from .config_client import cfg_get

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
                              corr_id: Optional[str] = None) -> Optional[Any]:
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
            config = await self._get_process_configuration(process_type, project_id, corr_id=corr_id)
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
            return await self._create_llm_instance(config)
            
        except Exception as e:
            self.logger.error(f"Error getting process LLM for {process_type}: {e}")
            return None

    async def _get_process_configuration(self,
                                         process_type: LLMProcessType,
                                         project_id: str = None,
                                         corr_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
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

            # 3) Global configurations list (from /llm-configurations)
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

    async def _create_llm_instance(self, config: Dict[str, Any]) -> Optional[Any]:
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
            max_tokens = int(config.get('max_tokens', 32000))
            
            # Create LLM instance based on provider with increased timeout
            if provider == 'openai':
                return llm_class(
                    model=model,
                    api_key=api_key,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=60.0,  # Increased from default
                    max_retries=3  # Added retry mechanism
                )
            elif provider == 'anthropic':
                return llm_class(
                    model=model,
                    api_key=api_key,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=60.0,  # Increased from default
                    max_retries=3  # Added retry mechanism
                )
            elif provider == 'gemini':
                # Clean model name for Gemini
                clean_model = model.replace('models/', '').replace('gemini/', '')
                return llm_class(
                    model=clean_model,
                    google_api_key=api_key,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=60.0,  # Increased from default
                    max_retries=3  # Added retry mechanism
                )
            elif provider == 'ollama':
                return llm_class(
                    model=model,
                    temperature=temperature,
                    timeout=60.0,  # Increased from default
                    max_retries=3  # Added retry mechanism
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
                        max_tokens: int) -> Any:
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
                                  project_id: str = None,
                                  corr_id: Optional[str] = None) -> str:
        """Process LLM request for specific process type with robust error handling"""
        try:
            debug_llm_cfg = cfg_get(["llm_service", "debug_llm_logs"], None)
            if isinstance(debug_llm_cfg, bool):
                debug_llm = debug_llm_cfg
            else:
                debug_llm = os.getenv("DEBUG_LLM_LOGS", "false").lower() in ("1", "true", "yes")
            
            # Get appropriate LLM instance
            llm = await self.get_process_llm(process_type, project_id, corr_id=corr_id)
            if not llm:
                error_msg = f"No LLM available for process type: {process_type}"
                self.logger.error(error_msg)
                return self._create_fallback_response(process_type, error_msg)
            
            # Structured pre-call logging
            safe_prompt = prompt[:5000] if debug_llm else f"{prompt[:200]}... (truncated)"
            self.logger.info(
                f"LLM call | process={getattr(process_type, 'value', process_type)} project_id={project_id or '-'} "
                f"corr_id={corr_id or '-'} prompt_chars={len(prompt)}"
            )
            if debug_llm:
                self.logger.debug(f"LLM prompt preview: {safe_prompt}")

            # Generate response with retry logic
            response = None
            max_retries = 3
            
            for attempt in range(max_retries):
                try:
                    # Enhanced invocation with different methods for better compatibility
                    if hasattr(llm, 'ainvoke'):
                        response = await llm.ainvoke(prompt)
                    elif hasattr(llm, 'agenerate'):
                        response = await llm.agenerate([prompt])
                        response = response.generations[0][0].text
                    elif hasattr(llm, 'invoke'):
                        # Try message format first for ChatModels
                        try:
                            from langchain.schema import HumanMessage
                            if hasattr(llm, '_llm_type') and 'chat' in str(llm._llm_type).lower():
                                response = llm.invoke([HumanMessage(content=prompt)])
                            else:
                                response = llm.invoke(prompt)
                        except Exception:
                            # Fallback to direct string invoke
                            response = llm.invoke(prompt)
                    else:
                        # Synchronous fallback
                        response = llm.invoke(prompt)
                    break
                except Exception as retry_error:
                    self.logger.warning(f"LLM call attempt {attempt + 1} failed: {retry_error}")
                    if attempt == max_retries - 1:
                        raise retry_error
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
            
            # Extract and validate content from response
            if response is None:
                error_msg = "LLM returned None response"
                self.logger.error(error_msg)
                return self._create_fallback_response(process_type, error_msg)
            
            # Extract content from response
            out = response.content if hasattr(response, 'content') else str(response)
            
            # Validate output
            if not out or out.strip() == "":
                error_msg = "LLM returned empty response"
                # Enhanced debugging for empty responses
                self.logger.error(f"{error_msg} - Response object: {type(response)}")
                if hasattr(response, '__dict__'):
                    self.logger.error(f"Response attributes: {list(response.__dict__.keys())}")
                if hasattr(response, 'response_metadata'):
                    self.logger.error(f"Response metadata: {response.response_metadata}")
                
                # For entity extraction, try to create a more helpful fallback
                if (isinstance(process_type, LLMProcessType) and process_type == LLMProcessType.ENTITY_EXTRACTION) or \
                   (isinstance(process_type, str) and process_type == "entity_extraction"):
                    # Log prompt details for debugging
                    self.logger.error(f"Empty response for entity extraction. Prompt length: {len(prompt)} chars")
                    if len(prompt) > 15000:
                        self.logger.error("Prompt may be too long for model - consider chunking")
                    
                return self._create_fallback_response(process_type, error_msg)
            
            # For entity extraction, validate JSON structure more thoroughly
            if (isinstance(process_type, LLMProcessType) and process_type == LLMProcessType.ENTITY_EXTRACTION) or \
               (isinstance(process_type, str) and process_type == "entity_extraction"):
                try:
                    import json
                    parsed = json.loads(out)
                    
                    # Ensure it has expected structure
                    if not isinstance(parsed, dict):
                        self.logger.warning(f"Entity extraction response not a dict, wrapping: {type(parsed)}")
                        out = json.dumps({"entities": parsed if isinstance(parsed, list) else [parsed], "relationships": []})
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
                    
                    # Log successful entity extraction for debugging
                    entity_count = len(parsed.get("entities", []))
                    rel_count = len(parsed.get("relationships", []))
                    self.logger.info(f"Entity extraction validation complete: {entity_count} entities, {rel_count} relationships")
                    
                except json.JSONDecodeError as json_error:
                    self.logger.warning(f"Entity extraction response not valid JSON: {json_error}")
                    self.logger.warning(f"Response content: {out[:1000]}...")
                    # Try to extract JSON from the response
                    out = self._extract_or_create_json(out, process_type)
            
            if debug_llm:
                preview = out[:2000]
                self.logger.debug(f"LLM response preview (first 2000 chars): {preview}")
            else:
                self.logger.info(f"LLM call complete | chars={len(out)} corr_id={corr_id or '-'}")
            
            return out
                
        except Exception as e:
            error_msg = f"Error processing LLM request: {e}"
            self.logger.error(error_msg)
            return self._create_fallback_response(process_type, error_msg)

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

    def _extract_or_create_json(self, response_text: str, process_type: Union[LLMProcessType, str]) -> str:
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
                                            corr_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        try:
            if isinstance(process_type, str):
                process_type = LLMProcessType(process_type)
            cfg = await self._get_process_configuration(process_type, project_id, corr_id=corr_id)
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
