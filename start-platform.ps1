# Nagarro AgentiMigrate Platform - Simple Windows Launcher (Rancher Desktop)
Write-Host "🚀 Nagarro AgentiMigrate Platform - Quick Launcher" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "   Using Rancher Desktop for containerization" -ForegroundColor Gray
Write-Host ""

# Check if Rancher Desktop is installed
$rancherPath = "$env:USERPROFILE\.rd\bin\rdctl.exe"
if (!(Test-Path $rancherPath)) {
    Write-Host "❌ Rancher Desktop not found!" -ForegroundColor Red
    Write-Host "   Please install Rancher Desktop first:" -ForegroundColor Yellow
    Write-Host "   1. Download from: https://rancherdesktop.io/" -ForegroundColor Yellow
    Write-Host "   2. Install and start Rancher Desktop" -ForegroundColor Yellow
    Write-Host "   3. Ensure 'dockerd (moby)' is selected as container runtime" -ForegroundColor Yellow
    Write-Host "   4. Run this script again" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if Docker is available through Rancher Desktop
try {
    $dockerVersion = docker --version 2>$null
    if (!$dockerVersion) {
        Write-Host "❌ Docker not available through Rancher Desktop!" -ForegroundColor Red
        Write-Host "   Please ensure Rancher Desktop is running:" -ForegroundColor Yellow
        Write-Host "   1. Start Rancher Desktop from Start Menu" -ForegroundColor Yellow
        Write-Host "   2. Wait for it to fully start (2-3 minutes)" -ForegroundColor Yellow
        Write-Host "   3. Ensure 'dockerd (moby)' is selected as container runtime" -ForegroundColor Yellow
        Write-Host "   4. Run this script again" -ForegroundColor Yellow
        Read-Host "Press Enter to exit"
        exit 1
    }
    Write-Host "✅ Rancher Desktop and Docker are available" -ForegroundColor Green
} catch {
    Write-Host "❌ Error checking Docker availability" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if setup has been run
if (!(Test-Path ".env")) {
    Write-Host "⚠️  First time setup required!" -ForegroundColor Yellow
    Write-Host "   Running setup.ps1..." -ForegroundColor Gray
    & ".\setup.ps1"

    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Setup failed. Please check the errors above." -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
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
