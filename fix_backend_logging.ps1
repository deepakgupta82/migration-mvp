# Fix Backend Logging Issues - PowerShell Script

Write-Host "🔧 Fixing Backend Logging Issues..." -ForegroundColor Yellow

# Change to backend directory
$backendPath = "C:\Users\deepakgupta13\OneDrive - Nagarro\Cloud Practice\migration_platform_2\backend"
Set-Location $backendPath

Write-Host "📍 Working in: $backendPath" -ForegroundColor Blue

# Stop any existing backend processes
Write-Host "🛑 Stopping backend processes..." -ForegroundColor Red
try {
    Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "*backend*" } | Stop-Process -Force
    Get-Process -Name "uvicorn" -ErrorAction SilentlyContinue | Stop-Process -Force
    Start-Sleep -Seconds 2
    Write-Host "✅ Backend processes stopped" -ForegroundColor Green
} catch {
    Write-Host "ℹ️ No backend processes to stop" -ForegroundColor Yellow
}

# Clean up log files
Write-Host "🧹 Cleaning up log files..." -ForegroundColor Blue

$logsPath = Join-Path $backendPath "logs"

# Ensure logs directory exists
if (!(Test-Path $logsPath)) {
    New-Item -ItemType Directory -Path $logsPath -Force | Out-Null
    Write-Host "✅ Created logs directory" -ForegroundColor Green
}

# Remove potentially locked log files
$logFiles = @("database.log.1", "platform.log.1", "platform_master.log.1", "agents.log.1")
foreach ($logFile in $logFiles) {
    $filePath = Join-Path $logsPath $logFile
    if (Test-Path $filePath) {
        try {
            Remove-Item $filePath -Force
            Write-Host "🗑️ Removed: $logFile" -ForegroundColor Green
        } catch {
            Write-Host "⚠️ Could not remove: $logFile (may not be locked)" -ForegroundColor Yellow
        }
    }
}

# Also clean up main log files if they're corrupted
$mainLogFiles = @("database.log", "platform.log", "platform_master.log", "agents.log")
foreach ($logFile in $mainLogFiles) {
    $filePath = Join-Path $logsPath $logFile
    if (Test-Path $filePath) {
        try {
            # Try to open and close the file to test if it's locked
            $stream = [System.IO.File]::Open($filePath, 'Open', 'Write', 'None')
            $stream.Close()
            Write-Host "✅ $logFile is not locked" -ForegroundColor Green
        } catch {
            Write-Host "🔒 $logFile is locked, attempting to rename..." -ForegroundColor Yellow
            try {
                $backupName = "$logFile.backup.$(Get-Date -Format 'yyyyMMdd_HHmmss')"
                Move-Item $filePath (Join-Path $logsPath $backupName) -Force
                Write-Host "✅ Moved locked file to: $backupName" -ForegroundColor Green
            } catch {
                Write-Host "❌ Could not move locked file: $logFile" -ForegroundColor Red
            }
        }
    }
}

Write-Host "✅ Log cleanup complete!" -ForegroundColor Green
Write-Host ""

# Check if the fixed logging configuration exists
$loggingConfigPath = Join-Path $backendPath "app\core\logging_config.py"
if (Test-Path $loggingConfigPath) {
    Write-Host "✅ Fixed logging configuration is in place" -ForegroundColor Green
} else {
    Write-Host "❌ Logging configuration file not found!" -ForegroundColor Red
    exit 1
}

# Ask user if they want to start the backend
$startBackend = Read-Host "🚀 Start the backend now? (y/n)"
if ($startBackend -eq "y" -or $startBackend -eq "Y") {
    Write-Host "🚀 Starting backend with fixed logging..." -ForegroundColor Blue
    Write-Host "📝 Logs will now use Windows-safe TimedRotatingFileHandler" -ForegroundColor Blue
    Write-Host "Press Ctrl+C to stop the backend when needed" -ForegroundColor Yellow
    Write-Host ""
    
    # Start the backend
    python -m app.main
} else {
    Write-Host "ℹ️ Backend not started. You can manually start it with:" -ForegroundColor Blue
    Write-Host "   cd '$backendPath'" -ForegroundColor White
    Write-Host "   python -m app.main" -ForegroundColor White
}

Write-Host ""
Write-Host "🎉 Backend logging issue should now be resolved!" -ForegroundColor Green
