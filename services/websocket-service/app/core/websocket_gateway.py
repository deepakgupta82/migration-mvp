#!/usr/bin/env python3
"""
WebSocket Gateway Service - Clean Architecture Implementation
Extracted and consolidated from backend WebSocket managers

This service handles:
- Project-specific WebSocket connections
- Real-time processing updates  
- Stats broadcasting
- Crew workflow updates
- Multi-client connection management
"""

import logging
import json
import asyncio
from typing import Dict, Set, List, Any, Optional
from datetime import datetime
from enum import Enum
from fastapi import WebSocket, WebSocketDisconnect
from contextlib import asynccontextmanager

logger = logging.getLogger("websocket_service")

class WebSocketChannelType(Enum):
    """Types of WebSocket channels supported"""
    PROJECT_PROCESSING = "project_processing"
    PROJECT_STATS = "project_stats"
    CREW_CONFIG = "crew_config"
    DASHBOARD_STATS = "dashboard_stats"
    AGENT_WORKFLOWS = "agent_workflows"

class WebSocketConnection:
    """Represents a single WebSocket connection with metadata"""
    
    def __init__(self, websocket: WebSocket, channel_type: WebSocketChannelType, 
                 project_id: Optional[str] = None, metadata: Optional[Dict] = None):
        self.websocket = websocket
        self.channel_type = channel_type
        self.project_id = project_id
        self.metadata = metadata or {}
        self.connected_at = datetime.now()
        self.last_activity = self.connected_at
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert connection to dictionary for debugging"""
        return {
            "channel_type": self.channel_type.value,
            "project_id": self.project_id,
            "connected_at": self.connected_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "metadata": self.metadata
        }

class WebSocketGateway:
    """
    Clean WebSocket Gateway Service
    Consolidates all WebSocket functionality from backend
    """
    
    def __init__(self):
        self.logger = logger
        
        # Connection storage by channel type and project
        self._connections: Dict[WebSocketChannelType, Dict[str, Set[WebSocketConnection]]] = {}
        self._global_connections: Dict[WebSocketChannelType, Set[WebSocketConnection]] = {}
        
        # Connection metadata for monitoring
        self._connection_registry: Dict[WebSocket, WebSocketConnection] = {}
        
        # Initialize storage structures
        for channel_type in WebSocketChannelType:
            self._connections[channel_type] = {}
            self._global_connections[channel_type] = set()
            
        self.logger.info("WebSocket Gateway initialized")

    async def connect(self, 
                     websocket: WebSocket, 
                     channel_type: WebSocketChannelType, 
                     project_id: Optional[str] = None,
                     metadata: Optional[Dict] = None) -> WebSocketConnection:
        """
        Accept and register a new WebSocket connection
        
        Args:
            websocket: FastAPI WebSocket instance
            channel_type: Type of channel to connect to
            project_id: Optional project ID for project-specific channels
            metadata: Optional metadata for the connection
        """
        try:
            await websocket.accept()
            
            # Create connection object
            connection = WebSocketConnection(websocket, channel_type, project_id, metadata)
            
            # Register connection
            self._connection_registry[websocket] = connection
            
            # Add to appropriate storage
            if project_id:
                project_connections = self._connections[channel_type].setdefault(project_id, set())
                project_connections.add(connection)
                self.logger.info(f"WebSocket connected to {channel_type.value} for project {project_id}. "
                               f"Total project connections: {len(project_connections)}")
            else:
                self._global_connections[channel_type].add(connection)
                self.logger.info(f"WebSocket connected to global {channel_type.value}. "
                               f"Total global connections: {len(self._global_connections[channel_type])}")
            
            # Send initial data if needed
            await self._send_initial_data(connection)
            
            return connection
            
        except Exception as e:
            self.logger.error(f"Error connecting WebSocket: {e}")
            await self._safe_close_websocket(websocket)
            raise

    async def disconnect(self, websocket: WebSocket):
        """Disconnect and clean up a WebSocket connection"""
        if websocket not in self._connection_registry:
            return
            
        connection = self._connection_registry[websocket]
        
        try:
            # Remove from project connections
            if connection.project_id:
                project_connections = self._connections[connection.channel_type].get(connection.project_id, set())
                project_connections.discard(connection)
                
                # Clean up empty project entries
                if not project_connections:
                    self._connections[connection.channel_type].pop(connection.project_id, None)
                    
            # Remove from global connections
            else:
                self._global_connections[connection.channel_type].discard(connection)
            
            # Remove from registry
            self._connection_registry.pop(websocket, None)
            
            self.logger.info(f"WebSocket disconnected from {connection.channel_type.value}")
            
        except Exception as e:
            self.logger.error(f"Error during WebSocket disconnect: {e}")

    async def broadcast_to_project(self, 
                                  channel_type: WebSocketChannelType, 
                                  project_id: str, 
                                  message: Dict[str, Any]):
        """Broadcast message to all connections for a specific project and channel"""
        if channel_type not in self._connections:
            return
            
        project_connections = self._connections[channel_type].get(project_id, set())
        if not project_connections:
            self.logger.debug(f"No connections for project {project_id} on channel {channel_type.value}")
            return
        
        dead_connections = []
        active_count = 0
        
        # Add timestamp to message
        message_with_timestamp = {
            **message,
            "timestamp": datetime.now().isoformat(),
            "channel": channel_type.value,
            "project_id": project_id
        }
        
        for connection in list(project_connections):
            try:
                await connection.websocket.send_json(message_with_timestamp)
                connection.last_activity = datetime.now()
                active_count += 1
            except Exception as e:
                self.logger.warning(f"Failed to send message to WebSocket: {e}")
                dead_connections.append(connection.websocket)
        
        # Clean up dead connections
        for dead_ws in dead_connections:
            await self.disconnect(dead_ws)
            
        if active_count > 0:
            self.logger.info(f"Broadcasted to {active_count} connections for project {project_id} on {channel_type.value}")

    async def broadcast_global(self, 
                              channel_type: WebSocketChannelType, 
                              message: Dict[str, Any]):
        """Broadcast message to all global connections for a channel"""
        global_connections = self._global_connections.get(channel_type, set())
        if not global_connections:
            self.logger.debug(f"No global connections for channel {channel_type.value}")
            return
        
        dead_connections = []
        active_count = 0
        
        # Add timestamp to message
        message_with_timestamp = {
            **message,
            "timestamp": datetime.now().isoformat(),
            "channel": channel_type.value
        }
        
        for connection in list(global_connections):
            try:
                await connection.websocket.send_json(message_with_timestamp)
                connection.last_activity = datetime.now()
                active_count += 1
            except Exception as e:
                self.logger.warning(f"Failed to send global message to WebSocket: {e}")
                dead_connections.append(connection.websocket)
        
        # Clean up dead connections  
        for dead_ws in dead_connections:
            await self.disconnect(dead_ws)
            
        if active_count > 0:
            self.logger.info(f"Broadcasted globally to {active_count} connections on {channel_type.value}")

    async def send_to_connection(self, websocket: WebSocket, message: Dict[str, Any]):
        """Send message to a specific WebSocket connection"""
        if websocket not in self._connection_registry:
            self.logger.warning("Attempted to send message to unregistered WebSocket")
            return False
            
        connection = self._connection_registry[websocket]
        
        try:
            message_with_metadata = {
                **message,
                "timestamp": datetime.now().isoformat(),
                "channel": connection.channel_type.value
            }
            
            await websocket.send_json(message_with_metadata)
            connection.last_activity = datetime.now()
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send message to specific WebSocket: {e}")
            await self.disconnect(websocket)
            return False

    async def _send_initial_data(self, connection: WebSocketConnection):
        """Send initial data when a connection is established"""
        try:
            initial_message = {
                "type": "connection_established",
                "channel": connection.channel_type.value,
                "project_id": connection.project_id,
                "message": f"Connected to {connection.channel_type.value} channel"
            }
            
            if connection.project_id:
                initial_message["project_id"] = connection.project_id
            
            await connection.websocket.send_json(initial_message)
            
        except Exception as e:
            self.logger.error(f"Error sending initial data: {e}")

    async def _safe_close_websocket(self, websocket: WebSocket):
        """Safely close a WebSocket connection"""
        try:
            await websocket.close()
        except Exception as e:
            self.logger.debug(f"Error closing WebSocket (may already be closed): {e}")

    def get_connection_stats(self) -> Dict[str, Any]:
        """Get statistics about current connections"""
        stats = {
            "total_connections": len(self._connection_registry),
            "channels": {},
            "projects": {}
        }
        
        # Channel statistics
        for channel_type in WebSocketChannelType:
            global_count = len(self._global_connections[channel_type])
            project_count = sum(len(conns) for conns in self._connections[channel_type].values())
            
            stats["channels"][channel_type.value] = {
                "global_connections": global_count,
                "project_connections": project_count,
                "total": global_count + project_count
            }
        
        # Project statistics
        for channel_type in WebSocketChannelType:
            for project_id, connections in self._connections[channel_type].items():
                if project_id not in stats["projects"]:
                    stats["projects"][project_id] = {}
                stats["projects"][project_id][channel_type.value] = len(connections)
        
        return stats

    def get_active_connections(self) -> List[Dict[str, Any]]:
        """Get list of all active connections for debugging"""
        return [conn.to_dict() for conn in self._connection_registry.values()]

    async def cleanup_stale_connections(self, max_idle_minutes: int = 30):
        """Clean up connections that haven't been active recently"""
        cutoff_time = datetime.now().timestamp() - (max_idle_minutes * 60)
        stale_websockets = []
        
        for websocket, connection in self._connection_registry.items():
            if connection.last_activity.timestamp() < cutoff_time:
                stale_websockets.append(websocket)
        
        for websocket in stale_websockets:
            self.logger.info(f"Cleaning up stale WebSocket connection")
            await self.disconnect(websocket)
        
        return len(stale_websockets)

    # Legacy compatibility methods for existing backend integration
    async def broadcast_process_update(self, project_id: str, message: str):
        """Legacy method: broadcast processing update"""
        await self.broadcast_to_project(
            WebSocketChannelType.PROJECT_PROCESSING,
            project_id,
            {"type": "processing_update", "message": message}
        )

    async def broadcast_stats_update(self, project_id: str, stats: Dict[str, Any]):
        """Legacy method: broadcast stats update"""
        await self.broadcast_to_project(
            WebSocketChannelType.PROJECT_STATS,
            project_id,
            {"type": "stats_update", "stats": stats}
        )

    async def broadcast_crew_config_update(self, config_data: Dict[str, Any]):
        """Legacy method: broadcast crew configuration update"""
        await self.broadcast_global(
            WebSocketChannelType.CREW_CONFIG,
            {"type": "crew_config_update", "config": config_data}
        )

    async def health_check(self) -> Dict[str, Any]:
        """Health check for WebSocket service"""
        stats = self.get_connection_stats()
        return {
            "status": "healthy",
            "total_connections": stats["total_connections"],
            "channels_active": len([ch for ch, data in stats["channels"].items() if data["total"] > 0]),
            "projects_active": len(stats["projects"])
        }
