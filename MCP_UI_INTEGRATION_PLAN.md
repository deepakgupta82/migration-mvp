# MCP Integration with UI Configuration - Implementation Plan
**Date:** January 9, 2025  
**Status:** 📋 PLANNING

## Overview

The platform already has a comprehensive MCP server configuration UI at **Settings → MCP Servers**. The Azure/GCP adapters in cloud-orchestration-service should use these configured MCP servers instead of hardcoding connections.

---

## Current Architecture

### ✅ **What Already Exists:**

#### 1. **UI Layer** (Frontend)
- **Location:** `frontend/src/components/settings/MCPServersPanel.tsx`
- **Route:** `/settings/mcp-servers`
- **Features:**
  - ✅ Provider selection (AWS, Azure, GCP, Custom)
  - ✅ Transport configuration (STDIO, WebSocket, SSE)
  - ✅ Environment variables (credentials)
    - Azure: `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`
    - GCP: `GOOGLE_APPLICATION_CREDENTIALS`
  - ✅ Rate limiting & concurrency controls
  - ✅ Tool discovery & caching
  - ✅ Health monitoring
  - ✅ Enable/disable servers
  - ✅ Tool allowlist/denylist

#### 2. **Backend API** (ai-agent-service)
- **Router:** `app/routers/mcp.py`
- **Endpoints:**
  ```
  GET    /api/mcp/servers              - List all MCP servers
  GET    /api/mcp/servers/{id}         - Get specific server
  POST   /api/mcp/servers              - Create new server
  PUT    /api/mcp/servers/{id}         - Update server
  DELETE /api/mcp/servers/{id}         - Delete server
  POST   /api/mcp/servers/{id}/discover - Discover tools
  GET    /api/mcp/servers/{id}/tools   - Get cached tools
  GET    /api/mcp/servers/{id}/health  - Health check
  GET    /api/mcp/tools                - List all tools (with filters)
  POST   /api/mcp/execute              - Execute MCP tool
  ```

#### 3. **MCP Registry** (ai-agent-service)
- **Location:** `app/repository/mcp_registry.py`
- **Storage:** In-memory (could be PostgreSQL)
- **Functions:**
  - Server CRUD operations
  - Tool caching with TTL
  - Health tracking

#### 4. **MCP Client** (shared common module)
- **Location:** `common/mcp.py`
- **Features:**
  - HTTP client to ai-agent-service
  - Tool execution requests
  - Server listing with filters

---

## Integration Strategy

### **Option A: Direct MCP Server Usage** ✅ **RECOMMENDED**

The cloud-orchestration-service adapters should:

1. **Discover Azure/GCP MCP servers** from ai-agent-service registry
2. **Execute tools** via the MCP execution API
3. **No direct MCP server connections** - all go through ai-agent-service

#### Architecture Flow:
```
User (UI) → cloud-orchestration-service → ai-agent-service (MCP Control Plane) → Azure/GCP MCP Server
```

#### Benefits:
- ✅ Single source of truth for MCP configuration
- ✅ Centralized credential management
- ✅ Rate limiting & concurrency control
- ✅ Tool discovery caching
- ✅ Health monitoring
- ✅ User can configure servers via UI
- ✅ No code changes needed when adding new servers

---

## Implementation Tasks

### **Task 1: Update Azure MCP Adapter to Use Registry** 🔧

**File:** `services/cloud-orchestration-service/app/adapters/azure_mcp_adapter.py`

**Changes:**

