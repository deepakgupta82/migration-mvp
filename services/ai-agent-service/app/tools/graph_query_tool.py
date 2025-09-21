"""
Graph Query Tool for ai-agent-service
Delegates to graph-service via local ServiceClient.
"""
from crewai.tools import BaseTool
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class GraphQueryTool(BaseTool):
    name: str = "Project Graph Database Query Tool"
    description: str = (
        "Query the graph via supported commands: \n"
        "- nodes <substring> [--type Type] [--limit N]\n"
        "- relationships [--type REL] [--limit N]\n"
        "- neighborhood <node_id> [--depth D] [--direction out|in|both] [--types R1,R2] [--limit N]\n"
        "- count nodes [--type Type]\n"
        "- count servers --os <substring>"
    )
    project_id: Optional[str] = None

    def __init__(self, project_id: Optional[str] = None, **kwargs):
        super().__init__(project_id=project_id, **kwargs)
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from app.core.service_client import get_service_client_sync
                self._client = get_service_client_sync()
            except Exception as e:
                logger.error(f"GraphQueryTool: failed to init service client: {e}")
                self._client = None
        return self._client

    class Config:
        arbitrary_types_allowed = True

    def run(self, query: str) -> str:
        try:
            if not self.project_id:
                return "GraphQueryTool error: project_id not set"
            client = self._get_client()
            if not client:
                return "Graph service client not available"
            cmd = (query or "").strip()
            if not cmd:
                return "Provide a command: nodes|relationships|neighborhood"
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
                        if "_" not in out:
                            out["_"] = t
                        i += 1
                return out

            if verb == "nodes":
                f = parse_flags(args)
                q = f.get("_") or ""
                node_type = f.get("type")
                limit = int(f.get("limit", "10"))
                res = client.search_graph_nodes(self.project_id, q, node_type=node_type, limit=limit)
                results = (res or {}).get("results", [])
                if not results:
                    return "No matching nodes"
                return "\n".join([f"- {n.get('name')} ({n.get('type') or ','.join(n.get('labels', []) or [])})" for n in results])

            if verb in ("relationships", "rels"):
                f = parse_flags(args)
                rel_type = f.get("type")
                limit = int(f.get("limit", "20"))
                res = client.search_graph_relationships(self.project_id, rel_type=rel_type, limit=limit)
                results = (res or {}).get("results", [])
                if not results:
                    return "No relationships found"
                return "\n".join([f"- {r.get('source_name')} -[{r.get('type')}]-> {r.get('target_name')}" for r in results])

            if verb in ("neighborhood", "nbr"):
                f = parse_flags(args)
                node_id = f.get("_")
                if not node_id:
                    return "Usage: neighborhood <node_id> [--depth D] [--direction out|in|both] [--types R1,R2] [--limit N]"
                depth = int(f.get("depth", "1"))
                direction = f.get("direction", "both")
                rel_types = f.get("types")
                rel_list = [s.strip().upper() for s in rel_types.split(',')] if rel_types else None
                limit = int(f.get("limit", "200"))
                res = client.get_graph_neighborhood(self.project_id, node_id, depth=depth, direction=direction, rel_types=rel_list, limit=limit)
                nodes = (res or {}).get("nodes", [])
                rels = (res or {}).get("relationships", [])
                lines = [f"Nodes: {len(nodes)} | Relationships: {len(rels)}"]
                for n in nodes[:20]:
                    lines.append(f"- {n.get('name')} ({n.get('type')})")
                if len(nodes) > 20:
                    lines.append(f"... and {len(nodes)-20} more nodes")
                return "\n".join(lines)

            if verb == "count":
                # Subcommands: nodes [--type T] | servers --os <q>
                f = parse_flags(args)
                sub = f.get("_")
                if not sub:
                    return "Usage: count nodes [--type T] | count servers --os <substring>"
                if sub == "nodes":
                    node_type = f.get("type")
                    res = client.count_graph_nodes(self.project_id, node_type=node_type)
                    cnt = (res or {}).get("count")
                    return f"Count of nodes{(' type '+node_type) if node_type else ''}: {cnt if cnt is not None else 0}"
                if sub == "servers":
                    os_q = f.get("os")
                    if not os_q:
                        return "Usage: count servers --os <substring>"
                    res = client.count_servers_by_os(self.project_id, os_query=os_q)
                    cnt = (res or {}).get("count")
                    return f"Servers matching OS '{os_q}': {cnt if cnt is not None else 0}"
                return "Unsupported count subcommand. Use: nodes | servers"

            return "Unsupported command. Use: nodes|relationships|neighborhood"
        except Exception as e:
            logger.error(f"Error in GraphQueryTool: {e}")
            return f"GraphQueryTool error: {str(e)}"

    def _run(self, query: str) -> str:
        return self.run(query)

    def _arun(self, query: str) -> str:
        return self.run(query)
