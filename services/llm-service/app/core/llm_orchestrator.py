#!/usr/bin/env python3
"""
Multi-Model LLM Orchestrator
Intelligent routing and orchestration for multiple LLM providers

This module provides:
- Smart model selection based on task type and requirements
- Cost optimization through intelligent routing
- Automatic failover and retry logic
- Performance monitoring and logging
- Support for Claude 4.5 Sonnet, GPT-4o, Gemini 2.5 Pro
"""

import logging
import time
from typing import Optional, Dict, Any, List, Tuple
from enum import Enum
import json

from .llm_processor import LLMProcessor, LLMProcessType
from .model_router import ModelConfigFetcher, LLMConfig
from .usage_client import get_usage_logger

logger = logging.getLogger("llm_orchestrator")


class TaskComplexity(Enum):
    """Task complexity levels for model selection"""
    SIMPLE = "simple"  # Simple classification, short responses
    MODERATE = "moderate"  # Entity extraction, structured data
    COMPLEX = "complex"  # Relationship inference, reasoning
    VERY_COMPLEX = "very_complex"  # Cross-document analysis, multi-hop reasoning


class OrchestratorConfig:
    """Configuration for LLM orchestrator behavior"""
    
    def __init__(
        self,
        max_retries: int = 3,
        timeout_seconds: int = 300,
        enable_failover: bool = True,
        prefer_cost_optimization: bool = True,
        log_performance_metrics: bool = True
    ):
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds
        self.enable_failover = enable_failover
        self.prefer_cost_optimization = prefer_cost_optimization
        self.log_performance_metrics = log_performance_metrics


class OrchestrationRequest:
    """Request object for LLM orchestration"""
    
    def __init__(
        self,
        task_type: str,  # LLMProcessType value
        content: str,
        project_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        context_size: Optional[int] = None,
        has_images: bool = False,
        has_diagrams: bool = False,
        complexity: TaskComplexity = TaskComplexity.MODERATE,
        preferred_model: Optional[str] = None,
        response_format: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ):
        self.task_type = task_type
        self.content = content
        self.project_id = project_id
        self.correlation_id = correlation_id or "unknown"
        self.context_size = context_size or len(content)
        self.has_images = has_images
        self.has_diagrams = has_diagrams
        self.complexity = complexity
        self.preferred_model = preferred_model
        self.response_format = response_format
        self.temperature = temperature
        self.max_tokens = max_tokens


