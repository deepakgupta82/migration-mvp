"""Base exception classes for AgentiMigrate Platform."""

from typing import Any, Dict, Optional


class AgentiMigrateException(Exception):
    """
    Base exception for all AgentiMigrate Platform errors.
    
    Provides structured error information including error codes,
    context data, and user-friendly messages.
    """
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        user_message: Optional[str] = None
    ):
        """
        Initialize the exception.
        
        Args:
            message: Technical error message for developers
            error_code: Unique error code for programmatic handling
            context: Additional context data for debugging
            user_message: User-friendly error message
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.context = context or {}
        self.user_message = user_message or message
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert exception to dictionary for serialization.
        
        Returns:
            Dictionary representation of the exception
        """
        return {
            "error_type": self.__class__.__name__,
            "error_code": self.error_code,
            "message": self.message,
            "user_message": self.user_message,
            "context": self.context
        }
    
    def __str__(self) -> str:
        """String representation of the exception."""
        return f"{self.error_code}: {self.message}"
    
    def __repr__(self) -> str:
        """Detailed string representation of the exception."""
        return (
            f"{self.__class__.__name__}("
            f"message='{self.message}', "
            f"error_code='{self.error_code}', "
            f"context={self.context})"
        )
