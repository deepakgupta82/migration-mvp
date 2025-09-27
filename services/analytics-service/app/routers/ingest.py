"""Analytics Ingestion Endpoint (Phase B → Phase C upgrade)

Enhancements added in Phase C:
 - Optional JSONL persistence of the rolling history (survives process restarts)
 - Explicit reload helper for tests / operational scripts
 - Lightweight pruning + compaction safeguard

Environment:
    ANALYTICS_HISTORY_MAX (default 500)            Max records retained in memory (deque cap)
    ANALYTICS_PERSIST_ENABLED (default false)      When true, append each ingest record as JSON line
    ANALYTICS_PERSIST_PATH (default analytics_history.jsonl)  File path for JSONL persistence
    ANALYTICS_PERSIST_COMPACT_EVERY (default 2000)  After this many appends, rewrite file with only current deque

Payload Example:
{
    "source": "document-service",
    "project_id": "abc123",
    "filename": "doc.pdf",
    "metrics": { ... layout_metrics ... }
}
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Deque
from collections import deque
import os
import time

router = APIRouter(tags=["analytics-ingest"])

_HISTORY_MAX = int(os.getenv("ANALYTICS_HISTORY_MAX", "500") or 500)
_HISTORY: Deque[Dict[str, Any]] = deque(maxlen=_HISTORY_MAX)

_PERSIST_ENABLED = os.getenv("ANALYTICS_PERSIST_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
_PERSIST_PATH = os.getenv("ANALYTICS_PERSIST_PATH", "analytics_history.jsonl")
_PERSIST_COMPACT_EVERY = int(os.getenv("ANALYTICS_PERSIST_COMPACT_EVERY", "2000") or 2000)
_persist_append_count = 0

def _persist_append(record: Dict[str, Any]):  # pragma: no cover - file IO small
    """Append record to JSONL file (best effort)."""
    global _persist_append_count
    if not _PERSIST_ENABLED:
        return
    try:
        import json, os
        with open(_PERSIST_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        _persist_append_count += 1
        # Periodic compaction to drop lines beyond deque capacity
        if _persist_append_count % _PERSIST_COMPACT_EVERY == 0:
            _compact_persist_file()
    except Exception:
        pass

def _compact_persist_file():  # pragma: no cover - infrequent maintenance
    if not _PERSIST_ENABLED:
        return
    try:
        import json, os, tempfile, shutil
        tmp_fd, tmp_path = tempfile.mkstemp(prefix="analytics_compact_", suffix=".jsonl")
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as wf:
            for rec in list(_HISTORY):
                wf.write(json.dumps(rec, ensure_ascii=False) + "\n")
        shutil.move(tmp_path, _PERSIST_PATH)
    except Exception:
        pass

def _load_persisted():  # pragma: no cover - exercised indirectly in tests
    """Load persisted JSONL file into deque (oldest → newest).

    Only the most recent _HISTORY_MAX records are retained in memory.
    """
    if not _PERSIST_ENABLED:
        return
    try:
        import json, os
        if not os.path.exists(_PERSIST_PATH):
            return
        # Read all lines, keep last N
        with open(_PERSIST_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
        tail = lines[-_HISTORY_MAX:]
        for line in tail:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                if isinstance(rec, dict):
                    _HISTORY.append(rec)
            except Exception:
                continue
    except Exception:
        pass

# Initialize from persistence at import time (safe no-op if disabled)
_load_persisted()

class IngestRecord(BaseModel):
    source: str = Field(..., description="Originating service name")
    project_id: Optional[str] = Field(None, description="Project identifier")
    filename: Optional[str] = Field(None, description="Document filename")
    metrics: Dict[str, Any] = Field(..., description="Arbitrary metrics map")
    ts: float = Field(default_factory=lambda: time.time(), description="Epoch seconds at ingestion")

class IngestResponse(BaseModel):
    accepted: bool
    history_size: int
    max_size: int
    persisted: bool

@router.post("/ingest", response_model=IngestResponse, summary="Ingest processing metrics")
async def ingest_metrics(rec: IngestRecord):
    try:
        data = rec.dict()
        _HISTORY.append(data)
        _persist_append(data)
        return IngestResponse(accepted=True, history_size=len(_HISTORY), max_size=_HISTORY_MAX, persisted=_PERSIST_ENABLED)
    except Exception as e:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Failed to store metrics: {e}")

@router.get("/ingest/history", summary="Return current rolling history (debug)")
async def ingest_history(limit: int = 50):
    if limit <= 0:
        limit = 1
    data = list(_HISTORY)[-limit:]
    return {"count": len(data), "records": data}

# Simple accessor for other modules
def get_history():  # pragma: no cover - utility
    return list(_HISTORY)

def reload_persisted():  # pragma: no cover - manual/test hook
    """Clear current history and reload from persistence (if enabled)."""
    try:
        _HISTORY.clear()
        _load_persisted()
    except Exception:
        pass

__all__ = ["router", "get_history", "reload_persisted"]
