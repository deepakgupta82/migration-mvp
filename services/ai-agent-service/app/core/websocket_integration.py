"""
WebSocket Integration for CrewAI Streaming
Integrates CrewAI streaming components with the existing WebSocket infrastructure.
"""

import asyncio
import logging
import json
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
import httpx

from .crewai_streamer import crewai_streamer, CrewAIEvent
from .crewai_message_router import crewai_message_router

logger = logging.getLogger(__name__)

class WebSocketIntegration:
    """
    Integrates CrewAI streaming with the existing WebSocket infrastructure.
    Handles connection management, broadcasting, and health monitoring.
    """

    def __init__(self,
                 websocket_service_url: str = "http://localhost:8009",
                 auth_token: str = "service-backend-token",
                 service_name: str = "ai-agent-service"):
        self.websocket_service_url = websocket_service_url
        self.auth_token = auth_token
        self.service_name = service_name
        self.is_connected = False
        self.last_health_check = None
        self.connection_errors = 0
        self.max_connection_errors = 5
        self.health_check_interval = 30  # seconds
        self.http_timeout = httpx.Timeout(10.0, connect=5.0)

        # Monitoring
        self.broadcast_count = 0
        self.error_count = 0
        self.last_broadcast_time = None

        # Health check task
        self.health_check_task = None

    async def start_integration(self):
        """Start the WebSocket integration"""
        try:
            # Test initial connection
            await self._test_connection()

            # Register event handlers
            await self._register_event_handlers()

            # Start health monitoring
            self.health_check_task = asyncio.create_task(self._health_monitor())

            self.is_connected = True
            logger.info("WebSocket integration started successfully")

        except Exception as e:
            logger.error(f"Failed to start WebSocket integration: {e}")
            raise

    async def stop_integration(self):
        """Stop the WebSocket integration"""
        self.is_connected = False

        if self.health_check_task:
            self.health_check_task.cancel()
            try:
                await self.health_check_task
            except asyncio.CancelledError:
                pass

        logger.info("WebSocket integration stopped")

    async def _test_connection(self):
        """Test connection to WebSocket service"""
        try:
            headers = {
                "Authorization": f"Bearer {self.auth_token}",
                "Content-Type": "application/json"
            }

            async with httpx.AsyncClient(timeout=self.http_timeout) as client:
                response = await client.get(
                    f"{self.websocket_service_url}/health",
                    headers=headers
                )

                if response.status_code == 200:
                    logger.info("WebSocket service connection test successful")
                    return True
                else:
                    raise Exception(f"WebSocket service returned status {response.status_code}")

        except Exception as e:
            self.connection_errors += 1
            logger.error(f"WebSocket service connection test failed: {e}")

            if self.connection_errors >= self.max_connection_errors:
                raise Exception(f"Max connection errors ({self.max_connection_errors}) exceeded")

            return False

    async def _register_event_handlers(self):
        """Register event handlers for CrewAI events"""
        # Register with the streamer
        crewai_streamer.register_event_handler("all", self._handle_crewai_event)

        # Register with the message router
        crewai_message_router.register_handler("all", self._handle_routed_message)

        logger.info("Event handlers registered with CrewAI components")

    async def _handle_crewai_event(self, event: CrewAIEvent):
        """Handle CrewAI events for broadcasting"""
        try:
            await self._broadcast_event(event)
        except Exception as e:
            logger.error(f"Error handling CrewAI event: {e}")
            self.error_count += 1

    async def _handle_routed_message(self, message):
        """Handle routed messages for broadcasting"""
        try:
            await self._broadcast_message(message)
        except Exception as e:
            logger.error(f"Error handling routed message: {e}")
            self.error_count += 1

    async def _broadcast_event(self, event: CrewAIEvent):
        """Broadcast a CrewAI event via WebSocket"""
        if not self.is_connected:
            return

        try:
            payload = {
                "type": "crewai_event",
                "event_type": event.event_type.value,
                "project_id": event.project_id,
                "correlation_id": event.correlation_id,
                "timestamp": event.timestamp.isoformat(),
                "data": event.data,
                "metadata": event.metadata,
                "source": self.service_name
            }

            headers = {
                "Authorization": f"Bearer {self.auth_token}",
                "X-Correlation-ID": event.correlation_id,
                "Content-Type": "application/json"
            }

            async with httpx.AsyncClient(timeout=self.http_timeout) as client:
                response = await client.post(
                    f"{self.websocket_service_url}/api/websocket/broadcast",
                    json=payload,
                    headers=headers
                )

                if response.status_code == 200:
                    self.broadcast_count += 1
                    self.last_broadcast_time = datetime.now()
                    logger.debug(f"Broadcasted CrewAI event: {event.event_type.value}")
                else:
                    raise Exception(f"Broadcast failed with status {response.status_code}: {response.text}")

        except Exception as e:
            logger.error(f"Error broadcasting CrewAI event: {e}")
            self.error_count += 1

            # Try to reconnect if connection seems broken
            if "connection" in str(e).lower():
                asyncio.create_task(self._test_connection())

    async def _broadcast_message(self, message):
        """Broadcast a routed message via WebSocket"""
        if not self.is_connected:
            return

        try:
            # Convert message to broadcast format
            payload = {
                "type": "crewai_message",
                "channel": message.channel.value if hasattr(message, 'channel') else "unknown",
                "priority": message.priority.value if hasattr(message, 'priority') else "normal",
                "project_id": message.project_id,
                "correlation_id": message.correlation_id,
                "payload": message.payload,
                "timestamp": message.timestamp.isoformat(),
                "source": self.service_name
            }

            headers = {
                "Authorization": f"Bearer {self.auth_token}",
                "X-Correlation-ID": message.correlation_id,
                "Content-Type": "application/json"
            }

            async with httpx.AsyncClient(timeout=self.http_timeout) as client:
                response = await client.post(
                    f"{self.websocket_service_url}/api/websocket/broadcast",
                    json=payload,
                    headers=headers
                )

                if response.status_code == 200:
                    self.broadcast_count += 1
                    self.last_broadcast_time = datetime.now()
                    logger.debug("Broadcasted routed message")
                else:
                    raise Exception(f"Broadcast failed with status {response.status_code}: {response.text}")

        except Exception as e:
            logger.error(f"Error broadcasting routed message: {e}")
            self.error_count += 1

    async def _health_monitor(self):
        """Monitor WebSocket service health"""
        while self.is_connected:
            try:
                await asyncio.sleep(self.health_check_interval)

                # Perform health check
                is_healthy = await self._test_connection()

                if is_healthy:
                    self.last_health_check = datetime.now()
                    self.connection_errors = 0  # Reset error count on successful health check
                else:
                    logger.warning("WebSocket service health check failed")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health monitor: {e}")

    async def broadcast_custom_message(self, channel: str, message: Dict[str, Any],
                                     project_id: str = "default", correlation_id: str = ""):
        """Broadcast a custom message"""
        if not self.is_connected:
            logger.warning("Cannot broadcast: WebSocket integration not connected")
            return

        try:
            payload = {
                "type": "custom_message",
                "channel": channel,
                "project_id": project_id,
                "correlation_id": correlation_id,
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "source": self.service_name
            }

            headers = {
                "Authorization": f"Bearer {self.auth_token}",
                "X-Correlation-ID": correlation_id,
                "Content-Type": "application/json"
            }

            async with httpx.AsyncClient(timeout=self.http_timeout) as client:
                response = await client.post(
                    f"{self.websocket_service_url}/api/websocket/broadcast",
                    json=payload,
                    headers=headers
                )

                if response.status_code == 200:
                    self.broadcast_count += 1
                    self.last_broadcast_time = datetime.now()
                    logger.debug(f"Broadcasted custom message to channel: {channel}")
                else:
                    logger.error(f"Custom message broadcast failed: {response.status_code}")

        except Exception as e:
            logger.error(f"Error broadcasting custom message: {e}")
            self.error_count += 1

    def get_integration_stats(self) -> Dict[str, Any]:
        """Get integration statistics"""
        return {
            "is_connected": self.is_connected,
            "broadcast_count": self.broadcast_count,
            "error_count": self.error_count,
            "connection_errors": self.connection_errors,
            "last_health_check": self.last_health_check.isoformat() if self.last_health_check else None,
            "last_broadcast_time": self.last_broadcast_time.isoformat() if self.last_broadcast_time else None,
            "websocket_service_url": self.websocket_service_url,
            "service_name": self.service_name
        }

    async def force_reconnect(self):
        """Force reconnection to WebSocket service"""
        logger.info("Forcing reconnection to WebSocket service")
        self.is_connected = False

        try:
            await self._test_connection()
            self.is_connected = True
            logger.info("Reconnection successful")
        except Exception as e:
            logger.error(f"Reconnection failed: {e}")

