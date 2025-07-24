"""Query base classes for CQRS pattern."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, TypeVar, Generic
from dataclasses import dataclass
from datetime import datetime
import uuid


@dataclass
class Query(ABC):
    """
    Base class for all queries in the CQRS pattern.
    
    Queries represent requests for data and should contain
    all necessary parameters for data retrieval.
    """
    query_id: str = None
    timestamp: datetime = None
    user_id: Optional[str] = None
    correlation_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.query_id is None:
            self.query_id = str(uuid.uuid4())
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.metadata is None:
            self.metadata = {}


TQuery = TypeVar('TQuery', bound=Query)
TResult = TypeVar('TResult')


class QueryHandler(ABC, Generic[TQuery, TResult]):
    """
    Base class for query handlers.
    
    Each query should have exactly one handler that contains
    the logic for retrieving and formatting the requested data.
    """
    
    @abstractmethod
    async def handle(self, query: TQuery) -> TResult:
        """
        Handle the query execution.
        
        Args:
            query: The query to execute
            
        Returns:
            Query result (typically a DTO)
            
        Raises:
            QueryHandlerError: If query execution fails
        """
        pass
    
    def can_handle(self, query: Query) -> bool:
        """
        Check if this handler can handle the given query.
        
        Args:
            query: Query to check
            
        Returns:
            True if this handler can handle the query
        """
        # Get the generic type argument
        import typing
        if hasattr(self, '__orig_bases__'):
            for base in self.__orig_bases__:
                if hasattr(base, '__args__') and base.__args__:
                    query_type = base.__args__[0]
                    return isinstance(query, query_type)
        return False
