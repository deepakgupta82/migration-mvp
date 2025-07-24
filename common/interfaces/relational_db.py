"""Abstract interface for relational database operations."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from contextlib import asynccontextmanager


class RelationalDBInterface(ABC):
    """
    Abstract interface for relational database operations.
    
    Provides a unified interface for different relational database implementations
    including local PostgreSQL, AWS RDS, Azure Database, etc.
    """
    
    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the database."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the database."""
        pass
    
    @abstractmethod
    async def execute_query(
        self, 
        query: str, 
        parameters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute a SELECT query and return results.
        
        Args:
            query: SQL query string
            parameters: Query parameters for safe parameterized queries
            
        Returns:
            List of dictionaries representing query results
        """
        pass
    
    @abstractmethod
    async def execute_command(
        self, 
        command: str, 
        parameters: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Execute an INSERT, UPDATE, or DELETE command.
        
        Args:
            command: SQL command string
            parameters: Command parameters for safe parameterized queries
            
        Returns:
            Number of affected rows
        """
        pass
    
    @abstractmethod
    async def execute_transaction(
        self, 
        commands: List[tuple[str, Optional[Dict[str, Any]]]]
    ) -> List[int]:
        """
        Execute multiple commands in a transaction.
        
        Args:
            commands: List of (command, parameters) tuples
            
        Returns:
            List of affected row counts for each command
            
        Raises:
            Exception: If any command fails, entire transaction is rolled back
        """
        pass
    
    @abstractmethod
    async def create_table(
        self, 
        table_name: str, 
        schema: Dict[str, str],
        indexes: Optional[List[str]] = None
    ) -> None:
        """
        Create a table with the specified schema.
        
        Args:
            table_name: Name of the table to create
            schema: Dictionary mapping column names to SQL types
            indexes: Optional list of column names to index
        """
        pass
    
    @abstractmethod
    async def table_exists(self, table_name: str) -> bool:
        """
        Check if a table exists in the database.
        
        Args:
            table_name: Name of the table to check
            
        Returns:
            True if table exists, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_table_schema(self, table_name: str) -> Dict[str, str]:
        """
        Get the schema of an existing table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            Dictionary mapping column names to SQL types
        """
        pass
    
    @abstractmethod
    @asynccontextmanager
    async def transaction(self):
        """
        Context manager for database transactions.
        
        Usage:
            async with db.transaction():
                await db.execute_command("INSERT ...")
                await db.execute_command("UPDATE ...")
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        Perform a health check on the database connection.
        
        Returns:
            True if database is healthy, False otherwise
        """
        pass
