#!/usr/bin/env python3
"""
Usage Logger Client for llm-service

Posts LLM call usage records to project-service /api/usage/llm-calls.
Best-effort, non-blocking semantics with short timeouts and error swallowing.
"""

from __future__ import annotations

import os
import asyncio
import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger("llm-service")


class UsageLogger:
    """Lightweight async client for posting LLM usage to project-service."""

    def __init__(self) -> None:
        self._project_service_url = os.getenv("PROJECT_SERVICE_URL", "http://localhost:8002")
        self._service_token = os.getenv("SERVICE_AUTH_TOKEN", "service-backend-token")
        # Bounds for payload sizes (defensive)
        self._prompt_cap = int(os.getenv("USAGE_PROMPT_MAX_CHARS", "12000"))
        self._response_cap = int(os.getenv("USAGE_RESPONSE_MAX_CHARS", "12000"))
        # Internal single-flight semaphore to avoid bursts piling up
        self._sem = asyncio.Semaphore(int(os.getenv("USAGE_LOGGER_MAX_IN_FLIGHT", "8")))

    def _headers(self, corr_id: Optional[str] = None) -> Dict[str, str]:
        h = {"Authorization": f"Bearer {self._service_token}"}
        if corr_id:
            h["X-Correlation-ID"] = corr_id
        return h

    def _truncate(self, s: Optional[str], cap: int) -> Optional[str]:
        if not s:
            return s
        if len(s) <= cap:
            return s
        return s[:cap]

    async def log_llm_call(
        self,
        *,
        project_id: Optional[str],
        correlation_id: Optional[str],
        provider: Optional[str],
        model: Optional[str],
        prompt: Optional[str],
        response: Optional[str],
        input_tokens: Optional[int],
        output_tokens: Optional[int],
        total_tokens: Optional[int],
        duration_ms: Optional[int],
        status: str,
        error_message: Optional[str] = None,
        task_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        content_policy_applied: bool = True,
        truncated: Optional[bool] = None,
        cost_usd_cents: Optional[int] = None,
    ) -> None:
        """Post a usage record. Never raises; logs warnings on failure."""
        url = f"{self._project_service_url}/api/usage/llm-calls"
        payload: Dict[str, Any] = {
            "project_id": project_id,
            "task_id": task_id,
            "correlation_id": correlation_id,
            "provider": provider or "unknown",
            "model": model or "unknown",
            "prompt": self._truncate(prompt, self._prompt_cap),
            "response": self._truncate(response, self._response_cap),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "cost_usd_cents": cost_usd_cents,
            "duration_ms": duration_ms,
            "status": status,
            "error_message": error_message,
            "metadata": metadata or {},
            "content_policy_applied": bool(content_policy_applied),
            "truncated": bool(truncated) if truncated is not None else False,
        }
        # Fire-and-forget with small timeout, swallow errors
        try:
            async with self._sem:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    await client.post(url, json=payload, headers=self._headers(correlation_id))
        except Exception as e:
            # Best-effort only; do not raise
            logger.debug(f"UsageLogger: failed to post usage (ignored): {e}")


# Singleton accessor
_LOGGER: Optional[UsageLogger] = None


def get_usage_logger() -> UsageLogger:
    global _LOGGER
    if _LOGGER is None:
        _LOGGER = UsageLogger()
    return _LOGGER
