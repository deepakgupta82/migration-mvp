# Nagarro AgentiMigrate Platform - Windows Run Script
[CmdletBinding()]
param (
    [switch]$SkipBuild,
    [switch]$StopOnly,
    [switch]$Reset,
    [switch]$HealthCheck
)

Write-Host "🚀 Nagarro AgentiMigrate Platform - Windows Runner" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

# Create logs directory if it doesn't exist
if (!(Test-Path "logs")) {
    New-Item -ItemType Directory -Path "logs" -Force | Out-Null
}

Start-Transcript -Path "logs/platform.log" -Append
Write-Host "Starting Nagarro AgentiMigrate Platform operations..."

# Check Rancher Desktop and determine Docker Compose command
Write-Host "🔍 Checking Rancher Desktop and Docker availability..." -ForegroundColor Yellow

# Check if Rancher Desktop is installed
$rancherPath = "$env:USERPROFILE\.rd\bin\rdctl.exe"
if (!(Test-Path $rancherPath)) {
    Write-Host "❌ Rancher Desktop not found. Please install it first." -ForegroundColor Red
    Write-Host "   Download from: https://rancherdesktop.io/" -ForegroundColor Yellow
    Write-Host "   Then run: .\setup.ps1" -ForegroundColor Yellow
    exit 1
}

# Check if Docker is available
try {
    $dockerVersion = docker --version 2>$null
    if (!$dockerVersion) {
        Write-Host "❌ Docker not available. Please ensure Rancher Desktop is running." -ForegroundColor Red
        Write-Host "   1. Start Rancher Desktop from Start Menu" -ForegroundColor Yellow
        Write-Host "   2. Wait for it to fully start (2-3 minutes)" -ForegroundColor Yellow
        Write-Host "   3. Ensure 'dockerd (moby)' is selected as container runtime" -ForegroundColor Yellow
        exit 1
    }
    Write-Host "✅ Docker available: $dockerVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Error: Docker not available through Rancher Desktop" -ForegroundColor Red
    exit 1
}

# Determine Docker Compose command
try {
    docker compose version > $null 2>&1
    if ($LASTEXITCODE -eq 0) {
        $DOCKER_COMPOSE = "docker compose"
    } else {
        docker-compose --version > $null 2>&1
        if ($LASTEXITCODE -eq 0) {
            $DOCKER_COMPOSE = "docker-compose"
        } else {
            Write-Host "❌ Error: Docker Compose not available" -ForegroundColor Red
            Write-Host "   Please ensure Rancher Desktop is properly configured" -ForegroundColor Yellow
            exit 1
        }
    }
    Write-Host "✅ Using: $DOCKER_COMPOSE" -ForegroundColor Green
} catch {
    Write-Host "❌ Error: Docker Compose not available" -ForegroundColor Red
    exit 1
}

# Handle different operation modes
if ($HealthCheck) {
    Write-Host "🏭 Running health check..." -ForegroundColor Yellow
    & ".\health-check.bat"
    exit 0
}

if ($StopOnly) {
    Write-Host "🛑 Stopping platform..." -ForegroundColor Yellow
    & $DOCKER_COMPOSE down --remove-orphans
    Write-Host "✅ Platform stopped" -ForegroundColor Green
    exit 0
}

if ($Reset) {
    Write-Host "💥 Resetting platform (removing all data)..." -ForegroundColor Red
    $confirm = Read-Host "Are you sure? This will remove all data (y/N)"
    if ($confirm -eq "y" -or $confirm -eq "Y") {
        & $DOCKER_COMPOSE down -v --remove-orphans
        docker system prune -f
        Write-Host "✅ Platform reset complete" -ForegroundColor Green
    } else {
        Write-Host "❌ Reset cancelled" -ForegroundColor Yellow
    }
    exit 0
}

# Check prerequisites
Write-Host "🔍 Checking prerequisites..." -ForegroundColor Yellow

# Check if .env file exists and has API key
if (!(Test-Path ".env")) {
    Write-Host "❌ .env file not found. Please run setup.ps1 first." -ForegroundColor Red
    exit 1
}

