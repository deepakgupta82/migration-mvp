"""
CrewAI Streaming Infrastructure
Provides real-time event processing and WebSocket broadcasting for granular CrewAI activities.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable, AsyncGenerator
from dataclasses import dataclass, asdict
from enum import Enum
import uuid

logger = logging.getLogger(__name__)

class CrewAIEventType(Enum):
    """Event types for CrewAI streaming"""
    CREW_START = "crew_start"
    CREW_COMPLETE = "crew_complete"
    CREW_ERROR = "crew_error"

    AGENT_SWITCH = "agent_switch"
    AGENT_START = "agent_start"
    AGENT_COMPLETE = "agent_complete"
    AGENT_ERROR = "agent_error"
    AGENT_REASONING = "agent_reasoning"

    TOOL_EXECUTION_START = "tool_execution_start"
    TOOL_EXECUTION_COMPLETE = "tool_execution_complete"
    TOOL_EXECUTION_ERROR = "tool_execution_error"

    TASK_START = "task_start"
    TASK_COMPLETE = "task_complete"
    TASK_ERROR = "task_error"

    PROGRESS_UPDATE = "progress_update"
    STATUS_UPDATE = "status_update"

@dataclass
class CrewAIEvent:
    """Represents a CrewAI streaming event"""
    event_id: str
    event_type: CrewAIEventType
    project_id: str
    correlation_id: str
    timestamp: datetime
    crew_id: Optional[str] = None
    agent_name: Optional[str] = None
    tool_name: Optional[str] = None
    task_name: Optional[str] = None
    data: Dict[str, Any] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.data is None:
            self.data = {}
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization"""
        result = asdict(self)
        result['event_type'] = self.event_type.value
        result['timestamp'] = self.timestamp.isoformat()
        return result

