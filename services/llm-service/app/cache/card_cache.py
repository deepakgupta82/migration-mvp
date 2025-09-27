"""Card Summary Cache

Lightweight LRU + TTL async-aware cache for card summarization responses.
Reduces recomputation when same (subject/predicate/object + evidence hashes + params)
are requested repeatedly (e.g., incremental regeneration workflows).

Env Vars:
  CARD_CACHE_ENABLED (default: true)
  CARD_CACHE_MAX_ENTRIES (default: 400)
  CARD_CACHE_TTL_SECONDS (default: 7200)
  MAX_CARD_SUMMARY_IN_FLIGHT (default: 4)

Public API:
  get_card_cache() -> singleton
  CardSummaryCache.get_or_set(key, factory, force_refresh=False)
  CardSummaryCache.metrics()

Implementation mirrors enrichment cache style for consistency.
"""
from __future__ import annotations
import os, time, asyncio, threading
from collections import OrderedDict
from typing import Any, Awaitable, Callable, Dict, Optional

class _Entry:
    __slots__ = ("value", "expires")
    def __init__(self, value: Any, expires: float):
        self.value = value
        self.expires = expires

class CardSummaryCache:
    def __init__(self) -> None:
        self.enabled = str(os.getenv("CARD_CACHE_ENABLED", "true")).lower() in ("1","true","yes","on")
        self.max_entries = int(os.getenv("CARD_CACHE_MAX_ENTRIES", "400"))
        self.ttl = int(os.getenv("CARD_CACHE_TTL_SECONDS", "7200"))  # 2h
        self.schema_version = str(os.getenv("CARD_CACHE_SCHEMA_VERSION", "v1"))
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
        }
        self._sem = asyncio.Semaphore(int(os.getenv("MAX_CARD_SUMMARY_IN_FLIGHT", "4")))

    def _purge_expired(self):
        if not self._data:
            return
        now = time.time()
        for k, entry in list(self._data.items())[:16]:
            if entry.expires < now:
                self._data.pop(k, None)

    def _evict_if_needed(self):
        while len(self._data) > self.max_entries:
            self._data.popitem(last=False)
            self._metrics["evictions"] += 1
            self._metrics["last_eviction_ts"] = time.time()

    async def get_or_set(self, key: str, factory: Callable[[], Awaitable[Any]], force_refresh: bool=False) -> Any:
        if not self.enabled:
            return await factory()
        vkey = f"{self.schema_version}|{key}"
        if not force_refresh:
            with self._lock:
                self._purge_expired()
                ent = self._data.get(vkey)
                if ent and ent.expires >= time.time():
                    self._data.move_to_end(vkey, last=True)
                    self._metrics["hits"] += 1
                    return ent.value
        self._metrics["misses"] += 1
        start_wait = time.time()
        await self._sem.acquire()
        wait_ms = (time.time() - start_wait) * 1000.0
        if wait_ms > 1:
            self._metrics["wait_count"] += 1
            self._metrics["wait_ms_total"] += wait_ms
        try:
            with self._lock:
                self._metrics["inflight_current"] += 1
                if self._metrics["inflight_current"] > self._metrics["inflight_max_observed"]:
                    self._metrics["inflight_max_observed"] = self._metrics["inflight_current"]
                # Check again
                if not force_refresh:
                    ent2 = self._data.get(vkey)
                    if ent2 and ent2.expires >= time.time():
                        self._data.move_to_end(vkey, last=True)
                        self._metrics["hits"] += 1
                        self._metrics["misses"] -= 1
                        return ent2.value
            val = await factory()
            expires = time.time() + self.ttl
            with self._lock:
                self._data[vkey] = _Entry(val, expires)
                self._data.move_to_end(vkey, last=True)
                self._evict_if_needed()
            return val
        finally:
            with self._lock:
                self._metrics["inflight_current"] -= 1
            self._sem.release()

    def metrics(self) -> Dict[str, Any]:
        with self._lock:
            snap = dict(self._metrics)
            snap["size"] = len(self._data)
            snap["enabled"] = self.enabled
            return snap

_card_cache: Optional[CardSummaryCache] = None

def get_card_cache() -> CardSummaryCache:
    global _card_cache
    if _card_cache is None:
        _card_cache = CardSummaryCache()
    return _card_cache
