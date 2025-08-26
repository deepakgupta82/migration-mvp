# Document Upload and Processing Monitor
# PowerShell script to upload document, trigger processing, and monitor logs

param(
    [Parameter(Mandatory=$true)]
    [string]$DocumentPath = "C:\Users\deepakgupta13\OneDrive - Nagarro\Cloud Practice\migration_platform_2\NBQ Assessment documents\NBQ- Documents Received\D8_NESA Self Assessment Report.pdf",
    
    [Parameter(Mandatory=$true)]
    [string]$ProjectId = "4b0adf70-cd45-466f-bd6e-b8b2d84e5559",
    
    [string]$BaseUrl = "http://localhost:8000",
    [int]$MonitoringDuration = 300  # 5 minutes in seconds
)

# Set error action and encoding
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Global variables
$global:CorrelationId = $null
$global:ProcessingLogs = @()
$global:ServiceResults = @{}

# Service endpoints configuration
$Services = @{
    'backend' = 8000
    'project-service' = 8002
    'reporting-service' = 8001
    'document-service' = 8003
    'vector-service' = 8005
    'graph-service' = 8006
    'llm-service' = 8007
    'ai-agent-service' = 8008
    'websocket-service' = 8009
    'storage-service' = 8010
    'service-registry' = 8011
    'cloud-tools-service' = 8012
}

function Write-Log {
    param(
        [string]$Message,
        [string]$Level = "INFO",
        [string]$Color = "White"
    )
    
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] [$Level] $Message"
    
    Write-Host $logEntry -ForegroundColor $Color
    $global:ProcessingLogs += $logEntry
}

function Test-ServiceHealth {
    Write-Log "🔍 Checking service health..." "INFO" "Cyan"
    
    $healthyServices = @()
    $unhealthyServices = @()
    
    foreach ($service in $Services.GetEnumerator()) {
        try {
            $response = Invoke-RestMethod -Uri "http://localhost:$($service.Value)/health" -Method Get -TimeoutSec 5 -ErrorAction Stop
            $healthyServices += $service.Key
            Write-Log "✅ $($service.Key) (port $($service.Value)): Healthy" "INFO" "Green"
        }
        catch {
            $unhealthyServices += $service.Key
            Write-Log "❌ $($service.Key) (port $($service.Value)): Unavailable" "ERROR" "Red"
        }
    }
    
    Write-Log "📊 Service Health: $($healthyServices.Count) healthy, $($unhealthyServices.Count) unavailable" "INFO" "Yellow"
    
    # Check essential services
    $essentialServices = @('backend', 'document-service', 'vector-service', 'graph-service', 'llm-service')
    $missingEssential = $essentialServices | Where-Object { $_ -in $unhealthyServices }
    
    if ($missingEssential.Count -gt 0) {
        Write-Log "❌ Essential services unavailable: $($missingEssential -join ', ')" "ERROR" "Red"
        return $false
    }
    
    return $true
}

function Test-ProjectExists {
    Write-Log "🔍 Verifying project exists..." "INFO" "Cyan"
    
    try {
        $response = Invoke-RestMethod -Uri "$BaseUrl/api/projects/$ProjectId" -Method Get -ErrorAction Stop
        Write-Log "✅ Project found: $($response.name) (Status: $($response.status))" "INFO" "Green"
        return $true
    }
    catch {
        Write-Log "❌ Project not found or inaccessible: $($_.Exception.Message)" "ERROR" "Red"
        return $false
    }
}

function Test-DocumentExists {
    Write-Log "🔍 Verifying document exists..." "INFO" "Cyan"
    
    if (Test-Path $DocumentPath) {
        $fileSize = (Get-Item $DocumentPath).Length / 1MB
        $fileName = Split-Path $DocumentPath -Leaf
        Write-Log "✅ Document found: $fileName ($([math]::Round($fileSize, 2)) MB)" "INFO" "Green"
        return $true
    }
    else {
        Write-Log "❌ Document not found: $DocumentPath" "ERROR" "Red"
        return $false
    }
}

