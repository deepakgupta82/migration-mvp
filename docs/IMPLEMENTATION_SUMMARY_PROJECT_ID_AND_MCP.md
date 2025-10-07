# Implementation Summary: LLM Config Fix & AWS Pricing MCP Integration

## Date: October 6, 2025

## Overview

This document summarizes the implementation of two major improvements:
1. **Fixed missing `project_id` in discussion/autogen LLM requests** 
2. **Removed all hardcoded LLM configurations**
3. **Configured AWS Pricing MCP Server integration**

---

## 1. Fixed Discussion Error: "Project ID is required by policy"

### Problem
When initiating a discussion in the Discussion tab, users received:
```
Error: Error processing LLM request: Project ID is required by policy: enforce_project_llm=true
```

### Root Cause
The `autogen_copilot.py` was not including `project_id` in the payload when calling the LLM service's `/api/llm/chat/completions` endpoint, despite the project being available in the discussion flow.

### Solution
Updated all LLM service calls in `autogen_copilot.py` to include `project_id`:

**Files Modified:**
- `services/ai-agent-service/app/core/autogen_copilot.py` (Lines 191, 810)

**Changes:**
```python
# Before
llm_payload = {
    "messages": [...],
    "model": self.llm_config.get("model"),
    "provider": self.llm_config.get("provider")
}

# After
llm_payload = {
    "messages": [...],
    "model": self.llm_config.get("model"),
    "provider": self.llm_config.get("provider"),
    "project_id": self.llm_config.get("project_id"),  # Required for ENFORCE_PROJECT_LLM policy
    "process_type": "conversation"  # Use conversation process type
}
```

---

## 2. Removed Hardcoded LLM Configurations

### Problem
Multiple hardcoded LLM model fallbacks were found across the codebase:
- `gpt-4` in 4 locations
- `gemini-2.5-pro` in 1 location  
- `gpt-3.5-turbo` in 1 location

This violates the principle that all LLM configurations should come from project-specific or process-specific settings.

### Hardcoded Values Removed

#### A. `services/ai-agent-service/main.py`
```python
# Before (Line 162)
"model": os.getenv("AUTOGEN_MODEL", "gpt-4")

# After  
"model": None  # Must be supplied per project request via conversation_llm_config
```

#### B. `services/ai-agent-service/app/core/autogen_copilot.py`
Multiple locations updated:

1. **Line 152** - Model Client Wrapper:
```python
# Before
model = self._base.get("model") or "gpt-4"

# After
model = self._base.get("model")
if not model:
    raise ValueError("Model not configured - project LLM config must include 'model'")
```

2. **Lines 234, 246** - Fallback configurations:
```python
# Before
"model": self.llm_config.get("model", "gpt-4")

# After
"model": self.llm_config.get("model")
```

3. **Line 810** - LLM Service call:
```python
# Before
"model": self.llm_config.get("model", "gemini-2.5-pro")

# After
"model": self.llm_config.get("model")
```

### Process-Specific Configuration Added

**New Database Column:**
```sql
ALTER TABLE projects 
ADD COLUMN conversation_llm_config TEXT NULL;
```

This allows projects to configure a specific LLM for conversation/discussion/autogen processes, separate from other processes like entity extraction or RAG synthesis.

**Migration Script:**
- `services/project-service/migrations/add_conversation_llm_config.py`

**File Modified:**
- `services/project-service/database.py` (Line 100)

---

## 3. AWS Pricing MCP Server Integration

### Docker Configuration

**New Dockerfile:**
- `docker/aws-pricing-mcp.Dockerfile`

**Updated Docker Compose:**
- `docker-compose.yml` - Added `aws-pricing-mcp` service on port 9051

### MCP Models Enhancement

**File Modified:**
- `services/ai-agent-service/app/core/mcp_models.py`

**Changes:**
```python
class AWSAuth(BaseModel):
    credentials: Optional[SecretRef] = None
    access_key_id: Optional[str] = Field(None)  # NEW: Direct AWS access key
    secret_access_key: Optional[str] = Field(None)  # NEW: Direct AWS secret
    session_token: Optional[str] = Field(None)  # NEW: Temporary credentials
    region: Optional[str] = None
    roleArn: Optional[str] = None
    externalId: Optional[str] = None
```

This allows users to input AWS credentials directly in the UI instead of requiring environment variable references.

### Secret Resolver Update

