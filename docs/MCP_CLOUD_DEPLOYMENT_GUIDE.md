# MCP Servers Cloud Deployment Architecture Guide

## Executive Summary

This guide explains how Model Context Protocol (MCP) servers work in your current dev environment and how they will function when deployed to the cloud (Azure/AWS/GCP).

---

## Current Architecture (Dev Machine)

### How MCP Servers Work Now

```
┌─────────────────────────────────────────────────────────────┐
│ Dev Machine (localhost)                                      │
│                                                              │
│  ┌─────────────────┐                                        │
│  │ Frontend (3000) │                                        │
│  └────────┬────────┘                                        │
│           │                                                  │
│           ▼                                                  │
│  ┌─────────────────┐                                        │
│  │ Backend (8000)  │                                        │
│  └────────┬────────┘                                        │
│           │                                                  │
│           ▼                                                  │
│  ┌──────────────────────┐                                   │
│  │ AI Agent Service     │                                   │
│  │ (8008)               │                                   │
│  │                      │                                   │
│  │  MCP Connection Mgr  │                                   │
│  └────────┬─────────────┘                                   │
│           │                                                  │
│           │ spawns subprocess via Popen()                   │
│           │                                                  │
│           ▼                                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ MCP Server Processes (local subprocesses)            │  │
│  │                                                       │  │
│  │  ┌─────────────────┐  ┌──────────────────┐          │  │
│  │  │ AWS Pricing MCP │  │ AWS Knowledge    │          │  │
│  │  │ (uvx python)    │  │ (node index.js)  │          │  │
│  │  │ Port: stdio     │  │ Port: stdio      │          │  │
│  │  └─────────────────┘  └──────────────────┘          │  │
│  │                                                       │  │
│  │  ┌─────────────────┐  ┌──────────────────┐          │  │
│  │  │ AWS S3 MCP      │  │ AWS IAM MCP      │          │  │
│  │  │ (npx)           │  │ (npx)            │          │  │
│  │  │ Port: stdio     │  │ Port: stdio      │          │  │
│  │  └─────────────────┘  └──────────────────┘          │  │
│  └──────────────────────────────────────────────────────┘  │
│           ▲                                                  │
│           │ stdin/stdout communication (JSON-RPC 2.0)       │
│           │                                                  │
└───────────┴──────────────────────────────────────────────────┘
```

**Key Points (Dev)**:
1. **MCP servers run as local subprocesses** - spawned by `ai-agent-service`
2. **Communication via STDIO** - JSON-RPC 2.0 over stdin/stdout pipes
3. **No network ports** - pure process-to-process communication
4. **Credentials via environment variables** - passed to subprocess
5. **Lifecycle managed by parent** - ai-agent-service starts/stops them

---

## Cloud Deployment Architecture

### Option 1: Same-Container Deployment (Recommended for MVP)

**Best for**: Quick deployment, simpler infrastructure

```
┌──────────────────────────────────────────────────────────────┐
│ Azure Container Instance / AWS ECS / GCP Cloud Run           │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ ai-agent-service Container                             │  │
│  │                                                         │  │
│  │  ┌──────────────────┐                                  │  │
│  │  │ Python Service   │                                  │  │
│  │  │ (FastAPI)        │                                  │  │
│  │  └────────┬─────────┘                                  │  │
│  │           │                                             │  │
│  │           │ spawns subprocesses (Popen)                │  │
│  │           ▼                                             │  │
│  │  ┌───────────────────────────────────────────────┐    │  │
│  │  │ MCP Server Subprocesses                       │    │  │
│  │  │                                                │    │  │
│  │  │  - uvx aws-pricing-mcp-server (Python)        │    │  │
│  │  │  - node index.js (AWS Knowledge)              │    │  │
│  │  │  - npx aws-s3-mcp-server (Node.js)           │    │  │
│  │  │                                                │    │  │
│  │  │  Environment: AWS_ACCESS_KEY_ID,              │    │  │
│  │  │               AWS_SECRET_ACCESS_KEY           │    │  │
│  │  │               (from Azure Key Vault/          │    │  │
│  │  │                AWS Secrets Manager)           │    │  │
│  │  └───────────────────────────────────────────────┘    │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
│  Container Requirements:                                      │
│  - Python 3.11+ (for ai-agent-service)                       │
│  - Node.js 18+ (for Node-based MCPs)                         │
│  - uv/uvx installed (for Python-based MCPs)                  │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

**Dockerfile Example**:
```dockerfile
FROM python:3.11-slim

