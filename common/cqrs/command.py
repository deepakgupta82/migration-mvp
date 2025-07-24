"""Command base classes for CQRS pattern."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, TypeVar, Generic
from dataclasses import dataclass
from datetime import datetime
import uuid


@dataclass
class Command(ABC):
    """
    Base class for all commands in the CQRS pattern.
    
    Commands represent intent to change state and should contain
    all necessary information to perform the operation.
    """
    command_id: str = None
    timestamp: datetime = None
    user_id: Optional[str] = None
    correlation_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.command_id is None:
            self.command_id = str(uuid.uuid4())
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.metadata is None:
            self.metadata = {}


TCommand = TypeVar('TCommand', bound=Command)


class CommandHandler(ABC, Generic[TCommand]):
    """
    Base class for command handlers.
    
    Each command should have exactly one handler that contains
    the business logic for executing that command.
    """
    
    @abstractmethod
    async def handle(self, command: TCommand) -> None:
        """
        Handle the command execution.
        
        Args:
            command: The command to execute
            
        Raises:
            CommandHandlerError: If command execution fails
        """
        pass
    
    def can_handle(self, command: Command) -> bool:
        """
        Check if this handler can handle the given command.
        
        Args:
            command: Command to check
            
        Returns:
            True if this handler can handle the command
        """
        # Get the generic type argument
        import typing
        if hasattr(self, '__orig_bases__'):
            for base in self.__orig_bases__:
                if hasattr(base, '__args__') and base.__args__:
                    command_type = base.__args__[0]
                    return isinstance(command, command_type)
        return False
