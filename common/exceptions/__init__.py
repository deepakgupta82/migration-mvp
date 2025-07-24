"""Custom exceptions for AgentiMigrate Platform."""

from .base import AgentiMigrateException
from .config import ConfigurationError
from .infrastructure import (
    InfrastructureError,
    DatabaseError,
    ObjectStorageError,
    MessageBusError,
    SecretsManagerError
)
from .domain import (
    DomainError,
    ValidationError,
    BusinessRuleViolationError,
    EntityNotFoundError
)
from .application import (
    ApplicationError,
    CommandHandlerError,
    QueryHandlerError,
    AuthenticationError,
    AuthorizationError
)

__all__ = [
    # Base
    "AgentiMigrateException",
    
    # Configuration
    "ConfigurationError",
    
    # Infrastructure
    "InfrastructureError",
    "DatabaseError", 
    "ObjectStorageError",
    "MessageBusError",
    "SecretsManagerError",
    
    # Domain
    "DomainError",
    "ValidationError",
    "BusinessRuleViolationError",
    "EntityNotFoundError",
    
    # Application
    "ApplicationError",
    "CommandHandlerError",
    "QueryHandlerError",
    "AuthenticationError",
    "AuthorizationError"
]
