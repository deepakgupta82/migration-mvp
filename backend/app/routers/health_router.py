import os, json, requests, subprocess, logging, time
from datetime import datetime
from fastapi import APIRouter, HTTPException, Response
from app.core.project_service import get_llm_configurations_from_db, get_project_service
from app.core.rag_service import RAGService  # optional future checks
import socket
import asyncio
from typing import Dict, Any, List

logger = logging.getLogger("platform.health_router")

# Service start time for uptime calculation
SERVICE_START_TIME = time.time()

router = APIRouter(tags=["health"])

# Simple in-memory cache for health endpoints
_health_cache: Dict[str, Any] = {"data": None, "ts": 0.0}
_containers_cache: Dict[str, Any] = {"data": None, "ts": 0.0}
_HEALTH_TTL_SEC = max(60.0, float(os.getenv("HEALTH_CACHE_TTL_SEC", os.getenv("HEALTH_POLL_INTERVAL_SEC", "60"))))
_CONTAINERS_TTL_SEC = max(60.0, float(os.getenv("CONTAINERS_CACHE_TTL_SEC", os.getenv("CONTAINERS_POLL_INTERVAL_SEC", "60"))))
_PROBE_HTTP_TIMEOUT = float(os.getenv("HEALTH_PROBE_HTTP_TIMEOUT_SEC", "2.5"))  # keep HTTP checks snappy
_PROBE_TCP_TIMEOUT = float(os.getenv("HEALTH_PROBE_TCP_TIMEOUT_SEC", "1.0"))   # fast TCP fallback
import time

async def check_basic_dependencies():
    """Check basic dependencies for readiness"""
    dependencies = {}

    # Check PostgreSQL
    try:
        pg_host = os.getenv("POSTGRES_HOST", "localhost")
        pg_port = int(os.getenv("POSTGRES_PORT", "5432"))
        with socket.create_connection((pg_host, pg_port), timeout=_PROBE_TCP_TIMEOUT):
            dependencies["postgresql"] = "healthy"
    except Exception as e:
        dependencies["postgresql"] = "unhealthy"

    return dependencies