**File Modified:**
- `services/ai-agent-service/app/core/secret_resolver.py` (build_env_for_mcp function)

**Enhancement:**
The resolver now checks for direct `access_key_id` and `secret_access_key` fields first before falling back to `credentials` SecretRef. This provides better UX for simple setups while still supporting secure secret management.

### Initialization Script

**New File:**
- `services/ai-agent-service/scripts/init_aws_pricing_mcp.py`

**Usage:**
```bash
# For Docker deployment
python scripts/init_aws_pricing_mcp.py --docker

# For local uvx deployment
python scripts/init_aws_pricing_mcp.py
```

### Documentation

**New Comprehensive Guide:**
- `docs/AWS_PRICING_MCP_SETUP.md` - Complete setup, configuration, troubleshooting guide

**Updated Service Docs:**
- `docs/services/ai-agent-service-mcp.md` - Added AWS Pricing MCP quick setup section

---

## Required IAM Permissions

For the AWS Pricing MCP Server to function, AWS credentials must have:

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

**Note:** AWS Pricing API calls are **FREE** - no charges incurred.

---

## Next Steps

### 1. Database Migration
Run the migration to add the `conversation_llm_config` column:

```bash
cd services/project-service
python migrations/add_conversation_llm_config.py
```

### 2. UI Updates Required

#### A. Project LLM Configuration UI
Add "Conversation/Discussion" tab in project LLM settings page:

**Location:** `frontend/src/components/ProjectSettings/LLMConfiguration.tsx` (or similar)

**Fields to Add:**
- Provider dropdown (OpenAI, Anthropic, Google, etc.)
- Model input (gpt-4, claude-3-5-sonnet, gemini-2.0-flash-exp, etc.)
- Temperature slider
- Max tokens input

**API Endpoint:**
```
PUT /api/projects/{project_id}/llm-config
Body: {
  "conversation_llm_config": {
    "provider": "openai",
    "model": "gpt-4",
    "temperature": 0.7,
    "max_tokens": 2000
  }
}
```

#### B. MCP Server Configuration UI
Update the MCP server configuration modal:

**Location:** `frontend/src/components/Settings/MCPServers.tsx` (or similar)

**New Fields for AWS Provider:**
- AWS Access Key ID (text input, type="password")
- AWS Secret Access Key (text input, type="password")
- AWS Session Token (text input, type="password", optional)
- AWS Region (dropdown with common regions)

**Conditional Display:**
Only show these fields when `provider === "aws"`

**Save Logic:**
```javascript
if (provider === "aws") {
  config.auth = {
    aws: {
      access_key_id: accessKeyId,
      secret_access_key: secretAccessKey,
      session_token: sessionToken || null,
      region: region || "us-east-1"
    }
  };
}
```

### 3. Build & Test AWS Pricing MCP

```bash
# Build the Docker image
docker-compose build aws-pricing-mcp

# Start the container
docker-compose up -d aws-pricing-mcp

# Check logs
docker-compose logs -f aws-pricing-mcp

# Register with AI Agent service
cd services/ai-agent-service
.venv\Scripts\activate
python scripts/init_aws_pricing_mcp.py --docker
```

### 4. Discover & Test Tools

```bash
# Get server ID from registration output, then:

# Discover available tools
curl -X POST http://localhost:8008/api/mcp/servers/{server_id}/discover

# Test a tool
curl -X POST http://localhost:8008/api/mcp/tools/execute \
  -H "Content-Type: application/json" \
  -d '{
    "server_id": "{server_id}",
    "tool": "get_aws_services",
    "args": {}
  }'
```

### 5. Test with AutoGen/CrewAI

Once tools are discovered, they can be invoked by AutoGen and CrewAI agents during discussions:

**Example Discussion:**
```
User: "What's the monthly cost for running 10 t3.xlarge instances in us-east-1?"

Agent: [Automatically invokes aws-pricing-mcp query_pricing tool]
       Based on current AWS pricing, 10 t3.xlarge instances...
```

---

## Breaking Changes

### ⚠️ Important: Projects Must Configure Conversation LLM

**Before:**
Projects could use discussions without explicit configuration because of hardcoded fallbacks.

**After:**
Projects MUST configure either:
1. **Conversation-specific LLM config** (preferred): Set `conversation_llm_config`
2. **Project default LLM config**: Set `llm_provider`, `llm_model`, `llm_api_key_id`

