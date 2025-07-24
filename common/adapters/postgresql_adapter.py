"""PostgreSQL adapter for local development."""

import asyncio
import asyncpg
from typing import Any, Dict, List, Optional
from contextlib import asynccontextmanager

from ..interfaces import RelationalDBInterface
from ..exceptions import DatabaseError


class PostgreSQLAdapter(RelationalDBInterface):
    """
    PostgreSQL adapter for local development.
    
    Implements the RelationalDBInterface using asyncpg for PostgreSQL connections.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize PostgreSQL adapter.
        
        Args:
            config: Database configuration
        """
        self.config = config
        self.host = config.get("host", "localhost")
        self.port = config.get("port", 5432)
        self.database = config.get("database", "agentimigrate")
        self.username = config.get("username", "postgres")
        self.password = config.get("password", "password")
        self.ssl_mode = config.get("ssl_mode", "disable")
        self.pool_size = config.get("connection_pool_size", 10)
        self.pool_timeout = config.get("connection_timeout", 30)
        
        self._pool: Optional[asyncpg.Pool] = None
    
    async def connect(self) -> None:
        """Establish connection pool to PostgreSQL."""
        try:
            self._pool = await asyncpg.create_pool(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.username,
                password=self.password,
                ssl=self.ssl_mode if self.ssl_mode != "disable" else False,
                min_size=1,
                max_size=self.pool_size,
                command_timeout=self.pool_timeout
            )
        except Exception as e:
            raise DatabaseError(
                f"Failed to connect to PostgreSQL: {str(e)}",
                database_type="postgresql",
                context={
                    "host": self.host,
                    "port": self.port,
                    "database": self.database
                }
            )
    
    async def disconnect(self) -> None:
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
    
    async def execute_query(
        self, 
        query: str, 
        parameters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Execute a SELECT query and return results."""
        if not self._pool:
            await self.connect()
        
        try:
            async with self._pool.acquire() as connection:
                if parameters:
                    # Convert named parameters to positional for asyncpg
                    param_values = list(parameters.values())
                    # Replace named placeholders with $1, $2, etc.
                    formatted_query = query
                    for i, key in enumerate(parameters.keys(), 1):
                        formatted_query = formatted_query.replace(f":{key}", f"${i}")
                    
                    rows = await connection.fetch(formatted_query, *param_values)
                else:
                    rows = await connection.fetch(query)
                
                # Convert asyncpg.Record to dict
                return [dict(row) for row in rows]
                
        except Exception as e:
            raise DatabaseError(
                f"Query execution failed: {str(e)}",
                database_type="postgresql",
                query=query,
                context={"parameters": parameters}
            )
    
    async def execute_command(
        self, 
        command: str, 
        parameters: Optional[Dict[str, Any]] = None
    ) -> int:
        """Execute an INSERT, UPDATE, or DELETE command."""
        if not self._pool:
            await self.connect()
        
        try:
            async with self._pool.acquire() as connection:
                if parameters:
                    param_values = list(parameters.values())
                    formatted_command = command
                    for i, key in enumerate(parameters.keys(), 1):
                        formatted_command = formatted_command.replace(f":{key}", f"${i}")
                    
                    result = await connection.execute(formatted_command, *param_values)
                else:
                    result = await connection.execute(command)
                
                # Extract affected row count from result
                if result.startswith("INSERT"):
                    return int(result.split()[-1])
                elif result.startswith(("UPDATE", "DELETE")):
                    return int(result.split()[-1])
                else:
                    return 0
                    
        except Exception as e:
            raise DatabaseError(
                f"Command execution failed: {str(e)}",
                database_type="postgresql",
                query=command,
                context={"parameters": parameters}
            )
    
    async def execute_transaction(
        self, 
        commands: List[tuple[str, Optional[Dict[str, Any]]]]
    ) -> List[int]:
        """Execute multiple commands in a transaction."""
        if not self._pool:
            await self.connect()
        
        try:
            async with self._pool.acquire() as connection:
                async with connection.transaction():
                    results = []
                    for command, parameters in commands:
                        if parameters:
                            param_values = list(parameters.values())
                            formatted_command = command
                            for i, key in enumerate(parameters.keys(), 1):
                                formatted_command = formatted_command.replace(f":{key}", f"${i}")
                            
                            result = await connection.execute(formatted_command, *param_values)
                        else:
                            result = await connection.execute(command)
                        
                        # Extract affected row count
                        if result.startswith("INSERT"):
                            results.append(int(result.split()[-1]))
                        elif result.startswith(("UPDATE", "DELETE")):
                            results.append(int(result.split()[-1]))
                        else:
                            results.append(0)
                    
                    return results
                    
        except Exception as e:
            raise DatabaseError(
                f"Transaction execution failed: {str(e)}",
                database_type="postgresql",
                context={"commands_count": len(commands)}
            )
    
    async def create_table(
        self, 
        table_name: str, 
        schema: Dict[str, str],
        indexes: Optional[List[str]] = None
    ) -> None:
        """Create a table with the specified schema."""
        columns = []
        for column_name, column_type in schema.items():
            columns.append(f"{column_name} {column_type}")
        
        create_sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(columns)})"
        
        await self.execute_command(create_sql)
        
        # Create indexes if specified
        if indexes:
            for index_column in indexes:
                index_name = f"idx_{table_name}_{index_column}"
                index_sql = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({index_column})"
                await self.execute_command(index_sql)
    
    async def table_exists(self, table_name: str) -> bool:
        """Check if a table exists."""
        query = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = :table_name
            )
        """
        
        result = await self.execute_query(query, {"table_name": table_name})
        return result[0]["exists"] if result else False
    
    async def get_table_schema(self, table_name: str) -> Dict[str, str]:
        """Get the schema of an existing table."""
        query = """
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = :table_name
            ORDER BY ordinal_position
        """
        
        result = await self.execute_query(query, {"table_name": table_name})
        return {row["column_name"]: row["data_type"] for row in result}
    
    @asynccontextmanager
    async def transaction(self):
        """Context manager for database transactions."""
        if not self._pool:
            await self.connect()
        
        async with self._pool.acquire() as connection:
            async with connection.transaction():
                yield connection
    
    async def health_check(self) -> bool:
        """Perform a health check on the database connection."""
        try:
            await self.execute_query("SELECT 1")
            return True
        except Exception:
            return False