@router.get("/livez")
async def liveness_check():
    """Liveness probe - checks if service is running"""
    return {
        "status": "healthy",
        "service": "api-gateway",
        "uptime": int(time.time() - SERVICE_START_TIME),
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

@router.get("/healthz")
async def readiness_check():
    """Readiness probe - checks if service is ready to accept traffic"""
    dependencies = await check_basic_dependencies()

    # Determine overall status
    overall_status = "healthy" if all(status == "healthy" for status in dependencies.values()) else "unhealthy"

    return {
        "status": overall_status,
        "service": "api-gateway",
        "uptime": int(time.time() - SERVICE_START_TIME),
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "dependencies": dependencies
    }

async def get_services_from_registry() -> Dict[str, Any]:
    """Get service status from the service registry if available"""
    try:
        service_registry_url = os.getenv("SERVICE_REGISTRY_URL", "http://localhost:8011")
        response = requests.get(f"{service_registry_url}/services", timeout=_PROBE_HTTP_TIMEOUT)
        if response.ok:
            data = response.json()
            # Transform service registry data to our format
            services_status = {}
            services_data = data.get("services", {})

            logger.debug(f"Service registry returned {len(services_data)} services")

            # Process services from the registry
            for service_name, service_info in services_data.items():
                # Skip decommissioned services
                if service_name == "reporting-service":
                    logger.info("Skipping decommissioned service from registry: reporting-service")
                    continue
                status = service_info.get("status", "unknown")

                # Map service registry status to our format
                if status in ["healthy", "up", "running"]:
                    mapped_status = "connected"
                elif status in ["timeout"]:
                    # Treat timeout as degraded but still functional
                    mapped_status = "connected"
                elif status in ["unhealthy", "error", "down"]:
                    mapped_status = "error"
                else:
                    mapped_status = "unknown"

                # Only add application services; containers are handled separately
                normalized_name = service_name.replace("-", "_")
                for key in {service_name, normalized_name}:
                    services_status[key] = mapped_status

                # Map specific service names for frontend compatibility
                if service_name == "project-service":
                    services_status["project"] = mapped_status
                    services_status["project_service"] = mapped_status
                elif service_name == "document-service":
                    services_status["document"] = mapped_status
                    services_status["document_service"] = mapped_status
                elif service_name == "vector-service":
                    services_status["vector"] = mapped_status
                    services_status["vector_service"] = mapped_status
                elif service_name == "graph-service":
                    services_status["graph"] = mapped_status
                    services_status["graph_service"] = mapped_status
                elif service_name == "llm-service":
                    services_status["llm"] = mapped_status
                    services_status["llm_service"] = mapped_status
                elif service_name == "ai-agent-service":
                    services_status["ai_agent"] = mapped_status
                    services_status["ai_agent_service"] = mapped_status
                elif service_name == "websocket-service":
                    services_status["websocket"] = mapped_status
                    services_status["websocket_service"] = mapped_status
                elif service_name == "storage-service":
                    services_status["storage"] = mapped_status
                    services_status["storage_service"] = mapped_status
                elif service_name == "service-registry":
                    services_status["service_registry"] = mapped_status
                elif service_name == "cloud-tools-service":
                    services_status["cloud_tools"] = mapped_status
                    services_status["cloud_tools_service"] = mapped_status
                elif service_name == "analytics-service":
                    services_status["analytics"] = mapped_status
                    services_status["analytics_service"] = mapped_status
                elif service_name == "security-service":
                    services_status["security"] = mapped_status
                    services_status["security_service"] = mapped_status
                elif service_name == "collaboration-service":
                    services_status["collaboration"] = mapped_status
                    services_status["collaboration_service"] = mapped_status
                elif service_name == "knowledge-service":
                    services_status["knowledge"] = mapped_status
                    services_status["knowledge_service"] = mapped_status
                elif service_name == "aws-data-service":
                    services_status["aws_data"] = mapped_status
                    services_status["aws_data_service"] = mapped_status
                elif service_name == "data-importer-service":
                    services_status["data_importer"] = mapped_status
                    services_status["data_importer_service"] = mapped_status

                logger.debug(f"Mapped service: {service_name} (status: {status}) -> {mapped_status}")

            logger.info(
                f"Service registry integration: {len(services_status)} service mappings from {len(services_data)} registry entries"
            )
            return services_status
    except Exception as e:
        logger.debug(f"Service registry unavailable: {e}")
    return {}


@router.get("/health", summary="Comprehensive platform health")
async def health_check(response: Response):
    """Return simplified service status map (for UI) plus detailed diagnostics.

    services: mapping of service -> 'connected' | 'error' | 'unknown'
    details: per-service rich diagnostics (legacy shape retained here)
    """
    # Serve from cache if fresh
    now = time.time()
    if _health_cache["data"] is not None and (now - _health_cache["ts"]) < _HEALTH_TTL_SEC:
        response.headers["Cache-Control"] = f"public, max-age={int(_HEALTH_TTL_SEC)}"
        return _health_cache["data"]

    overall_status = "healthy"
    services_simple = {}
    details = {}
    timestamp = datetime.now().isoformat()

    # Always report backend as running if this route is hit
    services_simple["backend"] = "connected"
    details["backend"] = {"status": "up", "timestamp": timestamp}

    # First, try to get services from the service registry
    registry_services = await get_services_from_registry()
    services_simple.update(registry_services)

    # Add details for registry services
    for name, status in registry_services.items():
        details[name] = {
            "status": "up" if status == "connected" else "down",
            "source": "service_registry",
            "timestamp": timestamp
        }

    # Special handling for backend since it should always show as connected if this endpoint responds
    services_simple["backend"] = "connected"
    details["backend"] = {"status": "up", "timestamp": timestamp, "source": "direct"}

    # Proactively direct-check application services if registry indicates unknown/error (to avoid 2+ min lag)
    # Build service URLs from env (fallback to local defaults)
    svc_urls = {
        # Use liveness endpoints for fast "running" indication without dependency coupling
        "project-service": f"{os.getenv('PROJECT_SERVICE_URL', 'http://localhost:8002')}/livez",
        "document-service": f"{os.getenv('DOCUMENT_SERVICE_URL', 'http://localhost:8003')}/livez",
        "vector-service": f"{os.getenv('VECTOR_SERVICE_URL', 'http://localhost:8005')}/livez",
        "graph-service": f"{os.getenv('GRAPH_SERVICE_URL', 'http://localhost:8006')}/livez",
        "llm-service": f"{os.getenv('LLM_SERVICE_URL', 'http://localhost:8007')}/livez",
        "ai-agent-service": f"{os.getenv('AI_AGENT_SERVICE_URL', 'http://localhost:8008')}/livez",
        "websocket-service": f"{os.getenv('WEBSOCKET_SERVICE_URL', 'http://localhost:8009')}/livez",
        "storage-service": f"{os.getenv('STORAGE_SERVICE_URL', 'http://localhost:8010')}/livez",
        "service-registry": f"{os.getenv('SERVICE_REGISTRY_URL', 'http://localhost:8011')}/health",
        "cloud-tools-service": f"{os.getenv('CLOUD_TOOLS_SERVICE_URL', 'http://localhost:8012')}/health",
        "analytics-service": f"{os.getenv('ANALYTICS_SERVICE_URL', 'http://localhost:8014')}/livez",
        "security-service": f"{os.getenv('SECURITY_SERVICE_URL', 'http://localhost:8015')}/livez",
        "collaboration-service": f"{os.getenv('COLLABORATION_SERVICE_URL', 'http://localhost:8016')}/livez",
        "knowledge-service": f"{os.getenv('KNOWLEDGE_SERVICE_URL', 'http://localhost:8017')}/livez",
    }

    # synonyms mapping for consistent keys
    def set_status_for_keys(base: str, status: str):
        keys = {base, base.replace('-', '_'), base.split('-')[0] if '-' in base else base}
        for k in keys:
            services_simple[k] = status
            details[k] = {"status": "up" if status == "connected" else ("down" if status == "error" else status), "source": "direct_or_registry", "timestamp": timestamp}

    for base, url in svc_urls.items():
        # If not present, or present but not connected, try a quick direct check
        existing = services_simple.get(base) or services_simple.get(base.replace('-', '_')) or services_simple.get(base.split('-')[0] if '-' in base else base)
        if existing != "connected":
            try:
                r = requests.get(url, timeout=_PROBE_HTTP_TIMEOUT)
                if r.ok:
                    set_status_for_keys(base, "connected")
                else:
                    # preserve error state if registry reported error, otherwise mark as error
                    set_status_for_keys(base, services_simple.get(base, "error"))
                    if overall_status != "degraded":
                        overall_status = "degraded"
            except Exception:
                # leave as-is but record detail
                status_now = services_simple.get(base, "error")
                set_status_for_keys(base, status_now)
                if status_now == "error" and overall_status != "degraded":
                    overall_status = "degraded"

    # TCP port fallback: if still not connected, try a 1s TCP connection to the known port
    tcp_ports = {
        "project-service": int(os.getenv('PROJECT_SERVICE_PORT', '8002')),
        "document-service": int(os.getenv('DOCUMENT_SERVICE_PORT', '8003')),
        "vector-service": int(os.getenv('VECTOR_SERVICE_PORT', '8005')),
        "graph-service": int(os.getenv('GRAPH_SERVICE_PORT', '8006')),
        "llm-service": int(os.getenv('LLM_SERVICE_PORT', '8007')),
        "ai-agent-service": int(os.getenv('AI_AGENT_SERVICE_PORT', '8008')),
        "websocket-service": int(os.getenv('WEBSOCKET_SERVICE_PORT', '8009')),
        "storage-service": int(os.getenv('STORAGE_SERVICE_PORT', '8010')),
        "service-registry": int(os.getenv('SERVICE_REGISTRY_PORT', '8011')),
        "cloud-tools-service": int(os.getenv('CLOUD_TOOLS_SERVICE_PORT', '8012')),
        "analytics-service": int(os.getenv('ANALYTICS_SERVICE_PORT', '8014')),
        "security-service": int(os.getenv('SECURITY_SERVICE_PORT', '8015')),
        "collaboration-service": int(os.getenv('COLLABORATION_SERVICE_PORT', '8016')),
        "knowledge-service": int(os.getenv('KNOWLEDGE_SERVICE_PORT', '8017')),
    }
    for base, port in tcp_ports.items():
        # consider alternate keys
        keys = [base, base.replace('-', '_'), base.split('-')[0] if '-' in base else base]
        current = None
        for k in keys:
            if k in services_simple:
                current = services_simple[k]
                break
        if current == "connected":
            continue
        try:
            with socket.create_connection(("localhost", port), timeout=_PROBE_TCP_TIMEOUT):
                for k in keys:
                    services_simple[k] = "connected"
                    details[k] = {"status": "up", "source": "tcp_fallback", "timestamp": timestamp}
        except Exception:
            # leave as is
            pass

    # Handle missing services that are expected by frontend but not in service registry
    expected_services = {
        "service_registry": "http://localhost:8011/health",
        "cloud_tools": "http://localhost:8012/health"
    }

    for service_key, health_url in expected_services.items():
        if service_key not in services_simple and service_key.replace("_", "-") not in services_simple:
            try:
                r = requests.get(health_url, timeout=_PROBE_HTTP_TIMEOUT)
                if r.ok:
                    services_simple[service_key] = "connected"
                    details[service_key] = {"status": "up", "source": "direct_check"}
                else:
                    services_simple[service_key] = "error"
                    details[service_key] = {"status": "error", "code": r.status_code}
            except Exception as e:
                services_simple[service_key] = "unknown"
                details[service_key] = {"status": "unknown", "error": str(e)}

    # Only check services directly if they're not already reported by the service registry
    # or for core infrastructure services that may not be in the registry

    # Project Service (only if not in registry)
    if "project-service" not in services_simple and "project_service" not in services_simple and "project" not in services_simple:
        project_service_url = os.getenv("PROJECT_SERVICE_URL", "http://localhost:8002")
        try:
            # Propagate correlation ID if present
            headers = {}
            try:
                from app.core.logging_config import correlation_id_ctx
                cid = correlation_id_ctx.get("-")
                if cid and cid != "-":
                    headers["X-Correlation-ID"] = cid
            except Exception:
                pass
            r = requests.get(f"{project_service_url}/livez", timeout=_PROBE_HTTP_TIMEOUT, headers=headers or None)
            if r.ok:
                services_simple["project_service"] = "connected"
                try:
                    details["project_service"] = r.json()
                except Exception:
                    details["project_service"] = {"status": "up"}
            else:
                services_simple["project_service"] = "error"
                details["project_service"] = {"status": "error", "code": r.status_code}
                overall_status = "degraded"
        except Exception as e:
            services_simple["project_service"] = "error"
            details["project_service"] = {"status": "down", "error": str(e)}
            overall_status = "degraded"

    # Graph service (only if not in registry)
    if "graph-service" not in services_simple and "graph_service" not in services_simple and "graph" not in services_simple:
        graph_service_url = os.getenv("GRAPH_SERVICE_URL", "http://localhost:8006")
        try:
            headers = {}
            try:
                from app.core.logging_config import correlation_id_ctx
                cid = correlation_id_ctx.get("-")
                if cid and cid != "-":
                    headers["X-Correlation-ID"] = cid
            except Exception:
                pass
            r = requests.get(f"{graph_service_url}/livez", timeout=_PROBE_HTTP_TIMEOUT, headers=headers or None)
            if r.ok:
                services_simple["graph_service"] = "connected"
                try:
                    details["graph_service"] = r.json()
                except Exception:
                    details["graph_service"] = {"status": "up"}
            else:
                services_simple["graph_service"] = "error"
                details["graph_service"] = {"status": "error", "code": r.status_code}
                overall_status = "degraded"
        except Exception as e:
            services_simple["graph_service"] = "error"
            details["graph_service"] = {"status": "down", "error": str(e)}
            overall_status = "degraded"

    # Vector service (only if not in registry)
    if "vector-service" not in services_simple and "vector_service" not in services_simple and "vector" not in services_simple:
        vector_service_url = os.getenv("VECTOR_SERVICE_URL", "http://localhost:8005")
        try:
            headers = {}
            try:
                from app.core.logging_config import correlation_id_ctx
                cid = correlation_id_ctx.get("-")
                if cid and cid != "-":
                    headers["X-Correlation-ID"] = cid
            except Exception:
                pass
            r = requests.get(f"{vector_service_url}/livez", timeout=_PROBE_HTTP_TIMEOUT, headers=headers or None)
            if r.ok:
                services_simple["vector_service"] = "connected"
                try:
                    details["vector_service"] = r.json()
                except Exception:
                    details["vector_service"] = {"status": "up"}
            else:
                services_simple["vector_service"] = "error"
                details["vector_service"] = {"status": "error", "code": r.status_code}
                overall_status = "degraded"
        except Exception as e:
            services_simple["vector_service"] = "error"
            details["vector_service"] = {"status": "down", "error": str(e)}
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


    # Infra: PostgreSQL
    try:
        pg_host = os.getenv("POSTGRES_HOST", "localhost")
        pg_port = int(os.getenv("POSTGRES_PORT", "5432"))
        with socket.create_connection((pg_host, pg_port), timeout=_PROBE_TCP_TIMEOUT):
            services_simple["postgresql"] = "connected"
            details["postgresql"] = {"status": "up", "host": pg_host, "port": pg_port}
    except Exception as e:
        services_simple["postgresql"] = "error"
        details["postgresql"] = {"status": "down", "error": str(e)}
        overall_status = "degraded"

    # Infra: MinIO
    try:
        minio_host = os.getenv("MINIO_HOST", "localhost")
        minio_port = int(os.getenv("MINIO_PORT", "9000"))
        with socket.create_connection((minio_host, minio_port), timeout=_PROBE_TCP_TIMEOUT):
            services_simple["minio"] = "connected"
            details["minio"] = {"status": "up", "host": minio_host, "port": minio_port}
    except Exception as e:
        services_simple["minio"] = "error"
        details["minio"] = {"status": "down", "error": str(e)}
        overall_status = "degraded"

    # Infra: Redis (optional)
    try:
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        with socket.create_connection((redis_host, redis_port), timeout=_PROBE_TCP_TIMEOUT):
            services_simple["redis"] = "connected"
            details["redis"] = {"status": "up", "host": redis_host, "port": redis_port}
    except Exception as e:
        # Do not degrade overall if redis is optional; mark error only
        services_simple["redis"] = "error"
        details["redis"] = {"status": "down", "error": str(e)}

    # Infra: Neo4j (only if not already from containers)
    if "neo4j" not in services_simple:
        try:
            neo4j_host = os.getenv("NEO4J_HOST", "localhost")
            neo4j_port = int(os.getenv("NEO4J_BOLT_PORT", "7687"))
            with socket.create_connection((neo4j_host, neo4j_port), timeout=_PROBE_TCP_TIMEOUT):
                services_simple["neo4j"] = "connected"
                details["neo4j"] = {"status": "up", "host": neo4j_host, "port": neo4j_port}
        except Exception as e:
            services_simple["neo4j"] = "error"
            details["neo4j"] = {"status": "down", "error": str(e)}
            overall_status = "degraded"

    # Infra: Weaviate (only if not already from containers)
    if "weaviate" not in services_simple:
        try:
            weaviate_url = os.getenv("WEAVIATE_URL", "http://localhost:8080")
            r = requests.get(f"{weaviate_url}/v1/meta", timeout=_PROBE_HTTP_TIMEOUT)
            if r.ok:
                services_simple["weaviate"] = "connected"
                details["weaviate"] = {"status": "up", "url": weaviate_url}
            else:
                services_simple["weaviate"] = "error"
                details["weaviate"] = {"status": "error", "code": r.status_code}
                overall_status = "degraded"
        except Exception as e:
            services_simple["weaviate"] = "error"
            details["weaviate"] = {"status": "down", "error": str(e)}
            overall_status = "degraded"

    # Infra: Loki (HTTP API)
    try:
        loki_url = os.getenv("LOKI_URL", "http://localhost:3100")
        r = requests.get(f"{loki_url}/ready", timeout=_PROBE_HTTP_TIMEOUT)
        if r.ok:
            services_simple["loki"] = "connected"
            details["loki"] = {"status": "up", "url": loki_url}
        else:
            services_simple["loki"] = "error"
            details["loki"] = {"status": "error", "code": r.status_code}
            overall_status = "degraded"
    except Exception as e:
        services_simple["loki"] = "error"
        details["loki"] = {"status": "down", "error": str(e)}
        overall_status = "degraded"

    # Infra: Promtail (optional; check local port default 9080 metrics)
    try:
        promtail_host = os.getenv("PROMTAIL_HOST", "localhost")
        promtail_port = int(os.getenv("PROMTAIL_PORT", "9080"))
        with socket.create_connection((promtail_host, promtail_port), timeout=_PROBE_TCP_TIMEOUT):
            services_simple["promtail"] = "connected"
            details["promtail"] = {"status": "up", "host": promtail_host, "port": promtail_port}
    except Exception as e:
        services_simple["promtail"] = "error"
        details["promtail"] = {"status": "down", "error": str(e)}

    # Derive overall status escalation if any 'error'
    if any(v == "error" for v in services_simple.values() if v):
        # If more than half are error -> unhealthy
        error_count = sum(1 for v in services_simple.values() if v == "error")
        total = len(services_simple)
        if error_count > total / 2:
            overall_status = "unhealthy"
        elif overall_status != "degraded":
            overall_status = "degraded"

    result = {
        "status": overall_status,
        "services": services_simple,  # UI consumes this
        "details": details,          # rich diagnostics retained
        "timestamp": timestamp
    }
    _health_cache["data"] = result
    _health_cache["ts"] = now
    response.headers["Cache-Control"] = f"public, max-age={int(_HEALTH_TTL_SEC)}"
    return result

# Provide a non-conflicting path for internal callers (e.g., gateway) to avoid route alias collisions
@router.get("/health/aggregate", include_in_schema=False)
async def health_check_aggregate(response: Response):
    return await health_check(response)

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
async def container_stats(response: Response):
    """Return container/service runtime stats if docker is available.

    Shape per item:
      { name, status, cpu_percent, memory_usage, memory_limit, network_io, block_io }
    """
    # Expanded list to include all platform-relevant containers
    wanted_services = {
        # Infrastructure services
        "neo4j", "minio", "loki", "promtail", "redis", "postgresql", "weaviate",
        # Platform services that might run in containers
    "backend", "project-service", "document-service", 
        "vector-service", "graph-service", "llm-service", "ai-agent-service",
        "websocket-service", "storage-service", "analytics-service", "security-service",
        "collaboration-service", "knowledge-service", "service-registry", "cloud-tools-service"
    }
    stats: dict = {}
    containers: list = []
    now_iso = datetime.now().isoformat()
    # Serve from cache if fresh
    now = time.time()
    if _containers_cache["data"] is not None and (now - _containers_cache["ts"]) < _CONTAINERS_TTL_SEC:
        response.headers["Cache-Control"] = f"public, max-age={int(_CONTAINERS_TTL_SEC)}"
        return _containers_cache["data"]

    try:
        # Use docker CLI to avoid extra Python deps. Works in Docker Desktop.
        # 1) docker ps to map name -> status and compose service label
        ps_cmd = ["docker", "ps", "--format", "{{.Names}}||{{.Status}}||{{.Label \"com.docker.compose.service\"}}"]
        ps_out = subprocess.check_output(ps_cmd, text=True, stderr=subprocess.DEVNULL)
        name_to_info = {}
        for line in (ps_out or "").splitlines():
            try:
                name, status, svc = line.split("||")
                name_to_info[name] = {"status": status, "svc": (svc or "").strip()}
            except ValueError:
                continue

        # 2) docker stats for CPU/MEM/IO
        st_cmd = [
            "docker", "stats", "--no-stream", "--format",
            "{{.Name}}||{{.CPUPerc}}||{{.MemUsage}}||{{.NetIO}}||{{.BlockIO}}"
        ]
        st_out = subprocess.check_output(st_cmd, text=True, stderr=subprocess.DEVNULL)
        for line in (st_out or "").splitlines():
            try:
                name, cpu, mem, netio, blockio = line.split("||")
            except ValueError:
                continue
            info = name_to_info.get(name, {"status": "unknown", "svc": ""})
            # Skip Kubernetes containers entirely
            if name.lower().startswith("k8s_") or "kube-system" in name.lower():
                continue
            # Normalize service name preference: label service, else container base name
            svc_label = (info.get("svc") or "").lower()
            base_name = name.lower()
            # Map common compose names to canonical service keys
            canonical = svc_label or base_name
            if canonical.startswith("postgres"):
                canonical = "postgresql"
            elif canonical.startswith("migration-platform") or canonical.startswith("migration_platform"):
                # Extract service name from migration platform containers
                parts = canonical.replace("-", "_").split("_")
                if len(parts) >= 3:  # migration_platform_servicename
                    canonical = parts[2]
            
            # Include more containers - less restrictive filtering
            # Only exclude if it's clearly not platform-related
            exclude_patterns = ["k8s_", "kube-system", "rancher", "docker", "registry"]
            should_exclude = any(pattern in canonical.lower() for pattern in exclude_patterns)
            
            if should_exclude:
                continue
            # Parse CPU percent to number
            try:
                cpu_num = float(cpu.strip().replace('%', ''))
            except Exception:
                cpu_num = 0.0

            # Split mem usage like "123MiB / 1GiB"
            mem_usage = mem
            mem_limit = ""
            if "/" in mem:
                parts = [p.strip() for p in mem.split("/")]
                if len(parts) == 2:
                    mem_usage, mem_limit = parts

            # Only keep infrastructure containers here; application services will be shown in left section via registry/back-end health
            infra_whitelist = {"neo4j", "minio", "loki", "promtail", "redis", "postgresql", "weaviate"}
            if canonical not in infra_whitelist:
                continue

            entry = {
                "name": canonical,
                "status": "running" if "Up" in info.get("status", "") else ("restarting" if "Restarting" in info.get("status", "") else "exited"),
                "cpu_percent": cpu_num,
                "memory_usage": mem_usage,
                "memory_limit": mem_limit,
                "network_io": netio,
                "block_io": blockio,
            }
            stats[canonical] = entry

        # Ensure we include placeholders for desired infra services even if not in docker stats
        for svc in wanted_services:
            # Only include infra placeholders
            if svc not in {"neo4j", "minio", "loki", "promtail", "redis", "postgresql", "weaviate"}:
                continue
            if svc not in stats:
                # Lightweight TCP/HTTP probe for status where sensible
                status = "exited"
                try:
                    if svc == "postgresql":
                        with socket.create_connection((os.getenv("POSTGRES_HOST", "localhost"), int(os.getenv("POSTGRES_PORT", "5432"))), timeout=_PROBE_TCP_TIMEOUT):
                            status = "running"
                    elif svc == "neo4j":
                        with socket.create_connection((os.getenv("NEO4J_HOST", "localhost"), int(os.getenv("NEO4J_BOLT_PORT", "7687"))), timeout=_PROBE_TCP_TIMEOUT):
                            status = "running"
                    elif svc == "minio":
                        with socket.create_connection((os.getenv("MINIO_HOST", "localhost"), int(os.getenv("MINIO_PORT", "9000"))), timeout=_PROBE_TCP_TIMEOUT):
                            status = "running"
                    elif svc == "loki":
                        r = requests.get(f"{os.getenv('LOKI_URL', 'http://localhost:3100')}/ready", timeout=_PROBE_HTTP_TIMEOUT)
                        status = "running" if r.ok else "exited"
                    elif svc == "promtail":
                        with socket.create_connection((os.getenv("PROMTAIL_HOST", "localhost"), int(os.getenv("PROMTAIL_PORT", "9080"))), timeout=_PROBE_TCP_TIMEOUT):
                            status = "running"
                    elif svc == "redis":
                        with socket.create_connection((os.getenv("REDIS_HOST", "localhost"), int(os.getenv("REDIS_PORT", "6379"))), timeout=_PROBE_TCP_TIMEOUT):
                            status = "running"
                    elif svc == "weaviate":
                        r = requests.get(f"{os.getenv('WEAVIATE_URL', 'http://localhost:8080')}/v1/meta", timeout=_PROBE_HTTP_TIMEOUT)
                        status = "running" if r.ok else "exited"
                except Exception:
                    pass
                stats[svc] = {
                    "name": svc,
                    "status": status,
                    "cpu_percent": 0.0,
                    "memory_usage": "—",
                    "memory_limit": "—",
                    "network_io": "—",
                    "block_io": "—",
                    "additional_info": {"source": "real"}
                }

        # Build final list in a stable order
        order = ["neo4j", "postgresql", "minio", "redis", "loki", "promtail", "weaviate"]
        for key in order:
            if key in stats:
                containers.append(stats[key])
        # Add any other entries not in predefined order
        for key, val in stats.items():
            if key not in order:
                containers.append(val)

    except Exception as e:
        logger.warning(f"Container stats collection issue: {e}")
        # Fallback minimal set
        for name, endpoint in { 
            'neo4j': 'bolt://localhost:7687', 
            'postgresql': 'localhost:5432', 
            'minio': 'localhost:9000',
            'redis': 'localhost:6379',
            'loki': 'http://localhost:3100',
            'promtail': 'localhost:9080',
            'weaviate': 'http://localhost:8080'
        }.items():
            containers.append({
                "name": name,
                "status": "unknown",
                "cpu_percent": 0.0,
                "memory_usage": "—",
                "memory_limit": "—",
                "network_io": "—",
                "block_io": "—",
            })

    result = {"containers": containers, "timestamp": now_iso}
    _containers_cache["data"] = result
    _containers_cache["ts"] = now
    response.headers["Cache-Control"] = f"public, max-age={int(_CONTAINERS_TTL_SEC)}"
    return result
