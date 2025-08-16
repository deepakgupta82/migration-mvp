#!/usr/bin/env pwsh
"""
Comprehensive API Gateway Testing Script
Tests all gateway endpoints to ensure proper routing to microservices
"""

# Gateway base URL
$gatewayUrl = "http://localhost:8000"

# Colors for output
$Green = "`e[32m"
$Red = "`e[31m"
$Yellow = "`e[33m"
$Blue = "`e[34m"
$Reset = "`e[0m"

function Write-ColoredOutput {
    param([string]$Text, [string]$Color = $Reset)
    Write-Host "${Color}${Text}${Reset}"
}

function Test-GatewayEndpoint {
    param([string]$TestName, [string]$Endpoint, [string]$Method = "GET", [hashtable]$Headers = @{}, [string]$Body = $null, [string]$ExpectedService = "")
    
    $url = "${gatewayUrl}${Endpoint}"
    
    try {
        Write-ColoredOutput "Testing: $TestName" $Blue
        Write-ColoredOutput "  URL: ${Method} ${url}" $Reset
        
        $params = @{
            Uri = $url
            Method = $Method
            Headers = $Headers
            TimeoutSec = 15
        }
        
        if ($Body) {
            $params.Body = $Body
            $params.ContentType = "application/json"
        }
        
        $response = Invoke-WebRequest @params
        $statusCode = $response.StatusCode
        $content = $response.Content | ConvertFrom-Json -ErrorAction SilentlyContinue
        
        if ($statusCode -ge 200 -and $statusCode -lt 300) {
            Write-ColoredOutput "✓ PASS: $TestName (Status: $statusCode)" $Green
            
            # Show response preview
            if ($content) {
                $preview = $content | ConvertTo-Json -Depth 2 -Compress
                if ($preview.Length -gt 100) {
                    $preview = $preview.Substring(0, 100) + "..."
                }
                Write-ColoredOutput "  Response: $preview" $Reset
            }
            
            return @{ Success = $true; StatusCode = $statusCode; Content = $content }
        } else {
            Write-ColoredOutput "✗ FAIL: $TestName (Status: $statusCode)" $Red
            return @{ Success = $false; StatusCode = $statusCode; Content = $content }
        }
    } catch {
        $errorMessage = $_.Exception.Message
        Write-ColoredOutput "✗ ERROR: $TestName - $errorMessage" $Red
        return @{ Success = $false; Error = $errorMessage }
    }
}

# Test Results Tracking
$totalTests = 0
$passedTests = 0
$failedTests = 0
$results = @()

function Record-Test {
    param([hashtable]$result, [string]$testName)
    
    $global:totalTests++
    if ($result.Success) {
        $global:passedTests++
    } else {
        $global:failedTests++
    }
    
    $global:results += @{
        Name = $testName
        Success = $result.Success
        StatusCode = $result.StatusCode
        Error = $result.Error
    }
}

Write-ColoredOutput "===============================================" $Yellow
Write-ColoredOutput "API GATEWAY COMPREHENSIVE TESTING" $Yellow
Write-ColoredOutput "===============================================" $Yellow

# Test 1: Gateway Health and Status
Write-ColoredOutput "`n🔹 Testing Gateway Health and Status..." $Yellow

$result = Test-GatewayEndpoint "Gateway Health Check" "/health"
Record-Test $result "Gateway Health"

$result = Test-GatewayEndpoint "Gateway Status" "/api/gateway/status"  
Record-Test $result "Gateway Status"

$result = Test-GatewayEndpoint "All Services Health" "/api/services/health"
Record-Test $result "All Services Health"

# Test 2: Project Management Endpoints
Write-ColoredOutput "`n🔹 Testing Project Management Routing..." $Yellow

$result = Test-GatewayEndpoint "List Projects" "/api/projects/"
Record-Test $result "List Projects"

$result = Test-GatewayEndpoint "List Projects (no slash)" "/api/projects"
Record-Test $result "List Projects Alt"

$result = Test-GatewayEndpoint "Project Stats" "/api/projects/stats"
Record-Test $result "Project Stats"

# Test project creation
$projectData = @{
    name = "Test Gateway Project"
    description = "Testing API Gateway routing"
} | ConvertTo-Json

$result = Test-GatewayEndpoint "Create Project" "/api/projects/" "POST" @{} $projectData
Record-Test $result "Create Project"

# Test 3: Document Processing Endpoints  
Write-ColoredOutput "`n🔹 Testing Document Processing Routing..." $Yellow

$testProjectId = "test-project-123"

$result = Test-GatewayEndpoint "List Uploaded Files" "/api/projects/${testProjectId}/uploaded-files"
Record-Test $result "List Uploaded Files"

$result = Test-GatewayEndpoint "Process All Documents" "/api/projects/${testProjectId}/process-all" "POST"
Record-Test $result "Process All Documents"

# Test 4: Knowledge Base Query Endpoints
Write-ColoredOutput "`n🔹 Testing Knowledge Base Routing..." $Yellow

$queryData = @{
    query = "test query"
    limit = 5
} | ConvertTo-Json

$result = Test-GatewayEndpoint "Vector Search" "/api/projects/${testProjectId}/query" "POST" @{} $queryData
Record-Test $result "Vector Search"

$result = Test-GatewayEndpoint "Project Graph" "/api/projects/${testProjectId}/graph"
Record-Test $result "Project Graph"

$result = Test-GatewayEndpoint "Clear Project Data" "/api/projects/${testProjectId}/clear-data" "POST"
Record-Test $result "Clear Project Data"

# Test 5: AI Agent Endpoints
Write-ColoredOutput "`n🔹 Testing AI Agent Routing..." $Yellow

