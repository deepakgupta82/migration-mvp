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
from dataclasses import dataclass, asdict, field
from contextlib import asynccontextmanager
from enum import Enum
from collections import defaultdict

import httpx
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks, UploadFile, File
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
    MENTION = "mention"
    TASK_ASSIGNED = "task_assigned"
    TASK_COMPLETED = "task_completed"
    FILE_SHARED = "file_shared"
    MEETING_INVITATION = "meeting_invitation"

class ActivityType(str, Enum):
    PROJECT_CREATED = "project_created"
    PROJECT_UPDATED = "project_updated"
    MIGRATION_STARTED = "migration_started"
    MIGRATION_COMPLETED = "migration_completed"
    DOCUMENT_UPLOADED = "document_uploaded"
    ANALYSIS_COMPLETED = "analysis_completed"
    USER_JOINED = "user_joined"
    COMMENT_ADDED = "comment_added"
    TASK_CREATED = "task_created"
    TASK_UPDATED = "task_updated"
    TASK_COMPLETED = "task_completed"
    FILE_SHARED = "file_shared"
    MEETING_SCHEDULED = "meeting_scheduled"
    MILESTONE_REACHED = "milestone_reached"

class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class MeetingStatus(str, Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class FileType(str, Enum):
    DOCUMENT = "document"
    IMAGE = "image"
    VIDEO = "video"
    ARCHIVE = "archive"
    OTHER = "other"

class NotificationChannel(str, Enum):
    IN_APP = "in_app"
    EMAIL = "email"
    WEBHOOK = "webhook"
    SLACK = "slack"
    TEAMS = "teams"

@dataclass
class TeamMember:
    """Team member information"""
    user_id: str
    name: str
    email: str
    role: str
    avatar_url: Optional[str] = None
    is_online: bool = False
    last_seen: Optional[datetime] = None
    skills: List[str] = field(default_factory=list)
    timezone: str = "UTC"
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if self.last_seen:
            data['last_seen'] = self.last_seen.isoformat()
        return data

@dataclass
class Task:
    """Task/todo item"""
    task_id: str
    workspace_id: str
    title: str
    description: str
    assignee_id: Optional[str]
    reporter_id: str
    status: TaskStatus
    priority: TaskPriority
    due_date: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    subtasks: List[str] = field(default_factory=list)  # task_ids
    dependencies: List[str] = field(default_factory=list)  # task_ids
    time_estimate_hours: Optional[float] = None
    time_spent_hours: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        if self.updated_at:
            data['updated_at'] = self.updated_at.isoformat()
        if self.completed_at:
            data['completed_at'] = self.completed_at.isoformat()
        if self.due_date:
            data['due_date'] = self.due_date.isoformat()
        return data

@dataclass
class SharedFile:
    """Shared file information"""
    file_id: str
    workspace_id: str
    filename: str
    file_type: FileType
    file_size: int
    uploader_id: str
    uploaded_at: datetime
    description: str = ""
    download_url: Optional[str] = None
    preview_url: Optional[str] = None
    version: int = 1
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['uploaded_at'] = self.uploaded_at.isoformat()
        return data

@dataclass
class Meeting:
    """Meeting/video call information"""
    meeting_id: str
    workspace_id: str
    title: str
    description: str
    organizer_id: str
    attendees: List[str]  # user_ids
    scheduled_start: datetime
    scheduled_end: datetime
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    status: MeetingStatus = MeetingStatus.SCHEDULED
    meeting_url: Optional[str] = None
    recording_url: Optional[str] = None
    agenda: List[str] = field(default_factory=list)
    notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['scheduled_start'] = self.scheduled_start.isoformat()
        data['scheduled_end'] = self.scheduled_end.isoformat()
        if self.actual_start:
            data['actual_start'] = self.actual_start.isoformat()
        if self.actual_end:
            data['actual_end'] = self.actual_end.isoformat()
        return data

@dataclass
class Comment:
    """Comment on activities, tasks, or resources"""
    comment_id: str
    workspace_id: str
    user_id: str
    resource_type: str  # "task", "activity", "file", etc.
    resource_id: str
    content: str
    mentions: List[str] = field(default_factory=list)  # mentioned user IDs
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    reactions: Dict[str, List[str]] = field(default_factory=dict)  # emoji -> user_ids
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if self.created_at:
            data['created_at'] = self.created_at.isoformat()
        if self.updated_at:
            data['updated_at'] = self.updated_at.isoformat()
        return data

@dataclass
class WorkspaceStats:
    """Workspace statistics and metrics"""
    total_members: int
    active_members: int
    total_tasks: int
    completed_tasks: int
    overdue_tasks: int
    total_files: int
    total_meetings: int
    total_comments: int
    activity_score: float  # 0-100
    last_activity: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if self.last_activity:
            data['last_activity'] = self.last_activity.isoformat()
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
    """Enhanced notification message with correlation ID"""
    notification_id: str
    user_id: str
    workspace_id: str
    notification_type: NotificationType
    title: str
    message: str
    created_at: datetime
    correlation_id: Optional[str] = None  # For tracking user actions
    metadata: Dict[str, Any] = field(default_factory=dict)
    channels: List[NotificationChannel] = field(default_factory=lambda: [NotificationChannel.IN_APP])
    is_read: bool = False
    read_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        if self.read_at:
            data['read_at'] = self.read_at.isoformat()
        return data

class CollaborationManager:
    """Manages comprehensive real-time collaboration and notifications"""
    
    def __init__(self):
        self.workspaces: Dict[str, Workspace] = {}
        self.activities: Dict[str, Activity] = {}
        self.notifications: Dict[str, Notification] = {}
        self.tasks: Dict[str, Task] = {}
        self.shared_files: Dict[str, SharedFile] = {}
        self.meetings: Dict[str, Meeting] = {}
        self.comments: Dict[str, Comment] = {}
        
        # Mapping dictionaries for efficient lookups
        self.workspace_activities: Dict[str, List[str]] = defaultdict(list)
        self.workspace_tasks: Dict[str, List[str]] = defaultdict(list)
        self.workspace_files: Dict[str, List[str]] = defaultdict(list)
        self.workspace_meetings: Dict[str, List[str]] = defaultdict(list)
        self.user_notifications: Dict[str, List[str]] = defaultdict(list)
        self.user_tasks: Dict[str, List[str]] = defaultdict(list)
        
        # Real-time connections
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_connections: Dict[str, Set[str]] = defaultdict(set)
        self.workspace_connections: Dict[str, Set[str]] = defaultdict(set)
        
        # Service URLs
        self.project_service_url = os.getenv("PROJECT_SERVICE_URL", "http://localhost:8010")
        self.storage_service_url = os.getenv("STORAGE_SERVICE_URL", "http://localhost:8004")
        self.websocket_url = os.getenv("WEBSOCKET_SERVICE_URL", "http://localhost:8009")
        
        self._initialize_sample_data()
        logger.info("Comprehensive Collaboration Manager initialized")
    
    def _initialize_sample_data(self):
        """Initialize with comprehensive sample collaboration data"""
        # Create sample workspace with enhanced features
        workspace_id = str(uuid.uuid4())
        workspace = Workspace(
            workspace_id=workspace_id,
            name="Migration Project Alpha",
            description="Enterprise application migration to cloud with comprehensive collaboration",
            project_id="project_001",
            members=[
                TeamMember(
                    user_id="user_001",
                    name="John Smith",
                    email="john.smith@nagarro.com",
                    role="Project Manager",
                    is_online=True,
                    skills=["Project Management", "Agile", "Cloud Migration"],
                    timezone="EST"
                ),
                TeamMember(
                    user_id="user_002",
                    name="Sarah Johnson",
                    email="sarah.johnson@nagarro.com",
                    role="Migration Specialist",
                    skills=["AWS", "Azure", "Database Migration"],
                    timezone="PST"
                ),
                TeamMember(
                    user_id="user_003",
                    name="Mike Chen",
                    email="mike.chen@nagarro.com",
                    role="Cloud Architect",
                    skills=["Architecture Design", "Security", "DevOps"],
                    timezone="EST"
                )
            ],
            created_at=datetime.now(),
            settings={
                "notifications_enabled": True,
                "task_notifications": True,
                "meeting_reminders": True,
                "file_sharing_enabled": True,
                "allow_external_guests": False
            }
        )
        
        self.workspaces[workspace_id] = workspace
        
        # Create sample tasks
        sample_tasks = [
            {
                "title": "Complete Infrastructure Assessment",
                "description": "Assess current infrastructure and dependencies",
                "assignee_id": "user_002",
                "reporter_id": "user_001",
                "priority": TaskPriority.HIGH,
                "status": TaskStatus.IN_PROGRESS,
                "due_date": datetime.now() + timedelta(days=7),
                "tags": ["assessment", "infrastructure"]
            },
            {
                "title": "Design Target Architecture",
                "description": "Design cloud target architecture with security considerations",
                "assignee_id": "user_003",
                "reporter_id": "user_001",
                "priority": TaskPriority.HIGH,
                "status": TaskStatus.TODO,
                "due_date": datetime.now() + timedelta(days=14),
                "tags": ["architecture", "design"]
            },
            {
                "title": "Prepare Migration Plan",
                "description": "Create detailed migration execution plan",
                "assignee_id": "user_002",
                "reporter_id": "user_001",
                "priority": TaskPriority.MEDIUM,
                "status": TaskStatus.TODO,
                "due_date": datetime.now() + timedelta(days=21),
                "tags": ["planning", "execution"]
            }
        ]
        
        for task_data in sample_tasks:
            task_id = str(uuid.uuid4())
            task = Task(
                task_id=task_id,
                workspace_id=workspace_id,
                title=task_data["title"],
                description=task_data["description"],
                assignee_id=task_data["assignee_id"],
                reporter_id=task_data["reporter_id"],
                status=task_data["status"],
                priority=task_data["priority"],
                due_date=task_data["due_date"],
                created_at=datetime.now(),
                tags=task_data["tags"]
            )
            
            self.tasks[task_id] = task
            self.workspace_tasks[workspace_id].append(task_id)
            self.user_tasks[task_data["assignee_id"]].append(task_id)
        
        # Create sample meetings
        meeting_id = str(uuid.uuid4())
        meeting = Meeting(
            meeting_id=meeting_id,
            workspace_id=workspace_id,
            title="Weekly Project Sync",
            description="Weekly synchronization meeting for project progress",
            organizer_id="user_001",
            attendees=["user_001", "user_002", "user_003"],
            scheduled_start=datetime.now() + timedelta(hours=24),
            scheduled_end=datetime.now() + timedelta(hours=25),
            agenda=["Project status review", "Upcoming deliverables", "Risk assessment"]
        )
        
        self.meetings[meeting_id] = meeting
        self.workspace_meetings[workspace_id].append(meeting_id)
    
    async def create_task(self, workspace_id: str, title: str, description: str, 
                         assignee_id: Optional[str], reporter_id: str, priority: TaskPriority,
                         due_date: Optional[datetime] = None, tags: List[str] = None) -> str:
        """Create new task"""
        task_id = str(uuid.uuid4())
        
        task = Task(
            task_id=task_id,
            workspace_id=workspace_id,
            title=title,
            description=description,
            assignee_id=assignee_id,
            reporter_id=reporter_id,
            status=TaskStatus.TODO,
            priority=priority,
            due_date=due_date,
            created_at=datetime.now(),
            tags=tags or []
        )
        
        self.tasks[task_id] = task
        self.workspace_tasks[workspace_id].append(task_id)
        
        if assignee_id:
            self.user_tasks[assignee_id].append(task_id)
            
            # Create notification for assignee
            await self.create_notification(
                assignee_id, workspace_id, NotificationType.TASK_ASSIGNED,
                "New Task Assigned", f"You have been assigned task: {title}",
                correlation_id=str(uuid.uuid4()),
                metadata={"task_id": task_id, "reporter_id": reporter_id}
            )
        
        # Create activity
        await self.add_activity(
            workspace_id, reporter_id, ActivityType.TASK_CREATED,
            "Task Created", f"Task '{title}' has been created",
            {"task_id": task_id, "assignee_id": assignee_id}
        )
        
        # Broadcast real-time update
        await self._broadcast_to_workspace(workspace_id, {
            "type": "task_created",
            "task": task.to_dict()
        })
        
        logger.info(f"Created task '{title}' in workspace {workspace_id}")
        return task_id
    
    async def update_task_status(self, task_id: str, status: TaskStatus, user_id: str) -> bool:
        """Update task status"""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        old_status = task.status
        task.status = status
        task.updated_at = datetime.now()
        
        if status == TaskStatus.COMPLETED:
            task.completed_at = datetime.now()
            
            # Notify reporter if different from assignee
            if task.reporter_id != user_id:
                await self.create_notification(
                    task.reporter_id, task.workspace_id, NotificationType.TASK_COMPLETED,
                    "Task Completed", f"Task '{task.title}' has been completed",
                    correlation_id=str(uuid.uuid4()),
                    metadata={"task_id": task_id, "completed_by": user_id}
                )
        
        # Create activity
        await self.add_activity(
            task.workspace_id, user_id, ActivityType.TASK_UPDATED,
            "Task Status Updated", f"Task '{task.title}' status changed from {old_status} to {status}",
            {"task_id": task_id, "old_status": old_status, "new_status": status}
        )
        
        # Broadcast real-time update
        await self._broadcast_to_workspace(task.workspace_id, {
            "type": "task_updated",
            "task": task.to_dict()
        })
        
        return True
    
    async def schedule_meeting(self, workspace_id: str, title: str, description: str,
                              organizer_id: str, attendees: List[str], 
                              start_time: datetime, end_time: datetime,
                              agenda: List[str] = None) -> str:
        """Schedule new meeting"""
        meeting_id = str(uuid.uuid4())
        
        meeting = Meeting(
            meeting_id=meeting_id,
            workspace_id=workspace_id,
            title=title,
            description=description,
            organizer_id=organizer_id,
            attendees=attendees,
            scheduled_start=start_time,
            scheduled_end=end_time,
            agenda=agenda or []
        )
        
        self.meetings[meeting_id] = meeting
        self.workspace_meetings[workspace_id].append(meeting_id)
        
        # Notify all attendees
        for attendee_id in attendees:
            if attendee_id != organizer_id:
                await self.create_notification(
                    attendee_id, workspace_id, NotificationType.MEETING_INVITATION,
                    "Meeting Invitation", f"You're invited to meeting: {title}",
                    correlation_id=str(uuid.uuid4()),
                    metadata={"meeting_id": meeting_id, "organizer_id": organizer_id}
                )
        
        # Create activity
        await self.add_activity(
            workspace_id, organizer_id, ActivityType.MEETING_SCHEDULED,
            "Meeting Scheduled", f"Meeting '{title}' has been scheduled",
            {"meeting_id": meeting_id, "attendees_count": len(attendees)}
        )
        
        logger.info(f"Scheduled meeting '{title}' in workspace {workspace_id}")
        return meeting_id
    
    async def share_file(self, workspace_id: str, file: UploadFile, uploader_id: str,
                        description: str = "", tags: List[str] = None) -> str:
        """Share file in workspace"""
        file_id = str(uuid.uuid4())
        
        # Determine file type
        file_type = self._get_file_type(file.filename)
        
        # In a real implementation, upload to storage service
        download_url = f"http://localhost:8004/files/{file_id}/{file.filename}"
        
        shared_file = SharedFile(
            file_id=file_id,
            workspace_id=workspace_id,
            filename=file.filename,
            file_type=file_type,
            file_size=file.size or 0,
            uploader_id=uploader_id,
            uploaded_at=datetime.now(),
            description=description,
            download_url=download_url,
            tags=tags or []
        )
        
        self.shared_files[file_id] = shared_file
        self.workspace_files[workspace_id].append(file_id)
        
        # Create activity
        await self.add_activity(
            workspace_id, uploader_id, ActivityType.FILE_SHARED,
            "File Shared", f"File '{file.filename}' has been shared",
            {"file_id": file_id, "file_type": file_type, "file_size": file.size or 0}
        )
        
        # Broadcast real-time update
        await self._broadcast_to_workspace(workspace_id, {
            "type": "file_shared",
            "file": shared_file.to_dict()
        })
        
        logger.info(f"Shared file '{file.filename}' in workspace {workspace_id}")
        return file_id
    
    def _get_file_type(self, filename: str) -> FileType:
        """Determine file type from filename"""
        extension = filename.lower().split('.')[-1] if '.' in filename else ''
        
        if extension in ['pdf', 'doc', 'docx', 'txt', 'md']:
            return FileType.DOCUMENT
        elif extension in ['jpg', 'jpeg', 'png', 'gif', 'svg']:
            return FileType.IMAGE
        elif extension in ['mp4', 'avi', 'mov', 'wmv']:
            return FileType.VIDEO
        elif extension in ['zip', 'tar', 'gz', 'rar']:
            return FileType.ARCHIVE
        else:
            return FileType.OTHER
    
    async def add_comment(self, workspace_id: str, user_id: str, resource_type: str,
                         resource_id: str, content: str, mentions: List[str] = None) -> str:
        """Add comment to resource"""
        comment_id = str(uuid.uuid4())
        
        comment = Comment(
            comment_id=comment_id,
            workspace_id=workspace_id,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            content=content,
            mentions=mentions or [],
            created_at=datetime.now()
        )
        
        self.comments[comment_id] = comment
        
        # Notify mentioned users
        for mentioned_user in mentions or []:
            await self.create_notification(
                mentioned_user, workspace_id, NotificationType.MENTION,
                "You were mentioned", f"You were mentioned in a comment on {resource_type}",
                correlation_id=str(uuid.uuid4()),
                metadata={"comment_id": comment_id, "resource_type": resource_type}
            )
        
        # Create activity
        await self.add_activity(
            workspace_id, user_id, ActivityType.COMMENT_ADDED,
            "Comment Added", f"New comment on {resource_type}",
            {"comment_id": comment_id, "resource_type": resource_type, "mentions_count": len(mentions or [])}
        )
        
        return comment_id
    
    def get_workspace_stats(self, workspace_id: str) -> Optional[WorkspaceStats]:
        """Get comprehensive workspace statistics"""
        workspace = self.workspaces.get(workspace_id)
        if not workspace:
            return None
        
        # Calculate statistics
        total_members = len(workspace.members)
        active_members = len([m for m in workspace.members if m.is_online])
        
        workspace_tasks = [self.tasks[tid] for tid in self.workspace_tasks[workspace_id] if tid in self.tasks]
        total_tasks = len(workspace_tasks)
        completed_tasks = len([t for t in workspace_tasks if t.status == TaskStatus.COMPLETED])
        overdue_tasks = len([t for t in workspace_tasks if t.due_date and t.due_date < datetime.now() and t.status != TaskStatus.COMPLETED])
        
        total_files = len(self.workspace_files[workspace_id])
        total_meetings = len(self.workspace_meetings[workspace_id])
        
        # Count comments in this workspace
        total_comments = len([c for c in self.comments.values() if c.workspace_id == workspace_id])
        
        # Calculate activity score (0-100) based on recent activity
        recent_activities = self.get_workspace_activities(workspace_id, limit=50)
        activity_score = min(100, len(recent_activities) * 2)  # Simple scoring
        
        last_activity_time = None
        if recent_activities:
            last_activity_time = recent_activities[0].timestamp
        
        return WorkspaceStats(
            total_members=total_members,
            active_members=active_members,
            total_tasks=total_tasks,
            completed_tasks=completed_tasks,
            overdue_tasks=overdue_tasks,
            total_files=total_files,
            total_meetings=total_meetings,
            total_comments=total_comments,
            activity_score=activity_score,
            last_activity=last_activity_time
        )
    
    async def create_notification(self, user_id: str, workspace_id: str, 
                                 notification_type: NotificationType, title: str, 
                                 message: str, correlation_id: Optional[str] = None,
                                 metadata: Dict[str, Any] = None,
                                 channels: List[NotificationChannel] = None) -> str:
        """Create enhanced notification with correlation ID for tracking"""
        notification_id = str(uuid.uuid4())
        
        notification = Notification(
            notification_id=notification_id,
            user_id=user_id,
            workspace_id=workspace_id,
            notification_type=notification_type,
            title=title,
            message=message,
            created_at=datetime.now(),
            correlation_id=correlation_id,
            metadata=metadata or {},
            channels=channels or [NotificationChannel.IN_APP]
        )
        
        self.notifications[notification_id] = notification
        self.user_notifications[user_id].append(notification_id)
        
        # Send notification via requested channels
        await self._send_notification_via_channels(notification)
        
        # Broadcast real-time update
        await self._broadcast_to_user(user_id, {
            "type": "notification_received",
            "notification": notification.to_dict()
        })
        
        logger.info(f"Created notification '{title}' for user {user_id} (correlation: {correlation_id})")
        return notification_id
    
    async def _send_notification_via_channels(self, notification: Notification):
        """Send notification via specified channels"""
        for channel in notification.channels:
            try:
                if channel == NotificationChannel.IN_APP:
                    # Already handled by broadcast
                    pass
                elif channel == NotificationChannel.EMAIL:
                    # Simulate email sending
                    logger.info(f"Email notification sent to user {notification.user_id}")
                elif channel == NotificationChannel.WEBHOOK:
                    # Simulate webhook call
                    await self._send_webhook_notification(notification)
                # Add other channel implementations
            except Exception as e:
                logger.error(f"Failed to send notification via {channel}: {e}")
    
    async def _send_webhook_notification(self, notification: Notification):
        """Send webhook notification"""
        webhook_url = os.getenv("NOTIFICATION_WEBHOOK_URL")
        if webhook_url:
            async with httpx.AsyncClient() as client:
                await client.post(webhook_url, json=notification.to_dict())
    
    async def mark_notification_read(self, notification_id: str) -> bool:
        """Mark notification as read"""
        if notification_id not in self.notifications:
            return False
        
        notification = self.notifications[notification_id]
        notification.is_read = True
        notification.read_at = datetime.now()
        
        return True
    
    async def _broadcast_to_workspace(self, workspace_id: str, message: Dict[str, Any]):
        """Broadcast message to all workspace members"""
        connections_to_remove = []
        
        for connection_id in self.workspace_connections[workspace_id]:
            if connection_id in self.active_connections:
                try:
                    await self.active_connections[connection_id].send_text(json.dumps(message))
                except:
                    connections_to_remove.append(connection_id)
        
        # Clean up dead connections
        for conn_id in connections_to_remove:
            self.workspace_connections[workspace_id].discard(conn_id)
            if conn_id in self.active_connections:
                del self.active_connections[conn_id]
    
    async def _broadcast_to_user(self, user_id: str, message: Dict[str, Any]):
        """Broadcast message to specific user"""
        connections_to_remove = []
        
        for connection_id in self.user_connections[user_id]:
            if connection_id in self.active_connections:
                try:
                    await self.active_connections[connection_id].send_text(json.dumps(message))
                except:
                    connections_to_remove.append(connection_id)
        
        # Clean up dead connections
        for conn_id in connections_to_remove:
            self.user_connections[user_id].discard(conn_id)
            if conn_id in self.active_connections:
                del self.active_connections[conn_id]
    
    def get_user_tasks(self, user_id: str, status_filter: Optional[TaskStatus] = None) -> List[Task]:
        """Get tasks assigned to user"""
        task_ids = self.user_tasks[user_id]
        tasks = [self.tasks[tid] for tid in task_ids if tid in self.tasks]
        
        if status_filter:
            tasks = [t for t in tasks if t.status == status_filter]
        
        return sorted(tasks, key=lambda x: x.due_date or datetime.max)
    
    def get_workspace_tasks(self, workspace_id: str, status_filter: Optional[TaskStatus] = None) -> List[Task]:
        """Get tasks in workspace"""
        task_ids = self.workspace_tasks[workspace_id]
        tasks = [self.tasks[tid] for tid in task_ids if tid in self.tasks]
        
        if status_filter:
            tasks = [t for t in tasks if t.status == status_filter]
        
        return sorted(tasks, key=lambda x: x.due_date or datetime.max)
    
    def get_workspace_files(self, workspace_id: str) -> List[SharedFile]:
        """Get files shared in workspace"""
        file_ids = self.workspace_files[workspace_id]
        files = [self.shared_files[fid] for fid in file_ids if fid in self.shared_files]
        return sorted(files, key=lambda x: x.uploaded_at, reverse=True)
    
    def get_workspace_meetings(self, workspace_id: str, upcoming_only: bool = False) -> List[Meeting]:
        """Get meetings in workspace"""
        meeting_ids = self.workspace_meetings[workspace_id]
        meetings = [self.meetings[mid] for mid in meeting_ids if mid in self.meetings]
        
        if upcoming_only:
            now = datetime.now()
            meetings = [m for m in meetings if m.scheduled_start > now]
        
        return sorted(meetings, key=lambda x: x.scheduled_start)
    
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