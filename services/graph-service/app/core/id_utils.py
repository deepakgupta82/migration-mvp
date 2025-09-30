from __future__ import annotations

import hashlib
import re


def _slug(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^a-z0-9\- _]+", "", s)
    s = s.replace(" ", "-")
    return s


def make_canonical_id(project_id: str, entity_type: str, name: str, source: str | None = None) -> str:
    """Create a stable canonical ID.

    Format: <project>:<type>:<hash>
    - hash is SHA1 of (project|type|name|source?) truncated to 12 chars
    - type/name normalized to slugs for readability in prefix
    """
    p = _slug(project_id)
    t = _slug(entity_type)
    n = (name or "").strip()
    basis = f"{project_id}|{entity_type}|{name}|{source or ''}"
    h = hashlib.sha1(basis.encode("utf-8", errors="ignore")).hexdigest()[:12]
    return f"{p}:{t}:{h}"
