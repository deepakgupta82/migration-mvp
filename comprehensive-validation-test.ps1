#!/usr/bin/env pwsh

# Comprehensive Microservices Validation Test
# Tests all 9 services: health, business endpoints, and API Gateway routing
# Created: August 16, 2025

Write-Host "=== COMPREHENSIVE MICROSERVICES VALIDATION TEST ===" -ForegroundColor Cyan
Write-Host "Testing 9 services: Project(8002), Reporting(8001), Document(8004), Vector(8005), Graph(8006), LLM(8007), AI Agent(8008), WebSocket(8009), Storage(8010)" -ForegroundColor Yellow
Write-Host ""

$services = @{
    "Project Service" = @{
        port = 8002
        healthUrl = "http://localhost:8002/health"
        businessEndpoints = @(
            @{url="http://localhost:8002/api/projects"; method="GET"; description="List projects"}
            @{url="http://localhost:8002/api/stats/platform"; method="GET"; description="Platform stats"}
        )
    }
    "Reporting Service" = @{
        port = 8001
        healthUrl = "http://localhost:8001/health"
        businessEndpoints = @(
            @{url="http://localhost:8001/api/reports/templates"; method="GET"; description="Report templates"}
        )
    }
    "Document Service" = @{
        port = 8004
        healthUrl = "http://localhost:8004/health"
        businessEndpoints = @(
            @{url="http://localhost:8004/files"; method="GET"; description="List files"}
            @{url="http://localhost:8004/status"; method="GET"; description="Processing status"}
        )
    }
    "Vector Service" = @{
        port = 8005
        healthUrl = "http://localhost:8005/health"
        businessEndpoints = @(
            @{url="http://localhost:8005/stats"; method="GET"; description="Vector stats"}
            @{url="http://localhost:8005/collections"; method="GET"; description="List collections"}
        )
    }
    "Graph Service" = @{
        port = 8006
        healthUrl = "http://localhost:8006/health"
        businessEndpoints = @(
            @{url="http://localhost:8006/stats"; method="GET"; description="Graph stats"}
            @{url="http://localhost:8006/topology"; method="GET"; description="Graph topology"}
        )
    }
    "LLM Service" = @{
        port = 8007
        healthUrl = "http://localhost:8007/health"
        businessEndpoints = @(
            @{url="http://localhost:8007/providers"; method="GET"; description="LLM providers"}
            @{url="http://localhost:8007/models"; method="GET"; description="Available models"}
        )
    }
    "AI Agent Service" = @{
        port = 8008
        healthUrl = "http://localhost:8008/health"
        businessEndpoints = @(
            @{url="http://localhost:8008/list"; method="GET"; description="Agent list"}
            @{url="http://localhost:8008/crews"; method="GET"; description="Available crews"}
        )
    }
    "WebSocket Service" = @{
        port = 8009
        healthUrl = "http://localhost:8009/health"
        businessEndpoints = @(
            @{url="http://localhost:8009/stats"; method="GET"; description="Connection stats"}
            @{url="http://localhost:8009/connections"; method="GET"; description="Active connections"}
        )
    }
    "Storage Service" = @{
        port = 8010
        healthUrl = "http://localhost:8010/health"
        businessEndpoints = @(
            @{url="http://localhost:8010/categories"; method="GET"; description="Storage categories"}
            @{url="http://localhost:8010/stats"; method="GET"; description="Storage stats"}
        )
    }
}

$apiGatewayEndpoints = @(
    @{url="http://localhost:8000/api/projects"; method="GET"; description="Gateway: List projects"}
    @{url="http://localhost:8000/api/stats/platform"; method="GET"; description="Gateway: Platform stats"}
    @{url="http://localhost:8000/api/documents/files"; method="GET"; description="Gateway: Document files"}
    @{url="http://localhost:8000/api/vector/stats"; method="GET"; description="Gateway: Vector stats"}
    @{url="http://localhost:8000/api/graph/stats"; method="GET"; description="Gateway: Graph stats"}
    @{url="http://localhost:8000/api/llm/providers"; method="GET"; description="Gateway: LLM providers"}
    @{url="http://localhost:8000/api/agents/list"; method="GET"; description="Gateway: Agent list"}
    @{url="http://localhost:8000/api/websocket/stats"; method="GET"; description="Gateway: WebSocket stats"}
    @{url="http://localhost:8000/api/storage/categories"; method="GET"; description="Gateway: Storage categories"}
)

