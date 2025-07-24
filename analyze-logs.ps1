# Nagarro AgentiMigrate Platform - Log Analysis Script
param(
    [string]$LogFile = "",
    [switch]$ShowErrors,
    [switch]$ShowWarnings,
    [switch]$ShowAll,
    [switch]$Latest,
    [int]$LastHours = 24
)

Write-Host "🔍 Nagarro AgentiMigrate Platform - Log Analyzer" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

# Function to analyze log entries
function Analyze-LogEntry {
    param([string]$Line)

    if ($Line -match '\[(.*?)\] \[(.*?)\] \[(.*?)\] (.*)') {
        return @{
            Timestamp = $matches[1]
            Level = $matches[2]
            Component = $matches[3]
            Message = $matches[4]
            OriginalLine = $Line
        }
    }
    return $null
}

# Function to display log entry with color
function Show-LogEntry {
    param($Entry)

    $color = switch ($Entry.Level) {
        "ERROR" { "Red" }
        "WARNING" { "Yellow" }
        "SUCCESS" { "Green" }
        "INFO" { "White" }
        default { "Gray" }
    }

    Write-Host "[$($Entry.Timestamp)] " -NoNewline -ForegroundColor Gray
    Write-Host "[$($Entry.Level)] " -NoNewline -ForegroundColor $color
    Write-Host "[$($Entry.Component)] " -NoNewline -ForegroundColor Cyan
    Write-Host $Entry.Message -ForegroundColor $color
}

# Determine which log file to analyze
if ($Latest) {
    $LogFile = "logs/platform_master.log"
} elseif ($LogFile -eq "") {
    if (Test-Path "logs/platform_master.log") {
        $LogFile = "logs/platform_master.log"
    } else {
        Write-Host "❌ No log file specified and master log not found" -ForegroundColor Red
        Write-Host "Usage: .\analyze-logs.ps1 [-LogFile path] [-Latest] [-ShowErrors] [-ShowWarnings] [-ShowAll]" -ForegroundColor Yellow
        exit 1
    }
}

if (!(Test-Path $LogFile)) {
    Write-Host "❌ Log file not found: $LogFile" -ForegroundColor Red
    exit 1
}

Write-Host "📄 Analyzing log file: $LogFile" -ForegroundColor Green
Write-Host ""

# Read and parse log file
$logContent = Get-Content $LogFile -ErrorAction SilentlyContinue
if (!$logContent) {
    Write-Host "❌ Could not read log file or file is empty" -ForegroundColor Red
    exit 1
}

$entries = @()
$errorCount = 0
$warningCount = 0
$successCount = 0
$infoCount = 0

foreach ($line in $logContent) {
    $entry = Analyze-LogEntry $line
    if ($entry) {
        # Filter by time if specified
        if ($LastHours -gt 0) {
            try {
                $entryTime = [DateTime]::Parse($entry.Timestamp)
                $cutoffTime = (Get-Date).AddHours(-$LastHours)
                if ($entryTime -lt $cutoffTime) {
                    continue
                }
            } catch {
                # If we can't parse the timestamp, include the entry
            }
        }

        $entries += $entry

        switch ($entry.Level) {
            "ERROR" { $errorCount++ }
            "WARNING" { $warningCount++ }
            "SUCCESS" { $successCount++ }
            "INFO" { $infoCount++ }
        }
    }
}

# Display summary
Write-Host "📊 Log Summary (Last $LastHours hours):" -ForegroundColor Cyan
Write-Host "  Total Entries: $($entries.Count)" -ForegroundColor White
Write-Host "  Errors: $errorCount" -ForegroundColor Red
Write-Host "  Warnings: $warningCount" -ForegroundColor Yellow
Write-Host "  Success: $successCount" -ForegroundColor Green
Write-Host "  Info: $infoCount" -ForegroundColor White
Write-Host ""

