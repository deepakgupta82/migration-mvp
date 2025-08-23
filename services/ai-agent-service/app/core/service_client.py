"""
AI Agent ServiceClient (local)
Minimal HTTP client used by tools inside ai-agent-service to call other microservices.
"""

from __future__ import annotations

import os
import logging
from typing import Optional, Dict, Any

import httpx

logger = logging.getLogger("ai-agent-service.client")


class ServiceClient:
    """HTTP client for communicating with microservices (minimal subset for tools)."""

    def __init__(self) -> None:
        self.services: Dict[str, str] = {
            "project": os.getenv("PROJECT_SERVICE_URL", "http://localhost:8002"),
            "vector": os.getenv("VECTOR_SERVICE_URL", "http://localhost:8005"),
            "graph": os.getenv("GRAPH_SERVICE_URL", "http://localhost:8006"),
            "llm": os.getenv("LLM_SERVICE_URL", "http://localhost:8007"),
        }
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=5.0),
            follow_redirects=True,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=50),
        )

    async def close(self):
        try:
            await self._client.aclose()
        except Exception:
            pass

    def _headers(self) -> Dict[str, str]:
        headers = {"Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"}
        # Correlation ID passthrough if available in env (middleware usually sets context)
        corr = os.getenv("X_CORRELATION_ID")
        if corr:
            headers["X-Correlation-ID"] = corr
        return headers

    async def _req(
        self,
        method: str,
        service: str,
        path: str,
        *,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if service not in self.services:
            raise ValueError(f"Unknown service: {service}")
        url = f"{self.services[service]}{path}"
        headers = self._headers()
        if json is not None:
            headers["Content-Type"] = "application/json"
        logger.debug(f"ServiceClient: {method} {url}")
        resp = await self._client.request(method, url, json=json, params=params, headers=headers)
        ctype = (resp.headers.get("content-type") or "").lower()
        if ctype.startswith("application/json"):
            data = resp.json()
        else:
            data = {"status_code": resp.status_code, "content": resp.content, "content-type": ctype}
        if resp.status_code >= 400:
            logger.error(f"Service error {resp.status_code} at {url}: {data}")
            resp.raise_for_status()
        return data

    # Vector service
    async def vector_search(self, project_id: str, query: str, limit: int = 10) -> Dict[str, Any]:
        return await self._req(
            "POST", "vector", f"/api/vectors/projects/{project_id}/search", json={"query": query, "limit": limit}
        )

    async def hybrid_search(self, project_id: str, query: str, limit: int = 10) -> Dict[str, Any]:
        return await self._req(
            "POST", "vector", f"/api/vectors/projects/{project_id}/search/hybrid", json={"query": query, "limit": limit}
        )

    # Graph service
    async def search_graph_nodes(
        self, project_id: str, q: str, *, node_type: Optional[str] = None, limit: int = 20
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"q": q, "limit": limit}
        if node_type:
            params["node_type"] = node_type
        return await self._req("GET", "graph", f"/api/graphs/projects/{project_id}/nodes/search", params=params)

    async def search_graph_relationships(
        self, project_id: str, *, rel_type: Optional[str] = None, limit: int = 50
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"limit": limit}
        if rel_type:
            params["rel_type"] = rel_type
        return await self._req("GET", "graph", f"/api/graphs/projects/{project_id}/relationships/search", params=params)

    async def get_graph_neighborhood(
        self,
        project_id: str,
        node_id: str,
        *,
        depth: int = 1,
        direction: str = "both",
        rel_types: Optional[list[str]] = None,
        limit: int = 200,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"node_id": node_id, "depth": depth, "direction": direction, "limit": limit}
        if rel_types:
            params["rel_types"] = ",".join(rel_types)
        return await self._req("GET", "graph", f"/api/graphs/projects/{project_id}/neighborhood", params=params)


_client_singleton: Optional[ServiceClient] = None


async def get_service_client() -> ServiceClient:
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = ServiceClient()
    return _client_singleton


async def close_service_client():
    global _client_singleton
    if _client_singleton is not None:
        try:
            await _client_singleton.close()
        finally:
            _client_singleton = None
