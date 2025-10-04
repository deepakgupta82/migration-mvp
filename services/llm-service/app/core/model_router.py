#!/usr/bin/env python3
"""
Model Router - Intelligent Model Selection
Smart routing logic for selecting optimal LLM model based on task requirements

This module provides:
- Task-based model selection
- Cost optimization logic
- Context-aware routing
- Failover model recommendations
"""

import logging
from typing import Dict, Optional, Any
from enum import Enum

logger = logging.getLogger("model_router")


class TaskComplexity(Enum):
    """Task complexity levels"""
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    VERY_COMPLEX = "very_complex"


class ModelRouter:
    """
    Intelligent model router for LLM selection
    
    Routing Strategy:
    1. GPT-4o: Best for images, diagrams, visual content
    2. Claude 3.5 Sonnet: Best for complex reasoning, structured extraction
    3. Gemini 2.5 Pro: Best for large context (2M tokens), cross-document analysis
    """
    
    # Model capabilities and characteristics
    MODEL_PROFILES = {
        "gpt-4o": {
            "provider": "openai",
            "strengths": ["vision", "diagrams", "images", "multimodal"],
            "max_context": 128_000,
            "cost_tier": "medium",  # $2.50/$10.00 per 1M tokens
            "best_for": ["diagram_understanding", "image_analysis", "visual_content"]
        },
        "claude-3-5-sonnet-20241022": {
            "provider": "anthropic",
            "strengths": ["reasoning", "structured_output", "json_adherence", "complex_logic"],
            "max_context": 200_000,
            "cost_tier": "medium",  # $3.00/$15.00 per 1M tokens
            "best_for": ["entity_extraction", "relationship_inference", "structured_data"]
        },
        "gemini-2.0-flash-exp": {
            "provider": "gemini",
            "strengths": ["large_context", "fast", "cost_effective", "batch_processing"],
            "max_context": 2_000_000,
            "cost_tier": "low",  # $0.075/$0.30 per 1M tokens
            "best_for": ["cross_document", "large_batches", "cost_optimization"]
        },
        "gpt-4o-mini": {
            "provider": "openai",
            "strengths": ["speed", "cost_effective", "simple_tasks"],
            "max_context": 128_000,
            "cost_tier": "low",  # $0.15/$0.60 per 1M tokens
            "best_for": ["simple_classification", "quick_tasks"]
        },
        "claude-3-haiku-20240307": {
            "provider": "anthropic",
            "strengths": ["speed", "cost_effective", "simple_tasks"],
            "max_context": 200_000,
            "cost_tier": "low",  # $0.25/$1.25 per 1M tokens
            "best_for": ["simple_extraction", "fast_processing"]
        }
    }
    
    # Task-to-model mapping
    TASK_PREFERENCES = {
        "entity_extraction": {
            "primary": "claude-3-5-sonnet-20241022",
            "secondary": "gpt-4o",
            "cost_optimized": "gemini-2.0-flash-exp"
        },
        "fact_extraction": {
            "primary": "claude-3-5-sonnet-20241022",
            "secondary": "gpt-4o",
            "cost_optimized": "gemini-2.0-flash-exp"
        },
        "document_analysis": {
            "primary": "claude-3-5-sonnet-20241022",
            "secondary": "gpt-4o",
            "cost_optimized": "gemini-2.0-flash-exp"
        },
        "domain_classification": {
            "primary": "gpt-4o-mini",
            "secondary": "claude-3-haiku-20240307",
            "cost_optimized": "gemini-2.0-flash-exp"
        },
        "schema_discovery": {
            "primary": "claude-3-5-sonnet-20241022",
            "secondary": "gpt-4o",
            "cost_optimized": "gemini-2.0-flash-exp"
        },
        "relationship_inference": {
            "primary": "claude-3-5-sonnet-20241022",
            "secondary": "gpt-4o",
            "cost_optimized": "gemini-2.0-flash-exp"
        },
        "entity_resolution": {
            "primary": "claude-3-5-sonnet-20241022",
            "secondary": "gemini-2.0-flash-exp",
            "cost_optimized": "gpt-4o-mini"
        },
        "diagram_understanding": {
            "primary": "gpt-4o",
            "secondary": "claude-3-5-sonnet-20241022",
            "cost_optimized": "gpt-4o"  # No cost alternative for vision
        },
        "table_extraction": {
            "primary": "claude-3-5-sonnet-20241022",
            "secondary": "gpt-4o",
            "cost_optimized": "gemini-2.0-flash-exp"
        },
        "conversation": {
            "primary": "gpt-4o",
            "secondary": "claude-3-5-sonnet-20241022",
            "cost_optimized": "gpt-4o-mini"
        }
    }
    
    def __init__(self):
        logger.info("Model Router initialized with multi-provider support")
    
    def select_model(
        self,
        task_type: str,
        context_size: int = 0,
        has_images: bool = False,
        has_diagrams: bool = False,
        complexity: TaskComplexity = TaskComplexity.MODERATE,
        prefer_cost_optimization: bool = False
    ) -> Dict[str, str]:
        """
        Select optimal model based on task requirements
        
        Args:
            task_type: Type of task (entity_extraction, etc.)
            context_size: Size of context in characters
            has_images: Whether content includes images
            has_diagrams: Whether content includes diagrams
            complexity: Task complexity level
            prefer_cost_optimization: Prefer cheaper models when possible
            
        Returns:
            Dict with model_name, provider, and reason
        """
        # Rule 1: If images/diagrams, use GPT-4o (best vision model)
        if has_images or has_diagrams:
            logger.info(
                f"Selected GPT-4o for visual content | "
                f"task={task_type} has_images={has_images} has_diagrams={has_diagrams}"
            )
            return {
                "model_name": "gpt-4o",
                "provider": "openai",
                "reason": "visual_content_requires_vision_model"
            }
        
        # Rule 2: If very large context (>200K tokens ~800K chars), use Gemini
        if context_size > 800_000:
            logger.info(
                f"Selected Gemini 2.0 Flash for large context | "
                f"task={task_type} context_size={context_size}"
            )
            return {
                "model_name": "gemini-2.0-flash-exp",
                "provider": "gemini",
                "reason": "large_context_requires_gemini_2m_window"
            }
        
        # Rule 3: Get task preferences
        task_prefs = self.TASK_PREFERENCES.get(task_type)
        if not task_prefs:
            # Default to Claude for unknown tasks
            logger.warning(
                f"Unknown task type '{task_type}', using default Claude model"
            )
            return {
                "model_name": "claude-3-5-sonnet-20241022",
                "provider": "anthropic",
                "reason": "default_for_unknown_task"
            }
        
        # Rule 4: If cost optimization preferred and task is simple/moderate
        if prefer_cost_optimization and complexity in [TaskComplexity.SIMPLE, TaskComplexity.MODERATE]:
            model_name = task_prefs["cost_optimized"]
            logger.info(
                f"Selected cost-optimized model | "
                f"task={task_type} model={model_name} complexity={complexity.value}"
            )
            return {
                "model_name": model_name,
                "provider": self.MODEL_PROFILES[model_name]["provider"],
                "reason": "cost_optimization_enabled"
            }
        
        # Rule 5: Use primary model for complex tasks
        if complexity in [TaskComplexity.COMPLEX, TaskComplexity.VERY_COMPLEX]:
            model_name = task_prefs["primary"]
            logger.info(
                f"Selected primary model for complex task | "
                f"task={task_type} model={model_name} complexity={complexity.value}"
            )
            return {
                "model_name": model_name,
                "provider": self.MODEL_PROFILES[model_name]["provider"],
                "reason": "complex_task_requires_best_model"
            }
        
        # Rule 6: Default to primary model for task
        model_name = task_prefs["primary"]
        logger.info(
            f"Selected primary model | "
            f"task={task_type} model={model_name}"
        )
        return {
            "model_name": model_name,
            "provider": self.MODEL_PROFILES[model_name]["provider"],
            "reason": "default_primary_for_task"
        }
    
    def get_failover_model(
        self,
        task_type: str,
        failed_model: str,
        context_size: int = 0
    ) -> Optional[Dict[str, str]]:
        """
        Get alternative model for failover
        
        Args:
            task_type: Type of task
            failed_model: Model that failed
            context_size: Context size
            
        Returns:
            Alternative model selection or None
        """
        task_prefs = self.TASK_PREFERENCES.get(task_type)
        if not task_prefs:
            return None
        
        # Get primary and secondary models
        primary = task_prefs["primary"]
        secondary = task_prefs["secondary"]
        
        # If primary failed, use secondary
        if failed_model == primary:
            logger.info(
                f"Failover from primary to secondary | "
                f"task={task_type} failed={failed_model} failover={secondary}"
            )
            return {
                "model_name": secondary,
                "provider": self.MODEL_PROFILES[secondary]["provider"],
                "reason": "failover_to_secondary"
            }
        
        # If secondary failed, try cost optimized
        if failed_model == secondary:
            cost_opt = task_prefs["cost_optimized"]
            if cost_opt != failed_model:
                logger.info(
                    f"Failover to cost-optimized model | "
                    f"task={task_type} failed={failed_model} failover={cost_opt}"
                )
                return {
                    "model_name": cost_opt,
                    "provider": self.MODEL_PROFILES[cost_opt]["provider"],
                    "reason": "failover_to_cost_optimized"
                }
        
        # No more failover options
        logger.warning(
            f"No failover options available | "
            f"task={task_type} failed={failed_model}"
        )
        return None
    
    def get_model_info(self, model_name: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a model
        
        Args:
            model_name: Model name
            
        Returns:
            Model profile dict or None
        """
        return self.MODEL_PROFILES.get(model_name)
    
    def list_available_models(self) -> list[str]:
        """
        List all available models
        
        Returns:
            List of model names
        """
        return list(self.MODEL_PROFILES.keys())
    
    def get_models_for_task(self, task_type: str) -> Dict[str, str]:
        """
        Get all recommended models for a task type
        
        Args:
            task_type: Task type
            
        Returns:
            Dict with primary, secondary, cost_optimized models
        """
        return self.TASK_PREFERENCES.get(task_type, {})
