"""Mediator pattern implementation for CQRS."""

from typing import Any, Dict, List, Type, TypeVar, Union
from .command import Command, CommandHandler
from .query import Query, QueryHandler
from ..exceptions import CommandHandlerError, QueryHandlerError


TCommand = TypeVar('TCommand', bound=Command)
TQuery = TypeVar('TQuery', bound=Query)
TResult = TypeVar('TResult')


class Mediator:
    """
    Mediator for routing commands and queries to their handlers.
    
    Implements the mediator pattern to decouple the API layer
    from the application layer by routing requests to appropriate handlers.
    """
    
    def __init__(self):
        self._command_handlers: Dict[Type[Command], CommandHandler] = {}
        self._query_handlers: Dict[Type[Query], QueryHandler] = {}
    
    def register_command_handler(
        self, 
        command_type: Type[TCommand], 
        handler: CommandHandler[TCommand]
    ) -> None:
        """
        Register a command handler.
        
        Args:
            command_type: Type of command this handler processes
            handler: Command handler instance
        """
        self._command_handlers[command_type] = handler
    
    def register_query_handler(
        self, 
        query_type: Type[TQuery], 
        handler: QueryHandler[TQuery, TResult]
    ) -> None:
        """
        Register a query handler.
        
        Args:
            query_type: Type of query this handler processes
            handler: Query handler instance
        """
        self._query_handlers[query_type] = handler
    
    async def send_command(self, command: Command) -> None:
        """
        Send a command to its handler.
        
        Args:
            command: Command to execute
            
        Raises:
            CommandHandlerError: If no handler found or execution fails
        """
        command_type = type(command)
        
        if command_type not in self._command_handlers:
            raise CommandHandlerError(
                f"No handler registered for command type: {command_type.__name__}",
                command_type=command_type.__name__
            )
        
        handler = self._command_handlers[command_type]
        
        try:
            await handler.handle(command)
        except Exception as e:
            raise CommandHandlerError(
                f"Command handler failed: {str(e)}",
                command_type=command_type.__name__,
                handler_type=type(handler).__name__
            ) from e
    
    async def send_query(self, query: Query) -> Any:
        """
        Send a query to its handler.
        
        Args:
            query: Query to execute
            
        Returns:
            Query result
            
        Raises:
            QueryHandlerError: If no handler found or execution fails
        """
        query_type = type(query)
        
        if query_type not in self._query_handlers:
            raise QueryHandlerError(
                f"No handler registered for query type: {query_type.__name__}",
                query_type=query_type.__name__
            )
        
        handler = self._query_handlers[query_type]
        
        try:
            return await handler.handle(query)
        except Exception as e:
            raise QueryHandlerError(
                f"Query handler failed: {str(e)}",
                query_type=query_type.__name__,
                handler_type=type(handler).__name__
            ) from e
    
    def get_registered_commands(self) -> List[Type[Command]]:
        """
        Get list of registered command types.
        
        Returns:
            List of command types
        """
        return list(self._command_handlers.keys())
    
    def get_registered_queries(self) -> List[Type[Query]]:
        """
        Get list of registered query types.
        
        Returns:
            List of query types
        """
        return list(self._query_handlers.keys())
