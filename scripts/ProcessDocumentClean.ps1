# Document Upload and Processing Monitor
param(
    [string]$DocumentPath = "C:\Users\deepakgupta13\OneDrive - Nagarro\Cloud Practice\migration_platform_2\NBQ Assessment documents\NBQ- Documents Received\D8_NESA Self Assessment Report.pdf",
    [string]$ProjectId = "4b0adf70-cd45-466f-bd6e-b8b2d84e5559",
    [string]$BaseUrl = "http://localhost:8000"
)

$CorrelationId = $null
$ProcessingLogs = @()

function Write-LogMessage {
    param([string]$Message, [string]$Color = "White")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] $Message" -ForegroundColor $Color
    $script:ProcessingLogs += "[$timestamp] $Message"
}

function Test-Services {
    Write-LogMessage "Checking essential services..." "Cyan"
    
    $services = @{
        'backend' = 8000
        'document-service' = 8003
        'vector-service' = 8005
        'graph-service' = 8006
        'llm-service' = 8007
    }
    
    $allHealthy = $true
    foreach ($service in $services.GetEnumerator()) {
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:$($service.Value)/health" -Method Get -TimeoutSec 25 -UseBasicParsing
            Write-LogMessage "SUCCESS: $($service.Key) is healthy" "Green"
        }
        catch {
            Write-LogMessage "ERROR: $($service.Key) is unavailable" "Red"
            $allHealthy = $false
        }
    }
    return $allHealthy
}

function Test-Project {
    Write-LogMessage "Verifying project..." "Cyan"
    try {
        $response = Invoke-RestMethod -Uri "$BaseUrl/api/projects/$ProjectId" -Method Get
        Write-LogMessage "SUCCESS: Project found - $($response.name)" "Green"
        return $true
    }
    catch {
        Write-LogMessage "ERROR: Project not found" "Red"
        return $false
    }
}

function Test-Document {
    Write-LogMessage "Verifying document..." "Cyan"
    if (Test-Path $DocumentPath) {
        $fileName = Split-Path $DocumentPath -Leaf
        $fileSize = [math]::Round((Get-Item $DocumentPath).Length / 1MB, 2)
        Write-LogMessage "SUCCESS: Document found - $fileName ($fileSize MB)" "Green"
        return $true
    }
    else {
        Write-LogMessage "ERROR: Document not found - $DocumentPath" "Red"
        return $false
    }
}

function Upload-Document {
    Write-LogMessage "Uploading document..." "Cyan"
    
    # Generate correlation ID
    $script:CorrelationId = "doc_upload_$([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds())"
    Write-LogMessage "Correlation ID: $CorrelationId" "Yellow"
    
    try {
        # Use curl for file upload
        $fileName = Split-Path $DocumentPath -Leaf
        $uploadUrl = "$BaseUrl/api/projects/$ProjectId/files"
        
        $curlCommand = "curl -X POST -H `"X-Correlation-ID: $CorrelationId`" -F `"files=@$DocumentPath`" `"$uploadUrl`""
        Write-LogMessage "Executing: $curlCommand" "Gray"
        
        $result = Invoke-Expression $curlCommand
        
        if ($LASTEXITCODE -eq 0) {
            Write-LogMessage "SUCCESS: Document uploaded successfully!" "Green"
            Write-LogMessage "Response: $result" "White"
            return $true
        }
        else {
            Write-LogMessage "ERROR: Upload failed - Exit code $LASTEXITCODE" "Red"
            Write-LogMessage "Output: $result" "Red"
            return $false
        }
    }
    catch {
        Write-LogMessage "ERROR: Upload exception - $($_.Exception.Message)" "Red"
        return $false
    }
}

