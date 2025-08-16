#!/usr/bin/env pwsh
# API Gateway Endpoint Testing Script
# Tests all newly added endpoints for frontend-backend integration

Write-Host "=== API Gateway Endpoint Integration Test ===" -ForegroundColor Green
Write-Host "Testing all newly added endpoints for frontend compatibility"
Write-Host ""

# Configuration
$BASE_URL = "http://localhost:8000"
$TEST_PROJECT_ID = "test-project-123"

# Function to test endpoint
function Test-Endpoint {
    param(
        [string]$Method = "GET",
        [string]$Endpoint,
        [string]$Description,
        [hashtable]$Body = $null
    )
    
    Write-Host "Testing: $Description" -ForegroundColor Yellow
    Write-Host "  $Method $Endpoint"
    
    try {
        $params = @{
            Uri = "$BASE_URL$Endpoint"
            Method = $Method
            ContentType = "application/json"
            TimeoutSec = 30
        }
        
        if ($Body) {
            $params.Body = ($Body | ConvertTo-Json -Depth 3)
        }
        
        $response = Invoke-RestMethod @params
        Write-Host "  ✅ SUCCESS - Status: OK" -ForegroundColor Green
        return $true
    }
    catch {
        $statusCode = $_.Exception.Response.StatusCode.value__
        $errorMsg = $_.Exception.Message
        Write-Host "  ❌ FAILED - Status: $statusCode" -ForegroundColor Red
        Write-Host "     Error: $errorMsg" -ForegroundColor Red
        return $false
    }
}

Write-Host "=== Document/Template Management Endpoints ===" -ForegroundColor Cyan

# Test project uploads (legacy endpoint)
Test-Endpoint -Endpoint "/api/projects/$TEST_PROJECT_ID/uploads" -Description "Project Uploads (Legacy)"

# Test project deliverables
Test-Endpoint -Endpoint "/api/projects/$TEST_PROJECT_ID/deliverables" -Description "Get Project Deliverables"
Test-Endpoint -Method "POST" -Endpoint "/api/projects/$TEST_PROJECT_ID/deliverables" -Description "Create Project Deliverable" -Body @{
    name = "Test Deliverable"
    type = "document"
    template = "standard"
}

# Test global templates
Test-Endpoint -Endpoint "/api/templates/global" -Description "Get Global Templates"
Test-Endpoint -Method "POST" -Endpoint "/api/templates/global" -Description "Create Global Template" -Body @{
    name = "Test Template"
    type = "assessment"
    content = "Template content"
}

# Test generation requests
Test-Endpoint -Endpoint "/api/projects/$TEST_PROJECT_ID/generation-requests" -Description "Get Generation Requests"
Test-Endpoint -Method "POST" -Endpoint "/api/projects/$TEST_PROJECT_ID/generation-requests" -Description "Create Generation Request" -Body @{
    template_id = "template-123"
    parameters = @{}
}

# Test template usage and history
Test-Endpoint -Endpoint "/api/projects/$TEST_PROJECT_ID/template-usage" -Description "Get Template Usage Stats"
Test-Endpoint -Endpoint "/api/projects/$TEST_PROJECT_ID/generation-history" -Description "Get Generation History"

Write-Host ""
Write-Host "=== LLM Configuration Endpoints ===" -ForegroundColor Cyan

# Test LLM process configs
Test-Endpoint -Endpoint "/api/projects/$TEST_PROJECT_ID/llm-process-configs" -Description "Get LLM Process Configs"
Test-Endpoint -Method "POST" -Endpoint "/api/projects/$TEST_PROJECT_ID/llm-process-configs" -Description "Update LLM Process Configs" -Body @{
    extraction = @{
        model = "gpt-4"
        temperature = 0.1
    }
}

# Test LLM config testing
Test-Endpoint -Method "POST" -Endpoint "/api/projects/$TEST_PROJECT_ID/process-llm-config/extraction/test" -Description "Test LLM Process Config" -Body @{
    input = "Test input text"
}

# Test Ollama models
Test-Endpoint -Endpoint "/api/ollama/models" -Description "Get Ollama Models"

Write-Host ""
Write-Host "=== Core Project Endpoints ===" -ForegroundColor Cyan

# Test basic project endpoints
Test-Endpoint -Endpoint "/api/projects/" -Description "List Projects"
Test-Endpoint -Endpoint "/api/projects/$TEST_PROJECT_ID" -Description "Get Project Details"

Write-Host ""
Write-Host "=== Service Health Check ===" -ForegroundColor Cyan

# Test service health
Test-Endpoint -Endpoint "/api/health" -Description "Gateway Health Check"

Write-Host ""
Write-Host "=== Test Summary ===" -ForegroundColor Magenta
Write-Host "Frontend-Backend Integration Test Completed"
Write-Host "Review the results above to identify any failing endpoints"
Write-Host ""
Write-Host "Next Steps:"
Write-Host "1. Fix any failing endpoints"
Write-Host "2. Start microservices if they're not running"
Write-Host "3. Verify frontend components use these gateway routes"
Write-Host "4. Run end-to-end user workflow tests"
