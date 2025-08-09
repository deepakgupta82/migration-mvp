"""
WebSocket Stats Manager for real-time statistics updates
Manages WebSocket connections for project and platform statistics
"""

import asyncio
import json
import logging
from typing import Dict, List, Set
from fastapi import WebSocket
from datetime import datetime

logger = logging.getLogger(__name__)


class WebSocketStatsManager:
    """Manages WebSocket connections for real-time stats updates"""
    
    def __init__(self):
        # Project-specific connections: {project_id: [websockets]}
        self.project_connections: Dict[str, List[WebSocket]] = {}
        
        # Dashboard/platform-wide connections
        self.dashboard_connections: List[WebSocket] = []
        
        # Connection metadata for debugging
        self.connection_metadata: Dict[WebSocket, Dict] = {}
        
        logger.info("WebSocket Stats Manager initialized")
    
    async def subscribe_to_project_stats(self, websocket: WebSocket, project_id: str):
        """Subscribe a WebSocket to project-specific stats updates"""
        try:
            if project_id not in self.project_connections:
                self.project_connections[project_id] = []
            
            self.project_connections[project_id].append(websocket)
            self.connection_metadata[websocket] = {
                "type": "project",
                "project_id": project_id,
                "connected_at": datetime.now().isoformat()
            }
            
            logger.info(f"WebSocket subscribed to project {project_id} stats. Total project connections: {len(self.project_connections[project_id])}")
            
            # Send initial stats
            await self._send_initial_project_stats(websocket, project_id)
            
        except Exception as e:
            logger.error(f"Error subscribing to project stats: {e}")
            await self._safe_close_websocket(websocket)
    
    async def subscribe_to_dashboard_stats(self, websocket: WebSocket):
        """Subscribe a WebSocket to platform-wide stats updates"""
        try:
            self.dashboard_connections.append(websocket)
            self.connection_metadata[websocket] = {
                "type": "dashboard",
                "connected_at": datetime.now().isoformat()
            }
            
            logger.info(f"WebSocket subscribed to dashboard stats. Total dashboard connections: {len(self.dashboard_connections)}")
            
            # Send initial stats
            await self._send_initial_platform_stats(websocket)
            
        except Exception as e:
            logger.error(f"Error subscribing to dashboard stats: {e}")
            await self._safe_close_websocket(websocket)
    
    async def broadcast_to_project(self, project_id: str, message: dict):
        """Broadcast stats update to all project subscribers"""
        if project_id not in self.project_connections:
            return
        
        dead_connections = []
        active_connections = self.project_connections[project_id].copy()
        
        logger.info(f"Broadcasting to {len(active_connections)} project {project_id} connections")
        
        for websocket in active_connections:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send message to project websocket: {e}")
                dead_connections.append(websocket)
        
        # Clean up dead connections
        for dead_ws in dead_connections:
            await self._remove_connection(dead_ws)
    
    async def broadcast_to_dashboard(self, message: dict):
        """Broadcast stats update to all dashboard subscribers"""
        dead_connections = []
        active_connections = self.dashboard_connections.copy()
        
        logger.info(f"Broadcasting to {len(active_connections)} dashboard connections")
        
        for websocket in active_connections:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send message to dashboard websocket: {e}")
                dead_connections.append(websocket)
        
        # Clean up dead connections
        for dead_ws in dead_connections:
            await self._remove_connection(dead_ws)
    
    async def disconnect_websocket(self, websocket: WebSocket):
        """Properly disconnect and clean up a WebSocket"""
        await self._remove_connection(websocket)
        await self._safe_close_websocket(websocket)
    
    async def _remove_connection(self, websocket: WebSocket):
        """Remove a WebSocket from all connection lists"""
        try:
            # Remove from dashboard connections
            if websocket in self.dashboard_connections:
                self.dashboard_connections.remove(websocket)
                logger.info(f"Removed dashboard connection. Remaining: {len(self.dashboard_connections)}")
            
            # Remove from project connections
            for project_id, connections in self.project_connections.items():
                if websocket in connections:
                    connections.remove(websocket)
                    logger.info(f"Removed project {project_id} connection. Remaining: {len(connections)}")
                    
                    # Clean up empty project connection lists
                    if not connections:
                        del self.project_connections[project_id]
            
            # Remove metadata
            if websocket in self.connection_metadata:
                del self.connection_metadata[websocket]
                
        except Exception as e:
            logger.error(f"Error removing connection: {e}")
    
    async def _safe_close_websocket(self, websocket: WebSocket):
        """Safely close a WebSocket connection"""
        try:
            await websocket.close()
        except Exception as e:
            logger.warning(f"Error closing websocket: {e}")
    
    async def _send_initial_project_stats(self, websocket: WebSocket, project_id: str):
        """Send initial project stats to a newly connected WebSocket"""
        try:
            from app.core.stats_service import get_stats_service
            stats_service = get_stats_service()
            stats = await stats_service.calculate_project_stats(project_id)
            
            message = {
                "type": "initial_project_stats",
                "project_id": project_id,
                "data": stats,
                "timestamp": datetime.now().isoformat()
            }
            
            await websocket.send_json(message)
            logger.info(f"Sent initial project stats for {project_id}: {stats}")

        except Exception as e:
            logger.error(f"Error sending initial project stats for {project_id}: {e}", exc_info=True)
    
    async def _send_initial_platform_stats(self, websocket: WebSocket):
        """Send initial platform stats to a newly connected WebSocket"""
        try:
            from app.core.stats_service import get_stats_service
            stats_service = get_stats_service()
            stats = await stats_service.calculate_platform_stats()
            
            message = {
                "type": "initial_platform_stats",
                "data": stats,
                "timestamp": datetime.now().isoformat()
            }
            
            await websocket.send_json(message)
            logger.info("Sent initial platform stats")
            
        except Exception as e:
            logger.error(f"Error sending initial platform stats: {e}")
    
    def get_connection_stats(self) -> dict:
        """Get statistics about current WebSocket connections"""
        total_project_connections = sum(len(connections) for connections in self.project_connections.values())
        
        return {
            "dashboard_connections": len(self.dashboard_connections),
            "project_connections": total_project_connections,
            "projects_with_connections": len(self.project_connections),
            "total_connections": len(self.dashboard_connections) + total_project_connections
        }


# Global instance
_websocket_stats_manager = None


def get_websocket_stats_manager() -> WebSocketStatsManager:
    """Get the global WebSocket stats manager instance"""
    global _websocket_stats_manager
    if _websocket_stats_manager is None:
        _websocket_stats_manager = WebSocketStatsManager()
    return _websocket_stats_manager
