# Document Processing Monitor - PowerShell Wrapper
# This script runs the document processing monitor and log streamer

param(
    [string]$Mode = "full",  # "full", "monitor", "logs"
    [string]$CorrelationId = ""
)

# Set console encoding for proper output
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "🚀 Document Processing Monitor" -ForegroundColor Green
Write-Host "=" * 60 -ForegroundColor Yellow

# Check if Python is available
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✅ Python detected: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python not found. Please install Python 3.7+ and add it to PATH." -ForegroundColor Red
    exit 1
}

# Check if required packages are installed
Write-Host "🔍 Checking required packages..." -ForegroundColor Cyan

$requiredPackages = @("requests", "websockets", "asyncio")
$missingPackages = @()

foreach ($package in $requiredPackages) {
    try {
        python -c "import $package" 2>$null
        Write-Host "✅ $package" -ForegroundColor Green
    } catch {
        $missingPackages += $package
        Write-Host "❌ $package (missing)" -ForegroundColor Red
    }
}

if ($missingPackages.Count -gt 0) {
    Write-Host "📦 Installing missing packages..." -ForegroundColor Yellow
    foreach ($package in $missingPackages) {
        Write-Host "Installing $package..." -ForegroundColor Cyan
        pip install $package
    }
}

# Get the script directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$monitorScript = Join-Path $scriptDir "monitor_document_processing.py"
$logStreamScript = Join-Path $scriptDir "stream_processing_logs.py"

# Check if scripts exist
if (-not (Test-Path $monitorScript)) {
    Write-Host "❌ Monitor script not found: $monitorScript" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $logStreamScript)) {
    Write-Host "❌ Log stream script not found: $logStreamScript" -ForegroundColor Red
    exit 1
}

Write-Host "=" * 60 -ForegroundColor Yellow

switch ($Mode.ToLower()) {
    "full" {
        Write-Host "🎯 Running full monitoring (upload + process + logs)" -ForegroundColor Green
        
        # Start log streamer in background
        Write-Host "📡 Starting log streamer..." -ForegroundColor Cyan
        $logStreamJob = Start-Job -ScriptBlock {
            param($script, $correlationId)
            if ($correlationId) {
                python $script $correlationId
            } else {
                python $script
            }
        } -ArgumentList $logStreamScript, $CorrelationId
        
        # Wait a moment for log streamer to start
        Start-Sleep -Seconds 2
        
        # Run main monitor
        Write-Host "🔍 Starting document processing monitor..." -ForegroundColor Cyan
        python $monitorScript
        
        # Stop log streamer
        Write-Host "🛑 Stopping log streamer..." -ForegroundColor Yellow
        Stop-Job $logStreamJob -PassThru | Remove-Job
    }
    
    "monitor" {
        Write-Host "🔍 Running document processing monitor only" -ForegroundColor Green
        python $monitorScript
    }
    
    "logs" {
        Write-Host "📡 Running log streamer only" -ForegroundColor Green
        if ($CorrelationId) {
            Write-Host "🔗 Filtering by correlation ID: $CorrelationId" -ForegroundColor Cyan
            python $logStreamScript $CorrelationId
        } else {
            Write-Host "📋 Streaming all logs" -ForegroundColor Cyan
            python $logStreamScript
        }
    }
    
    default {
        Write-Host "❌ Invalid mode: $Mode" -ForegroundColor Red
        Write-Host "Valid modes: full, monitor, logs" -ForegroundColor Yellow
        exit 1
    }
}

Write-Host "=" * 60 -ForegroundColor Yellow
Write-Host "✅ Script execution completed!" -ForegroundColor Green