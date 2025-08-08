"""
RAG Query Tool - Queries project-specific knowledge base using RAG
Moved from backend/app/core/crew.py for better organization
"""

from crewai.tools import BaseTool
from typing import Optional, Any
from pydantic import Field
import logging

logger = logging.getLogger(__name__)

class RAGQueryTool(BaseTool):
    """
    A custom tool for the agents to query the project-specific knowledge base.
    This is the only way for them to access information from the uploaded documents.
    """
    name: str = "Project Knowledge Base Query Tool"
    description: str = (
        "Use this tool to answer any questions about the client's project. "
        "It queries a vector database containing the contents of all uploaded documents "
        "(architecture diagrams, project charters, security audits, server lists, etc.). "
        "Formulate clear, specific questions to get the best results."
    )

    def __init__(self, rag_service=None, **kwargs):
        super().__init__(**kwargs)
        # Use private attribute to avoid Pydantic validation
        self._rag_service = rag_service

    @property
    def rag_service(self):
        return self._rag_service

    class Config:
        arbitrary_types_allowed = True

    def run(self, question: str) -> str:
        """Executes the query against the RAG service."""
        if not self.rag_service:
            return "Error: RAG service not initialized"
        
        try:
            logger.debug(f"RAGQueryTool received query: '{question}'")
            result = self.rag_service.query(question)
            logger.debug(f"RAGQueryTool returning {len(str(result))} characters")
            return result
        except Exception as e:
            logger.error(f"Error in RAGQueryTool: {e}")
            return f"Error querying knowledge base: {str(e)}"

    def _run(self, question: str) -> str:
        """Legacy method for older CrewAI versions."""
        return self.run(question)

    def _arun(self, question: str) -> str:
        """Async version of _run."""
        return self.run(question)
