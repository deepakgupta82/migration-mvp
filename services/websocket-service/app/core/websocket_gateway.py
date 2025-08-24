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
import uuid
from typing import Dict, Set, List, Any, Optional, Union
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
from fastapi import WebSocket, WebSocketDisconnect
from contextlib import asynccontextmanager

logger = logging.getLogger("websocket_service")

@dataclass
class ProgressEvent:
    """Represents a progress tracking event"""
    event_id: str
    project_id: str
    service_name: str
    operation: str
    status: str  # pending, in_progress, completed, failed
    progress_percentage: float
    current_step: str
    total_steps: int
    current_step_number: int
    metadata: Dict[str, Any]
    timestamp: datetime
    estimated_completion: Optional[datetime] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        if self.estimated_completion:
            data['estimated_completion'] = self.estimated_completion.isoformat()
        return data

@dataclass
class ServiceHealthEvent:
    """Represents a service health event"""
    service_name: str
    status: str  # healthy, unhealthy, timeout, error
    response_time: Optional[float]
    timestamp: datetime
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data

class ProgressTracker:
    """Advanced progress tracking with event history and analytics"""
    
    def __init__(self):
        self.active_operations: Dict[str, ProgressEvent] = {}
        self.event_history: List[ProgressEvent] = []
        self.service_health: Dict[str, ServiceHealthEvent] = {}
        self.max_history_size = 1000
        
    def start_operation(self, project_id: str, service_name: str, operation: str, 
                       total_steps: int, metadata: Optional[Dict] = None) -> str:
        """Start tracking a new operation"""
        event_id = str(uuid.uuid4())
        
        progress_event = ProgressEvent(
            event_id=event_id,
            project_id=project_id,
            service_name=service_name,
            operation=operation,
            status="pending",
            progress_percentage=0.0,
            current_step="Initializing",
            total_steps=total_steps,
            current_step_number=0,
            metadata=metadata or {},
            timestamp=datetime.now()
        )
        
        self.active_operations[event_id] = progress_event
        self._add_to_history(progress_event)
        
        return event_id
    
    def update_progress(self, event_id: str, current_step: str, step_number: int, 
                       status: str = "in_progress", metadata: Optional[Dict] = None) -> Optional[ProgressEvent]:
        """Update progress for an operation"""
        if event_id not in self.active_operations:
            return None
            
        event = self.active_operations[event_id]
        event.current_step = current_step
        event.current_step_number = step_number
        event.status = status
        event.progress_percentage = (step_number / event.total_steps) * 100
        event.timestamp = datetime.now()
        
        if metadata:
            event.metadata.update(metadata)
            
        # Estimate completion time based on progress
        if step_number > 0 and status == "in_progress":
            elapsed = event.timestamp - event.timestamp
            time_per_step = elapsed.total_seconds() / step_number
            remaining_steps = event.total_steps - step_number
            estimated_remaining = timedelta(seconds=time_per_step * remaining_steps)
            event.estimated_completion = event.timestamp + estimated_remaining
        
        self._add_to_history(event)
        return event
    
    def complete_operation(self, event_id: str, success: bool = True, 
                          error_message: Optional[str] = None) -> Optional[ProgressEvent]:
        """Complete an operation"""
        if event_id not in self.active_operations:
            return None
            
        event = self.active_operations[event_id]
        event.status = "completed" if success else "failed"
        event.progress_percentage = 100.0 if success else event.progress_percentage
        event.timestamp = datetime.now()
        event.error_message = error_message
        
        self._add_to_history(event)
        
        # Remove from active operations
        del self.active_operations[event_id]
        
        return event
    
    def update_service_health(self, service_name: str, status: str, 
                             response_time: Optional[float] = None, 
                             metadata: Optional[Dict] = None) -> ServiceHealthEvent:
        """Update service health status"""
        health_event = ServiceHealthEvent(
            service_name=service_name,
            status=status,
            response_time=response_time,
            timestamp=datetime.now(),
            metadata=metadata or {}
        )
        
        self.service_health[service_name] = health_event
        return health_event
    
    def get_operation_status(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of an operation"""
        if event_id in self.active_operations:
            return self.active_operations[event_id].to_dict()
        return None
    
    def get_project_operations(self, project_id: str) -> List[Dict[str, Any]]:
        """Get all operations for a project"""
        operations = []
        for event in self.active_operations.values():
            if event.project_id == project_id:
                operations.append(event.to_dict())
        return operations
    
    def get_service_operations(self, service_name: str) -> List[Dict[str, Any]]:
        """Get all operations for a service"""
        operations = []
        for event in self.active_operations.values():
            if event.service_name == service_name:
                operations.append(event.to_dict())
        return operations
    
    def get_recent_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent operation history"""
        recent_events = sorted(self.event_history, key=lambda x: x.timestamp, reverse=True)[:limit]
        return [event.to_dict() for event in recent_events]
    
    def get_analytics_summary(self) -> Dict[str, Any]:
        """Get analytics summary of operations"""
        now = datetime.now()
        last_hour = now - timedelta(hours=1)
        last_day = now - timedelta(days=1)
        
        # Filter recent events
        hour_events = [e for e in self.event_history if e.timestamp >= last_hour]
        day_events = [e for e in self.event_history if e.timestamp >= last_day]
        
        return {
            "active_operations": len(self.active_operations),
            "total_services": len(set(e.service_name for e in self.active_operations.values())),
            "healthy_services": len([s for s in self.service_health.values() if s.status == "healthy"]),
            "operations_last_hour": len(hour_events),
            "operations_last_day": len(day_events),
            "success_rate_last_day": self._calculate_success_rate(day_events),
            "average_response_time": self._calculate_avg_response_time(),
            "service_health_summary": {name: health.status for name, health in self.service_health.items()}
        }
    
    def _add_to_history(self, event: ProgressEvent):
        """Add event to history with size management"""
        # Create a copy for history
        history_event = ProgressEvent(
            event_id=event.event_id,
            project_id=event.project_id,
            service_name=event.service_name,
            operation=event.operation,
            status=event.status,
            progress_percentage=event.progress_percentage,
            current_step=event.current_step,
            total_steps=event.total_steps,
            current_step_number=event.current_step_number,
            metadata=event.metadata.copy(),
            timestamp=event.timestamp,
            estimated_completion=event.estimated_completion,
            error_message=event.error_message
        )
        
        self.event_history.append(history_event)
        
        # Maintain history size
        if len(self.event_history) > self.max_history_size:
            self.event_history = self.event_history[-self.max_history_size:]
    
    def _calculate_success_rate(self, events: List[ProgressEvent]) -> float:
        """Calculate success rate for given events"""
        if not events:
            return 0.0
            
        completed_events = [e for e in events if e.status in ["completed", "failed"]]
        if not completed_events:
            return 0.0
            
        successful = len([e for e in completed_events if e.status == "completed"])
        return (successful / len(completed_events)) * 100
    
    def _calculate_avg_response_time(self) -> float:
        """Calculate average service response time"""
        response_times = [h.response_time for h in self.service_health.values() if h.response_time is not None]
        if not response_times:
            return 0.0
        return sum(response_times) / len(response_times)

class WebSocketChannelType(Enum):
    """Types of WebSocket channels supported"""
    PROJECT_PROCESSING = "project_processing"
    PROJECT_STATS = "project_stats"
    CREW_CONFIG = "crew_config"
    DASHBOARD_STATS = "dashboard_stats"
    AGENT_WORKFLOWS = "agent_workflows"
    PROGRESS_TRACKING = "progress_tracking"
    SERVICE_HEALTH = "service_health"
    DOCUMENT_PROCESSING = "document_processing"
    CLOUD_TOOLS = "cloud_tools"

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
    Consolidates all WebSocket functionality from backend with advanced progress tracking
    """
    
    def __init__(self):
        self.logger = logger
        
        # Connection storage by channel type and project
        self._connections: Dict[WebSocketChannelType, Dict[str, Set[WebSocketConnection]]] = {}
        self._global_connections: Dict[WebSocketChannelType, Set[WebSocketConnection]] = {}
        
        # Connection metadata for monitoring
        self._connection_registry: Dict[WebSocket, WebSocketConnection] = {}
        
        # Progress tracking system
        self.progress_tracker = ProgressTracker()
        
        # Initialize storage structures
        for channel_type in WebSocketChannelType:
            self._connections[channel_type] = {}
            self._global_connections[channel_type] = set()
            
        self.logger.info("WebSocket Gateway with Progress Tracking initialized")

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
    
    # Advanced Progress Tracking Methods
    
    async def start_operation_tracking(self, project_id: str, service_name: str, 
                                     operation: str, total_steps: int, 
                                     metadata: Optional[Dict] = None) -> str:
        """Start tracking a new operation and broadcast to relevant channels"""
        event_id = self.progress_tracker.start_operation(
            project_id, service_name, operation, total_steps, metadata
        )
        
        # Broadcast to progress tracking channel
        await self.broadcast_to_project(
            WebSocketChannelType.PROGRESS_TRACKING,
            project_id,
            {
                "type": "operation_started",
                "event_id": event_id,
                "operation": operation,
                "service_name": service_name,
                "total_steps": total_steps
            }
        )
        
        return event_id
    
    async def update_operation_progress(self, event_id: str, current_step: str, 
                                       step_number: int, status: str = "in_progress", 
                                       metadata: Optional[Dict] = None):
        """Update operation progress and broadcast updates"""
        event = self.progress_tracker.update_progress(
            event_id, current_step, step_number, status, metadata
        )
        
        if event:
            # Broadcast to progress tracking channel for the project
            await self.broadcast_to_project(
                WebSocketChannelType.PROGRESS_TRACKING,
                event.project_id,
                {
                    "type": "progress_update",
                    "event_id": event_id,
                    "progress": event.to_dict()
                }
            )
            
            # Also broadcast to project processing channel for legacy compatibility
            await self.broadcast_to_project(
                WebSocketChannelType.PROJECT_PROCESSING,
                event.project_id,
                {
                    "type": "processing_update",
                    "message": f"{event.current_step} ({event.progress_percentage:.1f}%)",
                    "progress_percentage": event.progress_percentage,
                    "event_id": event_id
                }
            )
    
    async def complete_operation_tracking(self, event_id: str, success: bool = True, 
                                         error_message: Optional[str] = None):
        """Complete operation tracking and broadcast completion"""
        event = self.progress_tracker.complete_operation(event_id, success, error_message)
        
        if event:
            # Broadcast completion to progress tracking channel
            await self.broadcast_to_project(
                WebSocketChannelType.PROGRESS_TRACKING,
                event.project_id,
                {
                    "type": "operation_completed",
                    "event_id": event_id,
                    "success": success,
                    "progress": event.to_dict()
                }
            )
            
            # Legacy compatibility broadcast
            await self.broadcast_to_project(
                WebSocketChannelType.PROJECT_PROCESSING,
                event.project_id,
                {
                    "type": "processing_complete",
                    "message": "Operation completed successfully" if success else f"Operation failed: {error_message}",
                    "success": success,
                    "event_id": event_id
                }
            )
    
    async def update_service_health_status(self, service_name: str, status: str, 
                                          response_time: Optional[float] = None, 
                                          metadata: Optional[Dict] = None):
        """Update service health and broadcast to health monitoring channel"""
        health_event = self.progress_tracker.update_service_health(
            service_name, status, response_time, metadata
        )
        
        # Broadcast to service health channel
        await self.broadcast_global(
            WebSocketChannelType.SERVICE_HEALTH,
            {
                "type": "service_health_update",
                "service_name": service_name,
                "health": health_event.to_dict()
            }
        )
    
    async def broadcast_analytics_summary(self):
        """Broadcast analytics summary to dashboard"""
        summary = self.progress_tracker.get_analytics_summary()
        
        await self.broadcast_global(
            WebSocketChannelType.DASHBOARD_STATS,
            {
                "type": "analytics_summary",
                "summary": summary
            }
        )
    
    def get_operation_status(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of an operation"""
        return self.progress_tracker.get_operation_status(event_id)
    
    def get_project_operations(self, project_id: str) -> List[Dict[str, Any]]:
        """Get all active operations for a project"""
        return self.progress_tracker.get_project_operations(project_id)
    
    def get_service_operations(self, service_name: str) -> List[Dict[str, Any]]:
        """Get all operations for a service"""
        return self.progress_tracker.get_service_operations(service_name)
    
    def get_recent_operation_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent operation history"""
        return self.progress_tracker.get_recent_history(limit)
    
    def get_analytics_summary(self) -> Dict[str, Any]:
        """Get analytics summary"""
        return self.progress_tracker.get_analytics_summary()
    
    def get_service_health_status(self) -> Dict[str, Any]:
        """Get current service health status"""
        return {
            service_name: health.to_dict() 
            for service_name, health in self.progress_tracker.service_health.items()
        }