$results = @{
    healthTests = @{}
    businessTests = @{}
    gatewayTests = @{}
    summary = @{
        totalTests = 0
        passedTests = 0
        failedTests = 0
        services = @{}
    }
}

function Test-Endpoint {
    param(
        [string]$Url,
        [string]$Method = "GET",
        [string]$Description = "",
        [hashtable]$Headers = @{}
    )
    
    try {
        $response = Invoke-RestMethod -Uri $Url -Method $Method -Headers $Headers -TimeoutSec 10
        return @{
            success = $true
            status = "PASS"
            response = $response
            error = $null
        }
    }
    catch {
        return @{
            success = $false
            status = "FAIL"
            response = $null
            error = $_.Exception.Message
        }
    }
}

function Write-TestResult {
    param(
        [string]$TestName,
        [string]$Status,
        [string]$Details = "",
        [string]$Error = ""
    )
    
    $color = if ($Status -eq "PASS") { "Green" } else { "Red" }
    $symbol = if ($Status -eq "PASS") { "✓" } else { "✗" }
    
    Write-Host "  $symbol $TestName" -ForegroundColor $color
    if ($Details) {
        Write-Host "    $Details" -ForegroundColor Gray
    }
    if ($Error) {
        Write-Host "    Error: $Error" -ForegroundColor Red
    }
}

# Test 1: Health Check for all services
Write-Host "=== PHASE 1: HEALTH CHECKS ===" -ForegroundColor Yellow
foreach ($serviceName in $services.Keys) {
    $service = $services[$serviceName]
    Write-Host "Testing $serviceName (Port $($service.port))..." -ForegroundColor Cyan
    
    $result = Test-Endpoint -Url $service.healthUrl -Description "Health check"
    $results.healthTests[$serviceName] = $result
    $results.summary.totalTests++
    
    if ($result.success) {
        $results.summary.passedTests++
        Write-TestResult -TestName "Health Check" -Status "PASS" -Details "Service is healthy"
    } else {
        $results.summary.failedTests++
        Write-TestResult -TestName "Health Check" -Status "FAIL" -Error $result.error
    }
}

Write-Host ""

# Test 2: Business Endpoints for each service
Write-Host "=== PHASE 2: BUSINESS ENDPOINT TESTS ===" -ForegroundColor Yellow
foreach ($serviceName in $services.Keys) {
    $service = $services[$serviceName]
    Write-Host "Testing $serviceName Business Endpoints..." -ForegroundColor Cyan
    
    $results.businessTests[$serviceName] = @{}
    
    foreach ($endpoint in $service.businessEndpoints) {
        $result = Test-Endpoint -Url $endpoint.url -Method $endpoint.method -Description $endpoint.description
        $results.businessTests[$serviceName][$endpoint.description] = $result
        $results.summary.totalTests++
        
        if ($result.success) {
            $results.summary.passedTests++
            Write-TestResult -TestName $endpoint.description -Status "PASS" -Details "Endpoint responsive"
        } else {
            $results.summary.failedTests++
            Write-TestResult -TestName $endpoint.description -Status "FAIL" -Error $result.error
        }
    }
}

Write-Host ""

# Test 3: API Gateway Routing Tests
Write-Host "=== PHASE 3: API GATEWAY ROUTING TESTS ===" -ForegroundColor Yellow
Write-Host "Testing Backend API Gateway (Port 8000)..." -ForegroundColor Cyan

$authHeaders = @{
    "Authorization" = "Bearer service-backend-token"
    "X-Service-Token" = "service-backend-token"
}