```python
class AzureMCPAdapter:
    """Adapter for Azure migration operations via MCP."""
    
    def __init__(self, mcp_client: Optional[MCPClient] = None):
        self.mcp_client = mcp_client or MCPClient(
            base_url=settings.AI_AGENT_SERVICE_URL
        )
        self.provider = "azure"
        self._server_cache = None
        self._cache_expires_at = None
    
    async def _get_azure_server(self) -> Optional[str]:
        """
        Get the ID of the first enabled Azure MCP server.
        Caches result for 60 seconds to reduce registry calls.
        """
        now = datetime.utcnow()
        if self._server_cache and self._cache_expires_at and now < self._cache_expires_at:
            return self._server_cache
        
        # List Azure servers from registry
        servers = await self.mcp_client.list_servers(provider="azure")
        
        # Find first enabled server
        azure_server = next(
            (s for s in servers if s.get("is_enabled", True)),
            None
        )
        
        if azure_server:
            self._server_cache = azure_server["id"]
            self._cache_expires_at = now + timedelta(seconds=60)
            return self._server_cache
        
        logger.warning("No enabled Azure MCP server found in registry")
        return None
    
    async def migrate_assess_server(
        self,
        subscription_id: str,
        resource_group: str,
        project_name: str,
        server_id: str,
        server_details: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Assess server for migration using Azure Migrate."""
        
        # Get Azure MCP server from registry
        server_id = await self._get_azure_server()
        if not server_id:
            raise ValueError(
                "No Azure MCP server configured. "
                "Please register an Azure MCP server in Settings → MCP Servers"
            )
        
        # Execute tool via MCP
        request = ExecuteToolRequest(
            server_id=server_id,
            tool="azure_migrate_assess_server",
            args={
                "subscription_id": subscription_id,
                "resource_group": resource_group,
                "project_name": project_name,
                "server_id": server_id,
                "server_details": server_details,
                "correlation_id": correlation_id
            }
        )
        
        response = await self.mcp_client.execute_tool(request)
        
        if not response.get("success"):
            raise RuntimeError(f"Azure Migrate assessment failed: {response.get('error')}")
        
        return response.get("output", {})
```

**Key Changes:**
1. ✅ Use `list_servers(provider="azure")` to find Azure MCP server
2. ✅ Cache server ID for 60 seconds (reduce registry calls)
3. ✅ Execute tools via `execute_tool()` API
4. ✅ Provide user-friendly error when no Azure server configured
5. ✅ Remove hardcoded server URLs

---

### **Task 2: Update GCP MCP Adapter** 🔧

**File:** `services/cloud-orchestration-service/app/adapters/gcp_mcp_adapter.py`

**Changes:** Same pattern as Azure adapter
- Replace `self.provider = "gcp"`
- Use `list_servers(provider="gcp")`
- Same caching and error handling

---

### **Task 3: Add MCP Server Configuration Guide to UI** 📖

**File:** `frontend/src/components/settings/MCPServersPanel.tsx`

**Enhancement:** Add help text and example configurations

```tsx
<Alert icon={<IconInfoCircle />} title="Azure MCP Server Setup" color="blue" mb="md">
  <Text size="sm">
    To enable Azure migration operations, register an Azure MCP server:
  </Text>
  <List size="sm" mt="xs">
    <List.Item>
      <b>Provider:</b> Select "Azure"
    </List.Item>
    <List.Item>
      <b>Credentials:</b> Enter Azure Client ID, Client Secret, and Tenant ID
    </List.Item>
    <List.Item>
      <b>Transport:</b> STDIO (for local) or WebSocket (for remote)
    </List.Item>
    <List.Item>
      <b>Command:</b> <Code>npx -y @azure/mcp-server</Code> (example)
    </List.Item>
  </List>
</Alert>
```

---

### **Task 4: Create MCP Server Setup Documentation** 📚

**File:** `docs/MCP_SERVER_SETUP.md`

**Content:**
- How to install Azure MCP server (npm package or Docker)
- How to install GCP MCP server
- How to obtain credentials (Azure Service Principal, GCP Service Account)
- How to register servers via UI
- How to test server connectivity
- Troubleshooting common issues

---

### **Task 5: Add MCP Server Validation** ✅

**File:** `services/ai-agent-service/app/routers/mcp.py`

**Enhancement:** Validate required credentials when creating server

```python
@router.post("/servers", response_model=MCPServerConfig)
async def create_server(cfg: MCPServerConfig):
    """Create new MCP server with validation."""
    
    # Validate Azure credentials
    if cfg.provider == "azure":
        required = ["AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET", "AZURE_TENANT_ID"]
        missing = [k for k in required if not cfg.env.get(k)]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Azure MCP server requires: {', '.join(missing)}"
            )
    
    # Validate GCP credentials
    if cfg.provider == "gcp":
        if not cfg.env.get("GOOGLE_APPLICATION_CREDENTIALS"):
            raise HTTPException(
                status_code=400,
                detail="GCP MCP server requires: GOOGLE_APPLICATION_CREDENTIALS"
            )
    
    # Validate AWS credentials
    if cfg.provider == "aws":
        required = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"]
        missing = [k for k in required if not cfg.env.get(k)]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"AWS MCP server requires: {', '.join(missing)}"
            )
    
    reg = get_registry()
    reg.upsert(cfg)
    return cfg
```

