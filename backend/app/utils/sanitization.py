from __future__ import annotations
import re

__all__ = ["sanitize_agent_output", "sanitize_for_latex"]

_SANITIZE_REPLACEMENTS = [
    (r"```(.*?)```", lambda m: m.group(0).replace("`", "´")),
]

_LATEX_REPLACEMENTS = [
    (r"\\", r"\\\\"),
    (r"([{}_#%&$])", r"\\\\\\1"),
]

def sanitize_agent_output(text: str) -> str:
    if not text:
        return ""
    cleaned = text
    for pattern, repl in _SANITIZE_REPLACEMENTS:
        cleaned = re.sub(pattern, repl, cleaned, flags=re.DOTALL)
    return cleaned.strip()

def sanitize_for_latex(text: str) -> str:
    if not text:
        return ""
    cleaned = text
    for pattern, repl in _LATEX_REPLACEMENTS:
        cleaned = re.sub(pattern, repl, cleaned)
    return cleaned
