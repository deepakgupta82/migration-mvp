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
        self._client = None
        self.cypher_generator = CypherGenerator()

    def _get_client(self):
        """Lazy load ServiceClient"""
        if self._client is None:
            try:
                import anyio
                from app.core.service_client import get_service_client
                async def _get():
                    return await get_service_client()
                self._client = anyio.run(_get)
                logger.info("Service client initialized for hybrid search")
            except Exception as e:
                logger.error(f"Failed to initialize service client: {e}")
                self._client = None
        return self._client

    def _run(self, query: str) -> str:
        """Execute hybrid search with intelligent query routing"""
        try:
            # Determine optimal search strategy
            search_strategy = self._intelligent_query_routing(query)

            if search_strategy == "semantic_only":
                return self._query_vectors(query)
            elif search_strategy == "graph_only":
                return self._query_graph(query)
            else:  # hybrid
                rag_results = self._query_vectors(query)
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

    def _query_vectors(self, query: str) -> str:
        """Query vector service via ServiceClient for semantic results"""
        try:
            client = self._get_client()
            if not client:
                return "Vector service client not available"
            import anyio
            async def _search():
                try:
                    return await client.vector_search(self.project_id, query, limit=5)
                except Exception:
                    return await client.hybrid_search(self.project_id, query, limit=5)
            res = anyio.run(_search)
            snippets = []
            for item in (res or {}).get("results", []) or []:
                content = item.get("content") or ""
                if content:
                    snippets.append(content)
            if not snippets:
                return "No semantic results found"
            return "\n\n".join(snippets)
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return f"Vector search error: {str(e)}"

    def _query_graph(self, query: str) -> str:
        """Query graph-service for related nodes using targeted node search endpoint."""
        try:
            client = self._get_client()
            if not client:
                return "Graph service client not available"
            import anyio
            async def _search():
                # Use graph-service node search; default limit 10
                return await client.search_graph_nodes(self.project_id, query, limit=10)
            res = anyio.run(_search)
            results = (res or {}).get("results", [])
            if not results:
                return "No related entities found in graph"
            lines = []
            for n in results:
                name = n.get("name") or ""
                type_ = n.get("type") or (",".join(n.get("labels", []) or []))
                lines.append(f"- {name} ({type_})")
            logger.info(f"Graph results: {len(lines)} hits via node search")
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Graph query failed via service client: {e}")
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