class WebSocketChannelManager:
    """
    Manages WebSocket channels for different types of CrewAI communications.
    """

    def __init__(self, integration: WebSocketIntegration):
        self.integration = integration
        self.channels = {
            "crew_events": "Crew execution events",
            "agent_activity": "Agent-specific activities",
            "tool_executions": "Tool execution monitoring",
            "progress_updates": "Progress and status updates",
            "error_alerts": "Error notifications",
            "system_notifications": "System-wide notifications"
        }

    async def broadcast_to_channel(self, channel: str, message: Dict[str, Any],
                                 project_id: str = "default", correlation_id: str = ""):
        """Broadcast message to a specific channel"""
        if channel not in self.channels:
            logger.warning(f"Unknown channel: {channel}")
            return

        await self.integration.broadcast_custom_message(
            channel, message, project_id, correlation_id
        )

    async def broadcast_crew_status(self, crew_id: str, status: str, project_id: str, correlation_id: str):
        """Broadcast crew status update"""
        message = {
            "crew_id": crew_id,
            "status": status,
            "timestamp": datetime.now().isoformat()
        }

        await self.broadcast_to_channel("crew_events", message, project_id, correlation_id)

    async def broadcast_agent_activity(self, agent_name: str, activity: str, project_id: str, correlation_id: str):
        """Broadcast agent activity"""
        message = {
            "agent_name": agent_name,
            "activity": activity,
            "timestamp": datetime.now().isoformat()
        }

        await self.broadcast_to_channel("agent_activity", message, project_id, correlation_id)

    async def broadcast_tool_execution(self, tool_name: str, status: str, project_id: str, correlation_id: str):
        """Broadcast tool execution status"""
        message = {
            "tool_name": tool_name,
            "status": status,
            "timestamp": datetime.now().isoformat()
        }

        await self.broadcast_to_channel("tool_executions", message, project_id, correlation_id)

    async def broadcast_error_alert(self, error_type: str, error_message: str, project_id: str, correlation_id: str):
        """Broadcast error alert"""
        message = {
            "error_type": error_type,
            "error_message": error_message,
            "timestamp": datetime.now().isoformat(),
            "severity": "high"
        }

        await self.broadcast_to_channel("error_alerts", message, project_id, correlation_id)

    def get_available_channels(self) -> Dict[str, str]:
        """Get list of available channels"""
        return self.channels.copy()

# Global instances
websocket_integration = WebSocketIntegration()
channel_manager = WebSocketChannelManager(websocket_integration)

async def initialize_websocket_integration():
    """Initialize WebSocket integration on startup"""
    try:
        await websocket_integration.start_integration()
        logger.info("WebSocket integration initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize WebSocket integration: {e}")
        # Don't raise - allow service to continue without WebSocket integration
        logger.warning("CrewAI streaming will work without WebSocket broadcasting")

# Auto-initialize on import
asyncio.create_task(initialize_websocket_integration())