"""
LLM Service Client for Graph Service.
Provides centralized LLM request handling with multi-provider support.
"""
import json
import logging
from typing import Dict, Any, Optional, List, Literal
from datetime import datetime
import httpx

logger = logging.getLogger(__name__)


class LLMServiceClient:
    """Client for communicating with LLM service."""
    
    def __init__(
        self,
        service_registry_url: str = "http://localhost:8011",
        llm_service_url: Optional[str] = None,
        timeout: int = 300,
        max_retries: int = 3
    ):
        """
        Initialize LLM service client.
        
        Args:
            service_registry_url: URL of service registry
            llm_service_url: Direct URL of LLM service (if known)
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
        """
        self.service_registry_url = service_registry_url
        self.llm_service_url = llm_service_url
        self.timeout = timeout
        self.max_retries = max_retries
        self._cached_llm_url: Optional[str] = None
    
    async def _get_llm_service_url(self) -> str:
        """Get LLM service URL from registry or cache."""
        if self.llm_service_url:
            return self.llm_service_url
        
        if self._cached_llm_url:
            return self._cached_llm_url
        
        # Try to get from service registry
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.service_registry_url}/api/registry/services/llm",
                    timeout=10.0
                )
                if response.status_code == 200:
                    data = response.json()
                    self._cached_llm_url = data.get("url", "http://localhost:8007")
                    return self._cached_llm_url
        except Exception as e:
            logger.warning(f"Failed to get LLM service URL from registry: {e}")
        
        # Fallback to default
        self._cached_llm_url = "http://localhost:8007"
        return self._cached_llm_url
    
    async def process_request(
        self,
        process_type: str,
        prompt: str,
        project_id: Optional[str] = None,
        allow_global: bool = True,
        correlation_id: Optional[str] = None,
        timeout: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send a processing request to LLM service.
        
        Args:
            process_type: Type of processing (entity_extraction, document_assessment, etc.)
            prompt: The prompt to send to LLM
            project_id: Optional project ID for scoped configuration
            allow_global: Whether to allow global configuration fallback
            correlation_id: Optional correlation ID for tracking
            timeout: Optional timeout override (seconds)
            metadata: Optional metadata to include
        
        Returns:
            Dict with LLM response
        
        Raises:
            Exception: If request fails after retries
        """
        llm_url = await self._get_llm_service_url()
        endpoint = f"{llm_url}/api/llm/process"
        
        payload = {
            "process_type": process_type,
            "prompt": prompt,
            "project_id": project_id,
            "allow_global": allow_global
        }
        
        if metadata:
            payload["metadata"] = metadata
        
        headers = {}
        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id
        
        request_timeout = timeout or self.timeout
        last_error = None
        
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    f"LLM request attempt {attempt}/{self.max_retries}: "
                    f"process_type={process_type}, prompt_length={len(prompt)}"
                )
                
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        endpoint,
                        json=payload,
                        headers=headers,
                        timeout=request_timeout
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        logger.info(
                            f"LLM request succeeded on attempt {attempt}: "
                            f"process_type={process_type}"
                        )
                        return result
                    else:
                        error_msg = f"LLM service returned {response.status_code}: {response.text[:200]}"
                        logger.warning(error_msg)
                        last_error = error_msg
                        
                        # Don't retry on 4xx errors (client errors)
                        if 400 <= response.status_code < 500:
                            raise Exception(f"Client error from LLM service: {error_msg}")
            
            except httpx.TimeoutException as e:
                last_error = f"Timeout after {request_timeout}s: {str(e)}"
                logger.warning(f"Attempt {attempt} timeout: {last_error}")
            
            except Exception as e:
                last_error = str(e)
                logger.error(f"Attempt {attempt} failed: {last_error}")
                
                # Re-raise client errors immediately
                if "Client error" in last_error:
                    raise
        
        # All retries failed
        error_msg = f"LLM request failed after {self.max_retries} attempts. Last error: {last_error}"
        logger.error(error_msg)
        raise Exception(error_msg)
    
    async def extract_entities(
        self,
        content: str,
        document_type: str = "infrastructure_general",
        project_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        focus_entities: Optional[List[str]] = None,
        strategy: Optional[str] = None,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Extract entities using LLM service.
        
        Args:
            content: Content to extract entities from
            document_type: Type of document
            project_id: Project ID
            correlation_id: Correlation ID
            focus_entities: Entity types to focus on
            strategy: Extraction strategy
            timeout: Request timeout
        
        Returns:
            Dict with entities and relationships
        """
        from app.prompts.infrastructure_prompts import build_extraction_prompt
        
        prompt = build_extraction_prompt(
            document_type=document_type,
            content=content,
            focus_entities=focus_entities,
            strategy=strategy,
            attempt=1
        )
        
        metadata = {
            "document_type": document_type,
            "content_length": len(content),
            "focus_entities": focus_entities or [],
            "strategy": strategy or "adaptive"
        }
        
        result = await self.process_request(
            process_type="entity_extraction",
            prompt=prompt,
            project_id=project_id,
            correlation_id=correlation_id,
            timeout=timeout,
            metadata=metadata
        )
        
        return self._parse_extraction_result(result)
    
    async def analyze_document(
        self,
        content: str,
        project_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Analyze document structure and content type.
        
        Args:
            content: Content to analyze
            project_id: Project ID
            correlation_id: Correlation ID
            timeout: Request timeout
        
        Returns:
            Dict with document analysis
        """
        from app.prompts.infrastructure_prompts import build_analysis_prompt
        
        prompt = build_analysis_prompt(content)
        
        metadata = {
            "content_length": len(content),
            "operation": "document_analysis"
        }
        
        result = await self.process_request(
            process_type="document_analysis",
            prompt=prompt,
            project_id=project_id,
            correlation_id=correlation_id,
            timeout=timeout or 60,  # Analysis should be faster
            metadata=metadata
        )
        
        return self._parse_analysis_result(result)
    
    def _parse_extraction_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Parse LLM extraction result and normalize format."""
        try:
            # Get the output from result
            # Fix: LLM service returns 'response' field, not 'result.output'
            output = result.get("response", result.get("result", {}).get("output", ""))
            
            if isinstance(output, dict):
                # Already parsed
                return output
            
            if isinstance(output, str):
                # Try to parse JSON from string
                content = output.strip()
                
                # Remove markdown code blocks if present
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]
                
                parsed = json.loads(content.strip())
                
                # Normalize to expected format
                if isinstance(parsed, dict):
                    return {
                        "entities": parsed.get("entities", []),
                        "relationships": parsed.get("relationships", [])
                    }
                elif isinstance(parsed, list):
                    # If we got a list, assume it's entities
                    return {
                        "entities": parsed,
                        "relationships": []
                    }
            
            # Fallback
            return {"entities": [], "relationships": []}
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse extraction result: {e}")
            return {"entities": [], "relationships": []}
        except Exception as e:
            logger.error(f"Error processing extraction result: {e}")
            return {"entities": [], "relationships": []}
    
    def _parse_analysis_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Parse LLM analysis result."""
        try:
            # Fix: LLM service returns 'response' field, not 'result.output'
            output = result.get("response", result.get("result", {}).get("output", ""))
            
            if isinstance(output, dict):
                return output
            
            if isinstance(output, str):
                content = output.strip()
                
                # Remove markdown code blocks
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]
                
                parsed = json.loads(content.strip())
                return parsed
            
            # Fallback to default analysis
            return {
                "document_type": "unknown",
                "suggested_entities": [],
                "extraction_strategy": "mixed_strategy",
                "confidence": 0.5,
                "key_indicators": [],
                "complexity": "medium",
                "metadata": {}
            }
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse analysis result: {e}")
            return {
                "document_type": "unknown",
                "suggested_entities": [],
                "extraction_strategy": "mixed_strategy",
                "confidence": 0.0,
                "key_indicators": [],
                "complexity": "medium",
                "metadata": {"parse_error": str(e)}
            }
        except Exception as e:
            logger.error(f"Error processing analysis result: {e}")
            return {
                "document_type": "unknown",
                "suggested_entities": [],
                "extraction_strategy": "mixed_strategy",
                "confidence": 0.0,
                "key_indicators": [],
                "complexity": "medium",
                "metadata": {"error": str(e)}
            }


# Global client instance
_llm_client: Optional[LLMServiceClient] = None


def get_llm_client() -> LLMServiceClient:
    """Get or create global LLM service client."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMServiceClient()
    return _llm_client
