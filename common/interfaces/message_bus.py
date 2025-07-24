"""Abstract interface for message bus operations."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Callable, Awaitable
from datetime import datetime
from dataclasses import dataclass
from enum import Enum


class MessagePriority(Enum):
    """Message priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Message:
    """Message structure for the message bus."""
    id: str
    topic: str
    payload: Dict[str, Any]
    priority: MessagePriority = MessagePriority.NORMAL
    created_at: datetime = None
    retry_count: int = 0
    max_retries: int = 3
    metadata: Optional[Dict[str, str]] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.metadata is None:
            self.metadata = {}


MessageHandler = Callable[[Message], Awaitable[None]]


class MessageBusInterface(ABC):
    """
    Abstract interface for message bus operations.
    
    Provides a unified interface for different message bus implementations
    including in-memory queues, AWS SQS/SNS, Azure Service Bus, etc.
    """
    
    @abstractmethod
    async def publish(
        self,
        topic: str,
        payload: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
        metadata: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Publish a message to a topic.
        
        Args:
            topic: Topic name
            payload: Message payload
            priority: Message priority
            metadata: Additional message metadata
            
        Returns:
            Message ID
        """
        pass
    
    @abstractmethod
    async def subscribe(
        self,
        topic: str,
        handler: MessageHandler,
        max_concurrent: int = 1
    ) -> str:
        """
        Subscribe to a topic with a message handler.
        
        Args:
            topic: Topic name
            handler: Async function to handle messages
            max_concurrent: Maximum concurrent message processing
            
        Returns:
            Subscription ID
        """
        pass
    
    @abstractmethod
    async def unsubscribe(self, subscription_id: str) -> None:
        """
        Unsubscribe from a topic.
        
        Args:
            subscription_id: Subscription ID returned by subscribe()
        """
        pass
    
    @abstractmethod
    async def send_to_queue(
        self,
        queue_name: str,
        payload: Dict[str, Any],
        delay_seconds: int = 0,
        priority: MessagePriority = MessagePriority.NORMAL,
        metadata: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Send a message to a specific queue.
        
        Args:
            queue_name: Queue name
            payload: Message payload
            delay_seconds: Delay before message becomes available
            priority: Message priority
            metadata: Additional message metadata
            
        Returns:
            Message ID
        """
        pass
    
    @abstractmethod
    async def receive_from_queue(
        self,
        queue_name: str,
        max_messages: int = 1,
        wait_time_seconds: int = 0
    ) -> List[Message]:
        """
        Receive messages from a queue.
        
        Args:
            queue_name: Queue name
            max_messages: Maximum number of messages to receive
            wait_time_seconds: Long polling wait time
            
        Returns:
            List of received messages
        """
        pass
    
    @abstractmethod
    async def acknowledge_message(self, message: Message) -> None:
        """
        Acknowledge successful processing of a message.
        
        Args:
            message: Message to acknowledge
        """
        pass
    
    @abstractmethod
    async def reject_message(
        self,
        message: Message,
        requeue: bool = True
    ) -> None:
        """
        Reject a message, optionally requeuing it.
        
        Args:
            message: Message to reject
            requeue: Whether to requeue the message for retry
        """
        pass
    
    @abstractmethod
    async def create_queue(
        self,
        queue_name: str,
        max_receive_count: int = 3,
        visibility_timeout_seconds: int = 30,
        message_retention_seconds: int = 86400
    ) -> None:
        """
        Create a new queue.
        
        Args:
            queue_name: Queue name
            max_receive_count: Maximum times a message can be received
            visibility_timeout_seconds: Message visibility timeout
            message_retention_seconds: How long messages are retained
        """
        pass
    
    @abstractmethod
    async def delete_queue(self, queue_name: str) -> None:
        """
        Delete a queue.
        
        Args:
            queue_name: Queue name
        """
        pass
    
    @abstractmethod
    async def create_topic(self, topic_name: str) -> None:
        """
        Create a new topic.
        
        Args:
            topic_name: Topic name
        """
        pass
    
    @abstractmethod
    async def delete_topic(self, topic_name: str) -> None:
        """
        Delete a topic.
        
        Args:
            topic_name: Topic name
        """
        pass
    
    @abstractmethod
    async def get_queue_stats(self, queue_name: str) -> Dict[str, Any]:
        """
        Get statistics for a queue.
        
        Args:
            queue_name: Queue name
            
        Returns:
            Dictionary with queue statistics
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        Perform a health check on the message bus.
        
        Returns:
            True if message bus is healthy, False otherwise
        """
        pass