function Trigger-Processing {
    Write-LogMessage "Triggering document processing..." "Cyan"
    
    try {
        $headers = @{
            'X-Correlation-ID' = $CorrelationId
            'Content-Type' = 'application/json'
        }
        
        $body = @{ correlation_id = $CorrelationId } | ConvertTo-Json
        $response = Invoke-RestMethod -Uri "$BaseUrl/api/projects/$ProjectId/assess" -Method Post -Headers $headers -Body $body
        
        Write-LogMessage "SUCCESS: Processing triggered!" "Green"
        Write-LogMessage "Response: $($response | ConvertTo-Json)" "White"
        return $true
    }
    catch {
        Write-LogMessage "ERROR: Failed to trigger processing - $($_.Exception.Message)" "Red"
        return $false
    }
}

function Monitor-Processing {
    Write-LogMessage "Monitoring processing for 5 minutes..." "Cyan"
    
    $startTime = Get-Date
    $endTime = $startTime.AddMinutes(5)
    $checkCount = 0
    
    while ((Get-Date) -lt $endTime) {
        $checkCount++
        Write-LogMessage "Check #$checkCount - Monitoring progress..." "Cyan"
        
        # Check project status
        try {
            $project = Invoke-RestMethod -Uri "$BaseUrl/api/projects/$ProjectId" -Method Get
            Write-LogMessage "Project status: $($project.status)" "Cyan"
            
            if ($project.status -eq "completed") {
                Write-LogMessage "SUCCESS: Processing completed!" "Green"
                break
            }
            elseif ($project.status -eq "running") {
                Write-LogMessage "INFO: Processing in progress..." "Yellow"
            }
        }
        catch {
            Write-LogMessage "WARNING: Could not check project status - $($_.Exception.Message)" "Yellow"
        }
        
        # Check service logs
        $services = @(
            @{Name='backend'; Port=8000},
            @{Name='document-service'; Port=8003},
            @{Name='vector-service'; Port=8005},
            @{Name='graph-service'; Port=8006},
            @{Name='llm-service'; Port=8007}
        )
        
        foreach ($service in $services) {
            try {
                $logUrl = "http://localhost:$($service.Port)/api/logs?correlation_id=$CorrelationId&limit=3"
                $headers = @{ 'X-Correlation-ID' = $CorrelationId }
                $logs = Invoke-RestMethod -Uri $logUrl -Headers $headers -TimeoutSec 5
                
                if ($logs -and $logs.Count -gt 0) {
                    Write-LogMessage "LOGS: $($service.Name) - $($logs.Count) entries" "White"
                    foreach ($log in $logs) {
                        if ($log.message -and $log.message.Contains($CorrelationId)) {
                            Write-LogMessage "  -> $($log.level): $($log.message)" "Gray"
                        }
                    }
                }
            }
            catch {
                # Service logs not available - continue silently
            }
        }
        
        Start-Sleep -Seconds 30
    }
    
    Write-LogMessage "Monitoring period completed." "Cyan"
}

function Get-Results {
    Write-LogMessage "Collecting processing results..." "Cyan"
    
    $results = @{}
    
    # Check various endpoints for results
    $endpoints = @{
        'Document Chunks' = "$BaseUrl/api/projects/$ProjectId/chunks"
        'Embeddings Count' = "$BaseUrl/api/projects/$ProjectId/embeddings/count"
        'Graph Nodes Count' = "$BaseUrl/api/projects/$ProjectId/graph/nodes/count"
        'Extracted Entities' = "$BaseUrl/api/projects/$ProjectId/entities"
    }
    
    foreach ($endpoint in $endpoints.GetEnumerator()) {
        try {
            $response = Invoke-RestMethod -Uri $endpoint.Value -Method Get -TimeoutSec 10
            $results[$endpoint.Key] = $response
            
            $count = if ($response.count) { 
                $response.count 
            } elseif ($response -is [array]) { 
                $response.Count 
            } else { 
                "Available" 
            }
            
            Write-LogMessage "SUCCESS: $($endpoint.Key) - $count" "Green"
        }
        catch {
            Write-LogMessage "WARNING: $($endpoint.Key) - Not available ($($_.Exception.Message))" "Yellow"
            $results[$endpoint.Key] = "Error: $($_.Exception.Message)"
        }
    }
    
    return $results
}

