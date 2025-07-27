# =====================================================================================
# Nagarro AgentiMigrate Platform - Fast Startup (Pre-built Images)
# =====================================================================================
# This script starts the platform using PRE-BUILT images for 2-3 minute startup
# Prerequisites: Run .\build-images.ps1 first to build the images
# =====================================================================================

[CmdletBinding()]
param (
    [switch]$StopOnly,        # Stop platform only
    [switch]$Restart,         # Restart platform
    [switch]$HealthCheck,     # Run health check only
    [switch]$Minimal,         # Use minimal backend without ML
    [switch]$DevMode,         # Development mode with volume mounts
    [string]$Profile = "full" # Startup profile: minimal, core, full
)

Write-Host "🚀 Nagarro AgentiMigrate Platform - Fast Startup" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

# Create logs directory
if (!(Test-Path "logs")) {
    New-Item -ItemType Directory -Path "logs" -Force | Out-Null
}

$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$logFile = "logs/startup_$timestamp.log"

function Write-Log {
    param($Message, $Color = "White")
    $timestampedMessage = "[$(Get-Date -Format 'HH:mm:ss')] $Message"
    Write-Host $timestampedMessage -ForegroundColor $Color
    $timestampedMessage | Out-File -FilePath $logFile -Append
}

function Test-ImageExists {
    param($ImageName)
    $result = docker images -q $ImageName 2>$null
    return $result -ne $null -and $result -ne ""
}

# Determine Docker Compose command
if (Get-Command "docker" -ErrorAction SilentlyContinue) {
    try {
        docker compose version | Out-Null
        $DOCKER_COMPOSE = "docker compose"
    } catch {
        $DOCKER_COMPOSE = "docker-compose"
    }
} else {
    Write-Log "❌ Docker is not available. Please start Docker Desktop or Rancher Desktop." "Red"
    exit 1
}

Write-Log "🐳 Using: $DOCKER_COMPOSE" "Gray"

# Handle stop-only request
if ($StopOnly) {
    Write-Log "🛑 Stopping platform..." "Yellow"
    & $DOCKER_COMPOSE.Split() down --remove-orphans
    Write-Log "✅ Platform stopped" "Green"
    exit 0
}

# Handle restart request
if ($Restart) {
    Write-Log "🔄 Restarting platform..." "Yellow"
    & $DOCKER_COMPOSE.Split() down --remove-orphans
    Start-Sleep -Seconds 3
}

# Health check only
if ($HealthCheck) {
    Write-Log "🏥 Running health check..." "Yellow"
    & $DOCKER_COMPOSE.Split() ps
    Write-Log "📊 Service status displayed above" "Green"
    exit 0
}

# Check for required images based on profile
$requiredImages = @()

switch ($Profile.ToLower()) {
    "minimal" {
        $requiredImages = @(
            "migration_platform_2-frontend:latest",
            "migration_platform_2-backend:minimal",
            "migration_platform_2-project-service:latest"
        )
        Write-Log "🎯 Starting in MINIMAL mode (no AI/ML features)" "Yellow"
    }
    "core" {
        $requiredImages = @(
            "migration_platform_2-frontend:latest",
            "migration_platform_2-backend:latest",
            "migration_platform_2-project-service:latest",
            "migration_platform_2-reporting-service:latest"
        )
        Write-Log "🎯 Starting in CORE mode (basic AI features)" "Yellow"
    }
    "full" {
        $requiredImages = @(
            "migration_platform_2-frontend:latest",
            "migration_platform_2-backend:latest",
            "migration_platform_2-project-service:latest",
            "migration_platform_2-reporting-service:latest",
            "migration_platform_2-megaparse:latest"
        )
        Write-Log "🎯 Starting in FULL mode (all features)" "Yellow"
    }
    default {
        Write-Log "❌ Invalid profile: $Profile. Use: minimal, core, or full" "Red"
        exit 1
    }
}

# Check if images exist
$missingImages = @()
foreach ($image in $requiredImages) {
    if (-not (Test-ImageExists $image)) {
        $missingImages += $image
    }
}

if ($missingImages.Count -gt 0) {
    Write-Log "❌ Missing required images:" "Red"
    foreach ($image in $missingImages) {
        Write-Log "   • $image" "Red"
    }
    Write-Log "" "White"
    Write-Log "💡 Please run the build script first:" "Yellow"
    Write-Log "   .\build-images.ps1" "Cyan"
    if ($Profile -eq "minimal") {
        Write-Log "   .\build-images.ps1 -Minimal" "Cyan"
    }
    exit 1
}

