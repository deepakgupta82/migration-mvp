"""Infrastructure-related exceptions."""

from typing import Any, Dict, Optional
from .base import AgentiMigrateException


class InfrastructureError(AgentiMigrateException):
    """Base class for infrastructure-related errors."""
    
    def __init__(
        self,
        message: str,
        service_name: Optional[str] = None,
        operation: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        error_context = context or {}
        if service_name:
            error_context["service_name"] = service_name
        if operation:
            error_context["operation"] = operation
        
        super().__init__(
            message=message,
            error_code="INFRASTRUCTURE_ERROR",
            context=error_context,
            user_message="A system service is temporarily unavailable. Please try again later."
        )


class DatabaseError(InfrastructureError):
    """Raised when database operations fail."""
    
    def __init__(
        self,
        message: str,
        database_type: Optional[str] = None,
        query: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        error_context = context or {}
        if database_type:
            error_context["database_type"] = database_type
        if query:
            error_context["query"] = query
        
        super().__init__(
            message=message,
            service_name="database",
            context=error_context
        )
        self.error_code = "DATABASE_ERROR"
        self.user_message = "Database operation failed. Please try again later."


class ObjectStorageError(InfrastructureError):
    """Raised when object storage operations fail."""
    
    def __init__(
        self,
        message: str,
        bucket_name: Optional[str] = None,
        object_key: Optional[str] = None,
        operation: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        error_context = context or {}
        if bucket_name:
            error_context["bucket_name"] = bucket_name
        if object_key:
            error_context["object_key"] = object_key
        
        super().__init__(
            message=message,
            service_name="object_storage",
            operation=operation,
            context=error_context
        )
        self.error_code = "OBJECT_STORAGE_ERROR"
        self.user_message = "File storage operation failed. Please try again later."


class ObjectNotFoundError(ObjectStorageError):
    """Raised when an object is not found in storage."""
    
    def __init__(self, object_key: str, bucket_name: Optional[str] = None):
        super().__init__(
            message=f"Object not found: {object_key}",
            bucket_name=bucket_name,
            object_key=object_key,
            operation="get"
        )
        self.error_code = "OBJECT_NOT_FOUND"
        self.user_message = "The requested file was not found."


class MessageBusError(InfrastructureError):
    """Raised when message bus operations fail."""
    
    def __init__(
        self,
        message: str,
        topic: Optional[str] = None,
        queue: Optional[str] = None,
        operation: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        error_context = context or {}
        if topic:
            error_context["topic"] = topic
        if queue:
            error_context["queue"] = queue
        
        super().__init__(
            message=message,
            service_name="message_bus",
            operation=operation,
            context=error_context
        )
        self.error_code = "MESSAGE_BUS_ERROR"
        self.user_message = "Message processing failed. Please try again later."


class SecretsManagerError(InfrastructureError):
    """Raised when secrets manager operations fail."""
    
    def __init__(
        self,
        message: str,
        secret_name: Optional[str] = None,
        operation: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        error_context = context or {}
        if secret_name:
            error_context["secret_name"] = secret_name
        
        super().__init__(
            message=message,
            service_name="secrets_manager",
            operation=operation,
            context=error_context
        )
        self.error_code = "SECRETS_MANAGER_ERROR"
        self.user_message = "Security configuration error. Please contact support."


class SecretNotFoundError(SecretsManagerError):
    """Raised when a secret is not found."""
    
    def __init__(self, secret_name: str):
        super().__init__(
            message=f"Secret not found: {secret_name}",
            secret_name=secret_name,
            operation="get"
        )
        self.error_code = "SECRET_NOT_FOUND"
        self.user_message = "Required security configuration is missing."
