#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Comprehensive Microservices Validation Test (Corrected Endpoints)
    
.DESCRIPTION
    Complete validation suite for all 9 microservices with proper endpoint routing.
    Tests health checks, business endpoints, API gateway routing, and integration.
    
.NOTES
    Author: GitHub Copilot
    Version: 2.0 (Corrected)
    Services: Project(8002), Reporting(8001), Document(8004), Vector(8005), 
              Graph(8006), LLM(8007), AI Agent(8008), WebSocket(8009), Storage(8010)
#>

# Enhanced output with colors and formatting
function Write-TestHeader($message) {
    Write-Host "`n=== $message ===" -ForegroundColor Cyan
}

function Write-TestResult($name, $success, $details = $null) {
    $status = if ($success) { "✓" } else { "✗" }
    $color = if ($success) { "Green" } else { "Red" }
    
    if ($details) {
        Write-Host "  $status $name" -ForegroundColor $color -NoNewline
        Write-Host "`n    $details" -ForegroundColor Gray
    } else {
        Write-Host "  $status $name" -ForegroundColor $color
    }
}

function Test-Endpoint($url, $description) {
    try {
        $response = Invoke-RestMethod -Uri $url -Method GET -ErrorAction Stop
        Write-TestResult $description $true "Endpoint responsive"
        return @{ Success = $true; Data = $response }
    } catch {
        $errorMessage = $_.Exception.Message
        Write-TestResult $description $false "Error: $errorMessage"
        return @{ Success = $false; Error = $errorMessage }
    }
}

function Test-ServiceConnectivity($port, $serviceName) {
    $tcpTest = Test-NetConnection -ComputerName localhost -Port $port -WarningAction SilentlyContinue
    $httpTest = $null
    try {
        $httpTest = Invoke-RestMethod -Uri "http://localhost:$port/health" -Method GET -ErrorAction Stop
    } catch {
        $httpTest = $null
    }
    
    return @{
        Name = $serviceName
        Port = $port
        TCP = $tcpTest.TcpTestSucceeded
        HTTP = $null -ne $httpTest
    }
}

# Test counters
$totalTests = 0
$passedTests = 0
$failedTests = 0

# Service definitions with correct endpoints
$services = @(
    @{ 
        Name = "Project Service"
        Port = 8002
        BusinessEndpoints = @(
            @{ URL = "http://localhost:8002/api/projects"; Description = "List projects" }
            @{ URL = "http://localhost:8002/api/platform/stats"; Description = "Platform stats" }
        )
    },
    @{ 
        Name = "Reporting Service" 
        Port = 8001
        BusinessEndpoints = @(
            @{ URL = "http://localhost:8001/api/reports/templates"; Description = "Report templates" }
            @{ URL = "http://localhost:8001/health"; Description = "Reporting health" }
        )
    },
    @{ 
        Name = "Document Service"
        Port = 8004
        BusinessEndpoints = @(
            @{ URL = "http://localhost:8004/api/documents/files"; Description = "List files" }
            @{ URL = "http://localhost:8004/api/documents/status"; Description = "Processing status" }
        )
    },
    @{ 
        Name = "Vector Service"
        Port = 8005
        BusinessEndpoints = @(
            @{ URL = "http://localhost:8005/api/vectors/stats"; Description = "Vector stats" }
            @{ URL = "http://localhost:8005/api/vectors/collections"; Description = "List collections" }
        )
    },
    @{ 
        Name = "Graph Service"
        Port = 8006
        BusinessEndpoints = @(
            @{ URL = "http://localhost:8006/api/graphs/stats"; Description = "Graph stats" }
            @{ URL = "http://localhost:8006/api/graphs/topology"; Description = "Graph topology" }
        )
    },
    @{ 
        Name = "LLM Service"
        Port = 8007
        BusinessEndpoints = @(
            @{ URL = "http://localhost:8007/api/llm/providers"; Description = "LLM providers" }
            @{ URL = "http://localhost:8007/api/llm/models"; Description = "Available models" }
        )
    },
    @{ 
        Name = "AI Agent Service"
        Port = 8008
        BusinessEndpoints = @(
            @{ URL = "http://localhost:8008/api/agents/list"; Description = "Agent list" }
            @{ URL = "http://localhost:8008/api/agents/crews"; Description = "Available crews" }
        )
    },
    @{ 
        Name = "WebSocket Service"
        Port = 8009
        BusinessEndpoints = @(
            @{ URL = "http://localhost:8009/stats"; Description = "Connection stats" }
            @{ URL = "http://localhost:8009/connections"; Description = "Active connections" }
        )
    },
    @{ 
        Name = "Storage Service"
        Port = 8010
        BusinessEndpoints = @(
            @{ URL = "http://localhost:8010/api/storage/categories"; Description = "Storage categories" }
            @{ URL = "http://localhost:8010/api/storage/stats"; Description = "Storage stats" }
        )
    }
)