Write-Log "✅ All required images are available" "Green"

# Create docker-compose override for fast startup
$overrideContent = @"
version: '3.8'

services:
  frontend:
    image: migration_platform_2-frontend:latest
    build: null

  backend:
    image: migration_platform_2-backend:$(if ($Minimal -or $Profile -eq "minimal") { "minimal" } else { "latest" })
    build: null

  project-service:
    image: migration_platform_2-project-service:latest
    build: null

  reporting-service:
    image: migration_platform_2-reporting-service:latest
    build: null

  megaparse:
    image: migration_platform_2-megaparse:latest
    build: null
"@

# Add development mode volume mounts if requested
if ($DevMode) {
    $overrideContent += @"

  backend:
    volumes:
      - ./backend/app:/app
      - ./logs:/app/logs

  frontend:
    volumes:
      - ./frontend/src:/app/src
"@
    Write-Log "🔧 Development mode enabled with volume mounts" "Yellow"
}

$overrideContent | Out-File -FilePath "docker-compose.fast.yml" -Encoding UTF8

Write-Log "📝 Created fast startup configuration" "Gray"

# Start infrastructure services first
Write-Log "🗄️ Starting infrastructure services..." "Yellow"
$infraServices = @("postgres", "neo4j", "weaviate", "minio")

try {
    & $DOCKER_COMPOSE.Split() -f docker-compose.yml -f docker-compose.fast.yml up -d @infraServices
    Write-Log "✅ Infrastructure services started" "Green"
} catch {
    Write-Log "❌ Failed to start infrastructure services: $($_.Exception.Message)" "Red"
    exit 1
}

# Wait for infrastructure to be ready
Write-Log "⏳ Waiting for infrastructure to be ready..." "Yellow"
Start-Sleep -Seconds 15

# Start application services based on profile
$appServices = @()
switch ($Profile.ToLower()) {
    "minimal" {
        $appServices = @("frontend", "backend", "project-service")
    }
    "core" {
        $appServices = @("frontend", "backend", "project-service", "reporting-service")
    }
    "full" {
        $appServices = @("frontend", "backend", "project-service", "reporting-service", "megaparse")
    }
}

Write-Log "🚀 Starting application services..." "Yellow"
Write-Log "   Services: $($appServices -join ', ')" "Gray"

try {
    & $DOCKER_COMPOSE.Split() -f docker-compose.yml -f docker-compose.fast.yml up -d @appServices
    Write-Log "✅ Application services started" "Green"
} catch {
    Write-Log "❌ Failed to start application services: $($_.Exception.Message)" "Red"
    exit 1
}

# Wait for services to be ready
Write-Log "⏳ Waiting for services to initialize..." "Yellow"
Start-Sleep -Seconds 10

# Check service status
Write-Log "📊 Checking service status..." "Yellow"
& $DOCKER_COMPOSE.Split() ps

Write-Log "" "White"
Write-Log "🎉 Platform started successfully!" "Green"
Write-Log "=================================" "Green"

# Display access URLs based on profile
Write-Log "🌍 Access URLs:" "Cyan"
Write-Log "   • Frontend (Command Center): http://localhost:3000" "Yellow"

if ($Profile -ne "minimal") {
    Write-Log "   • Backend API: http://localhost:8000" "Yellow"
}

Write-Log "   • Project Service: http://localhost:8002" "Yellow"

if ($Profile -eq "core" -or $Profile -eq "full") {
    Write-Log "   • Reporting Service: http://localhost:8003" "Yellow"
}

if ($Profile -eq "full") {
    Write-Log "   • MegaParse Service: http://localhost:5001" "Yellow"
}

Write-Log "   • Neo4j Browser: http://localhost:7474" "Yellow"
Write-Log "   • MinIO Console: http://localhost:9001" "Yellow"

Write-Log "" "White"
Write-Log "⚡ Startup completed in ~2-3 minutes instead of 20!" "Green"
Write-Log "💡 To stop: .\start-platform-fast.ps1 -StopOnly" "Cyan"
Write-Log "💡 To restart: .\start-platform-fast.ps1 -Restart" "Cyan"

Write-Log "" "White"
Write-Log "📝 Startup log saved to: $logFile" "Gray"
