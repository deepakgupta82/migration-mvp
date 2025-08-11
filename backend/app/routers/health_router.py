import os, json, requests, subprocess, logging
from datetime import datetime
from fastapi import APIRouter, HTTPException
from app.core.project_service import get_llm_configurations_from_db, get_project_service
from app.core.graph_service import GraphService
from app.core.rag_service import RAGService  # optional future checks

logger = logging.getLogger("platform.health_router")

router = APIRouter(tags=["health"])

@router.get("/health", summary="Comprehensive platform health")
async def health_check():
    """Return simplified service status map (for UI) plus detailed diagnostics.

    services: mapping of service -> 'connected' | 'error' | 'unknown'
    details: per-service rich diagnostics (legacy shape retained here)
    """
    overall_status = "healthy"
    services_simple = {}
    details = {}
    timestamp = datetime.now().isoformat()

    # Always report backend as running if this route is hit
    services_simple["backend"] = "connected"
    details["backend"] = {"status": "up", "timestamp": timestamp}

    # Project Service
    project_service_url = os.getenv("PROJECT_SERVICE_URL", "http://localhost:8002")
    try:
        r = requests.get(f"{project_service_url}/health", timeout=3)
        if r.ok:
            services_simple["project_service"] = "connected"
            details["project_service"] = r.json()
        else:
            services_simple["project_service"] = "error"
            details["project_service"] = {"status": "error", "code": r.status_code}
            overall_status = "degraded"
    except Exception as e:
        services_simple["project_service"] = "error"
        details["project_service"] = {"status": "down", "error": str(e)}
        overall_status = "degraded"

    # Neo4j
    try:
        g = GraphService()
        g.execute_query("RETURN 1 as ok")
        services_simple["neo4j"] = "connected"
        details["neo4j"] = {"status": "up"}
    except Exception as e:
        services_simple["neo4j"] = "error"
        details["neo4j"] = {"status": "down", "error": str(e)}
        overall_status = "degraded"

    # Chroma (presence check via path)
    try:
        chroma_path = os.getenv("CHROMA_DB_PATH", "./data/chroma_db")
        path_exists = os.path.exists(chroma_path)
        services_simple["chromadb"] = "connected" if path_exists else "error"
        details["chromadb"] = {"status": "present" if path_exists else "missing", "path_exists": path_exists, "path": chroma_path}
        if not path_exists:
            overall_status = "degraded"
    except Exception as e:
        services_simple["chromadb"] = "error"
        details["chromadb"] = {"status": "error", "error": str(e)}
        overall_status = "degraded"

    # LLM configs
    try:
        llm_configs = get_llm_configurations_from_db()
        count = len(llm_configs)
        services_simple["llm_configurations"] = "connected" if count > 0 else "error"
        details["llm_configurations"] = {"count": count}
        if count == 0:
            overall_status = "degraded"
    except Exception as e:
        services_simple["llm_configurations"] = "error"
        details["llm_configurations"] = {"status": "error", "error": str(e)}
        overall_status = "degraded"

    # Placeholder reporting service (not yet implemented)
    if "reporting_service" not in services_simple:
        services_simple["reporting_service"] = "unknown"
        details["reporting_service"] = {"status": "unimplemented"}

    # Derive overall status escalation if any 'error'
    if any(v == "error" for v in services_simple.values() if v):
        # If more than half are error -> unhealthy
        error_count = sum(1 for v in services_simple.values() if v == "error")
        total = len(services_simple)
        if error_count > total / 2:
            overall_status = "unhealthy"
        elif overall_status != "degraded":
            overall_status = "degraded"

    return {
        "status": overall_status,
        "services": services_simple,  # UI consumes this
        "details": details,          # rich diagnostics retained
        "timestamp": timestamp
    }

@router.get("/health/llm-configurations", summary="LLM configuration health")
async def llm_configurations_health():
    try:
        llm_configs = get_llm_configurations_from_db()
        if not llm_configs:
            return {"status": "critical", "message": "No LLM configurations found", "count": 0, "timestamp": datetime.now().isoformat()}
        configured = [c for c in llm_configs.values() if c.get('api_key') and c.get('api_key') != 'your-api-key-here']
        if not configured:
            return {"status": "warning", "message": "No valid API keys", "count": len(llm_configs), "configured_count": 0, "timestamp": datetime.now().isoformat()}
        return {"status": "healthy", "count": len(llm_configs), "configured_count": len(configured), "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"LLM config health error: {e}")
        return {"status": "critical", "message": str(e), "count": 0, "timestamp": datetime.now().isoformat()}

@router.get("/health/containers", summary="Container / service stats (lightweight)")
async def container_stats():
    container_stats = []
    try:
        # Fallback basic connectivity summary (avoid heavy docker dependency if not available)
        services = { 'neo4j': 'bolt://localhost:7687', 'postgresql': 'localhost:5432', 'minio': 'localhost:9000'}
        for name, endpoint in services.items():
            container_stats.append({"service": name, "endpoint": endpoint})
    except Exception as e:
        logger.warning(f"Container stats collection issue: {e}")
    return {"containers": container_stats, "timestamp": datetime.now().isoformat()}

