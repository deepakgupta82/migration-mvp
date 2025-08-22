"""
Graph Query Tool - Queries graph-service for relationships and neighborhoods
Now delegates to graph-service via ServiceClient instead of direct Neo4j access.
"""

from crewai.tools import BaseTool
from typing import Optional, Any, Dict
from pydantic import Field
import logging

logger = logging.getLogger(__name__)

class GraphQueryTool(BaseTool):
    """
    A custom tool for the agents to query the project-specific graph database.
    """
    name: str = "Project Graph Database Query Tool"
    description: str = (
        "Query the graph via supported commands: \n"
        "- nodes <substring> [--type Type] [--limit N]\n"
        "- relationships [--type REL] [--limit N]\n"
        "- neighborhood <node_id> [--depth D] [--direction out|in|both] [--types R1,R2] [--limit N]"
    )
    project_id: Optional[str] = None

    def __init__(self, project_id: Optional[str] = None, **kwargs):
        super().__init__(project_id=project_id, **kwargs)
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import anyio
                from app.core.service_client import get_service_client
                async def _get():
                    return await get_service_client()
                self._client = anyio.run(_get)
            except Exception as e:
                logger.error(f"GraphQueryTool: failed to init service client: {e}")
                self._client = None
        return self._client

    class Config:
        arbitrary_types_allowed = True

    def run(self, query: str) -> str:
        """Executes supported graph queries via graph-service."""
        try:
            if not self.project_id:
                return "GraphQueryTool error: project_id not set"
            client = self._get_client()
            if not client:
                return "Graph service client not available"
            cmd = (query or "").strip()
            if not cmd:
                return "Provide a command: nodes|relationships|neighborhood"
            lower = cmd.lower()
            import shlex
            tokens = shlex.split(cmd)
            if not tokens:
                return "Invalid command"
            verb = tokens[0].lower()
            args = tokens[1:]

            def parse_flags(argv: list[str]) -> Dict[str, str]:
                out: Dict[str, str] = {}
                i = 0
                while i < len(argv):
                    t = argv[i]
                    if t.startswith("--") and i + 1 < len(argv):
                        out[t[2:]] = argv[i + 1]
                        i += 2
                    else:
                        # first positional goes to '_'
                        if "_" not in out:
                            out["_"] = t
                        i += 1
                return out

            import anyio

            if verb == "nodes":
                f = parse_flags(args)
                q = f.get("_") or ""
                node_type = f.get("type")
                limit = int(f.get("limit", "10"))
                async def _call():
                    return await client.search_graph_nodes(self.project_id, q, node_type=node_type, limit=limit)
                res = anyio.run(_call)
                results = (res or {}).get("results", [])
                if not results:
                    return "No matching nodes"
                return "\n".join([f"- {n.get('name')} ({n.get('type') or ','.join(n.get('labels', []) or [])})" for n in results])

            if verb == "relationships" or verb == "rels":
                f = parse_flags(args)
                rel_type = f.get("type")
                limit = int(f.get("limit", "20"))
                async def _call():
                    return await client.search_graph_relationships(self.project_id, rel_type=rel_type, limit=limit)
                res = anyio.run(_call)
                results = (res or {}).get("results", [])
                if not results:
                    return "No relationships found"
                return "\n".join([f"- {r.get('source_name')} -[{r.get('type')}]-> {r.get('target_name')}" for r in results])

            if verb == "neighborhood" or verb == "nbr":
                f = parse_flags(args)
                node_id = f.get("_")
                if not node_id:
                    return "Usage: neighborhood <node_id> [--depth D] [--direction out|in|both] [--types R1,R2] [--limit N]"
                depth = int(f.get("depth", "1"))
                direction = f.get("direction", "both")
                rel_types = f.get("types")
                rel_list = [s.strip().upper() for s in rel_types.split(',')] if rel_types else None
                limit = int(f.get("limit", "200"))
                async def _call():
                    return await client.get_graph_neighborhood(self.project_id, node_id, depth=depth, direction=direction, rel_types=rel_list, limit=limit)
                res = anyio.run(_call)
                nodes = (res or {}).get("nodes", [])
                rels = (res or {}).get("relationships", [])
                lines = [f"Nodes: {len(nodes)} | Relationships: {len(rels)}"]
                for n in nodes[:20]:
                    lines.append(f"- {n.get('name')} ({n.get('type')})")
                if len(nodes) > 20:
                    lines.append(f"... and {len(nodes)-20} more nodes")
                return "\n".join(lines)

            return "Unsupported command. Use: nodes|relationships|neighborhood"
        except Exception as e:
            logger.error(f"Error in GraphQueryTool: {e}")
            return f"GraphQueryTool error: {str(e)}"

    def _run(self, query: str) -> str:
        """Legacy method for older CrewAI versions."""
        return self.run(query)

    def _arun(self, query: str) -> str:
        """Async version of _run."""
        return self.run(query)
