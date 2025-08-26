# Document Upload and Processing Monitor - Simplified Version
param(
    [string]$DocumentPath = "C:\Users\deepakgupta13\OneDrive - Nagarro\Cloud Practice\migration_platform_2\NBQ Assessment documents\NBQ- Documents Received\D8_NESA Self Assessment Report.pdf",
    [string]$ProjectId = "4b0adf70-cd45-466f-bd6e-b8b2d84e5559",
    [string]$BaseUrl = "http://localhost:8000"
)

# Set encoding
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Global variables
$CorrelationId = $null
$ProcessingLogs = @()

function Write-LogMessage {
    param([string]$Message, [string]$Color = "White")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] $Message" -ForegroundColor $Color
    $script:ProcessingLogs += "[$timestamp] $Message"
}

function Test-Services {
    Write-LogMessage "🔍 Checking essential services..." "Cyan"
    
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
            $response = Invoke-WebRequest -Uri "http://localhost:$($service.Value)/health" -Method Get -TimeoutSec 5 -UseBasicParsing
            Write-LogMessage "✅ $($service.Key): Healthy" "Green"
        }
        catch {
            Write-LogMessage "❌ $($service.Key): Unavailable" "Red"
            $allHealthy = $false
        }
    }
    return $allHealthy
}

function Test-Project {
    Write-LogMessage "🔍 Verifying project..." "Cyan"
    try {
        $response = Invoke-RestMethod -Uri "$BaseUrl/api/projects/$ProjectId" -Method Get
        Write-LogMessage "✅ Project found: $($response.name)" "Green"
        return $true
    }
    catch {
        Write-LogMessage "❌ Project not found" "Red"
        return $false
    }
}

function Test-Document {
    Write-LogMessage "🔍 Verifying document..." "Cyan"
    if (Test-Path $DocumentPath) {
        $fileName = Split-Path $DocumentPath -Leaf
        $fileSize = [math]::Round((Get-Item $DocumentPath).Length / 1MB, 2)
        Write-LogMessage "✅ Document found: $fileName ($fileSize MB)" "Green"
        return $true
    }
    else {
        Write-LogMessage "❌ Document not found: $DocumentPath" "Red"
        return $false
    }
}

