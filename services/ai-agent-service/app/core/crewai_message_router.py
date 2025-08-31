"""
CrewAI Message Router for WebSocket message routing and broadcasting.
Handles routing of CrewAI events to appropriate WebSocket channels and clients.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable, Set
from dataclasses import dataclass, asdict
from enum import Enum

from .crewai_streamer import CrewAIEvent, CrewAIEventType, TerminalFormatter

logger = logging.getLogger(__name__)

class MessagePriority(Enum):
    """Message priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"

class MessageChannel(Enum):
    """Available message channels"""
    CREW_EVENTS = "crew_events"
    AGENT_ACTIVITY = "agent_activity"
    TOOL_EXECUTIONS = "tool_executions"
    PROGRESS_UPDATES = "progress_updates"
    SYSTEM_NOTIFICATIONS = "system_notifications"
    ERROR_ALERTS = "error_alerts"

@dataclass
class RoutedMessage:
    """Represents a message to be routed"""
    message_id: str
    channel: MessageChannel
    priority: MessagePriority
    project_id: str
    correlation_id: str
    payload: Dict[str, Any]
    timestamp: datetime
    source: str
    target_clients: Optional[Set[str]] = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.target_clients is None:
            self.target_clients = set()
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary"""
        result = asdict(self)
        result['channel'] = self.channel.value
        result['priority'] = self.priority.value
        result['timestamp'] = self.timestamp.isoformat()
        return result

class MessageFilter:
    """Filter for routing messages based on criteria"""

    def __init__(self,
                 project_ids: Optional[Set[str]] = None,
                 correlation_ids: Optional[Set[str]] = None,
                 channels: Optional[Set[MessageChannel]] = None,
                 priorities: Optional[Set[MessagePriority]] = None,
                 event_types: Optional[Set[CrewAIEventType]] = None):
        self.project_ids = project_ids or set()
        self.correlation_ids = correlation_ids or set()
        self.channels = channels or set()
        self.priorities = priorities or set()
        self.event_types = event_types or set()

    def matches(self, message: RoutedMessage, event: Optional[CrewAIEvent] = None) -> bool:
        """Check if message matches filter criteria"""
        # Check project ID
        if self.project_ids and message.project_id not in self.project_ids:
            return False

        # Check correlation ID
        if self.correlation_ids and message.correlation_id not in self.correlation_ids:
            return False

        # Check channel
        if self.channels and message.channel not in self.channels:
            return False

        # Check priority
        if self.priorities and message.priority not in self.priorities:
            return False

        # Check event type if event is provided
        if event and self.event_types and event.event_type not in self.event_types:
            return False

        return True

class MessageTransformer:
    """Transforms messages for different output formats"""

    @staticmethod
    def to_websocket_format(message: RoutedMessage) -> Dict[str, Any]:
        """Transform message to WebSocket broadcast format"""
        return {
            "type": "crewai_message",
            "message_id": message.message_id,
            "channel": message.channel.value,
            "priority": message.priority.value,
            "project_id": message.project_id,
            "correlation_id": message.correlation_id,
            "payload": message.payload,
            "timestamp": message.timestamp.isoformat(),
            "source": message.source
        }

    @staticmethod
    def to_terminal_format(message: RoutedMessage, event: Optional[CrewAIEvent] = None) -> str:
        """Transform message to terminal display format"""
        if event:
            return TerminalFormatter.format_event(event)

        # Fallback formatting for non-event messages
        priority_emoji = {
            MessagePriority.LOW: "📝",
            MessagePriority.NORMAL: "💬",
            MessagePriority.HIGH: "⚡",
            MessagePriority.CRITICAL: "🚨"
        }.get(message.priority, "💬")

        channel_name = message.channel.value.replace("_", " ").title()
        return f"{priority_emoji} [{message.timestamp.strftime('%H:%M:%S')}] {channel_name}: {message.payload.get('message', 'No message')}"

    @staticmethod
    def to_log_format(message: RoutedMessage) -> str:
        """Transform message to log format"""
        return f"[{message.priority.value.upper()}] {message.channel.value}: {message.payload}"

class CrewAIMessageRouter:
    """
    Routes CrewAI messages to appropriate WebSocket channels and clients.
    Handles message filtering, transformation, and broadcasting.
    """

    def __init__(self, websocket_url: str = "http://localhost:8009"):
        self.websocket_url = websocket_url
        self.auth_token = "service-backend-token"
        self.message_handlers: Dict[MessageChannel, List[Callable]] = {}
        self.filters: List[MessageFilter] = []
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.is_routing = False

        # Initialize message handlers
        for channel in MessageChannel:
            self.message_handlers[channel] = []

        # Start message processing
        self.processing_task = None

    async def start_routing(self):
        """Start the message routing process"""
        if self.is_routing:
            return

        self.is_routing = True
        self.processing_task = asyncio.create_task(self._process_message_queue())
        logger.info("CrewAI Message Router started")

    async def stop_routing(self):
        """Stop the message routing process"""
        self.is_routing = False
        if self.processing_task:
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass
        logger.info("CrewAI Message Router stopped")

    def register_handler(self, channel: MessageChannel, handler: Callable):
        """Register a message handler for a specific channel"""
        self.message_handlers[channel].append(handler)
        logger.debug(f"Registered handler for channel: {channel.value}")

    def unregister_handler(self, channel: MessageChannel, handler: Callable):
        """Unregister a message handler"""
        if handler in self.message_handlers[channel]:
            self.message_handlers[channel].remove(handler)
            logger.debug(f"Unregistered handler for channel: {channel.value}")

    def add_filter(self, filter_obj: MessageFilter):
        """Add a message filter"""
        self.filters.append(filter_obj)
        logger.debug("Added message filter")

    def remove_filter(self, filter_obj: MessageFilter):
        """Remove a message filter"""
        if filter_obj in self.filters:
            self.filters.remove(filter_obj)
            logger.debug("Removed message filter")

    async def route_event(self, event: CrewAIEvent):
        """Route a CrewAI event to appropriate channels"""
        try:
            # Determine channel and priority based on event type
            channel, priority = self._determine_channel_and_priority(event)

            # Create routed message
            message = RoutedMessage(
                message_id=f"msg_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
                channel=channel,
                priority=priority,
                project_id=event.project_id,
                correlation_id=event.correlation_id,
                payload={
                    "event": event.to_dict(),
                    "formatted_message": TerminalFormatter.format_event(event)
                },
                timestamp=datetime.now(),
                source="crewai_router",
                metadata={"event_type": event.event_type.value}
            )

            # Add to queue for processing
            await self.message_queue.put((message, event))

        except Exception as e:
            logger.error(f"Error routing event {event.event_type.value}: {e}")

    async def route_message(self, channel: MessageChannel, priority: MessagePriority,
                           project_id: str, correlation_id: str, payload: Dict[str, Any],
                           source: str = "unknown", **kwargs):
        """Route a custom message"""
        try:
            message = RoutedMessage(
                message_id=f"msg_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
                channel=channel,
                priority=priority,
                project_id=project_id,
                correlation_id=correlation_id,
                payload=payload,
                timestamp=datetime.now(),
                source=source,
                **kwargs
            )

            await self.message_queue.put((message, None))

        except Exception as e:
            logger.error(f"Error routing message to {channel.value}: {e}")

    def _determine_channel_and_priority(self, event: CrewAIEvent) -> tuple[MessageChannel, MessagePriority]:
        """Determine the appropriate channel and priority for an event"""
        event_type = event.event_type

        # Determine channel
        if event_type in [CrewAIEventType.CREW_START, CrewAIEventType.CREW_COMPLETE, CrewAIEventType.CREW_ERROR]:
            channel = MessageChannel.CREW_EVENTS
        elif event_type in [CrewAIEventType.AGENT_SWITCH, CrewAIEventType.AGENT_START,
                           CrewAIEventType.AGENT_COMPLETE, CrewAIEventType.AGENT_ERROR,
                           CrewAIEventType.AGENT_REASONING]:
            channel = MessageChannel.AGENT_ACTIVITY
        elif event_type in [CrewAIEventType.TOOL_EXECUTION_START, CrewAIEventType.TOOL_EXECUTION_COMPLETE,
                           CrewAIEventType.TOOL_EXECUTION_ERROR]:
            channel = MessageChannel.TOOL_EXECUTIONS
        elif event_type == CrewAIEventType.PROGRESS_UPDATE:
            channel = MessageChannel.PROGRESS_UPDATES
        else:
            channel = MessageChannel.SYSTEM_NOTIFICATIONS

        # Determine priority
        if event_type in [CrewAIEventType.CREW_ERROR, CrewAIEventType.AGENT_ERROR,
                         CrewAIEventType.TOOL_EXECUTION_ERROR]:
            priority = MessagePriority.HIGH
        elif event_type in [CrewAIEventType.CREW_START, CrewAIEventType.CREW_COMPLETE]:
            priority = MessagePriority.NORMAL
        else:
            priority = MessagePriority.LOW

        return channel, priority

    async def _process_message_queue(self):
        """Process messages from the queue"""
        while self.is_routing:
            try:
                # Get message from queue with timeout
                try:
                    message, event = await asyncio.wait_for(self.message_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                # Apply filters
                if not self._passes_filters(message, event):
                    continue

                # Call registered handlers
                await self._call_handlers(message, event)

                # Broadcast via WebSocket
                await self._broadcast_message(message, event)

                # Mark task as done
                self.message_queue.task_done()

            except Exception as e:
                logger.error(f"Error processing message queue: {e}")

    def _passes_filters(self, message: RoutedMessage, event: Optional[CrewAIEvent]) -> bool:
        """Check if message passes all filters"""
        for filter_obj in self.filters:
            if not filter_obj.matches(message, event):
                return False
        return True

    async def _call_handlers(self, message: RoutedMessage, event: Optional[CrewAIEvent]):
        """Call registered handlers for the message"""
        handlers = self.message_handlers[message.channel]
        for handler in handlers:
            try:
                if event:
                    await handler(message, event)
                else:
                    await handler(message)
            except Exception as e:
                logger.error(f"Error in message handler: {e}")

    async def _broadcast_message(self, message: RoutedMessage, event: Optional[CrewAIEvent]):
        """Broadcast message via WebSocket"""
        try:
            import httpx

            # Prepare WebSocket payload
            ws_payload = MessageTransformer.to_websocket_format(message)

            # Add event-specific data
            if event:
                ws_payload["event_data"] = event.to_dict()

            headers = {
                "Authorization": f"Bearer {self.auth_token}",
                "X-Correlation-ID": message.correlation_id,
                "Content-Type": "application/json"
            }

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    f"{self.websocket_url}/api/websocket/broadcast",
                    json=ws_payload,
                    headers=headers
                )

                if response.status_code != 200:
                    logger.warning(f"WebSocket broadcast failed: {response.status_code}")

        except Exception as e:
            logger.debug(f"WebSocket broadcast error (non-critical): {e}")

    def get_router_stats(self) -> Dict[str, Any]:
        """Get router statistics"""
        return {
            "is_routing": self.is_routing,
            "queue_size": self.message_queue.qsize(),
            "registered_handlers": {
                channel.value: len(handlers)
                for channel, handlers in self.message_handlers.items()
            },
            "active_filters": len(self.filters)
        }

    async def clear_queue(self):
        """Clear the message queue"""
        while not self.message_queue.empty():
            try:
                self.message_queue.get_nowait()
                self.message_queue.task_done()
            except asyncio.QueueEmpty:
                break

        logger.info("Message queue cleared")

# Global router instance
crewai_message_router = CrewAIMessageRouter()

# Integration with CrewAIStreamer
async def integrate_router_with_streamer():
    """Integrate the message router with the CrewAI streamer"""

    async def handle_crewai_event(event: CrewAIEvent):
        """Handle CrewAI events from the streamer"""
        await crewai_message_router.route_event(event)

    # Register the handler with the streamer
    crewai_streamer.register_event_handler(CrewAIEventType.CREW_START, handle_crewai_event)
    crewai_streamer.register_event_handler(CrewAIEventType.CREW_COMPLETE, handle_crewai_event)
    crewai_streamer.register_event_handler(CrewAIEventType.CREW_ERROR, handle_crewai_event)
    crewai_streamer.register_event_handler(CrewAIEventType.AGENT_START, handle_crewai_event)
    crewai_streamer.register_event_handler(CrewAIEventType.AGENT_COMPLETE, handle_crewai_event)
    crewai_streamer.register_event_handler(CrewAIEventType.AGENT_ERROR, handle_crewai_event)
    crewai_streamer.register_event_handler(CrewAIEventType.TOOL_EXECUTION_START, handle_crewai_event)
    crewai_streamer.register_event_handler(CrewAIEventType.TOOL_EXECUTION_COMPLETE, handle_crewai_event)
    crewai_streamer.register_event_handler(CrewAIEventType.TOOL_EXECUTION_ERROR, handle_crewai_event)
    crewai_streamer.register_event_handler(CrewAIEventType.PROGRESS_UPDATE, handle_crewai_event)

    logger.info("CrewAI Message Router integrated with CrewAI Streamer")

# Auto-start router on import
asyncio.create_task(crewai_message_router.start_routing())
asyncio.create_task(integrate_router_with_streamer())