function Invoke-DocumentUpload {
    Write-Log "📤 Starting document upload..." "INFO" "Cyan"
    
    # Generate correlation ID
    $global:CorrelationId = "doc_upload_$([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds())"
    Write-Log "🔗 Correlation ID: $global:CorrelationId" "INFO" "Yellow"
    
    try {
        # Prepare file for upload
        $fileName = Split-Path $DocumentPath -Leaf
        $fileBytes = [System.IO.File]::ReadAllBytes($DocumentPath)
        $fileContent = [System.Net.Http.ByteArrayContent]::new($fileBytes)
        $fileContent.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse("application/pdf")
        
        # Create multipart form data
        $multipartContent = [System.Net.Http.MultipartFormDataContent]::new()
        $multipartContent.Add($fileContent, "files", $fileName)
        
        # Prepare HTTP client with correlation ID
        $httpClient = [System.Net.Http.HttpClient]::new()
        $httpClient.DefaultRequestHeaders.Add("X-Correlation-ID", $global:CorrelationId)
        $httpClient.Timeout = [TimeSpan]::FromSeconds(60)
        
        # Upload file
        $uploadUrl = "$BaseUrl/api/projects/$ProjectId/files"
        $response = $httpClient.PostAsync($uploadUrl, $multipartContent).Result
        
        if ($response.IsSuccessStatusCode) {
            $responseContent = $response.Content.ReadAsStringAsync().Result
            $uploadResult = $responseContent | ConvertFrom-Json
            Write-Log "✅ Document uploaded successfully!" "INFO" "Green"
            Write-Log "📋 Upload ID: $($uploadResult.id)" "INFO" "White"
            return $true
        }
        else {
            $errorContent = $response.Content.ReadAsStringAsync().Result
            Write-Log "❌ Upload failed: HTTP $($response.StatusCode)" "ERROR" "Red"
            Write-Log "Response: $errorContent" "ERROR" "Red"
            return $false
        }
    }
    catch {
        Write-Log "❌ Upload error: $($_.Exception.Message)" "ERROR" "Red"
        return $false
    }
    finally {
        if ($httpClient) { $httpClient.Dispose() }
        if ($multipartContent) { $multipartContent.Dispose() }
        if ($fileContent) { $fileContent.Dispose() }
    }
}
}

function Invoke-DocumentProcessing {
    Write-Log "⚙️ Triggering document processing..." "INFO" "Cyan"
    
    try {
        $headers = @{
            'X-Correlation-ID' = $global:CorrelationId
            'Content-Type' = 'application/json'
        }
        
        $body = @{
            correlation_id = $global:CorrelationId
        } | ConvertTo-Json
        
        $response = Invoke-RestMethod -Uri "$BaseUrl/api/projects/$ProjectId/assess" -Method Post -Headers $headers -Body $body -TimeoutSec 30
        
        Write-Log "✅ Processing triggered successfully!" "INFO" "Green"
        Write-Log "📋 Response: $($response | ConvertTo-Json -Depth 2)" "INFO" "White"
        return $true
    }
    catch {
        Write-Log "❌ Failed to trigger processing: $($_.Exception.Message)" "ERROR" "Red"
        return $false
    }
}