$envContent = Get-Content ".env" -Raw
if ($envContent -match "your_openai_api_key_here") {
    Write-Host "⚠️  Warning: OpenAI API key not configured in .env file" -ForegroundColor Yellow
    Write-Host "   The platform will not work without a valid API key." -ForegroundColor Yellow
    Write-Host "   Please edit .env and add your OpenAI API key." -ForegroundColor Yellow
    $continue = Read-Host "   Continue anyway? (y/N)"
    if ($continue -ne "y" -and $continue -ne "Y") {
        exit 1
    }
}

# Create necessary directories
Write-Host "📁 Creating necessary directories..." -ForegroundColor Yellow
$directories = @("minio_data", "postgres_data")
foreach ($dir in $directories) {
    if (!(Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "   Created: $dir" -ForegroundColor Gray
    }
}

# Stop any running containers
Write-Host "🛑 Stopping any running containers..." -ForegroundColor Yellow
& $DOCKER_COMPOSE down --remove-orphans 2>$null

# Build services if not skipped
if (-not $SkipBuild) {
    Write-Host "📦 Building services..." -ForegroundColor Yellow

    # Enable BuildKit
    $env:DOCKER_BUILDKIT = "1"
    $env:COMPOSE_DOCKER_CLI_BUILD = "1"

    # Build all services
    Write-Host "   Building all services with optimized caching..." -ForegroundColor Gray
    & $DOCKER_COMPOSE build --build-arg BUILDKIT_INLINE_CACHE=1

    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Build failed. Check the logs above for details." -ForegroundColor Red
        exit 1
    }

    Write-Host "✅ All services built successfully" -ForegroundColor Green
} else {
    Write-Host "⏭️ Skipping build as requested" -ForegroundColor Yellow
}

# Start the platform
Write-Host "🚀 Starting the platform..." -ForegroundColor Yellow
& $DOCKER_COMPOSE up -d

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to start platform. Check logs with: $DOCKER_COMPOSE logs" -ForegroundColor Red
    exit 1
}

# Wait a moment for services to start
Write-Host "   Waiting for services to start..." -ForegroundColor Gray
Start-Sleep -Seconds 10

# Check service status
Write-Host "📊 Checking service status..." -ForegroundColor Yellow
& $DOCKER_COMPOSE ps

Write-Host ""
Write-Host "🎉 Nagarro AgentiMigrate Platform is starting up!" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "🌍 Access URLs:" -ForegroundColor Cyan
Write-Host "   • Frontend (Command Center): http://localhost:3000" -ForegroundColor Yellow
Write-Host "   • Backend API: http://localhost:8000" -ForegroundColor Yellow
Write-Host "   • Project Service: http://localhost:8002" -ForegroundColor Yellow
Write-Host "   • Reporting Service: http://localhost:8003" -ForegroundColor Yellow
Write-Host "   • MegaParse Service: http://localhost:5001" -ForegroundColor Yellow
Write-Host "   • Neo4j Browser: http://localhost:7474" -ForegroundColor Yellow
Write-Host "   • Weaviate: http://localhost:8080" -ForegroundColor Yellow
Write-Host "   • MinIO Console: http://localhost:9001" -ForegroundColor Yellow
Write-Host ""
Write-Host "🔑 Default Credentials:" -ForegroundColor Cyan
Write-Host "   • Neo4j: neo4j / password" -ForegroundColor Gray
Write-Host "   • MinIO: minioadmin / minioadmin" -ForegroundColor Gray
Write-Host ""
Write-Host "🔍 Management Commands:" -ForegroundColor Cyan
Write-Host "   • Check status: $DOCKER_COMPOSE ps" -ForegroundColor Gray
Write-Host "   • View logs: $DOCKER_COMPOSE logs -f [service_name]" -ForegroundColor Gray
Write-Host "   • Stop platform: $DOCKER_COMPOSE down" -ForegroundColor Gray
Write-Host "   • Health check: .\health-check.bat" -ForegroundColor Gray
Write-Host "   • Reset platform: .\run-mvp.ps1 -Reset" -ForegroundColor Gray
Write-Host ""

Stop-Transcript
