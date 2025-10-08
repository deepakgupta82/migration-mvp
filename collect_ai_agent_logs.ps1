param(
    [Parameter(Mandatory=$true)]
    [string]$CorrelationId,

    [Parameter(Mandatory=$false)]
    [int]$TimeRangeMinutes = 30,

    [Parameter(Mandatory=$false)]
    [string]$OutputFile = "",
    
    [Parameter(Mandatory=$false)]
    [string[]]$Services = @("ai-agent-service", "llm-service", "vector-service", "graph-service", "document-service")
)

# ==============================================================================
# AI AGENT DISCUSSION LOG COLLECTION SCRIPT
# Purpose: Collect correlation-based logs from AI agent discussions
# ==============================================================================

# If no output file specified, create one with timestamp
if ([string]::IsNullOrEmpty($OutputFile)) {
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $OutputFile = "ai_agent_logs_${CorrelationId}_${timestamp}.txt"
}

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "AI AGENT DISCUSSION LOG COLLECTOR" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""
Write-Host "Collecting logs for correlation ID: $CorrelationId" -ForegroundColor Yellow
Write-Host "Time range: Last $TimeRangeMinutes minutes" -ForegroundColor Yellow
Write-Host "Services to search: $($Services -join ', ')" -ForegroundColor Yellow
Write-Host "Output file: $OutputFile" -ForegroundColor Yellow
Write-Host ""

# Calculate the cutoff time
$cutoffTime = (Get-Date).AddMinutes(-$TimeRangeMinutes)
Write-Host "Looking for logs since: $cutoffTime" -ForegroundColor Gray
Write-Host ""

# Build log directories to search
$logDirectories = @()
$baseDir = "c:\Users\deepakgupta13\OneDrive - Nagarro\Cloud Practice\migration_platform_2"

foreach ($service in $Services) {
    $serviceLogDir = Join-Path $baseDir "services\$service\logs"
    if (Test-Path $serviceLogDir) {
        $logDirectories += $serviceLogDir
    } else {
        Write-Host "Warning: Service logs directory not found: $serviceLogDir" -ForegroundColor Yellow
    }
}

if ($logDirectories.Count -eq 0) {
    Write-Host "ERROR: No log directories found! Exiting." -ForegroundColor Red
    exit 1
}

$collectedLogs = @()
$totalFilesProcessed = 0
$totalMatchingLines = 0
$serviceStats = @{}