# Install Node.js and npm
RUN apt-get update && \
    apt-get install -y nodejs npm curl && \
    npm install -g npx && \
    curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application code
COPY . /app
WORKDIR /app

# Environment variables (injected at runtime from Key Vault)
ENV AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
ENV AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8008"]
```

**Pros**:
- ✅ Simple deployment (single container)
- ✅ Same architecture as dev
- ✅ No networking complexity
- ✅ Easier debugging

**Cons**:
- ⚠️ Container must include Python + Node.js + uv
- ⚠️ Larger container image (~500MB+)
- ⚠️ Resource consumption in single container

---

### Option 2: Sidecar Container Pattern

**Best for**: Production, better isolation

```
┌────────────────────────────────────────────────────────────┐
│ Azure Container Group / AWS ECS Task / K8s Pod             │
│                                                             │
│  ┌─────────────────────┐  ┌──────────────────────────┐    │
│  │ ai-agent-service    │  │ MCP Sidecar Container    │    │
│  │ Container           │  │                          │    │
│  │                     │  │  - Node.js runtime       │    │
│  │  FastAPI app        │  │  - Python runtime        │    │
│  │                     │  │  - All MCP servers       │    │
│  └──────────┬──────────┘  └────────┬─────────────────┘    │
│             │                      │                        │
│             └──────────┬───────────┘                        │
│                        │                                    │
│              Shared: localhost/127.0.0.1                    │
│              OR Unix domain socket                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Communication Options**:
1. **STDIO over shared volume** - MCP servers write to named pipes
2. **Unix domain sockets** - Faster than network, shared filesystem
3. **Localhost TCP** - Simplest but requires port management

**Pros**:
- ✅ Better isolation
- ✅ Independent scaling
- ✅ Easier to update MCP servers
- ✅ Cleaner container images

**Cons**:
- ⚠️ More complex orchestration
- ⚠️ Need K8s or similar orchestrator
- ⚠️ Networking configuration

---

### Option 3: Serverless Functions (Future)

**Best for**: Extreme scale, cost optimization

```
┌──────────────────────────────────────────────────────────┐
│ Serverless Platform                                       │
│                                                           │
│  ┌─────────────────────┐                                 │
│  │ Azure Functions /   │                                 │
│  │ AWS Lambda /        │                                 │
│  │ GCP Cloud Functions │                                 │
│  │                     │                                 │
│  │  ai-agent-service   │                                 │
│  └──────────┬──────────┘                                 │
│             │                                             │
│             │ HTTP/gRPC calls                             │
│             ▼                                             │
│  ┌─────────────────────────────────────────────────┐    │
│  │ MCP Server Functions (separate deployments)     │    │
│  │                                                  │    │
│  │  ┌─────────────┐  ┌──────────────┐             │    │
│  │  │ Pricing     │  │ Knowledge    │             │    │
│  │  │ Function    │  │ Function     │             │    │
│  │  └─────────────┘  └──────────────┘             │    │
│  └─────────────────────────────────────────────────┘    │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

**Requires**:
- Rewrite MCP servers to expose HTTP endpoints
- API Gateway for routing
- Shared state management (Redis/DynamoDB)

**Pros**:
- ✅ Auto-scaling
- ✅ Pay-per-use
- ✅ Zero infrastructure management

**Cons**:
- ⚠️ Major refactoring needed
- ⚠️ Cold start latency
- ⚠️ Not standard MCP anymore

---

## Credential Management in Cloud

### Current (Dev)
```python
# Environment variables in .env file
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=wJal...

# Passed directly to subprocess
env = {
    **os.environ,
    "AWS_ACCESS_KEY_ID": config.env.get("AWS_ACCESS_KEY_ID"),
    "AWS_SECRET_ACCESS_KEY": config.env.get("AWS_SECRET_ACCESS_KEY")
}
```

### Cloud (Production)

**Option A: Azure Key Vault / AWS Secrets Manager**
```python
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

# At runtime, fetch from Key Vault
credential = DefaultAzureCredential()
client = SecretClient(vault_url="https://myvault.vault.azure.net/", credential=credential)

aws_key = client.get_secret("aws-access-key-id").value
aws_secret = client.get_secret("aws-secret-access-key").value

