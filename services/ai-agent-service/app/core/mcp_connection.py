"""
MCP Connection Manager (skeleton)

Supports:
- stdio subprocess launch (Node-based servers like AWS labs)
- ws/sse placeholders (to be implemented)

Provides tool discovery stub and execute stub to be fleshed out later.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import logging
from typing import Dict, Any, List, Optional
from asyncio.subprocess import create_subprocess_exec
import websockets
import aiohttp
import time
from datetime import datetime

from .secret_resolver import build_env_for_mcp

from app.core.mcp_models import MCPServerConfig, UnifiedToolSchema

logger = logging.getLogger("mcp-conn")


class MCPConnectionManager:
    def __init__(self):
        self._processes: Dict[str, asyncio.subprocess.Process] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._rate_buckets: Dict[str, List[float]] = {}
        self._concurrency: Dict[str, int] = {}
        self._fail_counts: Dict[str, int] = {}
        self._circuit_open_until: Dict[str, float] = {}
        self._audit_path = os.path.join(
            os.getenv("AI_AGENT_LOG_DIR", os.path.join(os.getenv("TEMP", "/tmp"), "ai-agent-service")),
            "mcp_audit.jsonl",
        )

    def _get_lock(self, server_id: str) -> asyncio.Lock:
        if server_id not in self._locks:
            self._locks[server_id] = asyncio.Lock()
        return self._locks[server_id]

    async def connect_and_discover(self, cfg: MCPServerConfig) -> List[UnifiedToolSchema]:
        """Connect to the MCP server and return discovered tools.

        For MVP: if stdio, spawn the process and assume a well-known set of tools
        for known servers (e.g., AWS labs). We will refine to real MCP handshake later.
        """
        if cfg.connection.transport == "stdio":
            return await self._spawn_stdio_and_handshake(cfg)
        elif cfg.connection.transport == "ws":
            return await self._connect_ws_and_handshake(cfg)
        elif cfg.connection.transport == "sse":
            return await self._connect_sse_and_handshake(cfg)
        else:
            logger.info(f"Unknown transport {cfg.connection.transport}; returning no tools")
            return []

    async def _spawn_stdio_and_handshake(self, cfg: MCPServerConfig) -> List[UnifiedToolSchema]:
        lock = self._get_lock(cfg.id)
        async with lock:
            if cfg.id in self._processes and self._processes[cfg.id] and self._processes[cfg.id].returncode is None:
                logger.info(f"MCP stdio process already running for {cfg.name}")
            else:
                try:
                    # Special case for tests: allow a no-op command that skips spawning any external process
                    if (cfg.connection.stdio.command or '').lower() in ("noop", "none", "skip"):
                        logger.info(f"Skipping process spawn for {cfg.name} using noop command")
                    else:
                        env, temp_gcp = build_env_for_mcp(cfg)
                        cmd = [cfg.connection.stdio.command] + (cfg.connection.stdio.args or [])
                        logger.info(f"Launching MCP stdio server: {cmd} cwd={cfg.connection.stdio.cwd}")
                        proc = await create_subprocess_exec(
                            *cmd,
                            cwd=cfg.connection.stdio.cwd or None,
                            env=env,
                            stdin=asyncio.subprocess.PIPE,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                        )
                        self._processes[cfg.id] = proc
                        # Brief delay to allow startup
                        await asyncio.sleep(0.3)
                except Exception as e:
                    logger.error(f"Failed to launch MCP server {cfg.name}: {e}")
                    return []

        # If noop, return provider-based mock tools (dev convenience)
        if (cfg.connection.stdio.command or '').lower() in ("noop", "none", "skip"):
            return self._mock_tools(cfg)

        # Real stdio handshake (JSON-RPC via LSP framing)
        proc = self._processes.get(cfg.id)
        if not proc or not proc.stdout or not proc.stdin:
            logger.error("STDIO process missing pipes; cannot handshake")
            return []

        try:
            # Send an initialize request per MCP draft: method "initialize"
            req = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "clientInfo": {"name": "ai-agent-service", "version": "1.0"}
                },
            }
            payload = json.dumps(req).encode("utf-8")
            header = f"Content-Length: {len(payload)}\r\n\r\n".encode("ascii")
            proc.stdin.write(header + payload)
            await proc.stdin.drain()

            # Read response head then body
            content_length = None
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                line_s = line.decode("ascii", errors="ignore").strip()
                if line_s.lower().startswith("content-length:"):
                    try:
                        content_length = int(line_s.split(":")[1].strip())
                    except Exception:
                        pass
                if line_s == "":
                    # blank line, headers end
                    break
            body = await proc.stdout.readexactly(content_length) if content_length else b""
            resp = json.loads(body.decode("utf-8")) if body else {}
            if resp.get("error"):
                logger.error(f"MCP initialize error: {resp['error']}")
                return []

            # Now request tools: method "tools/list"
            req2 = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
            payload2 = json.dumps(req2).encode("utf-8")
            header2 = f"Content-Length: {len(payload2)}\r\n\r\n".encode("ascii")
            proc.stdin.write(header2 + payload2)
            await proc.stdin.drain()

            # Read tools response
            content_length = None
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                line_s = line.decode("ascii", errors="ignore").strip()
                if line_s.lower().startswith("content-length:"):
                    try:
                        content_length = int(line_s.split(":")[1].strip())
                    except Exception:
                        pass
                if line_s == "":
                    break
            body2 = await proc.stdout.readexactly(content_length) if content_length else b""
            resp2 = json.loads(body2.decode("utf-8")) if body2 else {}
            tool_items = resp2.get("result") or resp2.get("tools") or []
            return self._normalize_tools(cfg, tool_items)
        except Exception as e:
            logger.warning(f"Falling back to mock tools due to handshake error: {e}")
            return self._mock_tools(cfg)

    async def _connect_ws_and_handshake(self, cfg: MCPServerConfig) -> List[UnifiedToolSchema]:
        if not cfg.connection.ws or not cfg.connection.ws.url:
            logger.error("WS transport selected but no url provided")
            return []
        try:
            async with websockets.connect(cfg.connection.ws.url, extra_headers=cfg.connection.ws.headers or {}) as ws:
                # Send initialize
                await ws.send(json.dumps({
                    "jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"clientInfo": {"name": "ai-agent-service", "version": "1.0"}}
                }))
                _ = await ws.recv()
                # List tools
                await ws.send(json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}))
                msg = await ws.recv()
                data = json.loads(msg)
                items = data.get("result") or data.get("tools") or []
                return self._normalize_tools(cfg, items)
        except Exception as e:
            logger.warning(f"WS handshake failed; returning mock tools: {e}")
            return self._mock_tools(cfg)

    async def _connect_sse_and_handshake(self, cfg: MCPServerConfig) -> List[UnifiedToolSchema]:
        if not cfg.connection.sse or not cfg.connection.sse.url:
            logger.error("SSE transport selected but no url provided")
            return []
        # For SSE, some servers expose an initialize event stream; we'll simulate by POSTing initialize and fetching tools via a normal GET
        try:
            headers = cfg.connection.sse.headers or {}
            async with aiohttp.ClientSession() as session:
                # Initialize (best-effort)
                try:
                    init_payload = {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {"clientInfo": {"name": "ai-agent-service", "version": "1.0"}},
                    }
                    await session.post(cfg.connection.sse.url, json=init_payload, headers=headers, timeout=10)
                except Exception:
                    pass
                # Request tools list
                tools_req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
                async with session.post(cfg.connection.sse.url, json=tools_req, headers=headers, timeout=20) as resp:
                    data = await resp.json(content_type=None)
                    items = (data or {}).get("result") or (data or {}).get("tools") or []
                    return self._normalize_tools(cfg, items)
        except Exception as e:
            logger.warning(f"SSE handshake failed; returning mock tools: {e}")
            return self._mock_tools(cfg)

    def _mock_tools(self, cfg: MCPServerConfig) -> List[UnifiedToolSchema]:
        tools: List[UnifiedToolSchema] = []
        prov = cfg.provider
        if prov == "aws":
            names = [
                "cost_explorer.query_costs",
                "pricing.get_price",
                "resource_graph.search",
                "documentation.lookup",
                "knowledge.search",
            ]
        elif prov == "azure":
            names = [
                "resource_graph.query",
                "cost_management.actuals",
                "pricing.retail_rates",
                "docs.search",
            ]
        elif prov == "gcp":
            names = [
                "asset_inventory.search",
                "billing.costs",
                "pricing.catalog",
                "docs.search",
            ]
        else:
            names = ["echo.run", "docs.search"]
        for n in names:
            if cfg.tool_allowlist and n not in cfg.tool_allowlist:
                continue
            if cfg.tool_denylist and n in cfg.tool_denylist:
                continue
            tools.append(
                UnifiedToolSchema(
                    name=n,
                    description=f"Tool {n} from {cfg.name}",
                    input_schema=None,
                    server_id=cfg.id,
                    provider=cfg.provider,
                )
            )
        return tools

    def _normalize_tools(self, cfg: MCPServerConfig, raw_items: Any) -> List[UnifiedToolSchema]:
        tools: List[UnifiedToolSchema] = []
        try:
            for item in (raw_items or []):
                name = item.get("name") if isinstance(item, dict) else None
                if not name:
                    continue
                if cfg.tool_allowlist and name not in cfg.tool_allowlist:
                    continue
                if cfg.tool_denylist and name in cfg.tool_denylist:
                    continue
                tools.append(
                    UnifiedToolSchema(
                        name=name,
                        description=item.get("description"),
                        input_schema=item.get("inputSchema") or item.get("input_schema"),
                        server_id=cfg.id,
                        provider=cfg.provider,
                    )
                )
        except Exception as e:
            logger.warning(f"Failed to normalize tools; returning mock tools: {e}")
            return self._mock_tools(cfg)
        return tools

    async def execute(self, cfg: MCPServerConfig, tool: str, args: Dict[str, Any]) -> Any:
        """Execute a tool call via MCP.

    MVP: if stdio 'noop', return mock response. Otherwise try JSON-RPC call 'tools/execute'.
        """
        # Apply allow/deny
        if cfg.tool_allowlist and tool not in cfg.tool_allowlist:
            raise RuntimeError("Tool not permitted by allowlist")
        if cfg.tool_denylist and tool in cfg.tool_denylist:
            raise RuntimeError("Tool denied by policy")

        # If noop, return mock
        if (cfg.connection.stdio and (cfg.connection.stdio.command or '').lower() in ("noop", "none", "skip")) or cfg.connection.transport != "stdio":
            return {
                "tool": tool,
                "args": args,
                "server": cfg.name,
                "provider": cfg.provider,
                "note": "MCP execution mocked (noop/stdio disabled)",
            }

        # Policy: rate limit, concurrency, circuit breaker
        start_ts = time.time()
        self._enforce_policies_before(cfg)

        proc = self._processes.get(cfg.id)
        if not proc or not proc.stdout or not proc.stdin:
            raise RuntimeError("MCP stdio process not available for execute")

        try:
            req = {"jsonrpc": "2.0", "id": 3, "method": "tools/execute", "params": {"name": tool, "arguments": args}}
            payload = json.dumps(req).encode("utf-8")
            header = f"Content-Length: {len(payload)}\r\n\r\n".encode("ascii")
            proc.stdin.write(header + payload)
            await proc.stdin.drain()

            # Read response
            content_length = None
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                line_s = line.decode("ascii", errors="ignore").strip()
                if line_s.lower().startswith("content-length:"):
                    try:
                        content_length = int(line_s.split(":")[1].strip())
                    except Exception:
                        pass
                if line_s == "":
                    break
            body = await proc.stdout.readexactly(content_length) if content_length else b""
            resp = json.loads(body.decode("utf-8")) if body else {}
            if resp.get("error"):
                raise RuntimeError(str(resp["error"]))
            result = resp.get("result") if "result" in resp else resp
            self._record_success(cfg)
            self._audit_log(
                action="execute",
                cfg=cfg,
                tool=tool,
                args=args,
                status="success",
                duration_ms=int((time.time() - start_ts) * 1000),
            )
            return result
        except Exception as e:
            self._record_failure(cfg)
            logger.warning(f"Execute fallback (mock) due to error: {e}")
            out = {
                "tool": tool,
                "args": args,
                "server": cfg.name,
                "provider": cfg.provider,
                "note": f"MCP execution mocked (error: {e})",
            }
            self._audit_log(
                action="execute",
                cfg=cfg,
                tool=tool,
                args=args,
                status="error",
                error=str(e),
                duration_ms=int((time.time() - start_ts) * 1000),
            )
            return out

    # --- Policies & Audit ---
    def _enforce_policies_before(self, cfg: MCPServerConfig):
        # Circuit breaker
        now = time.time()
        open_until = self._circuit_open_until.get(cfg.id)
        if open_until and now < open_until:
            raise RuntimeError("Circuit open for MCP server; try later")
        # Rate limiting (token-bucket-like using timestamps)
        rpm = max(1, int(cfg.rate_limit_rpm or 60))
        window = 60.0
        bucket = self._rate_buckets.setdefault(cfg.id, [])
        # Drop timestamps older than window
        while bucket and (now - bucket[0] > window):
            bucket.pop(0)
        if len(bucket) >= rpm:
            raise RuntimeError("MCP rate limit exceeded for server")
        bucket.append(now)
        # Concurrency
        cur = self._concurrency.get(cfg.id, 0)
        max_c = max(1, int(cfg.max_concurrency or 4))
        if cur >= max_c:
            raise RuntimeError("MCP concurrency limit reached for server")
        self._concurrency[cfg.id] = cur + 1

    def _record_success(self, cfg: MCPServerConfig):
        self._concurrency[cfg.id] = max(0, self._concurrency.get(cfg.id, 1) - 1)
        self._fail_counts[cfg.id] = 0

    def _record_failure(self, cfg: MCPServerConfig):
        self._concurrency[cfg.id] = max(0, self._concurrency.get(cfg.id, 1) - 1)
        cnt = 1 + int(self._fail_counts.get(cfg.id, 0))
        self._fail_counts[cfg.id] = cnt
        threshold = max(1, int(cfg.circuit_breaker_threshold or 5))
        if cnt >= threshold:
            cooldown = max(5, int(cfg.circuit_breaker_cooldown_sec or 60))
            self._circuit_open_until[cfg.id] = time.time() + cooldown
            logger.warning(f"Opened circuit for {cfg.name} for {cooldown}s (failures={cnt})")

    def _audit_log(self, action: str, cfg: MCPServerConfig, tool: Optional[str] = None, args: Optional[Dict[str, Any]] = None, status: str = "success", error: Optional[str] = None, duration_ms: Optional[int] = None):
        try:
            os.makedirs(os.path.dirname(self._audit_path), exist_ok=True)
            record = {
                "ts": datetime.utcnow().isoformat(),
                "action": action,
                "server_id": cfg.id,
                "server_name": cfg.name,
                "provider": cfg.provider,
                "status": status,
                "tool": tool,
                "duration_ms": duration_ms,
                "error": error,
                "args_preview": list((args or {}).keys())[:6],
            }
            with open(self._audit_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except Exception:
            pass


# Singleton
_mgr: Optional[MCPConnectionManager] = None


def get_connection_manager() -> MCPConnectionManager:
    global _mgr
    if _mgr is None:
        _mgr = MCPConnectionManager()
    return _mgr
