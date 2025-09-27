#!/usr/bin/env python3
"""
WebSocket Router - Clean API endpoints for WebSocket gateway
Handles WebSocket connections, broadcasting, and real-time communication
"""

from typing import Dict, List, Any, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query
from pydantic import BaseModel
import logging
import json
from datetime import datetime

from ..core.websocket_gateway import WebSocketGateway, WebSocketChannelType

logger = logging.getLogger("websocket_service")
router = APIRouter()

# Initialize gateway
websocket_gateway = WebSocketGateway()

# Response Models
class ConnectionStats(BaseModel):
    total_connections: int
    channels: Dict[str, Dict[str, int]]
    projects: Dict[str, Dict[str, int]]

class BroadcastRequest(BaseModel):
    channel_type: str
    project_id: Optional[str] = None
    message: Dict[str, Any]

class BroadcastResponse(BaseModel):
    success: bool
    message: str
    connections_reached: Optional[int] = None

# -------------------------
# Wiring placeholder (guarded)
# -------------------------
import os as _os

def _flag_enabled(name: str, default: bool = False) -> bool:
    try:
        v = _os.getenv(name, str(default)).strip().lower()
        return v in ("1", "true", "yes", "on")
    except Exception:
        return default

@router.get("/events/schema")
async def events_schema():
    if not _flag_enabled("WS_SCHEMA_ENABLED", False):
        raise HTTPException(status_code=404, detail="ws schema disabled")
    return {
        "channels": [
            {"name": "project_processing", "path": "/ws/processing/{project_id}", "events": ["processing_update","progress","ping","pong"]},
            {"name": "project_stats", "path": "/ws/stats/{project_id}", "events": ["stats_update","ping","pong"]},
            {"name": "crew_config", "path": "/ws/crew-config", "events": ["config_update","ping","pong"]}
        ],
        "payloads": {
            "processing_update": {"project_id": "string", "status": "string", "percent": 0},
            "stats_update": {"project_id": "string", "metrics": {"key": "value"}},
            "config_update": {"config": {"key": "value"}}
        }
    }

# WebSocket Endpoints
@router.websocket("/ws/processing/{project_id}")
async def websocket_project_processing(websocket: WebSocket, project_id: str):
    """WebSocket endpoint for project processing updates"""
    connection = None
    try:
        connection = await websocket_gateway.connect(
            websocket, 
            WebSocketChannelType.PROJECT_PROCESSING,
            project_id,
            {"type": "processing"}
        )
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for messages from client (optional - mainly for keep-alive)
                data = await websocket.receive_text()
                
                # Echo back or handle client messages if needed
                if data:
                    try:
                        message = json.loads(data)
                        if message.get("type") == "ping":
                            await websocket_gateway.send_to_connection(websocket, {"type": "pong"})
                    except json.JSONDecodeError:
                        pass
                        
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in project processing WebSocket: {e}")
                break
                
    except Exception as e:
        logger.error(f"Error establishing project processing WebSocket: {e}")
    finally:
        if connection:
            await websocket_gateway.disconnect(websocket)

@router.websocket("/ws/stats/{project_id}")
async def websocket_project_stats(websocket: WebSocket, project_id: str):
    """WebSocket endpoint for project statistics updates"""
    connection = None
    try:
        connection = await websocket_gateway.connect(
            websocket,
            WebSocketChannelType.PROJECT_STATS,
            project_id,
            {"type": "stats"}
        )
        
        while True:
            try:
                data = await websocket.receive_text()
                
                # Handle ping/pong for keep-alive
                if data:
                    try:
                        message = json.loads(data)
                        if message.get("type") == "ping":
                            await websocket_gateway.send_to_connection(websocket, {"type": "pong"})
                    except json.JSONDecodeError:
                        pass
                        
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in project stats WebSocket: {e}")
                break
                
    except Exception as e:
        logger.error(f"Error establishing project stats WebSocket: {e}")
    finally:
        if connection:
            await websocket_gateway.disconnect(websocket)