function Save-Report {
    param([hashtable]$Results)
    
    Write-LogMessage "Saving consolidated report..." "Cyan"
    
    $report = @{
        metadata = @{
            correlation_id = $CorrelationId
            project_id = $ProjectId
            document_path = $DocumentPath
            timestamp = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ssZ")
        }
        processing_logs = $ProcessingLogs
        results = $Results
    }
    
    $reportFile = "processing_report_$CorrelationId.json"
    
    try {
        $report | ConvertTo-Json -Depth 5 | Out-File -FilePath $reportFile -Encoding UTF8
        Write-LogMessage "SUCCESS: Report saved - $reportFile" "Green"
        return $reportFile
    }
    catch {
        Write-LogMessage "ERROR: Failed to save report - $($_.Exception.Message)" "Red"
        return $null
    }
}

function Show-Summary {
    param([hashtable]$Results, [string]$ReportFile)
    
    Write-Host ""
    Write-Host "=" * 80 -ForegroundColor Yellow
    Write-Host "DOCUMENT PROCESSING SUMMARY" -ForegroundColor Green
    Write-Host "=" * 80 -ForegroundColor Yellow
    
    Write-Host "Correlation ID: $CorrelationId" -ForegroundColor Cyan
    Write-Host "Project ID: $ProjectId" -ForegroundColor Cyan
    Write-Host "Document: $(Split-Path $DocumentPath -Leaf)" -ForegroundColor Cyan
    Write-Host ""
    
    Write-Host "PROCESSING RESULTS:" -ForegroundColor Green
    foreach ($result in $Results.GetEnumerator()) {
        if ($result.Value -like "Error:*") {
            Write-Host "ERROR: $($result.Key) - $($result.Value)" -ForegroundColor Red
        }
        else {
            Write-Host "SUCCESS: $($result.Key) - $($result.Value)" -ForegroundColor Green
        }
    }
    
    if ($ReportFile) {
        Write-Host ""
        Write-Host "Full report saved to: $ReportFile" -ForegroundColor Green
    }
    
    Write-Host ""
    Write-Host "=" * 80 -ForegroundColor Yellow
}

# Main execution
try {
    Write-Host "Document Upload and Processing Monitor" -ForegroundColor Green
    Write-Host "=" * 60 -ForegroundColor Yellow
    
    # Pre-flight checks
    Write-LogMessage "Starting pre-flight checks..." "Cyan"
    
    if (-not (Test-Services)) { 
        Write-LogMessage "FATAL: Essential services unavailable" "Red"
        exit 1 
    }
    
    if (-not (Test-Project)) { 
        Write-LogMessage "FATAL: Project verification failed" "Red"
        exit 1 
    }
    
    if (-not (Test-Document)) { 
        Write-LogMessage "FATAL: Document verification failed" "Red"
        exit 1 
    }
    
    Write-LogMessage "SUCCESS: All pre-flight checks passed!" "Green"
    Write-Host "=" * 60 -ForegroundColor Yellow
    
    # Upload and process
    if (-not (Upload-Document)) { 
        Write-LogMessage "FATAL: Document upload failed" "Red"
        exit 1 
    }
    
    Write-LogMessage "Waiting 3 seconds for file registration..." "Cyan"
    Start-Sleep -Seconds 3
    
    if (-not (Trigger-Processing)) { 
        Write-LogMessage "FATAL: Processing trigger failed" "Red"
        exit 1 
    }
    
    # Monitor and collect results
    Monitor-Processing
    $results = Get-Results
    $reportFile = Save-Report -Results $results
    
    # Show summary
    Show-Summary -Results $results -ReportFile $reportFile
    
    Write-LogMessage "SUCCESS: Monitoring completed successfully!" "Green"
}
catch {
    Write-LogMessage "FATAL: Script failed - $($_.Exception.Message)" "Red"
    Write-LogMessage "Stack trace: $($_.ScriptStackTrace)" "Red"
    exit 1
}