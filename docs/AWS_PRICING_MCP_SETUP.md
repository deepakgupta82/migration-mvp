# AWS Pricing MCP Server Integration

## Overview

The AWS Pricing MCP (Model Context Protocol) Server provides AI agents with real-time access to AWS pricing information, cost analysis capabilities, and service catalog exploration. This integration enables intelligent cost planning, optimization recommendations, and pricing comparisons within the migration platform.

## Features

### Pricing Discovery & Information
- **Service catalog exploration**: Discover all AWS services with available pricing information
- **Pricing attribute discovery**: Identify filterable dimensions (instance types, regions, storage classes, etc.)
- **Real-time pricing queries**: Access current pricing data with advanced filtering
- **Multi-region comparisons**: Compare pricing across different AWS regions
- **Bulk data access**: Download complete pricing datasets in CSV/JSON formats

### Cost Analysis & Planning
- **Detailed cost reports**: Generate comprehensive cost analysis with unit pricing and usage scenarios
- **Infrastructure analysis**: Scan CDK and Terraform projects to identify AWS services
- **Architecture patterns**: Get cost considerations for architecture patterns
- **Optimization recommendations**: Receive AWS Well-Architected Framework aligned suggestions

### Natural Language Queries
- Ask questions about AWS pricing in plain English
- Get instant answers from the AWS Pricing API
- Retrieve comprehensive pricing with flexible filtering

## Prerequisites

### 1. AWS Credentials

You need an AWS account with appropriate permissions:

- **IAM Permissions**: Your IAM user/role must have `pricing:*` permissions
- **Cost**: All pricing API calls are **free of charge**
- **Data**: The server only accesses generally available pricing information (no user-specific data)

### 2. Python & uv Package Manager

For local development:
```bash
# Install uv
pip install uv

# Or follow https://docs.astral.sh/uv/getting-started/installation/
```

### 3. Docker (for containerized deployment)

Ensure Docker and Docker Compose are installed.

## Installation

### Option 1: Docker Deployment (Recommended for Production)

#### Step 1: Configure AWS Credentials

You have two options for providing AWS credentials:

**Option A: Environment Variables** (in `docker-compose.yml`):
```yaml
aws-pricing-mcp:
  environment:
    - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
    - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
    - AWS_SESSION_TOKEN=${AWS_SESSION_TOKEN}  # For temporary credentials
    - AWS_REGION=us-east-1
```

**Option B: Mount AWS Config** (in `docker-compose.yml`):
```yaml
aws-pricing-mcp:
  volumes:
    - ~/.aws:/root/.aws:ro
  environment:
    - AWS_PROFILE=default
    - AWS_REGION=us-east-1
```

#### Step 2: Build and Start the Container

```bash
# Build the Docker image
docker-compose build aws-pricing-mcp

# Start the container
docker-compose up -d aws-pricing-mcp

# Check status
docker-compose ps aws-pricing-mcp

# View logs
docker-compose logs -f aws-pricing-mcp
```

#### Step 3: Register with AI Agent Service

```bash
# Navigate to ai-agent-service
cd services/ai-agent-service

# Activate virtual environment
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# Run initialization script for Docker mode
python scripts/init_aws_pricing_mcp.py --docker
```

### Option 2: Local Development (uvx)

#### Step 1: Install the MCP Server

```bash
# Install globally using uvx
uvx awslabs.aws-pricing-mcp-server@latest
```

#### Step 2: Configure AWS Credentials

```bash
# Configure using AWS CLI
aws configure

# Or set environment variables
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_REGION=us-east-1
```

#### Step 3: Register with AI Agent Service

```bash
# Navigate to ai-agent-service
cd services/ai-agent-service

# Activate virtual environment
.venv\Scripts\activate  # Windows

# Run initialization script for local mode
python scripts/init_aws_pricing_mcp.py
```

## Configuration

### MCP Server Configuration

The AWS Pricing MCP server is registered in the AI Agent service's MCP registry with the following configuration:

```json
{
  "name": "aws-pricing-mcp-server",
  "provider": "aws",
  "connection": {
    "transport": "stdio",
    "stdio": {
      "command": "uvx",  // or "docker" for containerized
      "args": ["awslabs.aws-pricing-mcp-server@latest"]
    }
  },
  "auth": {
    "aws": {
      "region": "us-east-1"
    }
  },
  "env": {
    "FASTMCP_LOG_LEVEL": "ERROR",
    "AWS_REGION": "us-east-1"
  },
  "is_enabled": true,
  "rate_limit_rpm": 60,
  "max_concurrency": 4
}
```

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `AWS_ACCESS_KEY_ID` | AWS access key ID | - | Yes* |
| `AWS_SECRET_ACCESS_KEY` | AWS secret access key | - | Yes* |
| `AWS_SESSION_TOKEN` | AWS session token for temporary credentials | - | No |
| `AWS_REGION` | AWS region for pricing API endpoint | `us-east-1` | No |
| `AWS_PROFILE` | AWS profile name from `~/.aws/credentials` | `default` | No |
| `FASTMCP_LOG_LEVEL` | Logging level for MCP server | `ERROR` | No |

