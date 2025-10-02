#!/usr/bin/env python3
"""
Shared Usage Logger Client

Posts usage records to project-service /api/usage endpoints.
Supports:
- log_llm_call
- log_agent_run (create records with status running/completed/failed)
- log_agent_event (step-level events tied to an agent run)

Design goals:
- Lightweight, async, short timeouts
- Best-effort: swallow errors and never block main flows
- Correlation ID is propagated via X-Correlation-ID
"""

from __future__ import annotations

import os
import asyncio
import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger("usage-client")


class UsageClient:
    def __init__(self) -> None:
        self._project_service_url = os.getenv("PROJECT_SERVICE_URL", "http://localhost:8002")
        self._service_token = os.getenv("SERVICE_AUTH_TOKEN", "service-backend-token")
        self._timeout = float(os.getenv("USAGE_HTTP_TIMEOUT_SECONDS", "3.0"))
        # Bounds for payload sizes
        self._prompt_cap = int(os.getenv("USAGE_PROMPT_MAX_CHARS", "12000"))
        self._response_cap = int(os.getenv("USAGE_RESPONSE_MAX_CHARS", "12000"))
        self._sem = asyncio.Semaphore(int(os.getenv("USAGE_LOGGER_MAX_IN_FLIGHT", "8")))

    def _headers(self, corr_id: Optional[str] = None) -> Dict[str, str]:
        h = {"Authorization": f"Bearer {self._service_token}"}
        if corr_id:
            h["X-Correlation-ID"] = corr_id
        return h

    def _truncate(self, s: Optional[str], cap: int) -> Optional[str]:
        if not s:
            return s
        return s if len(s) <= cap else s[:cap]

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
    ) -> Optional[Dict[str, Any]]:
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
        try:
            async with self._sem:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.post(url, json=payload, headers=self._headers(correlation_id))
                    if resp.status_code == 200:
                        return resp.json()
        except Exception as e:
            logger.debug(f"UsageClient.llm: failed to post usage (ignored): {e}")
        return None

    async def log_agent_run(
        self,
        *,
        project_id: Optional[str],
        correlation_id: Optional[str],
        agent_type: Optional[str],
        task_name: Optional[str],
        status: str = "running",
        total_input_tokens: Optional[int] = None,
        total_output_tokens: Optional[int] = None,
        total_cost_usd_cents: Optional[int] = None,
        duration_ms: Optional[int] = None,
        started_at: Optional[str] = None,
        completed_at: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        url = f"{self._project_service_url}/api/usage/agent-runs"
        payload: Dict[str, Any] = {
            "project_id": project_id,
            "correlation_id": correlation_id,
            "agent_type": agent_type,
            "task_name": task_name,
            "status": status,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_cost_usd_cents": total_cost_usd_cents,
            "duration_ms": duration_ms,
            "started_at": started_at,
            "completed_at": completed_at,
            "metadata": metadata or {},
        }
        try:
            async with self._sem:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.post(url, json=payload, headers=self._headers(correlation_id))
                    if resp.status_code == 200:
                        return resp.json()
        except Exception as e:
            logger.debug(f"UsageClient.agent-run: failed to post (ignored): {e}")
        return None

    async def log_agent_event(
        self,
        *,
        run_id: str,
        project_id: Optional[str],
        correlation_id: Optional[str],
        event_type: str,
        role: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        content: Optional[str] = None,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
        cost_usd_cents: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        url = f"{self._project_service_url}/api/usage/agent-events"
        payload: Dict[str, Any] = {
            "run_id": run_id,
            "project_id": project_id,
            "correlation_id": correlation_id,
            "event_type": event_type,
            "role": role,
            "provider": provider,
            "model": model,
            "content": content,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "cost_usd_cents": cost_usd_cents,
            "metadata": metadata or {},
        }
        try:
            async with self._sem:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.post(url, json=payload, headers=self._headers(correlation_id))
                    if resp.status_code == 200:
                        return resp.json()
        except Exception as e:
            logger.debug(f"UsageClient.agent-event: failed to post (ignored): {e}")
        return None


# Singleton accessor
_USAGE_CLIENT: Optional[UsageClient] = None


def get_usage_client() -> UsageClient:
    global _USAGE_CLIENT
    if _USAGE_CLIENT is None:
        _USAGE_CLIENT = UsageClient()
    return _USAGE_CLIENT
