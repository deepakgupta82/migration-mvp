"""
Hybrid Search Tool for ai-agent-service
Calls vector-service and graph-service via local ServiceClient and synthesizes results.
"""
from crewai.tools import BaseTool
import logging
from typing import Optional, Any

from app.utils.cypher_generator import CypherGenerator

logger = logging.getLogger(__name__)

class HybridSearchTool(BaseTool):
    name: str = "Hybrid Search Tool"
    description: str = "Queries both semantic and graph databases to find and synthesize information with LLM-powered query generation."
    project_id: Optional[str] = None
    llm: Optional[Any] = None
    cypher_generator: Optional[Any] = None

    def __init__(self, project_id: Optional[str] = None, llm=None, **kwargs):
        super().__init__(project_id=project_id, llm=llm, cypher_generator=None, **kwargs)
        self._client = None
        self.cypher_generator = CypherGenerator()

    def _get_client(self):
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
        try:
            strategy = self._route(query)
            if strategy == "semantic_only":
                return self._query_vectors(query)
            elif strategy == "graph_only":
                return self._query_graph(query)
            else:
                rag = self._query_vectors(query)
                graph = self._query_graph(query)
                return self._synthesize(query, rag, graph)
        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            return f"Hybrid search error: {str(e)}"

    def _route(self, query: str) -> str:
        q = query.lower()
        graph_kw = ["connected", "depends on", "relationship", "dependencies", "how many", "count", "find all", "what connects"]
        sem_kw = ["explain", "describe", "what is", "how to", "why", "when", "documentation", "details", "information about"]
        g = sum(1 for k in graph_kw if k in q)
        s = sum(1 for k in sem_kw if k in q)
        if g > s and g > 0: return "graph_only"
        if s > g and s > 0: return "semantic_only"
        return "hybrid"

    def _query_vectors(self, query: str) -> str:
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

    def _query_graph(self, query: str) -> str:
        client = self._get_client()
        if not client:
            return "Graph service client not available"
        import anyio
        async def _search():
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

    def _synthesize(self, query: str, rag_results: str, graph_results: str) -> str:
        out = f"# Hybrid Search Results for: {query}\n\n"
        out += "## Semantic Search Results (RAG):\n"
        out += (f"{rag_results}\n\n" if rag_results and "error" not in rag_results.lower() else f"⚠️ {rag_results}\n\n")
        out += "## Graph Database Results:\n"
        out += (f"{graph_results}\n\n" if graph_results and "error" not in graph_results.lower() and "not available" not in graph_results.lower() else f"⚠️ {graph_results}\n\n")
        out += "## Summary:\n"
        if "error" not in rag_results.lower() and "error" not in graph_results.lower():
            out += "Successfully retrieved information from both semantic search and graph database."
        else:
            out += "Partial results retrieved. Some services may be unavailable."
        return out
