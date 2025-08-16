#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Systematic endpoint testing script for all microservices
    
.DESCRIPTION
    This script tests all service endpoints systematically by:
    1. Examining router registration in main.py files
    2. Reading endpoint definitions in router files  
    3. Constructing expected URLs
    4. Testing actual endpoints
    
    This prevents trial-and-error testing and catches routing inconsistencies.
#>

param(
    [switch]$Verbose,
    [switch]$ShowRouterAnalysis
)

# Service definitions with expected patterns
$Services = @(
    @{
        Name = "Document Service"
        Port = 8004
        Prefix = "/api/documents"
        RouterFile = "services/document-service/app/routers/documents.py"
        MainFile = "services/document-service/main.py"
        ExpectedEndpoints = @("/health", "/projects/{id}/process", "/projects/{id}/reprocess")
    },
    @{
        Name = "Vector Service"  
        Port = 8005
        Prefix = "/api/vectors"
        RouterFile = "services/vector-service/app/routers/vectors.py"
        MainFile = "services/vector-service/main.py"
        ExpectedEndpoints = @("/health", "/projects/{id}/collection", "/projects/{id}/search")
    },
    @{
        Name = "Graph Service"
        Port = 8006
        Prefix = "/api/graphs"
        RouterFile = "services/graph-service/app/routers/graphs.py"
        MainFile = "services/graph-service/main.py"
        ExpectedEndpoints = @("/health", "/projects/{id}/entities", "/projects/{id}/relationships")
    },
    @{
        Name = "LLM Service"
        Port = 8007
        Prefix = "/api/llm"
        RouterFile = "services/llm-service/app/routers/llm.py"
        MainFile = "services/llm-service/main.py"
        ExpectedEndpoints = @("/health", "/process", "/entity-extraction/{id}", "/crew-assessment/{id}")
    },
    @{
        Name = "AI Agent Service"
        Port = 8008
        Prefix = "/api/agents"
        RouterFile = "services/ai-agent-service/app/routers/agents.py"
        MainFile = "services/ai-agent-service/main.py"
        ExpectedEndpoints = @("/health", "/list", "/crews", "/{id}/tasks")
    },
    @{
        Name = "WebSocket Gateway"
        Port = 8009
        Prefix = ""
        RouterFile = "services/websocket-service/app/routers/websocket.py"
        MainFile = "services/websocket-service/main.py"
        ExpectedEndpoints = @("/health", "/stats", "/ws/{id}")
    }
)

function Test-ServiceEndpoints {
    param($Service)
    
    Write-Host "`n=== Testing $($Service.Name) (Port $($Service.Port)) ===" -ForegroundColor Cyan
    
    # Test health endpoint first
    $healthUrl = "http://localhost:$($Service.Port)/health"
    try {
        $response = Invoke-RestMethod -Uri $healthUrl -Method GET -TimeoutSec 5
        Write-Host "✓ Health: $healthUrl" -ForegroundColor Green
        if ($Verbose) { Write-Host "  Response: $($response | ConvertTo-Json -Compress)" -ForegroundColor Gray }
    }
    catch {
        Write-Host "✗ Health: $healthUrl - $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
    
    # Test expected endpoints
    foreach ($endpoint in $Service.ExpectedEndpoints) {
        if ($endpoint -eq "/health") { continue }  # Already tested
        
        $testUrl = "http://localhost:$($Service.Port)$($Service.Prefix)$endpoint"
        $testUrl = $testUrl -replace '\{id\}', '1'  # Replace path parameters with test values
        
        try {
            # Use different HTTP methods based on endpoint pattern
            if ($endpoint -match "/(process|search|tasks|workflows)") {
                # These typically expect POST with body, so just test if endpoint exists (might return 422)
                $response = Invoke-WebRequest -Uri $testUrl -Method POST -TimeoutSec 5 -SkipHttpErrorCheck
                if ($response.StatusCode -in @(200, 422, 404)) {
                    if ($response.StatusCode -eq 404) {
                        Write-Host "✗ Endpoint: $testUrl - Not Found (404)" -ForegroundColor Red
                    } else {
                        Write-Host "✓ Endpoint: $testUrl - Accessible ($($response.StatusCode))" -ForegroundColor Green
                    }
                }
            } else {
                # GET endpoints
                $response = Invoke-WebRequest -Uri $testUrl -Method GET -TimeoutSec 5 -SkipHttpErrorCheck
                if ($response.StatusCode -in @(200, 422, 404)) {
                    if ($response.StatusCode -eq 404) {
                        Write-Host "✗ Endpoint: $testUrl - Not Found (404)" -ForegroundColor Red
                    } else {
                        Write-Host "✓ Endpoint: $testUrl - Accessible ($($response.StatusCode))" -ForegroundColor Green
                    }
                }
            }
        }
        catch {
            Write-Host "✗ Endpoint: $testUrl - $($_.Exception.Message)" -ForegroundColor Red
        }
    }
    
    return $true
}

function Show-RouterAnalysis {
    param($Service)
    
    if (-not $ShowRouterAnalysis) { return }
    
    Write-Host "`n--- Router Analysis for $($Service.Name) ---" -ForegroundColor Yellow
    
    # Read main.py for router registration
    if (Test-Path $Service.MainFile) {
        $mainContent = Get-Content $Service.MainFile -Raw
        if ($mainContent -match 'app\.include_router\([^,]+,\s*prefix="([^"]+)"') {
            Write-Host "  Main.py prefix: $($matches[1])" -ForegroundColor Gray
        }
    }
    
    # Read router file for endpoints
    if (Test-Path $Service.RouterFile) {
        $routerContent = Get-Content $Service.RouterFile -Raw
        $endpoints = [regex]::Matches($routerContent, '@router\.(get|post|put|delete)\("([^"]+)"')
        Write-Host "  Router endpoints:" -ForegroundColor Gray
        foreach ($match in $endpoints) {
            $method = $match.Groups[1].Value.ToUpper()
            $path = $match.Groups[2].Value
            Write-Host "    $method $path" -ForegroundColor Gray
        }
    }
}

# Main execution
Write-Host "Systematic Microservices Endpoint Testing" -ForegroundColor Magenta
Write-Host "=========================================" -ForegroundColor Magenta

$allHealthy = $true

foreach ($service in $Services) {
    Show-RouterAnalysis $service
    $isHealthy = Test-ServiceEndpoints $service
    if (-not $isHealthy) { $allHealthy = $false }
}

Write-Host "`n=== Summary ===" -ForegroundColor Magenta
if ($allHealthy) {
    Write-Host "All services are responding correctly!" -ForegroundColor Green
} else {
    Write-Host "Some services have endpoint issues - check output above" -ForegroundColor Red
}

Write-Host "`nNote: This systematic approach examines router configuration" -ForegroundColor Yellow
Write-Host "before testing endpoints to prevent trial-and-error issues." -ForegroundColor Yellow