class TerminalFormatter:
    """Terminal-style message formatting with ANSI color codes"""

    # ANSI color codes
    COLORS = {
        'reset': '\033[0m',
        'black': '\033[30m',
        'red': '\033[31m',
        'green': '\033[32m',
        'yellow': '\033[33m',
        'blue': '\033[34m',
        'magenta': '\033[35m',
        'cyan': '\033[36m',
        'white': '\033[37m',
        'bright_red': '\033[91m',
        'bright_green': '\033[92m',
        'bright_yellow': '\033[93m',
        'bright_blue': '\033[94m',
        'bright_magenta': '\033[95m',
        'bright_cyan': '\033[96m',
    }

    PROGRESS_CHARS = {
        'start': '🚀',
        'complete': '✅',
        'error': '❌',
        'warning': '⚠️',
        'info': 'ℹ️',
        'agent': '🤖',
        'tool': '🔧',
        'task': '📋',
        'crew': '👥',
        'thinking': '💭',
        'processing': '⚙️'
    }

    @classmethod
    def format_event(cls, event: CrewAIEvent) -> str:
        """Format event as terminal-style message"""
        event_type = event.event_type
        timestamp = event.timestamp.strftime('%H:%M:%S')

        if event_type == CrewAIEventType.CREW_START:
            return f"{cls.PROGRESS_CHARS['start']} {cls.COLORS['bright_blue']}[{timestamp}] Crew '{event.crew_id}' started{cls.COLORS['reset']}"

        elif event_type == CrewAIEventType.CREW_COMPLETE:
            duration = event.data.get('duration_seconds', 0)
            return f"{cls.PROGRESS_CHARS['complete']} {cls.COLORS['bright_green']}[{timestamp}] Crew '{event.crew_id}' completed in {duration:.1f}s{cls.COLORS['reset']}"

        elif event_type == CrewAIEventType.CREW_ERROR:
            error = event.data.get('error', 'Unknown error')
            return f"{cls.PROGRESS_CHARS['error']} {cls.COLORS['bright_red']}[{timestamp}] Crew '{event.crew_id}' failed: {error}{cls.COLORS['reset']}"

        elif event_type == CrewAIEventType.AGENT_SWITCH:
            return f"{cls.PROGRESS_CHARS['agent']} {cls.COLORS['cyan']}[{timestamp}] Switching to agent: {event.agent_name}{cls.COLORS['reset']}"

        elif event_type == CrewAIEventType.AGENT_START:
            goal = event.data.get('goal', '')[:50]
            return f"{cls.PROGRESS_CHARS['agent']} {cls.COLORS['green']}[{timestamp}] Agent '{event.agent_name}' started: {goal}...{cls.COLORS['reset']}"

        elif event_type == CrewAIEventType.AGENT_COMPLETE:
            return f"{cls.PROGRESS_CHARS['complete']} {cls.COLORS['green']}[{timestamp}] Agent '{event.agent_name}' completed{cls.COLORS['reset']}"

        elif event_type == CrewAIEventType.AGENT_ERROR:
            error = event.data.get('error', 'Unknown error')
            return f"{cls.PROGRESS_CHARS['error']} {cls.COLORS['bright_red']}[{timestamp}] Agent '{event.agent_name}' error: {error}{cls.COLORS['reset']}"

        elif event_type == CrewAIEventType.AGENT_REASONING:
            thought = event.data.get('thought', '')[:100]
            return f"{cls.PROGRESS_CHARS['thinking']} {cls.COLORS['yellow']}[{timestamp}] {event.agent_name}: {thought}...{cls.COLORS['reset']}"

        elif event_type == CrewAIEventType.TOOL_EXECUTION_START:
            return f"{cls.PROGRESS_CHARS['tool']} {cls.COLORS['blue']}[{timestamp}] {event.agent_name} executing tool: {event.tool_name}{cls.COLORS['reset']}"

        elif event_type == CrewAIEventType.TOOL_EXECUTION_COMPLETE:
            return f"{cls.PROGRESS_CHARS['complete']} {cls.COLORS['green']}[{timestamp}] Tool '{event.tool_name}' completed{cls.COLORS['reset']}"

        elif event_type == CrewAIEventType.TOOL_EXECUTION_ERROR:
            error = event.data.get('error', 'Unknown error')
            return f"{cls.PROGRESS_CHARS['error']} {cls.COLORS['bright_red']}[{timestamp}] Tool '{event.tool_name}' failed: {error}{cls.COLORS['reset']}"

        elif event_type == CrewAIEventType.TASK_START:
            return f"{cls.PROGRESS_CHARS['task']} {cls.COLORS['magenta']}[{timestamp}] Task started: {event.task_name}{cls.COLORS['reset']}"

        elif event_type == CrewAIEventType.TASK_COMPLETE:
            return f"{cls.PROGRESS_CHARS['complete']} {cls.COLORS['green']}[{timestamp}] Task completed: {event.task_name}{cls.COLORS['reset']}"

        elif event_type == CrewAIEventType.PROGRESS_UPDATE:
            progress = event.data.get('progress_percentage', 0)
            current_step = event.data.get('current_step', '')
            progress_bar = cls._create_progress_bar(progress)
            return f"{cls.PROGRESS_CHARS['processing']} {cls.COLORS['cyan']}[{timestamp}] {progress_bar} {progress:.1f}% - {current_step}{cls.COLORS['reset']}"

        else:
            return f"{cls.PROGRESS_CHARS['info']} {cls.COLORS['white']}[{timestamp}] {event_type.value}: {event.data}{cls.COLORS['reset']}"

    @classmethod
    def _create_progress_bar(cls, percentage: float, width: int = 20) -> str:
        """Create a visual progress bar"""
        filled = int(width * percentage / 100)
        bar = '█' * filled + '░' * (width - filled)
        return f"[{bar}]"

