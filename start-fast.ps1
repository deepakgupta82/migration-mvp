# =====================================================================================
# Nagarro AgentiMigrate Platform - Fast Startup (Clean Version)
# =====================================================================================

[CmdletBinding()]
param (
    [switch]$StopOnly,
    [switch]$Minimal
)

Write-Host "Fast Platform Startup" -ForegroundColor Cyan
Write-Host "=====================" -ForegroundColor Cyan

# Determine Docker Compose command
if (Get-Command "docker" -ErrorAction SilentlyContinue) {
    try {
        docker compose version | Out-Null
        $DOCKER_COMPOSE = "docker compose"
    } catch {
        $DOCKER_COMPOSE = "docker-compose"
    }
} else {
    Write-Host "ERROR: Docker is not available" -ForegroundColor Red
    exit 1
}

Write-Host "Using: $DOCKER_COMPOSE" -ForegroundColor Gray

# Handle stop-only request
if ($StopOnly) {
    Write-Host "Stopping platform..." -ForegroundColor Yellow
    & $DOCKER_COMPOSE.Split() down --remove-orphans
    Write-Host "Platform stopped" -ForegroundColor Green
    exit 0
}

# Check if frontend image exists
$frontendExists = docker images -q migration_platform_2-frontend:latest 2>$null
if (-not $frontendExists) {
    Write-Host "ERROR: Frontend image not found" -ForegroundColor Red
    Write-Host "Please run: docker compose build frontend" -ForegroundColor Yellow
    exit 1
}

Write-Host "Frontend image found" -ForegroundColor Green

# Start infrastructure services
Write-Host "Starting infrastructure services..." -ForegroundColor Yellow
try {
    & $DOCKER_COMPOSE.Split() up -d postgres neo4j weaviate minio
    Write-Host "Infrastructure services started" -ForegroundColor Green
} catch {
    Write-Host "Failed to start infrastructure services" -ForegroundColor Red
    exit 1
}

# Wait for infrastructure
Write-Host "Waiting for infrastructure..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# Start frontend
Write-Host "Starting frontend..." -ForegroundColor Yellow
try {
    & $DOCKER_COMPOSE.Split() up -d frontend
    Write-Host "Frontend started" -ForegroundColor Green
} catch {
    Write-Host "Failed to start frontend" -ForegroundColor Red
    exit 1
}

# Check status
Write-Host "Checking service status..." -ForegroundColor Yellow
& $DOCKER_COMPOSE.Split() ps

Write-Host ""
Write-Host "Platform started successfully!" -ForegroundColor Green
Write-Host "Frontend: http://localhost:3000" -ForegroundColor Yellow
Write-Host ""
Write-Host "To stop: .\start-fast.ps1 -StopOnly" -ForegroundColor Cyan