---

### **Task 6: Update AWS MCP Adapter to Use Registry** 🔧

**File:** `services/cloud-orchestration-service/app/adapters/aws_mcp_adapter.py`

**Status:** ✅ **COMPLETED**

**Changes Made:**
- Added `_get_aws_server_id()` method with 60-second caching
- Updated all 16 tool execution methods (MGN, DMS, DataSync)
- Replaced `server_id=self.server_id` with `server_id=await self._get_aws_server_id()`
- Replaced `self.client` with `self.mcp_client`
- Added error message: "No enabled AWS MCP server found in registry"

**Services Updated:**
- ✅ AWS Application Migration Service (MGN) - 6 methods
- ✅ AWS Database Migration Service (DMS) - 5 methods  
- ✅ AWS DataSync - 5 methods

---

### **Task 7: Add MCP Server Status Indicators** 🎨

**File:** `frontend/src/components/settings/MCPServersPanel.tsx`

**Enhancement:** Show which services depend on each MCP server

```tsx
<Table.Td>
  <Stack gap={4}>
    <Text fw={600}>{s.name}</Text>
    <Text size="xs" c="dimmed">{s.description}</Text>
    {s.provider === 'azure' && (
      <Badge size="xs" variant="dot" color="blue">
        Used by: Cloud Orchestration
      </Badge>
    )}
    {s.provider === 'gcp' && (
      <Badge size="xs" variant="dot" color="green">
        Used by: Cloud Orchestration
      </Badge>
    )}
    {s.provider === 'aws' && (
      <Badge size="xs" variant="dot" color="orange">
        Used by: Cloud Orchestration
      </Badge>
    )}
  </Stack>
</Table.Td>
```

---

## User Workflow

### **Step 1: Configure Azure MCP Server**

1. Navigate to **Settings → MCP Servers**
2. Click **"Add Server"**
3. Fill in:
   - **Name:** "Azure Migration Server"
   - **Provider:** Azure
   - **Transport:** STDIO
   - **Command:** `npx -y @azure/mcp-server`
   - **Azure Client ID:** `<your-client-id>`
   - **Azure Client Secret:** `<your-client-secret>`
   - **Azure Tenant ID:** `<your-tenant-id>`
4. Click **"Create Server"**
5. Click **"Discover"** to verify connection

### **Step 2: Configure AWS MCP Server**

1. Navigate to **Settings → MCP Servers**
2. Click **"Add Server"**
3. Fill in:
   - **Name:** "AWS Migration Server"
   - **Provider:** AWS
   - **Transport:** STDIO or WebSocket or Lambda
   - **Command (STDIO):** `npx -y @aws/mcp-server`
   - **URL (WebSocket):** `ws://localhost:8082`
   - **AWS Access Key ID:** `<your-access-key-id>`
   - **AWS Secret Access Key:** `<your-secret-access-key>`
   - **AWS Default Region:** `us-east-1` (or your preferred region)
4. Click **"Create Server"**
5. Click **"Discover"** to verify connection and retrieve AWS tools
6. Check **"Health"** shows "healthy"

### **Step 2: Use Azure Migration Features**

1. Navigate to **Cloud Orchestration → Migration Waves**
2. Click **"Create Wave"**
3. Select **Azure** as target platform
4. Configure migration settings
5. The system automatically uses registered Azure MCP server

**No code changes needed!** ✅

---

## Benefits of This Approach

### **For Users:**
- ✅ **UI-based configuration** - No editing config files
- ✅ **Credential security** - Stored in backend, not in code
- ✅ **Easy testing** - Discover and health check buttons
- ✅ **Multiple servers** - Can have dev/prod Azure/GCP/AWS servers
- ✅ **Provider flexibility** - Switch between Azure, GCP, AWS easily
- ✅ **Unified management** - All cloud providers in one interface

### **For Developers:**
- ✅ **No hardcoding** - All config in registry
- ✅ **Testable** - Mock MCP client easily
- ✅ **Maintainable** - One place to update MCP logic
- ✅ **Extensible** - Add new providers without code changes
- ✅ **Observable** - Centralized health monitoring
- ✅ **Consistent pattern** - Azure, GCP, AWS use same approach