$result = Test-GatewayEndpoint "List AI Agents" "/api/agents"
Record-Test $result "List AI Agents"

$result = Test-GatewayEndpoint "List AI Crews" "/api/crews"
Record-Test $result "List AI Crews"

# Test agent task
$agentTaskData = @{
    input_data = @{
        task = "test task"
    }
    parameters = @{}
} | ConvertTo-Json

$result = Test-GatewayEndpoint "Start Agent Task" "/api/agents/test-agent/tasks" "POST" @{} $agentTaskData
Record-Test $result "Start Agent Task"

# Test 6: LLM Configuration Endpoints
Write-ColoredOutput "`n🔹 Testing LLM Configuration Routing..." $Yellow

$result = Test-GatewayEndpoint "Get LLM Providers" "/api/llm/providers"
Record-Test $result "LLM Providers"

$result = Test-GatewayEndpoint "Get LLM Configurations" "/api/llm/configurations"
Record-Test $result "LLM Configurations"

# Test 7: Storage Endpoints
Write-ColoredOutput "`n🔹 Testing Storage Service Routing..." $Yellow

$result = Test-GatewayEndpoint "List Project Files" "/api/storage/projects/${testProjectId}/files/uploads_raw"
Record-Test $result "List Project Files"

$result = Test-GatewayEndpoint "Project Storage Stats" "/api/storage/projects/${testProjectId}/stats"
Record-Test $result "Project Storage Stats"

# Test 8: Individual Service Health Checks
Write-ColoredOutput "`n🔹 Testing Individual Service Health Routing..." $Yellow

$services = @("project", "reporting", "document", "vector", "graph", "llm", "ai_agent", "websocket", "storage")

foreach ($service in $services) {
    $result = Test-GatewayEndpoint "Health Check: $service" "/api/services/${service}/health"
    Record-Test $result "Health: $service"
}

# Test 9: Legacy Endpoints Compatibility  
Write-ColoredOutput "`n🔹 Testing Legacy Endpoints..." $Yellow

$result = Test-GatewayEndpoint "Legacy Upload Endpoint" "/upload/${testProjectId}"
Record-Test $result "Legacy Upload"

# Test Summary
Write-ColoredOutput "`n===============================================" $Yellow
Write-ColoredOutput "API GATEWAY TESTING SUMMARY" $Yellow
Write-ColoredOutput "===============================================" $Yellow

Write-ColoredOutput "Total Tests: $totalTests" $Blue
Write-ColoredOutput "Passed: $passedTests" $Green  
Write-ColoredOutput "Failed: $failedTests" $Red

$successRate = if ($totalTests -gt 0) { [math]::Round(($passedTests / $totalTests) * 100, 2) } else { 0 }
Write-ColoredOutput "Success Rate: ${successRate}%" $(if ($successRate -ge 90) { $Green } elseif ($successRate -ge 70) { $Yellow } else { $Red })

# Show failed tests
if ($failedTests -gt 0) {
    Write-ColoredOutput "`n❌ FAILED TESTS:" $Red
    foreach ($result in $results) {
        if (-not $result.Success) {
            $status = if ($result.StatusCode) { "Status: $($result.StatusCode)" } else { "Error: $($result.Error)" }
            Write-ColoredOutput "  • $($result.Name) - $status" $Red
        }
    }
}

# Show routing analysis
Write-ColoredOutput "`n📊 ROUTING ANALYSIS:" $Blue

$serviceRoutes = @{
    "Project Management" = ($results | Where-Object { $_.Name -match "Project|List Projects" }).Count
    "Document Processing" = ($results | Where-Object { $_.Name -match "Document|Upload|Process" }).Count  
    "Knowledge Base" = ($results | Where-Object { $_.Name -match "Vector|Graph|Query" }).Count
    "AI Agents" = ($results | Where-Object { $_.Name -match "Agent|Crew" }).Count
    "Storage" = ($results | Where-Object { $_.Name -match "Storage|Files" }).Count
    "Health Checks" = ($results | Where-Object { $_.Name -match "Health" }).Count
}

foreach ($route in $serviceRoutes.GetEnumerator()) {
    $routeSuccess = ($results | Where-Object { $_.Name -match $route.Key.Split(' ')[0] -and $_.Success }).Count
    $routeTotal = $route.Value
    $routeRate = if ($routeTotal -gt 0) { [math]::Round(($routeSuccess / $routeTotal) * 100, 2) } else { 0 }
    
    $color = if ($routeRate -ge 90) { $Green } elseif ($routeRate -ge 70) { $Yellow } else { $Red }
    Write-ColoredOutput "  $($route.Key): $routeSuccess/$routeTotal (${routeRate}%)" $color
}

# Final Assessment
Write-ColoredOutput "`n🎯 FINAL ASSESSMENT:" $Yellow

if ($failedTests -eq 0) {
    Write-ColoredOutput "🎉 EXCELLENT! All API Gateway routing is working perfectly!" $Green
    Write-ColoredOutput "✅ All microservices are properly connected through the gateway" $Green
    Write-ColoredOutput "✅ No frontend changes required - all existing endpoints work" $Green
} elseif ($successRate -ge 80) {
    Write-ColoredOutput "⚠️  GOOD! Most routing works, but some issues need fixing" $Yellow  
    Write-ColoredOutput "🔧 Fix the failed endpoints above before production deployment" $Yellow
} else {
    Write-ColoredOutput "❌ CRITICAL! Major routing issues detected" $Red
    Write-ColoredOutput "🚨 Significant fixes required before the gateway can be used" $Red
}

Write-ColoredOutput "`n===============================================" $Yellow