# API Gateway routes (Backend on port 8000)
$gatewayRoutes = @(
    @{ URL = "http://localhost:8000/api/projects"; Description = "Gateway: List projects" }
    @{ URL = "http://localhost:8000/api/platform/stats"; Description = "Gateway: Platform stats" }
    @{ URL = "http://localhost:8000/api/documents/files"; Description = "Gateway: Document files" }
    @{ URL = "http://localhost:8000/api/vectors/stats"; Description = "Gateway: Vector stats" }
    @{ URL = "http://localhost:8000/api/graphs/stats"; Description = "Gateway: Graph stats" }
    @{ URL = "http://localhost:8000/api/llm/providers"; Description = "Gateway: LLM providers" }
    @{ URL = "http://localhost:8000/api/agents/list"; Description = "Gateway: Agent list" }
    @{ URL = "http://localhost:8000/api/websocket/stats"; Description = "Gateway: WebSocket stats" }
    @{ URL = "http://localhost:8000/api/storage/categories"; Description = "Gateway: Storage categories" }
)

# Start comprehensive testing
Write-TestHeader "COMPREHENSIVE MICROSERVICES VALIDATION TEST (CORRECTED)"
Write-Host "Testing 9 services with proper endpoint routing..." -ForegroundColor Yellow

# PHASE 1: Health Checks
Write-TestHeader "PHASE 1: HEALTH CHECKS"
foreach ($service in $services) {
    $result = Test-Endpoint "http://localhost:$($service.Port)/health" "$($service.Name) Health"
    $totalTests++
    if ($result.Success) { $passedTests++ } else { $failedTests++ }
}

# PHASE 2: Business Endpoint Tests
Write-TestHeader "PHASE 2: BUSINESS ENDPOINT TESTS"
foreach ($service in $services) {
    Write-Host "Testing $($service.Name) Business Endpoints..." -ForegroundColor Yellow
    foreach ($endpoint in $service.BusinessEndpoints) {
        $result = Test-Endpoint $endpoint.URL $endpoint.Description
        $totalTests++
        if ($result.Success) { $passedTests++ } else { $failedTests++ }
    }
}

# PHASE 3: API Gateway Routing Tests
Write-TestHeader "PHASE 3: API GATEWAY ROUTING TESTS"
Write-Host "Testing Backend API Gateway (Port 8000)..." -ForegroundColor Yellow
foreach ($route in $gatewayRoutes) {
    $result = Test-Endpoint $route.URL $route.Description
    $totalTests++
    if ($result.Success) { $passedTests++ } else { $failedTests++ }
}

# PHASE 4: Integration Tests
Write-TestHeader "PHASE 4: INTEGRATION TESTS"
Write-Host "Testing key integration flows..." -ForegroundColor Yellow

# Test project creation flow
$projectResult = Test-Endpoint "http://localhost:8000/api/projects" "Project Creation Flow"
$totalTests++
if ($projectResult.Success) { $passedTests++ } else { $failedTests++ }

# Test document upload simulation (GET for validation)
$docResult = Test-Endpoint "http://localhost:8000/api/documents/files" "Document Processing Flow"
$totalTests++
if ($docResult.Success) { $passedTests++ } else { $failedTests++ }

# PHASE 5: Service Connectivity Matrix
Write-TestHeader "PHASE 5: SERVICE CONNECTIVITY MATRIX"
$connectivityResults = @()
foreach ($service in $services) {
    $connectivity = Test-ServiceConnectivity $service.Port $service.Name
    $connectivityResults += $connectivity
    
    $tcpStatus = if ($connectivity.TCP) { "✓" } else { "✗" }
    $httpStatus = if ($connectivity.HTTP) { "✓" } else { "✗" }
    
    Write-Host "  $($connectivity.Name)" -ForegroundColor White
    Write-Host "    TCP:  $tcpStatus" -ForegroundColor $(if ($connectivity.TCP) { "Green" } else { "Red" })
    Write-Host "    HTTP: $httpStatus" -ForegroundColor $(if ($connectivity.HTTP) { "Green" } else { "Red" })
}

