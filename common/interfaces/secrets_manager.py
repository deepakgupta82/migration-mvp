"""Abstract interface for secrets management operations."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass


@dataclass
class SecretMetadata:
    """Metadata for a secret."""
    name: str
    version: str
    created_at: datetime
    last_modified: datetime
    description: Optional[str] = None
    tags: Optional[Dict[str, str]] = None


class SecretsManagerInterface(ABC):
    """
    Abstract interface for secrets management operations.
    
    Provides a unified interface for different secrets management implementations
    including environment variables, AWS Secrets Manager, Azure Key Vault, etc.
    """
    
    @abstractmethod
    async def get_secret(self, secret_name: str) -> str:
        """
        Retrieve a secret value.
        
        Args:
            secret_name: Name of the secret
            
        Returns:
            Secret value as string
            
        Raises:
            SecretNotFoundError: If secret doesn't exist
        """
        pass
    
    @abstractmethod
    async def get_secret_json(self, secret_name: str) -> Dict[str, Any]:
        """
        Retrieve a secret value as JSON.
        
        Args:
            secret_name: Name of the secret
            
        Returns:
            Secret value as dictionary
            
        Raises:
            SecretNotFoundError: If secret doesn't exist
            ValueError: If secret is not valid JSON
        """
        pass
    
    @abstractmethod
    async def set_secret(
        self,
        secret_name: str,
        secret_value: str,
        description: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Store a secret value.
        
        Args:
            secret_name: Name of the secret
            secret_value: Secret value to store
            description: Optional description
            tags: Optional tags for the secret
            
        Returns:
            Version ID of the stored secret
        """
        pass
    
    @abstractmethod
    async def set_secret_json(
        self,
        secret_name: str,
        secret_value: Dict[str, Any],
        description: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Store a secret value as JSON.
        
        Args:
            secret_name: Name of the secret
            secret_value: Secret value as dictionary
            description: Optional description
            tags: Optional tags for the secret
            
        Returns:
            Version ID of the stored secret
        """
        pass
    
    @abstractmethod
    async def delete_secret(self, secret_name: str) -> None:
        """
        Delete a secret.
        
        Args:
            secret_name: Name of the secret to delete
        """
        pass
    
    @abstractmethod
    async def secret_exists(self, secret_name: str) -> bool:
        """
        Check if a secret exists.
        
        Args:
            secret_name: Name of the secret
            
        Returns:
            True if secret exists, False otherwise
        """
        pass
    
    @abstractmethod
    async def list_secrets(
        self,
        prefix: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> List[SecretMetadata]:
        """
        List available secrets.
        
        Args:
            prefix: Filter secrets by name prefix
            tags: Filter secrets by tags
            
        Returns:
            List of secret metadata
        """
        pass
    
    @abstractmethod
    async def get_secret_metadata(self, secret_name: str) -> SecretMetadata:
        """
        Get metadata for a secret.
        
        Args:
            secret_name: Name of the secret
            
        Returns:
            Secret metadata
            
        Raises:
            SecretNotFoundError: If secret doesn't exist
        """
        pass
    
    @abstractmethod
    async def rotate_secret(
        self,
        secret_name: str,
        new_secret_value: str
    ) -> str:
        """
        Rotate a secret to a new value.
        
        Args:
            secret_name: Name of the secret
            new_secret_value: New secret value
            
        Returns:
            Version ID of the new secret
        """
        pass
    
    @abstractmethod
    async def get_secret_versions(self, secret_name: str) -> List[str]:
        """
        Get all versions of a secret.
        
        Args:
            secret_name: Name of the secret
            
        Returns:
            List of version IDs
        """
        pass
    
    @abstractmethod
    async def get_secret_by_version(
        self,
        secret_name: str,
        version_id: str
    ) -> str:
        """
        Retrieve a specific version of a secret.
        
        Args:
            secret_name: Name of the secret
            version_id: Version ID
            
        Returns:
            Secret value for the specified version
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        Perform a health check on the secrets manager.
        
        Returns:
            True if secrets manager is healthy, False otherwise
        """
        pass
