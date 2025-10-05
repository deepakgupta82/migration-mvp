"""
LLM Process Factory - Centralized LLM management for different processes
Supports process-specific LLM configuration with fallback strategies
"""

import logging
import json
import os
from typing import Optional, Dict, Any, Union
from langchain.schema.language_model import BaseLanguageModel
from enum import Enum
from .llm_utils import get_llm_class, LLMInitializationError, test_llm_connection

logger = logging.getLogger("platform.llm_factory")

class LLMProcessType(Enum):
    """Supported LLM process types"""
    ENTITY_EXTRACTION = "entity_extraction"
    FACT_EXTRACTION = "fact_extraction"
    DOCUMENT_ANALYSIS = "document_analysis"
    DOCUMENT_ASSESSMENT = "document_assessment"
    CREW_ASSESSMENT = "crew_assessment"
    CREW_DOCUMENTATION = "crew_documentation"
    RAG_SYNTHESIS = "rag_synthesis"
    HYBRID_SEARCH = "hybrid_search"
    
    # Phase 1 & 2: New process types for intelligent document processing
    SCHEMA_DISCOVERY = "schema_discovery"
    ADAPTIVE_EXTRACTION = "adaptive_extraction"
    RELATIONSHIP_INFERENCE = "relationship_inference"
    DOMAIN_CLASSIFICATION = "domain_classification"