# Pass to MCP subprocess
env = {
    "AWS_ACCESS_KEY_ID": aws_key,
    "AWS_SECRET_ACCESS_KEY": aws_secret
}
```

**Option B: Managed Identity / IAM Roles**
```python
# Best practice: Use cloud provider's managed identity
# No credentials needed - cloud handles authentication

# Azure: Managed Identity
# AWS: IAM Role for Tasks/Containers
# GCP: Workload Identity

# MCP server automatically uses cloud credentials
# No need to pass AWS_ACCESS_KEY_ID
```

**Recommended Approach**:
1. **Database**: Store only encrypted credential references (e.g., Key Vault secret name)
2. **Runtime**: Fetch actual credentials from Key Vault/Secrets Manager
3. **Subprocess**: Pass decrypted credentials as environment variables
4. **Best**: Use Managed Identity where possible (no credentials to manage)

---

## Deployment Steps

### Azure Container Instance Deployment

**1. Build Docker Image**
```bash
# Build multi-runtime image
docker build -t migration-platform-ai-agent:latest .

# Push to Azure Container Registry
az acr login --name myregistry
docker tag migration-platform-ai-agent:latest myregistry.azurecr.io/ai-agent:latest
docker push myregistry.azurecr.io/ai-agent:latest
```

**2. Create Container Instance**
```bash
az container create \
  --resource-group migration-platform-rg \
  --name ai-agent-service \
  --image myregistry.azurecr.io/ai-agent:latest \
  --cpu 2 \
  --memory 4 \
  --registry-login-server myregistry.azurecr.io \
  --registry-username $ACR_USERNAME \
  --registry-password $ACR_PASSWORD \
  --environment-variables \
    AWS_ACCESS_KEY_ID="$(az keyvault secret show --vault-name my-vault --name aws-key --query value -o tsv)" \
    AWS_SECRET_ACCESS_KEY="$(az keyvault secret show --vault-name my-vault --name aws-secret --query value -o tsv)" \
  --ports 8008 \
  --dns-name-label ai-agent-service
```

**3. Configure Networking**
```bash
# Allow inbound on port 8008
# Connect to Azure Virtual Network
az container create ... --vnet my-vnet --subnet ai-agent-subnet
```

---

### AWS ECS Deployment

**1. Create Task Definition**
```json
{
  "family": "ai-agent-service",
  "containerDefinitions": [
    {
      "name": "ai-agent",
      "image": "123456789.dkr.ecr.us-east-1.amazonaws.com/ai-agent:latest",
      "memory": 4096,
      "cpu": 2048,
      "essential": true,
      "portMappings": [{"containerPort": 8008, "protocol": "tcp"}],
      "secrets": [
        {
          "name": "AWS_ACCESS_KEY_ID",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:123:secret:aws-key"
        },
        {
          "name": "AWS_SECRET_ACCESS_KEY",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:123:secret:aws-secret"
        }
      ]
    }
  ]
}
```

**2. Create ECS Service**
```bash
aws ecs create-service \
  --cluster migration-platform \
  --service-name ai-agent-service \
  --task-definition ai-agent-service:1 \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-12345],securityGroups=[sg-12345]}"
```

---

## Resource Requirements

### Per MCP Server
| Server | Runtime | Memory | CPU | Startup Time |
|--------|---------|--------|-----|--------------|
| AWS Pricing | Python (uvx) | ~150MB | 0.1 | ~2s |
| AWS Knowledge | Node.js | ~200MB | 0.1 | ~3s |
| AWS S3 | Node.js (npx) | ~180MB | 0.1 | ~4s |
| AWS IAM | Node.js (npx) | ~180MB | 0.1 | ~4s |

### Recommended Container Specs
- **CPU**: 2 cores minimum (handle multiple concurrent MCP operations)
- **Memory**: 4GB minimum (Python + Node.js + all MCPs)
- **Storage**: 10GB (for npm/pip caches)

---

## Network & Security

### Firewall Rules
```
Inbound:
- Port 8008: ai-agent-service API (from backend service only)

