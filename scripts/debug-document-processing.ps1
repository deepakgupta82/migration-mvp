#!/usr/bin/env pwsh
<#
.SYNOPSIS
Debug Document Processing Script for Migration Platform

.DESCRIPTION
This script helps debug and test the document processing pipeline by:
1. Checking service health and connectivity
2. Testing Weaviate connection (both HTTP and gRPC)
3. Uploading and processing a test document
4. Monitoring processing logs and status
5. Generating comprehensive debugging reports

.PARAMETER ProjectId
The project ID to use for testing (optional, will create test project if not provided)

.PARAMETER TestFile
Path to a test document file (optional, will use default test file if not provided)

.PARAMETER SkipWeaviate
Skip Weaviate connectivity tests

.PARAMETER Verbose
Enable verbose logging output

.EXAMPLE
.\debug-document-processing.ps1 -ProjectId "test-project-123" -TestFile "C:\path\to\test.pdf" -Verbose
#>

param(
    [string]$ProjectId = "",
    [string]$TestFile = "",
    [switch]$SkipWeaviate = $false,
    [switch]$Verbose = $false
)

# Configuration
$ErrorActionPreference = "Continue"
$WarningPreference = "Continue"
$VerbosePreference = if ($Verbose) { "Continue" } else { "SilentlyContinue" }

# Service endpoints
$Services = @{
    "backend" = "http://localhost:8000"
    "document-service" = "http://localhost:8003"
    "vector-service" = "http://localhost:8005"
    "storage-service" = "http://localhost:8010"
    "weaviate-http" = "http://localhost:8080"
    "weaviate-grpc" = "localhost:50051"
}

# Colors for output
$Green = "Green"
$Red = "Red"
$Yellow = "Yellow"
$Blue = "Blue"
$Cyan = "Cyan"

function Write-ColorOutput {
    param([string]$Message, [string]$Color = "White")
    Write-Host $Message -ForegroundColor $Color
}

function Write-SectionHeader {
    param([string]$Title)
    Write-Host ""
    Write-ColorOutput "=" * 60 -Color $Cyan
    Write-ColorOutput "  $Title" -Color $Cyan
    Write-ColorOutput "=" * 60 -Color $Cyan
}

function Test-ServiceHealth {
    param([string]$ServiceName, [string]$Url)
    
    Write-ColorOutput "Testing $ServiceName at $Url..." -Color $Blue
    
    try {
        # Test health endpoint
        $healthUrl = if ($ServiceName -eq "weaviate-http") { "$Url/v1/.well-known/ready" } else { "$Url/health" }
        $response = Invoke-RestMethod -Uri $healthUrl -Method GET -TimeoutSec 5
        
        if ($ServiceName -eq "weaviate-http") {
            $status = if ($response) { "healthy" } else { "unhealthy" }
        } else {
            $status = $response.status -or "unknown"
        }
        
        Write-ColorOutput "✓ $ServiceName is $status" -Color $Green
        return $true
    }
    catch {
        Write-ColorOutput "✗ $ServiceName is not responding: $($_.Exception.Message)" -Color $Red
        return $false
    }
}

function Test-WeaviateGrpc {
    param([string]$Host)
    
    Write-ColorOutput "Testing Weaviate gRPC connection at $Host..." -Color $Blue
    
    try {
        # Test if port is open using .NET socket
        $tcpClient = New-Object System.Net.Sockets.TcpClient
        $asyncResult = $tcpClient.BeginConnect($Host.Split(':')[0], [int]$Host.Split(':')[1], $null, $null)
        $success = $asyncResult.AsyncWaitHandle.WaitOne(3000, $false)
        
        if ($success -and $tcpClient.Connected) {
            Write-ColorOutput "✓ Weaviate gRPC port is accessible" -Color $Green
            $tcpClient.Close()
            return $true
        } else {
            Write-ColorOutput "✗ Weaviate gRPC port is not accessible" -Color $Red
            $tcpClient.Close()
            return $false
        }
    }
    catch {
        Write-ColorOutput "✗ Weaviate gRPC connection failed: $($_.Exception.Message)" -Color $Red
        return $false
    }
}