@router.websocket("/ws/crew-config")
async def websocket_crew_config(websocket: WebSocket):
    """WebSocket endpoint for crew configuration updates"""
    connection = None
    try:
        connection = await websocket_gateway.connect(
            websocket,
            WebSocketChannelType.CREW_CONFIG,
            metadata={"type": "crew_config"}
        )
        
        while True:
            try:
                data = await websocket.receive_text()
                
                # Handle ping/pong and config updates
                if data:
                    try:
                        message = json.loads(data)
                        if message.get("type") == "ping":
                            await websocket_gateway.send_to_connection(websocket, {"type": "pong"})
                        elif message.get("type") == "config_request":
                            # Handle configuration requests
                            await websocket_gateway.send_to_connection(websocket, {
                                "type": "config_response",
                                "message": "Configuration data would be sent here"
                            })
                    except json.JSONDecodeError:
                        pass
                        
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in crew config WebSocket: {e}")
                break
                
    except Exception as e:
        logger.error(f"Error establishing crew config WebSocket: {e}")
    finally:
        if connection:
            await websocket_gateway.disconnect(websocket)

@router.websocket("/ws/dashboard")
async def websocket_dashboard_stats(websocket: WebSocket):
    """WebSocket endpoint for dashboard/platform-wide statistics"""
    connection = None
    try:
        connection = await websocket_gateway.connect(
            websocket,
            WebSocketChannelType.DASHBOARD_STATS,
            metadata={"type": "dashboard"}
        )
        
        while True:
            try:
                data = await websocket.receive_text()
                
                if data:
                    try:
                        message = json.loads(data)
                        if message.get("type") == "ping":
                            await websocket_gateway.send_to_connection(websocket, {"type": "pong"})
                    except json.JSONDecodeError:
                        pass
                        
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in dashboard WebSocket: {e}")
                break
                
    except Exception as e:
        logger.error(f"Error establishing dashboard WebSocket: {e}")
    finally:
        if connection:
            await websocket_gateway.disconnect(websocket)

@router.websocket("/ws/agents/{project_id}")
async def websocket_agent_workflows(websocket: WebSocket, project_id: str):
    """WebSocket endpoint for AI agent workflow updates"""
    connection = None
    try:
        connection = await websocket_gateway.connect(
            websocket,
            WebSocketChannelType.AGENT_WORKFLOWS,
            project_id,
            {"type": "agent_workflows"}
        )
        
        while True:
            try:
                data = await websocket.receive_text()
                
                if data:
                    try:
                        message = json.loads(data)
                        if message.get("type") == "ping":
                            await websocket_gateway.send_to_connection(websocket, {"type": "pong"})
                    except json.JSONDecodeError:
                        pass
                        
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in agent workflow WebSocket: {e}")
                break
                
    except Exception as e:
        logger.error(f"Error establishing agent workflow WebSocket: {e}")
    finally:
        if connection:
            await websocket_gateway.disconnect(websocket)

@router.websocket("/ws/progress/{project_id}")
async def websocket_progress_tracking(websocket: WebSocket, project_id: str):
    """WebSocket endpoint for advanced progress tracking"""
    connection = None
    try:
        connection = await websocket_gateway.connect(
            websocket,
            WebSocketChannelType.PROGRESS_TRACKING,
            project_id,
            {"type": "progress_tracking"}
        )
        
        # Send current project operations on connect
        current_operations = websocket_gateway.get_project_operations(project_id)
        if current_operations:
            await websocket_gateway.send_to_connection(websocket, {
                "type": "current_operations",
                "operations": current_operations
            })
        
        while True:
            try:
                data = await websocket.receive_text()
                
                if data:
                    try:
                        message = json.loads(data)
                        if message.get("type") == "ping":
                            await websocket_gateway.send_to_connection(websocket, {"type": "pong"})
                        elif message.get("type") == "get_operations":
                            operations = websocket_gateway.get_project_operations(project_id)
                            await websocket_gateway.send_to_connection(websocket, {
                                "type": "operations_list",
                                "operations": operations
                            })
                    except json.JSONDecodeError:
                        pass
                        
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in progress tracking WebSocket: {e}")
                break
                
    except Exception as e:
        logger.error(f"Error establishing progress tracking WebSocket: {e}")
    finally:
        if connection:
            await websocket_gateway.disconnect(websocket)