**Error if Not Configured:**
```
LLM config error: Incomplete project LLM configuration: missing model, api_key.
Please set the project's default LLM (provider, model, api_key) before using discussions.
```

### Migration Path for Existing Projects

For projects that were relying on hardcoded `gpt-4` or `gemini-2.5-pro`:

1. **Update project default LLM config via UI** (Settings > LLM Configuration)
2. **OR use API:**
```bash
curl -X PUT http://localhost:8002/api/projects/{project_id} \
  -H "Content-Type: application/json" \
  -d '{
    "llm_provider": "openai",
    "llm_model": "gpt-4",
    "llm_api_key_id": "your-key-reference"
  }'
```

---

## Testing Checklist

- [ ] Run database migration for `conversation_llm_config`
- [ ] Verify project LLM config is required for discussions
- [ ] Test discussion with conversation-specific LLM config
- [ ] Test discussion with project default LLM config
- [ ] Build AWS Pricing MCP Docker image
- [ ] Start AWS Pricing MCP container
- [ ] Register AWS Pricing MCP with AI Agent service
- [ ] Discover tools from AWS Pricing MCP server
- [ ] Execute a test tool (e.g., get_aws_services)
- [ ] Test AWS Pricing MCP tool invocation from AutoGen discussion
- [ ] UI: Add conversation LLM config fields
- [ ] UI: Add AWS credentials fields for MCP servers
- [ ] UI: Test MCP server creation with AWS credentials
- [ ] UI: Verify AWS credentials are securely stored (not visible in responses)

---

## Security Considerations

### AWS Credentials in MCP Config

**Current Implementation:**
- Credentials are stored in the `AWSAuth` model fields
- They are passed to MCP server via environment variables
- **TODO:** Encrypt sensitive fields before storing in database
- **TODO:** Implement secure vault integration (Azure Key Vault, AWS Secrets Manager)

**Recommendations:**
1. For production, use SecretRef with vault provider instead of direct fields
2. Implement field-level encryption for `access_key_id` and `secret_access_key`
3. Add audit logging for credential access
4. Implement credential rotation policies

### LLM API Keys

**Current Implementation:**
- API keys are referenced by `llm_api_key_id`
- Actual keys stored in separate secrets table
- Keys are resolved at runtime, never exposed in responses

**No Changes Required:** Existing security is adequate.

---

## Files Modified Summary

### Backend Changes
1. `services/ai-agent-service/app/core/autogen_copilot.py` - Fixed project_id, removed hardcoded models
2. `services/ai-agent-service/main.py` - Removed hardcoded AUTOGEN_MODEL fallback
3. `services/ai-agent-service/app/core/mcp_models.py` - Added AWS credential fields
4. `services/ai-agent-service/app/core/secret_resolver.py` - Enhanced AWS auth resolution
5. `services/project-service/database.py` - Added conversation_llm_config column

### New Files
1. `docker/aws-pricing-mcp.Dockerfile` - AWS Pricing MCP Docker image
2. `docker-compose.yml` - Added aws-pricing-mcp service
3. `services/ai-agent-service/scripts/init_aws_pricing_mcp.py` - MCP server registration
4. `services/project-service/migrations/add_conversation_llm_config.py` - Database migration
5. `docs/AWS_PRICING_MCP_SETUP.md` - Comprehensive setup guide
6. `docs/HARDCODED_LLM_REMOVAL_PLAN.md` - Analysis and planning document

### Documentation Updates
1. `docs/services/ai-agent-service-mcp.md` - Added AWS Pricing MCP section

---

## Support & Troubleshooting

### Issue: Discussion fails with "Project ID is required"
**Solution:** Ensure the discussion endpoint is passing `project_id` to autogen copilot (should be fixed by changes in autogen_copilot.py)

### Issue: Discussion fails with "Model not configured"
**Solution:** Set up project LLM configuration (either conversation-specific or default)

### Issue: AWS Pricing MCP tools not discovered
**Solution:**
1. Check Docker container is running: `docker ps | grep aws_pricing`
2. Check AWS credentials are configured
3. Manually trigger discovery: `POST /api/mcp/servers/{server_id}/discover`

### Issue: AWS Pricing MCP returns "Access Denied"
**Solution:** Verify IAM permissions include `pricing:*` actions

---

## Conclusion

These changes establish a more robust, secure, and flexible LLM configuration system while adding powerful AWS pricing analysis capabilities to the platform. The removal of hardcoded fallbacks ensures consistent configuration across all projects and processes.