function Test-DocumentUpload {
    param([string]$ProjectId, [string]$FilePath)
    
    Write-ColorOutput "Testing document upload..." -Color $Blue
    
    try {
        # Prepare multipart form data
        $boundary = [System.Guid]::NewGuid().ToString()
        $fileName = Split-Path $FilePath -Leaf
        $fileBytes = [System.IO.File]::ReadAllBytes($FilePath)
        
        # Create form data
        $formData = @"
--$boundary
Content-Disposition: form-data; name="project_id"

$ProjectId
--$boundary
Content-Disposition: form-data; name="file"; filename="$fileName"
Content-Type: application/octet-stream

"@
        
        $formDataBytes = [System.Text.Encoding]::UTF8.GetBytes($formData)
        $endBoundaryBytes = [System.Text.Encoding]::UTF8.GetBytes("`r`n--$boundary--`r`n")
        
        # Combine all parts
        $bodyBytes = $formDataBytes + $fileBytes + $endBoundaryBytes
        
        # Upload file
        $headers = @{
            "Content-Type" = "multipart/form-data; boundary=$boundary"
        }
        
        $response = Invoke-RestMethod -Uri "$($Services['document-service'])/documents/upload" -Method POST -Body $bodyBytes -Headers $headers -TimeoutSec 30
        
        Write-ColorOutput "✓ Document uploaded successfully: $($response.document_id)" -Color $Green
        return $response.document_id
    }
    catch {
        Write-ColorOutput "✗ Document upload failed: $($_.Exception.Message)" -Color $Red
        Write-Verbose "Upload error details: $($_.ErrorDetails.Message)"
        return $null
    }
}

function Get-ProcessingStatus {
    param([string]$DocumentId)
    
    Write-ColorOutput "Checking processing status for document $DocumentId..." -Color $Blue
    
    try {
        $response = Invoke-RestMethod -Uri "$($Services['document-service'])/documents/$DocumentId/status" -Method GET -TimeoutSec 10
        
        $status = $response.status
        $statusColor = switch ($status) {
            "completed" { $Green }
            "processing" { $Yellow }
            "failed" { $Red }
            default { $Blue }
        }
        
        Write-ColorOutput "Status: $status" -Color $statusColor
        
        if ($response.errors -and $response.errors.Count -gt 0) {
            Write-ColorOutput "Errors:" -Color $Red
            $response.errors | ForEach-Object { Write-ColorOutput "  - $_" -Color $Red }
        }
        
        if ($response.warnings -and $response.warnings.Count -gt 0) {
            Write-ColorOutput "Warnings:" -Color $Yellow
            $response.warnings | ForEach-Object { Write-ColorOutput "  - $_" -Color $Yellow }
        }
        
        return $response
    }
    catch {
        Write-ColorOutput "✗ Failed to get processing status: $($_.Exception.Message)" -Color $Red
        return $null
    }
}

function Get-ServiceLogs {
    param([string]$ServiceName)
    
    Write-ColorOutput "Getting recent logs for $ServiceName..." -Color $Blue
    
    try {
        # Try to get logs via task output if running in VS Code
        $taskId = switch ($ServiceName) {
            "document-service" { "document" }
            "vector-service" { "vector" }
            "storage-service" { "storage" }
            default { $ServiceName }
        }
        
        # For now, just provide instructions for manual log checking
        Write-ColorOutput "To check $ServiceName logs:" -Color $Yellow
        Write-ColorOutput "  - Check VS Code terminal for task '$taskId'" -Color $Yellow
        Write-ColorOutput "  - Or run: docker logs migration_platform_${ServiceName}_1" -Color $Yellow
        
        return $true
    }
    catch {
        Write-ColorOutput "✗ Failed to get logs for ${ServiceName}: $($_.Exception.Message)" -Color $Red
        return $false
    }
}

function Create-TestProject {
    Write-ColorOutput "Creating test project..." -Color $Blue
    
    try {
        $projectData = @{
            name = "Document Processing Test - $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
            description = "Automated test project for document processing debugging"
            client_name = "Debug Client"
            client_contact = "debug@test.com"
            cloud_provider = "AWS"
            migration_type = "Infrastructure"
        } | ConvertTo-Json
        
        $response = Invoke-RestMethod -Uri "$($Services['backend'])/projects" -Method POST -Body $projectData -ContentType "application/json" -TimeoutSec 10
        
        $projectId = $response.id
        Write-ColorOutput "✓ Test project created: $projectId" -Color $Green
        return $projectId
    }
    catch {
        Write-ColorOutput "✗ Failed to create test project: $($_.Exception.Message)" -Color $Red
        return $null
    }
}

function Create-TestDocument {
    $testContent = @"
# Test Document for Processing

This is a test document created for debugging the document processing pipeline.

## Section 1: Text Processing
This section contains regular text that should be processed correctly by all extraction methods.

## Section 2: Lists
- Item 1: First test item
- Item 2: Second test item
- Item 3: Third test item

## Section 3: Technical Content
The migration platform supports various cloud providers:
1. Amazon Web Services (AWS)
2. Microsoft Azure
3. Google Cloud Platform (GCP)

## Section 4: Special Characters
Testing special characters: àáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ

## Conclusion
This test document should be processed successfully by the document processing pipeline.
"@
    
    $tempFile = [System.IO.Path]::GetTempFileName()
    $testFile = $tempFile -replace '\.tmp$', '.txt'
    Move-Item $tempFile $testFile
    
    [System.IO.File]::WriteAllText($testFile, $testContent, [System.Text.Encoding]::UTF8)
    
    return $testFile
}

