from neo4j import GraphDatabase
import logging
import os
from typing import Dict, Any, Optional, List
from threading import Lock
import time
import tempfile

# Use external / temp log directory to avoid triggering auto-reload on file writes
LOG_DIR = os.getenv("LOG_DIR") or os.path.join(tempfile.gettempdir(), "ascent_logs")
os.makedirs(LOG_DIR, exist_ok=True)
log_path = os.path.join(LOG_DIR, "database.log")

# Database logging setup (moved)
db_logger = logging.getLogger("database")
# Remove existing file handlers pointing inside project
for h in list(db_logger.handlers):
    try:
        if isinstance(h, logging.FileHandler) and "database.log" in getattr(h, 'baseFilename', ''):
            db_logger.removeHandler(h)
    except Exception:
        pass
if not any(isinstance(h, logging.FileHandler) and getattr(h, 'baseFilename', '') == log_path for h in db_logger.handlers):
    db_handler = logging.FileHandler(log_path, encoding='utf-8')
    db_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
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
        # Prefer IPv4 for localhost on Windows to avoid ::1 issues
        prefer_ipv4 = os.getenv("PREFER_IPV4", "1").lower() in ("1", "true", "yes")
        if prefer_ipv4 and "://localhost" in neo4j_url:
            neo4j_url = neo4j_url.replace("://localhost", "://127.0.0.1")
            db_logger.info(f"Using IPv4 loopback for Neo4j URL: {neo4j_url}")

        try:
            self.driver = GraphDatabase.driver(
                neo4j_url,
                auth=(neo4j_user, neo4j_password),
                max_connection_lifetime=3600,  # 1 hour
                max_connection_pool_size=self.max_connections,
                connection_acquisition_timeout=60  # 60 seconds
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
            self._initialize_driver()
            if self.driver is None:
                raise RuntimeError("Neo4j driver not initialized")

        # Check if driver is still open before using it
        try:
            # Test if driver is still valid by checking if it's closed
            if hasattr(self.driver, '_closed') and self.driver._closed:
                db_logger.warning("Neo4j driver was closed, reinitializing...")
                self._initialize_driver()
                if self.driver is None:
                    raise RuntimeError("Neo4j driver reinitialization failed")
        except AttributeError:
            # Some driver versions don't have _closed attribute, continue
            pass

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
        """Execute a Cypher query with connection pooling support and robust error handling."""
        if not self.driver:
            db_logger.debug("Neo4j driver not available, returning empty results")
            return []

        parameters = parameters or {}

        def _run(session):
            start_time = time.time()
            results = session.run(query, parameters)
            records = [dict(record) for record in results]
            execution_time = time.time() - start_time
            db_logger.debug(f"Query executed in {execution_time:.3f}s, returned {len(records)} records")
            return records

        try:
            if self.use_connection_pool and self.pool:
                session = self.pool.get_session()
                try:
                    return _run(session)
                finally:
                    session.close()
                    self.pool.release_session()
            else:
                with self.driver.session() as session:
                    return _run(session)
        except Exception as e:
            msg = str(e).lower()
            db_logger.error(f"GraphService query failed: {str(e)} | Query: {query} | Parameters: {parameters}")
            # Retry once on defunct/closed connection
            if "defunct" in msg or "closed" in msg:
                db_logger.warning("Defunct/closed Neo4j connection detected; reinitializing driver and retrying once")
                try:
                    if self.use_connection_pool and self.pool:
                        self.pool._initialize_driver()
                        if self.pool.driver is None:
                            return []
                        session = self.pool.get_session()
                        try:
                            return _run(session)
                        finally:
                            session.close()
                            self.pool.release_session()
                    else:
                        # Recreate single driver
                        neo4j_url = os.getenv("NEO4J_URL", "bolt://127.0.0.1:7687")
                        neo4j_user = os.getenv("NEO4J_USER", "neo4j")
                        neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
                        self.driver = GraphDatabase.driver(neo4j_url, auth=(neo4j_user, neo4j_password))
                        with self.driver.session() as session:
                            return _run(session)
                except Exception as e2:
                    db_logger.error(f"Retry after driver reinit failed: {e2}")
            return []

    def execute_write_query(self, query: str, parameters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute a write query (CREATE, UPDATE, DELETE) with connection pooling"""
        if not self.driver:
            db_logger.warning("Neo4j driver not available")
            return {"success": False, "error": "Driver not available"}

        parameters = parameters or {}

        def _run(session):
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

        try:
            if self.use_connection_pool and self.pool:
                session = self.pool.get_session()
                try:
                    return _run(session)
                finally:
                    session.close()
                    self.pool.release_session()
            else:
                with self.driver.session() as session:
                    return _run(session)
        except Exception as e:
            msg = str(e).lower()
            db_logger.error(f"Error executing Neo4j write query: {str(e)}")
            if "defunct" in msg or "closed" in msg:
                db_logger.warning("Defunct/closed Neo4j connection on write; reinitializing and retrying once")
                try:
                    if self.use_connection_pool and self.pool:
                        self.pool._initialize_driver()
                        if self.pool.driver is None:
                            return {"success": False, "error": "Driver not available after reinit"}
                        session = self.pool.get_session()
                        try:
                            return _run(session)
                        finally:
                            session.close()
                            self.pool.release_session()
                    else:
                        neo4j_url = os.getenv("NEO4J_URL", "bolt://127.0.0.1:7687")
                        neo4j_user = os.getenv("NEO4J_USER", "neo4j")
                        neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
                        self.driver = GraphDatabase.driver(neo4j_url, auth=(neo4j_user, neo4j_password))
                        with self.driver.session() as session:
                            return _run(session)
                except Exception as e2:
                    db_logger.error(f"Retry after driver reinit (write) failed: {e2}")
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
