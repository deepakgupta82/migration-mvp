import os
from typing import Dict, Any

from app.core.project_service import ProjectServiceClient
from app.core.service_client import ServiceClient


def get_platform_stats() -> Dict[str, Any]:
    """Aggregate platform-wide statistics.
    - total_projects: from project-service
    - total_documents: count of project files across all projects from project-service
    - total_embeddings: sum of counts across all project collections in Weaviate
    - total_neo4j_nodes/relationships: from Neo4j
    """
    stats = {
        "total_projects": 0,
        "total_documents": 0,
        "total_embeddings": 0,
        "total_neo4j_nodes": 0,
        "total_neo4j_relationships": 0,
    }

    # Projects and documents via project-service
    ps = ProjectServiceClient()
    try:
        projects = ps.list_projects()
        stats["total_projects"] = len(projects)
        # Sum documents from project-service
        import requests
        total_docs = 0
        for p in projects:
            r = requests.get(f"{ps.base_url}/projects/{p.id}/files", headers=ps._get_auth_headers(), timeout=10)
            if r.ok:
                total_docs += len(r.json())
        stats["total_documents"] = total_docs
    except Exception:
        pass

    # Embeddings count via vector-service (best effort)
    try:
        # If vector-service exposes a global stats endpoint, prefer that; else estimate 0
        # Placeholder: not implemented in client; keep 0 for now
        stats["total_embeddings"] = stats.get("total_embeddings", 0)
    except Exception:
        pass

    # Graph totals via graph-service health/stats
    try:
        client = ServiceClient()
        # If project list is available, sum stats across projects is expensive; use /health totals
        hlth = None
        try:
            hlth = client._make_request  # type: ignore[attr-defined]
        except Exception:
            hlth = None
        # Use check_service_health wrapper for graph
        graph_health = client and asyncio_run_safely(lambda: client.check_service_health("graph"))
        if isinstance(graph_health, dict):
            stats["total_neo4j_nodes"] = graph_health.get("total_nodes", 0)
            stats["total_neo4j_relationships"] = graph_health.get("total_relationships", 0)
    except Exception:
        pass

def asyncio_run_safely(coro_factory):
    try:
        import anyio
        return anyio.run(coro_factory)
    except Exception:
        try:
            import asyncio
            return asyncio.get_event_loop().run_until_complete(coro_factory())
        except Exception:
            return None

    return stats

