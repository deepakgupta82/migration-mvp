param(
    [Parameter(Mandatory=$true)]
    [string]$CorrelationId,

    [Parameter(Mandatory=$false)]
    [int]$TimeRangeMinutes = 30,

    [Parameter(Mandatory=$false)]
    [string]$OutputFile = ""
)

# ==============================================================================
# CONFIGURATION SECTION - Edit this section to add/remove services to search
# ==============================================================================

# Default services to search (modify this list as needed)
$servicesToSearch = @(
    "document-service",
    "vector-service",
    "graph-service",
    "llm-service"
    # Add more services here as needed, e.g.:
    # "storage-service",
    # "project-service",
    # "ai-agent-service"
)

# Also search backend logs (set to $false to exclude)
$includeBackendLogs = $false

# ==============================================================================
# END CONFIGURATION SECTION
# ==============================================================================

# If no output file specified, create one with timestamp
if ([string]::IsNullOrEmpty($OutputFile)) {
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $OutputFile = "correlation_logs_${CorrelationId}_${timestamp}.txt"
}

Write-Host "Collecting logs for correlation ID: $CorrelationId"
Write-Host "Time range: Last $TimeRangeMinutes minutes"
Write-Host "Services to search: $($servicesToSearch -join ', ')"
if ($includeBackendLogs) {
    Write-Host "Also searching: backend logs"
}
Write-Host "Output file: $OutputFile"
Write-Host ""

# Calculate the cutoff time
$cutoffTime = (Get-Date).AddMinutes(-$TimeRangeMinutes)
Write-Host "Looking for logs since: $cutoffTime"
Write-Host ""

# Build log directories to search
$logDirectories = @()

# Add backend logs if enabled
if ($includeBackendLogs) {
    $backendLogDir = "c:\Users\deepakgupta13\OneDrive - Nagarro\Cloud Practice\migration_platform_2\backend\logs"
    if (Test-Path $backendLogDir) {
        $logDirectories += $backendLogDir
    }
}

# Add service logs
foreach ($service in $servicesToSearch) {
    $serviceLogDir = "c:\Users\deepakgupta13\OneDrive - Nagarro\Cloud Practice\migration_platform_2\services\$service\logs"
    if (Test-Path $serviceLogDir) {
        $logDirectories += $serviceLogDir
    } else {
        Write-Host "Warning: Service logs directory not found: $serviceLogDir" -ForegroundColor Yellow
    }
}

$collectedLogs = @()
$totalFilesProcessed = 0
$totalMatchingLines = 0

foreach ($logDir in $logDirectories) {
    Write-Host "Searching in: $logDir"

    # Get all .log files in the directory
    $logFiles = Get-ChildItem -Path $logDir -Filter "*.log" -File -ErrorAction SilentlyContinue

    foreach ($logFile in $logFiles) {
        $totalFilesProcessed++
        Write-Host "  Processing: $($logFile.Name)" -NoNewline

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
                # {"ts": "2025-08-21T07:42:17.726568", "level": "INFO", "service": "llm-service", "corr_id": "5e00aa2d-4e65-45ed-8f99-b1103543803d", ...}
                if ($line -match '"ts":\s*"([^"]+)"') {
                    $timestampStr = $matches[1]
                    try {
                        $logTimestamp = [DateTime]::Parse($timestampStr)
                    } catch {
                        # Try alternative format
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
                # 2025-08-18 18:29:05 INFO [llm-service] [corr_id=9f3569f8-ed1d-4fc0-bc7a-c62c63901a63] Getting LLM for process: entity_extraction
                elseif ($line -match '^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}') {
                    $timestampMatch = [regex]::Match($line, '(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:,\d{3})?)')
                    if ($timestampMatch.Success) {
                        $timestampStr = $timestampMatch.Groups[1].Value
                        try {
                            # Handle formats with and without milliseconds
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
                # Format 3: Storage service format
                # 2025-08-18 10:37:56,154 - storage-service - INFO - [corr_id=- req_id=-] - Starting Storage Service on port 8010...
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

                    # Check if correlation ID matches (storage format)
                    if ($line -match "\[corr_id=$CorrelationId(\s+|\])") {
                        $includeLine = $true
                    }
                }

                # Include line if correlation ID matches and timestamp is within range
                if ($includeLine -and $logTimestamp -and $logTimestamp -ge $cutoffTime) {
                    $fileContent += $line
                    $matchingLines++
                }
            }

            if ($matchingLines -gt 0) {
                $collectedLogs += ""
                $collectedLogs += "=================================================================================="
                $collectedLogs += "SERVICE: $($logFile.Directory.Parent.Name)/$($logFile.Name)"
                $collectedLogs += "FILE: $($logFile.FullName)"
                $collectedLogs += "MATCHING LINES: $matchingLines"
                $collectedLogs += "=================================================================================="
                $collectedLogs += $fileContent
                $totalMatchingLines += $matchingLines
            }

            Write-Host " - $matchingLines matching lines"

        } catch {
            Write-Host " - ERROR: $($_.Exception.Message)" -ForegroundColor Red
        }
    }
}

# Write output to file
Write-Host ""
Write-Host "Summary:"
Write-Host "- Files processed: $totalFilesProcessed"
Write-Host "- Total matching lines: $totalMatchingLines"
Write-Host ""

if ($totalMatchingLines -gt 0) {
    $collectedLogs | Out-File -FilePath $OutputFile -Encoding UTF8
    Write-Host "Logs collected and saved to: $OutputFile" -ForegroundColor Green
    Write-Host ""
    Write-Host "You can now share this file with GitHub Copilot for analysis."
} else {
    Write-Host "No logs found matching the correlation ID within the specified time range." -ForegroundColor Yellow
}