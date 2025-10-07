# Test AWS Pricing MCP Server
# This script tests the complete MCP integration with the AI Agent service

param(
    [string]$ServerId = "",
    [switch]$Discover,
    [switch]$ListTools,
    [switch]$TestTool
)

$ErrorActionPreference = "Stop"
$baseUrl = "http://localhost:8008"

Write-Host "🧪 AWS Pricing MCP Test Suite" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Helper function to make API calls
function Invoke-API {
    param(
        [string]$Method,
        [string]$Endpoint,
        [object]$Body = $null
    )
    
    $uri = "$baseUrl$Endpoint"
    $headers = @{
        "Content-Type" = "application/json"
    }
    
    try {
        if ($Body) {
            $json = $Body | ConvertTo-Json -Depth 10
            Write-Host "  📤 $Method $uri" -ForegroundColor Gray
            $response = Invoke-RestMethod -Uri $uri -Method $Method -Headers $headers -Body $json
        } else {
            Write-Host "  📤 $Method $uri" -ForegroundColor Gray
            $response = Invoke-RestMethod -Uri $uri -Method $Method -Headers $headers
        }
        return $response
    } catch {
        Write-Host "  ❌ API call failed: $_" -ForegroundColor Red
        if ($_.ErrorDetails.Message) {
            Write-Host "  Details: $($_.ErrorDetails.Message)" -ForegroundColor Red
        }
        throw
    }
}

# Step 1: Check if AI Agent service is running
Write-Host "1️⃣  Checking AI Agent Service..." -ForegroundColor Yellow
try {
    $health = Invoke-API -Method GET -Endpoint "/health"
    Write-Host "  ✅ AI Agent service is healthy" -ForegroundColor Green
} catch {
    Write-Host "  ❌ AI Agent service is not responding" -ForegroundColor Red
    Write-Host "  Make sure the service is running on port 8008" -ForegroundColor Yellow
    exit 1
}

# Step 2: List all MCP servers
Write-Host ""
Write-Host "2️⃣  Listing registered MCP servers..." -ForegroundColor Yellow
try {
    $servers = Invoke-API -Method GET -Endpoint "/api/mcp/servers"
    
    if ($servers.Count -eq 0) {
        Write-Host "  ⚠️  No MCP servers registered" -ForegroundColor Yellow
        Write-Host "  Run the init script first:" -ForegroundColor Yellow
        Write-Host "    cd services/ai-agent-service" -ForegroundColor Gray
        Write-Host "    .venv\Scripts\python.exe scripts/init_aws_pricing_mcp.py --docker" -ForegroundColor Gray
        exit 1
    }
    
    Write-Host "  📋 Found $($servers.Count) MCP server(s):" -ForegroundColor Green
    foreach ($server in $servers) {
        $status = if ($server.is_enabled) { "✅ Enabled" } else { "❌ Disabled" }
        Write-Host "    - $($server.name) ($($server.id)) - $status" -ForegroundColor Cyan
        
        # Auto-select AWS Pricing server if not specified
        if (-not $ServerId -and $server.name -like "*aws-pricing*") {
            $Script:ServerId = $server.id
            Write-Host "      🎯 Auto-selected for testing" -ForegroundColor Green
        }
    }
    
    if (-not $ServerId) {
        Write-Host "  ⚠️  AWS Pricing MCP server not found" -ForegroundColor Yellow
        exit 1
    }
    
} catch {
    Write-Host "  ❌ Failed to list servers" -ForegroundColor Red
    exit 1
}