function Upload-Document {
    Write-LogMessage "📤 Uploading document..." "Cyan"
    
    # Generate correlation ID
    $script:CorrelationId = "doc_upload_$([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds())"
    Write-LogMessage "🔗 Correlation ID: $CorrelationId" "Yellow"
    
    try {
        # Use curl for simpler file upload
        $fileName = Split-Path $DocumentPath -Leaf
        $curlArgs = @(
            "-X", "POST"
            "-H", "X-Correlation-ID: $CorrelationId"
            "-F", "files=@`"$DocumentPath`""
            "$BaseUrl/api/projects/$ProjectId/files"
        )
        
        $result = & curl @curlArgs 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            Write-LogMessage "✅ Document uploaded successfully!" "Green"
            Write-LogMessage "📋 Response: $result" "White"
            return $true
        }
        else {
            Write-LogMessage "❌ Upload failed: $result" "Red"
            return $false
        }
    }
    catch {
        Write-LogMessage "❌ Upload error: $($_.Exception.Message)" "Red"
        return $false
    }
}

function Trigger-Processing {
    Write-LogMessage "⚙️ Triggering document processing..." "Cyan"
    
    try {
        $headers = @{
            'X-Correlation-ID' = $CorrelationId
            'Content-Type' = 'application/json'
        }
        
        $body = @{ correlation_id = $CorrelationId } | ConvertTo-Json
        $response = Invoke-RestMethod -Uri "$BaseUrl/api/projects/$ProjectId/assess" -Method Post -Headers $headers -Body $body
        
        Write-LogMessage "✅ Processing triggered!" "Green"
        return $true
    }
    catch {
        Write-LogMessage "❌ Failed to trigger processing: $($_.Exception.Message)" "Red"
        return $false
    }
}

function Monitor-Processing {
    Write-LogMessage "🔄 Monitoring processing (5 minutes)..." "Cyan"
    
    $startTime = Get-Date
    $endTime = $startTime.AddMinutes(5)
    
    while ((Get-Date) -lt $endTime) {
        # Check project status
        try {
            $project = Invoke-RestMethod -Uri "$BaseUrl/api/projects/$ProjectId" -Method Get
            Write-LogMessage "📊 Project status: $($project.status)" "Cyan"
            
            if ($project.status -eq "completed") {
                Write-LogMessage "✅ Processing completed!" "Green"
                break
            }
        }
        catch {
            Write-LogMessage "⚠️ Could not check project status" "Yellow"
        }
        
        # Check service logs
        $services = @('backend', 'document-service', 'vector-service', 'graph-service', 'llm-service')
        $ports = @(8000, 8003, 8005, 8006, 8007)
        
        for ($i = 0; $i -lt $services.Count; $i++) {
            try {
                $headers = @{ 'X-Correlation-ID' = $CorrelationId }
                $logs = Invoke-RestMethod -Uri "http://localhost:$($ports[$i])/api/logs?correlation_id=$CorrelationId&limit=5" -Headers $headers -TimeoutSec 5
                
                if ($logs -and $logs.Count -gt 0) {
                    Write-LogMessage "📋 $($services[$i]): $($logs.Count) new log entries" "White"
                    foreach ($log in $logs) {
                        if ($log.message -and $log.message.Contains($CorrelationId)) {
                            Write-LogMessage "  └─ $($log.level): $($log.message)" "Gray"
                        }
                    }
                }
            }
            catch {
                # Service logs not available - continue
            }
        }
        
        Start-Sleep -Seconds 30
    }
}

function Get-Results {
    Write-LogMessage "🔍 Collecting processing results..." "Cyan"
    
    $results = @{}
    
    # Check various endpoints for results
    $endpoints = @{
        'Chunks' = "$BaseUrl/api/projects/$ProjectId/chunks"
        'Embeddings' = "$BaseUrl/api/projects/$ProjectId/embeddings/count"
        'Graph Nodes' = "$BaseUrl/api/projects/$ProjectId/graph/nodes/count"
        'Entities' = "$BaseUrl/api/projects/$ProjectId/entities"
    }
    
    foreach ($endpoint in $endpoints.GetEnumerator()) {
        try {
            $response = Invoke-RestMethod -Uri $endpoint.Value -Method Get -TimeoutSec 10
            $results[$endpoint.Key] = $response
            
            $count = if ($response.count) { $response.count } 
                    elseif ($response -is [array]) { $response.Count } 
                    else { "✓" }
            
            Write-LogMessage "✅ $($endpoint.Key): $count" "Green"
        }
        catch {
            Write-LogMessage "⚠️ $($endpoint.Key): Not available" "Yellow"
            $results[$endpoint.Key] = "Error: $($_.Exception.Message)"
        }
    }
    
    return $results
}

function Save-Report {
    param([hashtable]$Results)
    
    Write-LogMessage "💾 Saving consolidated report..." "Cyan"
    
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
        Write-LogMessage "📄 Report saved: $reportFile" "Green"
        return $reportFile
    }
    catch {
        Write-LogMessage "❌ Failed to save report" "Red"
        return $null
    }
}

function Show-Summary {
    param([hashtable]$Results, [string]$ReportFile)
    
    Write-Host ""
    Write-Host "=" * 80 -ForegroundColor Yellow
    Write-Host "📊 DOCUMENT PROCESSING SUMMARY" -ForegroundColor Green
    Write-Host "=" * 80 -ForegroundColor Yellow
    
    Write-Host "🔗 Correlation ID: $CorrelationId" -ForegroundColor Cyan
    Write-Host "📁 Project ID: $ProjectId" -ForegroundColor Cyan
    Write-Host "📄 Document: $(Split-Path $DocumentPath -Leaf)" -ForegroundColor Cyan
    Write-Host ""
    
    Write-Host "🎯 PROCESSING RESULTS:" -ForegroundColor Green
    foreach ($result in $Results.GetEnumerator()) {
        if ($result.Value -like "Error:*") {
            Write-Host "❌ $($result.Key): $($result.Value)" -ForegroundColor Red
        }
        else {
            Write-Host "✅ $($result.Key): $($result.Value)" -ForegroundColor Green
        }
    }
    
    if ($ReportFile) {
        Write-Host ""
        Write-Host "📄 Full report: $ReportFile" -ForegroundColor Green
    }
    
    Write-Host ""
    Write-Host "=" * 80 -ForegroundColor Yellow
}

# Main execution
try {
    Write-Host "🚀 Document Upload and Processing Monitor" -ForegroundColor Green
    Write-Host "=" * 60 -ForegroundColor Yellow
    
    # Pre-flight checks
    if (-not (Test-Services)) { 
        Write-LogMessage "❌ Essential services unavailable" "Red"
        exit 1 
    }
    
    if (-not (Test-Project)) { 
        Write-LogMessage "❌ Project verification failed" "Red"
        exit 1 
    }
    
    if (-not (Test-Document)) { 
        Write-LogMessage "❌ Document verification failed" "Red"
        exit 1 
    }
    
    Write-LogMessage "✅ Pre-flight checks passed!" "Green"
    
    # Upload and process
    if (-not (Upload-Document)) { 
        Write-LogMessage "❌ Upload failed" "Red"
        exit 1 
    }
    
    Start-Sleep -Seconds 3
    
    if (-not (Trigger-Processing)) { 
        Write-LogMessage "❌ Processing trigger failed" "Red"
        exit 1 
    }
    
    # Monitor and collect results
    Monitor-Processing
    $results = Get-Results
    $reportFile = Save-Report -Results $results
    
    # Show summary
    Show-Summary -Results $results -ReportFile $reportFile
    
    Write-LogMessage "🎉 Monitoring completed successfully!" "Green"
}
catch {
    Write-LogMessage "💥 Script failed: $($_.Exception.Message)" "Red"
    exit 1
}