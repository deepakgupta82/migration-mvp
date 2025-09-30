"""
In-memory MCP Server Registry.

For MVP, we keep configurations in memory and (optionally) mirror to a JSON file
under the service data directory. Later this can be moved to Postgres.
"""

from __future__ import annotations

import json
import os
from typing import Dict, List, Optional
from threading import RLock

from app.core.mcp_models import MCPServerConfig, MCPServerWithTools, UnifiedToolSchema


class MCPRegistry:
    def __init__(self, persist_path: Optional[str] = None):
        self._servers: Dict[str, MCPServerConfig] = {}
        self._tools_cache: Dict[str, List[UnifiedToolSchema]] = {}
        self._persist_path = persist_path
        self._lock = RLock()
        if persist_path and os.path.exists(persist_path):
            try:
                with open(persist_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data.get("servers", []):
                        cfg = MCPServerConfig(**item)
                        self._servers[cfg.id] = cfg
            except Exception:
                pass

    def _save(self):
        if not self._persist_path:
            return
        try:
            os.makedirs(os.path.dirname(self._persist_path), exist_ok=True)
            with open(self._persist_path, "w", encoding="utf-8") as f:
                json.dump({"servers": [s.model_dump() for s in self._servers.values()]}, f, indent=2)
        except Exception:
            pass

    def list(self) -> List[MCPServerConfig]:
        with self._lock:
            return list(self._servers.values())

    def get(self, server_id: str) -> Optional[MCPServerConfig]:
        with self._lock:
            return self._servers.get(server_id)

    def upsert(self, cfg: MCPServerConfig) -> MCPServerConfig:
        with self._lock:
            self._servers[cfg.id] = cfg
            self._save()
            return cfg

    def delete(self, server_id: str) -> bool:
        with self._lock:
            if server_id in self._servers:
                del self._servers[server_id]
                self._tools_cache.pop(server_id, None)
                self._save()
                return True
            return False

    def get_tools(self, server_id: str) -> List[UnifiedToolSchema]:
        with self._lock:
            return self._tools_cache.get(server_id, [])

    def set_tools(self, server_id: str, tools: List[UnifiedToolSchema]):
        with self._lock:
            self._tools_cache[server_id] = tools


# Singleton accessor
_registry: Optional[MCPRegistry] = None


def get_registry() -> MCPRegistry:
    global _registry
    if _registry is None:
        # Persist under temp dir by default
        base_dir = os.getenv("AI_AGENT_DATA_DIR") or os.path.join(os.getenv("TEMP", "/tmp"), "ai-agent-service")
        persist = os.path.join(base_dir, "mcp_registry.json")
        _registry = MCPRegistry(persist)
    return _registry
