from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx


class ServiceRegistryClient:
    """Minimal client to query service-registry for service endpoints.

    Phase 1 scaffolding; optional use in later phases.
    """

    def __init__(self, base_url: Optional[str] = None, service_token: Optional[str] = None, timeout: float = 10.0):
        self.base_url = base_url or os.getenv("SERVICE_REGISTRY_URL", "http://localhost:8011")
        self.service_token = service_token or os.getenv("SERVICE_AUTH_TOKEN", "service-backend-token")
        self.timeout = timeout

    def _headers(self, corr_id: Optional[str]) -> Dict[str, str]:
        h = {"Authorization": f"Bearer {self.service_token}"}
        if corr_id:
            h["X-Correlation-ID"] = corr_id
        return h

    async def services(self, corr_id: Optional[str] = None) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.get(f"{self.base_url}/services", headers=self._headers(corr_id))
            return r.json() if r.status_code == 200 else {"error": r.text, "code": r.status_code}
