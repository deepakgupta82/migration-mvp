"""Configuration-related exceptions."""

from typing import Any, Dict, Optional
from .base import AgentiMigrateException


class ConfigurationError(AgentiMigrateException):
    """Raised when there are configuration-related errors."""
    
    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        config_file: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize configuration error.
        
        Args:
            message: Error message
            config_key: Configuration key that caused the error
            config_file: Configuration file that caused the error
            context: Additional context
        """
        error_context = context or {}
        if config_key:
            error_context["config_key"] = config_key
        if config_file:
            error_context["config_file"] = config_file
        
        super().__init__(
            message=message,
            error_code="CONFIG_ERROR",
            context=error_context,
            user_message="Configuration error occurred. Please check your configuration files."
        )
