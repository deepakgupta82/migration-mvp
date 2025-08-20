"""
Lightweight centralized config client for project-service.
Fetches backend config.local.json with a small TTL cache and provides cfg_get().
"""
from __future__ import annotations

import os
import time
from typing import Any, Iterable, Optional


_CONFIG_CACHE: dict[str, Any] | None = None
_CONFIG_CACHE_AT: float | None = None
_CONFIG_TTL_SEC = 10.0


def _backend_config_url() -> str:
    # Allow override via env; default backend config route
    return os.getenv("BACKEND_CONFIG_URL", "http://localhost:8000/config/config.local.json")


def _http_get_json(url: str, timeout: float = 1.5) -> Optional[dict]:
    # Try httpx first, then requests; keep deps minimal
    try:
        import httpx  # type: ignore
        with httpx.Client(timeout=timeout) as client:
            r = client.get(url)
            if r.status_code == 200:
                return r.json()
    except Exception:
        pass
    try:
        import requests  # type: ignore
        r = requests.get(url, timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def _load_config(force: bool = False) -> dict[str, Any]:
    global _CONFIG_CACHE, _CONFIG_CACHE_AT
    now = time.time()
    if (not force and _CONFIG_CACHE is not None and _CONFIG_CACHE_AT is not None
            and (now - _CONFIG_CACHE_AT) < _CONFIG_TTL_SEC):
        return _CONFIG_CACHE  # type: ignore

    cfg = _http_get_json(_backend_config_url())
    if isinstance(cfg, dict):
        _CONFIG_CACHE = cfg
        _CONFIG_CACHE_AT = now
        return cfg
    # Fallback to empty dict to avoid None handling downstream
    _CONFIG_CACHE = {}
    _CONFIG_CACHE_AT = now
    return _CONFIG_CACHE


def cfg_get(path: Iterable[str], default: Any = None) -> Any:
    """Get a nested value from centralized config using a path of keys.
    Example: cfg_get(["backend", "cors_origins"], [])
    """
    cfg = _load_config()
    cur: Any = cfg
    try:
        for key in path:
            if not isinstance(cur, dict):
                return default
            cur = cur.get(key)
        return default if cur is None else cur
    except Exception:
        return default
