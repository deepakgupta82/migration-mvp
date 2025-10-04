#!/usr/bin/env python3
"""
LLM Service Client
Client-side utilities for interacting with LLM service

This module provides:
- Adaptive prompt building (client-side replica)
- LLM service API client
- Helper functions for common LLM tasks
"""

import logging
import httpx
import json
import os
from typing import Dict, List, Optional, Any

logger = logging.getLogger("llm_service_client")


class AdaptivePromptBuilder:
    """
    Client-side adaptive prompt builder
    Mirrors the prompts from LLM service for consistency
    """
    
    def build_domain_classification_prompt(
        self,
        content: str,
        structure_type: Optional[str] = None
    ) -> str:
        """Build domain classification prompt"""
        prompt = f"""Classify the domain and content type of this document.

**Document Content** (first 2000 chars):
{content[:2000]}

**Structure Type**: {structure_type or "unknown"}

**Instructions**:
1. Identify the PRIMARY domain (infrastructure, organizational, financial, legal, process, hr, technical, other)
2. Identify SECONDARY domains if applicable
3. Determine structure type (tabular, narrative, mixed, diagram, list)
4. Estimate entity density (low, medium, high)
5. Recommend extraction strategy

**Output Format**: JSON
{{
  "primary_domain": "domain_name",
  "secondary_domains": ["domain2", "domain3"],
  "confidence": 0.95,
  "structure_type": "tabular|narrative|mixed|diagram|list",
  "entity_density": "low|medium|high",
  "estimated_entity_count": 100,
  "recommended_strategy": "spreadsheet_extraction|narrative_extraction|mixed"
}}

**Examples**:
- Server inventory Excel → infrastructure, tabular, high density
- Org chart document → organizational, mixed, medium density
- Process flowchart → process, diagram, low density
"""
        return prompt
    
    def build_entity_extraction_prompt(
        self,
        content: str,
        domain: str = "general",
        discovered_schema: Optional[Dict] = None
    ) -> str:
        """Build entity extraction prompt (placeholder for future use)"""
        # For now, return basic prompt
        # In Phase 2, this will use full domain-specific templates
        schema_info = ""
        if discovered_schema:
            schema_info = f"\n**Schema**: {json.dumps(discovered_schema, indent=2)}\n"
        
        return f"""Extract entities from this {domain} document.

**Content**:
{content}

{schema_info}

**Instructions**:
1. Identify all significant entities
2. Extract attributes for each entity
3. Preserve exact values (no modification)
4. Include confidence scores

**Output Format**: JSON array of entities
"""


class LLMServiceClient:
    """
    Client for calling LLM service endpoints
    """
    
    def __init__(self):
        self.llm_service_url = os.getenv("LLM_SERVICE_URL", "http://localhost:8007")
        self.service_token = os.getenv("SERVICE_AUTH_TOKEN", "service-backend-token")
        logger.info(f"LLM Service Client initialized | url={self.llm_service_url}")
    
    async def orchestrate(
        self,
        task_type: str,
        content: str,
        project_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        complexity: str = "moderate",
        response_format: Optional[Dict] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Call LLM service orchestrate endpoint
        
        Args:
            task_type: Type of task (entity_extraction, etc.)
            content: Content to process
            project_id: Project ID
            correlation_id: Correlation ID
            complexity: Task complexity
            response_format: Expected response format
            temperature: Temperature override
            **kwargs: Additional parameters
            
        Returns:
            Orchestration result dict
        """
        url = f"{self.llm_service_url}/orchestrate"
        
        headers = {
            "Authorization": f"Bearer {self.service_token}",
            "Content-Type": "application/json"
        }
        
        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id
        
        payload = {
            "task_type": task_type,
            "content": content,
            "project_id": project_id,
            "complexity": complexity,
            **kwargs
        }
        
        if response_format:
            payload["response_format"] = response_format
        
        if temperature is not None:
            payload["temperature"] = temperature
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            
            if not result.get("success"):
                raise Exception(f"LLM orchestration failed: {result.get('error')}")
            
            return result
    
    async def classify_domain(
        self,
        content: str,
        project_id: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Classify document domain
        
        Args:
            content: Document content
            project_id: Project ID
            correlation_id: Correlation ID
            
        Returns:
            Classification result
        """
        # Build prompt
        prompt_builder = AdaptivePromptBuilder()
        prompt = prompt_builder.build_domain_classification_prompt(content)
        
        # Call orchestrator
        result = await self.orchestrate(
            task_type="domain_classification",
            content=prompt,
            project_id=project_id,
            correlation_id=correlation_id,
            complexity="simple",
            response_format={"type": "json_object"},
            temperature=0.1
        )
        
        # Parse result
        llm_output = result.get("result")
        if isinstance(llm_output, str):
            llm_output = json.loads(llm_output)
        
        return llm_output
