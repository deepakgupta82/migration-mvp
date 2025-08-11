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
    status = {"status": "healthy", "services": {}, "timestamp": datetime.now().isoformat()}

    # Project Service
    project_service_url = os.getenv("PROJECT_SERVICE_URL", "http://localhost:8002")
    try:
        r = requests.get(f"{project_service_url}/health", timeout=3)
        status["services"]["project_service"] = r.json() if r.ok else {"status": "error", "code": r.status_code}
    except Exception as e:
        status["services"]["project_service"] = {"status": "down", "error": str(e)}
        status["status"] = "degraded"

    # Neo4j
    try:
        g = GraphService()
        g.execute_query("RETURN 1 as ok")
        status["services"]["neo4j"] = {"status": "up"}
    except Exception as e:
        status["services"]["neo4j"] = {"status": "down", "error": str(e)}
        status["status"] = "degraded"

    # Chroma (presence check via path)
    try:
        chroma_path = os.getenv("CHROMA_DB_PATH", "./data/chroma_db")
        status["services"]["chromadb"] = {"status": "present", "path_exists": os.path.exists(chroma_path)}
    except Exception as e:
        status["services"]["chromadb"] = {"status": "error", "error": str(e)}

    # LLM configs
    try:
        llm_configs = get_llm_configurations_from_db()
        status["services"]["llm_configurations"] = {"count": len(llm_configs)}
        if not llm_configs:
            status["status"] = "degraded"
    except Exception as e:
        status["services"]["llm_configurations"] = {"status": "error", "error": str(e)}
        status["status"] = "degraded"

    return status

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