foreach ($logDir in $logDirectories) {
    $serviceName = (Split-Path (Split-Path $logDir -Parent) -Leaf)
    Write-Host "Searching in: $serviceName" -ForegroundColor Cyan

    # Get all .log files in the directory
    $logFiles = Get-ChildItem -Path $logDir -Filter "*.log" -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending

    $serviceMatchCount = 0
    
    foreach ($logFile in $logFiles) {
        $totalFilesProcessed++
        Write-Host "  Processing: $($logFile.Name)" -NoNewline -ForegroundColor Gray

        $matchingLines = 0
        $fileContent = @()

        try {
            # Read the file content
            $lines = Get-Content -Path $logFile.FullName -ErrorAction Stop

            foreach ($line in $lines) {
                $includeLine = $false
                $logTimestamp = $null

                # Check different log formats and extract timestamp

                # Format 1: JSON format (newer services)
                # {"ts": "2025-10-08T17:23:51.717000", "level": "INFO", "service": "llm-service", "corr_id": "550e8400-e29b-41d4-a716-446655440000", ...}
                if ($line -match '"ts":\s*"([^"]+)"') {
                    $timestampStr = $matches[1]
                    try {
                        $logTimestamp = [DateTime]::Parse($timestampStr)
                    } catch {
                        try {
                            $logTimestamp = [DateTime]::ParseExact($timestampStr, "yyyy-MM-ddTHH:mm:ss.ffffff", $null)
                        } catch {
                            $logTimestamp = $null
                        }
                    }

                    # Check if correlation ID matches (JSON format)
                    if ($line -match "`"corr_id`":\s*`"($CorrelationId)`"") {
                        $includeLine = $true
                    }
                }
                # Format 2: Legacy format with [corr_id=UUID]
                # 2025-10-08 17:23:51 INFO [llm-service] [corr_id=550e8400-e29b-41d4-a716-446655440000] Getting LLM for process
                elseif ($line -match '^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}') {
                    $timestampMatch = [regex]::Match($line, '(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:,\d{3})?)')
                    if ($timestampMatch.Success) {
                        $timestampStr = $timestampMatch.Groups[1].Value
                        try {
                            if ($timestampStr -match ',') {
                                $logTimestamp = [DateTime]::ParseExact($timestampStr, "yyyy-MM-dd HH:mm:ss,fff", $null)
                            } else {
                                $logTimestamp = [DateTime]::ParseExact($timestampStr, "yyyy-MM-dd HH:mm:ss", $null)
                            }
                        } catch {
                            $logTimestamp = $null
                        }
                    }

                    # Check if correlation ID matches (legacy format)
                    if ($line -match "\[corr_id=$CorrelationId\]") {
                        $includeLine = $true
                    }
                    # Also check for corr_id with req_id format
                    elseif ($line -match "\[corr_id=$CorrelationId\s+req_id=[^\]]+\]") {
                        $includeLine = $true
                    }
                }
                # Format 3: Python logging format
                # 2025-10-08 17:23:51,154 - ai-agent-service - INFO - [corr_id=550e8400-e29b-41d4-a716-446655440000 req_id=-] - Message
                elseif ($line -match '^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},\d{3}\s+-\s+[^-]+\s+-\s+\w+\s+-\s+\[corr_id=([^\s]+)') {
                    $timestampMatch = [regex]::Match($line, '(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},\d{3})')
                    if ($timestampMatch.Success) {
                        $timestampStr = $timestampMatch.Groups[1].Value
                        try {
                            $logTimestamp = [DateTime]::ParseExact($timestampStr, "yyyy-MM-dd HH:mm:ss,fff", $null)
                        } catch {
                            $logTimestamp = $null
                        }
                    }

                    # Check if correlation ID matches
                    if ($line -match "\[corr_id=$CorrelationId(\s+|\])") {
                        $includeLine = $true
                    }
                }

                # Include line if correlation ID matches and timestamp is within range
                if ($includeLine -and $logTimestamp -and $logTimestamp -ge $cutoffTime) {
                    $fileContent += $line
                    $matchingLines++
                    $serviceMatchCount++
                }
            }

            if ($matchingLines -gt 0) {
                $collectedLogs += ""
                $collectedLogs += "=" * 100
                $collectedLogs += "SERVICE: $serviceName"
                $collectedLogs += "FILE: $($logFile.FullName)"
                $collectedLogs += "LAST MODIFIED: $($logFile.LastWriteTime)"
                $collectedLogs += "MATCHING LINES: $matchingLines"
                $collectedLogs += "=" * 100
                $collectedLogs += $fileContent
                $totalMatchingLines += $matchingLines
            }

            Write-Host " - $matchingLines matching lines" -ForegroundColor $(if ($matchingLines -gt 0) { "Green" } else { "Gray" })

        } catch {
            Write-Host " - ERROR: $($_.Exception.Message)" -ForegroundColor Red
        }
    }
    
    if ($serviceMatchCount -gt 0) {
        $serviceStats[$serviceName] = $serviceMatchCount
    }
}

# Write output to file
Write-Host ""
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "SUMMARY" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "Files processed: $totalFilesProcessed" -ForegroundColor White
Write-Host "Total matching lines: $totalMatchingLines" -ForegroundColor White
Write-Host ""

if ($serviceStats.Count -gt 0) {
    Write-Host "Matches by service:" -ForegroundColor Yellow
    foreach ($svc in $serviceStats.GetEnumerator() | Sort-Object Value -Descending) {
        Write-Host "  - $($svc.Key): $($svc.Value) lines" -ForegroundColor Cyan
    }
    Write-Host ""
}

if ($totalMatchingLines -gt 0) {
    $collectedLogs | Out-File -FilePath $OutputFile -Encoding UTF8
    Write-Host "SUCCESS: Logs collected and saved to: $OutputFile" -ForegroundColor Green
    Write-Host ""
    Write-Host "You can now review this file or share it for analysis." -ForegroundColor White
    Write-Host "To open the file, run: notepad $OutputFile" -ForegroundColor Gray
} else {
    Write-Host "WARNING: No logs found matching correlation ID '$CorrelationId'" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Troubleshooting tips:" -ForegroundColor Yellow
    Write-Host "  1. Verify the correlation ID is correct (check UI or API response)" -ForegroundColor Gray
    Write-Host "  2. Try increasing -TimeRangeMinutes (current: $TimeRangeMinutes)" -ForegroundColor Gray
    Write-Host "  3. Check if the services are running and generating logs" -ForegroundColor Gray
    Write-Host "  4. Verify log directories exist for: $($Services -join ', ')" -ForegroundColor Gray
}

Write-Host ""
Write-Host "=" * 80 -ForegroundColor Cyan
