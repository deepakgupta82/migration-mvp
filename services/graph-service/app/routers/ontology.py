from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from typing import Any, Dict, List
import os

from app.core.ontology_registry import OntologyRegistry


router = APIRouter(prefix="/api/ontology", tags=["ontology"])

_registry = None


def _get_registry() -> OntologyRegistry:
    global _registry
    if _registry is None:
        base_dir = os.getenv("ONTOLOGY_STORAGE_DIR", os.path.join(os.getcwd(), "var", "ontology"))
        _registry = OntologyRegistry(base_dir)
    return _registry


@router.get("")
async def get_latest_ontology() -> Dict[str, Any]:
    reg = _get_registry()
    try:
        latest = reg.load_latest()
        return latest
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Ontology not found")


@router.put("")
async def put_new_ontology(ontology_json: Dict[str, Any], request: Request) -> Dict[str, Any]:
    reg = _get_registry()
    try:
        # Minimal validation beyond structural checks
        ents: List[Dict[str, Any]] = ontology_json.get("entities", [])
        rels: List[Dict[str, Any]] = ontology_json.get("relationships", [])
        if not isinstance(ents, list) or not isinstance(rels, list):
            raise ValueError("Ontology must include 'entities' and 'relationships' arrays")
        # Basic entity/relationship shape checks (names present)
        for i, e in enumerate(ents[:500]):
            if not isinstance(e, dict) or not e.get("name"):
                raise ValueError(f"Invalid entity at index {i}: missing name")
        for i, r in enumerate(rels[:2000]):
            if not isinstance(r, dict) or not r.get("name") or not r.get("from_type") or not r.get("to_type"):
                raise ValueError(f"Invalid relationship at index {i}: name/from_type/to_type required")
        saved = reg.save_new(ontology_json)
        # Write a small audit breadcrumb
        try:
            from app.main import app as _app  # type: ignore
            gp = getattr(_app.state, "graph_processor", None)
            if gp and getattr(gp, "redis_client", None):
                who = request.headers.get("X-User-Id") or request.headers.get("X-User-Email") or "unknown"
                await gp.redis_client.lpush("ontology:audit", json.dumps({
                    "who": who,
                    "ts": __import__("datetime").datetime.utcnow().isoformat(),
                    "version": saved["version"],
                }))
                await gp.redis_client.ltrim("ontology:audit", 0, 199)
        except Exception:
            pass
        return {"version": saved["version"], "created_at": saved["created_at"]}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/history")
async def get_ontology_history() -> Dict[str, Any]:
    """Return recent ontology version audit entries (best-effort)."""
    try:
        from app.main import app as _app  # type: ignore
        gp = getattr(_app.state, "graph_processor", None)
        items: List[Dict[str, Any]] = []
        if gp and getattr(gp, "redis_client", None):
            raw = await gp.redis_client.lrange("ontology:audit", 0, 50)
            for r in raw or []:
                try:
                    items.append(json.loads(r))
                except Exception:
                    continue
        return {"count": len(items), "items": items}
    except Exception:
        return {"count": 0, "items": []}
