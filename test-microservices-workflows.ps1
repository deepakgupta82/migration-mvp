# Comprehensive Microservices Workflow Testing Script
# Tests all user workflows through the API Gateway to identify routing issues

param(
    [string]$GatewayUrl = "http://localhost:8000",
    [string]$TestProjectName = "Workflow_Test_$(Get-Date -Format 'yyyyMMdd_HHmmss')",
    [switch]$Verbose,
    [switch]$StopOnFirstError,
    [switch]$CleanupAfter
)

# Global test results
$script:TestResults = @()
$script:TestCount = 0
$script:PassCount = 0
$script:FailCount = 0
$script:TestProjectId = $null
$script:CreatedLLMConfigId = $null

function Write-ColoredOutput {
    param([string]$Message, [string]$Color = "White")
    Write-Host $Message -ForegroundColor $Color
}

function Test-GatewayEndpoint {
    param(
        [string]$TestName,
        [string]$Endpoint,
        [string]$Method = "GET",
        [hashtable]$Headers = @{},
        [object]$Body = $null,
        [string]$ContentType = "application/json",
        [int]$ExpectedStatus = 200,
        [int]$TimeoutSeconds = 30
    )
    
    $script:TestCount++
    $fullUrl = "$GatewayUrl$Endpoint"
    
    # Default headers (simulate frontend)
    $defaultHeaders = @{
        "Authorization" = "Bearer service-backend-token"
        "User-Agent" = "Microservices-Workflow-Test/1.0"
    }
    
    # Merge headers
    foreach ($key in $Headers.Keys) {
        $defaultHeaders[$key] = $Headers[$key]
    }
    
    if ($Body -and $ContentType -eq "application/json") {
        $defaultHeaders["Content-Type"] = "application/json"
    }
    
    $startTime = Get-Date
    
    try {
        Write-ColoredOutput "🔹 Testing: $TestName" "Cyan"
        Write-ColoredOutput "   $Method $fullUrl" "White"
        
        $requestParams = @{
            Uri = $fullUrl
            Method = $Method
            Headers = $defaultHeaders
            TimeoutSec = $TimeoutSeconds
            UseBasicParsing = $true
        }
        
        if ($Body) {
            if ($ContentType -eq "application/json") {
                $requestParams.Body = ($Body | ConvertTo-Json -Depth 10)
            } else {
                $requestParams.Body = $Body
            }
        }
        
        $response = Invoke-WebRequest @requestParams
        $endTime = Get-Date
        $duration = ($endTime - $startTime).TotalMilliseconds
        
        $success = $response.StatusCode -eq $ExpectedStatus
        
        if ($success) {
            Write-ColoredOutput "   ✅ PASS ($($response.StatusCode)) - ${duration}ms" "Green"
            $script:PassCount++
        } else {
            Write-ColoredOutput "   ❌ FAIL - Expected $ExpectedStatus, got $($response.StatusCode) - ${duration}ms" "Red"
            $script:FailCount++
        }
        
        $result = @{
            TestName = $TestName
            Method = $Method
            Endpoint = $Endpoint
            Status = $response.StatusCode
            Success = $success
            Duration = $duration
            Response = $response.Content
            Error = $null
        }
        
        if ($Verbose -and $response.Content) {
            $content = $response.Content
            if ($content.Length -gt 500) {
                $content = $content.Substring(0, 500) + "..."
            }
            Write-ColoredOutput "   Response: $content" "Gray"
        }
        
        return $result
        
    } catch {
        $endTime = Get-Date
        $duration = ($endTime - $startTime).TotalMilliseconds
        
        Write-ColoredOutput "   ❌ ERROR - $($_.Exception.Message) - ${duration}ms" "Red"
        $script:FailCount++
        
        $result = @{
            TestName = $TestName
            Method = $Method
            Endpoint = $Endpoint
            Status = if ($_.Exception.Response) { $_.Exception.Response.StatusCode } else { "ERROR" }
            Success = $false
            Duration = $duration
            Response = $null
            Error = $_.Exception.Message
        }
        
        if ($StopOnFirstError) {
            Write-ColoredOutput "🛑 Stopping on first error as requested" "Red"
            exit 1
        }
        
        return $result
    } finally {
        $script:TestResults += $result
    }
}