Outbound:
- Port 443: AWS API calls (Pricing, S3, IAM APIs)
- Port 443: Azure/GCP APIs if using multi-cloud MCPs
```

### Security Best Practices
1. **Never commit credentials** to git (use .env, Key Vault)
2. **Encrypt credentials** in database (Phase 6)
3. **Use managed identities** where possible
4. **Rotate credentials** regularly (90 days)
5. **Audit MCP tool executions** (log all AWS API calls)
6. **Least privilege IAM** (grant only needed permissions)

---

## Monitoring & Observability

### Metrics to Track
- MCP subprocess spawns/crashes
- Tool discovery latency
- Tool execution success/failure rates
- Credential fetch times
- Container resource usage

### Logging
```python
# Log MCP operations
logger.info(f"MCP subprocess started: {server_id} (pid={process.pid})")
logger.info(f"Tool discovered: {tool_name} from {server_id}")
logger.error(f"MCP connection failed: {server_id}, error={str(e)}")
```

### Health Checks
```bash
# Container health check
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD curl -f http://localhost:8008/health || exit 1
```

---

## Cost Optimization

### Dev Environment
- **Free**: All MCP servers run locally, no cloud costs

### Cloud Deployment
| Component | Azure | AWS | Monthly Cost (est) |
|-----------|-------|-----|-------------------|
| Container Instance | 2 vCore, 4GB | Fargate 2 vCPU, 4GB | $70-100 |
| Key Vault | Standard tier | Secrets Manager | $3-5 |
| Networking | VNet, NSG | VPC, Security Groups | $10-20 |
| **Total** | | | **$83-125/month** |

**Savings Tips**:
- Use Azure Container Apps (cheaper than ACI for prod)
- Implement auto-scaling (scale to 0 when idle)
- Use spot instances for non-critical workloads
- Cache MCP tool discovery results (reduce AWS API calls)

---

## Migration Path (Dev → Cloud)

### Phase 1: Containerize (Week 1)
- [ ] Create Dockerfile with Python + Node.js
- [ ] Test container locally
- [ ] Validate all MCP servers work in container

### Phase 2: Cloud Secrets (Week 2)
- [ ] Set up Azure Key Vault / AWS Secrets Manager
- [ ] Migrate credentials from .env to Key Vault
- [ ] Update code to fetch secrets at runtime

### Phase 3: Deploy (Week 3)
- [ ] Push image to container registry
- [ ] Deploy to Azure Container Instance / AWS ECS
- [ ] Configure networking and firewall
- [ ] Set up monitoring and alerts

### Phase 4: Optimize (Week 4)
- [ ] Implement credential encryption (Phase 6)
- [ ] Add health checks and auto-restart
- [ ] Set up CI/CD pipeline
- [ ] Load testing and performance tuning

---

## FAQ

### Q: Do MCP servers need their own IP addresses?
**A**: No. MCP servers communicate via STDIO (stdin/stdout) with the parent process. No network required.

### Q: Can I run MCP servers as separate containers?
**A**: Yes, but you'll need to modify the communication from STDIO to HTTP/WebSocket, which breaks MCP standard. Sidecar pattern (same pod/container group) is better.

### Q: How do I update an MCP server?
**A**: 
- **Same container**: Rebuild and redeploy entire image
- **Sidecar**: Update only the sidecar container
- **Serverless**: Deploy new function version

### Q: What if an MCP server crashes?
**A**: The parent process (ai-agent-service) detects the crash and can auto-restart the subprocess. Add retry logic in `mcp_connection.py`.

### Q: Do I need Node.js AND Python in production?
**A**: Yes, if using both Python-based (uvx) and Node-based (npx) MCP servers. Alternative: Convert all to one runtime or use separate containers.

### Q: Can agents work without MCP servers?
**A**: Yes. Agents can function with built-in tools (cloud_catalog, migration_advisor). MCP servers are optional add-ons for AWS/Azure/GCP integrations.

---

## Recommendation

**For your platform, I recommend Option 1 (Same-Container) for MVP**:

✅ **Why**:
1. Simplest deployment (matches dev environment)
2. No networking complexity
3. Faster time to market
4. Easier debugging and troubleshooting
5. Cost-effective for initial scale

🔄 **Future Migration**:
Once you reach scale (1000+ concurrent users), migrate to:
- **Kubernetes** with sidecar pattern for better isolation
- **Managed Identity** to eliminate credential management
- **Auto-scaling** based on agent workload

---

## Next Steps

1. **Test all MCP servers** locally with proper credentials ✅ (in progress)
2. **Create Dockerfile** with Python + Node.js runtimes
3. **Set up Azure Key Vault** or AWS Secrets Manager
4. **Implement Phase 6** (credential encryption in database)
5. **Deploy to cloud** using Option 1 architecture
6. **Monitor and optimize** based on actual usage

---

**Created**: October 7, 2025  
**Author**: Migration Platform Team  
**Status**: Ready for cloud deployment
