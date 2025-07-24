# Nagarro AgentiMigrate Platform - Simple Windows Launcher (Rancher Desktop)
Write-Host "🚀 Nagarro AgentiMigrate Platform - Quick Launcher" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "   Using Rancher Desktop for containerization" -ForegroundColor Gray
Write-Host ""

# Create logs directory if it doesn't exist
if (!(Test-Path "logs")) {
    New-Item -ItemType Directory -Path "logs" -Force | Out-Null
}

# Enhanced logging setup
$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$logFile = "logs/start_platform_$timestamp.log"
$masterLogFile = "logs/platform_master.log"

# Function for enhanced logging
function Write-LogMessage {
    param(
        [string]$Message,
        [string]$Level = "INFO",
        [string]$Color = "White"
    )
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] [$Level] [START-PLATFORM] $Message"

    # Write to console with color
    Write-Host $Message -ForegroundColor $Color

    # Write to both session log and master log
    Add-Content -Path $logFile -Value $logEntry -Encoding UTF8
    Add-Content -Path $masterLogFile -Value $logEntry -Encoding UTF8
}

Write-LogMessage "=== NAGARRO AGENTIMIGRATE PLATFORM LAUNCHER STARTED ===" "INFO" "Cyan"
Write-LogMessage "Launcher Log File: $logFile" "INFO" "Gray"
Write-LogMessage "Master Log File: $masterLogFile" "INFO" "Gray"
Write-LogMessage "PowerShell Version: $($PSVersionTable.PSVersion)" "INFO" "Gray"
Write-LogMessage "Current Directory: $(Get-Location)" "INFO" "Gray"

# Enhanced Rancher Desktop detection
Write-LogMessage "Checking for Rancher Desktop installation..." "INFO" "Yellow"

# Multiple possible locations for Rancher Desktop
$possiblePaths = @(
    "$env:USERPROFILE\.rd\bin\rdctl.exe",
    "$env:LOCALAPPDATA\Programs\Rancher Desktop\resources\resources\win32\bin\rdctl.exe",
    "$env:PROGRAMFILES\Rancher Desktop\resources\resources\win32\bin\rdctl.exe",
    "$env:PROGRAMFILES(x86)\Rancher Desktop\resources\resources\win32\bin\rdctl.exe"
)

$rancherFound = $false
$rancherPath = ""

foreach ($path in $possiblePaths) {
    Write-LogMessage "Checking path: $path" "INFO" "Gray"
    if (Test-Path $path) {
        $rancherFound = $true
        $rancherPath = $path
        Write-LogMessage "Rancher Desktop found at: $path" "SUCCESS" "Green"
        break
    } else {
        Write-LogMessage "Not found at: $path" "INFO" "Gray"
    }
}

# Also check if Rancher Desktop is running (alternative detection)
if (!$rancherFound) {
    Write-LogMessage "Checking if Rancher Desktop process is running..." "INFO" "Gray"
    $rancherProcess = Get-Process -Name "Rancher Desktop" -ErrorAction SilentlyContinue
    if ($rancherProcess) {
        Write-LogMessage "Rancher Desktop process found running (PID: $($rancherProcess.Id))" "SUCCESS" "Green"
        $rancherFound = $true
    } else {
        Write-LogMessage "Rancher Desktop process not found" "INFO" "Gray"
    }
}

if (!$rancherFound) {
    Write-LogMessage "Rancher Desktop not found in any expected location" "ERROR" "Red"
    Write-LogMessage "Searched paths:" "ERROR" "Red"
    foreach ($path in $possiblePaths) {
        Write-LogMessage "  - $path" "ERROR" "Red"
    }
    Write-LogMessage "Please install Rancher Desktop first:" "ERROR" "Yellow"
    Write-LogMessage "1. Download from: https://rancherdesktop.io/" "ERROR" "Yellow"
    Write-LogMessage "2. Install and start Rancher Desktop" "ERROR" "Yellow"
    Write-LogMessage "3. Ensure 'dockerd (moby)' is selected as container runtime" "ERROR" "Yellow"
    Write-LogMessage "4. Run this script again" "ERROR" "Yellow"
    Write-LogMessage "=== LAUNCHER FAILED - RANCHER DESKTOP NOT FOUND ===" "ERROR" "Red"
    Read-Host "Press Enter to exit"
    exit 1
} else {
    Write-LogMessage "Rancher Desktop installation confirmed" "SUCCESS" "Green"
}

