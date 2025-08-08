import os
from typing import Dict, Any

from app.core.rag_service import RAGService
from app.core.graph_service import GraphService
from app.core.project_service import ProjectServiceClient


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

    # Weaviate embeddings across all project collections
    try:
        # Connect without LLM; we just need Weaviate client for aggregation
        rag = RAGService(project_id="global", llm=None)
        client = rag.weaviate_client
        if client and client.is_ready():
            # Weaviate v4: list collections
            cols = client.collections.list_all()
            total = 0
            for col in cols:
                try:
                    agg = col.aggregate.over_all(total_count=True)
                    total += agg.total_count or 0
                except Exception:
                    continue
            stats["total_embeddings"] = total
    except Exception:
        pass

    # Neo4j totals
    try:
        g = GraphService()
        res = g.execute_query("MATCH (n) RETURN count(n) AS c")
        if res:
            stats["total_neo4j_nodes"] = res[0].get("c", 0)
        res2 = g.execute_query("MATCH ()-[r]-() RETURN count(r) AS c")
        if res2:
            stats["total_neo4j_relationships"] = res2[0].get("c", 0)
        g.close()
    except Exception:
        pass

    return stats