class CrewAIStreamer:
    """
    Orchestrates real-time event processing for CrewAI activities.
    Handles event collection, processing, and broadcasting via WebSocket.
    """

    def __init__(self, websocket_url: str = "http://localhost:8009", auth_token: str = "service-backend-token"):
        self.websocket_url = websocket_url
        self.auth_token = auth_token
        self.event_handlers: Dict[CrewAIEventType, List[Callable]] = {}
        self.active_streams: Dict[str, Dict[str, Any]] = {}
        self.event_buffer: List[CrewAIEvent] = []
        self.buffer_size = 1000
        self.logger = logger

        # Initialize event handler lists
        for event_type in CrewAIEventType:
            self.event_handlers[event_type] = []

    def register_event_handler(self, event_type: CrewAIEventType, handler: Callable):
        """Register an event handler for a specific event type"""
        self.event_handlers[event_type].append(handler)
        self.logger.debug(f"Registered handler for {event_type.value}")

    def unregister_event_handler(self, event_type: CrewAIEventType, handler: Callable):
        """Unregister an event handler"""
        if handler in self.event_handlers[event_type]:
            self.event_handlers[event_type].remove(handler)
            self.logger.debug(f"Unregistered handler for {event_type.value}")

    async def emit_event(self, event: CrewAIEvent):
        """Emit an event to all registered handlers and WebSocket"""
        try:
            # Add to buffer for potential replay
            self.event_buffer.append(event)
            if len(self.event_buffer) > self.buffer_size:
                self.event_buffer.pop(0)

            # Call registered handlers
            for handler in self.event_handlers[event.event_type]:
                try:
                    await handler(event)
                except Exception as e:
                    self.logger.error(f"Event handler error: {e}")

            # Broadcast via WebSocket
            await self._broadcast_event(event)

            # Log formatted message
            formatted_message = TerminalFormatter.format_event(event)
            self.logger.info(formatted_message)

        except Exception as e:
            self.logger.error(f"Error emitting event {event.event_type.value}: {e}")

    def _create_event(self, event_type: CrewAIEventType, project_id: str, correlation_id: str,
                     crew_id: Optional[str] = None, agent_name: Optional[str] = None,
                     tool_name: Optional[str] = None, task_name: Optional[str] = None,
                     data: Optional[Dict[str, Any]] = None) -> CrewAIEvent:
        """Create a new CrewAIEvent"""
        return CrewAIEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            project_id=project_id,
            correlation_id=correlation_id,
            timestamp=datetime.now(),
            crew_id=crew_id,
            agent_name=agent_name,
            tool_name=tool_name,
            task_name=task_name,
            data=data or {}
        )

    async def _broadcast_event(self, event: CrewAIEvent):
        """Broadcast event via WebSocket service"""
        try:
            import httpx

            payload = {
                "project_id": event.project_id,
                "correlation_id": event.correlation_id,
                "event_type": "crewai_event",
                "timestamp": event.timestamp.isoformat(),
                "data": {
                    "event": event.to_dict(),
                    "formatted_message": TerminalFormatter.format_event(event)
                }
            }

            headers = {
                "Authorization": f"Bearer {self.auth_token}",
                "X-Correlation-ID": event.correlation_id,
                "Content-Type": "application/json"
            }

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    f"{self.websocket_url}/api/websocket/broadcast",
                    json=payload,
                    headers=headers
                )

                if response.status_code != 200:
                    self.logger.warning(f"WebSocket broadcast failed: {response.status_code}")

        except Exception as e:
            self.logger.debug(f"WebSocket broadcast error (non-critical): {e}")

    async def start_stream(self, project_id: str, correlation_id: str, crew_id: str) -> str:
        """Start a new streaming session"""
        stream_id = str(uuid.uuid4())

        self.active_streams[stream_id] = {
            "project_id": project_id,
            "correlation_id": correlation_id,
            "crew_id": crew_id,
            "started_at": datetime.now(),
            "event_count": 0,
            "status": "active"
        }

        # Emit crew start event
        start_event = CrewAIEvent(
            event_id=str(uuid.uuid4()),
            event_type=CrewAIEventType.CREW_START,
            project_id=project_id,
            correlation_id=correlation_id,
            timestamp=datetime.now(),
            crew_id=crew_id,
            data={"stream_id": stream_id}
        )

        await self.emit_event(start_event)

        self.logger.info(f"Started CrewAI stream {stream_id} for crew {crew_id}")
        return stream_id

    async def end_stream(self, stream_id: str, success: bool = True, error_message: Optional[str] = None):
        """End a streaming session"""
        if stream_id not in self.active_streams:
            self.logger.warning(f"Attempted to end unknown stream: {stream_id}")
            return

        stream_info = self.active_streams[stream_id]
        duration = (datetime.now() - stream_info["started_at"]).total_seconds()

        # Emit crew completion/error event
        event_type = CrewAIEventType.CREW_COMPLETE if success else CrewAIEventType.CREW_ERROR
        event_data = {
            "stream_id": stream_id,
            "duration_seconds": duration,
            "event_count": stream_info["event_count"]
        }

        if not success and error_message:
            event_data["error"] = error_message

        end_event = CrewAIEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            project_id=stream_info["project_id"],
            correlation_id=stream_info["correlation_id"],
            timestamp=datetime.now(),
            crew_id=stream_info["crew_id"],
            data=event_data
        )

        await self.emit_event(end_event)

        # Clean up
        stream_info["status"] = "completed" if success else "failed"
        stream_info["ended_at"] = datetime.now()
        stream_info["duration_seconds"] = duration

        self.logger.info(f"Ended CrewAI stream {stream_id} ({'success' if success else 'failed'})")

    async def emit_agent_event(self, stream_id: str, event_type: CrewAIEventType,
                              agent_name: str, **kwargs):
        """Emit an agent-related event"""
        if stream_id not in self.active_streams:
            return

        stream_info = self.active_streams[stream_id]
        stream_info["event_count"] += 1

        event = CrewAIEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            project_id=stream_info["project_id"],
            correlation_id=stream_info["correlation_id"],
            timestamp=datetime.now(),
            crew_id=stream_info["crew_id"],
            agent_name=agent_name,
            data=kwargs
        )

        await self.emit_event(event)

    async def emit_tool_event(self, stream_id: str, event_type: CrewAIEventType,
                             agent_name: str, tool_name: str, **kwargs):
        """Emit a tool-related event"""
        if stream_id not in self.active_streams:
            return

        stream_info = self.active_streams[stream_id]
        stream_info["event_count"] += 1

        event = CrewAIEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            project_id=stream_info["project_id"],
            correlation_id=stream_info["correlation_id"],
            timestamp=datetime.now(),
            crew_id=stream_info["crew_id"],
            agent_name=agent_name,
            tool_name=tool_name,
            data=kwargs
        )

        await self.emit_event(event)

    async def emit_progress_event(self, stream_id: str, progress_percentage: float,
                                 current_step: str, **kwargs):
        """Emit a progress update event"""
        if stream_id not in self.active_streams:
            return

        stream_info = self.active_streams[stream_id]
        stream_info["event_count"] += 1

        event = CrewAIEvent(
            event_id=str(uuid.uuid4()),
            event_type=CrewAIEventType.PROGRESS_UPDATE,
            project_id=stream_info["project_id"],
            correlation_id=stream_info["correlation_id"],
            timestamp=datetime.now(),
            crew_id=stream_info["crew_id"],
            data={
                "progress_percentage": progress_percentage,
                "current_step": current_step,
                **kwargs
            }
        )

        await self.emit_event(event)

    def get_stream_info(self, stream_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a streaming session"""
        return self.active_streams.get(stream_id)

    def get_active_streams(self) -> List[Dict[str, Any]]:
        """Get all active streaming sessions"""
        return [
            {**info, "stream_id": stream_id}
            for stream_id, info in self.active_streams.items()
            if info["status"] == "active"
        ]

    def get_event_history(self, stream_id: Optional[str] = None, limit: int = 100) -> List[CrewAIEvent]:
        """Get event history, optionally filtered by stream"""
        if stream_id:
            return [e for e in self.event_buffer if e.correlation_id == stream_id][-limit:]
        return self.event_buffer[-limit:]

    async def cleanup_inactive_streams(self, max_age_minutes: int = 60):
        """Clean up inactive streaming sessions"""
        cutoff_time = datetime.now().timestamp() - (max_age_minutes * 60)
        inactive_streams = []

        for stream_id, info in self.active_streams.items():
            if info["status"] != "active" and info.get("ended_at", datetime.min).timestamp() < cutoff_time:
                inactive_streams.append(stream_id)

        for stream_id in inactive_streams:
            del self.active_streams[stream_id]
            self.logger.debug(f"Cleaned up inactive stream: {stream_id}")

        return len(inactive_streams)

# Global streamer instance
crewai_streamer = CrewAIStreamer()