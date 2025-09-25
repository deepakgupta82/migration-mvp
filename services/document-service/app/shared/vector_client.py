from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx


class VectorServiceClient:
    """Lightweight HTTP client for vector-service.

    Phase 1: Scaffolding only; no callers wired yet.
    """

    def __init__(self, base_url: Optional[str] = None, service_token: Optional[str] = None, timeout: float = 20.0):
        self.base_url = base_url or os.getenv("VECTOR_SERVICE_URL", "http://localhost:8005")
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

    async def index_status(self, project_id: str, corr_id: Optional[str] = None) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Align with vector-service router prefix "/api/vectors" and reuse stats as status
            r = await client.get(f"{self.base_url}/api/vectors/projects/{project_id}/stats", headers=self._headers(corr_id))
            return r.json() if r.status_code == 200 else {"error": r.text, "code": r.status_code}

    # --- Placeholders for index preparation and ingestion (PVC adjacent) ---
    async def prepare_index(self, project_id: str, corr_id: Optional[str] = None) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(
                f"{self.base_url}/api/vectors/projects/{project_id}/collection",
                headers=self._headers(corr_id),
            )
            return r.json() if r.status_code in (200, 201) else {"error": r.text, "code": r.status_code}

    async def upsert_embeddings(self, project_id: str, items: Dict[str, Any], corr_id: Optional[str] = None) -> Dict[str, Any]:
        # items is expected to include a key "documents": List[{id?, content, filename?, source?}]
        payload = {"documents": items.get("documents", [])}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(
                f"{self.base_url}/api/vectors/projects/{project_id}/documents/sync",
                headers=self._headers(corr_id),
                json=payload,
            )
            return r.json() if r.status_code in (200, 201) else {"error": r.text, "code": r.status_code}

    # --- New: Kind-aware (multi-embedding) helpers ---
    async def prepare_kind_collection(self, project_id: str, kind: str, corr_id: Optional[str] = None) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(
                f"{self.base_url}/api/vectors/projects/{project_id}/collections/{kind}",
                headers=self._headers(corr_id),
            )
            return r.json() if r.status_code in (200, 201) else {"error": r.text, "code": r.status_code}

    async def upsert_embeddings_kind(self, project_id: str, kind: str, items: Dict[str, Any], corr_id: Optional[str] = None) -> Dict[str, Any]:
        payload = {"documents": items.get("documents", [])}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(
                f"{self.base_url}/api/vectors/projects/{project_id}/collections/{kind}/documents/sync",
                headers=self._headers(corr_id),
                json=payload,
            )
            return r.json() if r.status_code in (200, 201) else {"error": r.text, "code": r.status_code}
