"""
Reporting-service config client to fetch centralized config.local.json from backend.
"""
from __future__ import annotations

import os
import time
from typing import Any, Dict, List

_CACHE: Dict[str, Any] = {"ts": 0.0, "cfg": {}}
_TTL = 10.0


def _fetch() -> Dict[str, Any]:
    url = os.getenv("BACKEND_CONFIG_URL", "http://localhost:8000/config/config.local.json")
    try:
        try:
            import httpx
            with httpx.Client(timeout=1.5) as c:
                r = c.get(url)
                if r.status_code == 200:
                    return r.json()
        except Exception:
            pass
        try:
            import requests
            r = requests.get(url, timeout=1.5)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
    except Exception:
        pass
    return {}


def get_config() -> Dict[str, Any]:
    now = time.time()
    if now - float(_CACHE.get("ts") or 0.0) > _TTL:
        cfg = _fetch()
        _CACHE["cfg"] = cfg or _CACHE.get("cfg", {})
        _CACHE["ts"] = now
    return _CACHE.get("cfg", {})


def cfg_get(path: List[str], default: Any = None) -> Any:
    cfg = get_config()
    cur: Any = cfg
    try:
        for k in path:
            if isinstance(cur, dict) and k in cur:
                cur = cur[k]
            else:
                return default
        return cur if cur is not None else default
    except Exception:
        return default