*Required unless using AWS profile or IAM role

## Usage

### 1. Discover Available Tools

After registration, discover what tools the AWS Pricing MCP server provides:

```bash
# Using curl
curl -X POST http://localhost:8008/api/mcp/servers/{server_id}/discover

# Response will include available tools like:
# - get_aws_services
# - get_pricing_attributes
# - query_pricing
# - compare_regions
# - generate_cost_report
# etc.
```

### 2. Execute Tools via API

```bash
# Example: Get list of AWS services
curl -X POST http://localhost:8008/api/mcp/tools/execute \
  -H "Content-Type: application/json" \
  -d '{
    "server_id": "{server_id}",
    "tool": "get_aws_services",
    "args": {}
  }'

# Example: Query EC2 pricing
curl -X POST http://localhost:8008/api/mcp/tools/execute \
  -H "Content-Type: application/json" \
  -d '{
    "server_id": "{server_id}",
    "tool": "query_pricing",
    "args": {
      "service": "AmazonEC2",
      "filters": {
        "instanceType": "t3.medium",
        "location": "US East (N. Virginia)",
        "tenancy": "Shared"
      }
    }
  }'
```

### 3. Use in AI Agent Conversations

The AWS Pricing MCP server can be invoked automatically by AI agents during discussions:

```
User: "What's the monthly cost for running a t3.xlarge instance in us-east-1?"

Agent: [Invokes aws-pricing-mcp-server query_pricing tool]
       Based on current AWS pricing, a t3.xlarge instance in us-east-1 costs...
```

## AWS IAM Policy

Create an IAM policy for the MCP server with minimum required permissions:

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

### Issue: "Access Denied" errors

**Cause**: IAM permissions insufficient

**Solution**: 
1. Verify your IAM user/role has `pricing:*` permissions
2. Check AWS credentials are correctly configured
3. Ensure credentials haven't expired (for temporary credentials)

### Issue: MCP server not starting in Docker

**Cause**: AWS credentials not properly mounted/passed

**Solution**:
1. Check `docker-compose.yml` environment variables
2. Verify AWS credentials file exists at `~/.aws/credentials`
3. Check Docker logs: `docker-compose logs aws-pricing-mcp`

### Issue: "Server not found" when executing tools

**Cause**: MCP server not registered

**Solution**:
Run the initialization script:
```bash
python services/ai-agent-service/scripts/init_aws_pricing_mcp.py --docker
```

### Issue: Tools not discovered

**Cause**: Server connectivity or configuration issue

**Solution**:
1. Check server health: `GET /api/mcp/servers/{server_id}`
2. Manually trigger discovery: `POST /api/mcp/servers/{server_id}/discover`
3. Check logs for connection errors

## Security Considerations

### Credentials Management

- **Never** commit AWS credentials to version control
- Use environment variables or AWS profiles
- For production, use IAM roles attached to EC2/ECS instances
- Rotate credentials regularly
- Use temporary credentials (STS) when possible

### Network Security

- The pricing API endpoints are public AWS APIs
- No sensitive data is transmitted (only public pricing info)
- Consider VPC endpoints for AWS API calls in production

### Access Control

- Limit `pricing:*` permissions to only services that need them
- Use separate IAM roles for different environments (dev/staging/prod)
- Monitor CloudTrail logs for pricing API access

## Monitoring & Health Checks

### Health Check Endpoint

The Docker container includes a basic health check. Monitor via:

```bash
# Check container health
docker inspect aws_pricing_mcp_service | grep -A 10 Health

# Check MCP registry status
curl http://localhost:8008/api/mcp/servers
```

### Metrics to Monitor

- **Tool execution success rate**: Track via MCP audit logs
- **Response times**: Monitor latency of pricing queries
- **Rate limiting**: AWS Pricing API has rate limits
- **Circuit breaker status**: Check if server is circuit broken

## Cost Considerations

- **Pricing API Calls**: FREE - no charges for AWS Pricing API usage
- **Data Transfer**: Negligible (pricing data is small JSON responses)
- **Compute**: Minimal - MCP server is lightweight Python process

## Additional Resources

- [AWS Pricing MCP Server GitHub](https://github.com/awslabs/mcp/tree/main/src/aws-pricing-mcp-server)
- [AWS Pricing API Documentation](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/price-changes.html)
- [MCP Protocol Specification](https://modelcontextprotocol.io/)
- [Migration Platform MCP Architecture](./MCP_ARCHITECTURE.md)

## Support

For issues specific to:
- **AWS Pricing MCP Server**: [GitHub Issues](https://github.com/awslabs/mcp/issues)
- **Migration Platform Integration**: Internal support channels
- **AWS Pricing API**: AWS Support
