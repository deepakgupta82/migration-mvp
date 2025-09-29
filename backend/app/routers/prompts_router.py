from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from datetime import datetime
import os
import httpx

from app.utils.prompt_store import list_services, list_prompts, get_prompt, validate_prompt, save_prompt
from app.utils.git_utils import git_auto_commit


router = APIRouter(prefix="/api/prompts", tags=["prompts"])


@router.get("/services")
async def get_services():
    return {"services": list_services()}


@router.get("/{service}")
async def get_service_prompts(service: str):
    return {"service": service, "prompts": list_prompts(service)}


@router.get("/{service}/{prompt_id}")
async def get_prompt_by_id(service: str, prompt_id: str):
    data = get_prompt(service, prompt_id)
    if not data:
        raise HTTPException(status_code=404, detail="prompt not found")
    return data


@router.post("/validate")
async def validate(doc: Dict[str, Any]):
    errors = validate_prompt(doc)
    return {"valid": len(errors) == 0, "errors": errors}


@router.put("/{service}/{prompt_id}")
async def update_prompt(service: str, prompt_id: str, doc: Dict[str, Any]):
    # normalize
    doc = dict(doc or {})
    doc["service"] = service
    doc["id"] = prompt_id
    doc.setdefault("version", 1)
    doc["updated_at"] = datetime.utcnow().isoformat()
    # validate
    errors = validate_prompt(doc)
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})
    # save
    path = save_prompt(doc)
    # auto-commit
    git_auto_commit([path], f"chore(prompts): update {service}/{prompt_id}")
    return {"success": True, "path": path}


async def _post(url: str, payload: Dict[str, Any]):
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            return await client.post(url, json=payload)
    except Exception:
        return None


@router.post("/{service}/reload")
async def reload_service_prompts(service: str):
    """Ask the service to reload in-memory prompt cache.
    Service must expose POST /admin/prompts/reload
    """
    base_map = {
        "llm-service": os.getenv("LLM_SERVICE_URL", "http://localhost:8007"),
        "ai-agent-service": os.getenv("AI_AGENT_SERVICE_URL", "http://localhost:8008"),
        "graph-service": os.getenv("GRAPH_SERVICE_URL", "http://localhost:8006"),
        "document-service": os.getenv("DOCUMENT_SERVICE_URL", "http://localhost:8003"),
    }
    base = base_map.get(service) or base_map.get(f"{service}")
    if not base:
        # try guess
        base = os.getenv("SERVICE_BASE_URL", f"http://localhost:8000")
    resp = await _post(f"{base}/admin/prompts/reload", {"source": "backend"})
    ok = bool(resp and resp.status_code in (200, 204))
    return {"requested": True, "service": service, "ok": ok, "status_code": getattr(resp, 'status_code', None)}
