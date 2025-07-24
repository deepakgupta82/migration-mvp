"""Application-related exceptions."""

from typing import Any, Dict, Optional
from .base import AgentiMigrateException


class ApplicationError(AgentiMigrateException):
    """Base class for application layer errors."""
    
    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        error_context = context or {}
        if operation:
            error_context["operation"] = operation
        
        super().__init__(
            message=message,
            error_code="APPLICATION_ERROR",
            context=error_context,
            user_message="An application error occurred. Please try again."
        )


class CommandHandlerError(ApplicationError):
    """Raised when command handler execution fails."""
    
    def __init__(
        self,
        message: str,
        command_type: Optional[str] = None,
        handler_type: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        error_context = context or {}
        if command_type:
            error_context["command_type"] = command_type
        if handler_type:
            error_context["handler_type"] = handler_type
        
        super().__init__(
            message=message,
            operation="command_execution",
            context=error_context
        )
        self.error_code = "COMMAND_HANDLER_ERROR"
        self.user_message = "Command execution failed. Please try again."


class QueryHandlerError(ApplicationError):
    """Raised when query handler execution fails."""
    
    def __init__(
        self,
        message: str,
        query_type: Optional[str] = None,
        handler_type: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        error_context = context or {}
        if query_type:
            error_context["query_type"] = query_type
        if handler_type:
            error_context["handler_type"] = handler_type
        
        super().__init__(
            message=message,
            operation="query_execution",
            context=error_context
        )
        self.error_code = "QUERY_HANDLER_ERROR"
        self.user_message = "Query execution failed. Please try again."


class AuthenticationError(ApplicationError):
    """Raised when authentication fails."""
    
    def __init__(
        self,
        message: str = "Authentication failed",
        username: Optional[str] = None,
        auth_method: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        error_context = context or {}
        if username:
            error_context["username"] = username
        if auth_method:
            error_context["auth_method"] = auth_method
        
        super().__init__(
            message=message,
            operation="authentication",
            context=error_context
        )
        self.error_code = "AUTHENTICATION_ERROR"
        self.user_message = "Authentication failed. Please check your credentials."


class AuthorizationError(ApplicationError):
    """Raised when authorization fails."""
    
    def __init__(
        self,
        message: str = "Access denied",
        user_id: Optional[str] = None,
        resource: Optional[str] = None,
        action: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        error_context = context or {}
        if user_id:
            error_context["user_id"] = user_id
        if resource:
            error_context["resource"] = resource
        if action:
            error_context["action"] = action
        
        super().__init__(
            message=message,
            operation="authorization",
            context=error_context
        )
        self.error_code = "AUTHORIZATION_ERROR"
        self.user_message = "You don't have permission to perform this action."


class InvalidCommandError(ApplicationError):
    """Raised when a command is invalid."""
    
    def __init__(
        self,
        message: str,
        command_type: Optional[str] = None,
        validation_errors: Optional[Dict[str, str]] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        error_context = context or {}
        if command_type:
            error_context["command_type"] = command_type
        if validation_errors:
            error_context["validation_errors"] = validation_errors
        
        super().__init__(
            message=message,
            operation="command_validation",
            context=error_context
        )
        self.error_code = "INVALID_COMMAND"
        self.user_message = f"Invalid request: {message}"


class InvalidQueryError(ApplicationError):
    """Raised when a query is invalid."""
    
    def __init__(
        self,
        message: str,
        query_type: Optional[str] = None,
        validation_errors: Optional[Dict[str, str]] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        error_context = context or {}
        if query_type:
            error_context["query_type"] = query_type
        if validation_errors:
            error_context["validation_errors"] = validation_errors
        
        super().__init__(
            message=message,
            operation="query_validation",
            context=error_context
        )
        self.error_code = "INVALID_QUERY"
        self.user_message = f"Invalid request: {message}"


class ConcurrencyError(ApplicationError):
    """Raised when a concurrency conflict occurs."""
    
    def __init__(
        self,
        message: str = "Concurrency conflict detected",
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        error_context = context or {}
        if entity_type:
            error_context["entity_type"] = entity_type
        if entity_id:
            error_context["entity_id"] = entity_id
        
        super().__init__(
            message=message,
            operation="concurrency_check",
            context=error_context
        )
        self.error_code = "CONCURRENCY_ERROR"
        self.user_message = "The resource was modified by another user. Please refresh and try again."
