#!/usr/bin/env pwsh
"""
Comprehensive Service Endpoint Testing Script
Tests all 7 microservices endpoints directly to verify they work before testing gateway routing
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

function Test-ServiceEndpoint {
    param([string]$ServiceName, [string]$BaseUrl, [string]$Endpoint, [string]$Method = "GET", [hashtable]$Headers = @{}, [string]$Body = $null)
    
    $url = "${BaseUrl}${Endpoint}"
    $testName = "${ServiceName}: ${Method} ${Endpoint}"
    
    try {
        Write-ColoredOutput "Testing: $testName" $Blue
        
        $params = @{
            Uri = $url
            Method = $Method
            Headers = $Headers
            TimeoutSec = 10
        }
        
        if ($Body) {
            $params.Body = $Body
            $params.ContentType = "application/json"
        }
        
        $response = Invoke-WebRequest @params
        $statusCode = $response.StatusCode
        
        if ($statusCode -ge 200 -and $statusCode -lt 300) {
            Write-ColoredOutput "✓ PASS: $testName (Status: $statusCode)" $Green
            return $true
        } else {
            Write-ColoredOutput "✗ FAIL: $testName (Status: $statusCode)" $Red
            return $false
        }
    } catch {
        $errorMessage = $_.Exception.Message
        Write-ColoredOutput "✗ ERROR: $testName - $errorMessage" $Red
        return $false
    }
}

# Test Results Tracking
$totalTests = 0
$passedTests = 0
$failedTests = 0

Write-ColoredOutput "===============================================" $Yellow
Write-ColoredOutput "MICROSERVICES DIRECT ENDPOINT TESTING" $Yellow
Write-ColoredOutput "===============================================" $Yellow

# Test 1: Project Service (Port 8002)
Write-ColoredOutput "`n🔹 Testing Project Service..." $Yellow
$authHeaders = @{ "Authorization" = "Bearer $env:SERVICE_AUTH_TOKEN" }

$projectTests = @(
    @{ Endpoint = "/health"; Method = "GET"; Headers = @{} },
    @{ Endpoint = "/projects"; Method = "GET"; Headers = $authHeaders },
    @{ Endpoint = "/projects/stats"; Method = "GET"; Headers = $authHeaders },
    @{ Endpoint = "/users"; Method = "GET"; Headers = $authHeaders },
    @{ Endpoint = "/llm-configurations"; Method = "GET"; Headers = $authHeaders }
)

foreach ($test in $projectTests) {
    $totalTests++
    if (Test-ServiceEndpoint "Project" $services.project $test.Endpoint $test.Method $test.Headers) {
        $passedTests++
    } else {
        $failedTests++
    }
}

# Test 2: Reporting Service (Port 8001)
Write-ColoredOutput "`n🔹 Testing Reporting Service..." $Yellow

$reportingTests = @(
    @{ Endpoint = "/health"; Method = "GET"; Headers = @{} },
    @{ Endpoint = "/reports/templates"; Method = "GET"; Headers = @{} },
    @{ Endpoint = "/reports/status"; Method = "GET"; Headers = @{} }
)

foreach ($test in $reportingTests) {
    $totalTests++
    if (Test-ServiceEndpoint "Reporting" $services.reporting $test.Endpoint $test.Method $test.Headers) {
        $passedTests++
    } else {
        $failedTests++
    }
}

# Test 3: Document Service (Port 8004)
Write-ColoredOutput "`n🔹 Testing Document Service..." $Yellow

$documentTests = @(
    @{ Endpoint = "/health"; Method = "GET"; Headers = @{} },
    @{ Endpoint = "/api/documents/capabilities"; Method = "GET"; Headers = @{} },
    @{ Endpoint = "/api/documents/stats"; Method = "GET"; Headers = @{} }
)

foreach ($test in $documentTests) {
    $totalTests++
    if (Test-ServiceEndpoint "Document" $services.document $test.Endpoint $test.Method $test.Headers) {
        $passedTests++
    } else {
        $failedTests++
    }
}

# Test 4: Vector Service (Port 8005)
Write-ColoredOutput "`n🔹 Testing Vector Service..." $Yellow

$vectorTests = @(
    @{ Endpoint = "/health"; Method = "GET"; Headers = @{} },
    @{ Endpoint = "/api/vectors/collections"; Method = "GET"; Headers = @{} },
    @{ Endpoint = "/api/vectors/stats"; Method = "GET"; Headers = @{} }
)

foreach ($test in $vectorTests) {
    $totalTests++
    if (Test-ServiceEndpoint "Vector" $services.vector $test.Endpoint $test.Method $test.Headers) {
        $passedTests++
    } else {
        $failedTests++
    }
}

# Test 5: Graph Service (Port 8006) 
Write-ColoredOutput "`n🔹 Testing Graph Service..." $Yellow

$graphTests = @(
    @{ Endpoint = "/health"; Method = "GET"; Headers = @{} },
    @{ Endpoint = "/api/graphs/stats"; Method = "GET"; Headers = @{} },
    @{ Endpoint = "/api/graphs/capabilities"; Method = "GET"; Headers = @{} }
)

foreach ($test in $graphTests) {
    $totalTests++
    if (Test-ServiceEndpoint "Graph" $services.graph $test.Endpoint $test.Method $test.Headers) {
        $passedTests++
    } else {
        $failedTests++
    }
}

# Test 6: LLM Service (Port 8007)
Write-ColoredOutput "`n🔹 Testing LLM Service..." $Yellow

$llmTests = @(
    @{ Endpoint = "/health"; Method = "GET"; Headers = @{} },
    @{ Endpoint = "/api/llm/providers"; Method = "GET"; Headers = @{} },
    @{ Endpoint = "/api/llm/capabilities"; Method = "GET"; Headers = @{} }
)

foreach ($test in $llmTests) {
    $totalTests++
    if (Test-ServiceEndpoint "LLM" $services.llm $test.Endpoint $test.Method $test.Headers) {
        $passedTests++
    } else {
        $failedTests++
    }
}

# Test 7: AI Agent Service (Port 8008)
Write-ColoredOutput "`n🔹 Testing AI Agent Service..." $Yellow

$agentTests = @(
    @{ Endpoint = "/health"; Method = "GET"; Headers = @{} },
    @{ Endpoint = "/api/agents/list"; Method = "GET"; Headers = @{} },
    @{ Endpoint = "/api/crews/list"; Method = "GET"; Headers = @{} }
)

foreach ($test in $agentTests) {
    $totalTests++
    if (Test-ServiceEndpoint "AI Agent" $services.ai_agent $test.Endpoint $test.Method $test.Headers) {
        $passedTests++
    } else {
        $failedTests++
    }
}

# Test 8: WebSocket Service (Port 8009)
Write-ColoredOutput "`n🔹 Testing WebSocket Service..." $Yellow

$websocketTests = @(
    @{ Endpoint = "/health"; Method = "GET"; Headers = @{} },
    @{ Endpoint = "/api/websocket/stats"; Method = "GET"; Headers = @{} }
)

foreach ($test in $websocketTests) {
    $totalTests++
    if (Test-ServiceEndpoint "WebSocket" $services.websocket $test.Endpoint $test.Method $test.Headers) {
        $passedTests++
    } else {
        $failedTests++
    }
}

# Test 9: Storage Service (Port 8010)
Write-ColoredOutput "`n🔹 Testing Storage Service..." $Yellow

$storageTests = @(
    @{ Endpoint = "/health"; Method = "GET"; Headers = @{} },
    @{ Endpoint = "/api/storage/stats"; Method = "GET"; Headers = @{} },
    @{ Endpoint = "/api/storage/capabilities"; Method = "GET"; Headers = @{} }
)

foreach ($test in $storageTests) {
    $totalTests++
    if (Test-ServiceEndpoint "Storage" $services.storage $test.Endpoint $test.Method $test.Headers) {
        $passedTests++
    } else {
        $failedTests++
    }
}

# Test Summary
Write-ColoredOutput "`n===============================================" $Yellow
Write-ColoredOutput "DIRECT ENDPOINT TESTING SUMMARY" $Yellow
Write-ColoredOutput "===============================================" $Yellow
Write-ColoredOutput "Total Tests: $totalTests" $Blue
Write-ColoredOutput "Passed: $passedTests" $Green
Write-ColoredOutput "Failed: $failedTests" $Red

$successRate = [math]::Round(($passedTests / $totalTests) * 100, 2)
Write-ColoredOutput "Success Rate: ${successRate}%" $(if ($successRate -ge 90) { $Green } elseif ($successRate -ge 70) { $Yellow } else { $Red })

if ($failedTests -eq 0) {
    Write-ColoredOutput "`n🎉 All microservices endpoints are working correctly!" $Green
    Write-ColoredOutput "Ready to test API Gateway routing..." $Blue
} else {
    Write-ColoredOutput "`n⚠️  Some endpoints failed. Fix these issues before testing gateway routing." $Yellow
}

Write-ColoredOutput "`n===============================================" $Yellow
