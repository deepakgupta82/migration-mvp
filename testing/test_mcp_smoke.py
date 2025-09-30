import requests

BASE = "http://localhost:8008/api/mcp"

# Simple smoke test for MCP endpoints against a running ai-agent-service

def test_mcp_crud_and_discovery():
    # Create a noop stdio server for safe discovery
    cfg = {
        "name": "Local Mock AWS MCP",
        "provider": "aws",
        "connection": {"transport": "stdio", "stdio": {"command": "noop", "args": []}},
        "env": {},
        "tool_allowlist": [],
        "tool_denylist": [],
        "is_enabled": True,
        "description": "Mock AWS MCP for tests"
    }

    r = requests.post(f"{BASE}/servers", json=cfg)
    assert r.ok, r.text
    created = r.json()
    sid = created["id"]

    # List
    r = requests.get(f"{BASE}/servers")
    assert r.ok
    servers = r.json()
    assert any(s["id"] == sid for s in servers)

    # Discover tools (mocked)
    r = requests.post(f"{BASE}/servers/{sid}/discover")
    assert r.ok, r.text
    tools = r.json()
    assert isinstance(tools, list)

    # Execute a tool (mock)
    if tools:
        tool_name = tools[0]["name"]
        r = requests.post(f"{BASE}/tools/execute", json={"server_id": sid, "tool": tool_name, "args": {"query": "test"}})
        assert r.ok, r.text
        resp = r.json()
        assert resp.get("success") is True

    # Cleanup
    r = requests.delete(f"{BASE}/servers/{sid}")
    assert r.ok
