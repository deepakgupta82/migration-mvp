"""
Global GraphService instance to prevent frequent connection pool reinitialization
"""
from .graph_service import GraphService
import logging

logger = logging.getLogger("global_graph_service")

# Global singleton instance
_global_graph_service = None

def get_graph_service() -> GraphService:
    """Get the global GraphService instance"""
    global _global_graph_service
    if _global_graph_service is None:
        logger.info("Initializing global GraphService instance")
        _global_graph_service = GraphService(use_connection_pool=True, max_connections=10)
    return _global_graph_service

def close_graph_service():
    """Close the global GraphService instance"""
    global _global_graph_service
    if _global_graph_service is not None:
        logger.info("Closing global GraphService instance")
        _global_graph_service.close()
        _global_graph_service = None