### **For Operations:**
- ✅ **Centralized control** - All MCP servers in one place
- ✅ **Rate limiting** - Prevent API quota exhaustion
- ✅ **Credential rotation** - Update in UI, not code
- ✅ **Monitoring** - Health status, last discovery time
- ✅ **Audit trail** - Who configured what servers

---

## Migration Path from Mock to Real

### **Current State:**
```python
# Adapters have hardcoded mock responses
async def migrate_assess_server(...):
    return {"status": "mock", "assessment": {...}}
```

### **Target State:**
```python
# Adapters use MCP registry and real servers
async def migrate_assess_server(...):
    server_id = await self._get_azure_server()
    response = await self.mcp_client.execute_tool(
        ExecuteToolRequest(server_id=server_id, tool="...", args={...})
    )
    return response["output"]
```

### **Migration Steps:**
1. ✅ UI already supports Azure/GCP server registration
2. 🔧 Update adapters to use MCP registry (Tasks 1-2)
3. 📖 Document MCP server setup (Task 4)
4. ✅ Add validation (Task 5)
5. 🎨 Enhance UI (Tasks 3, 6)
6. 🧪 Test with real Azure MCP server
7. 🧪 Test with real GCP MCP server
8. 📝 Update user documentation

---

## Testing Strategy

### **Unit Tests:**
```python
# Test adapter with mocked MCP client
async def test_azure_adapter_no_server():
    client = MockMCPClient(servers=[])
    adapter = AzureMCPAdapter(mcp_client=client)
    
    with pytest.raises(ValueError, match="No Azure MCP server configured"):
        await adapter.migrate_assess_server(...)

async def test_azure_adapter_with_server():
    client = MockMCPClient(servers=[
        {"id": "azure-1", "provider": "azure", "is_enabled": True}
    ])
    adapter = AzureMCPAdapter(mcp_client=client)
    
    result = await adapter.migrate_assess_server(...)
    assert result["success"] == True
```

### **Integration Tests:**
```python
# Test with real MCP server (requires Azure credentials)
@pytest.mark.integration
async def test_real_azure_mcp():
    # Assumes Azure MCP server registered in test environment
    adapter = AzureMCPAdapter()
    result = await adapter.migrate_assess_server(
        subscription_id=TEST_SUBSCRIPTION,
        ...
    )
    assert "assessment_id" in result
```

---

## Rollout Plan

### **Phase 1: Update Adapters** (Week 1)
- ✅ Update Azure adapter to use MCP registry
- ✅ Update GCP adapter to use MCP registry
- ✅ Add unit tests
- ✅ Deploy to development environment

### **Phase 2: Documentation** (Week 1)
- 📖 Create MCP server setup guide
- 📖 Update user documentation
- 🎨 Add UI help text

### **Phase 3: Real MCP Server Testing** (Week 2)
- 🧪 Install Azure MCP server (local)
- 🧪 Configure via UI
- 🧪 Test one Azure operation end-to-end
- 🧪 Install GCP MCP server (local)
- 🧪 Test one GCP operation end-to-end

### **Phase 4: Production Deployment** (Week 3)
- 🚀 Deploy to production
- 📊 Monitor health metrics
- 📝 Collect user feedback
- 🐛 Fix issues

---

## Risk Mitigation

### **Risk 1: No MCP Server Configured**
- **Mitigation:** Clear error message with setup instructions
- **Fallback:** Suggest using Settings → MCP Servers

### **Risk 2: MCP Server Down**
- **Mitigation:** Health monitoring + automatic retry
- **Fallback:** Show last known status, allow manual retry

### **Risk 3: Credential Rotation**
- **Mitigation:** UI allows easy credential update
- **Fallback:** Detailed error logs for auth failures

### **Risk 4: Rate Limiting**
- **Mitigation:** Per-server RPM limits in UI
- **Fallback:** Queue requests, retry with backoff

---

## Next Steps

1. ✅ **Approve this plan**
2. 🔧 **Implement Tasks 1-2** (Update adapters)
3. ✅ **Implement Task 5** (Add validation)
4. 📖 **Implement Tasks 3-4** (Documentation)
5. 🧪 **Test with real Azure MCP server**
6. 🧪 **Test with real GCP MCP server**
7. 📝 **Document results**
8. 🚀 **Deploy to production**

---

**Ready to proceed with implementation?**
