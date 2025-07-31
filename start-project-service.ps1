#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Start Project Service with proper environment variables
.DESCRIPTION
    Starts the project service with required authentication token
#>

Write-Host "🚀 Starting Project Service..." -ForegroundColor Green

# Set environment variables
$env:SERVICE_AUTH_TOKEN = "service-backend-token"

# Change to project service directory
Set-Location "project-service"

Write-Host "📋 Environment Variables:" -ForegroundColor Yellow
Write-Host "  SERVICE_AUTH_TOKEN: $env:SERVICE_AUTH_TOKEN" -ForegroundColor Cyan

Write-Host "🔄 Starting service..." -ForegroundColor Yellow
try {
    python main.py
} catch {
    Write-Host "❌ Error starting project service: $_" -ForegroundColor Red
    exit 1
}
