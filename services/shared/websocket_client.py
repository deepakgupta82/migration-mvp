#!/usr/bin/env python3
"""
Shared WebSocket Client for Services
Standardized client for communicating with the WebSocket service
"""

import logging
from typing import Dict, Any, Optional, List
from enum import Enum

import sys
import os
sys.path.append(os.path.dirname(__file__))
from .service_client import get_service_client

logger = logging.getLogger("websocket_client")


class WebSocketChannelType(str, Enum):
    """WebSocket channel types matching the gateway"""
    PROJECT_PROCESSING = "project_processing"
    PROJECT_STATS = "project_stats"
    CREW_CONFIG = "crew_config"
    DASHBOARD_STATS = "dashboard_stats"
    AGENT_WORKFLOWS = "agent_workflows"
    PROGRESS_TRACKING = "progress_tracking"
    SERVICE_HEALTH = "service_health"
    DOCUMENT_PROCESSING = "document_processing"
    CLOUD_TOOLS = "cloud_tools"


class WebSocketClient:
    """Client for interacting with the WebSocket service"""

    def __init__(self):
        self.service_client = None

    async def _get_client(self):
        """Get the service client instance"""
        if self.service_client is None:
            self.service_client = await get_service_client()
        return self.service_client

    async def broadcast_to_project(
        self,
        channel_type: WebSocketChannelType,
        project_id: str,
        message: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Broadcast message to project-specific WebSocket channel"""
        try:
            client = await self._get_client()

            broadcast_request = {
                "channel_type": channel_type.value,
                "project_id": project_id,
                "message": message
            }

            response = await client.post("websocket", "/broadcast", json=broadcast_request)
            logger.info(f"Broadcasted to project {project_id} on {channel_type.value}")
            return response

        except Exception as e:
            logger.error(f"Failed to broadcast to project {project_id}: {e}")
            raise

    async def broadcast_global(
        self,
        channel_type: WebSocketChannelType,
        message: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Broadcast message to global WebSocket channel"""
        try:
            client = await self._get_client()

            broadcast_request = {
                "channel_type": channel_type.value,
                "message": message
            }

            response = await client.post("websocket", "/broadcast", json=broadcast_request)
            logger.info(f"Broadcasted globally on {channel_type.value}")
            return response

        except Exception as e:
            logger.error(f"Failed to broadcast globally: {e}")
            raise

    async def send_processing_update(self, project_id: str, message: str) -> Dict[str, Any]:
        """Send processing update to project"""
        return await self.broadcast_to_project(
            WebSocketChannelType.PROJECT_PROCESSING,
            project_id,
            {"type": "processing_update", "message": message}
        )

    async def send_stats_update(self, project_id: str, stats: Dict[str, Any]) -> Dict[str, Any]:
        """Send statistics update to project"""
        return await self.broadcast_to_project(
            WebSocketChannelType.PROJECT_STATS,
            project_id,
            {"type": "stats_update", "stats": stats}
        )

    async def send_progress_update(
        self,
        project_id: str,
        event_id: str,
        progress_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send progress update to project"""
        return await self.broadcast_to_project(
            WebSocketChannelType.PROGRESS_TRACKING,
            project_id,
            {
                "type": "progress_update",
                "event_id": event_id,
                "progress": progress_data
            }
        )

    async def send_document_processing_update(
        self,
        project_id: str,
        document_id: str,
        status: str,
        progress: Optional[float] = None,
        message: Optional[str] = None,
        analysis_id: Optional[str] = None,
        analysis_status: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send document processing update"""
        message_data = {
            "type": "document_update",
            "document_id": document_id,
            "status": status
        }

        if progress is not None:
            message_data["progress"] = progress
        if message:
            message_data["message"] = message
        if analysis_id:
            message_data["analysis_id"] = analysis_id
        if analysis_status:
            message_data["analysis_status"] = analysis_status

        return await self.broadcast_to_project(
            WebSocketChannelType.DOCUMENT_PROCESSING,
            project_id,
            message_data
        )

    async def send_agent_workflow_update(
        self,
        project_id: str,
        workflow_id: str,
        status: str,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Send AI agent workflow update"""
        message_data = {
            "type": "workflow_update",
            "workflow_id": workflow_id,
            "status": status
        }

        if data:
            message_data.update(data)

        return await self.broadcast_to_project(
            WebSocketChannelType.AGENT_WORKFLOWS,
            project_id,
            message_data
        )

    async def send_service_health_update(
        self,
        service_name: str,
        status: str,
        response_time: Optional[float] = None
    ) -> Dict[str, Any]:
        """Send service health update"""
        try:
            client = await self._get_client()

            health_data = {
                "service_name": service_name,
                "status": status
            }

            if response_time is not None:
                health_data["response_time"] = response_time

            response = await client.post("websocket", "/health/update", json=health_data)
            logger.info(f"Updated health status for {service_name}: {status}")
            return response

        except Exception as e:
            logger.error(f"Failed to update service health for {service_name}: {e}")
            raise

    async def start_operation_tracking(
        self,
        project_id: str,
        service_name: str,
        operation: str,
        total_steps: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Start operation tracking"""
        try:
            client = await self._get_client()

            tracking_data = {
                "project_id": project_id,
                "service_name": service_name,
                "operation": operation,
                "total_steps": total_steps
            }

            if metadata:
                tracking_data["metadata"] = metadata

            response = await client.post("websocket", "/progress/start", json=tracking_data)

            event_id = response.get("event_id")
            if event_id:
                logger.info(f"Started tracking operation {operation} for project {project_id}")
                return event_id
            else:
                raise ValueError("No event_id returned from tracking start")

        except Exception as e:
            logger.error(f"Failed to start operation tracking: {e}")
            raise

    async def update_operation_progress(
        self,
        event_id: str,
        current_step: str,
        step_number: int,
        status: str = "in_progress",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Update operation progress"""
        try:
            client = await self._get_client()

            progress_data = {
                "event_id": event_id,
                "current_step": current_step,
                "step_number": step_number,
                "status": status
            }

            if metadata:
                progress_data["metadata"] = metadata

            response = await client.post("websocket", "/progress/update", json=progress_data)
            logger.debug(f"Updated progress for event {event_id}: {current_step}")
            return response

        except Exception as e:
            logger.error(f"Failed to update operation progress for {event_id}: {e}")
            raise

    async def complete_operation_tracking(
        self,
        event_id: str,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """Complete operation tracking"""
        try:
            client = await self._get_client()

            completion_data = {
                "event_id": event_id,
                "success": success
            }

            if error_message:
                completion_data["error_message"] = error_message

            response = await client.post("websocket", "/progress/complete", json=completion_data)
            logger.info(f"Completed tracking for event {event_id}: {'success' if success else 'failed'}")
            return response

        except Exception as e:
            logger.error(f"Failed to complete operation tracking for {event_id}: {e}")
            raise

    async def get_operation_status(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get operation status"""
        try:
            client = await self._get_client()
            response = await client.get("websocket", f"/progress/operation/{event_id}")
            return response.get("operation")
        except Exception as e:
            logger.error(f"Failed to get operation status for {event_id}: {e}")
            return None

    async def get_project_operations(self, project_id: str) -> List[Dict[str, Any]]:
        """Get all operations for a project"""
        try:
            client = await self._get_client()
            response = await client.get("websocket", f"/progress/project/{project_id}")
            return response.get("operations", [])
        except Exception as e:
            logger.error(f"Failed to get project operations for {project_id}: {e}")
            return []


# Global WebSocket client instance
_websocket_client = None


async def get_websocket_client() -> WebSocketClient:
    """Get global WebSocket client instance"""
    global _websocket_client
    if _websocket_client is None:
        _websocket_client = WebSocketClient()
    return _websocket_client