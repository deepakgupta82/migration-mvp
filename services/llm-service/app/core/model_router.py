#!/usr/bin/env python3
"""
Model Router - Project LLM Configuration Integration
Fetches and manages LLM configuration from project settings

This module provides:
- Project-level LLM configuration fetching
- Process-specific LLM config support
- Integration with backend API
- Fallback strategies
"""

import logging
import httpx
import os
from typing import Dict, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("model_router")


@dataclass
class LLMConfig:
    """LLM Configuration"""
    provider: str
    model: str
    api_key: str
    temperature: float = 0.7
    max_tokens: int = 4000
    config_id: Optional[str] = None
    source: str = "project_default"  # project_default, process_specific, system_fallback


class TaskComplexity(Enum):
    """Task complexity levels"""
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    VERY_COMPLEX = "very_complex"


class ModelConfigFetcher:
class ModelConfigFetcher:
    """
    Fetches LLM configuration from project settings.
    Integrates with backend API for project-level and process-specific configs.
    
    Priority:
    1. Process-specific override (if process_type provided)
    2. Project default LLM config
    3. System fallback (if project has no config)
    """
    
    def __init__(self):
        # Backend service URL
        self.backend_url = os.getenv("BACKEND_SERVICE_URL", "http://localhost:8000")
        self.project_service_url = os.getenv("PROJECT_SERVICE_URL", "http://localhost:8002")
        self.service_token = os.getenv("SERVICE_AUTH_TOKEN", "service-backend-token")
        
        # System fallback config (when project has no config)
        self.system_fallback = LLMConfig(
            provider=os.getenv("DEFAULT_LLM_PROVIDER", "openai"),
            model=os.getenv("DEFAULT_LLM_MODEL", "gpt-4o-mini"),
            api_key=os.getenv("OPENAI_API_KEY", ""),
            temperature=0.7,
            max_tokens=4000,
            source="system_fallback"
        )
        
        logger.info(f"ModelConfigFetcher initialized | backend={self.backend_url}")
    
    async def get_project_llm_config(
        self,
        project_id: str,
        process_type: Optional[str] = None
    ) -> LLMConfig:
        """
        Fetch LLM configuration from project settings.
        
        Args:
            project_id: Project UUID
            process_type: Optional process type for specific override
                         (e.g., "entity_extraction", "schema_discovery")
        
        Returns:
            LLMConfig with provider, model, api_key, etc.
        """
        try:
            # Step 1: Try process-specific config first (if process_type provided)
            if process_type:
                process_config = await self._get_process_specific_config(
                    project_id, process_type
                )
                if process_config:
                    logger.info(
                        f"Using process-specific LLM config | "
                        f"project={project_id} process={process_type} "
                        f"model={process_config.model}"
                    )
                    return process_config
            
            # Step 2: Get project default LLM config
            project_config = await self._get_project_default_config(project_id)
            if project_config:
                logger.info(
                    f"Using project default LLM config | "
                    f"project={project_id} model={project_config.model}"
                )
                return project_config
            
            # Step 3: Fallback to system default
            logger.warning(
                f"No project LLM config found, using system fallback | "
                f"project={project_id} fallback_model={self.system_fallback.model}"
            )
            return self.system_fallback
            
        except Exception as e:
            logger.error(
                f"Error fetching project LLM config: {e} | "
                f"project={project_id}, using system fallback"
            )
            return self.system_fallback
    
    async def _get_process_specific_config(
        self,
        project_id: str,
        process_type: str
    ) -> Optional[LLMConfig]:
        """
        Get process-specific LLM configuration from backend.
        
        Endpoint: GET /api/llm-config/{project_id}/llm-process-configs
        Returns: {entity_extraction: {...}, crew_assessment: {...}, ...}
        """
        try:
            url = f"{self.backend_url}/api/llm-config/{project_id}/llm-process-configs"
            headers = {"Authorization": f"Bearer {self.service_token}"}
            
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url, headers=headers)
                
                if response.status_code == 200:
                    configs = response.json()
                    
                    # Get config for specific process type
                    process_config_data = configs.get(process_type)
                    if process_config_data:
                        return self._parse_config_response(
                            process_config_data,
                            source="process_specific"
                        )
                
                logger.debug(
                    f"No process-specific config found | "
                    f"project={project_id} process={process_type}"
                )
                return None
                
        except Exception as e:
            logger.warning(
                f"Error fetching process-specific config: {e} | "
                f"project={project_id} process={process_type}"
            )
            return None
    
    async def _get_project_default_config(
        self,
        project_id: str
    ) -> Optional[LLMConfig]:
        """
        Get project's default LLM configuration.
        
        Endpoint: GET /api/projects/{project_id}/llm-config
        Returns: {provider, model, api_key, temperature, max_tokens, config_id, source}
        """
        try:
            # Try project service first
            url = f"{self.project_service_url}/api/projects/{project_id}/llm-config"
            headers = {"Authorization": f"Bearer {self.service_token}"}
            
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url, headers=headers)
                
                if response.status_code == 200:
                    config_data = response.json()
                    return self._parse_config_response(
                        config_data,
                        source="project_default"
                    )
                
                logger.debug(
                    f"No project default config found | "
                    f"project={project_id} status={response.status_code}"
                )
                return None
                
        except Exception as e:
            logger.warning(
                f"Error fetching project default config: {e} | "
                f"project={project_id}"
            )
            return None
    
    def _parse_config_response(
        self,
        config_data: Dict[str, Any],
        source: str
    ) -> LLMConfig:
        """
        Parse LLM config response into LLMConfig object.
        
        Args:
            config_data: Config data from API
            source: Source of config (project_default, process_specific)
        
        Returns:
            LLMConfig instance
        """
        return LLMConfig(
            provider=config_data.get("provider", "openai"),
            model=config_data.get("model", "gpt-4o-mini"),
            api_key=config_data.get("api_key", ""),
            temperature=float(config_data.get("temperature", 0.7)),
            max_tokens=int(config_data.get("max_tokens", 4000)),
            config_id=config_data.get("config_id"),
            source=source
        )
    
    async def select_model(
        self,
        project_id: str,
        process_type: str,
        fallback_model: Optional[str] = None
    ) -> LLMConfig:
        """
        Get model configuration for specific process type.
        Uses project's configured model, not hardcoded routing.
        
        Args:
            project_id: Project UUID
            process_type: Process type (e.g., "entity_extraction", "schema_discovery")
            fallback_model: Optional fallback model name if project has no config
        
        Returns:
            LLMConfig with model selection
        """
        config = await self.get_project_llm_config(project_id, process_type)
        
        # If using system fallback and fallback_model provided, override
        if config.source == "system_fallback" and fallback_model:
            config.model = fallback_model
            logger.info(
                f"Overriding system fallback model | "
                f"project={project_id} fallback_model={fallback_model}"
            )
        
        return config


