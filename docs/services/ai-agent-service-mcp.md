# AI Agent Service - MCP Integration

This document describes the Model Context Protocol (MCP) integration within the ai-agent service.

## Overview

- MCP Server Registry: CRUD API to register AWS/Azure/GCP/custom MCP servers.
- Connection Manager: Launches stdio servers (Node-based) and will support WS/SSE.
- Tool Discovery: Discovers (mocked for MVP) and caches available tools per server.
- Adapters: Unified tool listing and execution endpoints for CrewAI/AutoGen usage.
- UI: Settings > MCP Servers tab to manage servers and trigger discovery.

## APIs (ai-agent-service)

Base: http://localhost:8008/api/mcp

- GET /servers: List configured servers
- POST /servers: Create server (body: MCPServerConfig)
- PUT /servers/{id}: Update server
- DELETE /servers/{id}: Delete server
- POST /servers/{id}/discover: Connect and discover tools; caches the list
- GET /servers/{id}/tools: Get cached tools
- POST /tools/execute: Execute a tool (body: { server_id, tool, args })

Note: For MVP, discovery and execution are mocked; stdio process is spawned.

### AutoGen passthrough (optional)

Base: http://localhost:8008/api/autogen

- GET /mcp/tools: List all cached MCP tools across servers
- POST /mcp/execute: Execute a tool via AutoGen path (body: { server_id, tool, args })

## Frontend

Settings > MCP Servers tab provides:
- List of servers with provider, transport, status.
- Add/Edit server modal with provider/transport and stdio fields.
- Discover Tools and View Tools actions per server.

Tip: After discovering tools, you can enable MCP tools inside CrewAI agents by setting
ENABLE_MCP_TOOLS_FOR_CREW=true in the ai-agent-service environment. Agents will receive
MCP passthrough tools named like mcp::<provider>::<tool_name>.

## Security & Secrets

- Secrets are represented as SecretRef in schemas; do not store raw secrets.
- Env-based resolver (current): set SecretRef.provider="env" and supply a JSON string in the referenced env var
	- AWS (env var contains JSON):
		{"access_key_id":"...","secret_access_key":"...","session_token":"..."}
		-> Injects AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN (and AWS_REGION if provided in config)
	- Azure (env var contains JSON):
		{"tenant_id":"...","client_id":"...","client_secret":"..."}
		-> Injects AZURE_TENANT_ID / AZURE_CLIENT_ID / AZURE_CLIENT_SECRET
		Also honors tenantId/clientId supplied directly in config.
	- GCP (env var contains service account JSON string):
		-> Writes to a temp file and sets GOOGLE_APPLICATION_CREDENTIALS to that file
- Future: integrate with secret stores (Azure Key Vault, AWS Secrets Manager, GCP Secret Manager).

## Transports

- stdio: Real JSON-RPC handshake is implemented (LSP framing with Content-Length headers): initialize → tools/list; tools/execute uses tools/execute RPC.
- ws: WebSocket JSON-RPC handshake implemented: initialize → tools/list.
- sse: Not yet implemented; returns a warning. Provide specific endpoint details if SSE servers are needed and we’ll wire it next.

## Roadmap

- Implement full MCP handshake for stdio and ws/sse transports.
- Real tool schema discovery and execution.
- Per-tenant visibility and policies.
- CrewAI and AutoGen dynamic tool registration.

## Testing

- Use the UI to add a "custom" stdio server and run Discover (mock list returned).
- Call APIs directly for smoke testing.
