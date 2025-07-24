"""Data Transfer Object base classes."""

from abc import ABC
from dataclasses import dataclass
from typing import Any, Dict, Optional
from datetime import datetime


@dataclass
class DTO(ABC):
    """
    Base class for Data Transfer Objects.
    
    DTOs are used to transfer data between layers and should be
    immutable, serializable objects that contain only data.
    """
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert DTO to dictionary for serialization.
        
        Returns:
            Dictionary representation of the DTO
        """
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, datetime):
                result[key] = value.isoformat()
            elif isinstance(value, DTO):
                result[key] = value.to_dict()
            elif isinstance(value, list) and value and isinstance(value[0], DTO):
                result[key] = [item.to_dict() for item in value]
            else:
                result[key] = value
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DTO':
        """
        Create DTO from dictionary.
        
        Args:
            data: Dictionary data
            
        Returns:
            DTO instance
        """
        # This is a basic implementation - subclasses should override
        # for more complex deserialization logic
        return cls(**data)
