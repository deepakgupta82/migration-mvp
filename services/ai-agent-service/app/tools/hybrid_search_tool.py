"""
Hybrid Search Tool for ai-agent-service
Calls vector-service and graph-service via local ServiceClient and synthesizes results.
"""
from crewai.tools import BaseTool
import logging
from typing import Optional, Any
import re

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
                from app.core.service_client import get_service_client_sync
                self._client = get_service_client_sync()
                logger.info("Service client initialized for hybrid search (sync)")
            except Exception as e:
                logger.error(f"Failed to initialize service client: {e}")
                self._client = None
        return self._client

    def _run(self, query: str) -> str:
        try:
            # If the query is an explicit count request, run graph count path directly
            if self._looks_like_count(query):
                cnt = self._run_counts(query)
                return cnt
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

    def _looks_like_count(self, query: str) -> bool:
        q = (query or "").lower()
        return ("how many" in q) or (q.strip().startswith("count ")) or (" count " in q)

    def _run_counts(self, query: str) -> str:
        """Very small parser for count-style questions to call graph count endpoints.
        Examples:
          - how many windows servers -> servers-by-os windows
          - count servers with linux -> servers-by-os linux
          - count server nodes -> nodes type=Server
        """
        client = self._get_client()
        if not client:
            return "Graph service client not available"
        q = (query or "").lower()
        # Heuristic: try OS substring
        os_terms = ["windows", "linux", "ubuntu", "red hat", "rhel", "centos", "suse"]
        os_q = next((t for t in os_terms if t in q), None)
        try:
            if "server" in q and os_q:
                res = client.count_servers_by_os(self.project_id, os_query=os_q)
                cnt = (res or {}).get("count")
                return f"Servers matching OS '{os_q}': {cnt if cnt is not None else 0}"
            # Generic node counts
            if "server" in q:
                res = client.count_graph_nodes(self.project_id, node_type="Server")
                cnt = (res or {}).get("count")
                return f"Count of nodes type Server: {cnt if cnt is not None else 0}"
            # Fallback: total nodes
            res = client.count_graph_nodes(self.project_id, node_type=None)
            cnt = (res or {}).get("count")
            return f"Total node count: {cnt if cnt is not None else 0}"
        except Exception as e:
            logger.error(f"Count path failed: {e}")
            return f"Count error: {str(e)}"

    def _query_vectors(self, query: str) -> str:
        client = self._get_client()
        if not client:
            return "Vector service client not available"
        try:
            res = client.vector_search(self.project_id, query, limit=5)
        except Exception:
            res = client.hybrid_search(self.project_id, query, limit=5)
        snippets = []
        for item in (res or {}).get("results", []) or []:
            content = item.get("content") or item.get("text") or ""
            if not content:
                doc = item.get("document") or {}
                if isinstance(doc, dict):
                    content = doc.get("content") or doc.get("text") or ""
            if content:
                snippets.append(str(content))
        if not snippets:
            return "No semantic results found"
        return "\n\n".join(snippets)

    def _query_graph(self, query: str) -> str:
        client = self._get_client()
        if not client:
            return "Graph service client not available"
        res = client.search_graph_nodes(self.project_id, query, limit=10)
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