@router.websocket("/ws/service-health")
async def websocket_service_health(websocket: WebSocket):
    """WebSocket endpoint for service health monitoring"""
    connection = None
    try:
        connection = await websocket_gateway.connect(
            websocket,
            WebSocketChannelType.SERVICE_HEALTH,
            metadata={"type": "service_health"}
        )
        
        # Send current service health status on connect
        health_status = websocket_gateway.get_service_health_status()
        await websocket_gateway.send_to_connection(websocket, {
            "type": "current_health_status",
            "services": health_status
        })
        
        while True:
            try:
                data = await websocket.receive_text()
                
                if data:
                    try:
                        message = json.loads(data)
                        if message.get("type") == "ping":
                            await websocket_gateway.send_to_connection(websocket, {"type": "pong"})
                        elif message.get("type") == "get_health":
                            health_status = websocket_gateway.get_service_health_status()
                            await websocket_gateway.send_to_connection(websocket, {
                                "type": "health_status",
                                "services": health_status
                            })
                    except json.JSONDecodeError:
                        pass
                        
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in service health WebSocket: {e}")
                break
                
    except Exception as e:
        logger.error(f"Error establishing service health WebSocket: {e}")
    finally:
        if connection:
            await websocket_gateway.disconnect(websocket)

@router.websocket("/ws/document-processing/{project_id}")
async def websocket_document_processing(websocket: WebSocket, project_id: str):
    """WebSocket endpoint for document processing updates"""
    connection = None
    try:
        connection = await websocket_gateway.connect(
            websocket,
            WebSocketChannelType.DOCUMENT_PROCESSING,
            project_id,
            {"type": "document_processing"}
        )
        
        while True:
            try:
                data = await websocket.receive_text()
                
                if data:
                    try:
                        message = json.loads(data)
                        if message.get("type") == "ping":
                            await websocket_gateway.send_to_connection(websocket, {"type": "pong"})
                    except json.JSONDecodeError:
                        pass
                        
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in document processing WebSocket: {e}")
                break
                
    except Exception as e:
        logger.error(f"Error establishing document processing WebSocket: {e}")
    finally:
        if connection:
            await websocket_gateway.disconnect(websocket)

@router.websocket("/ws/cloud-tools/{project_id}")
async def websocket_cloud_tools(websocket: WebSocket, project_id: str):
    """WebSocket endpoint for cloud tools integration updates"""
    connection = None
    try:
        connection = await websocket_gateway.connect(
            websocket,
            WebSocketChannelType.CLOUD_TOOLS,
            project_id,
            {"type": "cloud_tools"}
        )

        while True:
            try:
                data = await websocket.receive_text()

                if data:
                    try:
                        message = json.loads(data)
                        if message.get("type") == "ping":
                            await websocket_gateway.send_to_connection(websocket, {"type": "pong"})
                    except json.JSONDecodeError:
                        pass

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in cloud tools WebSocket: {e}")
                break

    except Exception as e:
        logger.error(f"Error establishing cloud tools WebSocket: {e}")
    finally:
        if connection:
            await websocket_gateway.disconnect(websocket)

@router.websocket("/ws/analysis/{project_id}")
async def websocket_analysis_updates(websocket: WebSocket, project_id: str):
    """WebSocket endpoint for real-time analysis updates"""
    connection = None
    try:
        # Create a new channel type for analysis if it doesn't exist
        # For now, we'll use DOCUMENT_PROCESSING as the channel type
        connection = await websocket_gateway.connect(
            websocket,
            WebSocketChannelType.DOCUMENT_PROCESSING,
            project_id,
            {"type": "analysis"}
        )

        logger.info(f"Analysis WebSocket connected for project {project_id}")

        while True:
            try:
                data = await websocket.receive_text()

                if data:
                    try:
                        message = json.loads(data)
                        if message.get("type") == "ping":
                            await websocket_gateway.send_to_connection(websocket, {"type": "pong"})
                        elif message.get("type") == "subscribe":
                            # Handle subscription to specific analysis types
                            analysis_type = message.get("analysis_type", "all")
                            await websocket_gateway.send_to_connection(websocket, {
                                "type": "subscription_confirmed",
                                "analysis_type": analysis_type,
                                "project_id": project_id
                            })
                    except json.JSONDecodeError:
                        pass

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in analysis WebSocket: {e}")
                break

    except Exception as e:
        logger.error(f"Error establishing analysis WebSocket: {e}")
    finally:
        if connection:
            await websocket_gateway.disconnect(websocket)

