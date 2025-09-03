"""
Service Discovery Module
Handles dynamic service URL resolution using the service registry
"""

import asyncio
import logging
import os
from typing import Dict, Optional, Any
from functools import lru_cache
import httpx
import time

logger = logging.getLogger(__name__)

class ServiceDiscovery:
    """Service discovery client for the service registry"""

    def __init__(self):
        self.registry_url = os.getenv("SERVICE_REGISTRY_URL", "http://localhost:8011")
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl = int(os.getenv("SERVICE_CACHE_TTL", "300"))  # 5 minutes default
        self._last_cache_update = 0

    async def _fetch_services_from_registry(self) -> Dict[str, Dict[str, Any]]:
        """Fetch all services from the service registry"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.registry_url}/services")
                if response.status_code == 200:
                    data = response.json()
                    return data.get("services", {})
                else:
                    logger.warning(f"Failed to fetch services from registry: {response.status_code}")
                    return {}
        except Exception as e:
            logger.error(f"Error fetching services from registry: {e}")
            return {}

    async def _get_service_info(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Get service information from registry"""
        # Check cache first
        current_time = time.time()
        if current_time - self._last_cache_update > self.cache_ttl:
            # Cache expired, refresh
            self.cache = await self._fetch_services_from_registry()
            self._last_cache_update = current_time

        return self.cache.get(service_name)

    async def get_service_url(self, service_name: str) -> Optional[str]:
        """Get the full URL for a service"""
        service_info = await self._get_service_info(service_name)
        if service_info and service_info.get("status") == "healthy":
            host = service_info.get("host", "localhost")
            port = service_info.get("port")
            return f"http://{host}:{port}"
        return None

    async def get_service_endpoint(self, service_name: str, endpoint: str = "") -> Optional[str]:
        """Get the full URL for a service endpoint"""
        base_url = await self.get_service_url(service_name)
        if base_url:
            return f"{base_url}{endpoint}"
        return None

    async def is_service_healthy(self, service_name: str) -> bool:
        """Check if a service is healthy"""
        service_info = await self._get_service_info(service_name)
        return service_info is not None and service_info.get("status") == "healthy"

    async def get_all_services(self) -> Dict[str, Dict[str, Any]]:
        """Get all registered services"""
        current_time = time.time()
        if current_time - self._last_cache_update > self.cache_ttl:
            self.cache = await self._fetch_services_from_registry()
            self._last_cache_update = current_time
        return self.cache

# Global service discovery instance
service_discovery = ServiceDiscovery()

# Convenience functions
async def get_storage_service_url() -> str:
    """Get storage service URL"""
    url = await service_discovery.get_service_url("storage-service")
    return url or "http://localhost:8010"  # fallback

async def get_project_service_url() -> str:
    """Get project service URL"""
    url = await service_discovery.get_service_url("project-service")
    return url or "http://localhost:8002"  # fallback

async def get_vector_service_url() -> str:
    """Get vector service URL"""
    url = await service_discovery.get_service_url("vector-service")
    return url or "http://localhost:8005"  # fallback

async def get_graph_service_url() -> str:
    """Get graph service URL"""
    url = await service_discovery.get_service_url("graph-service")
    return url or "http://localhost:8006"  # fallback

async def get_analytics_service_url() -> str:
    """Get analytics service URL"""
    url = await service_discovery.get_service_url("analytics-service")
    return url or "http://localhost:8014"  # fallback