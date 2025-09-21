#!/usr/bin/env python3
"""
LLM-Based Content Summarization Engine
Implements intelligent multi-stage summarization with chunking and hierarchical processing
"""

import logging
import json
import asyncio
import hashlib
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import httpx
import os
from dataclasses import dataclass

logger = logging.getLogger("document-service.summarization-engine")

@dataclass
class SummarizationConfig:
    """Configuration for summarization engine"""
    max_chunk_size: int = 4000
    overlap_size: int = 200
    max_summary_length: int = 500
    hierarchical_levels: int = 3
    cache_ttl_seconds: int = 3600  # 1 hour
    max_concurrent_requests: int = 5
    retry_attempts: int = 3
    retry_delay: float = 1.0

class LLMSummarizationEngine:
    """
    Intelligent summarization engine with multi-stage processing:
    1. Document chunking with semantic boundaries
    2. Chunk-level summarization
    3. Hierarchical summarization (chunk summaries -> section summaries -> final summary)
    4. Quality validation and refinement
    """

    def __init__(self, config: Optional[SummarizationConfig] = None):
        self.config = config or SummarizationConfig()
        self.llm_service_url = os.getenv("LLM_SERVICE_URL", "http://localhost:8007")
        self.auth_token = os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')
        self.http_timeout = httpx.Timeout(60.0, connect=10.0)

        # Caching for summaries
        self._summary_cache = {}
        self._cache_cleanup_task = None

        # Start cache cleanup task
        asyncio.create_task(self._start_cache_cleanup())

    async def _start_cache_cleanup(self):
        """Start background cache cleanup task"""
        while True:
            await asyncio.sleep(300)  # Clean every 5 minutes
            await self._cleanup_expired_cache()

    async def _cleanup_expired_cache(self):
        """Remove expired cache entries"""
        current_time = datetime.now().timestamp()
        expired_keys = []

        for key, entry in self._summary_cache.items():
            if current_time - entry['timestamp'] > self.config.cache_ttl_seconds:
                expired_keys.append(key)

        for key in expired_keys:
            del self._summary_cache[key]

        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired summary cache entries")

    def _get_cache_key(self, content: str, summary_type: str = "general") -> str:
        """Generate cache key for content"""
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        return f"{summary_type}_{content_hash}"

    async def _get_cached_summary(self, cache_key: str) -> Optional[str]:
        """Get summary from cache if available and not expired"""
        if cache_key in self._summary_cache:
            entry = self._summary_cache[cache_key]
            if datetime.now().timestamp() - entry['timestamp'] < self.config.cache_ttl_seconds:
                logger.info(f"Using cached summary for key: {cache_key}")
                return entry['summary']
            else:
                # Remove expired entry
                del self._summary_cache[cache_key]
        return None

    def _cache_summary(self, cache_key: str, summary: str):
        """Cache summary with timestamp"""
        self._summary_cache[cache_key] = {
            'summary': summary,
            'timestamp': datetime.now().timestamp()
        }

    async def summarize_content(
        self,
        content: str,
        filename: str = "",
        summary_type: str = "comprehensive",
        project_id: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main summarization method with multi-stage processing

        Args:
            content: Text content to summarize
            filename: Original filename for context
            summary_type: Type of summary (comprehensive, executive, technical, etc.)
            project_id: Project ID for LLM configuration
            correlation_id: Request correlation ID

        Returns:
            Dict with summary and metadata including token usage
        """
        try:
            start_time = datetime.now()

            # Check cache first
            cache_key = self._get_cache_key(content, summary_type)
            cached_summary = await self._get_cached_summary(cache_key)
            if cached_summary:
                return {
                    "summary": cached_summary,
                    "cached": True,
                    "processing_time": 0.0,
                    "method": "cached",
                    "token_usage": {"cached": True, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
                    "timestamp": datetime.now().isoformat()
                }

            # Clean and validate content
            cleaned_content = self._clean_content(content)
            if not cleaned_content or len(cleaned_content.strip()) < 100:
                return self._create_fallback_summary(content, "insufficient_content")

            # Determine processing strategy based on content length
            content_length = len(cleaned_content)

            if content_length <= self.config.max_chunk_size:
                # Single-stage summarization for short content
                summary, token_usage = await self._single_stage_summarization(
                    cleaned_content, summary_type, project_id, correlation_id
                )
                method = "single_stage"
            else:
                # Multi-stage hierarchical summarization for long content
                summary, token_usage = await self._hierarchical_summarization(
                    cleaned_content, summary_type, project_id, correlation_id
                )
                method = "hierarchical"

            processing_time = (datetime.now() - start_time).total_seconds()

            # Cache the result
            self._cache_summary(cache_key, summary)

            return {
                "summary": summary,
                "cached": False,
                "processing_time": processing_time,
                "method": method,
                "content_length": content_length,
                "summary_length": len(summary),
                "token_usage": token_usage,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error in content summarization: {e}")
            return self._create_fallback_summary(content, f"summarization_error: {str(e)}")

    def _clean_content(self, content: str) -> str:
        """Clean and normalize content for summarization"""
        if not content:
            return ""

        # Remove excessive whitespace
        content = ' '.join(content.split())

        # Remove markdown formatting that might confuse LLM
        import re
        content = re.sub(r'\*\*([^*]+)\*\*', r'\1', content)  # Bold
        content = re.sub(r'\*([^*]+)\*', r'\1', content)      # Italic
        content = re.sub(r'`([^`]+)`', r'\1', content)        # Code
        content = re.sub(r'#+\s*', '', content)               # Headers
        content = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', content)  # Links

        return content.strip()

    async def _single_stage_summarization(
        self,
        content: str,
        summary_type: str,
        project_id: Optional[str],
        correlation_id: Optional[str]
    ) -> Tuple[str, Dict[str, Any]]:
        """Single-stage summarization for shorter content"""
        prompt = self._build_summarization_prompt(content, summary_type, "single")

        response, token_usage = await self._call_llm_service(
            prompt, project_id, correlation_id
        )

        summary = self._extract_summary_from_response(response)
        return summary, token_usage

    async def _hierarchical_summarization(
        self,
        content: str,
        summary_type: str,
        project_id: Optional[str],
        correlation_id: Optional[str]
    ) -> Tuple[str, Dict[str, Any]]:
        """Multi-stage hierarchical summarization for longer content"""
        total_token_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

        # Stage 1: Chunk the content
        chunks = self._chunk_content_semantically(content)

        # Stage 2: Summarize each chunk concurrently
        chunk_summaries, chunk_token_usage = await self._summarize_chunks_concurrent(
            chunks, summary_type, project_id, correlation_id
        )

        # Accumulate token usage
        for usage in chunk_token_usage:
            total_token_usage["input_tokens"] += usage.get("input_tokens", 0)
            total_token_usage["output_tokens"] += usage.get("output_tokens", 0)
            total_token_usage["total_tokens"] += usage.get("total_tokens", 0)

        # Stage 3: Combine chunk summaries into final summary
        if len(chunk_summaries) == 1:
            final_summary = chunk_summaries[0]
            combine_token_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        else:
            final_summary, combine_token_usage = await self._combine_chunk_summaries(
                chunk_summaries, summary_type, project_id, correlation_id
            )

        # Accumulate combine token usage
        total_token_usage["input_tokens"] += combine_token_usage.get("input_tokens", 0)
        total_token_usage["output_tokens"] += combine_token_usage.get("output_tokens", 0)
        total_token_usage["total_tokens"] += combine_token_usage.get("total_tokens", 0)

        # Stage 4: Quality validation and refinement
        final_summary, refine_token_usage = await self._validate_and_refine_summary(
            final_summary, content, summary_type, project_id, correlation_id
        )

        # Accumulate refine token usage
        total_token_usage["input_tokens"] += refine_token_usage.get("input_tokens", 0)
        total_token_usage["output_tokens"] += refine_token_usage.get("output_tokens", 0)
        total_token_usage["total_tokens"] += refine_token_usage.get("total_tokens", 0)

        return final_summary, total_token_usage

    def _chunk_content_semantically(self, content: str) -> List[str]:
        """Chunk content using semantic boundaries"""
        chunks = []
        remaining_content = content

        while remaining_content:
            # Try to find natural break points
            chunk = self._extract_semantic_chunk(remaining_content)
            chunks.append(chunk)

            # Remove processed content
            remaining_content = remaining_content[len(chunk):].lstrip()

            # Prevent infinite loops
            if len(chunks) > 100:  # Reasonable limit
                logger.warning("Too many chunks generated, truncating")
                break

        return chunks

    def _extract_semantic_chunk(self, content: str) -> str:
        """Extract a semantic chunk from content"""
        if len(content) <= self.config.max_chunk_size:
            return content

        # Look for paragraph breaks first
        paragraphs = content.split('\n\n')
        chunk_parts = []
        current_length = 0

        for para in paragraphs:
            para_length = len(para)
            if current_length + para_length > self.config.max_chunk_size:
                if chunk_parts:  # Don't break if we haven't added anything
                    break
                # Force add this paragraph if it's the first one
                chunk_parts.append(para)
                current_length += para_length
                break

            chunk_parts.append(para)
            current_length += para_length

            # Add overlap if we're approaching the limit
            if current_length >= self.config.max_chunk_size - self.config.overlap_size:
                break

        return '\n\n'.join(chunk_parts)

    async def _summarize_chunks_concurrent(
        self,
        chunks: List[str],
        summary_type: str,
        project_id: Optional[str],
        correlation_id: Optional[str]
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """Summarize multiple chunks concurrently"""
        semaphore = asyncio.Semaphore(self.config.max_concurrent_requests)

        async def summarize_chunk(chunk: str) -> Tuple[str, Dict[str, Any]]:
            async with semaphore:
                prompt = self._build_summarization_prompt(chunk, summary_type, "chunk")
                response, token_usage = await self._call_llm_service(prompt, project_id, correlation_id)
                summary = self._extract_summary_from_response(response)
                return summary, token_usage

        # Process chunks concurrently
        tasks = [summarize_chunk(chunk) for chunk in chunks]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions and collect results
        processed_summaries = []
        token_usages = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(f"Error summarizing chunk {i}: {result}")
                processed_summaries.append(f"Error summarizing chunk {i}")
                token_usages.append({"input_tokens": 0, "output_tokens": 0, "total_tokens": 0})
            else:
                summary, token_usage = result
                processed_summaries.append(summary)
                token_usages.append(token_usage)

        return processed_summaries, token_usages

    async def _combine_chunk_summaries(
        self,
        chunk_summaries: List[str],
        summary_type: str,
        project_id: Optional[str],
        correlation_id: Optional[str]
    ) -> Tuple[str, Dict[str, Any]]:
        """Combine multiple chunk summaries into a cohesive final summary"""
        combined_content = "\n\n".join(f"Section {i+1}: {summary}"
                                      for i, summary in enumerate(chunk_summaries))

        prompt = self._build_summarization_prompt(combined_content, summary_type, "combine")

        response, token_usage = await self._call_llm_service(prompt, project_id, correlation_id)
        summary = self._extract_summary_from_response(response)
        return summary, token_usage

    async def _validate_and_refine_summary(
        self,
        summary: str,
        original_content: str,
        summary_type: str,
        project_id: Optional[str],
        correlation_id: Optional[str]
    ) -> Tuple[str, Dict[str, Any]]:
        """Validate summary quality and refine if necessary"""
        total_token_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

        # Basic validation
        if len(summary) < 50:
            logger.warning("Summary too short, attempting refinement")
            refined_summary, refine_token_usage = await self._refine_summary(summary, original_content, summary_type, project_id, correlation_id)
            return refined_summary, refine_token_usage

        if len(summary) > self.config.max_summary_length * 1.5:
            logger.warning("Summary too long, attempting refinement")
            refined_summary, refine_token_usage = await self._refine_summary(summary, original_content, summary_type, project_id, correlation_id)
            return refined_summary, refine_token_usage

        return summary, total_token_usage

    async def _refine_summary(
        self,
        current_summary: str,
        original_content: str,
        summary_type: str,
        project_id: Optional[str],
        correlation_id: Optional[str]
    ) -> Tuple[str, Dict[str, Any]]:
        """Refine a summary to improve quality"""
        prompt = f"""Please refine the following summary to make it more concise and comprehensive:

Original Summary: {current_summary}

Refinement Guidelines:
- Keep the most important information
- Ensure coherence and flow
- Remove redundancy
- Aim for {self.config.max_summary_length} characters or less
- Maintain key facts and insights

Refined Summary:"""

        response, token_usage = await self._call_llm_service(prompt, project_id, correlation_id)
        refined = self._extract_summary_from_response(response)

        # Ensure it's within bounds
        if len(refined) > self.config.max_summary_length:
            refined = refined[:self.config.max_summary_length - 3] + "..."

        return refined, token_usage

    def _build_summarization_prompt(
        self,
        content: str,
        summary_type: str,
        stage: str
    ) -> str:
        """Build appropriate prompt based on summary type and processing stage"""
        base_prompts = {
            "comprehensive": "Provide a comprehensive summary covering all key points, main ideas, and important details.",
            "executive": "Provide an executive summary highlighting the most critical information for decision-makers.",
            "technical": "Provide a technical summary focusing on technical details, methodologies, and specifications.",
            "abstract": "Provide an abstract summarizing the main purpose, methods, results, and conclusions.",
            "key_points": "Extract and summarize the key points and main takeaways."
        }

        summary_instruction = base_prompts.get(summary_type, base_prompts["comprehensive"])

        if stage == "single":
            prompt = f"""{summary_instruction}

Content to summarize:
{content}

Summary:"""
        elif stage == "chunk":
            prompt = f"""Summarize this section of content, focusing on the most important information:

Content:
{content}

Section Summary:"""
        elif stage == "combine":
            prompt = f"""{summary_instruction}

Combine these section summaries into a cohesive overall summary:

{content}

Final Summary:"""

        return prompt

    async def _call_llm_service(
        self,
        prompt: str,
        project_id: Optional[str],
        correlation_id: Optional[str]
    ) -> Tuple[str, Dict[str, Any]]:
        """Call LLM service for summarization"""
        headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json"
        }

        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id

        payload = {
            "process_type": "content_summarization",
            "prompt": prompt,
            "project_id": project_id,
            "allow_global": True
        }

        for attempt in range(self.config.retry_attempts):
            try:
                async with httpx.AsyncClient(timeout=self.http_timeout) as client:
                    response = await client.post(
                        f"{self.llm_service_url}/api/llm/process",
                        json=payload,
                        headers=headers
                    )

                    if response.status_code == 200:
                        try:
                            result = response.json()
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse LLM service response as JSON: {e}")
                            raise Exception(f"Invalid JSON response from LLM service: {e}")

                        if result.get("success"):
                            # Extract token usage from response if available
                            token_usage = result.get("token_usage", {})
                            if not token_usage:
                                # Estimate token usage if not provided
                                input_tokens = len(prompt.split()) * 1.3  # Rough estimate
                                output_tokens = len(result["response"].split()) * 1.3
                                token_usage = {
                                    "input_tokens": int(input_tokens),
                                    "output_tokens": int(output_tokens),
                                    "total_tokens": int(input_tokens + output_tokens)
                                }

                            return result["response"], token_usage
                        else:
                            raise Exception(f"LLM service error: {result.get('error', 'Unknown error')}")
                    else:
                        raise Exception(f"LLM service HTTP {response.status_code}: {response.text}")

            except Exception as e:
                logger.warning(f"LLM service call attempt {attempt + 1} failed: {e}")
                if attempt < self.config.retry_attempts - 1:
                    await asyncio.sleep(self.config.retry_delay * (2 ** attempt))  # Exponential backoff
                else:
                    raise e

        raise Exception("All LLM service call attempts failed")

    def _extract_summary_from_response(self, response: str) -> str:
        """Extract clean summary from LLM response"""
        if not response:
            return ""

        # Clean up response
        response = response.strip()

        # Remove common prefixes
        prefixes_to_remove = [
            "Summary:", "Final Summary:", "Section Summary:",
            "Refined Summary:", "Response:", "Answer:"
        ]

        for prefix in prefixes_to_remove:
            if response.startswith(prefix):
                response = response[len(prefix):].strip()
                break

        return response

    def _create_fallback_summary(self, content: str, reason: str) -> Dict[str, Any]:
        """Create fallback summary when main processing fails"""
        # Extractive fallback
        if content and len(content) > 100:
            sentences = content.split('.')[:3]  # First 3 sentences
            fallback_summary = '. '.join(sentences) + '.'
            if len(fallback_summary) > self.config.max_summary_length:
                fallback_summary = fallback_summary[:self.config.max_summary_length - 3] + "..."
        else:
            fallback_summary = "Content too short for summarization."

        return {
            "summary": fallback_summary,
            "cached": False,
            "processing_time": 0.0,
            "method": f"fallback_{reason}",
            "timestamp": datetime.now().isoformat()
        }

    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        current_time = datetime.now().timestamp()
        valid_entries = 0
        expired_entries = 0

        for entry in self._summary_cache.values():
            if current_time - entry['timestamp'] < self.config.cache_ttl_seconds:
                valid_entries += 1
            else:
                expired_entries += 1

        return {
            "total_entries": len(self._summary_cache),
            "valid_entries": valid_entries,
            "expired_entries": expired_entries,
            "cache_ttl_seconds": self.config.cache_ttl_seconds
        }

    async def clear_cache(self):
        """Clear all cached summaries"""
        self._summary_cache.clear()
        logger.info("Summary cache cleared")