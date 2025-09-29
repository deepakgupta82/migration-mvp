import os
import json
from typing import Dict, Optional

_CACHE: Dict[str, Dict] = {}
_PROMPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "prompts"))


def reload_cache() -> int:
    global _CACHE
    _CACHE = {}
    if not os.path.isdir(_PROMPT_DIR):
        return 0
    count = 0
    for fn in os.listdir(_PROMPT_DIR):
        if fn.endswith(".json"):
            try:
                with open(os.path.join(_PROMPT_DIR, fn), "r", encoding="utf-8") as f:
                    data = json.load(f)
                    pid = data.get("id") or os.path.splitext(fn)[0]
                    _CACHE[pid] = data
                    count += 1
            except Exception:
                continue
    return count


def get_prompt(pid: str) -> Optional[Dict]:
    if not _CACHE and os.path.isdir(_PROMPT_DIR):
        reload_cache()
    return _CACHE.get(pid)