class OrchestrationResult:
    """Result object from LLM orchestration"""
    
    def __init__(
        self,
        success: bool,
        result: Any,
        model_used: str,
        provider: str,
        tokens: Dict[str, int],
        cost_usd: float,
        duration_ms: int,
        attempts: int = 1,
        error: Optional[str] = None
    ):
        self.success = success
        self.result = result
        self.model_used = model_used
        self.provider = provider
        self.tokens = tokens
        self.cost_usd = cost_usd
        self.duration_ms = duration_ms
        self.attempts = attempts
        self.error = error
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary"""
        return {
            "success": self.success,
            "result": self.result,
            "model_used": self.model_used,
            "provider": self.provider,
            "tokens": self.tokens,
            "cost_usd": round(self.cost_usd, 6),
            "duration_ms": self.duration_ms,
            "attempts": self.attempts,
            "error": self.error
        }


class LLMOrchestrator:
    """
    Multi-model LLM orchestrator with intelligent routing and optimization
    
    Features:
    - Automatic model selection based on task requirements
    - Cost optimization through smart routing
    - Failover to alternative models on failure
    - Performance tracking and logging
    - Support for multiple providers (OpenAI, Anthropic, Google)
    """
    
    def __init__(
        self,
        config: Optional[OrchestratorConfig] = None
    ):
        self.config = config or OrchestratorConfig()
        self.llm_processor = LLMProcessor()
        self.model_config_fetcher = ModelConfigFetcher()
        self.usage_logger = get_usage_logger()
        
        logger.info(
            f"LLM Orchestrator initialized | "
            f"max_retries={self.config.max_retries} "
            f"failover={self.config.enable_failover} "
            f"cost_optimization={self.config.prefer_cost_optimization}"
        )
    
    async def orchestrate(
        self,
        request: OrchestrationRequest
    ) -> OrchestrationResult:
        """
        Orchestrate LLM call with intelligent routing and error handling
        
        Args:
            request: Orchestration request with task details
            
        Returns:
            OrchestrationResult with response and metrics
            
        Raises:
            ValueError: If project_id is missing from request
        """
        if not request.project_id:
            raise ValueError("project_id is required for LLM orchestration")
        
        start_time = time.time()
        attempts = 0
        last_error = None
        
        logger.info(
            f"Orchestration started | "
            f"corr_id={request.correlation_id} "
            f"project_id={request.project_id} "
            f"task_type={request.task_type} "
            f"context_size={request.context_size} "
            f"complexity={request.complexity.value}"
        )
        
        # Step 1: Select optimal model from project LLM config
        model_selection = await self._select_model(request)
        
        # Step 2: Attempt with primary model
        for attempt in range(1, self.config.max_retries + 1):
            attempts = attempt
            
            try:
                result = await self._execute_with_model(
                    request=request,
                    model_name=model_selection["model_name"],
                    provider=model_selection["provider"],
                    llm_config=model_selection.get("config")
                )
                
                # Success!
                duration_ms = int((time.time() - start_time) * 1000)
                
                orchestration_result = OrchestrationResult(
                    success=True,
                    result=result["response"],
                    model_used=model_selection["model_name"],
                    provider=model_selection["provider"],
                    tokens=result.get("tokens", {}),
                    cost_usd=result.get("cost_usd", 0.0),
                    duration_ms=duration_ms,
                    attempts=attempts
                )
                
                # Log performance metrics
                if self.config.log_performance_metrics:
                    self._log_performance_metrics(request, orchestration_result)
                
                logger.info(
                    f"Orchestration succeeded | "
                    f"corr_id={request.correlation_id} "
                    f"model={model_selection['model_name']} "
                    f"attempts={attempts} "
                    f"duration_ms={duration_ms}"
                )
                
                return orchestration_result
                
            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"Orchestration attempt failed | "
                    f"corr_id={request.correlation_id} "
                    f"attempt={attempt}/{self.config.max_retries} "
                    f"model={model_selection['model_name']} "
                    f"error={last_error}"
                )
                
                # Try failover if enabled and not last attempt
                if self.config.enable_failover and attempt < self.config.max_retries:
                    # On failover, re-fetch project config (same model, might work on retry)
                    logger.info(
                        f"Retrying with same model configuration | "
                        f"corr_id={request.correlation_id} "
                        f"attempt={attempt + 1}"
                    )
        
        # All attempts failed
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.error(
            f"Orchestration failed after {attempts} attempts | "
            f"corr_id={request.correlation_id} "
            f"final_error={last_error}"
        )
        
        return OrchestrationResult(
            success=False,
            result=None,
            model_used=model_selection["model_name"],
            provider=model_selection["provider"],
            tokens={},
            cost_usd=0.0,
            duration_ms=duration_ms,
            attempts=attempts,
            error=last_error
        )
    
    async def _select_model(
        self,
        request: OrchestrationRequest
    ) -> Dict[str, Any]:
        """
        Select optimal model based on project LLM configuration
        
        Args:
            request: Orchestration request
            
        Returns:
            Dict with model_name, provider, and LLMConfig
        """
        # If user explicitly prefers a model, use it but still fetch project config for API keys
        if request.preferred_model:
            try:
                # Fetch project config to get API keys and settings
                llm_config = await self.model_config_fetcher.get_project_llm_config(
                    project_id=request.project_id,
                    process_type=request.task_type
                )
                
                # Override model if user has preference
                llm_config.model = request.preferred_model
                llm_config.provider = self._get_provider_for_model(request.preferred_model)
                
                logger.info(
                    f"Using user-preferred model with project config | "
                    f"corr_id={request.correlation_id} "
                    f"model={request.preferred_model} "
                    f"config_source={llm_config.source}"
                )
                
                return {
                    "model_name": llm_config.model,
                    "provider": llm_config.provider,
                    "config": llm_config
                }
            except Exception as e:
                logger.warning(
                    f"Failed to fetch project config for preferred model, using system fallback | "
                    f"error={str(e)}"
                )
                provider = self._get_provider_for_model(request.preferred_model)
                return {"model_name": request.preferred_model, "provider": provider, "config": None}
        
        # Use project LLM configuration (process-specific or project default)
        try:
            llm_config = await self.model_config_fetcher.select_model(
                project_id=request.project_id,
                process_type=request.task_type,
                fallback_model=None
            )
            
            logger.info(
                f"Model selected from project config | "
                f"corr_id={request.correlation_id} "
                f"project_id={request.project_id} "
                f"model={llm_config.model} "
                f"provider={llm_config.provider} "
                f"source={llm_config.source}"
            )
            
            return {
                "model_name": llm_config.model,
                "provider": llm_config.provider,
                "config": llm_config
            }
        except Exception as e:
            logger.error(
                f"Failed to select model from project config | "
                f"project_id={request.project_id} "
                f"task_type={request.task_type} "
                f"error={str(e)}"
            )
            raise
    
    async def _execute_with_model(
        self,
        request: OrchestrationRequest,
        model_name: str,
        provider: str,
        llm_config: Optional[LLMConfig] = None
    ) -> Dict[str, Any]:
        """
        Execute LLM call with specific model
        
        Args:
            request: Orchestration request
            model_name: Model to use
            provider: Provider (openai, anthropic, gemini)
            llm_config: Optional LLMConfig from project settings
            
        Returns:
            Dict with response and metadata
        """
        # Build prompt based on task type
        prompt = self._build_prompt(request)
        
        # Build LLM config, prioritizing project config
        config_dict = {
            "provider": provider,
            "model_name": model_name,
            "temperature": request.temperature if request.temperature is not None else (llm_config.temperature if llm_config else 0.1),
            "max_tokens": request.max_tokens if request.max_tokens is not None else (llm_config.max_tokens if llm_config else 4000)
        }
        
        if request.response_format:
            config_dict["response_format"] = request.response_format
        
        # Add API key from project config if available
        if llm_config and llm_config.api_key:
            config_dict["api_key"] = llm_config.api_key
        
        # Call LLM processor
        llm = self.llm_processor.get_llm(
            process_type=request.task_type,
            project_id=request.project_id,
            correlation_id=request.correlation_id,
            config_override=config_dict
        )
        
        # Execute
        response = await llm.ainvoke(prompt)
        
        # Extract response content
        if hasattr(response, "content"):
            response_text = response.content
        else:
            response_text = str(response)
        
        # Parse JSON if needed
        result_data = response_text
        if request.response_format and request.response_format.get("type") == "json_object":
            try:
                result_data = json.loads(response_text)
            except json.JSONDecodeError:
                logger.warning(
                    f"Failed to parse JSON response | corr_id={request.correlation_id}"
                )
        
        # Extract token usage (if available)
        tokens = {}
        cost_usd = 0.0
        
        if hasattr(response, "response_metadata"):
            usage = response.response_metadata.get("usage", {})
            tokens = {
                "prompt": usage.get("prompt_tokens", 0),
                "completion": usage.get("completion_tokens", 0),
                "total": usage.get("total_tokens", 0)
            }
            
            # Calculate cost based on provider and model
            cost_usd = self._calculate_cost(
                provider=provider,
                model_name=model_name,
                tokens=tokens
            )
        
        return {
            "response": result_data,
            "tokens": tokens,
            "cost_usd": cost_usd
        }
    
    def _build_prompt(self, request: OrchestrationRequest) -> str:
        """
        Build prompt based on task type and content
        
        Args:
            request: Orchestration request
            
        Returns:
            Formatted prompt string
        """
        # For now, return content as-is
        # In Phase 1.3, we'll integrate AdaptivePromptBuilder
        return request.content
    
    def _calculate_cost(
        self,
        provider: str,
        model_name: str,
        tokens: Dict[str, int]
    ) -> float:
        """
        Calculate cost in USD for the LLM call
        
        Args:
            provider: Provider name
            model_name: Model name
            tokens: Token usage dict
            
        Returns:
            Cost in USD
        """
        # Pricing as of October 2024 (per 1M tokens)
        PRICING = {
            "openai": {
                "gpt-4o": {"input": 2.50, "output": 10.00},
                "gpt-4o-mini": {"input": 0.15, "output": 0.60},
                "gpt-4-turbo": {"input": 10.00, "output": 30.00}
            },
            "anthropic": {
                "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
                "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
                "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25}
            },
            "gemini": {
                "gemini-2.0-flash-exp": {"input": 0.075, "output": 0.30},
                "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
                "gemini-1.5-flash": {"input": 0.075, "output": 0.30}
            }
        }
        
        pricing = PRICING.get(provider, {}).get(model_name)
        if not pricing:
            logger.warning(
                f"No pricing data for {provider}/{model_name}, using default"
            )
            pricing = {"input": 1.0, "output": 3.0}
        
        prompt_tokens = tokens.get("prompt", 0)
        completion_tokens = tokens.get("completion", 0)
        
        cost = (
            (prompt_tokens / 1_000_000) * pricing["input"] +
            (completion_tokens / 1_000_000) * pricing["output"]
        )
        
        return cost
    
    def _get_provider_for_model(self, model_name: str) -> str:
        """
        Get provider name for a given model
        
        Args:
            model_name: Model name
            
        Returns:
            Provider name (openai, anthropic, gemini)
        """
        if "gpt" in model_name.lower():
            return "openai"
        elif "claude" in model_name.lower():
            return "anthropic"
        elif "gemini" in model_name.lower():
            return "gemini"
        else:
            return "openai"  # Default
    
    def _log_performance_metrics(
        self,
        request: OrchestrationRequest,
        result: OrchestrationResult
    ):
        """
        Log performance metrics for monitoring and optimization
        
        Args:
            request: Original request
            result: Orchestration result
        """
        logger.info(
            f"Performance metrics | "
            f"corr_id={request.correlation_id} "
            f"task_type={request.task_type} "
            f"model={result.model_used} "
            f"provider={result.provider} "
            f"duration_ms={result.duration_ms} "
            f"tokens={result.tokens.get('total', 0)} "
            f"cost_usd={result.cost_usd:.6f} "
            f"attempts={result.attempts}"
        )