function Get-ServiceLogs {
    param([string]$ServiceName, [int]$Port)
    
    try {
        $headers = @{ 'X-Correlation-ID' = $global:CorrelationId }
        $params = @{
            correlation_id = $global:CorrelationId
            limit = 50
            since = (Get-Date).AddMinutes(-10).ToString("yyyy-MM-ddTHH:mm:ssZ")
        }
        
        $queryString = ($params.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join "&"
        $response = Invoke-RestMethod -Uri "http://localhost:$Port/api/logs?$queryString" -Headers $headers -TimeoutSec 10
        
        if ($response -and $response.Count -gt 0) {
            return $response
        }
        return @()
    }
    catch {
        Write-Log "⚠️ $ServiceName logs unavailable: $($_.Exception.Message)" "WARN" "Yellow"
        return @()
    }
}

function Get-ProcessingStatus {
    param([string]$ServiceName, [int]$Port, [string]$Endpoint)
    
    try {
        $headers = @{ 'X-Correlation-ID' = $global:CorrelationId }
        $response = Invoke-RestMethod -Uri "http://localhost:$Port$Endpoint" -Headers $headers -TimeoutSec 10
        return $response
    }
    catch {
        return $null
    }
}

function Watch-ProcessingProgress {
    Write-Log "🔄 Starting processing monitoring..." "INFO" "Cyan"
    
    $startTime = Get-Date
    $endTime = $startTime.AddSeconds($MonitoringDuration)
    $lastCheck = Get-Date
    
    while ((Get-Date) -lt $endTime) {
        # Check processing stages
        $stages = @(
            @{ Name = "Document Service"; Port = 8003; Endpoint = "/api/processing/status" }
            @{ Name = "Vector Service"; Port = 8005; Endpoint = "/api/embeddings/status" }
            @{ Name = "Graph Service"; Port = 8006; Endpoint = "/api/graph/status" }
            @{ Name = "LLM Service"; Port = 8007; Endpoint = "/api/llm/status" }
        )
        
        foreach ($stage in $stages) {
            $status = Get-ProcessingStatus -ServiceName $stage.Name -Port $stage.Port -Endpoint $stage.Endpoint
            if ($status) {
                $global:ServiceResults[$stage.Name] = $status
                Write-Log "📊 $($stage.Name): Processing active" "INFO" "Cyan"
            }
        }
        
        # Check project status
        try {
            $project = Invoke-RestMethod -Uri "$BaseUrl/api/projects/$ProjectId" -Method Get
            if ($project.status -eq "completed") {
                Write-Log "✅ Project processing completed!" "INFO" "Green"
                break
            }
            elseif ($project.status -eq "running") {
                Write-Log "🔄 Project status: Processing..." "INFO" "Yellow"
            }
        }
        catch {
            Write-Log "⚠️ Could not check project status" "WARN" "Yellow"
        }
        
        # Collect logs every 30 seconds
        if (((Get-Date) - $lastCheck).TotalSeconds -ge 30) {
            Write-Log "📜 Collecting service logs..." "INFO" "Cyan"
            
            foreach ($service in $Services.GetEnumerator()) {
                $logs = Get-ServiceLogs -ServiceName $service.Key -Port $service.Value
                if ($logs.Count -gt 0) {
                    Write-Log "📋 $($service.Key): $($logs.Count) new log entries" "INFO" "White"
                    $global:ServiceResults["$($service.Key)_logs"] = $logs
                }
            }
            $lastCheck = Get-Date
        }
        
        Start-Sleep -Seconds 10
    }
}
}

function Get-ProcessingResults {
    Write-Log "🔍 Checking processing results..." "INFO" "Cyan"
    
    $results = @{}
    
    $checks = @(
        @{ Name = "Document Chunks"; Url = "$BaseUrl/api/projects/$ProjectId/chunks" }
        @{ Name = "Embeddings Count"; Url = "$BaseUrl/api/projects/$ProjectId/embeddings/count" }
        @{ Name = "Graph Nodes Count"; Url = "$BaseUrl/api/projects/$ProjectId/graph/nodes/count" }
        @{ Name = "Extracted Entities"; Url = "$BaseUrl/api/projects/$ProjectId/entities" }
    )
    
    foreach ($check in $checks) {
        try {
            $response = Invoke-RestMethod -Uri $check.Url -Method Get -TimeoutSec 10
            $results[$check.Name] = $response
            Write-Log "✅ $($check.Name): Retrieved successfully" "INFO" "Green"
        }
        catch {
            $results[$check.Name] = @{ error = $_.Exception.Message }
            Write-Log "⚠️ $($check.Name): $($_.Exception.Message)" "WARN" "Yellow"
        }
    }
    
    return $results
}

function Export-ConsolidatedReport {
    param([hashtable]$ProcessingResults)
    
    Write-Log "💾 Generating consolidated report..." "INFO" "Cyan"
    
    $report = @{
        metadata = @{
            correlation_id = $global:CorrelationId
            project_id = $ProjectId
            document_path = $DocumentPath
            timestamp = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ssZ")
            monitoring_duration = $MonitoringDuration
        }
        processing_logs = $global:ProcessingLogs
        service_results = $global:ServiceResults
        processing_results = $ProcessingResults
        summary = @{
            upload_success = $true
            processing_triggered = $true
            services_monitored = $Services.Keys.Count
            log_entries_collected = ($global:ServiceResults.Keys | Where-Object { $_ -like "*_logs" }).Count
        }
    }
    
    $reportFile = "document_processing_report_$($global:CorrelationId).json"
    $reportPath = Join-Path (Get-Location) $reportFile
    
    try {
        $report | ConvertTo-Json -Depth 10 | Out-File -FilePath $reportPath -Encoding UTF8
        Write-Log "📄 Report saved: $reportPath" "INFO" "Green"
        return $reportPath
    }
    catch {
        Write-Log "❌ Failed to save report: $($_.Exception.Message)" "ERROR" "Red"
        return $null
    }
}