# Main execution
Write-SectionHeader "Document Processing Debug Script"
Write-ColorOutput "Started at: $(Get-Date)" -Color $Blue

# Step 1: Test service health
Write-SectionHeader "Step 1: Service Health Checks"
$healthResults = @{}

foreach ($service in $Services.GetEnumerator()) {
    if ($service.Key -eq "weaviate-grpc") {
        if (-not $SkipWeaviate) {
            $healthResults[$service.Key] = Test-WeaviateGrpc -Host $service.Value
        }
    } else {
        $healthResults[$service.Key] = Test-ServiceHealth -ServiceName $service.Key -Url $service.Value
    }
}

# Step 2: Create test project if needed
Write-SectionHeader "Step 2: Project Setup"
if (-not $ProjectId) {
    $ProjectId = Create-TestProject
    if (-not $ProjectId) {
        Write-ColorOutput "Failed to create test project. Exiting." -Color $Red
        exit 1
    }
} else {
    Write-ColorOutput "Using provided project ID: $ProjectId" -Color $Blue
}

# Step 3: Prepare test file
Write-SectionHeader "Step 3: Test File Setup"
if (-not $TestFile -or -not (Test-Path $TestFile)) {
    if ($TestFile) {
        Write-ColorOutput "Provided test file not found: $TestFile" -Color $Yellow
    }
    Write-ColorOutput "Creating temporary test document..." -Color $Blue
    $TestFile = Create-TestDocument
    Write-ColorOutput "✓ Test document created: $TestFile" -Color $Green
} else {
    Write-ColorOutput "Using provided test file: $TestFile" -Color $Blue
}

# Step 4: Test document upload and processing
Write-SectionHeader "Step 4: Document Upload and Processing"
if ($healthResults["document-service"]) {
    $documentId = Test-DocumentUpload -ProjectId $ProjectId -FilePath $TestFile
    
    if ($documentId) {
        # Wait a moment for processing to start
        Start-Sleep -Seconds 2
        
        # Check processing status
        $maxAttempts = 10
        $attempt = 0
        
        do {
            $attempt++
            Write-ColorOutput "Checking status (attempt $attempt/$maxAttempts)..." -Color $Blue
            $status = Get-ProcessingStatus -DocumentId $documentId
            
            if ($status -and $status.status -eq "completed") {
                Write-ColorOutput "✓ Document processing completed successfully!" -Color $Green
                break
            } elseif ($status -and $status.status -eq "failed") {
                Write-ColorOutput "✗ Document processing failed!" -Color $Red
                break
            } else {
                Write-ColorOutput "Processing still in progress..." -Color $Yellow
                Start-Sleep -Seconds 3
            }
        } while ($attempt -lt $maxAttempts)
        
        if ($attempt -eq $maxAttempts) {
            Write-ColorOutput "⚠ Processing status check timed out" -Color $Yellow
        }
    }
} else {
    Write-ColorOutput "⚠ Skipping document upload - document service is not healthy" -Color $Yellow
}

# Step 5: Get service logs
Write-SectionHeader "Step 5: Service Logs"
$logsToCheck = @("document-service", "vector-service", "storage-service")
foreach ($service in $logsToCheck) {
    Get-ServiceLogs -ServiceName $service
}

# Step 6: Summary
Write-SectionHeader "Step 6: Debug Summary"
Write-ColorOutput "Service Health Summary:" -Color $Blue
foreach ($result in $healthResults.GetEnumerator()) {
    $status = if ($result.Value) { "✓ HEALTHY" } else { "✗ UNHEALTHY" }
    $color = if ($result.Value) { $Green } else { $Red }
    Write-ColorOutput "  $($result.Key): $status" -Color $color
}

Write-ColorOutput "" 
Write-ColorOutput "Next Steps:" -Color $Blue
Write-ColorOutput "1. Ensure all services are healthy before processing documents" -Color $Yellow
Write-ColorOutput "2. Check Weaviate is running: docker-compose up weaviate" -Color $Yellow
Write-ColorOutput "3. Verify gRPC port 50051 is accessible from vector-service" -Color $Yellow
Write-ColorOutput "4. Review service logs for detailed error information" -Color $Yellow

# Cleanup temporary test file if created
if ($TestFile -and $TestFile.Contains([System.IO.Path]::GetTempPath())) {
    Remove-Item $TestFile -ErrorAction SilentlyContinue
    Write-Verbose "Cleaned up temporary test file: $TestFile"
}

Write-ColorOutput ""
Write-ColorOutput "Debug script completed at: $(Get-Date)" -Color $Blue
