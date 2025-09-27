"""Section Enrichment LRU + TTL cache (A3 advanced)

Lightweight in-process cache to avoid recomputing section enrichment for the same
structured document output (idempotent deterministic transformation).

Design notes:
 - Key should incorporate a schema version (for safe future evolution), project id,
   structured filename, and a stable digest of element ids & basic stats so that
   enrichment invalidates if underlying structured extraction changes.
 - Implementation mirrors llm-service enrichment cache but omits concurrency
   semaphore (enrichment is cheap) and keeps code minimal (pure Python OrderedDict).
 - Metrics exposed for optional future health endpoint wiring (not yet surfaced).

Environment variables:
  SECTION_ENRICH_CACHE_ENABLED (default true)
  SECTION_ENRICH_CACHE_MAX_ENTRIES (default 300)
  SECTION_ENRICH_CACHE_TTL_SECONDS (default 3600)
  SECTION_ENRICH_SCHEMA_VERSION (default v1)

Public API:
  get_section_enrich_cache() -> singleton
  SectionEnrichCache.get(key) / set(key, value)
  build_cache_key(project_id, structured_filename, element_digest) helper
"""
from __future__ import annotations

import os
import time
import threading
import hashlib
from collections import OrderedDict
from typing import Any, Dict, Optional

class _Entry:
    __slots__ = ("value", "expires")
    def __init__(self, value: Any, expires: float):
        self.value = value
        self.expires = expires

class SectionEnrichCache:
    def __init__(self) -> None:
        self.enabled = str(os.getenv("SECTION_ENRICH_CACHE_ENABLED", "true")).lower() in ("1","true","yes","on")
        self.max_entries = int(os.getenv("SECTION_ENRICH_CACHE_MAX_ENTRIES", "300"))
        self.ttl = int(os.getenv("SECTION_ENRICH_CACHE_TTL_SECONDS", "3600"))
        self.schema_version = str(os.getenv("SECTION_ENRICH_SCHEMA_VERSION", "v1"))
        self._lock = threading.Lock()
        self._data: "OrderedDict[str, _Entry]" = OrderedDict()
        self._metrics = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "size": 0,
            "version": self.schema_version,
        }

    # ---------------- internal helpers ----------------
    def _purge_expired(self):
        if not self._data:
            return
        now = time.time()
        removed = False
        for k, entry in list(self._data.items())[:24]:  # slice for bounded work
            if entry.expires < now:
                self._data.pop(k, None)
                removed = True
        if removed:
            self._metrics["size"] = len(self._data)

    def _evict_if_needed(self):
        while len(self._data) > self.max_entries:
            self._data.popitem(last=False)
            self._metrics["evictions"] += 1
        self._metrics["size"] = len(self._data)

    # ---------------- public API ----------------
    def get(self, key: str) -> Optional[Any]:
        if not self.enabled:
            return None
        vkey = f"{self.schema_version}|{key}"
        with self._lock:
            self._purge_expired()
            entry = self._data.get(vkey)
            if entry and entry.expires >= time.time():
                self._data.move_to_end(vkey, last=True)
                self._metrics["hits"] += 1
                return entry.value
            self._metrics["misses"] += 1
            return None

    def set(self, key: str, value: Any):
        if not self.enabled:
            return
        vkey = f"{self.schema_version}|{key}"
        expires = time.time() + self.ttl
        with self._lock:
            self._data[vkey] = _Entry(value, expires)
            self._data.move_to_end(vkey, last=True)
            self._evict_if_needed()

    def metrics(self) -> Dict[str, Any]:
        with self._lock:
            snap = dict(self._metrics)
            snap["enabled"] = self.enabled
            return snap

def build_cache_key(project_id: str, structured_filename: str, element_ids: list[str], total_text_len: int) -> str:
    base = f"{project_id}|{structured_filename}|{len(element_ids)}|{total_text_len}".encode()
    digest = hashlib.sha256(base + "|".join(element_ids).encode()).hexdigest()[:40]
    return digest

_section_cache: Optional[SectionEnrichCache] = None

def get_section_enrich_cache() -> SectionEnrichCache:
    global _section_cache
    if _section_cache is None:
        _section_cache = SectionEnrichCache()
    return _section_cache
