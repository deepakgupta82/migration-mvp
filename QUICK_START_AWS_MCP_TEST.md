# Quick Start: Test AWS Pricing MCP

## 1. Prerequisites Check
```powershell
# Ensure Docker is running
docker ps

# Ensure ai-agent-service is running (port 8008)
curl http://localhost:8008/health
```

## 2. Set Up AWS Credentials

**Option A: Using the script (Recommended)**
```powershell
# Copy template
Copy-Item .env.aws.template .env.aws

# Edit and add your AWS credentials
notepad .env.aws

# Start the service (loads credentials automatically)
.\start_aws_pricing_mcp.ps1
```

**Option B: Manual setup**
```powershell
# Set environment variables
$env:AWS_ACCESS_KEY_ID = "your_access_key"
$env:AWS_SECRET_ACCESS_KEY = "your_secret_key"
$env:AWS_REGION = "us-east-1"

# Start container
docker-compose up -d aws-pricing-mcp
```

## 3. Verify Container is Running
```powershell
# Check container status
docker-compose ps aws-pricing-mcp

# View logs
docker-compose logs -f aws-pricing-mcp
```

## 4. Register with AI Agent Service
```powershell
cd services\ai-agent-service
.venv\Scripts\python.exe scripts\init_aws_pricing_mcp.py --docker
```

**Expected output:**
```
✅ AWS Pricing MCP Server registered successfully!
   - Server ID: <uuid>
   - Name: aws-pricing-mcp-server
   - Provider: aws
   - Transport: stdio
   - Docker mode: True
```

## 5. Test MCP Integration
```powershell
cd ..\..  # Back to project root
.\test_aws_pricing_mcp.ps1 -Discover -TestTool
```

**What it does:**
- ✅ Checks AI Agent service health
- ✅ Lists all registered MCP servers
- ✅ Gets AWS Pricing server details
- ✅ Discovers available tools
- ✅ Executes a test tool

## 6. Configure Project in UI

1. Open browser: `http://localhost:3000`
2. Navigate to your project
3. Go to **LLM Configuration** tab
4. Find **Conversation / Discussion** section
5. Configure:
   - **Use Default**: Toggle OFF for custom settings
   - **Provider**: OpenAI / Anthropic / Google
   - **Model**: gpt-4 / claude-3-sonnet / gemini-2.0-pro
   - **Temperature**: 0.1
6. Click **Save**

## 7. Test in Discussion Tab

1. Click **Discussion** tab
2. Start a new conversation
3. Try these prompts:

```
What are the EC2 instance pricing options in us-east-1?
```

```
Compare the cost of t3.medium vs t3.large instances.
```

```
What's the pricing for S3 Standard storage in eu-west-1?
```

4. Observe:
   - ✅ Agent should invoke AWS Pricing MCP tools
   - ✅ Response includes real pricing data
   - ✅ Check logs for MCP tool execution

## 8. Verify Tool Execution

Check ai-agent-service logs:
```powershell
docker-compose logs -f ai-agent-service | Select-String "mcp"
```

Look for:
- `MCP tool discovery`
- `Executing MCP tool: get_service_pricing`
- `MCP tool result:`

## Troubleshooting

### Container won't start
```powershell
# Rebuild without cache
docker-compose build --no-cache aws-pricing-mcp

# Check for errors
docker-compose logs aws-pricing-mcp
```

### Registration fails
```powershell
# Ensure ai-agent-service is running
curl http://localhost:8008/health

# Check Python environment
cd services\ai-agent-service
.venv\Scripts\python.exe --version
```

### Tools not discovered
```powershell
# Test API directly
$headers = @{"Content-Type" = "application/json"}
Invoke-RestMethod -Method GET -Uri "http://localhost:8008/api/mcp/servers" -Headers $headers

# Try discovery manually
$serverId = "<server-id-from-above>"
Invoke-RestMethod -Method POST -Uri "http://localhost:8008/api/mcp/servers/$serverId/discover" -Headers $headers
```

### AWS credentials error
```powershell
# Verify credentials are set
$env:AWS_ACCESS_KEY_ID
$env:AWS_SECRET_ACCESS_KEY

# Test with AWS CLI (if installed)
aws sts get-caller-identity --region us-east-1

# Check IAM permissions for pricing:* actions
```

## Useful Commands

```powershell
# View all MCP servers
Invoke-RestMethod http://localhost:8008/api/mcp/servers | ConvertTo-Json

# Restart container
docker-compose restart aws-pricing-mcp

# Stop container
docker-compose stop aws-pricing-mcp

# Remove container
docker-compose down aws-pricing-mcp

# Rebuild and restart
docker-compose up -d --build aws-pricing-mcp
```

## Expected Results

✅ **Container Running**: `docker-compose ps` shows `aws_pricing_mcp_service` as `Up`
✅ **Registered**: API returns server with name `aws-pricing-mcp-server`
✅ **Tools Discovered**: Discovery returns list of pricing tools
✅ **Test Tool Works**: Tool execution returns AWS pricing data
✅ **UI Shows Config**: Conversation section visible in LLM config tab
✅ **Discussion Works**: Agents can invoke MCP tools in conversations

## Next Steps

After successful testing:

1. **Add to Production**:
   - Set up AWS IAM role for production
   - Use AWS Secrets Manager for credentials
   - Configure monitoring and alerting

2. **Expand MCP Capabilities**:
   - Add more AWS MCP servers (EC2, S3, etc.)
   - Create custom MCP servers for migration tools
   - Integrate with other cloud providers

3. **Optimize Performance**:
   - Tune rate limits and concurrency
   - Enable caching for pricing data
   - Monitor MCP tool execution times

## Support

- 📖 Full docs: `docs/AWS_PRICING_MCP_SETUP.md`
- 📝 Implementation: `IMPLEMENTATION_SUMMARY_CONVERSATION_MCP.md`
- 🐛 Issues: Check container logs and ai-agent-service logs
