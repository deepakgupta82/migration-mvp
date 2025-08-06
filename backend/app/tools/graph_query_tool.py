"""
Graph Query Tool - Queries Neo4j graph database for relationships
Moved from backend/app/core/crew.py for better organization
"""

from crewai.tools import BaseTool
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class GraphQueryTool(BaseTool):
    """
    A custom tool for the agents to query the project-specific graph database.
    """
    name: str = "Project Graph Database Query Tool"
    description: str = (
        "Use this tool to query the graph database for relationships between entities. "
        "Formulate clear, specific Cypher queries to get the best results."
    )
    
    def __init__(self, graph_service=None):
        super().__init__()
        self.graph_service = graph_service

    class Config:
        arbitrary_types_allowed = True

    def run(self, query: str) -> str:
        """Executes the query against the Graph service."""
        if not self.graph_service:
            return "Error: Graph service not initialized"
        
        try:
            logger.debug(f"GraphQueryTool received query: '{query}'")
            result = self.graph_service.execute_query(query)
            logger.debug(f"GraphQueryTool returning {len(str(result))} results")
            return str(result)
        except Exception as e:
            logger.error(f"Error in GraphQueryTool: {e}")
            return f"Error querying graph database: {str(e)}"

    def _run(self, query: str) -> str:
        """Legacy method for older CrewAI versions."""
        return self.run(query)

    def _arun(self, query: str) -> str:
        """Async version of _run."""
        return self.run(query)