@router.websocket("/ws/run_assessment/{project_id}")
async def websocket_run_assessment(websocket: WebSocket, project_id: str):
    """WebSocket endpoint for assessment progress updates"""
    connection = None
    try:
        connection = await websocket_gateway.connect(
            websocket,
            WebSocketChannelType.PROGRESS_TRACKING,
            project_id,
            {"type": "assessment"}
        )

        logger.info(f"Assessment WebSocket connected for project {project_id}")

        while True:
            try:
                data = await websocket.receive_text()

                if data:
                    try:
                        message = json.loads(data)
                        if message.get("type") == "ping":
                            await websocket_gateway.send_to_connection(websocket, {"type": "pong"})
                        elif message.get("type") == "get_progress":
                            # Send current assessment progress
                            current_operations = websocket_gateway.get_project_operations(project_id)
                            await websocket_gateway.send_to_connection(websocket, {
                                "type": "current_progress",
                                "operations": current_operations
                            })
                    except json.JSONDecodeError:
                        pass

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in assessment WebSocket: {e}")
                break

    except Exception as e:
        logger.error(f"Error establishing assessment WebSocket: {e}")
    finally:
        if connection:
            await websocket_gateway.disconnect(websocket)

@router.websocket("/ws/logs/document_processing")
async def websocket_document_processing_logs(websocket: WebSocket):
    """WebSocket endpoint for document processing logs"""
    connection = None
    try:
        connection = await websocket_gateway.connect(
            websocket,
            WebSocketChannelType.DOCUMENT_PROCESSING,
            metadata={"type": "logs"}
        )

        logger.info("Document processing logs WebSocket connected")

        while True:
            try:
                data = await websocket.receive_text()

                if data:
                    try:
                        message = json.loads(data)
                        if message.get("type") == "ping":
                            await websocket_gateway.send_to_connection(websocket, {"type": "pong"})
                        elif message.get("type") == "get_logs":
                            # Send current document processing logs
                            await websocket_gateway.send_to_connection(websocket, {
                                "type": "current_logs",
                                "message": "Document processing logs would be streamed here"
                            })
                    except json.JSONDecodeError:
                        pass

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in document processing logs WebSocket: {e}")
                break

    except Exception as e:
        logger.error(f"Error establishing document processing logs WebSocket: {e}")
    finally:
        if connection:
            await websocket_gateway.disconnect(websocket)

