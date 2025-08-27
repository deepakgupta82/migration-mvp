# Document Processing and Log Export Script
# Automates the complete document processing workflow and exports logs for analysis

param(
    [Parameter(Mandatory=$false)]
    [string]$ProjectId = "",
    
    [Parameter(Mandatory=$false)]
    [string]$DocumentPath = "",
    
    [string]$BaseUrl = "http://localhost:8000"
)

# Set encoding for proper Unicode support
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Global variables
$CorrelationId = $null
$ProcessingLogs = @()
$StartTime = Get-Date
$TestMode = $false

function Write-LogMessage {
    param([string]$Message, [string]$Color = "White")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] $Message" -ForegroundColor $Color
    $script:ProcessingLogs += "[$timestamp] $Message"
}

function Show-Header {
    param([string]$Title)
    Write-Host "`n" + "=" * 60 -ForegroundColor Cyan
    Write-Host "$Title".PadLeft(30 + ($Title.Length / 2)).PadRight(60) -ForegroundColor Cyan
    Write-Host "=" * 60 -ForegroundColor Cyan
}

function Show-Step {
    param([string]$Step, [string]$Description)
    Write-Host "`n▶ $Step" -ForegroundColor Yellow
    Write-Host "  $Description" -ForegroundColor Gray
}

function Test-Connection {
    param([string]$Url, [string]$ServiceName)
    try {
        $response = Invoke-WebRequest -Uri $Url -Method Get -TimeoutSec 5 -UseBasicParsing
        return $true
    }
    catch {
        return $false
    }
}

function Select-Project {
    Write-LogMessage "📋 Selecting project..." "Cyan"
    
    if ($ProjectId -ne "") {
        # Validate provided project ID
        try {
            $project = Invoke-RestMethod -Uri "$BaseUrl/api/projects/$ProjectId" -Method Get -TimeoutSec 10
            Write-LogMessage "✅ Using project: $($project.name) ($ProjectId)" "Green"
            return $ProjectId
        }
        catch {
            Write-LogMessage "❌ Project not found: $ProjectId" "Red"
            Write-LogMessage "Available projects:" "Yellow"
        }
    }
    
    # List available projects
    try {
        $projects = Invoke-RestMethod -Uri "$BaseUrl/api/projects" -Method Get -TimeoutSec 10
        if ($projects -and $projects.Count -gt 0) {
            Write-LogMessage "Available projects:" "Yellow"
            for ($i = 0; $i -lt $projects.Count; $i++) {
                Write-Host "  [$i] $($projects[$i].name) ($($projects[$i].id))" -ForegroundColor White
            }
            
            do {
                $selection = Read-Host "Select project (0-$($projects.Count - 1)) or enter project ID"
                if ([int]::TryParse($selection, [ref]$index) -and $index -ge 0 -and $index -lt $projects.Count) {
                    $selectedProject = $projects[$index].id
                    Write-LogMessage "✅ Selected project: $($projects[$index].name)" "Green"
                    return $selectedProject
                }
                elseif ($selection -ne "") {
                    # Try as direct project ID
                    try {
                        $project = Invoke-RestMethod -Uri "$BaseUrl/api/projects/$selection" -Method Get -TimeoutSec 10
                        Write-LogMessage "✅ Using project: $($project.name)" "Green"
                        return $selection
                    }
                    catch {
                        Write-LogMessage "❌ Project not found: $selection" "Red"
                    }
                }
            } while ($true)
        }
        else {
            Write-LogMessage "⚠️ No projects found. Please create a project first." "Yellow"
            return $null
        }
    }
    catch {
        Write-LogMessage "❌ Failed to retrieve projects: $($_.Exception.Message)" "Red"
        return $null
    }
}

