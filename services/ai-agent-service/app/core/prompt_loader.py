import os
import json
from typing import Dict, Optional

_CACHE: Dict[str, Dict] = {}
_PROMPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "prompts"))


def _path(pid: str) -> str:
    return os.path.join(_PROMPT_DIR, f"{pid}.json")


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


def render_text(pid: str, variables: Dict[str, str]) -> str:
    doc = get_prompt(pid) or {}
    text = doc.get("text", "")
    # very simple mustache-like replacements plus optional block for context_snippets
    out = text.replace("{{project_id}}", str(variables.get("project_id", ""))) \
             .replace("{{template_guidance}}", str(variables.get("template_guidance", "")))
    context_snippets = variables.get("context_snippets") or ""
    if "{{#if context_snippets}}" in out:
        if context_snippets:
            out = out.replace("{{#if context_snippets}}", "").replace("{{/if}}", "")
            out = out.replace("{{context_snippets}}", str(context_snippets))
        else:
            # remove block entirely
            start = out.find("{{#if context_snippets}}")
            end = out.find("{{/if}}", start)
            if start != -1 and end != -1:
                block = out[start:end+len("{{/if}}")]
                out = out.replace(block, "").strip()
    return out or ""
