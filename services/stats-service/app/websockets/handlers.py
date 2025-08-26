"""
WebSocket handlers for real-time statistics updates
"""

import json
import logging
from fastapi import WebSocket, WebSocketDisconnect
from typing import Set, Dict, Any
import asyncio

logger = logging.getLogger("websocket-handlers")

class StatsWebSocketManager:
    """Manage WebSocket connections for real-time stats updates"""
    
    def __init__(self):
        # Active connections for platform stats
        self.platform_connections: Set[WebSocket] = set()
        
        # Active connections for project stats (project_id -> set of websockets)
        self.project_connections: Dict[str, Set[WebSocket]] = {}
        
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()
    
    async def connect_platform(self, websocket: WebSocket):
        """Connect a client to platform-wide stats updates"""
        await websocket.accept()
        async with self._lock:
            self.platform_connections.add(websocket)
        logger.info(f"Platform stats client connected. Total: {len(self.platform_connections)}")
    
    async def disconnect_platform(self, websocket: WebSocket):
        """Disconnect a client from platform stats updates"""
        async with self._lock:
            self.platform_connections.discard(websocket)
        logger.info(f"Platform stats client disconnected. Total: {len(self.platform_connections)}")
    
    async def connect_project(self, websocket: WebSocket, project_id: str):
        """Connect a client to project-specific stats updates"""
        await websocket.accept()
        async with self._lock:
            if project_id not in self.project_connections:
                self.project_connections[project_id] = set()
            self.project_connections[project_id].add(websocket)
        logger.info(f"Project {project_id} stats client connected. Total: {len(self.project_connections[project_id])}")
    
    async def disconnect_project(self, websocket: WebSocket, project_id: str):
        """Disconnect a client from project stats updates"""
        async with self._lock:
            if project_id in self.project_connections:
                self.project_connections[project_id].discard(websocket)
                # Clean up empty project connections
                if not self.project_connections[project_id]:
                    del self.project_connections[project_id]
        logger.info(f"Project {project_id} stats client disconnected")
    
    async def broadcast_platform_update(self, stats_data: Dict[str, Any]):
        """Broadcast platform stats update to all connected clients"""
        if not self.platform_connections:
            return
        
        message = {
            "type": "platform_stats_update",
            "data": stats_data,
            "timestamp": stats_data.get("last_updated")
        }
        
        disconnected = set()
        async with self._lock:
            for websocket in self.platform_connections:
                try:
                    await websocket.send_text(json.dumps(message))
                except Exception as e:
                    logger.warning(f"Failed to send platform stats to client: {e}")
                    disconnected.add(websocket)
            
            # Remove disconnected clients
            self.platform_connections -= disconnected
        
        if disconnected:
            logger.info(f"Removed {len(disconnected)} disconnected platform clients")
    
    async def broadcast_project_update(self, project_id: str, stats_data: Dict[str, Any]):
        """Broadcast project stats update to all clients connected to that project"""
        if project_id not in self.project_connections:
            return
        
        message = {
            "type": "project_stats_update",
            "project_id": project_id,
            "data": stats_data,
            "timestamp": stats_data.get("last_updated")
        }
        
        disconnected = set()
        async with self._lock:
            for websocket in self.project_connections[project_id]:
                try:
                    await websocket.send_text(json.dumps(message))
                except Exception as e:
                    logger.warning(f"Failed to send project {project_id} stats to client: {e}")
                    disconnected.add(websocket)
            
            # Remove disconnected clients
            self.project_connections[project_id] -= disconnected
            
            # Clean up empty project connections
            if not self.project_connections[project_id]:
                del self.project_connections[project_id]
        
        if disconnected:
            logger.info(f"Removed {len(disconnected)} disconnected project {project_id} clients")
    
    async def get_connection_stats(self) -> Dict[str, Any]:
        """Get current WebSocket connection statistics"""
        async with self._lock:
            project_counts = {
                project_id: len(connections) 
                for project_id, connections in self.project_connections.items()
            }
            
            return {
                "platform_connections": len(self.platform_connections),
                "project_connections": project_counts,
                "total_connections": (
                    len(self.platform_connections) + 
                    sum(len(conns) for conns in self.project_connections.values())
                )
            }

# Global WebSocket manager instance
websocket_manager = StatsWebSocketManager()

async def handle_platform_websocket(websocket: WebSocket, stats_processor):
    """Handle WebSocket connection for platform-wide statistics"""
    await websocket_manager.connect_platform(websocket)
    
    try:
        # Send initial stats
        platform_stats = await stats_processor.get_platform_stats()
        await websocket.send_text(json.dumps({
            "type": "initial_platform_stats",
            "data": platform_stats
        }))
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for any message (ping/pong or requests)
                message = await websocket.receive_text()
                data = json.loads(message)
                
                if data.get("type") == "request_update":
                    # Client requesting fresh stats
                    fresh_stats = await stats_processor.get_platform_stats()
                    await websocket.send_text(json.dumps({
                        "type": "platform_stats_update",
                        "data": fresh_stats
                    }))
                    
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                # Invalid JSON, ignore
                pass
            except Exception as e:
                logger.error(f"Error in platform WebSocket handler: {e}")
                break
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Platform WebSocket error: {e}")
    finally:
        await websocket_manager.disconnect_platform(websocket)

async def handle_project_websocket(websocket: WebSocket, project_id: str, stats_processor):
    """Handle WebSocket connection for project-specific statistics"""
    await websocket_manager.connect_project(websocket, project_id)
    
    try:
        # Send initial project stats
        project_stats = await stats_processor.get_project_stats(project_id)
        await websocket.send_text(json.dumps({
            "type": "initial_project_stats",
            "project_id": project_id,
            "data": project_stats
        }))
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for any message (ping/pong or requests)
                message = await websocket.receive_text()
                data = json.loads(message)
                
                if data.get("type") == "request_update":
                    # Client requesting fresh stats
                    fresh_stats = await stats_processor.get_project_stats(project_id)
                    await websocket.send_text(json.dumps({
                        "type": "project_stats_update",
                        "project_id": project_id,
                        "data": fresh_stats
                    }))
                    
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                # Invalid JSON, ignore
                pass
            except Exception as e:
                logger.error(f"Error in project {project_id} WebSocket handler: {e}")
                break
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Project {project_id} WebSocket error: {e}")
    finally:
        await websocket_manager.disconnect_project(websocket, project_id)