# Step 3: Get server details
Write-Host ""
Write-Host "3️⃣  Getting server details..." -ForegroundColor Yellow
try {
    $serverDetails = Invoke-API -Method GET -Endpoint "/api/mcp/servers/$ServerId"
    Write-Host "  ✅ Server: $($serverDetails.name)" -ForegroundColor Green
    Write-Host "    ID: $($serverDetails.id)" -ForegroundColor Gray
    Write-Host "    Provider: $($serverDetails.provider)" -ForegroundColor Gray
    Write-Host "    Transport: $($serverDetails.connection.transport)" -ForegroundColor Gray
    Write-Host "    Enabled: $($serverDetails.is_enabled)" -ForegroundColor Gray
} catch {
    Write-Host "  ❌ Failed to get server details" -ForegroundColor Red
    exit 1
}

# Step 4: Discover tools
if ($Discover -or $ListTools -or $TestTool) {
    Write-Host ""
    Write-Host "4️⃣  Discovering available tools..." -ForegroundColor Yellow
    try {
        $discovery = Invoke-API -Method POST -Endpoint "/api/mcp/servers/$ServerId/discover"
        
        if ($discovery.tools) {
            Write-Host "  ✅ Discovered $($discovery.tools.Count) tools:" -ForegroundColor Green
            foreach ($tool in $discovery.tools) {
                Write-Host "    📦 $($tool.name)" -ForegroundColor Cyan
                if ($tool.description) {
                    Write-Host "       $($tool.description)" -ForegroundColor Gray
                }
            }
        } else {
            Write-Host "  ⚠️  No tools discovered" -ForegroundColor Yellow
        }
        
        $Script:availableTools = $discovery.tools
    } catch {
        Write-Host "  ❌ Failed to discover tools" -ForegroundColor Red
        Write-Host "  This might indicate:" -ForegroundColor Yellow
        Write-Host "    - AWS credentials not configured correctly" -ForegroundColor Yellow
        Write-Host "    - Docker container not running" -ForegroundColor Yellow
        Write-Host "    - MCP server connection error" -ForegroundColor Yellow
        exit 1
    }
}

# Step 5: Test a tool
if ($TestTool) {
    Write-Host ""
    Write-Host "5️⃣  Testing AWS Pricing MCP tool..." -ForegroundColor Yellow
    
    # Try to find a simple tool to test
    $testToolName = $null
    $testArgs = @{}
    
    if ($availableTools) {
        # Look for common AWS Pricing tools
        $simpleTools = @("get_aws_services", "list_services", "get_service_list")
        foreach ($toolName in $simpleTools) {
            if ($availableTools | Where-Object { $_.name -eq $toolName }) {
                $testToolName = $toolName
                break
            }
        }
        
        # Fallback to first available tool
        if (-not $testToolName -and $availableTools.Count -gt 0) {
            $testToolName = $availableTools[0].name
        }
    }
    
    if ($testToolName) {
        Write-Host "  🔧 Testing tool: $testToolName" -ForegroundColor Cyan
        
        try {
            $toolRequest = @{
                server_id = $ServerId
                tool = $testToolName
                args = $testArgs
            }
            
            $result = Invoke-API -Method POST -Endpoint "/api/mcp/tools/execute" -Body $toolRequest
            
            Write-Host "  ✅ Tool executed successfully!" -ForegroundColor Green
            Write-Host ""
            Write-Host "  📊 Result:" -ForegroundColor Cyan
            $result | ConvertTo-Json -Depth 10 | Write-Host -ForegroundColor Gray
            
        } catch {
            Write-Host "  ❌ Tool execution failed" -ForegroundColor Red
        }
    } else {
        Write-Host "  ⚠️  No suitable test tool found" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "✅ Testing complete!" -ForegroundColor Green
Write-Host ""
Write-Host "📝 Next steps:" -ForegroundColor Cyan
Write-Host "  1. Configure conversation_llm_config for a project in the UI" -ForegroundColor Gray
Write-Host "  2. Open the Discussion tab" -ForegroundColor Gray
Write-Host "  3. Start a conversation mentioning AWS pricing" -ForegroundColor Gray
Write-Host "  4. The agent should use AWS Pricing MCP tools automatically" -ForegroundColor Gray