class LLMProcessFactory:
    """
    Factory for creating process-specific LLM instances
    Supports OpenAI, Anthropic, Gemini, and Ollama providers
    """
    
    def __init__(self):
        self._llm_classes = {}
        self._provider_configs = {
            'openai': {'class': None, 'module': 'langchain_openai', 'name': 'ChatOpenAI'},
            'anthropic': {'class': None, 'module': 'langchain_anthropic', 'name': 'ChatAnthropic'},
            'gemini': {'class': None, 'module': 'langchain_google_genai', 'name': 'ChatGoogleGenerativeAI'},
            'ollama': {'class': None, 'module': 'langchain_community.llms', 'name': 'Ollama'}
        }

    def _get_llm_class(self, provider: str):
        """Lazy load LLM classes to improve startup time"""
        if provider not in self._llm_classes:
            config = self._provider_configs.get(provider)
            if not config:
                raise ValueError(f"Unsupported LLM provider: {provider}")
            
            try:
                module = __import__(config['module'], fromlist=[config['name']])
                self._llm_classes[provider] = getattr(module, config['name'])
                logger.debug(f"Loaded LLM class for provider: {provider}")
            except ImportError as e:
                raise ValueError(f"Required library for {provider} not installed: {str(e)}")
                
        return self._llm_classes[provider]

    def get_process_llm(self, 
                       project, 
                       process_type: Union[LLMProcessType, str], 
                       fallback_to_project_default: bool = True) -> Optional[BaseLanguageModel]:
        """
        Get LLM instance for specific process type
        
        Args:
            project: Project object with LLM configuration
            process_type: Type of process needing LLM
            fallback_to_project_default: Whether to fallback to project default LLM
            
        Returns:
            BaseLanguageModel instance or None if not configured
        """
        try:
            if isinstance(process_type, str):
                process_type = LLMProcessType(process_type)
            
            logger.info(f"Getting LLM for process: {process_type.value}")
            
            # Step 1: Try process-specific configuration
            process_config = self._get_process_config(project, process_type)
            if process_config:
                logger.info(f"Using process-specific LLM config for {process_type.value}")
                return self._create_llm_from_config(process_config)
            
            # Step 2: Fallback to project default if enabled
            if fallback_to_project_default:
                logger.info(f"Falling back to project default LLM for {process_type.value}")
                return self._get_project_default_llm(project)
            
            logger.warning(f"No LLM configuration found for process: {process_type.value}")
            return None
            
        except Exception as e:
            logger.error(f"Error creating process LLM: {str(e)}")
            raise

    def _get_process_config(self, project, process_type: LLMProcessType) -> Optional[Dict[str, Any]]:
        """Get process-specific LLM configuration from project"""
        try:
            # Check for process-specific configuration fields
            config_field = f"{process_type.value}_llm_config"
            
            if hasattr(project, config_field):
                config_json = getattr(project, config_field)
                if config_json:
                    return json.loads(config_json) if isinstance(config_json, str) else config_json
            
            # Fallback: check for nested configuration
            if hasattr(project, 'llm_process_configs'):
                configs = project.llm_process_configs
                if isinstance(configs, str):
                    configs = json.loads(configs)
                return configs.get(process_type.value)
            
            return None
            
        except (json.JSONDecodeError, AttributeError) as e:
            logger.warning(f"Error parsing process config for {process_type.value}: {e}")
            return None

    def _get_project_default_llm(self, project) -> Optional[BaseLanguageModel]:
        """Get project's default LLM configuration"""
        try:
            # Use existing project LLM logic
            from app.core.crew import get_project_llm
            return get_project_llm(project)
        except Exception as e:
            logger.error(f"Error getting project default LLM: {str(e)}")
            return None

    def _create_llm_from_config(self, config: Dict[str, Any]) -> BaseLanguageModel:
        """Create LLM instance from configuration"""
        provider = config.get('provider')
        model = config.get('model')
        
        if not provider or not model:
            raise ValueError("LLM configuration must include provider and model")
        
        # Get configuration parameters
        temperature = float(config.get('temperature', 0.1))
        max_tokens = int(config.get('max_tokens', 4000))
        api_key_id = config.get('api_key_id')
        
        # Get API key if needed
        api_key = None
        if api_key_id and provider != 'ollama':
            api_key = self._get_api_key(api_key_id)
            if not api_key:
                raise ValueError(f"API key not found for configuration: {api_key_id}")
        
        # Create LLM instance
        return self._instantiate_llm(provider, model, api_key, temperature, max_tokens)

    def _get_api_key(self, api_key_id: str) -> Optional[str]:
        """Get API key from configuration database"""
        try:
            import requests
            from app.core.project_service import ProjectServiceClient
            
            project_service = ProjectServiceClient()
            response = requests.get(
                f"{project_service.base_url}/llm-configurations/{api_key_id}",
                headers=project_service._get_auth_headers(),
                timeout=5
            )
            
            if response.status_code == 200:
                llm_config = response.json()
                return llm_config.get('api_key')
            else:
                logger.error(f"LLM configuration '{api_key_id}' not found")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching API key for {api_key_id}: {e}")
            return None

    def _instantiate_llm(self, provider: str, model: str, api_key: Optional[str], 
                        temperature: float, max_tokens: int) -> BaseLanguageModel:
        """Instantiate specific LLM based on provider"""
        llm_class = self._get_llm_class(provider)
        
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
            # Handle Gemini model name formatting
            clean_model = model
            if model.startswith('models/'):
                clean_model = model.replace('models/', '')
            if clean_model.startswith('gemini/'):
                clean_model = clean_model.replace('gemini/', '')
                
            return llm_class(
                model=clean_model,
                google_api_key=api_key,
                temperature=temperature,
                max_tokens=max_tokens,
                max_retries=3,  # Limit retries to 3 attempts
                timeout=30.0    # 30 second timeout
            )
        elif provider == 'ollama':
            return llm_class(
                model=model,
                temperature=temperature
            )
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    def get_recommended_models(self, process_type: Union[LLMProcessType, str]) -> Dict[str, list]:
        """Get recommended models for specific process types"""
        if isinstance(process_type, str):
            process_type = LLMProcessType(process_type)
            
        recommendations = {
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
            # New process types (Phase 1 & 2)
            LLMProcessType.SCHEMA_DISCOVERY: {
                'openai': ['gpt-4o', 'gpt-4-turbo'],
                'anthropic': ['claude-3-5-sonnet-20241022', 'claude-3-sonnet-20240229'],
                'gemini': ['gemini-1.5-pro', 'gemini-2.0-flash-exp'],
                'ollama': ['llama3.1:70b', 'mixtral:8x7b']
            },
            LLMProcessType.ADAPTIVE_EXTRACTION: {
                'openai': ['gpt-4o', 'gpt-4o-mini'],
                'anthropic': ['claude-3-5-sonnet-20241022', 'claude-3-haiku-20240307'],
                'gemini': ['gemini-1.5-pro', 'gemini-2.0-flash-exp'],
                'ollama': ['llama3.1:8b', 'mistral:7b']
            },
            LLMProcessType.RELATIONSHIP_INFERENCE: {
                'openai': ['gpt-4o', 'gpt-4-turbo'],
                'anthropic': ['claude-3-5-sonnet-20241022', 'claude-3-opus-20240229'],
                'gemini': ['gemini-1.5-pro', 'gemini-2.0-flash-exp'],
                'ollama': ['llama3.1:70b', 'mixtral:8x7b']
            },
            LLMProcessType.DOMAIN_CLASSIFICATION: {
                'openai': ['gpt-4o-mini', 'gpt-3.5-turbo'],
                'anthropic': ['claude-3-haiku-20240307'],
                'gemini': ['gemini-1.5-flash', 'gemini-2.0-flash-exp'],
                'ollama': ['llama3.1:8b', 'mistral:7b']
            }
        }
        
        return recommendations.get(process_type, {})

# Legacy compatibility functions
def get_llm_and_model():  # identical signature
    """Legacy compatibility function"""
    provider = os.environ.get("LLM_PROVIDER", "openai").lower()
    try:
        llm = _initialize_provider(provider)
        if llm and test_llm_connection(llm):
            logger.info(f"Successfully initialized LLM with provider: {provider}")
            return llm
        raise Exception(f"LLM connection test failed for provider: {provider}")
    except Exception as e:
        logger.error(f"Failed to initialize {provider}: {e}")
        raise LLMInitializationError(
            f"Failed to initialize LLM provider '{provider}': {str(e)}. Check configuration.")

def _initialize_provider(provider: str):
    """Legacy provider initialization"""
    from .crew import _initialize_provider as _orig  # delegate to original to avoid duplication for now
    return _orig(provider)

def get_project_llm(project: Any):
    """Legacy compatibility function"""
    from .crew import get_project_llm as _orig_project
    return _orig_project(project)

# Global factory instance
llm_factory = LLMProcessFactory()
