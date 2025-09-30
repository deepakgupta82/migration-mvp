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

## Frontend

Settings > MCP Servers tab provides:
- List of servers with provider, transport, status.
- Add/Edit server modal with provider/transport and stdio fields.
- Discover Tools and View Tools actions per server.

## Security & Secrets

- Secrets are represented as SecretRef in schemas; do not store raw secrets.
- Future: integrate with secret stores (Azure Key Vault, AWS Secrets Manager, GCP Secret Manager).

## Roadmap

- Implement full MCP handshake for stdio and ws/sse transports.
- Real tool schema discovery and execution.
- Per-tenant visibility and policies.
- CrewAI and AutoGen dynamic tool registration.

## Testing

- Use the UI to add a "custom" stdio server and run Discover (mock list returned).
- Call APIs directly for smoke testing.
