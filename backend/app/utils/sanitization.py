# Utility sanitization functions extracted from main.py
import re
from typing import Any

def sanitize_agent_output(text: Any) -> str:
    """Sanitize agent/tool output to ensure clean, embeddable text."""
    if not isinstance(text, str):
        text = str(text)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
    text = re.sub(r'([A-Za-z0-9+/=]{100,})', '[REMOVED_BINARY]', text)
    text = re.sub(r'\s{3,}', '  ', text)
    text = '\n'.join([line if len(line) < 2000 else line[:2000] + '...[TRUNCATED]' for line in text.splitlines()])
    return text

def sanitize_for_latex(text: str) -> str:
    """Escape/clean LaTeX special characters and control bytes."""
    text = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', text)
    text = text.replace('\\', '\\textbackslash{}')
    replacements = {
        '&': '\\&', '%': '\\%', '$': '\\$', '#': '\\#',
        '_': '\\_', '{': '\\{', '}': '\\}', '~': '\\textasciitilde{}', '^': '\\textasciicircum{}'
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text
