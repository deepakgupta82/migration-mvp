#!/usr/bin/env python3
"""
Shared Service Client for Microservices
HTTP client for service-to-service communication with standardized patterns
"""

import os
import logging
import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger("service-client")


class ServiceClient:
    """HTTP client for communicating with microservices"""

    def __init__(self):
        # Service endpoints configuration - can be extended via service discovery
        self.services = {
            "project": os.getenv("PROJECT_SERVICE_URL", "http://localhost:8002"),
            "reporting": os.getenv("REPORTING_SERVICE_URL", "http://localhost:8001"),
            "document": os.getenv("DOCUMENT_SERVICE_URL", "http://localhost:8003"),
            "vector": os.getenv("VECTOR_SERVICE_URL", "http://localhost:8005"),
            "graph": os.getenv("GRAPH_SERVICE_URL", "http://localhost:8006"),
            "llm": os.getenv("LLM_SERVICE_URL", "http://localhost:8007"),
            "ai_agent": os.getenv("AI_AGENT_SERVICE_URL", "http://localhost:8008"),
            "websocket": os.getenv("WEBSOCKET_SERVICE_URL", "http://localhost:8009"),
            "storage": os.getenv("STORAGE_SERVICE_URL", "http://localhost:8010"),
            "analytics": os.getenv("ANALYTICS_SERVICE_URL", "http://localhost:8014"),
            "security": os.getenv("SECURITY_SERVICE_URL", "http://localhost:8015"),
            "collaboration": os.getenv("COLLABORATION_SERVICE_URL", "http://localhost:8016"),
            "knowledge": os.getenv("KNOWLEDGE_SERVICE_URL", "http://localhost:8017"),
            "service-registry": os.getenv("SERVICE_REGISTRY_URL", "http://localhost:8011"),
        }

        # HTTP client configuration
        self.timeout = httpx.Timeout(30.0, connect=5.0)
        self.client = httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100)
        )

        logger.info(f"ServiceClient initialized with endpoints: {list(self.services.keys())}")

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()

    def update_service_url(self, service_name: str, url: str):
        """Update service URL (useful for service discovery)"""
        self.services[service_name] = url
        logger.info(f"Updated {service_name} URL to {url}")

    async def _make_request(self, method: str, service: str, path: str,
                           json: Optional[Dict] = None, params: Optional[Dict] = None,
                           files: Optional[Dict] = None, headers: Optional[Dict] = None) -> Dict[str, Any]:
        """Make HTTP request to service"""
        try:
            if service not in self.services:
                raise ValueError(f"Unknown service: {service}")

            url = f"{self.services[service]}{path}"

            # Always add service authentication header
            request_headers = {
                "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
            }

            # Add Content-Type only if we're sending JSON data
            if json is not None:
                request_headers["Content-Type"] = "application/json"

            # Correlation ID propagation - try to get from environment or context
            corr_id = os.getenv("X_CORRELATION_ID")
            if corr_id:
                request_headers["X-Correlation-ID"] = corr_id

            # Add any additional headers
            if headers:
                request_headers.update(headers)

            logger.debug(f"ServiceClient: {method} {url}")

            response = await self.client.request(
                method=method,
                url=url,
                json=json,
                params=params,
                files=files,
                headers=request_headers
            )

            # Handle different response types
            if response.headers.get("content-type", "").startswith("application/json"):
                result = response.json()
            else:
                # Return raw content plus a few headers so callers can propagate content-type
                result = {
                    "content": response.content,
                    "status_code": response.status_code,
                    "content-type": response.headers.get("content-type"),
                    "Content-Type": response.headers.get("Content-Type"),
                }

            if response.status_code >= 400:
                logger.error(f"Service error {response.status_code}: {result}")
                raise httpx.HTTPStatusError(f"Service error: {response.status_code}", request=response.request, response=response)

            logger.debug(f"Request successful: {method} {url}")
            return result

        except httpx.TimeoutException as e:
            logger.error(f"Timeout calling {service} service: {e}")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error calling {service} service: {e}")
            raise
        except Exception as e:
            logger.error(f"Error calling {service} service: {e}")
            raise

    # Generic HTTP methods
    async def get(self, service: str, path: str, params: Optional[Dict] = None, headers: Optional[Dict] = None) -> Dict[str, Any]:
        """Make GET request to service"""
        return await self._make_request("GET", service, path, params=params, headers=headers)

    async def post(self, service: str, path: str, json: Optional[Dict] = None, headers: Optional[Dict] = None) -> Dict[str, Any]:
        """Make POST request to service"""
        return await self._make_request("POST", service, path, json=json, headers=headers)

    async def put(self, service: str, path: str, json: Optional[Dict] = None, headers: Optional[Dict] = None) -> Dict[str, Any]:
        """Make PUT request to service"""
        return await self._make_request("PUT", service, path, json=json, headers=headers)

    async def delete(self, service: str, path: str, headers: Optional[Dict] = None) -> Dict[str, Any]:
        """Make DELETE request to service"""
        return await self._make_request("DELETE", service, path, headers=headers)

    async def patch(self, service: str, path: str, json: Optional[Dict] = None, headers: Optional[Dict] = None) -> Dict[str, Any]:
        """Make PATCH request to service"""
        return await self._make_request("PATCH", service, path, json=json, headers=headers)

    # Service health check
    async def check_service_health(self, service: str) -> Dict:
        """Check health of specific service"""
        return await self._make_request("GET", service, "/health")

    # Service discovery integration
    async def discover_services(self) -> Dict[str, str]:
        """Discover service URLs from service registry"""
        try:
            # Use direct httpx call to avoid circular dependency with service registry
            registry_url = self.services.get("service-registry", "http://localhost:8011")
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{registry_url}/services",
                                          headers={"Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"})
                if response.status_code == 200:
                    services_data = response.json().get("services", {})

                    # Update service URLs
                    for service_name, service_info in services_data.items():
                        if service_name in self.services and "url" in service_info:
                            self.update_service_url(service_name, service_info["url"])

                    return {name: info.get("url", "") for name, info in services_data.items()}
                else:
                    logger.warning(f"Service registry returned {response.status_code}")
                    return {}
        except Exception as e:
            logger.warning(f"Service discovery failed: {e}")
            return {}

    async def refresh_service_urls(self) -> bool:
        """Refresh all service URLs from service registry"""
        try:
            discovered = await self.discover_services()
            if discovered:
                logger.info(f"Refreshed {len(discovered)} service URLs from registry")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to refresh service URLs: {e}")
            return False

    def get_service_url(self, service_name: str) -> Optional[str]:
        """Get current URL for a service"""
        return self.services.get(service_name)

    def is_service_available(self, service_name: str) -> bool:
        """Check if a service is configured"""
        return service_name in self.services and self.services[service_name] is not None

    async def get_service_health(self, service_name: str) -> Dict[str, Any]:
        """Get health status of a service from registry"""
        try:
            registry_url = self.services.get("service-registry", "http://localhost:8011")
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{registry_url}/services/{service_name}",
                                          headers={"Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"})
                if response.status_code == 200:
                    return response.json()
                else:
                    return {"status": "unknown", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}


# Global service client instance
_service_client: Optional[ServiceClient] = None


async def get_service_client() -> ServiceClient:
    """Get global service client instance"""
    global _service_client
    if _service_client is None:
        _service_client = ServiceClient()
    return _service_client


async def close_service_client():
    """Close global service client"""
    global _service_client
    if _service_client:
        await _service_client.close()
        _service_client = None