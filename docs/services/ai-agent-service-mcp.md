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

- stdio: Real JSON-RPC handshake implemented (LSP framing with Content-Length headers): initialize → tools/list; tools/execute uses tools/execute RPC.
- ws: WebSocket JSON-RPC handshake implemented: initialize → tools/list.
- sse: Implemented as JSON-RPC over HTTP POST to the configured URL for initialize and tools/list. This covers discovery; streaming over SSE can be extended as needed.

## Policies, Health, and Audit

- Rate limiting: per-server RPM (`rate_limit_rpm`, default 60).
- Concurrency: per-server max concurrent calls (`max_concurrency`, default 4).
- Circuit breaker: opens after `circuit_breaker_threshold` consecutive failures and cools down for `circuit_breaker_cooldown_sec` seconds.
- Discovery cache: tools cached with TTL (`discovery_cache_ttl_sec`, default 900). Expiry triggers a background refresh on GET /tools.
- Health endpoint: `GET /api/mcp/servers/{id}/health` returns status and timestamps.
- Audit logging: `mcp_audit.jsonl` under `AI_AGENT_LOG_DIR` records discovery and execution events with status and duration.

## Seeding Common AWS MCP Servers

On startup, the service seeds disabled templates for the AWS Labs MCP servers (Pricing, S3, IAM, CloudWatch, Bedrock). They are added with `command: noop` as placeholders. To enable:

1) Install the specific MCP server (for example, aws-pricing-mcp-server)
2) Update the server entry with the actual `command`, `args`, and `cwd`
3) Toggle `Enabled` in the UI and click Discover

Example for a Node-based server:

- command: `node`
- args: `["dist/index.js"]`
- cwd: `C:/path/to/aws-pricing-mcp-server`

## Testing

- Use the UI to add a "custom" stdio server and run Discover (mock list returned).
- Call APIs directly for smoke testing.

## AWS Pricing MCP Server Setup

The AWS Pricing MCP Server is a production-ready MCP server that provides real-time AWS pricing information and cost analysis capabilities. 

### Quick Setup

1. **Configure AWS Credentials**:
   ```bash
   # Option 1: Using AWS CLI
   aws configure
   
   # Option 2: Environment variables
   export AWS_ACCESS_KEY_ID=your_key
   export AWS_SECRET_ACCESS_KEY=your_secret
   export AWS_REGION=us-east-1
   ```

2. **Docker Deployment** (Recommended):
   ```bash
   # Start the AWS Pricing MCP container
   docker-compose up -d aws-pricing-mcp
   
   # Register with AI Agent service
   cd services/ai-agent-service
   python scripts/init_aws_pricing_mcp.py --docker
   ```

3. **Local Development**:
   ```bash
   # Install using uvx
   uvx awslabs.aws-pricing-mcp-server@latest
   
   # Register with AI Agent service
   cd services/ai-agent-service
   python scripts/init_aws_pricing_mcp.py
   ```

### Required IAM Permissions

The AWS credentials must have `pricing:*` permissions. Create a policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "pricing:DescribeServices",
        "pricing:GetAttributeValues",
        "pricing:GetProducts"
      ],
      "Resource": "*"
    }
  ]
}
```

**Note**: AWS Pricing API calls are **free of charge**.

### Available Tools

After discovery, the AWS Pricing MCP server provides tools for:
- Service catalog exploration
- Real-time pricing queries
- Multi-region pricing comparisons
- Cost report generation
- Infrastructure cost analysis
- Architecture pattern cost guidance

### Documentation

See [AWS_PRICING_MCP_SETUP.md](../AWS_PRICING_MCP_SETUP.md) for comprehensive setup instructions, troubleshooting, and usage examples.
