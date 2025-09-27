"""Enrichment LRU + TTL cache (A8)

Provides coroutine-aware get_or_set with concurrency limiting and metrics.
Key design goals:
 - Avoid repeated expensive enrichment LLM calls for identical prompt/model/mode.
 - Support optional TTL expiry & bounded size (evict LRU on overflow).
 - Provide lightweight instrumentation for health endpoint.
 - Avoid external deps; pure Python structures.

Environment variables:
 ENRICH_CACHE_ENABLED (default: true)
 ENRICH_CACHE_MAX_ENTRIES (default: 500)
 ENRICH_CACHE_TTL_SECONDS (default: 3600)
 MAX_ENRICH_IN_FLIGHT (default: 4) - semaphore controlling concurrent enrich ops
 FORCE_REFRESH_ENRICH (optional; truthy => bypass cache for the request)

Public API:
  get_enrichment_cache() -> singleton instance
  class EnrichmentCache:
     async get_or_set(key: str, factory: Callable[[], Awaitable[Any]], force_refresh=False) -> Any
     metrics() -> Dict[str, Any]

Metrics collected:
  hits, misses, evictions, inflight_current, inflight_max_observed,
  wait_count, wait_ms_total, size, enabled

Thread-safety: Only asyncio use expected on single service instance; internal
lock (threading.Lock) protects shared state for metrics & map.
"""
from __future__ import annotations

import os
import time
import asyncio
import threading
from collections import OrderedDict
from typing import Any, Callable, Awaitable, Dict, Optional

class _Entry:
    __slots__ = ("value", "expires")
    def __init__(self, value: Any, expires: float):
        self.value = value
        self.expires = expires

class EnrichmentCache:
    def __init__(self) -> None:
        self.enabled = str(os.getenv("ENRICH_CACHE_ENABLED", "true")).lower() in ("1","true","yes","on")
        self.max_entries = int(os.getenv("ENRICH_CACHE_MAX_ENTRIES", "500"))
        self.ttl = int(os.getenv("ENRICH_CACHE_TTL_SECONDS", "3600"))  # 1h default
        self.schema_version = str(os.getenv("ENRICH_SCHEMA_VERSION", "v1"))
        self._lock = threading.Lock()
        self._data: "OrderedDict[str, _Entry]" = OrderedDict()
        self._metrics = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "inflight_current": 0,
            "inflight_max_observed": 0,
            "wait_count": 0,
            "wait_ms_total": 0.0,
            "last_eviction_ts": None,
            "version": self.schema_version,
            "version_mismatches": 0,
        }
        self._inflight_semaphore = asyncio.Semaphore(int(os.getenv("MAX_ENRICH_IN_FLIGHT", "4")))

    # --------------- Internal helpers ---------------
    def _evict_if_needed(self):
        while len(self._data) > self.max_entries:
            _, _ = self._data.popitem(last=False)
            self._metrics["evictions"] += 1
            self._metrics["last_eviction_ts"] = time.time()

    def _purge_expired(self):  # opportunistic purge of head entries
        if not self._data:
            return
        now = time.time()
        removed = False
        for k, entry in list(self._data.items())[:16]:  # check a slice to cap work
            if entry.expires < now:
                self._data.pop(k, None)
                removed = True
        if removed:
            # Not counting these as evictions for clarity (natural expiry)
            pass

    # --------------- Public API ---------------
    async def get_or_set(self, key: str, factory: Callable[[], Awaitable[Any]], force_refresh: bool=False) -> Any:
        if not self.enabled:
            return await factory()
        # Prefix key with schema version to isolate caches across upgrades
        vkey = f"{self.schema_version}|{key}"
        if not force_refresh:
            with self._lock:
                self._purge_expired()
                existing = self._data.get(vkey)
                if existing and existing.expires >= time.time():
                    # move to MRU
                    self._data.move_to_end(vkey, last=True)
                    self._metrics["hits"] += 1
                    return existing.value
        self._metrics["misses"] += 1

        # Concurrency control
        start_wait = time.time()
        acquired = await self._inflight_semaphore.acquire()
        wait_ms = (time.time() - start_wait) * 1000.0
        if wait_ms > 1:  # record only if measurable
            self._metrics["wait_count"] += 1
            self._metrics["wait_ms_total"] += wait_ms
        try:
            with self._lock:
                self._metrics["inflight_current"] += 1
                if self._metrics["inflight_current"] > self._metrics["inflight_max_observed"]:
                    self._metrics["inflight_max_observed"] = self._metrics["inflight_current"]
            # Double-check after acquiring (another task may have filled)
            if not force_refresh:
                with self._lock:
                    existing2 = self._data.get(vkey)
                    if existing2 and existing2.expires >= time.time():
                        self._data.move_to_end(vkey, last=True)
                        self._metrics["hits"] += 1  # retroactive hit instead of miss? keep to maintain semantics
                        self._metrics["misses"] -= 1  # adjust previous miss
                        return existing2.value
            # Compute fresh
            value = await factory()
            expires = time.time() + self.ttl
            with self._lock:
                # Detect if an old version existed and increment mismatch counter (when same logical key without version appears?)
                if key != vkey and any(k.endswith(key) for k in self._data.keys() if not k.startswith(self.schema_version)):
                    self._metrics["version_mismatches"] += 1
                self._data[vkey] = _Entry(value, expires)
                self._data.move_to_end(vkey, last=True)
                self._evict_if_needed()
            return value
        finally:
            with self._lock:
                self._metrics["inflight_current"] -= 1
            self._inflight_semaphore.release()

    def metrics(self) -> Dict[str, Any]:
        with self._lock:
            snap = dict(self._metrics)
            snap["size"] = len(self._data)
            snap["enabled"] = self.enabled
            return snap

# Singleton accessor
_enrichment_cache: Optional[EnrichmentCache] = None

def get_enrichment_cache() -> EnrichmentCache:
    global _enrichment_cache
    if _enrichment_cache is None:
        _enrichment_cache = EnrichmentCache()
    return _enrichment_cache
