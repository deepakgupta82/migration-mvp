from crewai.tools import BaseTool
import logging
import os
from typing import Optional, Dict, Any

# Import new utilities
from app.utils.cypher_generator import CypherGenerator

logger = logging.getLogger(__name__)

class HybridSearchTool(BaseTool):
    name: str = "Hybrid Search Tool"
    description: str = "Queries both semantic and graph databases to find and synthesize information with LLM-powered query generation."
    project_id: Optional[str] = None  # Declare as Pydantic field
    llm: Optional[Any] = None  # Declare as Pydantic field
    cypher_generator: Optional[Any] = None  # Declare as Pydantic field to avoid validation error

    def __init__(self, project_id: Optional[str] = None, llm=None, **kwargs):
        super().__init__(project_id=project_id, llm=llm, cypher_generator=None, **kwargs)
        self._rag_service = None
        self._graph_service = None
        self.cypher_generator = CypherGenerator()

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
        """Execute hybrid search with intelligent query routing"""
        try:
            # Determine optimal search strategy
            search_strategy = self._intelligent_query_routing(query)

            if search_strategy == "semantic_only":
                return self._query_rag(query)
            elif search_strategy == "graph_only":
                return self._query_graph(query)
            else:  # hybrid
                rag_results = self._query_rag(query)
                graph_results = self._query_graph(query)
                return self._synthesize(query, rag_results, graph_results)
        except Exception as e:
            logger.error(f"Error in hybrid search: {e}")
            return f"Hybrid search error: {str(e)}"

    def _intelligent_query_routing(self, query: str) -> str:
        """Determine optimal search strategy based on query type"""
        query_lower = query.lower()

        # Graph-oriented queries
        graph_keywords = [
            "connected to", "depends on", "relationship", "architecture",
            "dependencies", "how many", "count", "find all", "what connects"
        ]

        # Semantic-oriented queries
        semantic_keywords = [
            "explain", "describe", "what is", "how to", "why", "when",
            "documentation", "details", "information about"
        ]

        graph_score = sum(1 for keyword in graph_keywords if keyword in query_lower)
        semantic_score = sum(1 for keyword in semantic_keywords if keyword in query_lower)

        if graph_score > semantic_score and graph_score > 0:
            return "graph_only"
        elif semantic_score > graph_score and semantic_score > 0:
            return "semantic_only"
        else:
            return "hybrid"

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
        """Query Graph database for relationship information with LLM-powered Cypher generation"""
        try:
            graph_service = self._get_graph_service()
            if graph_service and graph_service.driver:
                # Use LLM to generate dynamic Cypher query if available
                if self.llm:
                    cypher_result = self.cypher_generator.generate_cypher_from_natural_language(query, self.llm)
                    cypher_query = cypher_result.query
                    parameters = cypher_result.parameters
                    logger.info(f"Generated Cypher query with confidence {cypher_result.confidence}: {cypher_result.explanation}")
                else:
                    # Fallback to pattern-based generation
                    cypher_result = self.cypher_generator.generate_cypher_from_natural_language(query)
                    cypher_query = cypher_result.query
                    parameters = cypher_result.parameters
                    logger.info(f"Using pattern-based Cypher generation: {cypher_result.explanation}")

                # Execute the generated query
                with graph_service.driver.session() as session:
                    # Merge query parameter with generated parameters
                    all_parameters = {"query": query}
                    all_parameters.update(parameters)
                    result = session.run(cypher_query, all_parameters)

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