function Test-FileUpload {
    param(
        [string]$TestName,
        [string]$ProjectId,
        [string]$FileName = "test-document.txt"
    )
    
    $script:TestCount++
    $endpoint = "/api/projects/$ProjectId/upload"
    $fullUrl = "$GatewayUrl$endpoint"
    
    Write-ColoredOutput "🔹 Testing: $TestName" "Cyan"
    Write-ColoredOutput "   POST $fullUrl" "White"
    
    $startTime = Get-Date
    
    try {
        # Create test file content
        $testContent = @"
This is a test document for API Gateway upload testing.
Created: $(Get-Date)
Project ID: $ProjectId
Test Name: $TestName

This document contains sample content to test the document processing pipeline.
It should be uploaded to the storage service and then processed into markdown format.
"@
        
        # Prepare multipart form data
        $boundary = [System.Guid]::NewGuid().ToString()
        $fileBytes = [System.Text.Encoding]::UTF8.GetBytes($testContent)
        
        $bodyLines = @()
        $bodyLines += "--$boundary"
        $bodyLines += "Content-Disposition: form-data; name=`"files`"; filename=`"$FileName`""
        $bodyLines += "Content-Type: text/plain"
        $bodyLines += ""
        
        $bodyText = ($bodyLines -join "`r`n") + "`r`n"
        $bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($bodyText)
        
        $footerText = "`r`n--$boundary--`r`n"
        $footerBytes = [System.Text.Encoding]::UTF8.GetBytes($footerText)
        
        # Combine all parts
        $totalBytes = New-Object byte[] ($bodyBytes.Length + $fileBytes.Length + $footerBytes.Length)
        [Array]::Copy($bodyBytes, 0, $totalBytes, 0, $bodyBytes.Length)
        [Array]::Copy($fileBytes, 0, $totalBytes, $bodyBytes.Length, $fileBytes.Length)
        [Array]::Copy($footerBytes, 0, $totalBytes, $bodyBytes.Length + $fileBytes.Length, $footerBytes.Length)
        
        $headers = @{
            "Authorization" = "Bearer service-backend-token"
            "Content-Type" = "multipart/form-data; boundary=$boundary"
        }
        
        $response = Invoke-WebRequest -Uri $fullUrl -Method POST -Headers $headers -Body $totalBytes -TimeoutSec 30 -UseBasicParsing
        
        $endTime = Get-Date
        $duration = ($endTime - $startTime).TotalMilliseconds
        
        $success = $response.StatusCode -eq 200
        
        if ($success) {
            Write-ColoredOutput "   ✅ PASS (200) - ${duration}ms" "Green"
            $script:PassCount++
        } else {
            Write-ColoredOutput "   ❌ FAIL - Expected 200, got $($response.StatusCode) - ${duration}ms" "Red"
            $script:FailCount++
        }
        
        $result = @{
            TestName = $TestName
            Method = "POST"
            Endpoint = $endpoint
            Status = $response.StatusCode
            Success = $success
            Duration = $duration
            Response = $response.Content
            Error = $null
        }
        
        return $result
        
    } catch {
        $endTime = Get-Date
        $duration = ($endTime - $startTime).TotalMilliseconds
        
        Write-ColoredOutput "   ❌ ERROR - $($_.Exception.Message) - ${duration}ms" "Red"
        $script:FailCount++
        
        $result = @{
            TestName = $TestName
            Method = "POST"
            Endpoint = $endpoint
            Status = if ($_.Exception.Response) { $_.Exception.Response.StatusCode } else { "ERROR" }
            Success = $false
            Duration = $duration
            Response = $null
            Error = $_.Exception.Message
        }
        
        return $result
    } finally {
        $script:TestResults += $result
    }
}

