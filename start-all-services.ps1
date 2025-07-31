#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Start all platform services in the correct order
.DESCRIPTION
    Starts project service, backend service, and frontend with proper environment variables
#>

Write-Host "🚀 Starting Nagarro's Ascent Platform Services..." -ForegroundColor Green

# Function to check if a port is in use
function Test-Port {
    param([int]$Port)
    try {
        $connection = New-Object System.Net.Sockets.TcpClient
        $connection.Connect("localhost", $Port)
        $connection.Close()
        return $true
    } catch {
        return $false
    }
}

# Check if infrastructure is running
Write-Host "🔍 Checking infrastructure services..." -ForegroundColor Yellow
$infraPorts = @(5432, 7474, 8080, 9000)  # PostgreSQL, Neo4j, Weaviate, MinIO
$infraRunning = $true

foreach ($port in $infraPorts) {
    if (-not (Test-Port $port)) {
        Write-Host "❌ Infrastructure service on port $port is not running" -ForegroundColor Red
        $infraRunning = $false
    }
}

if (-not $infraRunning) {
    Write-Host "⚠️  Please start infrastructure services first:" -ForegroundColor Yellow
    Write-Host "   docker-compose up -d postgres neo4j weaviate minio" -ForegroundColor Cyan
    exit 1
}

Write-Host "✅ Infrastructure services are running" -ForegroundColor Green

# Start Project Service
Write-Host "`n📦 Starting Project Service..." -ForegroundColor Yellow
Start-Process pwsh -ArgumentList "-File", "start-project-service.ps1" -WindowStyle Normal

# Wait for project service to start
Write-Host "⏳ Waiting for project service to start..." -ForegroundColor Magenta
do {
    Start-Sleep -Seconds 2
} while (-not (Test-Port 8002))
Write-Host "✅ Project Service is running on port 8002" -ForegroundColor Green

# Start Backend Service
Write-Host "`n🧠 Starting Backend Service..." -ForegroundColor Yellow
Start-Process pwsh -ArgumentList "-File", "start-backend-service.ps1" -WindowStyle Normal

Write-Host "⏳ Backend service is starting (this takes 10-15 minutes)..." -ForegroundColor Magenta
Write-Host "   You can continue with other tasks while it loads" -ForegroundColor Cyan

# Start Frontend (if not already running)
if (-not (Test-Port 3000)) {
    Write-Host "`n🎨 Starting Frontend..." -ForegroundColor Yellow
    Set-Location "frontend"
    Start-Process pwsh -ArgumentList "-Command", "npm start" -WindowStyle Normal
    Set-Location ".."
    
    Write-Host "⏳ Waiting for frontend to start..." -ForegroundColor Magenta
    do {
        Start-Sleep -Seconds 2
    } while (-not (Test-Port 3000))
    Write-Host "✅ Frontend is running on port 3000" -ForegroundColor Green
} else {
    Write-Host "✅ Frontend is already running on port 3000" -ForegroundColor Green
}

Write-Host "`n🎉 Platform services are starting!" -ForegroundColor Green
Write-Host "📊 Access URLs:" -ForegroundColor Yellow
Write-Host "   Frontend: http://localhost:3000" -ForegroundColor Cyan
Write-Host "   Project Service: http://localhost:8002/docs" -ForegroundColor Cyan
Write-Host "   Backend API: http://localhost:8000/docs (available when loaded)" -ForegroundColor Cyan

Write-Host "`n⏰ Backend Status:" -ForegroundColor Yellow
Write-Host "   The backend service is loading AI models and may take 10-15 minutes" -ForegroundColor Magenta
Write-Host "   You can use the frontend immediately for project management" -ForegroundColor Cyan
Write-Host "   AI features will be available once backend is fully loaded" -ForegroundColor Cyan
