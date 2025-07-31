#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Start Backend Service with proper environment variables
.DESCRIPTION
    Starts the backend service with required authentication and API keys
#>

Write-Host "🚀 Starting Backend Service..." -ForegroundColor Green

# Set environment variables
$env:SERVICE_AUTH_TOKEN = "service-backend-token"
$env:OPENAI_API_KEY = "your-openai-key-here"
$env:LLM_PROVIDER = "openai"
$env:OPENAI_MODEL_NAME = "gpt-4o"

# Change to backend directory
Set-Location "backend"

Write-Host "📋 Environment Variables:" -ForegroundColor Yellow
Write-Host "  SERVICE_AUTH_TOKEN: $env:SERVICE_AUTH_TOKEN" -ForegroundColor Cyan
Write-Host "  OPENAI_API_KEY: $($env:OPENAI_API_KEY.Substring(0,8))..." -ForegroundColor Cyan
Write-Host "  LLM_PROVIDER: $env:LLM_PROVIDER" -ForegroundColor Cyan
Write-Host "  OPENAI_MODEL_NAME: $env:OPENAI_MODEL_NAME" -ForegroundColor Cyan

Write-Host "🔄 Starting service (this may take 10-15 minutes to load AI models)..." -ForegroundColor Yellow
Write-Host "⏳ Please be patient while AI models are loading..." -ForegroundColor Magenta

try {
    python -m app.main
} catch {
    Write-Host "❌ Error starting backend service: $_" -ForegroundColor Red
    exit 1
}