function Show-ConsolidatedResults {
    param([hashtable]$ProcessingResults, [string]$ReportPath)
    
    Write-Host ""
    Write-Host "=" * 80 -ForegroundColor Yellow
    Write-Host "📊 CONSOLIDATED PROCESSING RESULTS" -ForegroundColor Green
    Write-Host "=" * 80 -ForegroundColor Yellow
    
    Write-Host "🔗 Correlation ID: $global:CorrelationId" -ForegroundColor Cyan
    Write-Host "📁 Project ID: $ProjectId" -ForegroundColor Cyan
    Write-Host "📄 Document: $(Split-Path $DocumentPath -Leaf)" -ForegroundColor Cyan
    Write-Host "⏱️ Monitoring Duration: $MonitoringDuration seconds" -ForegroundColor Cyan
    Write-Host ""
    
    Write-Host "🎯 PROCESSING RESULTS:" -ForegroundColor Green
    foreach ($result in $ProcessingResults.GetEnumerator()) {
        if ($result.Value.error) {
            Write-Host "❌ $($result.Key): $($result.Value.error)" -ForegroundColor Red
        }
        else {
            $count = if ($result.Value.count) { $result.Value.count } elseif ($result.Value -is [array]) { $result.Value.Count } else { "✓" }
            Write-Host "✅ $($result.Key): $count" -ForegroundColor Green
        }
    }
    
    Write-Host ""
    Write-Host "🛠️ SERVICE MONITORING:" -ForegroundColor Green
    $serviceLogsCount = ($global:ServiceResults.Keys | Where-Object { $_ -like "*_logs" }).Count
    Write-Host "📋 Services with logs: $serviceLogsCount" -ForegroundColor Cyan
    Write-Host "📈 Total log entries: $($global:ProcessingLogs.Count)" -ForegroundColor Cyan
    
    if ($ReportPath) {
        Write-Host ""
        Write-Host "📄 Full report saved to: $ReportPath" -ForegroundColor Green
    }
    
    Write-Host ""
    Write-Host "=" * 80 -ForegroundColor Yellow
}

# Main execution
function Main {
    try {
        Write-Host "🚀 Document Upload and Processing Monitor" -ForegroundColor Green
        Write-Host "=" * 60 -ForegroundColor Yellow
        
        # Pre-flight checks
        if (-not (Test-ServiceHealth)) { exit 1 }
        if (-not (Test-ProjectExists)) { exit 1 }
        if (-not (Test-DocumentExists)) { exit 1 }
        
        Write-Log "✅ Pre-flight checks passed!" "INFO" "Green"
        Write-Host "=" * 60 -ForegroundColor Yellow
        
        # Upload document
        if (-not (Invoke-DocumentUpload)) { exit 1 }
        
        # Wait for file registration
        Start-Sleep -Seconds 3
        
        # Trigger processing
        if (-not (Invoke-DocumentProcessing)) { exit 1 }
        
        # Monitor processing
        Watch-ProcessingProgress
        
        # Get final results
        $processingResults = Get-ProcessingResults
        
        # Generate report
        $reportPath = Export-ConsolidatedReport -ProcessingResults $processingResults
        
        # Show consolidated results
        Show-ConsolidatedResults -ProcessingResults $processingResults -ReportPath $reportPath
        
        Write-Log "🎉 Document processing monitoring completed successfully!" "INFO" "Green"
    }
    catch {
        Write-Log "💥 Script failed: $($_.Exception.Message)" "ERROR" "Red"
        Write-Log "Stack trace: $($_.ScriptStackTrace)" "ERROR" "Red"
        exit 1
    }
}

# Execute main function
Main