# Check if Docker is available through Rancher Desktop
Write-LogMessage "Checking Docker availability through Rancher Desktop..." "INFO" "Yellow"
try {
    Write-LogMessage "Running: docker --version" "INFO" "Gray"
    $dockerVersion = docker --version 2>$null
    if (!$dockerVersion) {
        Write-LogMessage "Docker command not available" "ERROR" "Red"
        Write-LogMessage "Please ensure Rancher Desktop is running:" "ERROR" "Yellow"
        Write-LogMessage "1. Start Rancher Desktop from Start Menu" "ERROR" "Yellow"
        Write-LogMessage "2. Wait for it to fully start (2-3 minutes)" "ERROR" "Yellow"
        Write-LogMessage "3. Ensure 'dockerd (moby)' is selected as container runtime" "ERROR" "Yellow"
        Write-LogMessage "4. Run this script again" "ERROR" "Yellow"
        Write-LogMessage "=== LAUNCHER FAILED - DOCKER NOT AVAILABLE ===" "ERROR" "Red"
        Read-Host "Press Enter to exit"
        exit 1
    }
    Write-LogMessage "Docker version: $dockerVersion" "SUCCESS" "Green"

    # Test Docker daemon connectivity
    Write-LogMessage "Testing Docker daemon connectivity..." "INFO" "Gray"
    $dockerTest = docker ps 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-LogMessage "Docker daemon is responding" "SUCCESS" "Green"
    } else {
        Write-LogMessage "Docker daemon not responding (exit code: $LASTEXITCODE)" "WARNING" "Yellow"
        Write-LogMessage "This may indicate Rancher Desktop is still starting up" "WARNING" "Yellow"
    }

} catch {
    Write-LogMessage "Exception while checking Docker: $($_.Exception.Message)" "ERROR" "Red"
    Write-LogMessage "=== LAUNCHER FAILED - DOCKER CHECK ERROR ===" "ERROR" "Red"
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if setup has been run
Write-LogMessage "Checking if initial setup has been completed..." "INFO" "Yellow"
if (!(Test-Path ".env")) {
    Write-LogMessage "First time setup required - .env file not found" "WARNING" "Yellow"
    Write-LogMessage "Running setup.ps1..." "INFO" "Gray"
    & ".\setup.ps1"

    if ($LASTEXITCODE -ne 0) {
        Write-LogMessage "Setup failed with exit code: $LASTEXITCODE" "ERROR" "Red"
        Write-LogMessage "=== LAUNCHER FAILED - SETUP ERROR ===" "ERROR" "Red"
        Read-Host "Press Enter to exit"
        exit 1
    } else {
        Write-LogMessage "Setup completed successfully" "SUCCESS" "Green"
    }
} else {
    Write-LogMessage ".env file found - setup previously completed" "SUCCESS" "Green"
}

# Check if OpenAI API key is configured
$envContent = Get-Content ".env" -Raw
if ($envContent -match "your_openai_api_key_here") {
    Write-Host "⚠️  OpenAI API key not configured!" -ForegroundColor Yellow
    Write-Host "   Please edit .env file and add your OpenAI API key." -ForegroundColor Yellow
    Write-Host "   Get one from: https://platform.openai.com/api-keys" -ForegroundColor Yellow
    Write-Host ""

    $openEnv = Read-Host "   Open .env file now? (y/N)"
    if ($openEnv -eq "y" -or $openEnv -eq "Y") {
        notepad ".env"
        Write-Host "   Please save the .env file after adding your API key." -ForegroundColor Yellow
        Read-Host "   Press Enter when done"
    }

    $continue = Read-Host "   Continue without API key? Platform won't work properly (y/N)"
    if ($continue -ne "y" -and $continue -ne "Y") {
        exit 0
    }
}

Write-Host ""
Write-Host "🚀 Starting the platform..." -ForegroundColor Green

# Use the optimized build script
if (Test-Path ".\build-optimized.bat") {
    & ".\build-optimized.bat"
} else {
    # Fallback to run-mvp.ps1
    & ".\run-mvp.ps1"
}

Write-Host ""
Write-Host "✨ Platform startup complete!" -ForegroundColor Green
Write-Host "   Access the Command Center at: http://localhost:3000" -ForegroundColor Yellow
Write-Host ""
Read-Host "Press Enter to exit"
