# AWS Pricing MCP Server - Simplified Setup

## Overview

This is the **SIMPLIFIED** setup for AWS Pricing MCP integration, following the official AWS Labs recommended approach.

**Key Point**: Use `uvx` directly. No Docker needed!

## Prerequisites

1. **Python 3.10+** and **uv package manager**
2. **AWS Credentials** with `pricing:*` permissions

## Installation (Windows)

###Step 1: Install uv

```powershell
# Install uv
pip install uv

# Verify installation
uv --version
```

### Step 2: Set AWS Credentials

```powershell
# Option A: Set environment variables (recommended for development)
$env:AWS_ACCESS_KEY_ID = "YOUR_ACCESS_KEY"
$env:AWS_SECRET_ACCESS_KEY = "YOUR_SECRET_KEY"
$env:AWS_REGION = "us-east-1"

# Option B: Use AWS CLI configure
aws configure
```

### Step 3: Register MCP Server

```powershell
cd services/ai-agent-service

# Ensure AWS credentials are in environment
python scripts/init_aws_pricing_mcp.py
```

Expected output:
```
✅ AWS Pricing MCP Server registered successfully!
   - Server ID: <uuid>
   - Name: AWS Pricing MCP
   - Provider: aws
   - Transport: stdio
   - Docker mode: False
```

### Step 4: Restart AI Agent Service

The service needs to restart to pick up the new MCP server:

```powershell
# If running via tasks.json
# Stop and restart the ai-agent task

# OR if running via docker-compose
docker-compose restart ai-agent-service

# Wait for service to be ready
Start-Sleep -Seconds 10
```

### Step 5: Discover Tools

```powershell
# Get the server ID from step 3
$serverId = "<your-server-id>"

# Discover available tools
Invoke-RestMethod -Uri "http://localhost:8008/api/mcp/servers/$serverId/discover" -Method Post
```

Expected output: List of AWS pricing tools like:
- `get_pricing_service_codes`
- `get_pricing_attribute_values`  
- `get_pricing`
- `generate_cost_report`
- `get_bedrock_patterns`

## Usage in Discussion Tab

Once registered and tools are discovered:

1. Open the **Discussion** tab in the frontend
2. Ensure `conversation_llm_config` is configured for your project
3. Start a discussion and ask about AWS pricing:
   - "What are the EC2 instance types available in us-east-1?"
   - "Compare pricing for t3.medium vs t3.large"
   - "What's the cost of running a t3.xlarge 24/7 for a month?"

The AutoGen agents will automatically invoke AWS Pricing MCP tools to answer.

## Configuration Details

### MCP Server Config (Auto-generated)

```json
{
  "name": "AWS Pricing MCP",
  "provider": "aws",
  "connection": {
    "transport": "stdio",
    "stdio": {
      "command": "uvx",
      "args": ["awslabs.aws-pricing-mcp-server@latest"]
    }
  },
  "env": {
    "FASTMCP_LOG_LEVEL": "ERROR",
    "AWS_REGION": "us-east-1"
  },
  "is_enabled": true
}
```

### Required AWS IAM Policy

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

## Troubleshooting

### Issue: "AWS credentials not found"

**Solution**: Set environment variables before starting ai-agent-service:

```powershell
$env:AWS_ACCESS_KEY_ID = "YOUR_KEY"
$env:AWS_SECRET_ACCESS_KEY = "YOUR_SECRET"
$env:AWS_REGION = "us-east-1"

# Then start/restart the service
```

### Issue: "No tools discovered" or "Discovered 0 tools"

**Causes**:
1. Service hasn't restarted after registration
2. AWS credentials not accessible to the service
3. `uvx` not in PATH

**Solutions**:
```powershell
# 1. Restart service
docker-compose restart ai-agent-service

# 2. Verify AWS credentials
$env:AWS_ACCESS_KEY_ID
$env:AWS_SECRET_ACCESS_KEY

# 3. Test uvx directly
uvx awslabs.aws-pricing-mcp-server@latest
```

### Issue: Tools work but return "Access Denied"

**Cause**: IAM permissions insufficient

**Solution**: Add `pricing:*` permissions to your IAM user/role

## Why This Approach is Simpler

| Aspect | Overcomplicated (Docker) | Simplified (uvx) |
|--------|--------------------------|------------------|
| **Setup** | Build custom image, docker-compose, env files | Just `pip install uv` |
| **Credentials** | Mount volumes or env files to container | Standard environment variables |
| **Windows Support** | asyncio subprocess issues, LSP framing problems | Works natively |
| **Maintenance** | Manage Docker images, containers, networks | Self-updating via `uvx` |
| **Official** | Custom integration | Recommended by AWS Labs |

## Next Steps

1. ✅ Install `uv`
2. ✅ Set AWS credentials
3. ✅ Register MCP server
4. ✅ Restart ai-agent-service
5. ⏳ Test in Discussion tab

## Related Documentation

- [Official AWS Pricing MCP Server](https://github.com/awslabs/mcp/tree/main/src/aws-pricing-mcp-server)
- [MCP Protocol Specification](https://modelcontextprotocol.io/)
- [AutoGen Framework](https://microsoft.github.io/autogen/)