# Show entries based on filters
if ($ShowAll) {
    Write-Host "📋 All Log Entries:" -ForegroundColor Cyan
    foreach ($entry in $entries) {
        Show-LogEntry $entry
    }
} elseif ($ShowErrors) {
    Write-Host "❌ Error Entries:" -ForegroundColor Red
    $errorEntries = $entries | Where-Object { $_.Level -eq "ERROR" }
    if ($errorEntries.Count -eq 0) {
        Write-Host "  No errors found! ✅" -ForegroundColor Green
    } else {
        foreach ($entry in $errorEntries) {
            Show-LogEntry $entry
        }
    }
} elseif ($ShowWarnings) {
    Write-Host "⚠️ Warning Entries:" -ForegroundColor Yellow
    $warningEntries = $entries | Where-Object { $_.Level -eq "WARNING" }
    if ($warningEntries.Count -eq 0) {
        Write-Host "  No warnings found! ✅" -ForegroundColor Green
    } else {
        foreach ($entry in $warningEntries) {
            Show-LogEntry $entry
        }
    }
} else {
    # Default: Show recent errors and warnings
    Write-Host "🔍 Recent Issues (Errors & Warnings):" -ForegroundColor Cyan
    $issues = $entries | Where-Object { $_.Level -eq "ERROR" -or $_.Level -eq "WARNING" } | Select-Object -Last 20
    if ($issues.Count -eq 0) {
        Write-Host "  No recent issues found! ✅" -ForegroundColor Green
    } else {
        foreach ($entry in $issues) {
            Show-LogEntry $entry
        }
    }
}

Write-Host ""

# Component analysis
$components = $entries | Group-Object Component | Sort-Object Count -Descending
if ($components.Count -gt 0) {
    Write-Host "📈 Activity by Component:" -ForegroundColor Cyan
    foreach ($comp in $components) {
        $compErrors = ($comp.Group | Where-Object { $_.Level -eq "ERROR" }).Count
        $compWarnings = ($comp.Group | Where-Object { $_.Level -eq "WARNING" }).Count

        $status = if ($compErrors -gt 0) { "❌" } elseif ($compWarnings -gt 0) { "⚠️" } else { "✅" }
        Write-Host "  $status $($comp.Name): $($comp.Count) entries" -ForegroundColor White
        if ($compErrors -gt 0) {
            Write-Host "    Errors: $compErrors" -ForegroundColor Red
        }
        if ($compWarnings -gt 0) {
            Write-Host "    Warnings: $compWarnings" -ForegroundColor Yellow
        }
    }
}

Write-Host ""

# Recommendations
if ($errorCount -gt 0) {
    Write-Host "🔧 Recommendations:" -ForegroundColor Yellow
    Write-Host "  • Review error entries above for specific issues" -ForegroundColor Yellow
    Write-Host "  • Check if Rancher Desktop is running properly" -ForegroundColor Yellow
    Write-Host "  • Verify OpenAI API key is configured correctly" -ForegroundColor Yellow
    Write-Host "  • Ensure all required services are accessible" -ForegroundColor Yellow
} elseif ($warningCount -gt 0) {
    Write-Host "✅ Platform appears healthy with minor warnings" -ForegroundColor Green
} else {
    Write-Host "🎉 Platform appears to be running smoothly!" -ForegroundColor Green
}

Write-Host ""
Write-Host "💡 Usage Tips:" -ForegroundColor Cyan
Write-Host "  .\analyze-logs.ps1 -ShowErrors     # Show only errors" -ForegroundColor Gray
Write-Host "  .\analyze-logs.ps1 -ShowWarnings   # Show only warnings" -ForegroundColor Gray
Write-Host "  .\analyze-logs.ps1 -ShowAll        # Show all entries" -ForegroundColor Gray
Write-Host "  .\analyze-logs.ps1 -LastHours 6    # Show last 6 hours only" -ForegroundColor Gray