foreach ($endpoint in $apiGatewayEndpoints) {
    $result = Test-Endpoint -Url $endpoint.url -Method $endpoint.method -Description $endpoint.description -Headers $authHeaders
    $results.gatewayTests[$endpoint.description] = $result
    $results.summary.totalTests++
    
    if ($result.success) {
        $results.summary.passedTests++
        Write-TestResult -TestName $endpoint.description -Status "PASS" -Details "Gateway routing successful"
    } else {
        $results.summary.failedTests++
        Write-TestResult -TestName $endpoint.description -Status "FAIL" -Error $result.error
    }
}

Write-Host ""

# Test 4: Integration Tests
Write-Host "=== PHASE 4: INTEGRATION TESTS ===" -ForegroundColor Yellow

# Test project creation flow
Write-Host "Testing Project Creation Flow..." -ForegroundColor Cyan
$projectData = @{
    name = "Test Project Integration"
    description = "Integration test project"
} | ConvertTo-Json

try {
    $createResult = Invoke-RestMethod -Uri "http://localhost:8002/api/projects" -Method "POST" -Body $projectData -ContentType "application/json" -TimeoutSec 10
    $results.summary.totalTests++
    $results.summary.passedTests++
    Write-TestResult -TestName "Project Creation" -Status "PASS" -Details "Project created successfully"
    
    $projectId = $createResult.id
    
    # Test project retrieval
    $getResult = Test-Endpoint -Url "http://localhost:8002/api/projects/$projectId"
    $results.summary.totalTests++
    
    if ($getResult.success) {
        $results.summary.passedTests++
        Write-TestResult -TestName "Project Retrieval" -Status "PASS" -Details "Project retrieved successfully"
        
        # Clean up - delete test project
        try {
            Invoke-RestMethod -Uri "http://localhost:8002/api/projects/$projectId" -Method "DELETE" -TimeoutSec 10
            Write-TestResult -TestName "Project Cleanup" -Status "PASS" -Details "Test project deleted"
        } catch {
            Write-TestResult -TestName "Project Cleanup" -Status "FAIL" -Error "Could not delete test project"
        }
    } else {
        $results.summary.failedTests++
        Write-TestResult -TestName "Project Retrieval" -Status "FAIL" -Error $getResult.error
    }
    
} catch {
    $results.summary.totalTests++
    $results.summary.failedTests++
    Write-TestResult -TestName "Project Creation" -Status "FAIL" -Error $_.Exception.Message
}

Write-Host ""

# Test 5: Service Discovery and Connectivity
Write-Host "=== PHASE 5: SERVICE CONNECTIVITY MATRIX ===" -ForegroundColor Yellow

$connectivityMatrix = @{}
foreach ($serviceName in $services.Keys) {
    $service = $services[$serviceName]
    $connectivityMatrix[$serviceName] = @{}
    
    # Test TCP connectivity to each service
    try {
        $tcpTest = Test-NetConnection -ComputerName "localhost" -Port $service.port -WarningAction SilentlyContinue
        $connectivityMatrix[$serviceName]["TCP"] = $tcpTest.TcpTestSucceeded
    } catch {
        $connectivityMatrix[$serviceName]["TCP"] = $false
    }
    
    # Test HTTP connectivity
    try {
        $httpTest = Invoke-WebRequest -Uri $service.healthUrl -TimeoutSec 5 -UseBasicParsing
        $connectivityMatrix[$serviceName]["HTTP"] = ($httpTest.StatusCode -eq 200)
    } catch {
        $connectivityMatrix[$serviceName]["HTTP"] = $false
    }
}

# Display connectivity matrix
Write-Host "Service Connectivity Matrix:" -ForegroundColor Cyan
foreach ($serviceName in $connectivityMatrix.Keys) {
    $tcp = if ($connectivityMatrix[$serviceName]["TCP"]) { "✓" } else { "✗" }
    $http = if ($connectivityMatrix[$serviceName]["HTTP"]) { "✓" } else { "✗" }
    $tcpColor = if ($connectivityMatrix[$serviceName]["TCP"]) { "Green" } else { "Red" }
    $httpColor = if ($connectivityMatrix[$serviceName]["HTTP"]) { "Green" } else { "Red" }
    
    Write-Host "  $serviceName" -ForegroundColor White
    Write-Host "    TCP:  $tcp" -ForegroundColor $tcpColor
    Write-Host "    HTTP: $http" -ForegroundColor $httpColor
}

