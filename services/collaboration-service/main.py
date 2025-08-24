"""
Real-time Collaboration & Notification System

This service provides:
1. Real-time team collaboration features
2. Intelligent notification management
3. Activity feeds and timeline tracking
4. Team workspace management
5. Cross-service event aggregation
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager
from enum import Enum

import httpx
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class NotificationType(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"
    URGENT = "urgent"

class ActivityType(str, Enum):
    PROJECT_CREATED = "project_created"
    PROJECT_UPDATED = "project_updated"
    MIGRATION_STARTED = "migration_started"
    MIGRATION_COMPLETED = "migration_completed"
    DOCUMENT_UPLOADED = "document_uploaded"
    ANALYSIS_COMPLETED = "analysis_completed"
    USER_JOINED = "user_joined"
    COMMENT_ADDED = "comment_added"

@dataclass
class TeamMember:
    """Team member information"""
    user_id: str
    name: str
    email: str
    role: str
    is_online: bool = False
    last_seen: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if self.last_seen:
            data['last_seen'] = self.last_seen.isoformat()
        return data

@dataclass
class Workspace:
    """Team workspace"""
    workspace_id: str
    name: str
    description: str
    project_id: str
    members: List[TeamMember]
    created_at: datetime
    settings: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        data['members'] = [member.to_dict() for member in self.members]
        return data

@dataclass
class Activity:
    """Activity/event in the system"""
    activity_id: str
    workspace_id: str
    user_id: str
    activity_type: ActivityType
    title: str
    description: str
    metadata: Dict[str, Any]
    timestamp: datetime
    is_important: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data

@dataclass
class Notification:
    """Notification message"""
    notification_id: str
    user_id: str
    workspace_id: str
    notification_type: NotificationType
    title: str
    message: str
    created_at: datetime
    is_read: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        return data

class CollaborationManager:
    """Manages real-time collaboration and notifications"""
    
    def __init__(self):
        self.workspaces: Dict[str, Workspace] = {}
        self.activities: Dict[str, Activity] = {}
        self.notifications: Dict[str, Notification] = {}
        self.workspace_activities: Dict[str, List[str]] = {}
        self.user_notifications: Dict[str, List[str]] = {}
        self.active_connections: Dict[str, WebSocket] = {}
        
        self._initialize_sample_data()
        logger.info("Collaboration Manager initialized")
    
    def _initialize_sample_data(self):
        """Initialize with sample collaboration data"""
        workspace_id = str(uuid.uuid4())
        workspace = Workspace(
            workspace_id=workspace_id,
            name="Migration Project Alpha",
            description="Enterprise application migration to cloud",
            project_id="project_001",
            members=[
                TeamMember(
                    user_id="user_001",
                    name="John Smith",
                    email="john.smith@nagarro.com",
                    role="Project Manager",
                    is_online=True
                ),
                TeamMember(
                    user_id="user_002",
                    name="Sarah Johnson",
                    email="sarah.johnson@nagarro.com",
                    role="Migration Specialist"
                )
            ],
            created_at=datetime.now(),
            settings={"notifications_enabled": True}
        )
        
        self.workspaces[workspace_id] = workspace
        self.workspace_activities[workspace_id] = []
    
    async def create_workspace(self, name: str, description: str, project_id: str, creator_id: str) -> str:
        """Create new team workspace"""
        workspace_id = str(uuid.uuid4())
        
        workspace = Workspace(
            workspace_id=workspace_id,
            name=name,
            description=description,
            project_id=project_id,
            members=[],
            created_at=datetime.now(),
            settings={"notifications_enabled": True}
        )
        
        self.workspaces[workspace_id] = workspace
        self.workspace_activities[workspace_id] = []
        
        await self.add_activity(
            workspace_id, creator_id, ActivityType.PROJECT_CREATED,
            "Workspace Created", f"Team workspace '{name}' has been created",
            {"creator_id": creator_id}
        )
        
        logger.info(f"Created workspace {name} with ID {workspace_id}")
        return workspace_id
    
    async def add_activity(self, workspace_id: str, user_id: str, activity_type: ActivityType,
                          title: str, description: str, metadata: Dict[str, Any],
                          is_important: bool = False) -> str:
        """Add new activity to workspace"""
        activity_id = str(uuid.uuid4())
        
        activity = Activity(
            activity_id=activity_id,
            workspace_id=workspace_id,
            user_id=user_id,
            activity_type=activity_type,
            title=title,
            description=description,
            metadata=metadata,
            timestamp=datetime.now(),
            is_important=is_important
        )
        
        self.activities[activity_id] = activity
        
        if workspace_id not in self.workspace_activities:
            self.workspace_activities[workspace_id] = []
        self.workspace_activities[workspace_id].append(activity_id)
        
        logger.info(f"Added activity {title} to workspace {workspace_id}")
        return activity_id
    
    async def create_notification(self, user_id: str, workspace_id: str, 
                                 notification_type: NotificationType, title: str, 
                                 message: str) -> str:
        """Create notification for user"""
        notification_id = str(uuid.uuid4())
        
        notification = Notification(
            notification_id=notification_id,
            user_id=user_id,
            workspace_id=workspace_id,
            notification_type=notification_type,
            title=title,
            message=message,
            created_at=datetime.now()
        )
        
        self.notifications[notification_id] = notification
        
        if user_id not in self.user_notifications:
            self.user_notifications[user_id] = []
        self.user_notifications[user_id].append(notification_id)
        
        logger.info(f"Created notification {title} for user {user_id}")
        return notification_id
    
    async def connect_websocket(self, websocket: WebSocket, user_id: str):
        """Handle WebSocket connection"""
        connection_id = str(uuid.uuid4())
        
        await websocket.accept()
        self.active_connections[connection_id] = websocket
        
        try:
            while True:
                data = await websocket.receive_text()
                message = json.loads(data)
                if message.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                    
        except WebSocketDisconnect:
            if connection_id in self.active_connections:
                del self.active_connections[connection_id]
    
    def get_workspace(self, workspace_id: str) -> Optional[Workspace]:
        """Get workspace by ID"""
        return self.workspaces.get(workspace_id)
    
    def get_workspace_activities(self, workspace_id: str, limit: int = 50) -> List[Activity]:
        """Get activities for workspace"""
        activity_ids = self.workspace_activities.get(workspace_id, [])
        activities = [self.activities[aid] for aid in activity_ids if aid in self.activities]
        return sorted(activities, key=lambda x: x.timestamp, reverse=True)[:limit]
    
    def get_user_notifications(self, user_id: str, limit: int = 50) -> List[Notification]:
        """Get notifications for user"""
        notification_ids = self.user_notifications.get(user_id, [])
        notifications = [self.notifications[nid] for nid in notification_ids if nid in self.notifications]
        return sorted(notifications, key=lambda x: x.created_at, reverse=True)[:limit]

# Global collaboration manager
collaboration_manager = CollaborationManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    logger.info("Real-time Collaboration & Notification Service started successfully")
    yield
    logger.info("Real-time Collaboration & Notification Service shut down successfully")

# FastAPI app
app = FastAPI(
    title="Real-time Collaboration & Notification Service",
    description="Team collaboration and notification system for Nagarro Ascent Platform",
    version="3.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for API
class CreateWorkspaceRequest(BaseModel):
    name: str
    description: str
    project_id: str

class AddActivityRequest(BaseModel):
    activity_type: ActivityType
    title: str
    description: str
    metadata: Dict[str, Any] = {}
    is_important: bool = False

class CreateNotificationRequest(BaseModel):
    user_id: str
    notification_type: NotificationType
    title: str
    message: str

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str = "3.0.0"
    service: str = "collaboration-service"

# API Endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat()
    )

@app.post("/workspaces")
async def create_workspace(request: CreateWorkspaceRequest, creator_id: str = "default_user"):
    """Create new team workspace"""
    workspace_id = await collaboration_manager.create_workspace(
        request.name, request.description, request.project_id, creator_id
    )
    
    return {
        "workspace_id": workspace_id,
        "message": "Workspace created successfully"
    }

@app.get("/workspaces/{workspace_id}")
async def get_workspace(workspace_id: str):
    """Get workspace details"""
    workspace = collaboration_manager.get_workspace(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    return {"workspace": workspace.to_dict()}

@app.post("/workspaces/{workspace_id}/activities")
async def add_activity(workspace_id: str, request: AddActivityRequest, user_id: str = "default_user"):
    """Add activity to workspace"""
    activity_id = await collaboration_manager.add_activity(
        workspace_id, user_id, request.activity_type, request.title,
        request.description, request.metadata, request.is_important
    )
    
    return {
        "activity_id": activity_id,
        "message": "Activity added successfully"
    }

@app.get("/workspaces/{workspace_id}/activities")
async def get_workspace_activities(workspace_id: str, limit: int = 50):
    """Get workspace activities"""
    activities = collaboration_manager.get_workspace_activities(workspace_id, limit)
    
    return {
        "workspace_id": workspace_id,
        "activities": [activity.to_dict() for activity in activities],
        "total_activities": len(activities)
    }

@app.post("/workspaces/{workspace_id}/notifications")
async def create_notification(workspace_id: str, request: CreateNotificationRequest):
    """Create notification"""
    notification_id = await collaboration_manager.create_notification(
        request.user_id, workspace_id, request.notification_type,
        request.title, request.message
    )
    
    return {
        "notification_id": notification_id,
        "message": "Notification created successfully"
    }

@app.get("/users/{user_id}/notifications")
async def get_user_notifications(user_id: str, limit: int = 50):
    """Get user notifications"""
    notifications = collaboration_manager.get_user_notifications(user_id, limit)
    
    return {
        "user_id": user_id,
        "notifications": [notification.to_dict() for notification in notifications],
        "total_notifications": len(notifications)
    }

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """WebSocket endpoint for real-time communication"""
    await collaboration_manager.connect_websocket(websocket, user_id)

@app.get("/stats")
async def get_collaboration_stats():
    """Get collaboration statistics"""
    total_workspaces = len(collaboration_manager.workspaces)
    total_activities = len(collaboration_manager.activities)
    total_notifications = len(collaboration_manager.notifications)
    active_connections = len(collaboration_manager.active_connections)
    
    return {
        "total_workspaces": total_workspaces,
        "total_activities": total_activities,
        "total_notifications": total_notifications,
        "active_connections": active_connections
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8017,
        reload=True,
        log_level="info"
    )