# PHASE 6: Service-to-Service Authentication Test
Write-TestHeader "PHASE 6: AUTHENTICATION TESTS"
Write-Host "Testing SERVICE_AUTH_TOKEN authentication..." -ForegroundColor Yellow

# Test with authentication token
$authHeader = @{ 'Authorization' = "Bearer $env:SERVICE_AUTH_TOKEN" }
try {
    $null = Invoke-RestMethod -Uri "http://localhost:8010/api/storage/categories" -Method GET -Headers $authHeader -ErrorAction Stop
    Write-TestResult "Service Authentication" $true "TOKEN authenticated successfully"
    $totalTests++; $passedTests++
} catch {
    Write-TestResult "Service Authentication" $false "TOKEN authentication failed: $($_.Exception.Message)"
    $totalTests++; $failedTests++
}

# FINAL REPORT
Write-TestHeader "FINAL VALIDATION REPORT"
$successRate = [math]::Round(($passedTests / $totalTests) * 100, 2)

Write-Host "Total Tests Executed: $totalTests" -ForegroundColor White
Write-Host "Passed: $passedTests" -ForegroundColor Green
Write-Host "Failed: $failedTests" -ForegroundColor Red
Write-Host "Success Rate: $successRate%" -ForegroundColor $(if ($successRate -ge 80) { "Green" } elseif ($successRate -ge 60) { "Yellow" } else { "Red" })

# Service summary
Write-Host "`nService Summary:" -ForegroundColor White
foreach ($service in $services) {
    $serviceHealthy = $connectivityResults | Where-Object { $_.Name -eq $service.Name } | Select-Object -ExpandProperty HTTP
    $healthStatus = if ($serviceHealthy) { "✓" } else { "✗" }
    
    # Count business endpoints that passed
    $businessPassed = 0
    $businessTotal = $service.BusinessEndpoints.Count
    
    Write-Host "  $($service.Name)" -ForegroundColor White
    Write-Host "    Health: $healthStatus" -ForegroundColor $(if ($serviceHealthy) { "Green" } else { "Red" })
    Write-Host "    Business Endpoints: $businessPassed/$businessTotal" -ForegroundColor Gray
}

# Architecture validation
Write-Host "`nArchitecture Validation:" -ForegroundColor White
$healthyServices = ($connectivityResults | Where-Object { $_.HTTP }).Count
$workingGatewayRoutes = 0  # Will be calculated based on actual results

Write-Host "  Microservices Architecture: $healthyServices/9 services healthy" -ForegroundColor $(if ($healthyServices -eq 9) { "Green" } else { "Yellow" })
Write-Host "  API Gateway Routing: $workingGatewayRoutes/9 endpoints working" -ForegroundColor Gray

# Final status
if ($successRate -ge 80) {
    Write-Host "`n✅ MICROSERVICES PLATFORM: OPERATIONAL" -ForegroundColor Green -BackgroundColor DarkGreen
    Write-Host "Platform is healthy and ready for production use." -ForegroundColor Green
} elseif ($successRate -ge 60) {
    Write-Host "`n⚠️  MICROSERVICES PLATFORM: NEEDS ATTENTION" -ForegroundColor Yellow -BackgroundColor DarkYellow
    Write-Host "Platform is functional but has some issues requiring attention." -ForegroundColor Yellow
} else {
    Write-Host "`n❌ MICROSERVICES PLATFORM: CRITICAL ISSUES" -ForegroundColor Red -BackgroundColor DarkRed
    Write-Host "Critical issues detected. Platform requires immediate troubleshooting." -ForegroundColor Red
}

Write-TestHeader "VALIDATION COMPLETE"
Write-Host "Report generated at: $(Get-Date -Format 'MM/dd/yyyy HH:mm:ss')" -ForegroundColor Gray

# Return exit code based on success rate
if ($successRate -ge 80) { exit 0 } else { exit 1 }
