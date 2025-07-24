"""Domain-related exceptions."""

from typing import Any, Dict, Optional
from .base import AgentiMigrateException


class DomainError(AgentiMigrateException):
    """Base class for domain-related errors."""
    
    def __init__(
        self,
        message: str,
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
            error_code="DOMAIN_ERROR",
            context=error_context,
            user_message="A business rule violation occurred."
        )


class ValidationError(DomainError):
    """Raised when domain validation fails."""
    
    def __init__(
        self,
        message: str,
        field_name: Optional[str] = None,
        field_value: Optional[Any] = None,
        validation_rule: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        error_context = context or {}
        if field_name:
            error_context["field_name"] = field_name
        if field_value is not None:
            error_context["field_value"] = str(field_value)
        if validation_rule:
            error_context["validation_rule"] = validation_rule
        
        super().__init__(
            message=message,
            context=error_context
        )
        self.error_code = "VALIDATION_ERROR"
        self.user_message = f"Invalid input: {message}"


class BusinessRuleViolationError(DomainError):
    """Raised when a business rule is violated."""
    
    def __init__(
        self,
        message: str,
        rule_name: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        error_context = context or {}
        if rule_name:
            error_context["rule_name"] = rule_name
        
        super().__init__(
            message=message,
            entity_type=entity_type,
            entity_id=entity_id,
            context=error_context
        )
        self.error_code = "BUSINESS_RULE_VIOLATION"
        self.user_message = f"Operation not allowed: {message}"


class EntityNotFoundError(DomainError):
    """Raised when a domain entity is not found."""
    
    def __init__(
        self,
        entity_type: str,
        entity_id: str,
        context: Optional[Dict[str, Any]] = None
    ):
        message = f"{entity_type} with ID '{entity_id}' not found"
        
        super().__init__(
            message=message,
            entity_type=entity_type,
            entity_id=entity_id,
            context=context
        )
        self.error_code = "ENTITY_NOT_FOUND"
        self.user_message = f"The requested {entity_type.lower()} was not found."


class DuplicateEntityError(DomainError):
    """Raised when attempting to create a duplicate entity."""
    
    def __init__(
        self,
        entity_type: str,
        identifier: str,
        identifier_field: str = "id",
        context: Optional[Dict[str, Any]] = None
    ):
        message = f"{entity_type} with {identifier_field} '{identifier}' already exists"
        
        error_context = context or {}
        error_context["identifier"] = identifier
        error_context["identifier_field"] = identifier_field
        
        super().__init__(
            message=message,
            entity_type=entity_type,
            context=error_context
        )
        self.error_code = "DUPLICATE_ENTITY"
        self.user_message = f"A {entity_type.lower()} with that {identifier_field} already exists."


class InvalidStateTransitionError(DomainError):
    """Raised when an invalid state transition is attempted."""
    
    def __init__(
        self,
        entity_type: str,
        entity_id: str,
        current_state: str,
        target_state: str,
        context: Optional[Dict[str, Any]] = None
    ):
        message = f"Invalid state transition for {entity_type} '{entity_id}': {current_state} -> {target_state}"
        
        error_context = context or {}
        error_context["current_state"] = current_state
        error_context["target_state"] = target_state
        
        super().__init__(
            message=message,
            entity_type=entity_type,
            entity_id=entity_id,
            context=error_context
        )
        self.error_code = "INVALID_STATE_TRANSITION"
        self.user_message = f"Cannot change {entity_type.lower()} from {current_state} to {target_state}."
