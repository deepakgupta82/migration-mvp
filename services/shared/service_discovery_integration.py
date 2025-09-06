#!/usr/bin/env python3
"""
Service Discovery Integration Module
Provides utilities for services to integrate with service discovery
"""

import asyncio
import logging
from typing import Dict, Any, Optional
import os

from .service_client import get_service_client

logger = logging.getLogger("service-discovery-integration")


class ServiceDiscoveryIntegration:
    """Integration layer for service discovery"""

    def __init__(self, refresh_interval: int = 300):  # 5 minutes default
        self.refresh_interval = refresh_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start_auto_refresh(self):
        """Start automatic service URL refresh"""
        if self._running:
            logger.warning("Service discovery auto-refresh already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._auto_refresh_loop())
        logger.info(f"Started service discovery auto-refresh (interval: {self.refresh_interval}s)")

    async def stop_auto_refresh(self):
        """Stop automatic service URL refresh"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Stopped service discovery auto-refresh")

    async def _auto_refresh_loop(self):
        """Background loop for automatic service URL refresh"""
        while self._running:
            try:
                await self._refresh_service_urls()
            except Exception as e:
                logger.error(f"Error in service discovery refresh: {e}")

            await asyncio.sleep(self.refresh_interval)

    async def _refresh_service_urls(self):
        """Refresh service URLs from registry"""
        try:
            client = await get_service_client()
            success = await client.refresh_service_urls()
            if success:
                logger.debug("Successfully refreshed service URLs")
            else:
                logger.debug("Service URL refresh completed with no changes")
        except Exception as e:
            logger.warning(f"Failed to refresh service URLs: {e}")

    async def manual_refresh(self) -> bool:
        """Manually trigger service URL refresh"""
        try:
            client = await get_service_client()
            return await client.refresh_service_urls()
        except Exception as e:
            logger.error(f"Manual service refresh failed: {e}")
            return False

    async def get_service_status(self) -> Dict[str, Any]:
        """Get status of all services"""
        try:
            client = await get_service_client()
            services_status = {}

            for service_name in client.services.keys():
                try:
                    health = await client.get_service_health(service_name)
                    services_status[service_name] = {
                        "url": client.get_service_url(service_name),
                        "health": health,
                        "available": client.is_service_available(service_name)
                    }
                except Exception as e:
                    services_status[service_name] = {
                        "url": client.get_service_url(service_name),
                        "health": {"status": "error", "error": str(e)},
                        "available": False
                    }

            return {
                "services": services_status,
                "auto_refresh": {
                    "running": self._running,
                    "interval": self.refresh_interval
                }
            }
        except Exception as e:
            logger.error(f"Failed to get service status: {e}")
            return {"error": str(e)}


# Global instance
_service_discovery_integration: Optional[ServiceDiscoveryIntegration] = None


async def get_service_discovery_integration() -> ServiceDiscoveryIntegration:
    """Get global service discovery integration instance"""
    global _service_discovery_integration
    if _service_discovery_integration is None:
        refresh_interval = int(os.getenv("SERVICE_DISCOVERY_REFRESH_INTERVAL", "300"))
        _service_discovery_integration = ServiceDiscoveryIntegration(refresh_interval)
    return _service_discovery_integration


async def start_service_discovery():
    """Start service discovery integration"""
    integration = await get_service_discovery_integration()
    await integration.start_auto_refresh()


async def stop_service_discovery():
    """Stop service discovery integration"""
    integration = await get_service_discovery_integration()
    await integration.stop_auto_refresh()


async def refresh_services_now() -> bool:
    """Manually refresh service URLs"""
    integration = await get_service_discovery_integration()
    return await integration.manual_refresh()


async def get_services_status() -> Dict[str, Any]:
    """Get current status of all services"""
    integration = await get_service_discovery_integration()
    return await integration.get_service_status()