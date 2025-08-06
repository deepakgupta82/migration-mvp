from neo4j import GraphDatabase
import logging
import os
from typing import Dict, Any, Optional, List
from threading import Lock
import time

# Database logging setup
os.makedirs("logs", exist_ok=True)
db_logger = logging.getLogger("database")
db_handler = logging.FileHandler("logs/database.log")
db_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
if not db_logger.hasHandlers():
    db_logger.addHandler(db_handler)
db_logger.setLevel(logging.INFO)

class GraphServicePool:
    """Connection pool manager for Neo4j"""
    _instance = None
    _lock = Lock()

    def __new__(cls, max_connections: int = 10):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, max_connections: int = 10):
        if hasattr(self, 'initialized'):
            return

        self.max_connections = max_connections
        self.active_connections = 0
        self.connection_lock = Lock()
        self.driver = None
        self.initialized = True

        # Initialize driver with connection pooling
        self._initialize_driver()

    def _initialize_driver(self):
        """Initialize Neo4j driver with connection pooling"""
        neo4j_url = os.getenv("NEO4J_URL", "bolt://localhost:7687")
        neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        neo4j_password = os.getenv("NEO4J_PASSWORD", "password")

        try:
            self.driver = GraphDatabase.driver(
                neo4j_url,
                auth=(neo4j_user, neo4j_password),
                max_connection_lifetime=3600,  # 1 hour
                max_connection_pool_size=self.max_connections,
                connection_acquisition_timeout=60,  # 60 seconds
                max_retry_time=15
            )

            # Test connection
            with self.driver.session() as session:
                session.run("RETURN 1")
            db_logger.info(f"Connected to Neo4j at {neo4j_url} with connection pool (max: {self.max_connections})")
        except Exception as e:
            db_logger.warning(f"Failed to connect to Neo4j at {neo4j_url}: {str(e)}")
            self.driver = None

    def get_session(self):
        """Get a session from the connection pool"""
        if self.driver is None:
            raise RuntimeError("Neo4j driver not initialized")

        with self.connection_lock:
            self.active_connections += 1
            db_logger.debug(f"Active connections: {self.active_connections}/{self.max_connections}")

        return self.driver.session()

    def release_session(self):
        """Release a session back to the pool"""
        with self.connection_lock:
            self.active_connections = max(0, self.active_connections - 1)
            db_logger.debug(f"Active connections: {self.active_connections}/{self.max_connections}")

    def close(self):
        """Close the driver and all connections"""
        if self.driver:
            self.driver.close()
            db_logger.info("Neo4j connection pool closed")

class GraphService:
    def __init__(self, use_connection_pool: bool = True, max_connections: int = 10):
        self.use_connection_pool = use_connection_pool

        if use_connection_pool:
            self.pool = GraphServicePool(max_connections)
            self.driver = self.pool.driver
        else:
            # Legacy single connection mode
            neo4j_url = os.getenv("NEO4J_URL", "bolt://localhost:7687")
            neo4j_user = os.getenv("NEO4J_USER", "neo4j")
            neo4j_password = os.getenv("NEO4J_PASSWORD", "password")

            try:
                self.driver = GraphDatabase.driver(neo4j_url, auth=(neo4j_user, neo4j_password))
                # Test connection
                with self.driver.session() as session:
                    session.run("RETURN 1")
                db_logger.info(f"Connected to Neo4j at {neo4j_url} (single connection mode)")
            except Exception as e:
                db_logger.warning(f"Failed to connect to Neo4j at {neo4j_url}: {str(e)}")
                self.driver = None
            self.pool = None

    def close(self):
        """Close the graph service connections"""
        if self.use_connection_pool and self.pool:
            self.pool.close()
        elif self.driver:
            self.driver.close()

    def execute_query(self, query: str, parameters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Execute a Cypher query with connection pooling support"""
        if not self.driver:
            db_logger.warning("Neo4j driver not available, returning empty results")
            return []

        parameters = parameters or {}

        try:
            if self.use_connection_pool and self.pool:
                # Use connection pool
                session = self.pool.get_session()
                try:
                    start_time = time.time()
                    results = session.run(query, parameters)
                    records = [dict(record) for record in results]
                    execution_time = time.time() - start_time

                    db_logger.debug(f"Query executed in {execution_time:.3f}s, returned {len(records)} records")
                    return records
                finally:
                    session.close()
                    self.pool.release_session()
            else:
                # Legacy single connection mode
                with self.driver.session() as session:
                    start_time = time.time()
                    results = session.run(query, parameters)
                    records = [dict(record) for record in results]
                    execution_time = time.time() - start_time

                    db_logger.debug(f"Query executed in {execution_time:.3f}s, returned {len(records)} records")
                    return records

        except Exception as e:
            db_logger.error(f"Error executing Neo4j query: {str(e)}")
            return []

    def execute_write_query(self, query: str, parameters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute a write query (CREATE, UPDATE, DELETE) with connection pooling"""
        if not self.driver:
            db_logger.warning("Neo4j driver not available")
            return {"success": False, "error": "Driver not available"}

        parameters = parameters or {}

        try:
            if self.use_connection_pool and self.pool:
                # Use connection pool
                session = self.pool.get_session()
                try:
                    start_time = time.time()
                    result = session.run(query, parameters)
                    summary = result.consume()
                    execution_time = time.time() - start_time

                    db_logger.info(f"Write query executed in {execution_time:.3f}s, "
                                 f"created: {summary.counters.nodes_created}, "
                                 f"relationships: {summary.counters.relationships_created}")

                    return {
                        "success": True,
                        "nodes_created": summary.counters.nodes_created,
                        "relationships_created": summary.counters.relationships_created,
                        "properties_set": summary.counters.properties_set,
                        "execution_time": execution_time
                    }
                finally:
                    session.close()
                    self.pool.release_session()
            else:
                # Legacy single connection mode
                with self.driver.session() as session:
                    start_time = time.time()
                    result = session.run(query, parameters)
                    summary = result.consume()
                    execution_time = time.time() - start_time

                    db_logger.info(f"Write query executed in {execution_time:.3f}s, "
                                 f"created: {summary.counters.nodes_created}, "
                                 f"relationships: {summary.counters.relationships_created}")

                    return {
                        "success": True,
                        "nodes_created": summary.counters.nodes_created,
                        "relationships_created": summary.counters.relationships_created,
                        "properties_set": summary.counters.properties_set,
                        "execution_time": execution_time
                    }

        except Exception as e:
            db_logger.error(f"Error executing Neo4j write query: {str(e)}")
            return {"success": False, "error": str(e)}

    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics"""
        if self.use_connection_pool and self.pool:
            return {
                "max_connections": self.pool.max_connections,
                "active_connections": self.pool.active_connections,
                "pool_enabled": True
            }
        else:
            return {
                "max_connections": 1,
                "active_connections": 1 if self.driver else 0,
                "pool_enabled": False
            }
