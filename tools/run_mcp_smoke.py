import requests
import sys

BASE = "http://localhost:8008/api/mcp"

def main():
    cfg = {
        "name": "Local Mock AWS MCP",
        "provider": "aws",
        "connection": {"transport": "stdio", "stdio": {"command": "noop", "args": []}},
        "env": {},
        "tool_allowlist": [],
        "tool_denylist": [],
        "is_enabled": True,
        "description": "Mock AWS MCP for tests",
    }
    # Create
    r = requests.post(f"{BASE}/servers", json=cfg)
    if not r.ok:
        print("CREATE FAIL", r.status_code, r.text)
        sys.exit(1)
    created = r.json()
    sid = created["id"]
    print("CREATED", sid)

    try:
        # Discover
        r = requests.post(f"{BASE}/servers/{sid}/discover")
        if not r.ok:
            print("DISCOVER FAIL", r.status_code, r.text)
            sys.exit(1)
        tools = r.json()
        print("TOOLS", tools)

        # Execute
        if tools:
            tname = tools[0]["name"]
            r = requests.post(f"{BASE}/tools/execute", json={"server_id": sid, "tool": tname, "args": {"query": "test"}})
            if not r.ok:
                print("EXEC FAIL", r.status_code, r.text)
                sys.exit(1)
            print("EXEC", r.json())
        print("SMOKE PASS")
    finally:
        # Cleanup
        try:
            r = requests.delete(f"{BASE}/servers/{sid}")
            print("DELETED", r.status_code)
        except Exception as e:
            print("DELETE ERROR", e)

if __name__ == "__main__":
    main()
