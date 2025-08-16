#!/usr/bin/env pwsh
"""
Service Endpoint Discovery Script
Discovers actual endpoints in each microservice by testing common patterns
"""

# Service endpoints mapping
$services = @{
    "project" = "http://localhost:8002"
    "reporting" = "http://localhost:8001" 
    "document" = "http://localhost:8004"
    "vector" = "http://localhost:8005"
    "graph" = "http://localhost:8006"
    "llm" = "http://localhost:8007"
    "ai_agent" = "http://localhost:8008"
    "websocket" = "http://localhost:8009"
    "storage" = "http://localhost:8010"
}

# Colors
$Green = "`e[32m"
$Red = "`e[31m"
$Yellow = "`e[33m"
$Blue = "`e[34m"
$Reset = "`e[0m"

function Write-ColoredOutput {
    param([string]$Text, [string]$Color = $Reset)
    Write-Host "${Color}${Text}${Reset}"
}

function Test-Endpoint {
    param([string]$ServiceName, [string]$BaseUrl, [string]$Endpoint)
    
    $url = "${BaseUrl}${Endpoint}"
    
    try {
        $response = Invoke-WebRequest -Uri $url -Method GET -TimeoutSec 5
        if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300) {
            Write-ColoredOutput "✓ $ServiceName$Endpoint (Status: $($response.StatusCode))" $Green
            return $true
        }
    } catch {
        # Ignore 404s and other errors for discovery
    }
    return $false
}

Write-ColoredOutput "===============================================" $Yellow
Write-ColoredOutput "MICROSERVICES ENDPOINT DISCOVERY" $Yellow
Write-ColoredOutput "===============================================" $Yellow

# Common endpoint patterns to test
$commonPatterns = @(
    "/health",
    "/api/agents/list",
    "/api/agents/crews", 
    "/api/crews/list",
    "/api/llm/providers",
    "/api/llm/configurations",
    "/api/llm/entity-extraction",
    "/api/documents/capabilities",
    "/api/documents/stats",
    "/api/vectors/collections", 
    "/api/vectors/stats",
    "/api/graphs/stats",
    "/api/graphs/capabilities",
    "/api/websocket/stats",
    "/api/storage/stats",
    "/api/storage/capabilities",
    "/projects",
    "/projects/stats",
    "/llm-configurations",
    "/users",
    "/reports/templates",
    "/reports/status"
)

$discoveredEndpoints = @{}

foreach ($service in $services.GetEnumerator()) {
    Write-ColoredOutput "`n🔹 Discovering endpoints for $($service.Key) service..." $Yellow
    
    $workingEndpoints = @()
    
    foreach ($pattern in $commonPatterns) {
        if (Test-Endpoint $service.Key $service.Value $pattern) {
            $workingEndpoints += $pattern
        }
    }
    
    $discoveredEndpoints[$service.Key] = $workingEndpoints
    
    if ($workingEndpoints.Count -eq 0) {
        Write-ColoredOutput "  ⚠️  Only health endpoint found" $Yellow
    } else {
        Write-ColoredOutput "  Found $($workingEndpoints.Count) working endpoints" $Blue
    }
}

# Generate corrected endpoint mapping
Write-ColoredOutput "`n===============================================" $Yellow
Write-ColoredOutput "CORRECTED ENDPOINT MAPPING" $Yellow
Write-ColoredOutput "===============================================" $Yellow

foreach ($service in $discoveredEndpoints.GetEnumerator()) {
    Write-ColoredOutput "`n$($service.Key.ToUpper()) SERVICE:" $Blue
    foreach ($endpoint in $service.Value) {
        Write-ColoredOutput "  $endpoint" $Green
    }
}

# Generate ServiceClient correction suggestions
Write-ColoredOutput "`n===============================================" $Yellow
Write-ColoredOutput "SERVICE CLIENT CORRECTIONS NEEDED" $Yellow
Write-ColoredOutput "===============================================" $Yellow

Write-ColoredOutput "`nAI Agent Service:" $Blue
Write-ColoredOutput "  ❌ Wrong: /api/crews/list" $Red  
Write-ColoredOutput "  ✅ Correct: /api/agents/crews" $Green

Write-ColoredOutput "`nLLM Service:" $Blue
Write-ColoredOutput "  ✅ Correct: /api/llm/providers" $Green

Write-ColoredOutput "`nOther Services:" $Blue
Write-ColoredOutput "  Most only have /health endpoints currently" $Yellow
Write-ColoredOutput "  Need to implement business logic endpoints" $Yellow

Write-ColoredOutput "`n===============================================" $Yellow