function Select-Document {
    Write-LogMessage "📂 Selecting document..." "Cyan"
    
    if ($DocumentPath -ne "" -and (Test-Path $DocumentPath)) {
        $fileName = Split-Path $DocumentPath -Leaf
        $fileSize = [math]::Round((Get-Item $DocumentPath).Length / 1MB, 2)
        Write-LogMessage "✅ Using document: $fileName ($fileSize MB)" "Green"
        return $DocumentPath
    }
    elseif ($DocumentPath -ne "") {
        Write-LogMessage "❌ Document not found: $DocumentPath" "Red"
    }
    
    # Prompt for document path
    do {
        $inputPath = Read-Host "Enter document path (or 'test' for sample document)"
        
        if ($inputPath -eq "test") {
            # Try to find a sample document
            $samplePaths = @(
                "C:\Users\deepakgupta13\OneDrive - Nagarro\Cloud Practice\migration_platform_2\NBQ Assessment documents\NBQ- Documents Received\D8_NESA Self Assessment Report.pdf",
                ".\samples\sample.pdf",
                ".\samples\sample.docx"
            )
            
            foreach ($path in $samplePaths) {
                if (Test-Path $path) {
                    Write-LogMessage "✅ Using sample document: $path" "Green"
                    return $path
                }
            }
            
            Write-LogMessage "❌ No sample document found. Please provide a document path." "Red"
            continue
        }
        
        if (Test-Path $inputPath) {
            $fileName = Split-Path $inputPath -Leaf
            $fileSize = [math]::Round((Get-Item $inputPath).Length / 1MB, 2)
            Write-LogMessage "✅ Selected document: $fileName ($fileSize MB)" "Green"
            return $inputPath
        }
        else {
            Write-LogMessage "❌ Document not found: $inputPath" "Red"
        }
    } while ($true)
}

function Test-Services {
    Write-LogMessage "🔍 Checking essential services..." "Cyan"
    
    $services = @(
        @{ Name = "Backend API"; Url = "$BaseUrl/health" },
        @{ Name = "Project Service"; Url = "http://localhost:8001/health" },
        @{ Name = "Document Service"; Url = "http://localhost:8003/health" },
        @{ Name = "Vector Service"; Url = "http://localhost:8005/health" },
        @{ Name = "Graph Service"; Url = "http://localhost:8006/health" },
        @{ Name = "LLM Service"; Url = "http://localhost:8007/health" }
    )
    
    $allHealthy = $true
    foreach ($service in $services) {
        if (Test-Connection -Url $service.Url -ServiceName $service.Name) {
            Write-LogMessage "✅ $($service.Name): Healthy" "Green"
        }
        else {
            Write-LogMessage "❌ $($service.Name): Unavailable" "Red"
            $allHealthy = $false
        }
    }
    
    if (-not $allHealthy) {
        $continue = Read-Host "Some services are unavailable. Continue anyway? (y/N)"
        if ($continue -ne "y" -and $continue -ne "Y") {
            return $false
        }
    }
    
    return $true
}

