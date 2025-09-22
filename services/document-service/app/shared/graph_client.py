from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx


class GraphServiceClient:
    """Lightweight HTTP client for graph-service.

    Phase 1: Scaffolding only; no callers wired yet.
    """

    def __init__(self, base_url: Optional[str] = None, service_token: Optional[str] = None, timeout: float = 20.0):
        self.base_url = base_url or os.getenv("GRAPH_SERVICE_URL", "http://localhost:8006")
        self.service_token = service_token or os.getenv("SERVICE_AUTH_TOKEN", "service-backend-token")
        self.timeout = timeout

    def _headers(self, corr_id: Optional[str]) -> Dict[str, str]:
        h = {"Authorization": f"Bearer {self.service_token}"}
        if corr_id:
            h["X-Correlation-ID"] = corr_id
        return h

    async def health(self) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.get(f"{self.base_url}/health")
            return r.json() if r.status_code == 200 else {"status": "unavailable", "code": r.status_code}

    async def get_stats(self, project_id: str, corr_id: Optional[str] = None) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.get(f"{self.base_url}/api/graphs/projects/{project_id}/stats", headers=self._headers(corr_id))
            return r.json() if r.status_code == 200 else {"error": r.text, "code": r.status_code}

    # --- Placeholders for Type Registry and Proposals (PVC) ---
    async def get_type_registry(self, project_id: str, corr_id: Optional[str] = None) -> Dict[str, Any]:
        return {"error": "not implemented", "code": 501}

    async def upsert_type_registry(self, project_id: str, snapshot: Dict[str, Any], corr_id: Optional[str] = None) -> Dict[str, Any]:
        return {"error": "not implemented", "code": 501}

    async def propose_entities(self, project_id: str, proposal: Dict[str, Any], corr_id: Optional[str] = None) -> Dict[str, Any]:
        return {"error": "not implemented", "code": 501}

    async def validate_proposal(self, proposal_id: str, corr_id: Optional[str] = None) -> Dict[str, Any]:
        return {"error": "not implemented", "code": 501}

    async def commit_proposal(self, proposal_id: str, corr_id: Optional[str] = None) -> Dict[str, Any]:
        return {"error": "not implemented", "code": 501}