# Legacy compatibility: Keep ModelRouter as alias
class ModelRouter:
    """
    DEPRECATED: Use ModelConfigFetcher instead.
    This class is kept for backward compatibility only.
    """
    
    def __init__(self):
        logger.warning(
            "ModelRouter is deprecated. Use ModelConfigFetcher for project-based LLM config."
        )
        self.config_fetcher = ModelConfigFetcher()
    
    async def select_model(
        self,
        task_type: str,
        project_id: str,
        context_size: int = 0,
        has_images: bool = False,
        has_diagrams: bool = False,
        complexity: TaskComplexity = TaskComplexity.MODERATE,
        prefer_cost_optimization: bool = False
    ) -> Dict[str, str]:
        """
        DEPRECATED: Legacy method kept for backward compatibility.
        Now uses project's LLM configuration instead of hardcoded routing.
        
        Args:
            task_type: Type of task (entity_extraction, etc.)
            project_id: Project UUID (REQUIRED)
            context_size: Size of context (ignored in new implementation)
            has_images: Whether content includes images (ignored)
            has_diagrams: Whether content includes diagrams (ignored)
            complexity: Task complexity (ignored)
            prefer_cost_optimization: Prefer cheaper models (ignored)
        
        Returns:
            Dict with model_name, provider, and reason
        """
        logger.warning(
            f"Using deprecated ModelRouter.select_model() | "
            f"task={task_type} project={project_id}"
        )
        
        config = await self.config_fetcher.get_project_llm_config(
            project_id=project_id,
            process_type=task_type
        )
        
        return {
            "model_name": config.model,
            "provider": config.provider,
            "reason": f"project_config_source_{config.source}"
        }

