from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx


class GraphServiceClient:
    """Lightweight HTTP client for graph-service.

    Phase 1: Scaffolding only; no callers wired yet.
    Updated: Increased default timeout from 300s (5 min) to 2700s (45 min) to handle heavy 
             concurrent LLM processing workloads with 10-20 documents simultaneously.
             
    Timeout Configuration:
        - Default: 2700s (45 minutes)
        - Environment Override: GRAPH_CLIENT_TIMEOUT_SECONDS
        - Rationale: Heavy LLM-based entity extraction and relationship analysis for multiple
                    concurrent documents can take 20-40 mins. This timeout provides buffer
                    for worst-case scenarios with complex documents.
        - Recommendation: For light workloads (1-5 docs), consider setting to 900s (15 mins)
    """

    def __init__(self, base_url: Optional[str] = None, service_token: Optional[str] = None, timeout: float = 2700.0):
        self.base_url = base_url or os.getenv("GRAPH_SERVICE_URL", "http://localhost:8006")
        self.service_token = service_token or os.getenv("SERVICE_AUTH_TOKEN", "service-backend-token")
        # Allow timeout override from environment, default 2700s (45 minutes)
        # Increased for heavy concurrent LLM processing with 10-20 documents
        self.timeout = float(os.getenv("GRAPH_CLIENT_TIMEOUT_SECONDS", str(timeout)))

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
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.get(f"{self.base_url}/api/graphs/projects/{project_id}/types", headers=self._headers(corr_id))
            return r.json() if r.status_code == 200 else {"error": r.text, "code": r.status_code}

    async def upsert_type_registry(self, project_id: str, snapshot: Dict[str, Any], corr_id: Optional[str] = None) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.put(
                f"{self.base_url}/api/graphs/projects/{project_id}/types",
                headers=self._headers(corr_id),
                json=snapshot,
            )
            return r.json() if r.status_code in (200, 201) else {"error": r.text, "code": r.status_code}

    async def propose_entities(self, project_id: str, proposal: Dict[str, Any], corr_id: Optional[str] = None) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(
                f"{self.base_url}/api/graphs/projects/{project_id}/proposals",
                headers=self._headers(corr_id),
                json=proposal,
            )
            return r.json() if r.status_code in (200, 201, 202) else {"error": r.text, "code": r.status_code}

    async def validate_proposal(self, proposal_id: str, corr_id: Optional[str] = None) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(
                f"{self.base_url}/api/graphs/proposals/{proposal_id}/validate",
                headers=self._headers(corr_id),
            )
            return r.json() if r.status_code == 200 else {"error": r.text, "code": r.status_code}

    async def commit_proposal(self, proposal_id: str, corr_id: Optional[str] = None) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(
                f"{self.base_url}/api/graphs/proposals/{proposal_id}/commit",
                headers=self._headers(corr_id),
            )
            return r.json() if r.status_code == 200 else {"error": r.text, "code": r.status_code}

    # --- New: Type registration and batch commit ---
    async def register_entity_type(self, project_id: str, payload: Dict[str, Any], corr_id: Optional[str] = None) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(
                f"{self.base_url}/api/graphs/projects/{project_id}/types/entity",
                headers=self._headers(corr_id),
                json=payload,
            )
            ok = r.status_code in (200, 201)
            return r.json() if ok else {"error": r.text, "code": r.status_code}

    async def register_relationship_type(self, project_id: str, payload: Dict[str, Any], corr_id: Optional[str] = None) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(
                f"{self.base_url}/api/graphs/projects/{project_id}/types/relationship",
                headers=self._headers(corr_id),
                json=payload,
            )
            ok = r.status_code in (200, 201)
            return r.json() if ok else {"error": r.text, "code": r.status_code}

    async def commit_proposals_batch(self, project_id: str, payload: Dict[str, Any] | None = None, corr_id: Optional[str] = None) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(
                f"{self.base_url}/api/graphs/projects/{project_id}/commit-proposals",
                headers=self._headers(corr_id),
                json=payload or {},
            )
            ok = r.status_code in (200, 201)
            return r.json() if ok else {"error": r.text, "code": r.status_code}
