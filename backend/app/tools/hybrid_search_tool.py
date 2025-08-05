from crewai_tools import BaseTool
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

class HybridSearchTool(BaseTool):
    name: str = "Hybrid Search Tool"
    description: str = "Queries both semantic and graph databases to find and synthesize information."

    def __init__(self, project_id: Optional[str] = None):
        super().__init__()
        self.project_id = project_id
        self._rag_service = None
        self._graph_service = None

    def _get_rag_service(self):
        """Lazy load RAG service"""
        if self._rag_service is None:
            try:
                from app.core.rag_service import RAGService
                self._rag_service = RAGService(self.project_id)
                logger.info("RAG service initialized for hybrid search")
            except Exception as e:
                logger.error(f"Failed to initialize RAG service: {e}")
                self._rag_service = None
        return self._rag_service

    def _get_graph_service(self):
        """Lazy load Graph service"""
        if self._graph_service is None:
            try:
                from app.core.graph_service import GraphService
                self._graph_service = GraphService()
                logger.info("Graph service initialized for hybrid search")
            except Exception as e:
                logger.error(f"Failed to initialize Graph service: {e}")
                self._graph_service = None
        return self._graph_service

    def _run(self, query: str) -> str:
        """Execute hybrid search combining RAG and Graph results"""
        try:
            rag_results = self._query_rag(query)
            graph_results = self._query_graph(query)
            return self._synthesize(query, rag_results, graph_results)
        except Exception as e:
            logger.error(f"Error in hybrid search: {e}")
            return f"Hybrid search error: {str(e)}"

    def _query_rag(self, query: str) -> str:
        """Query RAG service for semantic search results"""
        try:
            rag_service = self._get_rag_service()
            if rag_service:
                results = rag_service.query(query)
                logger.info("RAG query completed successfully")
                return results
            else:
                return "RAG service not available"
        except Exception as e:
            logger.error(f"RAG query failed: {e}")
            return f"RAG query error: {str(e)}"

    def _query_graph(self, query: str) -> str:
        """Query Graph database for relationship information"""
        try:
            graph_service = self._get_graph_service()
            if graph_service and graph_service.driver:
                # Simple graph query to find related entities
                with graph_service.driver.session() as session:
                    # Search for nodes containing query terms
                    cypher_query = """
                    MATCH (n)
                    WHERE toLower(n.name) CONTAINS toLower($query)
                       OR toLower(n.description) CONTAINS toLower($query)
                       OR toLower(n.type) CONTAINS toLower($query)
                    RETURN n.name as name, n.type as type, n.description as description
                    LIMIT 10
                    """
                    result = session.run(cypher_query, query=query)

                    graph_results = []
                    for record in result:
                        name = record.get("name", "Unknown")
                        node_type = record.get("type", "Unknown")
                        description = record.get("description", "No description")
                        graph_results.append(f"- {name} ({node_type}): {description}")

                    if graph_results:
                        logger.info(f"Graph query found {len(graph_results)} results")
                        return "\n".join(graph_results)
                    else:
                        return "No related entities found in graph database"
            else:
                return "Graph database not available"
        except Exception as e:
            logger.error(f"Graph query failed: {e}")
            return f"Graph query error: {str(e)}"

    def _synthesize(self, query: str, rag_results: str, graph_results: str) -> str:
        """Synthesize RAG and Graph results"""
        synthesis = f"# Hybrid Search Results for: {query}\n\n"

        synthesis += "## Semantic Search Results (RAG):\n"
        if rag_results and "error" not in rag_results.lower():
            synthesis += f"{rag_results}\n\n"
        else:
            synthesis += f"⚠️ {rag_results}\n\n"

        synthesis += "## Graph Database Results:\n"
        if graph_results and "error" not in graph_results.lower() and "not available" not in graph_results.lower():
            synthesis += f"{graph_results}\n\n"
        else:
            synthesis += f"⚠️ {graph_results}\n\n"

        synthesis += "## Summary:\n"
        if "error" not in rag_results.lower() and "error" not in graph_results.lower():
            synthesis += "Successfully retrieved information from both semantic search and graph database."
        else:
            synthesis += "Partial results retrieved. Some services may be unavailable."

        return synthesis