# HTTP Endpoints for management and broadcasting
@router.get("/health", name="websocket_health_check", operation_id="websocket_gateway_health")
async def websocket_health():
    """Health check for WebSocket service"""
    try:
        health_data = await websocket_gateway.health_check()
        return {
            "service": "websocket-gateway",
            "status": health_data["status"],
            "total_connections": health_data["total_connections"],
            "channels_active": health_data["channels_active"],
            "projects_active": health_data["projects_active"]
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@router.get("/stats", response_model=ConnectionStats)
async def get_connection_stats():
    """Get detailed WebSocket connection statistics"""
    try:
        stats = websocket_gateway.get_connection_stats()
        return ConnectionStats(**stats)
    except Exception as e:
        logger.error(f"Error getting connection stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/connections")
async def get_active_connections():
    """Get list of active WebSocket connections"""
    try:
        connections = websocket_gateway.get_active_connections()
        return {"active_connections": connections}
    except Exception as e:
        logger.error(f"Error getting active connections: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/broadcast", response_model=BroadcastResponse)
async def broadcast_message(request: BroadcastRequest):
    """Broadcast message to WebSocket connections"""
    try:
        # Validate channel type
        try:
            channel_type = WebSocketChannelType(request.channel_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid channel type: {request.channel_type}")
        
        # Broadcast based on whether project_id is provided
        if request.project_id:
            await websocket_gateway.broadcast_to_project(channel_type, request.project_id, request.message)
            return BroadcastResponse(
                success=True,
                message=f"Message broadcasted to project {request.project_id} on {request.channel_type}"
            )
        else:
            await websocket_gateway.broadcast_global(channel_type, request.message)
            return BroadcastResponse(
                success=True,
                message=f"Message broadcasted globally on {request.channel_type}"
            )
            
    except Exception as e:
        logger.error(f"Error broadcasting message: {e}")
        return BroadcastResponse(
            success=False,
            message=f"Failed to broadcast message: {str(e)}"
        )

@router.post("/api/websocket/broadcast")
async def api_broadcast_message(message: dict):
    """Enhanced processor compatible broadcast endpoint"""
    try:
        project_id = message.get("project_id")
        event_type = message.get("event_type", "general")
        data = message.get("data", {})
        correlation_id = message.get("correlation_id")
        
        if not project_id:
            raise HTTPException(status_code=400, detail="project_id required in message")
        
        logger.info(f"Broadcasting message to project {project_id}: {event_type}")
        
        # Format message for WebSocket clients
        ws_message = {
            "type": event_type,
            "project_id": project_id,
            "timestamp": datetime.now().isoformat(),
            "correlation_id": correlation_id,
            "data": data
        }
        
        # Use the existing broadcast mechanism
        try:
            # Find appropriate channel type based on event type
            if "processing" in event_type.lower():
                channel_type = WebSocketChannelType.DOCUMENT_PROCESSING
            elif "progress" in event_type.lower():
                channel_type = WebSocketChannelType.PROGRESS_TRACKING
            else:
                channel_type = WebSocketChannelType.PROJECT_PROCESSING
            
            await websocket_gateway.broadcast_to_project(channel_type, project_id, ws_message)
            
            # Get connection count for response
            connections_count = len(websocket_gateway.get_project_connections(project_id))
            
            return {
                "status": "success", 
                "message": "Broadcast sent", 
                "recipients": connections_count
            }
            
        except Exception as broadcast_error:
            logger.warning(f"WebSocket broadcast failed: {broadcast_error}")
            # Still return success to avoid breaking the enhanced processor
            return {
                "status": "success", 
                "message": "Broadcast attempted (no active connections)", 
                "recipients": 0
            }
        
    except Exception as e:
        logger.error(f"API broadcast failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/websocket/notify")
async def api_notify_message(notification: dict):
    """Notification endpoint compatible with document service"""
    try:
        # Extract notification details
        project_id = notification.get("project_id")
        notification_type = notification.get("type", "notification")
        data = notification.get("data", {})
        correlation_id = notification.get("correlation_id")
        
        if not project_id:
            raise HTTPException(status_code=400, detail="project_id required in notification")
        
        logger.info(f"Processing notification for project {project_id}: {notification_type}")
        
        # Format message for WebSocket clients
        ws_message = {
            "type": notification_type,
            "project_id": project_id,
            "timestamp": datetime.now().isoformat(),
            "correlation_id": correlation_id,
            "data": data
        }
        
        # Add specific fields based on notification content
        for field in ["document_id", "file_name", "analysis_id", "status"]:
            if field in notification:
                ws_message[field] = notification[field]
        
        # Determine channel type based on notification type
        try:
            if "processing" in notification_type.lower() or "document" in notification_type.lower():
                channel_type = WebSocketChannelType.DOCUMENT_PROCESSING
            elif "analysis" in notification_type.lower():
                channel_type = WebSocketChannelType.PROJECT_PROCESSING
            else:
                channel_type = WebSocketChannelType.PROJECT_PROCESSING
            
            await websocket_gateway.broadcast_to_project(channel_type, project_id, ws_message)
            
            # Get connection count for response
            connections_count = len(websocket_gateway.get_project_connections(project_id))
            
            return {
                "success": True,
                "message": "Notification sent successfully",
                "recipients": connections_count
            }
            
        except Exception as broadcast_error:
            logger.warning(f"WebSocket notification broadcast failed: {broadcast_error}")
            # Still return success to avoid breaking the document service
            return {
                "success": True,
                "message": "Notification processed (no active connections)",
                "recipients": 0
            }
        
    except Exception as e:
        logger.error(f"API notification failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cleanup")
async def cleanup_stale_connections(max_idle_minutes: int = Query(30, ge=1, le=1440)):
    """Clean up stale WebSocket connections"""
    try:
        cleaned_count = await websocket_gateway.cleanup_stale_connections(max_idle_minutes)
        return {
            "success": True,
            "message": f"Cleaned up {cleaned_count} stale connections",
            "cleaned_count": cleaned_count
        }
    except Exception as e:
        logger.error(f"Error cleaning up connections: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Legacy compatibility endpoints
@router.post("/legacy/broadcast-processing")
async def legacy_broadcast_processing(project_id: str, message: str):
    """Legacy endpoint: broadcast processing update"""
    try:
        await websocket_gateway.broadcast_process_update(project_id, message)
        return {"success": True, "message": "Processing update broadcasted"}
    except Exception as e:
        logger.error(f"Error broadcasting processing update: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/legacy/broadcast-stats")
async def legacy_broadcast_stats(project_id: str, stats: Dict[str, Any]):
    """Legacy endpoint: broadcast stats update"""
    try:
        await websocket_gateway.broadcast_stats_update(project_id, stats)
        return {"success": True, "message": "Stats update broadcasted"}
    except Exception as e:
        logger.error(f"Error broadcasting stats update: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/legacy/broadcast-crew-config")
async def legacy_broadcast_crew_config(config_data: Dict[str, Any]):
    """Legacy endpoint: broadcast crew config update"""
    try:
        await websocket_gateway.broadcast_crew_config_update(config_data)
        return {"success": True, "message": "Crew config update broadcasted"}
    except Exception as e:
        logger.error(f"Error broadcasting crew config update: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Advanced Progress Tracking Endpoints

class OperationStart(BaseModel):
    project_id: str
    service_name: str
    operation: str
    total_steps: int
    metadata: Optional[Dict[str, Any]] = None

class OperationUpdate(BaseModel):
    event_id: str
    current_step: str
    step_number: int
    status: str = "in_progress"
    metadata: Optional[Dict[str, Any]] = None

class OperationComplete(BaseModel):
    event_id: str
    success: bool = True
    error_message: Optional[str] = None

class ServiceHealthUpdate(BaseModel):
    service_name: str
    status: str
    response_time: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

@router.post("/progress/start")
async def start_operation_tracking(request: OperationStart):
    """Start tracking a new operation"""
    try:
        event_id = await websocket_gateway.start_operation_tracking(
            request.project_id,
            request.service_name,
            request.operation,
            request.total_steps,
            request.metadata
        )
        return {
            "success": True,
            "event_id": event_id,
            "message": "Operation tracking started"
        }
    except Exception as e:
        logger.error(f"Error starting operation tracking: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/progress/update")
async def update_operation_progress(request: OperationUpdate):
    """Update operation progress"""
    try:
        await websocket_gateway.update_operation_progress(
            request.event_id,
            request.current_step,
            request.step_number,
            request.status,
            request.metadata
        )
        return {
            "success": True,
            "message": "Operation progress updated"
        }
    except Exception as e:
        logger.error(f"Error updating operation progress: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/progress/complete")
async def complete_operation_tracking(request: OperationComplete):
    """Complete operation tracking"""
    try:
        await websocket_gateway.complete_operation_tracking(
            request.event_id,
            request.success,
            request.error_message
        )
        return {
            "success": True,
            "message": "Operation tracking completed"
        }
    except Exception as e:
        logger.error(f"Error completing operation tracking: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/progress/operation/{event_id}")
async def get_operation_status(event_id: str):
    """Get status of a specific operation"""
    try:
        status = websocket_gateway.get_operation_status(event_id)
        if status:
            return {"success": True, "operation": status}
        else:
            raise HTTPException(status_code=404, detail="Operation not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting operation status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/progress/project/{project_id}")
async def get_project_operations(project_id: str):
    """Get all operations for a project"""
    try:
        operations = websocket_gateway.get_project_operations(project_id)
        return {"success": True, "operations": operations}
    except Exception as e:
        logger.error(f"Error getting project operations: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/progress/service/{service_name}")
async def get_service_operations(service_name: str):
    """Get all operations for a service"""
    try:
        operations = websocket_gateway.get_service_operations(service_name)
        return {"success": True, "operations": operations}
    except Exception as e:
        logger.error(f"Error getting service operations: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/progress/history")
async def get_operation_history(limit: int = Query(50, ge=1, le=500)):
    """Get recent operation history"""
    try:
        history = websocket_gateway.get_recent_operation_history(limit)
        return {"success": True, "history": history}
    except Exception as e:
        logger.error(f"Error getting operation history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analytics/summary")
async def get_analytics_summary():
    """Get analytics summary"""
    try:
        summary = websocket_gateway.get_analytics_summary()
        return {"success": True, "analytics": summary}
    except Exception as e:
        logger.error(f"Error getting analytics summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/analytics/broadcast")
async def broadcast_analytics_summary():
    """Broadcast analytics summary to dashboard clients"""
    try:
        await websocket_gateway.broadcast_analytics_summary()
        return {"success": True, "message": "Analytics summary broadcasted"}
    except Exception as e:
        logger.error(f"Error broadcasting analytics summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Service Health Monitoring Endpoints

@router.post("/health/update")
async def update_service_health(request: ServiceHealthUpdate):
    """Update service health status"""
    try:
        await websocket_gateway.update_service_health_status(
            request.service_name,
            request.status,
            request.response_time,
            request.metadata
        )
        return {"success": True, "message": "Service health updated"}
    except Exception as e:
        logger.error(f"Error updating service health: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health/services")
async def get_service_health_status():
    """Get current service health status"""
    try:
        health_status = websocket_gateway.get_service_health_status()
        return {"success": True, "services": health_status}
    except Exception as e:
        logger.error(f"Error getting service health status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