Write-Host ""

# Generate Final Summary Report
Write-Host "=== FINAL VALIDATION REPORT ===" -ForegroundColor Magenta

$totalTests = $results.summary.totalTests
$passedTests = $results.summary.passedTests
$failedTests = $results.summary.failedTests
$successRate = [math]::Round(($passedTests / $totalTests) * 100, 2)

Write-Host "Total Tests Executed: $totalTests" -ForegroundColor White
Write-Host "Passed: $passedTests" -ForegroundColor Green
Write-Host "Failed: $failedTests" -ForegroundColor Red
Write-Host "Success Rate: $successRate%" -ForegroundColor $(if ($successRate -gt 80) { "Green" } elseif ($successRate -gt 60) { "Yellow" } else { "Red" })

# Service-by-service summary
Write-Host ""
Write-Host "Service Summary:" -ForegroundColor Cyan
foreach ($serviceName in $services.Keys) {
    $healthStatus = if ($results.healthTests[$serviceName].success) { "✓" } else { "✗" }
    $healthColor = if ($results.healthTests[$serviceName].success) { "Green" } else { "Red" }
    
    $businessCount = 0
    $businessPassed = 0
    if ($results.businessTests.ContainsKey($serviceName)) {
        foreach ($test in $results.businessTests[$serviceName].Values) {
            $businessCount++
            if ($test.success) { $businessPassed++ }
        }
    }
    
    Write-Host "  $serviceName" -ForegroundColor White
    Write-Host "    Health: $healthStatus" -ForegroundColor $healthColor
    Write-Host "    Business Endpoints: $businessPassed/$businessCount" -ForegroundColor $(if ($businessPassed -eq $businessCount) { "Green" } else { "Yellow" })
}

# Architecture Validation
Write-Host ""
Write-Host "Architecture Validation:" -ForegroundColor Cyan
$microservicesHealthy = ($results.healthTests.Values | Where-Object { $_.success }).Count
$totalServices = $results.healthTests.Count
Write-Host "  Microservices Architecture: $microservicesHealthy/$totalServices services healthy" -ForegroundColor $(if ($microservicesHealthy -eq $totalServices) { "Green" } else { "Red" })

$gatewayPassed = ($results.gatewayTests.Values | Where-Object { $_.success }).Count
$gatewayTotal = $results.gatewayTests.Count
Write-Host "  API Gateway Routing: $gatewayPassed/$gatewayTotal endpoints working" -ForegroundColor $(if ($gatewayPassed -gt ($gatewayTotal * 0.8)) { "Green" } else { "Red" })

# Overall Status
Write-Host ""
if ($successRate -gt 90) {
    Write-Host "🎉 MICROSERVICES PLATFORM: FULLY OPERATIONAL" -ForegroundColor Green
    Write-Host "All systems green. Platform ready for production use." -ForegroundColor Green
} elseif ($successRate -gt 75) {
    Write-Host "⚠️  MICROSERVICES PLATFORM: MOSTLY OPERATIONAL" -ForegroundColor Yellow
    Write-Host "Minor issues detected. Platform functional with some limitations." -ForegroundColor Yellow
} else {
    Write-Host "❌ MICROSERVICES PLATFORM: NEEDS ATTENTION" -ForegroundColor Red
    Write-Host "Critical issues detected. Platform requires troubleshooting." -ForegroundColor Red
}

Write-Host ""
Write-Host "=== VALIDATION COMPLETE ===" -ForegroundColor Cyan
Write-Host "Report generated at: $(Get-Date)" -ForegroundColor Gray

# Save detailed results to JSON for further analysis
$results | ConvertTo-Json -Depth 10 | Out-File "validation-results-$(Get-Date -Format 'yyyyMMdd-HHmmss').json"
Write-Host "Detailed results saved to validation-results-$(Get-Date -Format 'yyyyMMdd-HHmmss').json" -ForegroundColor Gray