function Start-WorkflowTests {
    Write-ColoredOutput "`n🚀 Starting Comprehensive Microservices Workflow Testing" "Cyan"
    Write-ColoredOutput "Gateway URL: $GatewayUrl" "White"
    Write-ColoredOutput "Test Project: $TestProjectName" "White"
    Write-ColoredOutput "=" * 80 "White"
    
    # Test 1: System Health Check
    Write-ColoredOutput "`n📋 Phase 1: System Health Check" "Yellow"
    
    $healthResult = Test-GatewayEndpoint "System Health Check" "/health"
    
    if (-not $healthResult.Success) {
        Write-ColoredOutput "❌ Gateway is not responding. Please ensure backend is running on port 8000." "Red"
        return
    }
    
    # Parse health response to check service status
    try {
        $healthData = $healthResult.Response | ConvertFrom-Json
        Write-ColoredOutput "   Services Status:" "White"
        foreach ($service in $healthData.services.PSObject.Properties) {
            $status = $service.Value
            $color = if ($status -eq "connected") { "Green" } else { "Red" }
            Write-ColoredOutput "   - $($service.Name): $status" $color
        }
    } catch {
        Write-ColoredOutput "   ⚠️ Could not parse health response" "Yellow"
    }
    
    # Test 2: Project Lifecycle Management
    Write-ColoredOutput "`n📋 Phase 2: Project Lifecycle Management" "Yellow"
    
    # Create Project
    $projectData = @{
        name = $TestProjectName
        description = "Comprehensive microservices workflow test project"
        client_name = "Workflow Test Client"
        client_contact = "workflow-test@example.com"
    }
    
    $createResult = Test-GatewayEndpoint "Create Project" "/api/projects" "POST" @{} $projectData
    
    if ($createResult.Success) {
        try {
            $projectResponse = $createResult.Response | ConvertFrom-Json
            $script:TestProjectId = $projectResponse.id
            Write-ColoredOutput "   📝 Created test project: $($script:TestProjectId)" "Green"
        } catch {
            Write-ColoredOutput "   ⚠️ Could not parse project creation response" "Yellow"
            $script:TestProjectId = "fallback-project-id"
        }
    } else {
        Write-ColoredOutput "   ❌ Failed to create test project. Using fallback ID." "Red"
        $script:TestProjectId = "fallback-project-id"
    }
    
    # Get Project
    if ($script:TestProjectId) {
        Test-GatewayEndpoint "Get Project Details" "/api/projects/$($script:TestProjectId)"
    }
    
    # List Projects
    Test-GatewayEndpoint "List All Projects" "/api/projects"

    # Test 3: LLM Configuration Management
    Write-ColoredOutput "`n📋 Phase 3: LLM Configuration Management" "Yellow"

    # List LLM Configurations
    Test-GatewayEndpoint "List LLM Configurations" "/api/llm/configurations"

    # Create LLM Configuration
    $llmConfigData = @{
        name = "Test_LLM_Config_$(Get-Date -Format 'HHmmss')"
        provider = "gemini"
        model = "gemini-2.5-pro"
        api_key = "test-api-key-placeholder"
        temperature = "0.1"
        max_tokens = "4000"
        description = "Test LLM configuration for workflow testing"
    }

    $llmCreateResult = Test-GatewayEndpoint "Create LLM Configuration" "/api/llm/configurations" "POST" @{} $llmConfigData

    if ($llmCreateResult.Success) {
        try {
            $llmResponse = $llmCreateResult.Response | ConvertFrom-Json
            $script:CreatedLLMConfigId = $llmResponse.id
            Write-ColoredOutput "   📝 Created LLM config: $($script:CreatedLLMConfigId)" "Green"
        } catch {
            Write-ColoredOutput "   ⚠️ Could not parse LLM config creation response" "Yellow"
        }
    }

    # Test LLM Configuration (if we have a config ID)
    if ($script:CreatedLLMConfigId) {
        Test-GatewayEndpoint "Test LLM Configuration" "/api/llm/test-llm-config?config_id=$($script:CreatedLLMConfigId)"
    } else {
        Test-GatewayEndpoint "Test LLM Configuration (no config)" "/api/llm/test-llm-config"
    }

    # List Provider Models
    Test-GatewayEndpoint "List Gemini Models" "/api/llm/models/gemini"
    Test-GatewayEndpoint "List OpenAI Models" "/api/llm/models/openai"

    # Update Project with LLM Configuration
    if ($script:TestProjectId -and $script:CreatedLLMConfigId) {
        $updateData = @{
            llm_provider = "gemini"
            llm_model = "gemini-2.5-pro"
            llm_api_key_id = $script:CreatedLLMConfigId
            llm_temperature = "0.1"
            llm_max_tokens = "4000"
        }
        Test-GatewayEndpoint "Update Project with LLM Config" "/api/projects/$($script:TestProjectId)" "PUT" @{} $updateData
    }

    # Test 4: Document Processing Pipeline
    Write-ColoredOutput "`n📋 Phase 4: Document Processing Pipeline" "Yellow"

    if ($script:TestProjectId) {
        # Upload Documents
        Test-FileUpload "Upload Test Document 1" $script:TestProjectId "workflow-test-1.txt"
        Test-FileUpload "Upload Test Document 2" $script:TestProjectId "workflow-test-2.txt"

        # List Uploaded Files
        Test-GatewayEndpoint "List Uploaded Files" "/api/projects/$($script:TestProjectId)/uploaded-files"

        # Process All Documents
        Test-GatewayEndpoint "Process All Documents" "/api/projects/$($script:TestProjectId)/process-all" "POST"

        # Wait a moment for processing
        Write-ColoredOutput "   ⏳ Waiting 3 seconds for document processing..." "Yellow"
        Start-Sleep -Seconds 3

        # Check processed files
        Test-GatewayEndpoint "List Files After Processing" "/api/projects/$($script:TestProjectId)/uploaded-files"
    }

    # Test 5: Knowledge Base Operations
    Write-ColoredOutput "`n📋 Phase 5: Knowledge Base Operations" "Yellow"

    if ($script:TestProjectId) {
        # Query Knowledge Base
        $queryData = @{
            query = "What is this document about?"
            limit = 5
        }
        Test-GatewayEndpoint "Query Knowledge Base" "/api/projects/$($script:TestProjectId)/query" "POST" @{} $queryData

        # Get Knowledge Graph
        Test-GatewayEndpoint "Get Knowledge Graph" "/api/projects/$($script:TestProjectId)/graph"

        # Clear Project Data
        Test-GatewayEndpoint "Clear Project Data" "/api/projects/$($script:TestProjectId)/clear-data" "POST"
    }

    # Test 6: Crew/Agent System
    Write-ColoredOutput "`n📋 Phase 6: Crew/Agent System" "Yellow"

    # Get Crew Configuration
    Test-GatewayEndpoint "Get Crew Configuration" "/api/crew-config"

    # Reload Crew Configuration
    Test-GatewayEndpoint "Reload Crew Configuration" "/api/crew-config/reload" "POST"

    if ($script:TestProjectId) {
        # Get LLM Process Configs
        Test-GatewayEndpoint "Get LLM Process Configs" "/api/projects/$($script:TestProjectId)/llm-process-configs"

        # Update LLM Process Configs
        $processConfigData = @{
            extraction = @{
                model = "gemini-2.5-pro"
                temperature = 0.1
                max_tokens = 4000
            }
            analysis = @{
                model = "gemini-2.5-pro"
                temperature = 0.2
                max_tokens = 4000
            }
        }
        Test-GatewayEndpoint "Update LLM Process Configs" "/api/projects/$($script:TestProjectId)/llm-process-configs" "POST" @{} $processConfigData
    }

    # Test 7: System Monitoring
    Write-ColoredOutput "`n📋 Phase 7: System Monitoring" "Yellow"

    # List Log Services
    Test-GatewayEndpoint "List Log Services" "/api/logs"

    # Tail Backend Logs
    Test-GatewayEndpoint "Tail Backend Logs" "/api/logs?service=backend&tail=5"

    # Test 8: Cleanup (if requested)
    if ($CleanupAfter -and $script:TestProjectId -and $script:TestProjectId -ne "fallback-project-id") {
        Write-ColoredOutput "`n📋 Phase 8: Cleanup" "Yellow"
        Test-GatewayEndpoint "Delete Test Project" "/api/projects/$($script:TestProjectId)" "DELETE"
    }

    # Generate Final Report
    Write-ColoredOutput "`n📊 Test Results Summary" "Cyan"
    Write-ColoredOutput "=" * 80 "White"
    Write-ColoredOutput "Total Tests: $script:TestCount" "White"
    Write-ColoredOutput "Passed: $script:PassCount" "Green"
    Write-ColoredOutput "Failed: $script:FailCount" "Red"

    $successRate = if ($script:TestCount -gt 0) { [math]::Round(($script:PassCount / $script:TestCount) * 100, 2) } else { 0 }
    Write-ColoredOutput "Success Rate: $successRate%" $(if ($successRate -ge 80) { "Green" } elseif ($successRate -ge 60) { "Yellow" } else { "Red" })

    # Show failed tests
    if ($script:FailCount -gt 0) {
        Write-ColoredOutput "`n❌ Failed Tests:" "Red"
        foreach ($result in $script:TestResults) {
            if (-not $result.Success) {
                Write-ColoredOutput "   - $($result.TestName): $($result.Method) $($result.Endpoint)" "Red"
                if ($result.Error) {
                    Write-ColoredOutput "     Error: $($result.Error)" "Red"
                } else {
                    Write-ColoredOutput "     Status: $($result.Status)" "Red"
                }
            }
        }
    }

    # Export detailed results
    $resultsFile = "test-results-$(Get-Date -Format 'yyyyMMdd-HHmmss').json"
    $script:TestResults | ConvertTo-Json -Depth 10 | Out-File -FilePath $resultsFile -Encoding UTF8
    Write-ColoredOutput "`n📄 Detailed results exported to: $resultsFile" "Cyan"

    Write-ColoredOutput "`n🏁 Testing Complete!" "Cyan"
}

# Run the tests
Start-WorkflowTests