function Upload-Document {
    param([string]$ProjectId, [string]$DocumentPath)
    
    Write-LogMessage "📤 Uploading document..." "Cyan"
    
    # Generate correlation ID
    $script:CorrelationId = "doc_process_$([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds())"
    Write-LogMessage "🔗 Correlation ID: $CorrelationId" "Yellow"
    
    try {
        # Use curl for simpler file upload
        $fileName = Split-Path $DocumentPath -Leaf
        Write-LogMessage "📄 Uploading: $fileName" "White"
        
        $curlArgs = @(
            "-X", "POST"
            "-H", "X-Correlation-ID: $CorrelationId"
            "-F", "files=@`"$DocumentPath`""
            "$BaseUrl/api/projects/$ProjectId/files"
        )
        
        $result = & curl @curlArgs 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            Write-LogMessage "✅ Document uploaded successfully!" "Green"
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
    param([string]$ProjectId)
    
    Write-LogMessage "⚙️ Triggering document processing..." "Cyan"
    
    try {
        $headers = @{
            'X-Correlation-ID' = $CorrelationId
            'Content-Type' = 'application/json'
        }
        
        $body = @{ correlation_id = $CorrelationId } | ConvertTo-Json
        $response = Invoke-RestMethod -Uri "$BaseUrl/api/projects/$ProjectId/assess" -Method Post -Headers $headers -Body $body
        
        Write-LogMessage "✅ Processing triggered successfully!" "Green"
        return $true
    }
    catch {
        Write-LogMessage "❌ Failed to trigger processing: $($_.Exception.Message)" "Red"
        return $false
    }
}

function Monitor-Processing {
    param([string]$ProjectId)
    
    Write-LogMessage "🔄 Monitoring processing (5 minutes)..." "Cyan"
    
    $startTime = Get-Date
    $endTime = $startTime.AddMinutes(5)
    $lastStatus = ""
    
    while ((Get-Date) -lt $endTime) {
        # Check project status
        try {
            $project = Invoke-RestMethod -Uri "$BaseUrl/api/projects/$ProjectId" -Method Get -TimeoutSec 10
            
            if ($project.status -ne $lastStatus) {
                Write-LogMessage "📊 Project status: $($project.status)" "Cyan"
                $lastStatus = $project.status
            }
            
            if ($project.status -eq "completed") {
                Write-LogMessage "🎉 Processing completed successfully!" "Green"
                return $true
            }
            
            if ($project.status -eq "failed") {
                Write-LogMessage "❌ Processing failed!" "Red"
                return $false
            }
        }
        catch {
            Write-LogMessage "⚠️ Could not check project status" "Yellow"
        }
        
        # Brief pause before next check
        Start-Sleep -Seconds 15
    }
    
    Write-LogMessage "⏰ Processing monitoring timeout (5 minutes)" "Yellow"
    return $false
}

function Get-ProcessingResults {
    param([string]$ProjectId)
    
    Write-LogMessage "🔍 Collecting processing results..." "Cyan"
    
    $results = @{}
    
    # Check various endpoints for results
    $endpoints = @(
        @{ Name = "Chunks"; Url = "$BaseUrl/api/projects/$ProjectId/chunks" },
        @{ Name = "Entities"; Url = "$BaseUrl/api/projects/$ProjectId/entities" },
        @{ Name = "Graph Nodes"; Url = "$BaseUrl/api/projects/$ProjectId/graph/nodes/count" }
    )
    
    foreach ($endpoint in $endpoints) {
        try {
            $response = Invoke-RestMethod -Uri $endpoint.Url -Method Get -TimeoutSec 15
            
            $count = if ($response.count) { $response.count } 
                    elseif ($response -is [array]) { $response.Count } 
                    else { "✓" }
            
            Write-LogMessage "✅ $($endpoint.Name): $count" "Green"
            $results[$endpoint.Name] = $response
        }
        catch {
            Write-LogMessage "⚠️ $($endpoint.Name): Not available" "Yellow"
        }
    }
    
    return $results
}

function Export-Logs {
    param([string]$ProjectId, [string]$CorrelationId)
    
    Write-LogMessage "📦 Exporting logs..." "Cyan"
    
    # Create timestamp for log file
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $logFileName = "document_processing_logs_$timestamp.log"
    $logFilePath = Join-Path "c:\Users\deepakgupta13\OneDrive - Nagarro\Cloud Practice\migration_platform_2\testing" $logFileName
    
    try {
        # Get list of available services
        Write-LogMessage "📋 Getting list of services..." "White"
        $servicesResp = Invoke-RestMethod -Uri "$BaseUrl/api/logs/services" -Method Get -TimeoutSec 10
        $services = $servicesResp.services
        
        if (-not $services -or $services.Count -eq 0) {
            Write-LogMessage "⚠️ No services found for log collection" "Yellow"
            return $false
        }
        
        Write-LogMessage "🔍 Found $($services.Count) services: $($services -join ', ')" "White"
        
        # Search logs by correlation ID across all services
        Write-LogMessage "🔍 Searching logs by correlation ID: $CorrelationId" "White"
        $searchParams = @{
            cid = $CorrelationId
            limit = 1000
        }
        
        $queryString = ($searchParams.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join '&'
        $searchUrl = "$BaseUrl/api/logs/search?$queryString"
        
        $logsResp = Invoke-RestMethod -Uri $searchUrl -Method Get -TimeoutSec 30
        
        if ($logsResp -and $logsResp.entries -and $logsResp.entries.Count -gt 0) {
            Write-LogMessage "✅ Found $($logsResp.entries.Count) log entries" "Green"
            
            # Format logs for export
            $logContent = @()
            $logContent += "=" * 80
            $logContent += "DOCUMENT PROCESSING LOGS EXPORT"
            $logContent += "Project ID: $ProjectId"
            $logContent += "Correlation ID: $CorrelationId"
            $logContent += "Export Timestamp: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
            $logContent += "Total Entries: $($logsResp.entries.Count)"
            $logContent += "=" * 80
            $logContent += ""
            
            # Group logs by service for better organization
            $logsByService = @{}
            foreach ($entry in $logsResp.entries) {
                $service = $entry.service
                if (-not $logsByService.ContainsKey($service)) {
                    $logsByService[$service] = @()
                }
                $logsByService[$service] += $entry
            }
            
            # Add logs to content, grouped by service
            foreach ($service in $logsByService.Keys | Sort-Object) {
                $logContent += "-" * 60
                $logContent += "SERVICE: $service ($($logsByService[$service].Count) entries)"
                $logContent += "-" * 60
                
                foreach ($entry in $logsByService[$service] | Sort-Object { $_.timestamp }) {
                    $timestamp = if ($entry.timestamp) { 
                        try { 
                            [DateTime]::Parse($entry.timestamp).ToString("yyyy-MM-dd HH:mm:ss.fff") 
                        } 
                        catch { 
                            $entry.timestamp 
                        } 
                    } else { 
                        "-" 
                    }
                    
                    $level = $entry.level.PadRight(7)
                    $message = $entry.message -replace "`n", "`n        "
                    
                    $logContent += "[$timestamp] [$level] $message"
                    
                    # Add additional fields if present
                    if ($entry.project_id) {
                        $logContent += "        Project ID: $($entry.project_id)"
                    }
                    if ($entry.correlation_id -and $entry.correlation_id -ne $CorrelationId) {
                        $logContent += "        Correlation ID: $($entry.correlation_id)"
                    }
                }
                $logContent += ""
            }
            
            # Write to file
            $logContent | Out-File -FilePath $logFilePath -Encoding UTF8
            Write-LogMessage "✅ Logs exported to: $logFilePath" "Green"
            
            # Show summary
            Write-LogMessage "📊 Log Summary:" "Cyan"
            foreach ($service in $logsByService.Keys | Sort-Object) {
                Write-LogMessage "  $service : $($logsByService[$service].Count) entries" "White"
            }
            
            return $true
        }
        else {
            Write-LogMessage "⚠️ No logs found for correlation ID: $CorrelationId" "Yellow"
            
            # Create empty log file with header
            $emptyContent = @(
                "=" * 80
                "DOCUMENT PROCESSING LOGS EXPORT"
                "Project ID: $ProjectId"
                "Correlation ID: $CorrelationId"
                "Export Timestamp: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
                "Total Entries: 0"
                "=" * 80
                ""
                "No log entries found for the specified correlation ID."
            )
            $emptyContent | Out-File -FilePath $logFilePath -Encoding UTF8
            Write-LogMessage "📝 Empty log file created: $logFilePath" "Yellow"
            
            return $false
        }
    }
    catch {
        Write-LogMessage "❌ Failed to export logs: $($_.Exception.Message)" "Red"
        return $false
    }
}

function Show-Summary {
    param([string]$ProjectId, [string]$DocumentPath, [hashtable]$Results)
    
    $endTime = Get-Date
    $duration = $endTime - $script:StartTime
    
    Write-Host "`n" + "=" * 80 -ForegroundColor Green
    Write-Host "PROCESSING COMPLETE - SUMMARY".PadLeft(40 + 15).PadRight(80) -ForegroundColor Green
    Write-Host "=" * 80 -ForegroundColor Green
    
    Write-Host "⏱️  Duration     : $($duration.ToString('hh\:mm\:ss'))" -ForegroundColor White
    Write-Host "📁 Document     : $(Split-Path $DocumentPath -Leaf)" -ForegroundColor White
    Write-Host "🔢 Project ID   : $ProjectId" -ForegroundColor White
    Write-Host "🔗 Correlation  : $CorrelationId" -ForegroundColor White
    
    if ($Results.Count -gt 0) {
        Write-Host "`n📊 Results:" -ForegroundColor Cyan
        foreach ($key in $Results.Keys) {
            $value = $Results[$key]
            $count = if ($value.count) { $value.count } 
                    elseif ($value -is [array]) { $value.Count } 
                    else { $value }
            Write-Host "  $key : $count" -ForegroundColor White
        }
    }
    
    Write-Host "`n" + "=" * 80 -ForegroundColor Green
}

# Main execution
try {
    Show-Header "ASCENT DOCUMENT PROCESSING & LOG EXPORT"
    
    # Check if we're in test mode
    if ($ProjectId -eq "test" -and $DocumentPath -eq "test") {
        $TestMode = $true
        Write-LogMessage "🧪 Running in test mode" "Yellow"
    }
    
    # Test service connectivity
    Show-Step "Step 1: Service Health Check" "Verifying all platform services are running"
    if (-not (Test-Services)) {
        Write-LogMessage "❌ Required services are not available. Exiting." "Red"
        exit 1
    }
    
    # Select project
    Show-Step "Step 2: Project Selection" "Choosing which project to process the document for"
    $selectedProjectId = Select-Project
    if (-not $selectedProjectId) {
        Write-LogMessage "❌ No project selected. Exiting." "Red"
        exit 1
    }
    
    # Select document
    Show-Step "Step 3: Document Selection" "Choosing which document to process"
    $selectedDocument = Select-Document
    if (-not $selectedDocument) {
        Write-LogMessage "❌ No document selected. Exiting." "Red"
        exit 1
    }
    
    # Upload document
    Show-Step "Step 4: Document Upload" "Uploading document to the platform"
    if (-not (Upload-Document -ProjectId $selectedProjectId -DocumentPath $selectedDocument)) {
        Write-LogMessage "❌ Document upload failed. Exiting." "Red"
        exit 1
    }
    
    # Trigger processing
    Show-Step "Step 5: Processing Trigger" "Starting document processing workflow"
    if (-not (Trigger-Processing -ProjectId $selectedProjectId)) {
        Write-LogMessage "❌ Failed to trigger processing. Exiting." "Red"
        exit 1
    }
    
    # Monitor processing
    Show-Step "Step 6: Processing Monitor" "Monitoring document processing for up to 5 minutes"
    $processingSuccess = Monitor-Processing -ProjectId $selectedProjectId
    
    # Get results
    Show-Step "Step 7: Results Collection" "Collecting processing results"
    $results = Get-ProcessingResults -ProjectId $selectedProjectId
    
    # Export logs
    Show-Step "Step 8: Log Export" "Exporting all logs related to this processing"
    Export-Logs -ProjectId $selectedProjectId -CorrelationId $CorrelationId
    
    # Show summary
    Show-Summary -ProjectId $selectedProjectId -DocumentPath $selectedDocument -Results $results
    
    Write-LogMessage "🎉 Document processing workflow completed!" "Green"
}
catch {
    Write-LogMessage "💥 Unexpected error: $($_.Exception.Message)" "Red"
    Write-LogMessage "Stack trace: $($_.ScriptStackTrace)" "Red"
    exit 1
}