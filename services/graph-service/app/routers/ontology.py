from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from typing import Any, Dict, List
import os
import json

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
        # Schema-like validation matching sample_ontology.txt
        ents: List[Dict[str, Any]] = ontology_json.get("entities", [])
        rels: List[Dict[str, Any]] = ontology_json.get("relationships", [])
        if not isinstance(ents, list) or not isinstance(rels, list):
            raise ValueError("Ontology must include 'entities' and 'relationships' arrays")
        # Entities: require label (string); optional required_props/optional_props/pii_props
        for i, e in enumerate(ents[:1000]):
            if not isinstance(e, dict):
                raise ValueError(f"Invalid entity at index {i}: must be object")
            if not isinstance(e.get("label"), str) or not e["label"].strip():
                raise ValueError(f"Invalid entity at index {i}: 'label' required")
            if "required_props" in e and not isinstance(e["required_props"], list):
                raise ValueError(f"Invalid entity at index {i}: required_props must be list")
            if "optional_props" in e and not isinstance(e["optional_props"], list):
                raise ValueError(f"Invalid entity at index {i}: optional_props must be list")
            if "pii_props" in e and not isinstance(e["pii_props"], list):
                raise ValueError(f"Invalid entity at index {i}: pii_props must be list")
        # Relationships: require type (UPPER_SNAKE), from (list of labels), to (list of labels), props (list)
        for i, r in enumerate(rels[:5000]):
            if not isinstance(r, dict):
                raise ValueError(f"Invalid relationship at index {i}: must be object")
            t = r.get("type")
            if not isinstance(t, str) or not t.strip():
                raise ValueError(f"Invalid relationship at index {i}: 'type' required")
            if not isinstance(r.get("from"), list) or not r["from"]:
                raise ValueError(f"Invalid relationship {t}: 'from' must be non-empty list")
            if not isinstance(r.get("to"), list) or not r["to"]:
                raise ValueError(f"Invalid relationship {t}: 'to' must be non-empty list")
            if "props" in r and not isinstance(r["props"], list):
                raise ValueError(f"Invalid relationship {t}: 'props' must be list if present")
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
